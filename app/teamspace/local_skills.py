"""Local ZIP intake: inspect first, import an immutable disabled draft, never run code."""
from __future__ import annotations
import hashlib,io,json,re,stat,zipfile
from pathlib import PurePosixPath
from typing import Any
import yaml
from fastapi import APIRouter,Depends,File,Form,UploadFile,Query
from octop.api.deps import current_user,get_server
from .platform_api import registry
from .store import Problem,dump
from .skill_library import ensure_file_table,package_files
from .skill_markets import unpack
router=APIRouter()
MAX_ARCHIVE=5*1024*1024
TEXT_SUFFIXES={'.md','.txt','.json','.yaml','.yml','.toml','.py','.js','.ts','.sh','.ps1','.csv','.html','.css','.xml','.ini','.cfg','.bat'}


def inspect_zip(raw:bytes,filename:str='skill.zip')->dict:
 if not raw or len(raw)>MAX_ARCHIVE:raise Problem(413,'ZIP 不能为空，且不能超过 5 MB')
 if not filename.lower().endswith('.zip'):raise Problem(422,'请上传 ZIP 格式的技能包')
 # Canonical paths and a single entrypoint prevent preview/import ambiguity.
 try:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   if len(z.infolist())>200:raise Problem(413,'技能包最多 150 个文件、200 个目录项')
   entries=[x for x in z.infolist() if not x.is_dir()]
   roots=[]
   for e in entries:
    n=e.filename;p=PurePosixPath(n)
    if n!=p.as_posix() or n.startswith('/') or any(x in ('..','.') for x in p.parts) or '\\' in n or ':' in n or any(ord(ch)<32 for ch in n) or stat.S_ISLNK(e.external_attr>>16):raise Problem(422,'技能包含不安全或歧义路径')
    if p.name=='SKILL.md':roots.append(n)
   if len(roots)!=1:raise Problem(422,'每次上传一个技能，压缩包中必须恰好包含一份 SKILL.md')
  files,_=unpack(raw)
 except Problem:raise
 except (zipfile.BadZipFile,RuntimeError,NotImplementedError,ValueError,OSError):raise Problem(422,'无法读取 ZIP，请检查文件完整性、加密和压缩格式') from None
 text=files['SKILL.md'].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n');meta={};body=text
 if text.startswith('---\n'):
  match=re.search(r'^---\s*$',text[4:],re.M)
  if not match:raise Problem(422,'SKILL.md 的 YAML 头缺少结束分隔线')
  head=text[4:4+match.start()]
  if len(head)>16000:raise Problem(413,'技能元数据过大')
  try:
   if any(isinstance(t,(yaml.tokens.AliasToken,yaml.tokens.AnchorToken)) for t in yaml.scan(head)):raise Problem(422,'技能元数据不接受 YAML 引用或锚点')
   meta=yaml.safe_load(head) or {}
  except yaml.YAMLError:raise Problem(422,'技能元数据 YAML 格式错误') from None
  if not isinstance(meta,dict):raise Problem(422,'技能元数据应为键值对象')
  body=text[4+match.end():].strip()
 if not body.strip():raise Problem(422,'SKILL.md 必须有操作正文')
 fallback=PurePosixPath(filename).stem
 name=meta.get('name') or fallback
 description=meta.get('description') or '本地上传的技能包，需审核后启用。'
 if not isinstance(name,str) or not 1<=len(name.strip())<=80:raise Problem(422,'技能名称需为 1–80 个字符')
 if not isinstance(description,str) or len(description)>2000:raise Problem(422,'技能说明需为不超过 2000 字符的文本')
 digest=hashlib.sha256(raw).hexdigest();slug=re.sub('[^a-z0-9_-]','-',name.lower()).strip('-')[:64] or 'local-'+digest[:12]
 scripts=[n for n in files if PurePosixPath(n).suffix.lower() in {'.py','.js','.ts','.sh','.ps1','.bat','.exe','.dll','.so'}]
 return {'name':name.strip(),'slug':slug,'description':description,'body':body,'files':files,'sha256':digest,'filename':PurePosixPath(filename.replace('\\','/')).name[:120],'script_files':scripts,'has_frontmatter':bool(meta),'warnings':[] if meta else ['没有 YAML 元数据，采用文件名作为显示名称；建议发布前补充用途。'],'automatic_execution':False,'review_required':True}


def public_inspection(d):
 return {**{k:v for k,v in d.items() if k!='files'},'files':[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(d['files'].items())]}


def import_zip(r,w,actor,raw,filename,expected_sha256,acknowledge_review):
 with r.store.connection() as c:r.manage(c,w,actor)
 d=inspect_zip(raw,filename)
 if expected_sha256!=d['sha256']:raise Problem(409,'技能包已变化，请重新预览后导入')
 if acknowledge_review is not True:raise Problem(422,'请确认仅导入待审草稿，不自动执行')
 ensure_file_table(r)
 with r.store.connection(True) as c:
  r.manage(c,w,actor)
  old=c.execute("SELECT id FROM team_platform_assets WHERE workspace_id=? AND kind='skill' AND json_extract(source_json,'$.kind')='local_zip_upload' AND json_extract(source_json,'$.package_sha256')=?",(w,d['sha256'])).fetchone()
  if old:return {**r.get(old[0],actor,c=c),'duplicate':True}
  name=d['name']
  if c.execute("SELECT 1 FROM team_platform_assets WHERE workspace_id=? AND kind='skill' AND name=?",(w,name)).fetchone():name=name[:65]+' · '+d['sha256'][:10]
  source={'kind':'local_zip_upload','filename':d['filename'],'package_sha256':d['sha256'],'review_required':True,'scripts_auto_executed':False,'script_files':d['script_files'],'files_count':len(d['files'])}
  body={'data':{'slug':d['slug'],'body':d['body'],'status':'draft'}}
  data=r.validate_platform_data(c,w,actor,'skill',body)
  aid=r._insert_asset(c,w,actor,'skill',name,data,d['description'],source=source,enabled=False,visibility='workspace')
  c.executemany('INSERT INTO team_skill_files VALUES(?,?,?,?)',[(aid,n,b,hashlib.sha256(b).hexdigest()) for n,b in d['files'].items()])
  asset=r.get(aid,actor,c=c)
 return {**asset,'package_files':len(d['files']),'automatically_mounted':False}


async def upload_bytes(file):
 try:
  data=await file.read(MAX_ARCHIVE+1)
  if len(data)>MAX_ARCHIVE:raise Problem(413,'技能 ZIP 超过 5 MB')
  return data
 finally:await file.close()


@router.post('/workspaces/{w}/local-skills/preview')
async def preview(w:str,file:UploadFile=File(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 import asyncio
 r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 raw=await upload_bytes(file);result=await asyncio.to_thread(inspect_zip,raw,file.filename or 'skill.zip')
 with r.store.connection() as c:r.manage(c,w,user.id)
 return public_inspection(result)


@router.post('/workspaces/{w}/local-skills/import',status_code=201)
async def install(w:str,file:UploadFile=File(...),expected_sha256:str=Form(...),acknowledge_review:bool=Form(False),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 import asyncio
 r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 raw=await upload_bytes(file)
 return await asyncio.to_thread(import_zip,r,w,user.id,raw,file.filename or 'skill.zip',expected_sha256,acknowledge_review)


@router.get('/skills/{id}/files')
def files(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);a=r.get(id,user.id,'skill');fs=package_files(r,a)
 return {'id':id,'name':a['name'],'revision':a['revision'],'status':a['data']['status'],'enabled':a['enabled'],'source':a['source'],'files':[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'text_preview':PurePosixPath(n).suffix.lower() in TEXT_SUFFIXES or n in ('LICENSE','NOTICE')} for n,b in sorted(fs.items())],'automatic_execution':False}


@router.get('/skills/{id}/file')
def file_content(id:str,path:str=Query(...,max_length=250),revision:int=Query(...,ge=1),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);a=r.get(id,user.id,'skill')
 if a['revision']!=revision:raise Problem(409,'技能已更新，请重新打开预览')
 fs=package_files(r,a)
 if path not in fs:raise Problem(404,'技能文件不存在')
 b=fs[path]
 if len(b)>200000:raise Problem(413,'文件较大，请导出 ZIP 查看原文件')
 if PurePosixPath(path).suffix.lower() not in TEXT_SUFFIXES and path not in ('LICENSE','NOTICE'):raise Problem(415,'此文件不支持文本预览，请导出 ZIP 查看')
 try:text=b.decode('utf-8-sig')
 except UnicodeError:raise Problem(415,'此文件不是 UTF-8 文本，请导出后查看') from None
 return {'path':path,'revision':revision,'content':text,'sha256':hashlib.sha256(b).hexdigest(),'format':'markdown' if path.lower().endswith('.md') else 'text','executed':False}
