"""Verified provider catalogues and real MCP directory. No mock servers in product catalogue."""
from __future__ import annotations
import asyncio,json,urllib.request,urllib.parse,datetime
from pathlib import Path
from typing import Any
from fastapi import APIRouter,Body,Depends,Query
from octop.api.deps import current_user,get_server
from .store import Problem,dump,now
from .presets import is_site_admin,read_preset
from .platform_api import registry,configure_model,_model_lock
from .platform_registry import stable
from .go_models import catalog,model_info
router=APIRouter()
DIRECTORY=[
 {'id':'official:microsoft-learn','name':'Microsoft Learn','publisher':'Microsoft','description':'搜索官方技术文档、获取文章和代码示例。无需账户认证。','category':'官方知识源','url':'https://learn.microsoft.com/api/mcp','documentation':'https://learn.microsoft.com/en-us/training/support/mcp','transport':'streamable_http','authentication':'none','source':'vendor_documentation'},
 {'id':'official:neon','name':'Neon PostgreSQL','publisher':'Neon','description':'连接自己的 Neon 项目与 PostgreSQL 数据库；需要 Neon API Key 或 OAuth 授权。','category':'数据库','url':'https://mcp.neon.tech/mcp','documentation':'https://neon.com/docs/ai/neon-mcp-server','transport':'streamable_http','authentication':'bearer_or_oauth','source':'official_registry','registry_name':'com.neon/mcp'},
 {'id':'official:supabase','name':'Supabase','publisher':'Supabase','description':'连接自己的开发／测试项目。可填写限定权限的个人访问令牌；OAuth 浏览器登录尚未接入。不要将开发者权限提供给学员或客户。','category':'数据库','url':'https://mcp.supabase.com/mcp','documentation':'https://supabase.com/docs/guides/ai-tools/mcp','transport':'streamable_http','authentication':'oauth_or_pat','source':'vendor_documentation'}]

def public_registry_search(q):
 url='https://registry.modelcontextprotocol.io/v0.1/servers?'+urllib.parse.urlencode({'search':q,'limit':30,'version':'latest'})
 req=urllib.request.Request(url,headers={'User-Agent':'gongzhi-teamspace/0.5.0'})
 with urllib.request.urlopen(req,timeout=12) as r:data=json.loads(r.read(1500000))
 out=[]
 for row in data.get('servers',[]):
  s=row.get('server',{});meta=(row.get('_meta') or {}).get('io.modelcontextprotocol.registry/official',{})
  if meta.get('status') not in (None,'active') or meta.get('isLatest') is False:continue
  remote=next((x for x in s.get('remotes',[]) if x.get('type') in ('streamable-http','sse') and x.get('url','').startswith('https://')),None)
  if not remote:continue
  out.append({'id':'registry:'+s['name'],'name':s.get('title') or s['name'],'publisher':s['name'].split('/')[0],'description':s.get('description',''),'category':'Registry 收录','url':remote['url'],'transport':remote['type'].replace('-','_'),'documentation':s.get('websiteUrl') or (s.get('repository') or {}).get('url') or 'https://registry.modelcontextprotocol.io/','authentication':'查看供应商说明','source':'official_registry','registry_name':s['name'],'version':s.get('version'),'registry_listing_not_security_audit':True})
 return out

@router.get('/workspaces/{w}/go-models')
def models(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 result=catalog();assets=r.catalog(w,user.id)['items'];by_model={a['data'].get('model'):a for a in assets if a['kind']=='model' and a['source'].get('kind')=='official_go_catalog'}
 report_path=Path(server.services.paths.root).parent/'evidence/ui5-go-model-tests.json';results={}
 if report_path.is_file():
  try:results={x['model_id']:x for x in json.loads(report_path.read_text(encoding='utf8')).get('results',[])}
  except (ValueError,KeyError):pass
 return {**result,'items':[{**m,'connection_id':by_model.get(m['id'],{}).get('id'),'verification':results.get(m['id'],{'status':'not_tested'})} for m in result['items']]}

@router.post('/workspaces/{w}/go-models/prepare')
async def prepare_model(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 info=model_info(body.get('model_id'));r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 if not is_site_admin(user):raise Problem(403,'使用服务器 Go 密钥创建连接需要系统管理员')
 if not info:raise Problem(422,'不在已核对的官方 Go 模型列表')
 cfg=read_preset(server,user)
 if not cfg:raise Problem(409,'尚未配置服务器 Go 密钥')
 async with _model_lock:
  aid=stable('v_',w+':official-go:'+info['id'])
  with r.store.connection(True) as c:
   if c.execute('SELECT 1 FROM team_platform_assets WHERE id=?',(aid,)).fetchone():return r.get(aid,user.id,c=c)
   r._insert_asset(c,w,user.id,'model',info['name'],{'provider_name':'','model':'','base_url':'','configured':False},'OpenCode Go · '+info['protocol'],{'kind':'official_go_catalog','source_url':info['source'],'protocol':info['protocol'],'contributor':info['contributor']},aid,False)
  a=r.get(aid,user.id)
  return await configure_model(r,server,a,user,{'expected_revision':a['revision'],'base_url':info['base_url'],'model':info['id'],'api_key':cfg['api_key']})

@router.get('/workspaces/{w}/mcp-directory')
async def mcp_directory(w:str,q:str=Query('',max_length=120),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 rows=[dict(x) for x in DIRECTORY if not q or q.casefold() in dump(x).casefold()];warning=None
 if q:
  try:rows+=await asyncio.to_thread(public_registry_search,q)
  except Exception as e:warning='官方 Registry 暂时无法读取；当前仅显示已核对的供应商目录，不表示连接成功。'
 return {'items':rows,'registry':'https://registry.modelcontextprotocol.io/','warning':warning,'automatic_installation':False,'oauth_supported':False,'note':'收录不是安全审计；接入真实数据库需要自己的账号和授权。'}

@router.post('/workspaces/{w}/mcp-directory/import',status_code=201)
async def import_mcp(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 if not is_site_admin(user):raise Problem(403,'导入外部连接需要系统管理员')
 id=body.get('catalog_id','');item=next((x for x in DIRECTORY if x['id']==id),None)
 if item is None and isinstance(id,str) and id.startswith('registry:') and len(id)<220:
  name=id.removeprefix('registry:')
  try:item=next((x for x in await asyncio.to_thread(public_registry_search,name) if x['id']==id),None)
  except Exception:raise Problem(502,'无法复核 Registry 记录；没有导入') from None
 if not item:raise Problem(404,'未找到可复核的真实 MCP 来源')
 from .mcp_bridge import validate_remote_url
 await asyncio.to_thread(validate_remote_url,item['url'])
 aid=stable('x_',w+':directory:'+id)
 with r.store.connection(True) as c:
  r.manage(c,w,user.id)
  if c.execute('SELECT 1 FROM team_platform_assets WHERE id=?',(aid,)).fetchone():return r.get(aid,user.id,c=c)
  r._insert_asset(c,w,user.id,'mcp',item['name'],{'transport':item['transport'],'url':item['url'],'allowed_tools':[],'approval_required':True},item['description'],{'kind':'official_mcp_directory','directory_id':id,'documentation':item['documentation'],'publisher':item['publisher'],'authentication':item['authentication'],'setup_status':'needs_discovery_and_authorization'},aid,False)
 return r.get(aid,user.id)
