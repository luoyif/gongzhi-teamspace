"""Loss-aware model-input compaction; raw tool evidence remains in scoped Trace.
No paid summarizer or retry. Preserve tool-call/result pairing and latest instructions.
"""
from __future__ import annotations
import json,hashlib
from langchain_core.messages import AIMessage,ToolMessage,HumanMessage,SystemMessage
from langchain_core.tools import StructuredTool
from .store import dump,Problem

class OutputLimitPause(Exception):pass

def small_json(value,limit=900):
 if isinstance(value,dict):
  keep={k:v for k,v in value.items() if k in ('id','document_id','title','filename','revision','path','offset','next_offset','total_characters','has_more','status','operation','sha256','duplicate','syntax_valid','executed','functional_tests_run')}
  if 'content' in value:keep['excerpt']=str(value['content'])[:300]
  if 'items' in value:keep['item_count']=len(value['items']);keep['items_preview']=value['items'][:2]
  text=dump(keep)
 else:text=str(value)
 return text[:limit]

def compact_history(messages,max_chars=32000):
 """Only change the next request, never persisted graph/transcript/Trace evidence."""
 before=sum(len(str(m.content))+len(dump(getattr(m,'tool_calls',[]))) for m in messages)
 tools=[i for i,m in enumerate(messages) if isinstance(m,ToolMessage)];recent=set(tools[-2:]);completed={m.tool_call_id for m in messages if isinstance(m,ToolMessage)};out=[];changed=0
 for i,m in enumerate(messages):
  if isinstance(m,ToolMessage):
   text=m.content if isinstance(m.content,str) else dump(m.content);limit=5000 if i in recent else 700
   if len(text)>limit:
    try:d=json.loads(text)
    except (TypeError,ValueError):d=text
    note=small_json(d,limit)+'\n【工具正文已从工作上下文压缩；完整回执保留。需要细节用tool_result_read(call_id="'+str(m.tool_call_id)+'",offset=0,length=4000)。不要重新执行写入。】'
    m=m.model_copy(update={'content':note});changed+=1
  elif isinstance(m,AIMessage) and m.tool_calls:
   calls=[]
   for call in m.tool_calls:
    c=dict(call);args=c.get('args',{})
    if c.get('id') in completed and len(dump(args))>1200:
     kept={k:v for k,v in args.items() if k in ('path','document_id','filename','section_id','expected_revision','offset','length','query') and len(str(v))<500};kept['_archived_arguments']={'characters':len(dump(args)),'sha256':hashlib.sha256(dump(args).encode()).hexdigest(),'readback_call_id':c['id']};c['args']=kept;changed+=1
    calls.append(c)
   content=m.content
   if isinstance(content,str) and len(content)>1200:content=content[:900]+'\n【此前过程文本已摘录；调用与结果另有记录】';changed+=1
   m=m.model_copy(update={'tool_calls':calls,'content':content,'additional_kwargs':{k:v for k,v in m.additional_kwargs.items() if k!='tool_calls'}})
  out.append(m)
 after=sum(len(str(m.content))+len(dump(getattr(m,'tool_calls',[]))) for m in out)
 if after>max_chars:
  # Keep newest rounds intact; shorten older turns with explicit task read-back pointers.
  latest_human=max((i for i,m in enumerate(out) if isinstance(m,HumanMessage)),default=-1)
  for i,m in enumerate(out[:-4]):
   if after<=max_chars:break
   if isinstance(m,SystemMessage) or (isinstance(m,HumanMessage) and (i==latest_human or str(m.content).startswith('本次请求：'))):continue
   text=m.content if isinstance(m.content,str) else dump(m.content)
   if len(text)<=700:continue
   shortened=text[:450]+'\n【较早上下文原文已保留；用task_conversation_read或tool_result_read回读，不从头重做。】'
   out[i]=m.model_copy(update={'content':shortened});after-=len(text)-len(shortened);changed+=1
 return out,{'before_characters':before,'after_characters':after,'compressed_messages':changed,'method':'extractive_tool_offload','raw_evidence_preserved':True,'additional_model_calls':0}

def build_readback(store,registry,cfg):
 async def tool_result_read(call_id:str,offset:int=0,length:int=4000,run_id:str='')->str:
  """Read a previously observed tool result without executing the tool again. Same task only. Use for compacted raw results; writes are never replayed."""
  if not isinstance(call_id,str) or len(call_id)>200 or type(offset) is not int or offset<0 or type(length) is not int or not 1<=length<=6000:raise Problem(422,'回执读取参数无效')
  p,actor,tid=cfg['_project_id'],cfg['_actor_id'],cfg['conversation_task_id'];rid=run_id or cfg['_run_id']
  with store.connection() as c:
   from .task_conversation import require_task
   require_task(store,c,p,tid,actor)
   row=c.execute("SELECT request_json FROM team_runs WHERE id=? AND project_id=?",(rid,p)).fetchone()
   if not row or json.loads(row[0]).get('task_id')!=tid:raise Problem(404,'只可读取当前任务的工具回执')
   ev=c.execute("SELECT payload_json FROM team_run_events WHERE run_id=? AND span_id=? AND event='tool.result' ORDER BY seq DESC LIMIT 1",(rid,call_id)).fetchone()
   if not ev:raise Problem(404,'工具回执尚不存在')
   payload=json.loads(ev[0]);text=payload.get('content','');text=text if isinstance(text,str) else dump(text)
   request_event=c.execute("SELECT payload_json FROM team_run_events WHERE run_id=? AND span_id=? AND event='tool.request' ORDER BY seq DESC LIMIT 1",(rid,call_id)).fetchone()
   arguments=json.loads(request_event[0]).get('arguments',{}) if request_event else {}
   if payload.get('name')=='project_read_document':registry.resolve_document(p,actor,arguments.get('document_id'),c)
   if payload.get('name')=='project_file_read':
    from .project_space import ProjectSpace
    ProjectSpace(store,p,actor).read(arguments.get('path',''),0,1)
  try:data=json.loads(text)
  except ValueError:data={}
  if isinstance(data,dict):
   docs=[]
   if data.get('document_id'):docs.append(data['document_id'])
   if payload.get('name') in ('project_search','project_rag_search'):
    docs += [d.get('document_id') for d in data.get('items',[]) if isinstance(d,dict)]
   for source in data.get('sources',[]):
    if isinstance(source,dict) and source.get('document_id'):docs.append(source['document_id'])
   for did in set(docs):registry.resolve_document(p,actor,did)
  elif isinstance(data,list):
   for d in data:
    if isinstance(d,dict) and d.get('document_id'):registry.resolve_document(p,actor,d['document_id'])
  return dump({'run_id':rid,'call_id':call_id,'tool':payload.get('name'),'content':text[offset:offset+length],'offset':offset,'total_characters':len(text),'has_more':offset+length<len(text),'next_offset':offset+length if offset+length<len(text) else None,'reexecuted':False})
 return StructuredTool.from_function(coroutine=tool_result_read,name='tool_result_read')
