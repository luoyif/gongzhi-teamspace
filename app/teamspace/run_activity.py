"""Small task-visible execution feed. Detailed Trace stays separate and protected.
SQL projects lightweight metadata, so normal chat never loads model prompts.
"""
from __future__ import annotations
import json
from typing import Any
from fastapi import APIRouter,Depends,Query
from octop.api.deps import current_user,get_server
from .agent_trace import require_run,redact
from .store import dump
router=APIRouter()
EVENTS=('context.compacted','output.truncated','input.progressive_context','run.start','agent.runtime','model.start','model.end','model.error','tool.request','tool.result','tool.error','tool.denied','approval.required','approval.decision','approval.auto','permission.changed','budget.warning','budget.finalizing','output.delta','run.end','run.stop_requested','input.project_workspace','agent.finished','agent.error','input.conversation','output.limit')

def compact_event(event):
 d=event.get('payload') or {};name=event['event']
 keys={
  'run.start':('actor_id','agent_id','agent_name','agent_revision','task_id','selection_mode'),
  'agent.runtime':('name','engine','version','revision'),
  'input.conversation':('task_id','through_seq','included_messages','total_messages','omitted_messages','truncated_sequences','first_seq','last_seq','human_messages','assistant_messages','authors','instruction_mode','instruction_source'),
  'model.start':('step','model'),'model.end':('step','elapsed_ms','finish_reason'),
  'input.project_workspace':('project_id','total_files'),
  'agent.finished':('model_steps','tool_calls','usage'),
 }.get(name)
 if keys is not None:d={k:d[k] for k in keys if k in d}
 elif name=='tool.request':
  args=d.get('arguments') or {};encoded=dump(args)
  d={'name':d.get('name'),'arguments':args if len(encoded)<=1800 else {'preview':encoded[:1800],'truncated':True},'argument_chars':len(encoded)}
 elif name=='tool.result':
  content=d.get('content','');receipt={}
  if isinstance(content,str):
   try:parsed=json.loads(content)
   except (ValueError,TypeError):parsed=None
   if isinstance(parsed,dict):receipt={k:parsed[k] for k in ('id','document_id','revision','path','status','operation','title','filename','has_more','next_offset','total_characters','duplicate') if k in parsed}
  preview=content if isinstance(content,str) else dump(content)
  d={'name':d.get('name'),'status':d.get('status','success'),'elapsed_ms':d.get('elapsed_ms'),'receipt':receipt,'preview':preview[:900],'content_chars':len(preview),'truncated':len(preview)>900}
 return {**event,'payload':d}

def public_run(row):
 cfg=json.loads(row['config_json']);a=cfg.get('agent_snapshot') or {};policy=cfg.get('execution_policy') or {};request=json.loads(row['request_json'])
 return {'id':row['id'],'project_id':row['project_id'],'task_id':request.get('task_id'),'actor_id':row['actor_id'],'agent_name':a.get('name','AI 员工'),'status':row['status'],'error':row['error'],'model':cfg.get('model'),'usage':json.loads(row['usage_json']) if row['usage_json'] else None,'created_at':row['created_at'],'input_seq':row['input_seq'],'permission_mode':policy.get('permission_mode','safe'),'budget':policy.get('budget','configured'),'limits':{k:a.get('data',{}).get(k) for k in ('max_model_steps','max_tool_calls','timeout_seconds')},'budget_limited':bool(cfg.get('budget_limited'))}

def read_activity(store,p,rid,actor,after=0,limit=250):
 row,_=require_run(store,p,rid,actor);events=[]
 with store.connection() as c:
  placeholders=','.join('?' for _ in EVENTS)
  # Heavy prompts are never selected, parsed, or sent through the chat feed.
  sql="""SELECT seq,layer,event,span_id,parent_span,created_at,
   CASE WHEN event='model.start' THEN json_object('step',json_extract(payload_json,'$.step'),'model',json_extract(payload_json,'$.model'))
   WHEN event='run.start' THEN json_object('actor_id',json_extract(payload_json,'$.actor_id'),'agent_name',json_extract(payload_json,'$.agent_name'),'task_id',json_extract(payload_json,'$.task_id'))
   WHEN event='input.project_workspace' THEN json_object('project_id',json_extract(payload_json,'$.project_id'),'total_files',json_extract(payload_json,'$.total_files'))
   WHEN event='input.conversation' THEN json_object('through_seq',json_extract(payload_json,'$.through_seq'),'included_messages',json_extract(payload_json,'$.included_messages'),'total_messages',json_extract(payload_json,'$.total_messages'),'omitted_messages',json_extract(payload_json,'$.omitted_messages'),'human_messages',json_extract(payload_json,'$.human_messages'),'assistant_messages',json_extract(payload_json,'$.assistant_messages'),'instruction_mode',json_extract(payload_json,'$.instruction_mode'),'instruction_source',json_extract(payload_json,'$.instruction_source'))
   ELSE payload_json END AS data FROM team_run_events WHERE run_id=? AND seq>? AND event IN ("""+placeholders+") ORDER BY seq LIMIT ?"
  rows=c.execute(sql,(rid,after,*EVENTS,min(500,limit))).fetchall()
  for raw in rows:
   e=dict(raw);e['run_id']=rid;e['payload']=json.loads(e.pop('data'));events.append(compact_event(e))
  latest=c.execute('SELECT COALESCE(MAX(seq),0) FROM team_run_events WHERE run_id=?',(rid,)).fetchone()[0]
  cursor=events[-1]['seq'] if len(events)==min(500,limit) else latest
  pending=[{'id':x['id'],'tool_name':x['tool_name'],'arguments':json.loads(x['args_json']),'requested_at':x['requested_at']} for x in c.execute("SELECT * FROM team_tool_approvals WHERE run_id=? AND status='pending'",(rid,))]
  run=public_run(row)
  if c.execute("SELECT 1 FROM sqlite_master WHERE name='team_run_controls'").fetchone():
   control=c.execute('SELECT permission_mode FROM team_run_controls WHERE run_id=?',(rid,)).fetchone()
   if control:run['permission_mode']=control[0]
  limited=c.execute("SELECT 1 FROM team_run_events WHERE run_id=? AND event='budget.finalizing' LIMIT 1",(rid,)).fetchone()
  run['budget_limited']=bool(limited)
 return {'items':events,'latest_seq':latest,'cursor':cursor,'status':row['status'],'task_id':run['task_id'],'approvals':pending,'has_more':cursor<latest,'run':run,'hidden_reasoning_included':False}

@router.get('/projects/{p}/runs/{rid}/activity')
def activity(p:str,rid:str,after:int=Query(0,ge=0),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .integration import store_for
 return read_activity(store_for(server),p,rid,user.id,after)
