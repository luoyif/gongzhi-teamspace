"""Official marketplace entrypoints and encrypted hosted MCP configuration import.
Discovery is not authorization. Imported services stay disabled until tested and
explicitly allowed. No command execution or automatic OAuth grants on import.
"""
from __future__ import annotations
import asyncio,json,re
from urllib.parse import urlsplit,urlunsplit
from typing import Any
from fastapi import APIRouter,Depends,Body
from octop.api.deps import current_user,get_server
from .platform_api import registry
from .presets import is_site_admin
from .store import Problem,dump,now,require_text
router=APIRouter()
MARKETS=[
 {'id':'registry','name':'MCP 官方 Registry','url':'https://registry.modelcontextprotocol.io/','description':'在本应用搜索公开注册记录；连接与工具权限仍需单独核验。','mode':'in_app_search'},
 {'id':'tencent','name':'腾讯云 MCP 广场','url':'https://cloud.tencent.com/developer/mcp','documentation':'https://cloud.tencent.com/document/product/1212/123193','description':'官方及第三方目录；在供应商页面生成个人托管 SSE 配置，再安全导入。','mode':'official_portal_config_import'},
 {'id':'modelscope','name':'ModelScope 魔搭 MCP 广场','url':'https://modelscope.cn/mcp','documentation':'https://modelscope.cn/mcp/servers/@modelscope/modelscope-mcp-server','description':'使用自己的 ModelScope 账号取得专属 SSE 地址。托管地址可能有有效期，地址本身是秘密。','mode':'official_portal_config_import'},
 {'id':'aliyun','name':'阿里云百炼 MCP','url':'https://bailian.console.aliyun.com/?tab=mcp#/mcp-market','documentation':'https://help.aliyun.com/zh/model-studio/official-and-third-party-mcp','description':'One Key 或需开通服务；复制自己的接入配置。部分服务可能计费，不自动开通。','mode':'official_portal_config_import'},
 {'id':'smithery','name':'Smithery','url':'https://smithery.ai/','description':'额外的 MCP 服务目录；完成供应商授权后导入远程配置。','mode':'official_portal_config_import'}]

def ensure(store):
 with store.export_lock:
  if getattr(store,'_sealed_mcp_ready',False):return
  with store.connection() as c:c.execute('CREATE TABLE IF NOT EXISTS team_mcp_private_endpoints(asset_id TEXT PRIMARY KEY,encrypted BLOB NOT NULL,updated_at TEXT NOT NULL)')
  store._sealed_mcp_ready=True

def validate_endpoint(url,resolve=True):
 if not isinstance(url,str) or len(url)>4096 or any(ch in url for ch in ('\r','\n','\x00')):raise Problem(422,'远程连接地址格式无效')
 u=urlsplit(url)
 if u.username or u.password or u.fragment or not u.hostname or u.scheme!='https' or u.port not in (None,443):raise Problem(422,'远程配置仅支持 HTTPS，不接受内嵌账号、片段或非标准端口')
 from .mcp_bridge import validate_remote_url
 validate_remote_url(urlunsplit((u.scheme,u.netloc,u.path,'','')),resolve=resolve)
 return url

def resolve_endpoint(server,r,asset):
 if not asset['data'].get('sealed_endpoint'):return asset['data']['url']
 ensure(r.store)
 with r.store.connection() as c:row=c.execute('SELECT encrypted FROM team_mcp_private_endpoints WHERE asset_id=?',(asset['id'],)).fetchone()
 if not row:raise Problem(503,'专属 MCP 地址缺失，请重新导入配置')
 from octop.infra.auth.sso.crypto import decrypt_secret
 try:return decrypt_secret(server.services.secret_repo,bytes(row[0]))
 except Exception:raise Problem(503,'无法解密专属 MCP 地址') from None

def parse_config(body):
 config=body.get('config');choice=body.get('server_name')
 if not isinstance(config,dict):raise Problem(422,'请提供标准 MCP 配置 JSON')
 servers=config.get('mcpServers')
 if servers is not None:
  if not isinstance(servers,dict) or not 1<=len(servers)<=20:raise Problem(422,'mcpServers 格式无效')
  if choice is None and len(servers)==1:choice=next(iter(servers))
  if choice not in servers:raise Problem(422,'配置有多个服务，请填写要导入的 server_name')
  config=servers[choice]
 if not isinstance(config,dict) or any(k in config for k in ('command','args','env')):raise Problem(422,'广场快速导入仅支持远程 HTTP/SSE；本机命令需独立审核，不在此执行')
 name=require_text(body.get('name') or choice or '远程 MCP','连接名称',80,False)
 url=validate_endpoint(config.get('url') or config.get('serverUrl'),resolve=False)
 transport=config.get('type') or config.get('transport') or ('sse' if urlsplit(url).path.endswith('/sse') else 'streamable_http')
 transport={'http':'streamable_http','streamable-http':'streamable_http'}.get(transport,transport)
 if transport not in ('sse','streamable_http'):raise Problem(422,'仅支持 SSE 和 Streamable HTTP')
 headers=config.get('headers') or {};clean={}
 if not isinstance(headers,dict) or len(headers)>12:raise Problem(422,'认证头格式无效')
 for k,v in headers.items():
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',k) or k.lower() in ('host','content-length','connection','transfer-encoding') or not isinstance(v,str) or len(v)>8192 or '\r' in v or '\n' in v:raise Problem(422,'不支持的认证头')
  clean[k]=v
 if '${' in url or '<' in url or any('${' in v for v in clean.values()):raise Problem(422,'配置仍有占位符，请从自己的账号复制真实配置')
 return name,url,transport,clean

@router.get('/workspaces/{w}/mcp-markets')
def markets(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return {'items':MARKETS,'discovery_is_not_connection':True,'oauth_automatic':False,'accounts_not_linked':True}
@router.post('/workspaces/{w}/mcp-config-import',status_code=201)
async def import_config(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 if not is_site_admin(user):raise Problem(403,'保存远程凭证需要系统管理员')
 name,url,transport,headers=parse_config(body);ensure(r.store)
 from octop.infra.auth.sso.crypto import encrypt_secret
 sealed=encrypt_secret(server.services.secret_repo,url);sealed_headers=encrypt_secret(server.services.secret_repo,dump(headers));host=urlsplit(url).hostname
 source=body.get('source','custom');source=source if source in {x['id'] for x in MARKETS} else 'custom'
 with r.store.connection(True) as c:
  r.manage(c,w,user.id)
  if c.execute("SELECT 1 FROM team_platform_assets WHERE workspace_id=? AND kind='mcp' AND name=?",(w,name)).fetchone():raise Problem(409,'已有同名连接，请使用不同名称，以免覆盖旧凭证')
  aid=r._insert_asset(c,w,user.id,'mcp',name,{'transport':transport,'url':'https://'+host+'/','sealed_endpoint':True,'allowed_tools':[],'approval_required':True},'由管理员导入的专属远程配置；地址已加密，待测试并选择工具。',{'kind':'marketplace_private_config','market':source,'endpoint_host':host,'authorization_status':'needs_probe'},enabled=False)
  c.execute('INSERT INTO team_mcp_private_endpoints VALUES(?,?,?)',(aid,sealed,now()));c.execute('INSERT INTO team_mcp_credentials VALUES(?,?)',(aid,sealed_headers))
 return {**r.get(aid,user.id),'credentials_returned':False,'enabled':False,'connection_tested':False}
