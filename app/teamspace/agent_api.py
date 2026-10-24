"""Thin authenticated adapters for Agents, skills, MCP and task-run SSE."""
from __future__ import annotations
import asyncio,json
from typing import Any
from fastapi import APIRouter,Body,Depends,Query,Request
from fastapi.responses import Response,StreamingResponse
from octop.api.deps import current_user,get_server
from .store import Problem,dump
from .presets import is_site_admin
from .platform_registry import PlatformRegistry as AgentRegistry
from .agent_trace import read_events,decide_approval,require_run

router=APIRouter()

def registry(server):
 from .integration import store_for
 return AgentRegistry(store_for(server))

@router.get('/projects/{p}/capabilities')
def capabilities(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return {'items':registry(server).list(p,user.id),'engine':'octop-harness','engine_version':'1.0.4','one_agent_per_run':True}

@router.post('/projects/{p}/capabilities',status_code=201)
def create(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.require(c,p,user.id,owner=True)
 raise Problem(409,'能力已独立到公司能力中心；项目只启用版本')

@router.patch('/capabilities/{id}')
def update(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);a=r.get(id,user.id)
 raise Problem(409,'请通过公司能力中心更新配置，不在项目入口编辑')

@router.get('/capabilities/{id}/history')
def history(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return {'items':registry(server).history(id,user.id)}

@router.get('/projects/{p}/mention-options')
def mentions(p:str,q:str=Query('',max_length=200),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);agents=[{'id':a['id'],'name':a['name'],'description':a['description'],'revision':a['revision'],'model':a['data']['model'],'type':'agent'} for a in r.list(p,user.id,'agent') if a['enabled'] and q.casefold() in (a['name']+' '+a['description']).casefold()]
 return {'agents':agents,'documents':r.documents(p,user.id,q),'scope':'project_and_published_company_knowledge'}

@router.post('/capabilities/{id}/provider')
async def bind_model(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 raise Problem(409,'模型连接已独立到公司能力中心，请先配置模型资产再给Agent绑定')

@router.get('/projects/{p}/skill-catalog')
async def catalog(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .skill_library import native_catalog
 r=registry(server)
 with r.store.connection() as c:r.store.require(c,p,user.id)
 rows=await asyncio.to_thread(native_catalog)
 return {'items':[{k:v for k,v in x.items() if k not in ('root','markdown','body')} for x in rows],'source':'installed_octop_harness_builtin','import_status':'draft_disabled'}

@router.post('/projects/{p}/skill-import',status_code=201)
async def import_skill(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .skill_library import import_native
 r=registry(server)
 with r.store.connection() as c:r.store.require(c,p,user.id,owner=True)
 raise Problem(409,'请在公司能力中心导入Skill，再通过项目启用')

@router.post('/projects/{p}/skill-from-knowledge',status_code=201)
def from_knowledge(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return registry(server).draft_skill_from_document(p,user.id,body.get('document_id'))

@router.get('/capabilities/{id}/export')
def export_asset(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);a=r.get(id,user.id)
 if a['kind']=='skill':
  from .skill_library import export_zip
  return Response(export_zip(r,a),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="'+id+'-skill.zip"'})
 data=a['data'];text='# '+a['name']+'\n\n'+a['description']+'\n\n'
 if a['kind']=='agent':
  for label,key in [('SYSTEM.md','system_prompt'),('SOUL.md','soul_md'),('AGENTS.md','agents_md'),('SEARCH.md','search_prompt')]:text+='## '+label+'\n\n'+data[key]+'\n\n'
  text+='## Runtime config\n\n```json\n'+json.dumps({k:v for k,v in data.items() if not k.endswith('_md') and not k.endswith('_prompt')},ensure_ascii=False,indent=2)+'\n```\n'
 else:text+='```json\n'+json.dumps(data,ensure_ascii=False,indent=2)+'\n```\n'
 return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="'+id+'.md"'})

@router.post('/capabilities/{id}/mcp-credentials')
def credentials(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .mcp_bridge import save_headers
 save_headers(server,registry(server),id,user,body.get('headers',{}));return {'saved':True,'credentials_returned':False}

@router.post('/capabilities/{id}/mcp-test')
async def probe_mcp(id:str,body:dict=Body(default={}),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .mcp_bridge import load_tools
 r=registry(server);a=r.get(id,user.id,'mcp')
 with r.store.connection() as c:r.manage(c,a['workspace_id'],user.id)
 if not is_site_admin(user):raise Problem(403,'MCP连接测试需系统管理员')
 if a['data']['transport']=='stdio' and body.get('acknowledge_host_execution') is not True:raise Problem(422,'测试会启动已配置的本机程序，需要明确确认')
 tools,_=await load_tools(server,r,a,user.id,for_probe=True)
 return {'status':'connected','tools':[{'name':m['tool_name'],'description':t.description,'input_schema':t.args_schema if isinstance(t.args_schema,dict) else t.args_schema.model_json_schema(),'allowed':m['tool_name'] in a['data']['allowed_tools']} for t,m in tools], 'business_tool_calls':0,'transport':a['data']['transport']}

@router.get('/projects/{p}/runs/{rid}/trace')
def trace(p:str,rid:str,after:int=Query(0,ge=0),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server);return read_events(r.store,p,rid,user.id,after)

@router.get('/projects/{p}/runs/{rid}/events')
async def events(p:str,rid:str,request:Request,after:int=Query(0,ge=0),view:str=Query('trace',pattern='^(trace|activity)$'),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s=registry(server).store;require_run(s,p,rid,user.id)
 from .run_activity import read_activity
 from .agent_trace import subscribe_run
 async def stream():
  cursor=after;idle=0;wake,close=subscribe_run(rid)
  try:
   while not await request.is_disconnected():
    wake.clear()
    try:batch=(read_activity if view=='activity' else read_events)(s,p,rid,user.id,cursor)
    except Problem:
     yield 'event: access_revoked\ndata: {"reason":"access_changed"}\n\n';return
    if view=='activity':yield 'event: run_info\ndata: '+dump(batch['run'])+'\n\n'
    for e in batch['items']:
     cursor=e['seq'];yield 'id: '+str(cursor)+'\nevent: trace\ndata: '+dump(e)+'\n\n'
    if view=='activity' and batch['cursor']>cursor:
     cursor=batch['cursor'];yield 'event: cursor\ndata: '+dump({'cursor':cursor})+'\n\n'
    if batch['has_more']:continue
    if batch['status'] not in ('queued','running'):
     yield 'event: terminal\ndata: '+dump({'status':batch['status'],'cursor':cursor})+'\n\n';return
    idle+=1
    if idle%15==0:yield ': heartbeat\n\n'
    try:await asyncio.wait_for(wake.wait(),timeout=1.0)
    except asyncio.TimeoutError:pass
  finally:close()
 return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

@router.post('/projects/{p}/runs/{rid}/cancel')
def cancel(p:str,rid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 from .api import controller
 return controller(server).cancel_run(p,rid,user.id)

@router.post('/projects/{p}/runs/{rid}/approvals/{id}')
def approve(p:str,rid:str,id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 return decide_approval(registry(server).store,p,rid,id,user.id,body.get('approve'))
