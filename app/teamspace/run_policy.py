"""Explicit run-scoped approval modes and bounded budgets; never host privileges.
Full mode is a human project-owner grant for this run's existing tool allowlist.
It does not grant tools, read other projects, alter credentials, or execute shell.
"""
from __future__ import annotations
import copy,json
from typing import Any
from fastapi import APIRouter,Body,Depends
from octop.api.deps import current_user,get_server
from .store import Problem,now,dump
from .agent_trace import require_run,RunTrace
router=APIRouter()
PRESETS={'standard':{'max_model_steps':24,'max_tool_calls':64,'timeout_seconds':900},'extended':{'max_model_steps':48,'max_tool_calls':128,'timeout_seconds':1800}}
SCHEMA='CREATE TABLE IF NOT EXISTS team_run_controls(run_id TEXT PRIMARY KEY,permission_mode TEXT NOT NULL,revision INTEGER NOT NULL,updated_by INTEGER NOT NULL,updated_at TEXT NOT NULL)'

def ensure_schema(store):
 if getattr(store,'_run_controls_ready',False):return
 with store.schema_lock:
  if getattr(store,'_run_controls_ready',False):return
  with store.connection() as c:c.execute(SCHEMA)
  store._run_controls_ready=True

def normalized_options(body):
 value=body.get('run_options')
 if value is None:return None
 if not isinstance(value,dict) or set(value)-{'permission_mode','budget','acknowledge_full_access'}:raise Problem(422,'运行设置格式无效')
 mode=value.get('permission_mode','safe');budget=value.get('budget','configured');ack=value.get('acknowledge_full_access',False)
 if mode not in ('safe','full') or budget not in ('configured',*PRESETS) or type(ack) is not bool:raise Problem(422,'请选择有效的权限模式和执行预算')
 if mode=='full' and ack is not True:raise Problem(422,'完全权限仅对本次已授权工具生效，需要明确确认')
 return {'permission_mode':mode,'budget':budget,'acknowledge_full_access':ack if mode=='full' else False}

def apply_policy(store,c,p,actor,body,cfg):
 options=normalized_options(body)
 if options is None:return cfg  # Preserve historical/API-client execution limits.
 store.require(c,p,actor,write=True)
 if options['permission_mode']=='full':store.require(c,p,actor,owner=True)
 cfg=copy.deepcopy(cfg);data=cfg['agent_snapshot']['data'];original={k:data[k] for k in ('max_model_steps','max_tool_calls','timeout_seconds')}
 if options['budget']!='configured':
  data.update(PRESETS[options['budget']]);data['max_output_tokens']=max(data.get('max_output_tokens',3072),8192)
 cfg['max_output_tokens']=data['max_output_tokens']
 cfg['execution_policy']={**options,'version':1,'authorized_by':actor,'project_id':p,'task_id':body.get('task_id'),'scope':'this_run_existing_tool_allowlist','original_limits':original,'effective_limits':{k:data[k] for k in original},'reserve_final_step':data['max_model_steps']>1,'max_output_tokens':data['max_output_tokens']}
 return cfg

def mode_now(store,cfg):
 policy=cfg.get('execution_policy') or {};mode=policy.get('permission_mode','safe')
 if mode not in ('safe','full'):raise Problem(403,'无效的运行授权')
 with store.connection() as c:
  store.require(c,cfg['_project_id'],cfg['_actor_id'],write=True)
  exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='team_run_controls'").fetchone()
  override=c.execute('SELECT permission_mode FROM team_run_controls WHERE run_id=?',(cfg['_run_id'],)).fetchone() if exists else None
  if override:mode=override[0]
  if mode=='full':
   if policy.get('version')!=1 or policy.get('authorized_by')!=cfg['_actor_id'] or policy.get('project_id')!=cfg['_project_id'] or policy.get('task_id')!=cfg.get('conversation_task_id') or policy.get('acknowledge_full_access') is not True:raise Problem(403,'本次免确认授权不匹配')
   store.require(c,cfg['_project_id'],cfg['_actor_id'],owner=True)
 return mode

def revoke_full(store,p,rid,actor):
 ensure_schema(store)
 with store.connection(True) as c:
  member=store.require(c,p,actor,write=True)
  row=c.execute('SELECT * FROM team_runs WHERE id=? AND project_id=?',(rid,p)).fetchone()
  if not row:raise Problem(404,'运行不存在')
  if row['actor_id']!=actor and member['role']!='owner':raise Problem(403,'只有发起人或项目管理员可收回免确认授权')
  if row['status'] not in ('queued','running'):raise Problem(409,'运行已经结束')
  c.execute("INSERT INTO team_run_controls VALUES(?,'safe',1,?,?) ON CONFLICT(run_id) DO UPDATE SET permission_mode='safe',revision=revision+1,updated_by=excluded.updated_by,updated_at=excluded.updated_at",(rid,actor,now()))
 RunTrace(store,rid).emit('control','permission.changed',{'permission_mode':'safe','actor_id':actor,'inflight_tool_not_rolled_back':True},parent_span=rid)
 return {'permission_mode':'safe','applies_to':'subsequent_tool_calls','inflight_tool_not_rolled_back':True}

@router.post('/projects/{p}/runs/{rid}/permission-mode')
def change_mode(p:str,rid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 if body.get('permission_mode')!='safe':raise Problem(422,'运行中只能切回安全模式；升级权限需明确发起新运行')
 from .integration import store_for
 return revoke_full(store_for(server),p,rid,user.id)
