"""User-managed project folders; metadata only, immutable blobs and document IDs.
Folder edits use optimistic revisions. Project ACL/recycle checks are never cached.
"""
from __future__ import annotations
import json,re,unicodedata
from typing import Any
from fastapi import APIRouter,Depends,Body,Query
from octop.api.deps import current_user,get_server
from .store import Problem,now,uid,dump
router=APIRouter()
SCHEMA='''
CREATE TABLE IF NOT EXISTS team_file_folders(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,parent_id TEXT NOT NULL DEFAULT '',
 name TEXT NOT NULL,name_key TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,
 deleted INTEGER NOT NULL DEFAULT 0,created_by INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS team_folder_unique ON team_file_folders(project_id,parent_id,name_key) WHERE deleted=0;
CREATE TABLE IF NOT EXISTS team_file_locations(
 document_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,folder_id TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_file_operations(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,actor_id INTEGER NOT NULL,action TEXT NOT NULL,
 details_json TEXT NOT NULL,created_at TEXT NOT NULL);
'''
def label(value):
 if not isinstance(value,str):raise Problem(422,'文件夹名称必须是文本')
 name=unicodedata.normalize('NFC',value).strip()
 if not name or len(name)>64 or name in ('.','..') or name.startswith('.') or re.search(r'[\\/:*?"<>|\x00-\x1f\x7f]',name) or name.endswith(('.', ' ')):raise Problem(422,'文件夹名需为1–64字，不能包含路径分隔符或特殊控制字符')
 if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'{x}{i}' for x in ('COM','LPT') for i in range(1,10)]}:raise Problem(422,'此名称是系统保留名称')
 return name

def folder(c,p,id):
 if not id:return None
 r=c.execute('SELECT * FROM team_file_folders WHERE id=? AND project_id=? AND deleted=0',(id,p)).fetchone()
 if not r:raise Problem(404,'文件夹不存在或不属于当前项目')
 return dict(r)

def folder_map(c,p):return {r['id']:dict(r) for r in c.execute('SELECT * FROM team_file_folders WHERE project_id=? AND deleted=0 ORDER BY name_key,id',(p,))}
def chain(items,id):
 out=[];seen=set()
 while id:
  if id in seen or id not in items:raise Problem(409,'文件夹层级已变化，请刷新')
  seen.add(id);out.append(items[id]);id=items[id]['parent_id']
  if len(out)>8:raise Problem(422,'文件夹最多8层')
 return list(reversed(out))

def paths(c,p):
 items=folder_map(c,p);return {id:'/'.join(x['name'] for x in chain(items,id)) for id in items}

def log(s,c,p,actor,action,details):
 c.execute('INSERT INTO team_file_operations VALUES(?,?,?,?,?,?)',(uid('fo_'),p,actor,action,dump(details),now()));s.touch(c,p)

def create_folder(s,p,actor,body):
 name=label(body.get('name'));parent=body.get('parent_id') or ''
 with s.connection(True) as c:
  s.require(c,p,actor,write=True);folder(c,p,parent);items=folder_map(c,p)
  if len(items)>=1000:raise Problem(422,'单项目最多1000个文件夹')
  if len(chain(items,parent))>=8:raise Problem(422,'文件夹最多8层')
  if len('/'.join([x['name'] for x in chain(items,parent)]+[name]))>160:raise Problem(422,'目录路径过长，请缩短名称')
  if c.execute('SELECT 1 FROM team_file_folders WHERE project_id=? AND parent_id=? AND name_key=? AND deleted=0',(p,parent,name.casefold())).fetchone():raise Problem(409,'同一位置已存在同名文件夹')
  id=uid('f_');stamp=now();c.execute('INSERT INTO team_file_folders VALUES(?,?,?,?,?,1,0,?,?,?)',(id,p,parent,name,name.casefold(),actor,stamp,stamp))
  log(s,c,p,actor,'folder.create',{'id':id,'name':name,'parent_id':parent});return folder(c,p,id)

def update_folder(s,p,actor,id,body):
 with s.connection(True) as c:
  s.require(c,p,actor,write=True);old=folder(c,p,id)
  if not old:raise Problem(422,'根目录不能修改')
  s.revision(old,body);name=label(body.get('name',old['name']));parent=body.get('parent_id',old['parent_id']) or '';folder(c,p,parent)
  items=folder_map(c,p)
  if id==parent or id in [x['id'] for x in chain(items,parent)]:raise Problem(422,'不能把文件夹移动到自己或子文件夹中')
  items[id]={**old,'parent_id':parent,'name':name}
  for item in items:
   if len('/'.join(x['name'] for x in chain(items,item)))>160:raise Problem(422,'目录路径过长，请缩短名称')
  if c.execute('SELECT 1 FROM team_file_folders WHERE project_id=? AND parent_id=? AND name_key=? AND deleted=0 AND id!=?',(p,parent,name.casefold(),id)).fetchone():raise Problem(409,'目标位置存在同名文件夹')
  c.execute('UPDATE team_file_folders SET name=?,name_key=?,parent_id=?,revision=revision+1,updated_at=? WHERE id=?',(name,name.casefold(),parent,now(),id))
  log(s,c,p,actor,'folder.update',{'id':id,'before':old,'name':name,'parent_id':parent});return folder(c,p,id)

def remove_folder(s,p,actor,id,body):
 with s.connection(True) as c:
  s.require(c,p,actor,owner=True);old=folder(c,p,id)
  if not old:raise Problem(422,'不能删除根目录')
  s.revision(old,body)
  # Includes soft-deleted documents: preserve their original location for restore.
  if c.execute('SELECT 1 FROM team_file_folders WHERE parent_id=? AND deleted=0',(id,)).fetchone() or c.execute('SELECT 1 FROM team_file_locations WHERE folder_id=?',(id,)).fetchone():raise Problem(409,'请先移出文件和子文件夹；回收站文件恢复后也需移出，避免丢失恢复位置')
  c.execute('UPDATE team_file_folders SET deleted=1,revision=revision+1,updated_at=? WHERE id=?',(now(),id));log(s,c,p,actor,'folder.delete',{'id':id,'name':old['name']})
 return {'id':id,'deleted':True,'files_deleted':0}

def move_documents(s,p,actor,body):
 selected=body.get('items');target=body.get('folder_id') or ''
 if not isinstance(selected,list) or not 1<=len(selected)<=100:raise Problem(422,'每次选择1–100个文件')
 with s.connection(True) as c:
  s.require(c,p,actor,write=True);folder(c,p,target);out=[];seen=set()
  for item in selected:
   if not isinstance(item,dict) or item.get('id') in seen:raise Problem(422,'文件选择无效或重复')
   id=item.get('id');seen.add(id);doc=s.object_row(c,id,actor,True,'document')
   if doc['project_id']!=p:raise Problem(404,'不能跨项目移动文件')
   old=c.execute('SELECT * FROM team_file_locations WHERE document_id=?',(id,)).fetchone();revision=old['revision'] if old else 0
   if type(item.get('location_revision')) is not int or item['location_revision']!=revision:raise Problem(409,'文件位置已被其他成员修改，请刷新后重试')
   c.execute('INSERT INTO team_file_locations VALUES(?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET folder_id=excluded.folder_id,revision=team_file_locations.revision+1,updated_at=excluded.updated_at',(id,p,target,revision+1,now()))
   out.append({'id':id,'folder_id':target,'location_revision':revision+1,'previous_folder_id':old['folder_id'] if old else ''})
  log(s,c,p,actor,'files.move',out)
 return {'items':out,'document_ids_unchanged':True,'content_revisions_unchanged':True}

def document_locations(c,p):return {x['document_id']:dict(x) for x in c.execute('SELECT * FROM team_file_locations WHERE project_id=?',(p,))}
def safe_filename(title):
 name=re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]','_',title).strip(' .')[:64]
 return name or 'document'

def apply_locations(c,p,entries):
 folders=paths(c,p);locations=document_locations(c,p);used=set()
 for item in entries:
  id=item.get('document_id');loc=locations.get(id);fid=loc['folder_id'] if loc else '';name=safe_filename(item.get('title',''))
  item['folder_id']=fid;item['location_revision']=loc['revision'] if loc else 0
  item['display_path']=(folders.get(fid,'')+'/' if fid else '')+name
  if fid:
   old=item['path'];candidate='files/'+folders[fid]+'/'+name+('' if name.lower().endswith('.md') else '.md')
   if candidate.casefold() in used:candidate=candidate[:-3]+'--'+id[-8:]+'.md'
   item['legacy_path']=old;item['path']=candidate
  used.add(item['path'].casefold())
 return entries

def browse(s,p,actor,folder_id='',query='',offset=0,limit=100):
 from .project_space import ProjectSpace
 with s.connection() as c:
  member=s.require(c,p,actor);folder(c,p,folder_id);fm=folder_map(c,p);trail=chain(fm,folder_id)
  allfolders=[{**f,'path':'/'.join(x['name'] for x in chain(fm,id))} for id,f in fm.items()]
 # Directory manifest contains only metadata, not all file bodies.
 space=ProjectSpace(s,p,actor);manifest=space.manifest(limit=200);items=list(manifest['items'])
 while manifest['has_more']:
  manifest=space.manifest(offset=manifest['next_offset'],limit=200);items.extend(manifest['items'])
 items=[x for x in items if x.get('document_id') and x['kind']!='company']
 if query:items=[x for x in items if query.casefold() in (x['title']+' '+x.get('display_path','')).casefold()]
 else:items=[x for x in items if x.get('folder_id','')==folder_id]
 items.sort(key=lambda x:(x['title'].casefold(),x['id']))
 return {'project_id':p,'folder_id':folder_id,'breadcrumbs':[{'id':x['id'],'name':x['name']} for x in trail],'folders':allfolders,'items':items[offset:offset+limit],'total':len(items),'has_more':offset+limit<len(items),'offset':offset,'can_write':member['role']!='viewer','can_delete':member['role']=='owner'}

def store(server):
 from .integration import store_for
 return store_for(server)
@router.get('/projects/{p}/file-browser')
def list_files(p:str,folder_id:str='',q:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=200),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return browse(store(server),p,user.id,folder_id,q,offset,limit)
@router.post('/projects/{p}/folders',status_code=201)
def new(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):return create_folder(store(server),p,user.id,body)
@router.patch('/projects/{p}/folders/{id}')
def edit(p:str,id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):return update_folder(store(server),p,user.id,id,body)
@router.delete('/projects/{p}/folders/{id}')
def delete(p:str,id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):return remove_folder(store(server),p,user.id,id,body)
@router.post('/projects/{p}/files/move')
def move(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):return move_documents(store(server),p,user.id,body)
