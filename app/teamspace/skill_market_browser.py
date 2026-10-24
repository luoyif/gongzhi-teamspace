"""In-app source package browser, safe downloads and direct server-side import."""
from __future__ import annotations
import asyncio,base64,hashlib,io,json,tempfile,urllib.parse,zipfile
from pathlib import Path
from typing import Any
from fastapi import APIRouter,Depends,Body,Query
from fastapi.responses import Response
from octop.api.deps import current_user,get_server
from .platform_api import registry
from .store import Problem
from .skill_markets import package,token
from .skill_library import package_files
from .preview_formats import INLINE
from .file_preview import run_preview
router=APIRouter()

def source_link(link):
 if not isinstance(link,str) or len(link)>1200:raise Problem(422,'技能链接无效')
 u=urllib.parse.urlsplit(link.strip());host=(u.hostname or '').lower();parts=[urllib.parse.unquote(x) for x in u.path.split('/') if x]
 if u.scheme!='https' or u.username or u.password or u.port not in (None,443):raise Problem(422,'请粘贴受支持技能站点的 HTTPS 页面链接')
 source='skillhub' if host in ('skillhub.cn','www.skillhub.cn','api.skillhub.cn') else 'clawhub' if host in ('clawhub.ai','www.clawhub.ai') else None
 if not source:raise Problem(422,'当前支持 SkillHub 与 ClawHub 链接，不能抓取任意下载地址')
 if parts[:3]==['api','v1','skills']:parts=parts[3:]
 elif parts[:1]==['skills']:parts=parts[1:]
 elif len(parts)==3 and parts[1]=='skills':parts=[parts[0],parts[2]]
 if len(parts)==1:owner='';slug=parts[0]
 elif len(parts)==2:owner,slug=parts;owner=owner.lstrip('@')
 else:raise Problem(422,'请粘贴具体技能详情页，而非主页或搜索页')
 token(slug,'技能标识')
 if owner:token(owner,'作者')
 return {'source':source,'slug':slug,'owner':owner,'version':''}

def inspect_entry(raw,name,sheet=0,offset=0,col=0):
 if len(raw)>2*1024*1024:raise Problem(413,'附属文件超过单项预览上限，请下载技能包')
 with tempfile.TemporaryDirectory(prefix='gongzhi-skill-preview-') as td:
  p=Path(td)/'source';p.write_bytes(raw);d=run_preview(p,name,sheet,offset,col)
 if d['format'] in ('pdf','image','audio','video'):d['binary_base64']=base64.b64encode(raw).decode('ascii')
 return {**d,'sha256':hashlib.sha256(raw).hexdigest(),'executed':False}

def checked_package(body):
 d=package(body.get('source'),body.get('slug'),body.get('owner',''),body.get('version',''))
 if body.get('expected_sha256')!=d['sha256']:raise Problem(409,'技能包版本或内容已变化，请重新打开预览')
 return d

def market_entry(r,w,actor,body):
 with r.store.connection() as c:r.store.workspace_require(c,w,actor)
 d=checked_package(body);path=body.get('path')
 if path not in d['files']:raise Problem(404,'技能包内文件不存在')
 result=inspect_entry(d['files'][path],path,int(body.get('sheet',0)),int(body.get('offset',0)),int(body.get('col',0)))
 with r.store.connection() as c:r.store.workspace_require(c,w,actor)
 return {**result,'path':path,'version':d['version'],'package_sha256':d['sha256']}

@router.post('/workspaces/{w}/skill-market/resolve')
def resolve(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return source_link(body.get('url'))
@router.post('/workspaces/{w}/skill-market/file')
async def read_market_file(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return await asyncio.to_thread(market_entry,registry(server),w,user.id,body)
@router.post('/workspaces/{w}/skill-market/download')
async def download(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 d=await asyncio.to_thread(checked_package,body);buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for name,raw in d['files'].items():z.writestr(name,raw)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return Response(buf.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="'+d['slug']+'.zip"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@router.get('/skills/{id}/preview')
def local_preview(id:str,path:str=Query(...,max_length=250),revision:int=Query(...,ge=1),sheet:int=Query(0,ge=0,le=200),offset:int=Query(0,ge=0,le=1000000),col:int=Query(0,ge=0,le=1000),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);a=r.get(id,user.id,'skill')
 if revision!=a['revision']:raise Problem(409,'技能已更新，请重新打开')
 fs=package_files(r,a)
 if path not in fs:raise Problem(404,'文件不存在')
 d=inspect_entry(fs[path],path,sheet,offset,col)
 if r.get(id,user.id,'skill')['revision']!=revision:raise Problem(409,'技能已更新，请重新打开')
 return {**d,'path':path,'revision':revision}
