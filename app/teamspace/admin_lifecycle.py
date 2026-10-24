"""Administrator lifecycle: reversible deletion, live ACL, no physical data erasure."""
from __future__ import annotations
import json
from typing import Any
from fastapi import APIRouter,Body,Depends
from octop.api.deps import current_user,get_server
from .store import Problem,dump,now,uid
from .platform_api import registry
router=APIRouter()
SCHEMA='''CREATE TABLE IF NOT EXISTS team_admin_trash(
 target_id TEXT PRIMARY KEY,kind TEXT NOT NULL,workspace_id TEXT NOT NULL,project_id TEXT,
 title TEXT NOT NULL,previous_json TEXT NOT NULL,deleted_by INTEGER NOT NULL,
 deleted_at TEXT NOT NULL,batch_id TEXT NOT NULL,restored_at TEXT);
 CREATE INDEX IF NOT EXISTS team_trash_scope ON team_admin_trash(workspace_id,restored_at);
'''

def gone(c,id):
 return bool(c.execute('SELECT 1 FROM team_admin_trash WHERE target_id=? AND restored_at IS NULL',(id,)).fetchone())

def project_admin(s,c,p,actor,allow_deleted=False):
 if not allow_deleted:s.require(c,p,actor)
 else:
  if not c.execute('SELECT 1 FROM team_members WHERE project_id=? AND user_id=?',(p,actor)).fetchone():raise Problem(404,'项目不存在或无权管理')
 link=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(p,)).fetchone()
 if not link:raise Problem(404,'项目没有团队归属')
 member=s.workspace_require(c,link[0],actor,write=True)
 role=c.execute('SELECT role FROM team_members WHERE project_id=? AND user_id=?',(p,actor)).fetchone()
 if member['role']!='owner' and (not role or role[0]!='owner'):raise Problem(403,'只有团队或项目管理员可以删除与恢复')
 return link[0]

def idle(c,p):
 if c.execute("SELECT 1 FROM team_runs WHERE project_id=? AND status IN ('queued','running')",(p,)).fetchone():raise Problem(409,'项目中有正在运行的 AI，请先停止执行再删除')

def remember(c,row,kind,w,p,actor,batch,extra=None):
 id=row['id'];title=row.get('title',row.get('name',id));snapshot={'row':dict(row),'extra':extra or {}}
 c.execute('INSERT INTO team_admin_trash VALUES(?,?,?,?,?,?,?,?,?,NULL) ON CONFLICT(target_id) DO UPDATE SET kind=excluded.kind,workspace_id=excluded.workspace_id,project_id=excluded.project_id,title=excluded.title,previous_json=excluded.previous_json,deleted_by=excluded.deleted_by,deleted_at=excluded.deleted_at,batch_id=excluded.batch_id,restored_at=NULL',(id,kind,w,p,title,dump(snapshot),actor,now(),batch))

def withdraw_sources(c,p,document_ids=None):
 count=0
 for r in c.execute("SELECT id,source_json FROM team_public_knowledge WHERE status='published'").fetchall():
  source=json.loads(r['source_json'])
  if source.get('project_id')==p and (document_ids is None or source.get('document_id') in document_ids):
   c.execute("UPDATE team_public_knowledge SET status='withdrawn',updated_at=? WHERE id=?",(now(),r['id']));count+=1
 return count

def delete_project(s,p,actor,body):
 with s.connection(True) as c:
  w=project_admin(s,c,p,actor,True)
  if gone(c,p):return {'id':p,'deleted':True,'duplicate':True}
  row=c.execute('SELECT * FROM team_projects WHERE id=?',(p,)).fetchone();s.revision(row,body);idle(c,p)
  if body.get('confirm_title')!=row['title']:raise Problem(422,'请输入完整项目名称确认删除')
  count=withdraw_sources(c,p);remember(c,dict(row),'project',w,p,actor,p,{'withdrawn_public_snapshots':count})
  c.execute('UPDATE team_projects SET revision=revision+1,updated_at=? WHERE id=?',(now(),p));s.touch(c,p)
 return {'id':p,'deleted':True,'recoverable':True,'withdrawn_public_snapshots':count,'originals_preserved':True}

def delete_object(s,id,actor,body):
 with s.connection(True) as c:
  row=c.execute('SELECT * FROM team_objects WHERE id=?',(id,)).fetchone()
  if not row:raise Problem(404,'记录不存在')
  p=row['project_id'];w=project_admin(s,c,p,actor);idle(c,p)
  if gone(c,id):return {'id':id,'deleted':True,'duplicate':True}
  s.revision(row,body);kind=row['kind']
  if kind not in ('task','event','document','proposal'):raise Problem(422,'此记录类型不能删除')
  targets=[dict(row)]
  if kind=='task':
   pending={id};seen={id}
   all_tasks=[dict(x) for x in c.execute("SELECT * FROM team_objects WHERE project_id=? AND kind='task' AND status!='deleted'",(p,))]
   while pending:
    next_rows=[x for x in all_tasks if x['id'] not in seen and json.loads(x['data_json']).get('parent_id') in pending]
    targets+=next_rows;pending={x['id'] for x in next_rows};seen|=pending
  for x in targets:
   if gone(c,x['id']):continue
   if x['kind']=='document' and x['status'] in ('uploaded','parsing'):raise Problem(409,'文件正在解析，请解析完成后再删除')
   remember(c,x,x['kind'],w,p,actor,id)
   c.execute("UPDATE team_objects SET status='deleted',revision=revision+1,updated_at=? WHERE id=?",(now(),x['id']))
   if x['kind']=='document':c.execute('DELETE FROM team_fts WHERE document_id=?',(x['id'],))
  n=withdraw_sources(c,p,[id]) if kind=='document' else 0;s.touch(c,p)
 return {'id':id,'deleted':True,'recoverable':True,'affected_objects':len(targets),'withdrawn_public_snapshots':n,'shared_files_preserved':kind=='task'}

def asset_references(r,c,a):
 refs=[];id=a['id']
 if c.execute('SELECT 1 FROM team_platform_defaults WHERE model_id=?',(id,)).fetchone():refs.append('公司默认模型')
 for raw in c.execute("SELECT * FROM team_platform_assets WHERE kind='agent' AND id!=?",(id,)):
  if gone(c,raw['id']):continue
  x=r.row(raw)
  if id in r.dependency_ids(x):refs.append('AI员工：'+x['name'])
 for raw in c.execute('SELECT project_id,asset_id,bundle_json FROM team_platform_bindings WHERE enabled=1'):
  if gone(c,raw['project_id']):continue
  if any(x['id']==id for x in json.loads(raw['bundle_json'])['assets']):refs.append('项目授权（请先取消绑定）')
 return refs

def delete_asset(r,id,actor,body):
 s=r.store
 with s.connection(True) as c:
  a=r._raw(c,id);r.manage(c,a['workspace_id'],actor)
  if gone(c,id):return {'id':id,'deleted':True,'duplicate':True}
  r._visible(c,a,actor);s.revision(a,body)
  if a['kind']=='agent':
   bindings=c.execute('SELECT * FROM team_platform_bindings WHERE asset_id=? AND enabled=1',(id,)).fetchall()
   for b in bindings:
    if gone(c,b['project_id']):continue
    project_admin(s,c,b['project_id'],actor);idle(c,b['project_id'])
   if bindings and body.get('detach_projects') is not True:raise Problem(409,'请确认同时从项目停用这位员工')
   for b in bindings:
    c.execute('INSERT INTO team_platform_binding_history VALUES(?,?,?,?,?)',(b['project_id'],id,b['revision'],dump(dict(b)),now()))
    c.execute('UPDATE team_platform_bindings SET enabled=0,revision=revision+1,updated_at=? WHERE project_id=? AND asset_id=?',(now(),b['project_id'],id));s.touch(c,b['project_id'])
  else:
   refs=asset_references(r,c,a)
   if refs:raise Problem(409,'仍被使用，不能删除：'+'；'.join(refs[:6]))
  raw=dict(c.execute('SELECT * FROM team_platform_assets WHERE id=?',(id,)).fetchone())
  remember(c,raw,'asset',a['workspace_id'],None,actor,id,{'asset_kind':a['kind']})
  c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(id,a['revision'],dump(a),now()))
  c.execute('UPDATE team_platform_assets SET enabled=0,revision=revision+1,updated_at=? WHERE id=?',(now(),id))
  if c.execute("SELECT 1 FROM sqlite_master WHERE name='team_vendor_models'").fetchone():c.execute('UPDATE team_vendor_models SET archived=1 WHERE asset_id=?',(id,))
 return {'id':id,'deleted':True,'recoverable':True,'restore_enabled':False,'historical_runs_preserved':True}

def delete_provider(r,id,actor,body):
 from .model_providers import provider_get
 v=provider_get(r,id,actor,True)
 with r.store.connection(True) as c:
  r.manage(c,v['workspace_id'],actor)
  if gone(c,id):return {'id':id,'deleted':True,'duplicate':True}
  r.store.revision(v,body)
  if c.execute('SELECT 1 FROM team_vendor_models WHERE provider_id=? AND archived=0',(id,)).fetchone():raise Problem(409,'请先移除该厂商下的模型，再删除厂商连接')
  if c.execute("SELECT 1 FROM team_model_probe_jobs WHERE provider_id=? AND status='running'",(id,)).fetchone():raise Problem(409,'请先停止模型连接测试')
  remember(c,v,'provider',v['workspace_id'],None,actor,id)
 return {'id':id,'deleted':True,'recoverable':True,'upstream_account_unchanged':True}

def list_trash(s,w,actor):
 with s.connection() as c:
  member=s.workspace_require(c,w,actor);out=[]
  for row in c.execute('SELECT * FROM team_admin_trash WHERE workspace_id=? AND restored_at IS NULL ORDER BY deleted_at DESC',(w,)):
   if row['batch_id']!=row['target_id']:continue
   try:
    if row['project_id']:project_admin(s,c,row['project_id'],actor,True)
    elif member['role']!='owner':continue
   except Problem:continue
   out.append({k:row[k] for k in ('target_id','kind','title','project_id','deleted_at','deleted_by')})
 return out

def restore(s,r,id,actor):
 with s.connection(True) as c:
  entry=c.execute('SELECT * FROM team_admin_trash WHERE target_id=? AND restored_at IS NULL',(id,)).fetchone()
  if not entry:raise Problem(404,'回收站记录不存在或已恢复')
  if entry['batch_id']!=id:raise Problem(409,'请恢复所属的父任务')
  p=entry['project_id'];kind=entry['kind']
  if p:project_admin(s,c,p,actor,True)
  else:s.workspace_require(c,entry['workspace_id'],actor,owner=True)
  if p and kind!='project' and gone(c,p):raise Problem(409,'请先恢复所属项目')
  rows=c.execute('SELECT * FROM team_admin_trash WHERE batch_id=? AND restored_at IS NULL',(id,)).fetchall()
  for item in rows:
   prior=json.loads(item['previous_json'])['row'];target=item['target_id']
   if item['kind']=='project':c.execute('UPDATE team_projects SET revision=revision+1,updated_at=? WHERE id=?',(now(),target))
   elif item['kind']=='asset':
    # Restore only the card, never silently reactivate tools or project bindings.
    c.execute('UPDATE team_platform_assets SET enabled=0,revision=revision+1,updated_at=? WHERE id=?',(now(),target))
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='team_vendor_models'").fetchone():c.execute('UPDATE team_vendor_models SET archived=0 WHERE asset_id=?',(target,))
   elif item['kind']!='provider':
    if item['kind']=='task':
     parent=json.loads(prior['data_json']).get('parent_id')
     if parent and gone(c,parent) and parent not in [x['target_id'] for x in rows]:raise Problem(409,'请先恢复父任务')
    c.execute('UPDATE team_objects SET status=?,revision=revision+1,updated_at=? WHERE id=?',(prior['status'],now(),target))
    if item['kind']=='document' and prior['status']=='ready':s.index(c,target,p,[('恢复资料',prior['body'])],prior['title'])
   c.execute('UPDATE team_admin_trash SET restored_at=? WHERE target_id=?',(now(),target))
  if p:s.touch(c,p)
 return {'id':id,'restored':True,'count':len(rows),'company_knowledge_republished':False,'capabilities_auto_enabled':False}

@router.delete('/projects/{p}')
def project_delete(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return delete_project(registry(server).store,p,user.id,body)
@router.delete('/records/{id}')
def record_delete(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return delete_object(registry(server).store,id,user.id,body)
@router.delete('/platform/assets/{id}')
def asset_delete(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return delete_asset(registry(server),id,user.id,body)
@router.delete('/model-providers/{id}')
def provider_delete(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return delete_provider(registry(server),id,user.id,body)
@router.get('/workspaces/{w}/trash')
def trash(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return {'items':list_trash(registry(server).store,w,user.id),'permanent_erasure':False}
@router.post('/trash/{id}/restore')
def restore_record(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);return restore(r.store,r,id,user.id)
