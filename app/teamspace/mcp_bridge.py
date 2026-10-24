"""MCP library using Octop's installed MCP adapter, with project-bound authority.

Remote endpoints are admin-configured HTTPS; external tool execution always
needs per-call approval. stdio is explicitly trusted host code, not a sandbox.
"""
from __future__ import annotations
import asyncio,ipaddress,json,re,socket,sys,os
from pathlib import Path
from urllib.parse import urlsplit
from .store import Problem,dump
from .presets import is_site_admin


def validate_remote_url(value,resolve=True):
 if not isinstance(value,str) or len(value)>1000:raise Problem(422,'MCP地址格式错误')
 u=urlsplit(value)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise Problem(422,'远程MCP必须使用不含密码和查询参数的HTTPS地址')
 if u.hostname.lower() in ('localhost','metadata.google.internal'):raise Problem(422,'不能使用私网MCP地址；本地工具请使用明确审批的stdio')
 try:
  ip=ipaddress.ip_address(u.hostname)
  if not ip.is_global:raise Problem(422,'MCP不能连接私网、回环或链路本地地址')
 except ValueError:pass
 if resolve:
  try:addresses=socket.getaddrinfo(u.hostname,u.port or 443,type=socket.SOCK_STREAM)
  except OSError:raise Problem(502,'MCP域名解析失败') from None
  if not addresses:raise Problem(422,'MCP域名没有可用地址')
  addresses_ip=[ipaddress.ip_address(a[4][0]) for a in addresses]
  if any(not ip.is_global for ip in addresses_ip):
   # Narrow deployment opt-in for a TUN fake-IP resolver. It is NOT a private
   # network allowlist: literal IPs/RFC1918/link-local addresses remain blocked.
   known={'learn.microsoft.com':'/api/mcp','mcp.neon.tech':'/mcp','mcp.supabase.com':'/mcp','mcp.exa.ai':'/mcp'}
   approved=set((os.environ.get('TEAMSPACE_MCP_TUN_HOSTS') or '').split(','))
   home=os.environ.get('OCTOP_HOME')
   if home:
    try:approved.update(json.loads((Path(home)/'network-policy.json').read_text(encoding='utf8')).get('mcp_tun_hosts',[]))
    except (OSError,ValueError,TypeError):pass
   proxy_ranges=(ipaddress.ip_network('198.18.0.0/15'),ipaddress.ip_network('fdfe:dcba:9876::/48'))
   proxy_only=all(ip.is_global or any(ip.version==network.version and ip in network for network in proxy_ranges) for ip in addresses_ip)
   if not (u.hostname in approved and known.get(u.hostname)==u.path.rstrip('/') and proxy_only):raise Problem(422,'MCP域名指向非公网地址；TUN代理仅能由部署管理员按官方主机单独批准')
 return value.rstrip('/')


def save_headers(server,registry,id,actor,headers):
 if not is_site_admin(actor):raise Problem(403,'只有系统管理员可设置MCP凭证')
 asset=registry.get(id,actor.id,'mcp')
 if hasattr(registry,'require_manage_asset'):registry.require_manage_asset(id,actor.id)
 else:
  with registry.store.connection() as c:registry.store.require(c,asset['project_id'],actor.id,owner=True)
 if not isinstance(headers,dict) or len(headers)>12:raise Problem(422,'认证头必须为有限对象')
 clean={}
 for k,v in headers.items():
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',k) or k.lower() in ('host','content-length','connection','transfer-encoding') or not isinstance(v,str) or len(v)>8192 or '\r' in v or '\n' in v:raise Problem(422,'不支持的认证头')
  clean[k]=v
 from octop.infra.auth.sso.crypto import encrypt_secret
 encrypted=encrypt_secret(server.services.secret_repo,dump(clean))
 with registry.store.connection(True) as c:
  if hasattr(registry,'require_manage_asset'):
   from .store import now
   current=registry.get(id,actor.id,'mcp',c);registry.manage(c,current['workspace_id'],actor.id)
   registry.store.revision(current,{'expected_revision':asset['revision']})
   c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(id,current['revision'],dump(current),now()))
   c.execute('UPDATE team_platform_assets SET revision=revision+1,updated_at=? WHERE id=?',(now(),id))
  c.execute('INSERT INTO team_mcp_credentials VALUES(?,?) ON CONFLICT(asset_id) DO UPDATE SET encrypted=excluded.encrypted',(id,encrypted))


def read_headers(server,registry,id):
 with registry.store.connection() as c:row=c.execute('SELECT encrypted FROM team_mcp_credentials WHERE asset_id=?',(id,)).fetchone()
 if not row:return {}
 from octop.infra.auth.sso.crypto import decrypt_secret
 try:return json.loads(decrypt_secret(server.services.secret_repo,bytes(row[0])))
 except Exception:raise Problem(503,'MCP认证配置无法解密，请重新配置') from None


def connection_spec(asset,headers=None):
 d=asset['data'];kind=d['transport']
 if kind=='builtin':return {'transport':'stdio','command':sys.executable,'args':['-m','teamspace.mcp_builtin'],'env':{'PYTHONPATH':str(Path(__file__).resolve().parents[1])}}
 if kind in ('streamable_http','sse'):
  return {'transport':kind,'url':validate_remote_url(d['url']),'headers':headers or {},'timeout':15,'sse_read_timeout':30}
 command=Path(d['command'])
 if not command.is_absolute() or not command.is_file():raise Problem(422,'MCP可执行文件不存在；不会下载或安装外部程序')
 return {'transport':'stdio','command':str(command),'args':d['args']}


async def load_tools(server,registry,asset,actor,for_probe=False):
 # This adapter is also Octop Harness's MCP transport implementation. Preserve
 # complete JSON schemas instead of coercing nested JSON arguments to strings.
 from langchain_mcp_adapters.client import MultiServerMCPClient
 from octop_harness.mcp import sanitize_llm_tool_name
 current=registry.get(asset['id'],actor,'mcp')
 if not for_probe and (not current['enabled'] or current['revision']!=asset['revision']):raise Problem(409,'MCP配置已改变，请重新发起运行')
 headers=read_headers(server,registry,asset['id'])
 from .mcp_markets import resolve_endpoint,validate_endpoint
 resolved=resolve_endpoint(server,registry,asset) if asset['data'].get('sealed_endpoint') else None
 if resolved:
  await asyncio.to_thread(validate_endpoint,resolved)
  spec={'transport':asset['data']['transport'],'url':resolved,'headers':headers,'timeout':15,'sse_read_timeout':30}
 else:spec=await asyncio.to_thread(connection_spec,asset,headers)
 try:
  tools=await asyncio.wait_for(MultiServerMCPClient({asset['id']:spec},tool_name_prefix=True).get_tools(),timeout=25)
 except asyncio.CancelledError:raise
 except (Exception,BaseExceptionGroup):raise Problem(502,'MCP连接或工具发现失败；请检查本地日志及认证配置，未自动重试') from None
 allowed=set(asset['data'].get('allowed_tools',[]));prefix=asset['id']+'_';result=[]
 for tool in tools[:100]:
  raw=tool.name.removeprefix(prefix)
  if not for_probe and raw not in allowed:continue
  tool.name=sanitize_llm_tool_name(tool.name)
  result.append((tool,{'asset_id':asset['id'],'asset_revision':asset['revision'],'server_name':asset['name'],'tool_name':raw,'approval_required':asset['data']['transport']!='builtin','_resolved_endpoint':resolved}))
 if not for_probe and allowed-set(m['tool_name'] for _,m in result):raise Problem(409,'MCP允许清单中的工具已缺失；请重新测试连接，不会静默跳过')
 return result,list(headers.values())+([resolved] if resolved else [])
