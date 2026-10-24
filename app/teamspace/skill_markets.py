"""Bounded public SkillHub/ClawHub discovery and review-only package imports.
External skill content is untrusted data: never executed, enabled, or attached.
"""
from __future__ import annotations
import asyncio,hashlib,io,json,re,stat,threading,time,urllib.parse,urllib.request,urllib.error,zipfile
from pathlib import PurePosixPath
from typing import Any
from fastapi import APIRouter,Depends,Query,Body
from octop.api.deps import current_user,get_server
from .store import Problem,dump,now
from .platform_api import registry
from .skill_library import ensure_file_table
router=APIRouter();_cache={};_lock=threading.Lock();_slots=threading.BoundedSemaphore(3)
SOURCES={
 'skillhub':{'id':'skillhub','name':'腾讯 SkillHub','base':'https://api.skillhub.cn','home':'https://skillhub.cn','docs':'https://github.com/Tencent/skillhub/tree/main/docs/api','capability':'search_preview_import'},
 'clawhub':{'id':'clawhub','name':'ClawHub','base':'https://clawhub.ai','home':'https://clawhub.ai','docs':'https://github.com/openclaw/clawhub/blob/main/docs/http-api.md','capability':'search_preview_import'}}

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def allowed_url(source,url):
 u=urllib.parse.urlsplit(url);host=(u.hostname or '').lower()
 if u.scheme!='https' or u.username or u.password or u.port not in (None,443):raise Problem(422,'技能下载只允许官方 HTTPS 来源')
 base=urllib.parse.urlsplit(SOURCES[source]['base']).hostname
 allowed=host==base or (source=='skillhub' and host.endswith('.myqcloud.com')) or (source=='clawhub' and host.endswith(('.convex.cloud','.convex.site')))
 if not allowed:raise Problem(422,'技能下载重定向到未审核的主机，已停止')
 return url

def fetch(source,path,limit=5*1024*1024,json_result=True):
 if source not in SOURCES:raise Problem(422,'未知技能来源')
 url=SOURCES[source]['base']+path
 if not path.startswith('/api/'):raise Problem(422,'不允许的技能接口路径')
 if not _slots.acquire(timeout=2):raise Problem(429,'技能广场请求较多，请稍后重试')
 try:
  opener=urllib.request.build_opener(NoRedirect())
  for attempt in range(4):
   allowed_url(source,url)
   request=urllib.request.Request(url,headers={'User-Agent':'gongzhi-teamspace/0.9.1','Accept':'application/json' if json_result else 'application/octet-stream'})
   try:
    with opener.open(request,timeout=18) as r:
     b=r.read(limit+1)
     if len(b)>limit:raise Problem(413,'技能响应超过大小限制')
     if json_result:
      try:return json.loads(b)
      except (ValueError,UnicodeError):raise Problem(502,'技能平台没有返回有效 JSON') from None
     return b
   except urllib.error.HTTPError as e:
    if e.code in (301,302,303,307,308):url=urllib.parse.urljoin(url,e.headers.get('Location',''));continue
    raise Problem(502 if e.code>=500 else e.code,'外部技能平台返回 HTTP '+str(e.code)+'；没有重试、安装或启用。') from None
  raise Problem(502,'下载重定向过多')
 except (TimeoutError,urllib.error.URLError):raise Problem(504,'外部技能平台暂时无法访问；本地功能不受影响') from None
 finally:_slots.release()

def token(value,label):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_@.\-]{1,120}',value):raise Problem(422,label+'格式无效')
 return value

def search(source,q,page=1,cursor=''):
 if source not in SOURCES:raise Problem(422,'未知技能来源')
 if not isinstance(q,str) or len(q)>160 or page<1 or page>100:raise Problem(422,'搜索参数无效')
 key=('search',source,q,page,cursor)
 with _lock:cached=_cache.get(key)
 if cached and time.monotonic()-cached[0]<180:return dict(cached[1],cached=True)
 if source=='skillhub':
  value=fetch(source,'/api/skills?'+urllib.parse.urlencode({'keyword':q,'page':page,'pageSize':15,'sortBy':'downloads','order':'desc'}));data=value.get('data') or {};raw=data.get('skills',[])
  items=[{'slug':x['slug'],'name':x.get('name') or x['slug'],'description':(x.get('description_zh') or x.get('description') or '')[:2000],'version':x.get('version'),'owner':(x.get('namespace') or {}).get('handle') or x.get('ownerName',''),'url':skillhub_listing_url(x),'upstream_source':x.get('source'),'requires_api_key':(x.get('labels') or {}).get('requires_api_key')=='true','source':source} for x in raw]
  result={'items':items,'total':data.get('total'),'next_page':page+1 if page*15<int(data.get('total') or 0) else None}
 else:
  if q:path='/api/v1/search?'+urllib.parse.urlencode({'q':q,'limit':15,'nonSuspiciousOnly':'true'})
  else:path='/api/v1/skills?'+urllib.parse.urlencode({'limit':15,'cursor':cursor,'sort':'downloads','nonSuspiciousOnly':'true'})
  value=fetch(source,path);raw=value.get('results',value.get('items',[]));items=[]
  for x in raw:
   owner=x.get('ownerHandle') or (x.get('owner') or {}).get('handle','');canonical=x.get('canonicalUrl')
   url='https://clawhub.ai'+canonical if isinstance(canonical,str) and canonical.startswith('/') and not canonical.startswith('//') else 'https://clawhub.ai/'+urllib.parse.quote(owner,safe='')+'/skills/'+urllib.parse.quote(x['slug'],safe='')
   items.append({'slug':x['slug'],'name':x.get('displayName') or x['slug'],'description':(x.get('summary') or '')[:2000],'version':x.get('version') or (x.get('latestVersion') or {}).get('version'),'owner':owner,'url':url,'source':source,'upstream_source':'ClawHub community'})
  result={'items':items,'next_cursor':value.get('nextCursor'),'total':None}
 result.update(source=source,source_name=SOURCES[source]['name'],at=now(),cached=False,automatic_execution=False,registry_listing_is_not_review=True)
 with _lock:
  if len(_cache)>100:_cache.clear()
  _cache[key]=(time.monotonic(),result)
 return result

def unpack(raw,max_files=150):
 if type(max_files) is not int or not 1<=max_files<=256:raise ValueError('invalid archive file budget')
 files={};total=0
 try:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   if len(z.infolist())>max_files*2:raise Problem(413,'技能包目录项超过限制')
   entries=[x for x in z.infolist() if not x.is_dir()]
   if not entries:raise Problem(422,'技能包中没有文件')
   if len(entries)>max_files:raise Problem(413,'技能包有 '+str(len(entries))+' 个文件，当前上限 '+str(max_files)+'；未导入部分内容')
   for e in entries:
    name=e.filename;p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or any(ord(ch)<32 for ch in name) or stat.S_ISLNK(e.external_attr>>16):raise Problem(422,'技能包包含不安全路径或符号链接')
    if e.flag_bits&1:raise Problem(422,'不能读取加密技能包')
    total+=e.file_size
    if total>5*1024*1024 or e.file_size>2*1024*1024 or e.file_size>max(e.compress_size,1)*200:raise Problem(413,'技能包超过展开限制')
    if name.casefold() in {x.casefold() for x in files}:raise Problem(422,'技能包存在冲突文件名')
    files[name]=z.read(e)
 except zipfile.BadZipFile:raise Problem(422,'供应方没有返回有效 ZIP') from None
 roots=[p[:-8] for p in files if p.endswith('SKILL.md')]
 root='' if 'SKILL.md' in files else min(roots,key=len) if roots else None
 if root is None:raise Problem(422,'技能包缺少 SKILL.md')
 if root:
  if any(not x.startswith(root) for x in files):raise Problem(422,'多根目录技能包需要人工整理后导入')
  files={n[len(root):]:b for n,b in files.items()}
 try:text=files['SKILL.md'].decode('utf-8-sig')
 except UnicodeError:raise Problem(422,'SKILL.md 必须为 UTF-8') from None
 if len(text)>100000:raise Problem(413,'SKILL.md 超出正文限制')
 if text.startswith('---\n'):
  end=text.find('\n---',4)
  if end>=0:text=text[end+4:].lstrip('\r\n')
 if not text.strip():raise Problem(422,'技能正文为空')
 return files,text

def publisher_handle(value,label='发布者'):
 """Normalize identifiers, never display names or caller-provided aliases."""
 if not isinstance(value,str):raise Problem(422,label+'标识无效')
 normalized=value.strip().lstrip('@').lower()
 if normalized:token(normalized,label)
 return normalized


def skillhub_listing_url(item):
 owner=publisher_handle((item.get('namespace') or {}).get('handle') or item.get('ownerName',''))
 slug=token(item['slug'],'技能标识')
 return 'https://skillhub.cn/'+(urllib.parse.quote(owner,safe='')+'/' if owner else 'skills/')+urllib.parse.quote(slug,safe='')


def resolve_publisher(source,slug,selected,detail):
 """SkillHub namespace != account handle; ClawHub uses the account handle.
 Only aliases present in this exact upstream detail are accepted. No guessing.
 """
 if not isinstance(detail,dict):raise Problem(502,'技能来源没有返回有效详情')
 skill=detail.get('skill') or {};ns=detail.get('namespace') or {};account=detail.get('owner') or {}
 if not all(isinstance(x,dict) for x in (skill,ns,account)):raise Problem(502,'技能来源身份字段格式错误')
 actual_slug=skill.get('slug')
 if actual_slug!=slug:raise Problem(409,'技能标识与所选结果不一致，请重新搜索；未下载其他技能')
 author=publisher_handle(account.get('handle') or '')
 namespace=publisher_handle(ns.get('handle') or '') if source=='skillhub' else ''
 canonical=namespace or author
 if not canonical:raise Problem(502,'技能来源没有返回可核验的发布者标识，尚未下载')
 aliases={canonical}
 if source=='skillhub' and author:aliases.add(author)
 if selected and selected not in aliases:
  raise Problem(409,'技能发布者与所选结果不一致：选择 @'+selected+'，来源返回 @'+canonical+'。请重新搜索或粘贴该发布者的详情链接；未导入其他作者的同名技能。')
 public_slug=ns.get('publicSlug')
 if public_slug and public_slug!=slug:raise Problem(409,'来源的发布者空间与技能标识不一致，请重新选择')
 return {'owner':canonical,'author_handle':author,'namespace':namespace,'canonical_name':'@'+canonical+'/'+slug,'identity_policy':'qualified-publisher-v1'}


def package(source,slug,owner='',version=''):
 if source not in SOURCES:raise Problem(422,'未知技能来源')
 token(slug,'技能标识');selected=publisher_handle(owner)
 if version:token(version,'版本')
 # Only canonical, already-validated identities are cached. Different authors
 # with an identical slug/version must not share metadata, bytes, or imports.
 if selected and version:
  with _lock:cached=_cache.get(('package',source,slug,selected,version))
  if cached and time.monotonic()-cached[0]<300:return cached[1]
 selector='namespace' if source=='skillhub' else 'ownerHandle'
 params={selector:selected} if selected else {}
 path='/api/v1/skills/'+urllib.parse.quote(slug,safe='')
 try:detail=fetch(source,path+('?' + urllib.parse.urlencode(params) if params else ''))
 except Problem as exc:
  # Old SkillHub clients may send an account ID rather than its namespace.
  # An unqualified detail may establish that exact alias, but NEVER weakens
  # the identity check below. Network/authorization errors are not retried.
  if source!='skillhub' or not selected or exc.status!=404:raise
  detail=fetch(source,path)
 identity=resolve_publisher(source,slug,selected,detail)
 mod=detail.get('moderation') or {}
 if mod.get('isMalwareBlocked') or mod.get('isSuspicious') or mod.get('verdict') in ('malicious','suspicious'):raise Problem(422,'来源平台已标记此技能存在风险，拒绝导入')
 v=version or (detail.get('latestVersion') or {}).get('version')
 if not v:raise Problem(502,'无法确定精确版本，未下载')
 token(v,'版本');actual_owner=identity['owner'];key=('package',source,slug,actual_owner,v)
 with _lock:cached=_cache.get(key)
 if cached and time.monotonic()-cached[0]<300:return cached[1]
 # Bind BOTH the detail and the ZIP download to the resolved publisher.
 query={'slug':slug,'version':v,selector:actual_owner}
 raw=fetch(source,'/api/v1/download?'+urllib.parse.urlencode(query),json_result=False)
 files,text=unpack(raw,max_files=256);skill=detail['skill'];script_files=[n for n in files if PurePosixPath(n).suffix.lower() in ('.py','.js','.ts','.sh','.ps1','.bat','.exe','.dll')]
 result={'source':source,'slug':slug,**identity,'version':v,'name':skill.get('displayName') or slug,'description':(skill.get('summary_zh') or skill.get('summary') or '')[:2000],'body':text,'sha256':hashlib.sha256(raw).hexdigest(),'files':files,'script_files':script_files,'review_required':True,'automatic_execution':False,'upstream_moderation':{k:mod.get(k) for k in ('verdict','isSuspicious','isMalwareBlocked')},'checked_at':now()}
 with _lock:
  if len(_cache)>100:_cache.clear()
  _cache[key]=(time.monotonic(),result)
 return result


def public_package(data):
 return {**{k:v for k,v in data.items() if k!='files'},'files':[{'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(data['files'].items())]}

def import_package(r,w,actor,body):
 with r.store.connection() as c:r.manage(c,w,actor)
 data=package(body.get('source'),body.get('slug'),body.get('owner',''),body.get('version',''))
 if body.get('expected_sha256')!=data['sha256']:raise Problem(409,'技能包已变化，请重新预览')
 if body.get('acknowledge_review') is not True:raise Problem(422,'请确认仅导入待审，不自动运行')
 ensure_file_table(r)
 with r.store.connection(True) as c:
  r.manage(c,w,actor)
  old=c.execute("SELECT id FROM team_platform_assets WHERE workspace_id=? AND kind='skill' AND json_extract(source_json,'$.package_sha256')=? AND json_extract(source_json,'$.market')=? AND json_extract(source_json,'$.catalog_slug')=? AND json_extract(source_json,'$.owner')=?",(w,data['sha256'],data['source'],data['slug'],data['owner'])).fetchone()
  if old:
   if r.store.deleted(c,old[0]):raise Problem(409,'此版本已在回收站，请先恢复后查看')
   return {**r.get(old[0],actor,c=c),'duplicate':True}
  name=(data['name']+' · '+data['source']+' '+data['version'])[:80]
  if c.execute("SELECT 1 FROM team_platform_assets WHERE workspace_id=? AND kind='skill' AND name=?",(w,name)).fetchone():name=name[:60]+' · '+data['sha256'][:10]
  slug=re.sub('[^a-z0-9_-]','-',(data['source']+'-'+data['slug']).lower())[:80]
  d=r.validate_platform_data(c,w,actor,'skill',{'data':{'slug':slug,'body':data['body'],'status':'draft'}})
  source={'kind':'external_skill_market','market':data['source'],'catalog_slug':data['slug'],'owner':data['owner'],'author_handle':data.get('author_handle',''),'namespace':data.get('namespace',''),'identity_policy':'qualified-publisher-v1','version':data['version'],'package_sha256':data['sha256'],'scripts_auto_executed':False,'review_required':True,'script_files':data['script_files'],'fetched_at':data['checked_at']}
  id=r._insert_asset(c,w,actor,'skill',name,d,data['description'],source=source,enabled=False,visibility='workspace')
  c.executemany('INSERT INTO team_skill_files VALUES(?,?,?,?)',[(id,n,b,hashlib.sha256(b).hexdigest()) for n,b in data['files'].items()])
  asset=r.get(id,actor,c=c)
 return {**asset,'package_files':len(data['files']),'automatically_mounted':False}


@router.get('/workspaces/{w}/skill-market')
async def market(w:str,source:str=Query('skillhub'),q:str=Query('',max_length=160),page:int=Query(1,ge=1,le=100),cursor:str=Query('',max_length=1000),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 result=await asyncio.to_thread(search,source,q,page,cursor)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return result
@router.post('/workspaces/{w}/skill-market/preview')
async def preview(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 result=await asyncio.to_thread(package,body.get('source'),body.get('slug'),body.get('owner',''),body.get('version',''))
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return public_package(result)
@router.post('/workspaces/{w}/skill-market/import',status_code=201)
async def install(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return await asyncio.to_thread(import_package,registry(server),w,user.id,body)
