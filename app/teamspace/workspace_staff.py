"""Team-published staff can be @mentioned without creating project bindings.
Explicit pins/exclusions and restricted legacy grants still take precedence.
Every run freezes configuration, while project data permissions remain live.
"""
import json
from .store import Problem

def implicit_binding(registry,c,p,aid,actor):
 root=registry.get(aid,actor,c=c)
 if root['kind']!='agent' or root['visibility']!='workspace':raise Problem(404,'此员工不是团队共享员工；专属员工需管理员授权')
 bundle=registry._bundle(c,root,p,actor)
 return {'project_id':p,'asset_id':aid,'asset_revision':root['revision'],'revision':0,'enabled':True,'bundle':bundle,'implicit':True,'availability':'workspace_shared'}

def extend_staff(registry,c,p,actor,out,kind=None):
 w=registry.workspace_for_project(c,p,actor);explicit={r['asset_id'] for r in c.execute('SELECT asset_id FROM team_platform_bindings WHERE project_id=?',(p,))}
 for r in c.execute("SELECT id FROM team_platform_assets WHERE workspace_id=? AND kind='agent' AND visibility='workspace' AND enabled=1 ORDER BY created_at,id",(w,)):
  if r['id'] in explicit:continue
  try:b=implicit_binding(registry,c,p,r['id'],actor)
  except Problem:continue
  for frozen in b['bundle']['assets']:
   a=registry.effective_agent(b['bundle']) if frozen['id']==b['asset_id'] else dict(frozen)
   if kind and a['kind']!=kind:continue
   a.update(binding_revision=0,canonical_scope='workspace',availability='workspace_shared',latest_revision=a['revision'],update_available=False)
   out.setdefault(a['id'],a)

def assert_implicit(registry,c,cfg):
 info=cfg['platform_binding'];p=cfg['_project_id'];actor=cfg['_actor_id'];registry.store.require(c,p,actor,write=True)
 exclusion=c.execute('SELECT enabled,revision FROM team_platform_bindings WHERE project_id=? AND asset_id=?',(p,info['asset_id'])).fetchone()
 if exclusion and not exclusion[0]:raise Problem(409,'此员工已在项目中停用')
 if exclusion and exclusion['revision']!=info.get('binding_revision',0):raise Problem(409,'此员工的项目可用性已变化，旧运行停止')
 for aid,version in info['versions'].items():
  current=registry._raw(c,aid);registry._usable_in(c,current,p,actor)
  if current['kind']=='agent' and current['visibility']!='workspace':raise Problem(409,'团队员工共享已撤回')
  if current['kind'] in ('model','mcp') and current['revision']!=version:raise Problem(409,'连接配置已变化；停止旧运行，请重新确认后发起')
