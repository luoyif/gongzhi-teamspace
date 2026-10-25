"""M2 bounded same-task Agent-to-Agent handoffs with explicit human approval.

One handoff per source Run; no automatic agent reply loops, no token spends until
approval. Each hop has its own immutable Run, current ACL and a stable idempotency key.
"""
from __future__ import annotations
import datetime,hashlib,json
from typing import Any
from fastapi import APIRouter, Body, Depends
from octop.api.deps import current_user,get_server
from .api import store_for, controller
from .store import Problem,dump,now,uid,require_text
from .task_conversation import require_task

router=APIRouter()
MAX_HOPS=2
SCHEMA="""
CREATE TABLE IF NOT EXISTS team_task_agent_handoffs(
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL,
 task_id TEXT NOT NULL,
 source_run_id TEXT NOT NULL,
 source_message_id TEXT NOT NULL,
 source_agent_id TEXT NOT NULL,
 target_agent_id TEXT NOT NULL,
 target_agent_revision INTEGER NOT NULL,
 requested_by INTEGER NOT NULL,
 instruction TEXT NOT NULL,
 input_hash TEXT NOT NULL,
 chain_id TEXT NOT NULL,
 hop INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 target_run_id TEXT,
 approved_by INTEGER,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(project_id,source_run_id)
);
CREATE INDEX IF NOT EXISTS team_handoffs_task ON team_task_agent_handoffs(task_id,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS team_handoffs_target_run ON team_task_agent_handoffs(target_run_id) WHERE target_run_id IS NOT NULL;
"""
def _row(c,p,tid,hid):
 row=c.execute('SELECT * FROM team_task_agent_handoffs WHERE id=? AND project_id=? AND task_id=?',(hid,p,tid)).fetchone()
 if not row:raise Problem(404,'交接请求不存在或不可访问')
 return dict(row)

def _public(row):
 return {key:row.get(key) for key in (
  'id','task_id','source_run_id','source_message_id','source_agent_id',
  'target_agent_id','target_agent_revision','requested_by','instruction',
  'chain_id','hop','status','target_run_id','approved_by','created_at','updated_at'
 )}

def _source(c,p,tid,runid):
 source=c.execute('SELECT id,project_id,actor_id,kind,status,request_json,config_json FROM team_runs WHERE id=? AND project_id=?',(runid,p)).fetchone()
 if not source:raise Problem(404,'来源 Agent Run 不存在')
 request=json.loads(source['request_json'])
 if request.get('task_id')!=tid:raise Problem(404,'来源 Run 不属于当前任务')
 if source['status']!='completed':raise Problem(409,'只有完成的 Agent 运行才能申请交接；失败或暂停的运行需人工核对')
 cfg=json.loads(source['config_json'])
 agent=cfg.get('agent_snapshot') or {}
 if not agent.get('id'):raise Problem(409,'来源运行没有可核验的 Agent 身份')
 output=c.execute("SELECT id,content FROM team_messages WHERE project_id=? AND run_id=? AND kind='assistant' ORDER BY seq DESC LIMIT 1",(p,runid)).fetchone()
 if not output:raise Problem(409,'源 Run 尚无持久化 AI 输出，不能交接')
 return dict(source),agent,dict(output)

def _request_hash(source_run_id,target_id,instruction):
 return hashlib.sha256(dump([source_run_id,target_id,instruction]).encode('utf8')).hexdigest()

@router.get('/tasks/{tid}/handoffs')
def list_handoffs(tid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 with s.connection() as c:
  require_task(s,c,p,tid,user.id)
  items=[_public(dict(r)) for r in c.execute('SELECT * FROM team_task_agent_handoffs WHERE project_id=? AND task_id=? ORDER BY created_at DESC LIMIT 50',(p,tid))]
 return {'items':items,'max_hops':MAX_HOPS,'manual_approval_required':True,'automatic_paid_dispatch':False}

@router.post('/tasks/{tid}/handoffs',status_code=201)
def propose_handoff(tid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 from .platform_registry import PlatformRegistry
 registry=PlatformRegistry(s)
 source_run=require_text(body.get('source_run_id'),'来源运行',128,False)
 target=require_text(body.get('target_agent_id'),'接力员工',128,False)
 instruction=require_text(body.get('instruction'),'明确的交接目标',1500,False)
 with s.connection(True) as c:
  require_task(s,c,p,tid,user.id)
  s.require(c,p,user.id,write=True)
  source,agent,out=_source(c,p,tid,source_run)
  if target==agent['id']:raise Problem(422,'不能将当前工作交给同一位 Agent')
  original=c.execute('SELECT * FROM team_task_agent_handoffs WHERE project_id=? AND source_run_id=?',(p,source_run)).fetchone()
  fingerprint=_request_hash(source_run,target,instruction)
  if original:
   if original['input_hash']!=fingerprint:raise Problem(409,'同一来源已存在不同交接请求；请先处理旧请求')
   return _public(dict(original))
  prior=c.execute("SELECT * FROM team_task_agent_handoffs WHERE target_run_id=? AND status='approved' LIMIT 1",(source_run,)).fetchone()
  hop=(int(prior['hop'])+1) if prior else 1
  if hop>MAX_HOPS:raise Problem(409,'Agent 接力已达到两跳上限，需要真人直接发起新任务')
  chain=prior['chain_id'] if prior else uid('hc_')
  settings=json.loads(c.execute('SELECT settings_json FROM team_projects WHERE id=?',(p,)).fetchone()[0])
  snap=registry.snapshot(c,p,user.id,{'agent_id':target},settings)
  target_snap=snap['agent_snapshot']
  if target_snap.get('id')!=target:raise Problem(409,'所选 Agent 不属于当前公司或已停用')
  stamp=now();hid=uid('hh_')
  c.execute("""INSERT INTO team_task_agent_handoffs
   (id,project_id,task_id,source_run_id,source_message_id,source_agent_id,target_agent_id,
    target_agent_revision,requested_by,instruction,input_hash,chain_id,hop,status,created_at,updated_at)
   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?)""",
   (hid,p,tid,source_run,out['id'],agent['id'],target,target_snap['revision'],user.id,instruction,fingerprint,chain,hop,stamp,stamp))
  return _public(dict(c.execute('SELECT * FROM team_task_agent_handoffs WHERE id=?',(hid,)).fetchone()))

@router.post('/tasks/{tid}/handoffs/{hid}/reject')
def reject_handoff(tid:str,hid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 with s.connection(True) as c:
  s.require(c,p,user.id,owner=True);require_task(s,c,p,tid,user.id)
  entry=_row(c,p,tid,hid)
  if entry['status'] in ('rejected','cancelled'):return _public(entry)
  if entry['status']!='pending':raise Problem(409,'交接已进入执行流程，不能按未批准请求撤回')
  c.execute("UPDATE team_task_agent_handoffs SET status='rejected',updated_at=? WHERE id=?",(now(),hid))
  return _public(_row(c,p,tid,hid))

@router.post('/tasks/{tid}/handoffs/{hid}/cancel')
def cancel_handoff(tid:str,hid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 with s.connection(True) as c:
  s.require(c,p,user.id,write=True);require_task(s,c,p,tid,user.id)
  entry=_row(c,p,tid,hid)
  membership=s.require(c,p,user.id)
  if entry['requested_by']!=user.id and membership['role']!='owner':raise Problem(403,'只能撤销自己发起的交接')
  if entry['status']=='cancelled':return _public(entry)
  if entry['status']!='pending':raise Problem(409,'运行中的交接须另行停止 Agent，不能在这里取消')
  c.execute("UPDATE team_task_agent_handoffs SET status='cancelled',updated_at=? WHERE id=?",(now(),hid))
  return _public(_row(c,p,tid,hid))

@router.post('/tasks/{tid}/handoffs/{hid}/approve')
async def approve_handoff(tid:str,hid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 from .platform_registry import PlatformRegistry
 registry=PlatformRegistry(s)
 with s.connection(True) as c:
  s.require(c,p,user.id,owner=True);require_task(s,c,p,tid,user.id)
  entry=_row(c,p,tid,hid)
  if entry['status']=='approved':
   return _public(entry)
  if entry['status']!='pending':raise Problem(409,'交接并非待批准状态；不自动重发模型运行')
  _source(c,p,tid,entry['source_run_id'])
  if int(entry['hop'])>MAX_HOPS:raise Problem(409,'超过安全接力上限')
  settings=json.loads(c.execute('SELECT settings_json FROM team_projects WHERE id=?',(p,)).fetchone()[0])
  current=registry.snapshot(c,p,user.id,{'agent_id':entry['target_agent_id']},settings)['agent_snapshot']
  if current['revision']!=entry['target_agent_revision']:raise Problem(409,'目标 Agent 已更新；请重新审核目标版本')
  # CAS reserves the handoff. If a crash occurs after reservation, do not
  # automatically resubmit: the operator must inspect the stable client ID.
  c.execute("UPDATE team_task_agent_handoffs SET status='dispatching',approved_by=?,updated_at=? WHERE id=?",
            (user.id,now(),hid))
 safe_prompt=(
  '本次为经项目管理员明确授权的任务内 Agent 接力（第'+str(entry['hop'])+'/'+str(MAX_HOPS)+'跳）。'
  '来源 Run='+entry['source_run_id']+'；来源消息='+entry['source_message_id']+'。'
  '先核查来源 Agent 报告与已有工具回执，未核实的内容不能冒充已完成。'
  '不要重新创建已有文件/日程，不得扩大本任务权限。'
  '目标要求：'+entry['instruction']
 )
 payload={'kind':'chat','task_id':tid,'agent_id':entry['target_agent_id'],
          'agent_revision':entry['target_agent_revision'],'prompt':safe_prompt,
          'client_id':'handoff-'+hid,'continue_from':entry['source_run_id'],
          'run_options':{'budget':'standard','permission_mode':'safe'}}
 try:
  result=controller(server).start_run(p,user,payload)
 except Exception:
  # Reconcile the stable idempotency key: no persisted Run means the
  # controller rejected before dispatch. An existing Run must never be resent.
  with s.connection(True) as c:
   existing=c.execute('SELECT id FROM team_runs WHERE project_id=? AND actor_id=? AND client_id=?',(p,user.id,'handoff-'+hid)).fetchone()
   if existing:
    c.execute("UPDATE team_task_agent_handoffs SET status='approved',target_run_id=?,updated_at=? WHERE id=? AND status='dispatching'",(existing['id'],now(),hid))
   else:
    c.execute("UPDATE team_task_agent_handoffs SET status='pending',approved_by=NULL,updated_at=? WHERE id=? AND status='dispatching'",(now(),hid))
  raise
 with s.connection(True) as c:
  c.execute("UPDATE team_task_agent_handoffs SET status='approved',target_run_id=?,updated_at=? WHERE id=? AND status='dispatching'",
            (result['id'],now(),hid))
  item=_row(c,p,tid,hid)
 try:
  from .task_live import publish
  publish(tid,'handoff',{'handoff_id':hid,'status':'approved'})
 except Exception:
  pass
 return _public(item)



@router.get('/tasks/{tid}/workflow')
def task_workflow(tid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 """Task-local read-only workflow projection; never invent DAG execution."""
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 with s.connection() as c:
  require_task(s,c,p,tid,user.id)
  entries=[dict(r) for r in c.execute(
   'SELECT * FROM team_task_agent_handoffs WHERE project_id=? AND task_id=? ORDER BY created_at',(p,tid))]
  nodes=[]
  for h in entries:
   source=c.execute('SELECT id,status,usage_json,error FROM team_runs WHERE id=? AND project_id=?',
       (h['source_run_id'],p)).fetchone()
   target=c.execute('SELECT id,status,usage_json,error FROM team_runs WHERE id=? AND project_id=?',
       (h['target_run_id'],p)).fetchone() if h['target_run_id'] else None
   nodes.append({'handoff_id':h['id'],'chain_id':h['chain_id'],'hop':h['hop'],
    'source_agent_id':h['source_agent_id'],'target_agent_id':h['target_agent_id'],
    'source_run_id':h['source_run_id'],'source_run_status':source['status'] if source else 'missing',
    'status':h['status'],'approved_by':h['approved_by'],
    'target_run_id':h['target_run_id'],'target_run_status':target['status'] if target else None,
    'known_total_tokens':(json.loads(target['usage_json'] or '{}').get('total_tokens') if target else None),
    'result_adopted':False,
    'source_message_id':h['source_message_id']})
 return {'task_id':tid,'nodes':nodes,'has_executable_dag':False,
         'manual_review_required':True,'status':'history_only' if not nodes else 'available'}


@router.post('/tasks/{tid}/handoffs/{hid}/reconcile')
def reconcile_handoff(tid:str,hid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 """Manual reconciliation of an interrupted dispatch, never a new model call."""
 s=store_for(server);task=s.object(tid,user.id,'task');p=task['project_id']
 with s.connection(True) as c:
  s.require(c,p,user.id,owner=True);require_task(s,c,p,tid,user.id)
  entry=_row(c,p,tid,hid)
  if entry['status']!='dispatching':
   raise Problem(409,'该接力没有需要核对的发送中记录')
  runs=c.execute("SELECT id,status,request_json,config_json FROM team_runs WHERE project_id=? AND client_id=?",
                 (p,'handoff-'+hid)).fetchall()
  if len(runs)>1:raise Problem(409,'同一接力出现重复运行记录，需要人工排查')
  if runs:
   r=dict(runs[0]);request=json.loads(r['request_json']);cfg=json.loads(r['config_json'])
   agent=cfg.get('agent_snapshot') or {}
   if request.get('task_id')!=tid or agent.get('id')!=entry['target_agent_id']:
    raise Problem(409,'运行身份和当前交接不一致，禁止自动采用')
   c.execute("UPDATE team_task_agent_handoffs SET status='approved',target_run_id=?,updated_at=? WHERE id=?",
             (r['id'],now(),hid))
  else:
   c.execute("UPDATE team_task_agent_handoffs SET status='pending',approved_by=NULL,updated_at=? WHERE id=?",
             (now(),hid))
  return _public(_row(c,p,tid,hid))
