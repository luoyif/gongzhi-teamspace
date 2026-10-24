"""Append-only, task-scoped trace. No credentials or hidden reasoning capture."""
from __future__ import annotations
import json,re,asyncio,threading
from .store import Problem,dump,now,uid

_SECRET_KEYS=re.compile(r'(?i)(api.?key|authorization|password|secret|access.?token|refresh.?token|cookie)')
_TOKEN=re.compile(r'(?i)(?:oc_sk_|sk-[a-z0-9]|Bearer\s+)[A-Za-z0-9_./+\-=]{8,}')

def redact(value,secrets=(),limit=600000):
 def clean(x):
  if isinstance(x,dict):return {str(k):('[redacted]' if _SECRET_KEYS.search(str(k)) else clean(v)) for k,v in x.items()}
  if isinstance(x,(list,tuple)):return [clean(v) for v in x[:300]]
  if isinstance(x,str):
   for secret in secrets:
    if secret:x=x.replace(secret,'[redacted]')
   return _TOKEN.sub('[redacted]',x)[:limit]
  if x is None or isinstance(x,(int,float,bool)):return x
  return clean(str(x))
 return clean(value)

_listeners={};_listeners_lock=threading.RLock()
def subscribe_run(rid):
 event=asyncio.Event();item=(asyncio.get_running_loop(),event)
 with _listeners_lock:_listeners.setdefault(rid,set()).add(item)
 def close():
  with _listeners_lock:
   group=_listeners.get(rid)
   if group is not None:
    group.discard(item)
    if not group:_listeners.pop(rid,None)
 return event,close
def notify_run(rid):
 with _listeners_lock:items=tuple(_listeners.get(rid,()))
 for loop,event in items:
  if not loop.is_closed():
   try:loop.call_soon_threadsafe(event.set)
   except RuntimeError:pass

class RunTrace:
 def __init__(self,store,run_id,secrets=()):self.store,self.run_id,self.secrets=store,run_id,tuple(secrets)
 def emit(self,layer,event,payload=None,span_id=None,parent_span=None):
  if layer not in ('human','input','agent','model','tool','output','control'):raise ValueError('invalid trace layer')
  data=redact(payload or {},self.secrets)
  encoded=dump(data)
  if len(encoded)>700000:data={'truncated':True,'preview':encoded[:650000]}
  with self.store.connection(True) as c:
   seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 FROM team_run_events WHERE run_id=?',(self.run_id,)).fetchone()[0]
   if seq>12000:raise Problem(429,'Trace事件超过本次上限，运行停止')
   span_id=span_id or uid('span_')
   c.execute('INSERT INTO team_run_events VALUES(?,?,?,?,?,?,?,?)',(self.run_id,seq,layer,event,span_id,parent_span,dump(data),now()))
  notify_run(self.run_id)
  return span_id
 def account(self,usage):
  with self.store.connection(True) as c:c.execute('UPDATE team_runs SET usage_json=? WHERE id=?',(dump(usage) if usage else None,self.run_id))


def require_run(store,p,run_id,actor,write=False):
 with store.connection() as c:
  member=store.require(c,p,actor,write=write)
  row=c.execute('SELECT * FROM team_runs WHERE id=? AND project_id=?',(run_id,p)).fetchone()
  if not row:raise Problem(404,'运行不存在或不可见')
  return dict(row),member


def read_events(store,p,run_id,actor,after=0,limit=500):
 row,_=require_run(store,p,run_id,actor)
 with store.connection() as c:
  events=[]
  for raw in c.execute('SELECT * FROM team_run_events WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?',(run_id,after,min(limit,500))):
   e=dict(raw);e['payload']=json.loads(e.pop('payload_json'));events.append(e)
  latest=c.execute('SELECT COALESCE(MAX(seq),0) FROM team_run_events WHERE run_id=?',(run_id,)).fetchone()[0]
  pending=[{'id':x['id'],'tool_name':x['tool_name'],'arguments':json.loads(x['args_json']),'requested_at':x['requested_at']} for x in c.execute("SELECT * FROM team_tool_approvals WHERE run_id=? AND status='pending'",(run_id,))]
 return {'items':events,'latest_seq':latest,'status':row['status'],'task_id':json.loads(row['request_json']).get('task_id'),'approvals':pending,'has_more':bool(events and events[-1]['seq']<latest)}


def decide_approval(store,p,run_id,id,actor,approve):
 if type(approve) is not bool:raise Problem(422,'approve必须是布尔值')
 with store.connection(True) as c:
  member=store.require(c,p,actor,write=True)
  run=c.execute('SELECT * FROM team_runs WHERE id=? AND project_id=?',(run_id,p)).fetchone()
  if not run:raise Problem(404,'运行不存在')
  if actor!=run['actor_id'] and member['role']!='owner':raise Problem(403,'只有本次发起人或项目管理员可批准工具')
  if run['status']!='running':raise Problem(409,'运行已结束')
  changed=c.execute("UPDATE team_tool_approvals SET status=?,decided_at=?,decided_by=? WHERE id=? AND run_id=? AND status='pending'",('approved' if approve else 'denied',now(),actor,id,run_id)).rowcount
  if not changed:raise Problem(409,'审批不存在或已经处理')
 RunTrace(store,run_id).emit('control','approval.decision',{'approval_id':id,'actor_id':actor,'approved':approve},parent_span=run_id)
 return {'ok':True,'approved':approve}
