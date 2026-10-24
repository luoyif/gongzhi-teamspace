"""Team-admin member creation and revocable single-use workspace invitations.
Uses native account password policy. Never creates site administrators or emails invitations.
"""
from __future__ import annotations
import datetime as dt,hashlib,json,secrets
from typing import Any
from fastapi import APIRouter,Body,Depends
from octop.api.deps import current_user,get_server
from octop.infra.users.identity import Role
from .api import store_for,account_fields,profile,session,_account_lock
from .store import Problem,dump,now,uid
router=APIRouter();public_router=APIRouter()
SCHEMA='''CREATE TABLE IF NOT EXISTS team_company_invites(
 id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL,workspace_id TEXT NOT NULL,
 role TEXT NOT NULL,category TEXT NOT NULL,projects_json TEXT NOT NULL,created_by INTEGER NOT NULL,
 created_at TEXT NOT NULL,expires_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',used_by INTEGER);
CREATE TABLE IF NOT EXISTS team_member_profiles(workspace_id TEXT NOT NULL,user_id INTEGER NOT NULL,
 category TEXT NOT NULL DEFAULT 'member',PRIMARY KEY(workspace_id,user_id));'''
def prepare(s):
 with s.connection() as c:c.executescript(SCHEMA)
def options(body):
 role=body.get('role','member');category=body.get('category','member');projects=body.get('project_ids',[])
 if role not in ('member','viewer'):raise Problem(422,'新成员仅能设为成员或只读；不能创建系统管理员')
 if category not in ('member','learner'):raise Problem(422,'成员类型无效')
 if not isinstance(projects,list) or len(projects)>50 or any(not isinstance(x,str) for x in projects):raise Problem(422,'项目选择格式无效')
 return role,category,list(dict.fromkeys(projects))
def authorize(s,c,w,actor,projects):
 s.workspace_require(c,w,actor,owner=True)
 for p in projects:
  s.require(c,p,actor,owner=True)
  row=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(p,)).fetchone()
  if not row or row[0]!=w:raise Problem(404,'项目不属于当前团队')
def enrol(s,c,w,user,role,category,projects):
 s._ensure_workspace_member(c,w,user,role)
 c.execute('INSERT INTO team_member_profiles VALUES(?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET category=excluded.category',(w,user.id,category))
 for p in projects:
  c.execute('INSERT OR IGNORE INTO team_members VALUES(?,?,?,?,?)',(p,user.id,user.username,user.display_name or user.username,role));s.touch(c,p)
def invite(s,c,token):
 if not isinstance(token,str) or len(token)>256:raise Problem(404,'邀请无效')
 row=c.execute('SELECT * FROM team_company_invites WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
 if not row or row['status']!='pending' or row['expires_at']<now():raise Problem(404,'邀请已使用、撤回或过期')
 d=dict(row);d['projects']=json.loads(d['projects_json']);authorize(s,c,d['workspace_id'],d['created_by'],d['projects']);return d
@router.get('/workspaces/{w}/people')
def people(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s)
 with s.connection() as c:
  member=s.workspace_require(c,w,user.id);items=[]
  for raw in c.execute('SELECT m.*,COALESCE(p.category,\'member\') AS category FROM team_workspace_members m LEFT JOIN team_member_profiles p ON p.workspace_id=m.workspace_id AND p.user_id=m.user_id WHERE m.workspace_id=? ORDER BY m.user_id',(w,)):
   item=dict(raw);item['projects']=[dict(x) for x in c.execute('SELECT p.id,p.title,m.role FROM team_members m JOIN team_projects p ON p.id=m.project_id JOIN team_project_workspace pw ON pw.project_id=p.id JOIN team_members viewer ON viewer.project_id=p.id AND viewer.user_id=? WHERE pw.workspace_id=? AND m.user_id=?',(user.id,w,item['user_id']))];items.append(item)
  invitations=[]
  if member['role']=='owner':
   for raw in c.execute('SELECT id,role,category,projects_json,created_at,expires_at,status FROM team_company_invites WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100',(w,)):
    d=dict(raw);d['project_ids']=json.loads(d.pop('projects_json'));d['status']='expired' if d['status']=='pending' and d['expires_at']<now() else d['status'];invitations.append(d)
 return {'items':items,'invitations':invitations,'can_manage':member['role']=='owner'}
@router.post('/workspaces/{w}/accounts',status_code=201)
async def create_account(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s);role,category,projects=options(body);username,password,name=account_fields(body)
 async with _account_lock:
  with s.connection() as c:authorize(s,c,w,user.id,projects)
  if server.services.user_repo.get_by_username(username) is not None:raise Problem(409,'用户名已存在；请使用添加已有成员，不会修改其密码')
  created=await server.user_manager.create(username=username,password=password,role=Role.USER,display_name=name,locale='zh')
  try:
   with s.connection(True) as c:authorize(s,c,w,user.id,projects);enrol(s,c,w,created,role,category,projects)
  except Exception:
   # Account creation raced an authorization change. Disable only this NEW account.
   await server.user_manager.disable(created.username)
   raise
 return {'user':profile(created),'category':category,'project_ids':projects,'password_returned':False,'message':'账号已创建；请安全告知登录凭证，成员可自行修改密码'}
@router.post('/workspaces/{w}/company-invites',status_code=201)
def create_invite(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s);role,category,projects=options(body);token=secrets.token_urlsafe(32);id=uid('wi_');expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=72)).isoformat(timespec='milliseconds')
 with s.connection(True) as c:
  authorize(s,c,w,user.id,projects)
  c.execute('INSERT INTO team_company_invites(id,token_hash,workspace_id,role,category,projects_json,created_by,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?)',(id,hashlib.sha256(token.encode()).hexdigest(),w,role,category,dump(projects),user.id,now(),expires))
 return {'id':id,'token':token,'expires_at':expires,'single_use':True,'project_ids':projects}
@router.delete('/workspaces/{w}/company-invites/{id}')
def revoke_invite(w:str,id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s)
 with s.connection(True) as c:
  s.workspace_require(c,w,user.id,owner=True)
  n=c.execute("UPDATE team_company_invites SET status='revoked' WHERE id=? AND workspace_id=? AND status='pending'",(id,w)).rowcount
  if not n:raise Problem(409,'邀请不存在或已经处理')
 return {'ok':True}
@public_router.post('/workspace-redeem',status_code=201)
async def redeem(body:dict=Body(...),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s);username,password,name=account_fields(body)
 async with _account_lock:
  with s.connection() as c:inv=invite(s,c,body.get('token'))
  if server.services.user_repo.get_by_username(username) is not None:raise Problem(409,'账号已存在，请登录后接受邀请')
  created=await server.user_manager.create(username=username,password=password,role=Role.USER,display_name=name,locale='zh')
  try:
   with s.connection(True) as c:
    inv=invite(s,c,body.get('token'));enrol(s,c,inv['workspace_id'],created,inv['role'],inv['category'],inv['projects'])
    c.execute("UPDATE team_company_invites SET status='used',used_by=? WHERE id=?",(created.id,inv['id']))
  except Exception:
   await server.user_manager.disable(created.username);raise
 return dict(session(server,created),workspace_id=inv['workspace_id'])
@router.post('/workspace-invites/join')
async def join(body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s)
 async with _account_lock:
  with s.connection(True) as c:
   inv=invite(s,c,body.get('token'));enrol(s,c,inv['workspace_id'],user,inv['role'],inv['category'],inv['projects']);c.execute("UPDATE team_company_invites SET status='used',used_by=? WHERE id=?",(user.id,inv['id']))
 return {'workspace_id':inv['workspace_id']}
@router.put('/workspaces/{w}/people/{target}/projects')
def assign_projects(w:str,target:int,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=store_for(server);prepare(s);role,_,projects=options(body)
 with s.connection(True) as c:
  authorize(s,c,w,user.id,projects)
  member=s.workspace_require(c,w,target)
  for p in projects:
   c.execute('INSERT OR IGNORE INTO team_members VALUES(?,?,?,?,?)',(p,target,member['username'],member['display_name'],role));s.touch(c,p)
 return {'ok':True,'project_ids':projects,'existing_roles_not_escalated':True}
