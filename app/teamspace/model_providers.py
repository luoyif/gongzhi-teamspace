"""Workspace provider groups, discovery, local model lifecycle and bounded probes.
No external calls during GET/list/navigation. Model deletion is a local archive,
not vendor-side deletion; referenced/default models cannot be removed silently.
"""
from __future__ import annotations
import asyncio,hashlib,json,urllib.parse
from typing import Any
from fastapi import APIRouter,Body,Depends
from octop.api.deps import current_user,get_server
from .store import Problem,dump,now,uid,require_text
from .platform_api import registry,_model_lock
from .platform_registry import stable
from .integration import _base_url
router=APIRouter()
SCHEMA='''
CREATE TABLE IF NOT EXISTS team_model_providers(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,family TEXT NOT NULL,
 base_url TEXT NOT NULL,models_url TEXT NOT NULL,native_name TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1,enabled INTEGER NOT NULL DEFAULT 1,
 discovered_json TEXT NOT NULL DEFAULT '[]',discovered_at TEXT,last_error TEXT,
 created_by INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_vendor_models(
 provider_id TEXT NOT NULL,asset_id TEXT NOT NULL,archived INTEGER NOT NULL DEFAULT 0,
 last_test_json TEXT,PRIMARY KEY(provider_id,asset_id));
CREATE TABLE IF NOT EXISTS team_model_probe_jobs(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,provider_id TEXT NOT NULL,
 actor_id INTEGER NOT NULL,status TEXT NOT NULL,request_json TEXT NOT NULL,
 results_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL,finished_at TEXT);
'''

def ensure(store):
 with store.schema_lock:
  if getattr(store,'_model_provider_schema',False):return
  with store.connection() as c:
   c.executescript(SCHEMA)
   c.execute("UPDATE team_model_probe_jobs SET status='interrupted',finished_at=? WHERE status='running'",(now(),))
  store._model_provider_schema=True

def validate_model_destination(url):
 import ipaddress,socket,os
 from pathlib import Path
 u=urllib.parse.urlsplit(_base_url(url))
 if u.hostname in ('localhost','127.0.0.1','::1'):return
 try:addresses=[ipaddress.ip_address(a[4][0]) for a in socket.getaddrinfo(u.hostname,u.port or 443,type=socket.SOCK_STREAM)]
 except OSError:raise Problem(502,'模型地址DNS解析失败') from None
 if not addresses:raise Problem(422,'模型地址没有有效解析')
 if any(not ip.is_global for ip in addresses):
  approved=set((__import__('os').environ.get('TEAMSPACE_MODEL_TUN_HOSTS') or '').split(','));home=os.environ.get('OCTOP_HOME')
  if home:
   try:approved.update(json.loads((Path(home)/'network-policy.json').read_text()).get('model_tun_hosts',[]))
   except (OSError,ValueError,TypeError):pass
  ranges=(ipaddress.ip_network('198.18.0.0/15'),ipaddress.ip_network('fdfe:dcba:9876::/48'))
  fake_only=all(ip.is_global or any(ip.version==n.version and ip in n for n in ranges) for ip in addresses)
  known=u.hostname=='opencode.ai' and u.port in (None,443) and u.path.startswith(('/inference/','/zen/'))
  if not (known and u.hostname in approved and fake_only):raise Problem(422,'模型地址解析到私网；未连接。TUN例外仅限部署管理员批准的官方主机')

def public(row):
 d=dict(row);d.pop('native_name',None);d['discovered']=json.loads(d.pop('discovered_json'));d['enabled']=bool(d['enabled']);d['configured']=True;return d

def provider_get(r,id,actor,manage=False):
 ensure(r.store)
 with r.store.connection() as c:
  row=c.execute('SELECT * FROM team_model_providers WHERE id=?',(id,)).fetchone()
  if not row or r.store.deleted(c,id):raise Problem(404,'厂商连接不存在或已删除')
  r.store.workspace_require(c,row['workspace_id'],actor,owner=manage)
  return dict(row)

def family_for(url):
 from .go_models import is_go_url
 u=urllib.parse.urlsplit(url)
 if is_go_url(url):return 'opencode-go','OpenCode Go','https://opencode.ai/inference/go/v1/models'
 if u.hostname=='opencode.ai':return 'opencode','OpenCode',url.rstrip('/')+'/models'
 return 'openai-compatible',u.hostname or '自定义厂商',url.rstrip('/')+'/models'

def bootstrap(r,server,w,actor):
 ensure(r.store)
 with r.store.connection() as c:
  r.store.workspace_require(c,w,actor)
  missing=c.execute("SELECT 1 FROM team_platform_assets a LEFT JOIN team_vendor_models m ON m.asset_id=a.id WHERE a.workspace_id=? AND a.kind='model' AND a.visibility='workspace' AND json_extract(a.data_json,'$.configured')=1 AND m.asset_id IS NULL LIMIT 1",(w,)).fetchone()
  if not missing:return
 with r.store.connection(True) as c:
  r.store.workspace_require(c,w,actor)
  rows=c.execute("SELECT a.* FROM team_platform_assets a LEFT JOIN team_vendor_models m ON m.asset_id=a.id WHERE a.workspace_id=? AND a.kind='model' AND a.visibility='workspace' AND m.asset_id IS NULL",(w,)).fetchall()
  for raw in rows:
   a=r.row(raw);d=a['data'];name=d.get('provider_name');native=server.services.provider_repo.get_by_name(name) if name else None
   if not native or not d.get('configured'):continue
   family,label,models=family_for(d['base_url']);key_hash=hashlib.sha256((native.api_key or '').encode()).hexdigest()
   group_scope=family if family in ('opencode','opencode-go') else d['base_url'].rstrip('/')
   id=stable('vendor_',w+':'+group_scope+':'+key_hash)
   c.execute('INSERT OR IGNORE INTO team_model_providers(id,workspace_id,name,family,base_url,models_url,native_name,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,w,label,family,d['base_url'],models,name,a['created_by'],now(),now()))
   c.execute('INSERT INTO team_vendor_models(provider_id,asset_id) VALUES(?,?)',(id,a['id']))

def used_by(r,c,asset_id):
 refs=[]
 for row in c.execute("SELECT id,name,data_json FROM team_platform_assets WHERE kind='agent' AND enabled=1"):
  if json.loads(row['data_json']).get('model_id')==asset_id:refs.append({'kind':'agent','id':row['id'],'name':row['name']})
 for row in c.execute('SELECT project_id,bundle_json FROM team_platform_bindings WHERE enabled=1'):
  if r.store.deleted(c,row['project_id']):continue
  if any(a['id']==asset_id for a in json.loads(row['bundle_json'])['assets']):refs.append({'kind':'project_binding','id':row['project_id']})
 if c.execute('SELECT 1 FROM team_platform_defaults WHERE model_id=?',(asset_id,)).fetchone():refs.append({'kind':'default'})
 return refs

@router.get('/workspaces/{w}/model-providers')
def groups(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);bootstrap(r,server,w,user.id)
 from pathlib import Path
 prior={}
 try:
  prior_report=json.loads((Path(server.services.paths.root).parent/'evidence/ui5-go-model-tests.json').read_text())
  prior={x['model_id']:dict(x,evidence='ui5-go-model-tests.json',at=prior_report.get('finished_at'),historical=True) for x in prior_report.get('results',[])}
 except (OSError,ValueError,KeyError,AttributeError):pass
 with r.store.connection() as c:
  member=r.store.workspace_require(c,w,user.id);items=[];referenced=set()
  for row in c.execute("SELECT data_json FROM team_platform_assets WHERE workspace_id=? AND kind='agent' AND enabled=1",(w,)):
   mid=json.loads(row[0]).get('model_id')
   if mid:referenced.add(mid)
  for row in c.execute('SELECT b.bundle_json FROM team_platform_bindings b JOIN team_project_workspace pw ON pw.project_id=b.project_id WHERE pw.workspace_id=? AND b.enabled=1',(w,)):
   referenced.update(a['id'] for a in json.loads(row[0])['assets'] if a['kind']=='model')
  referenced.update(row[0] for row in c.execute('SELECT model_id FROM team_platform_defaults WHERE workspace_id=?',(w,)))
  for row in c.execute('SELECT * FROM team_model_providers WHERE workspace_id=? ORDER BY name,id',(w,)):
   if r.store.deleted(c,row['id']):continue
   vendor=public(row);models=[]
   for m in c.execute('SELECT a.*,m.archived,m.last_test_json FROM team_vendor_models m JOIN team_platform_assets a ON a.id=m.asset_id WHERE m.provider_id=? ORDER BY a.name',(row['id'],)):
    try:r._visible(c,r.row(m),user.id)
    except Problem:continue
    a=r.row(m);a.pop('last_test_json',None);a['verification']=json.loads(m['last_test_json']) if m['last_test_json'] else (prior.get(a['data'].get('model')) if vendor['family']=='opencode-go' else None);a['referenced']=a['id'] in referenced;models.append(a)
   vendor['models']=models;items.append(vendor)
 return {'items':items,'can_manage':member['role']=='owner','external_calls':0,'deletion_scope':'local_archive_only'}

@router.post('/workspaces/{w}/model-providers',status_code=201)
async def create_provider(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);ensure(r.store)
 with r.store.connection() as c:r.manage(c,w,user.id)
 name=require_text(body.get('name'),'厂商名称',80,False);base=_base_url(body.get('base_url'));models=_base_url(body.get('models_url') or base+'/models')
 if urllib.parse.urlsplit(models).netloc!=urllib.parse.urlsplit(base).netloc:raise Problem(422,'模型发现地址必须与 API 地址同一主机，避免泄露密钥')
 key=require_text(body.get('api_key'),'API Key',8192,False)
 async with _model_lock:
  id=uid('vendor_');native_name='team-project-vendor-'+id;family,label,_=family_for(base)
  with r.store.connection() as c:
   if c.execute('SELECT 1 FROM team_model_providers WHERE workspace_id=? AND name=?',(w,name)).fetchone():raise Problem(409,'此团队已存在同名厂商，可编辑原连接')
  from .presets import go_headers
  server.services.provider_repo.create(name=native_name,kind='openai',base_url=base,api_key=key,models_json='[]',extra_json=dump({'headers':go_headers(base,native_name)}),note='Company provider '+id)
  with r.store.connection(True) as c:
   r.manage(c,w,user.id);c.execute('INSERT INTO team_model_providers(id,workspace_id,name,family,base_url,models_url,native_name,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,w,name,family,base,models,native_name,user.id,now(),now()))
 return public(provider_get(r,id,user.id))

@router.patch('/model-providers/{id}')
async def edit_provider(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 async with _model_lock:
  old=provider_get(r,id,user.id,True);r.store.revision(old,body)
  base=_base_url(body.get('base_url',old['base_url']));models=_base_url(body.get('models_url',old['models_url']));name=require_text(body.get('name',old['name']),'厂商名称',80,False)
  if urllib.parse.urlsplit(models).netloc!=urllib.parse.urlsplit(base).netloc:raise Problem(422,'模型发现地址必须与 API 同一主机')
  key=body.get('api_key','')
  if not isinstance(key,str) or len(key)>8192:raise Problem(422,'密钥格式无效')
  connection_changed=base!=old['base_url'] or bool(key.strip())
  if base!=old['base_url'] and not key.strip():raise Problem(422,'更换地址必须重新提供密钥')
  native=server.services.provider_repo.get_by_name(old['native_name'])
  if not native:raise Problem(409,'原连接已不存在')
  if connection_changed:
   from .presets import go_headers
   server.services.provider_repo.update(native.id,base_url=base,api_key=key.strip() or native.api_key,extra_json=dump({'headers':go_headers(base,native.name)}))
  with r.store.connection(True) as c:
   r.manage(c,old['workspace_id'],user.id);c.execute('UPDATE team_model_providers SET name=?,base_url=?,models_url=?,revision=revision+1,updated_at=? WHERE id=?',(name,base,models,now(),id))
   if connection_changed:
    for row in c.execute('SELECT a.* FROM team_platform_assets a JOIN team_vendor_models m ON m.asset_id=a.id WHERE m.provider_id=?',(id,)).fetchall():
     a=r.row(row);d={**a['data'],'provider_name':old['native_name'],'base_url':base}
     c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(a['id'],a['revision'],dump(a),now()));c.execute('UPDATE team_platform_assets SET data_json=?,revision=revision+1,updated_at=? WHERE id=?',(dump(d),now(),a['id']))
 return {**public(provider_get(r,id,user.id)),'project_bindings_require_upgrade':connection_changed}

async def fetch_models(url,key):
 import httpx
 # Explicitly configured HTTPS/same-host endpoints only. Never forward credentials
 # through redirects. Bound size and timeout; failures are not empty successes.
 await asyncio.to_thread(validate_model_destination,url)
 async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=5),follow_redirects=False) as client:
  async with client.stream('GET',url,headers={'Authorization':'Bearer '+key,'User-Agent':'gongzhi-teamspace/0.6.0'}) as response:
   if response.status_code!=200:raise Problem(502,'模型目录读取失败：HTTP '+str(response.status_code))
   chunks=[];size=0
   async for chunk in response.aiter_bytes():
    size+=len(chunk)
    if size>2000000:raise Problem(502,'模型目录超过2MB限制')
    chunks.append(chunk)
 try:data=json.loads(b''.join(chunks));rows=data['data']
 except (ValueError,KeyError,TypeError):raise Problem(502,'供应方未返回 OpenAI /models 的 data 数组；可手动添加模型 ID') from None
 if not isinstance(rows,list):raise Problem(502,'模型目录格式无效')
 out={}
 for row in rows[:1000]:
  if isinstance(row,dict) and isinstance(row.get('id'),str) and 0<len(row['id'])<=200:
   out[row['id']]={'id':row['id'],'name':str(row.get('name') or row['id'])[:200],'owned_by':str(row.get('owned_by',''))[:200]}
 return list(out.values())

@router.post('/model-providers/{id}/discover')
async def discover(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);v=provider_get(r,id,user.id,True);native=server.services.provider_repo.get_by_name(v['native_name'])
 if native is None:raise Problem(409,'请重新配置厂商连接')
 try:items=await fetch_models(v['models_url'],native.api_key)
 except Exception as e:
  message=e.detail if isinstance(e,Problem) else '模型目录连接失败（'+type(e).__name__+'），未自动重试'
  with r.store.connection(True) as c:c.execute('UPDATE team_model_providers SET last_error=? WHERE id=?',(message,id))
  raise Problem(502,message) from None
 with r.store.connection(True) as c:
  r.manage(c,v['workspace_id'],user.id);current=c.execute('SELECT revision FROM team_model_providers WHERE id=?',(id,)).fetchone()
  if current[0]!=v['revision']:raise Problem(409,'连接在发现期间被修改，未保存旧目录')
  c.execute('UPDATE team_model_providers SET discovered_json=?,discovered_at=?,last_error=NULL WHERE id=?',(dump(items),now(),id))
 return {'items':items,'source':'provider_models_endpoint','discovered_at':now(),'generation_calls':0}

@router.post('/model-providers/{id}/models')
async def import_models(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);v=provider_get(r,id,user.id,True);ids=body.get('model_ids',[])
 if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(x,str) or not x.strip() or len(x)>200 for x in ids):raise Problem(422,'选择1–100个模型ID')
 native=server.services.provider_repo.get_by_name(v['native_name'])
 if not native or not native.enabled:raise Problem(409,'厂商连接不可用')
 from .go_models import model_info
 added=[]
 with r.store.connection(True) as c:
  r.manage(c,v['workspace_id'],user.id)
  for mid in dict.fromkeys(ids):
   if v['family']=='opencode-go' and not model_info(mid):raise Problem(422,'此 Go 模型尚无协议映射，不能冒充可运行')
   aid=stable('v_',id+':'+mid);old=c.execute("SELECT a.id FROM team_vendor_models m JOIN team_platform_assets a ON a.id=m.asset_id WHERE m.provider_id=? AND json_extract(a.data_json,'$.model')=? ",(id,mid)).fetchone()
   if old:
    existing=r.get(old[0],user.id,'model',c)
    link=c.execute('SELECT archived FROM team_vendor_models WHERE provider_id=? AND asset_id=?',(id,old[0])).fetchone()
    if link[0]:
     c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(old[0],existing['revision'],dump(existing),now()))
     c.execute('UPDATE team_platform_assets SET enabled=1,revision=revision+1,updated_at=? WHERE id=?',(now(),old[0]));c.execute('UPDATE team_vendor_models SET archived=0 WHERE provider_id=? AND asset_id=?',(id,old[0]))
    added.append(old[0]);continue
   if c.execute('SELECT 1 FROM team_platform_assets WHERE id=?',(aid,)).fetchone():raise Problem(409,'模型已归档，请先恢复后再添加')
   r._insert_asset(c,v['workspace_id'],user.id,'model',mid,{'provider_name':v['native_name'],'base_url':v['base_url'],'model':mid,'configured':True},'厂商：'+v['name'],{'kind':'vendor_model','provider_id':id},aid,True)
   c.execute('INSERT INTO team_vendor_models(provider_id,asset_id) VALUES(?,?)',(id,aid));added.append(aid)
 return {'added_or_existing':added,'generation_calls':0}

@router.post('/model-providers/{id}/models/archive')
async def archive(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);v=provider_get(r,id,user.id,True);ids=body.get('asset_ids',[])
 if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(x,str) for x in ids):raise Problem(422,'模型选择无效')
 results=[]
 with r.store.connection(True) as c:
  r.manage(c,v['workspace_id'],user.id)
  for aid in dict.fromkeys(ids):
   link=c.execute('SELECT * FROM team_vendor_models WHERE provider_id=? AND asset_id=?',(id,aid)).fetchone()
   if not link:raise Problem(404,'模型不属于此厂商')
   a=r.get(aid,user.id,'model',c)
   if link['archived']:results.append({'id':aid,'status':'archived','duplicate':True});continue
   refs=used_by(r,c,aid)
   if refs:results.append({'id':aid,'status':'blocked_in_use','references':len(refs)});continue
   c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(aid,a['revision'],dump(a),now()))
   c.execute('UPDATE team_platform_assets SET enabled=0,revision=revision+1,updated_at=? WHERE id=?',(now(),aid));c.execute('UPDATE team_vendor_models SET archived=1 WHERE provider_id=? AND asset_id=?',(id,aid));results.append({'id':aid,'status':'archived'})
 return {'results':results,'remote_models_deleted':False,'historical_runs_preserved':True}

async def probe_one(server,r,asset_id,user,job):
 import httpx
 from octop_harness import ProviderConfig,ModelConfig
 from .agent_runtime import NoRetryFactory,visible_content
 from .go_models import protocol_config
 from .presets import go_headers
 a=r.get(asset_id,user.id,'model');native=server.services.provider_repo.get_by_name(a['data']['provider_name'])
 result={'asset_id':asset_id,'model_id':a['data']['model'],'at':now(),'scope':'single_streaming_coding_probe','requests':0};factory=None
 if not a['enabled'] or not native or not native.enabled:return {**result,'status':'unavailable'}
 protocol,base=protocol_config(native.base_url,a['data']['model']);_base_url(base)
 def check():
  with r.store.connection() as c:
   r.manage(c,a['workspace_id'],user.id)
   s=c.execute('SELECT status FROM team_model_probe_jobs WHERE id=?',(job,)).fetchone()
   if not s or s[0]!='running':raise Problem(409,'测试已停止')
 async def audit(request):check();result['requests']+=1
 transport=httpx.AsyncClient(timeout=25,follow_redirects=False,event_hooks={'request':[audit]})
 try:
  check();await asyncio.to_thread(validate_model_destination,base);provider=ProviderConfig(id='probe',api_key=native.api_key,base_url=base,protocol='anthropic' if protocol=='anthropic' else 'openai',headers=go_headers(native.base_url,job+':'+asset_id),models=[ModelConfig(id=a['data']['model'],api_mode='responses' if protocol=='responses' else 'chat_completions',max_output_tokens=512)])
  factory=NoRetryFactory([provider],cap=512,transport=transport);model=await asyncio.to_thread(factory.get_chat_model,'probe/'+a['data']['model']);full=None
  async with asyncio.timeout(30):
   async for chunk in model.astream([{'role':'user','content':'Code connection test: Python function f() returns 2 + 3. Reply with its result only, no explanation.'}]):full=chunk if full is None else full+chunk
  result['usage']=getattr(full,'usage_metadata',None);text=visible_content(getattr(full,'content','')).strip();meta=getattr(full,'response_metadata',{}) or {};reason=str(meta.get('finish_reason') or meta.get('stop_reason','')).lower()
  result.update(status='passed' if text=='5' and reason not in ('length','max_tokens') else 'needs_review',output_preview=text[:200],stream_received=full is not None)
 except asyncio.CancelledError:raise
 except Exception as e:
  result.update(status='failed',error_type=type(e).__name__,http_status=getattr(e,'status_code',None))
  if 'full' in locals() and full is not None:result['usage']=getattr(full,'usage_metadata',None)
 finally:
  if factory:
   try:await factory.aclose()
   except Exception:pass
  await transport.aclose()
 return result

async def probe_job(server,r,v,ids,user,jid):
 results=[]
 try:
  for aid in ids:
   with r.store.connection() as c:
    r.manage(c,v['workspace_id'],user.id);status=c.execute('SELECT status FROM team_model_probe_jobs WHERE id=?',(jid,)).fetchone()[0]
   if status!='running':break
   value=await probe_one(server,r,aid,user,jid);results.append(value)
   with r.store.connection(True) as c:
    c.execute('UPDATE team_model_probe_jobs SET results_json=? WHERE id=?',(dump(results),jid));c.execute('UPDATE team_vendor_models SET last_test_json=? WHERE provider_id=? AND asset_id=?',(dump(value),v['id'],aid))
  with r.store.connection(True) as c:c.execute("UPDATE team_model_probe_jobs SET status=CASE WHEN status='running' THEN 'completed' ELSE status END,finished_at=? WHERE id=?",(now(),jid))
 except BaseException:
  with r.store.connection(True) as c:c.execute("UPDATE team_model_probe_jobs SET status='interrupted',finished_at=? WHERE id=? AND status='running'",(now(),jid))

@router.post('/model-providers/{id}/test',status_code=202)
async def test_models(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);v=provider_get(r,id,user.id,True);ids=body.get('asset_ids',[])
 if not isinstance(ids,list) or not 1<=len(ids)<=50 or any(not isinstance(x,str) for x in ids):raise Problem(422,'一次选择1–50个模型')
 ids=list(dict.fromkeys(ids))
 with r.store.connection(True) as c:
  r.manage(c,v['workspace_id'],user.id)
  if c.execute("SELECT 1 FROM team_model_probe_jobs WHERE workspace_id=? AND status='running'",(v['workspace_id'],)).fetchone():raise Problem(409,'团队已有一批模型测试在运行')
  for aid in ids:
   a=r.get(aid,user.id,'model',c)
   if not c.execute('SELECT 1 FROM team_vendor_models WHERE provider_id=? AND asset_id=? AND archived=0',(id,aid)).fetchone() or not a['enabled']:raise Problem(422,'选择包含不可用模型')
  jid=uid('probe_');c.execute("INSERT INTO team_model_probe_jobs(id,workspace_id,provider_id,actor_id,status,request_json,created_at) VALUES(?,?,?,?,'running',?,?)",(jid,v['workspace_id'],id,user.id,dump(ids),now()))
 task=asyncio.create_task(probe_job(server,r,v,ids,user,jid));jobs=getattr(server,'team_model_jobs',None)
 if jobs is None:jobs=set();server.team_model_jobs=jobs
 jobs.add(task);task.add_done_callback(jobs.discard)
 return {'id':jid,'status':'running','selected':len(ids),'automatic_retries':False,'maximum_output_tokens_per_model':512}

@router.get('/model-probes/{id}')
def probe_status(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);ensure(r.store)
 with r.store.connection() as c:
  row=c.execute('SELECT * FROM team_model_probe_jobs WHERE id=?',(id,)).fetchone()
  if not row:raise Problem(404,'测试不存在')
  r.store.workspace_require(c,row['workspace_id'],user.id,owner=True);d=dict(row);d['results']=json.loads(d.pop('results_json'));d['selected']=len(json.loads(d.pop('request_json')));return d

@router.post('/model-probes/{id}/cancel')
def cancel_probe(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);d=probe_status(id,user,server)
 with r.store.connection(True) as c:c.execute("UPDATE team_model_probe_jobs SET status='cancelled',finished_at=? WHERE id=? AND status='running'",(now(),id))
 return {'status':'cancelled','in_flight_request_may_finish':True}
