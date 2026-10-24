"""Authenticated original/structured preview; no public file URLs or token query strings."""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,threading,time
from typing import Any
from pathlib import Path
from fastapi import APIRouter,Depends,Query
from fastapi.responses import FileResponse
from octop.api.deps import current_user,get_server
from .store import Problem
from .preview_formats import INLINE
router=APIRouter();_cache={};_lock=threading.Lock();_slots=threading.BoundedSemaphore(3)

def run_preview(path,filename,sheet=0,offset=0,col=0):
 if not _slots.acquire(timeout=2):raise Problem(429,'预览较多，请稍后重试；不影响聊天')
 try:
  try:p=subprocess.run([sys.executable,'-m','teamspace.preview_formats',str(path),filename,str(sheet),str(offset),str(col)],capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=30,env=os.environ.copy())
  except subprocess.TimeoutExpired:raise Problem(504,'本地预览超时，原件仍然保留') from None
  if p.returncode or len(p.stdout)>8*1024*1024:raise Problem(422,'文件无法安全预览或内容过大，请下载原件')
  try:return json.loads(p.stdout)
  except ValueError:raise Problem(422,'预览未返回有效内容，原件保留') from None
 finally:_slots.release()

def inspect_document(s,id,actor,sheet=0,offset=0,col=0):
 doc=s.object(id,actor,'document')
 if 'sha256' not in doc or not doc.get('filename'):
  return {'format':'markdown','content':doc['body'][offset:offset+50000],'has_more':offset+50000<len(doc['body']),'next_offset':offset+50000,'id':id,'revision':doc['revision'],'title':doc['title'],'status':doc['status'],'adopted':bool(doc.get('adopted'))}
 path,name=s.blob(id,actor);key=(str(s.db_path),id,doc['revision'],doc['sha256'],sheet,offset,col)
 with _lock:cached=_cache.get(key)
 if cached and time.monotonic()-cached[0]<180:value=cached[1]
 else:
  value=run_preview(path,name,sheet,offset,col)
  with _lock:
   if len(_cache)>=12:_cache.clear()
   _cache[key]=(time.monotonic(),value)
 current=s.object(id,actor,'document')
 if current['revision']!=doc['revision']:raise Problem(409,'文件已变化，请重新预览')
 return {**value,'id':id,'revision':doc['revision'],'title':doc['title'],'filename':name,'status':doc['status'],'adopted':bool(doc.get('adopted')),'source_url':'/documents/'+id+'/preview-original','sha256':doc['sha256']}

def get_store(server):
 from .integration import store_for
 return store_for(server)
@router.get('/documents/{id}/preview')
def show(id:str,sheet:int=Query(0,ge=0,le=200),offset:int=Query(0,ge=0,le=1000000),col:int=Query(0,ge=0,le=1000),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return inspect_document(get_store(server),id,user.id,sheet,offset,col)
@router.get('/documents/{id}/preview-original')
def original(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=get_store(server);path,name=s.blob(id,user.id);ext=Path(name).suffix.lower()
 if ext not in INLINE:raise Problem(415,'此类型不允许作为活动页面嵌入，请使用结构化预览或下载')
 return FileResponse(path,filename=name,content_disposition_type='inline',media_type=INLINE[ext][1],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
