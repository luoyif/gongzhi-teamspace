"""Single-agent execution on the pinned Octop Harness (not a second model loop).

A fresh scoped filesystem is built per run. The shared task transcript remains
in our transactional store; no personal Octop thread/memory is borrowed.
"""
from __future__ import annotations
import asyncio,contextlib,hashlib,json,tempfile,time
from pathlib import Path
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage,AIMessage
from langchain_core.tools import StructuredTool
from octop_harness import HarnessAgent,HarnessAgentConfig,ProviderConfig,ModelConfig,ChatRequest
from octop_harness.llm.factory import ChatModelFactory
from .store import Problem,dump,now,uid
from .context_compaction import compact_history,OutputLimitPause
from .platform_registry import PlatformRegistry as AgentRegistry
from .agent_trace import RunTrace,redact


def tool_name(tool):
 if isinstance(tool,dict):return (tool.get('function') or tool).get('name','')
 return getattr(tool,'name','')


def visible_content(content):
 if isinstance(content,list):return '\n'.join(x.get('text','') for x in content if isinstance(x,dict) and x.get('type')=='text')
 if not isinstance(content,str):return ''
 if '<think>' in content:
  from octop_harness.protocols.think_splitter import ThinkSplitter
  splitter=ThinkSplitter();text,_=splitter.feed(content);inside=splitter.in_think;tail=splitter.drain();return text+('' if inside else tail)
 return content

def message_view(message):
 return {'role':getattr(message,'type','unknown'),'content':visible_content(getattr(message,'content','')),'tool_calls':getattr(message,'tool_calls',[]),'tool_call_id':getattr(message,'tool_call_id',None)}


def current_model_output(message):
 """Only the latest actual model response may complete a run, never history.
 Truncated/unfinished tool arguments are not output text or executable tools.
 """
 if not isinstance(message,AIMessage):return '',{}
 metadata=getattr(message,'response_metadata',{}) or {}
 if message.tool_calls or getattr(message,'invalid_tool_calls',[]):return '',metadata
 return visible_content(message.content),metadata


class NoRetryFactory(ChatModelFactory):
 def __init__(self,*args,cap,transport,**kwargs):
  super().__init__(*args,**kwargs);self.cap=cap;self.transport=transport;self.bound=set();self.google_models={};self.secondary_transports=[]
 def get_chat_model(self,model_ref,*,max_retries=None):
  from .go_models import protocol_config,build_google
  provider_id,_,mid=model_ref.partition('/');provider=self._providers[provider_id]
  protocol,_=protocol_config(provider.base_url,mid)
  if protocol=='google':
   if model_ref not in self.google_models:self.google_models[model_ref]=build_google(provider,mid,self.cap,self.transport)
   return self.google_models[model_ref]
  model=super().get_chat_model(model_ref,max_retries=0)
  if id(model) not in self.bound:
   if protocol=='anthropic':
    # Anthropic 1.x uses httpx2; keep the same audit hooks, but own its transport.
    import httpx2
    transport=httpx2.AsyncClient(timeout=120.0,follow_redirects=False,event_hooks=self.transport.event_hooks)
    self.secondary_transports.append(transport)
    model._async_client=model._async_client.with_options(max_retries=0,timeout=120.0,http_client=transport)
   else:
    client=getattr(model,'root_async_client',None)
    if client is None:raise Problem(503,'模型协议适配器没有可审计的传输接口')
    model.root_async_client=client.with_options(max_retries=0,timeout=120.0,http_client=self.transport)
    model.async_client=model.root_async_client.chat.completions
   model.max_tokens=self.cap;self.bound.add(id(model))
  return model
 async def aclose(self):
  for model in self.google_models.values():
   with contextlib.suppress(Exception):await model.client.aio.aclose()
  for transport in self.secondary_transports:
   with contextlib.suppress(Exception):await transport.aclose()
  await super().aclose()


class SummarizationMiddleware(AgentMiddleware):
 """Replace the native public middleware name, not its private internals.

 Explicit discussion summaries remain normal traced Agent runs. Automatic
 compression/ContextOverflow retries would create unbudgeted paid generations.
 """
 async def awrap_model_call(self,request,handler):
  return await handler(request)


class TaskHarness(HarnessAgent):
 """Pinned narrow extension: native graph, skills, memory files and streaming."""
 def _build_tools(self):
  # No host shell, browser, environment-file, subagent or desktop tools.
  return list(self._config.tools or [])


class TraceGuard(AgentMiddleware):
 def __init__(self,store,registry,cfg,trace,allowed,external):
  super().__init__();self.store=store;self.registry=registry;self.cfg=cfg;self.trace=trace
  self.allowed=set(allowed);self.external=external;self.steps=0;self.tool_count=0
  self.model_span=None;self.started=time.monotonic();self.last_finish=None;self.last_model_response=None;self.budget_finalizing=False;self.warned=False
 def authorize(self):
  if hasattr(self.registry,"assert_run_scope"):self.registry.assert_run_scope(self.cfg)
  with self.store.connection() as c:
   self.store.require(c,self.cfg['_project_id'],self.cfg['_actor_id'],write=True)
   run=c.execute('SELECT status FROM team_runs WHERE id=?',(self.cfg['_run_id'],)).fetchone()
   if not run or run[0]!='running':raise Problem(409,'运行已停止或访问权已撤销')
   agent=self.registry.get(self.cfg['agent_snapshot']['id'],self.cfg['_actor_id'],'agent',c)
   if not agent['enabled']:raise Problem(409,'Agent已被停用')
   for snapshot in self.cfg.get('skill_snapshots',[]):
    skill=self.registry.get(snapshot['id'],self.cfg['_actor_id'],'skill',c)
    if not skill['enabled'] or skill['data']['status']!='published':raise Problem(409,'运行使用的技能已被停用或撤回')
   for snapshot in self.cfg.get('mcp_snapshots',[]):
    asset=self.registry.get(snapshot['id'],self.cfg['_actor_id'],'mcp',c)
    if not asset['enabled'] or asset['revision']!=snapshot['revision']:raise Problem(409,'MCP配置已改变或停用，运行停止')
   for d in self.cfg.get('explicit_documents',[]):self.registry.resolve_document(self.cfg['_project_id'],self.cfg['_actor_id'],d['document_id'],c)
  if time.monotonic()-self.started>self.cfg['agent_snapshot']['data']['timeout_seconds']:raise Problem(504,'Agent达到运行时限')
 async def awrap_model_call(self,request,handler):
  self.authorize()
  if self.steps>=self.cfg['agent_snapshot']['data']['max_model_steps']:raise Problem(429,'Agent达到模型步骤上限，未继续调用')
  self.steps+=1
  tools=[t for t in request.tools or [] if tool_name(t) in self.allowed]
  if self.cfg.get('execution_policy',{}).get('reserve_final_step'):
   limits=self.cfg['agent_snapshot']['data'];remaining=limits['max_model_steps']-self.steps
   final=remaining==0 or self.tool_count>=limits['max_tool_calls'] or limits['timeout_seconds']-(time.monotonic()-self.started)<35
   if remaining<=3 and not self.warned:
    self.warned=True;self.trace.emit('control','budget.warning',{'remaining_model_steps':remaining,'max_model_steps':limits['max_model_steps']},parent_span=self.cfg['_run_id'])
   if final:
    from langchain_core.messages import SystemMessage
    self.budget_finalizing=True;tools=[]
    system=getattr(request.system_message,'content','')
    request=request.override(system_message=SystemMessage(content=str(system)+'\n这是本次预算内最后一步，只输出阶段性结论：已完成、未完成、实际产物ID与建议下一步。不得调用工具，不得把未做的检查称为通过，不得宣称任务全部完成。'),tool_choice='none')
    self.trace.emit('control','budget.finalizing',{'step':self.steps,'max_model_steps':limits['max_model_steps'],'reason':'bounded_budget','further_tool_calls_allowed':False},parent_span=self.cfg['_run_id'])
  compacted,compression=compact_history(request.messages)
  request=request.override(tools=tools,messages=compacted)
  if compression['compressed_messages']:self.trace.emit('input','context.compacted',compression,parent_span=self.cfg['_run_id'])
  input_payload={'step':self.steps,'model':self.cfg['model'],'system':getattr(request.system_message,'content',''),
                 'messages':[message_view(m) for m in request.messages], 'tools':[tool_name(t) for t in tools]}
  if len(dump(input_payload))>300000:raise Problem(422,'本次Agent上下文过大，请减少指定文件或历史范围')
  span=self.trace.emit('model','model.start',input_payload,parent_span=self.cfg['_run_id']);self.model_span=span
  start=time.monotonic()
  try:
   result=await handler(request)
   # Actual final metadata, never an inferred success based on HTTP status.
   response=getattr(result,'result',[])
   for msg in response:
    if isinstance(msg,AIMessage):
     self.last_model_response=msg;meta=getattr(msg,'response_metadata',{}) or {};self.last_finish=meta.get('finish_reason') or meta.get('stop_reason')
     if getattr(msg,'usage_metadata',None):
      if not hasattr(self,'usage_by_step'):self.usage_by_step={}
      self.usage_by_step[self.steps]=dict(msg.usage_metadata)
   self.trace.emit('model','model.end',{'step':self.steps,'elapsed_ms':round((time.monotonic()-start)*1000),'finish_reason':self.last_finish},span_id=span,parent_span=self.cfg['_run_id'])
   if str(self.last_finish).upper() in ('LENGTH','MAX_TOKENS') or getattr(self.last_model_response,'invalid_tool_calls',[]):
    self.trace.emit('control','output.truncated',{'step':self.steps,'finish_reason':self.last_finish,'tool_execution_blocked':True,'automatic_retry':False},parent_span=self.cfg['_run_id'])
    raise OutputLimitPause('模型输出截断；工具参数未执行，不自动重试')
   return result
  except asyncio.CancelledError:raise
  except Exception as exc:
   self.trace.emit('model','model.error',{'step':self.steps,'error_type':type(exc).__name__},span_id=span,parent_span=self.cfg['_run_id']);raise
 async def awrap_tool_call(self,request,handler):
  self.authorize();call=request.tool_call;name=call.get('name','');call_id=call.get('id') or uid('tc_')
  if str(self.last_finish).upper() in ('LENGTH','MAX_TOKENS'):raise OutputLimitPause('截断后的工具参数不执行')
  if self.budget_finalizing:raise Problem(429,'收尾步骤不能继续调用工具；已完成的操作保留')
  if name not in self.allowed:
   self.trace.emit('tool','tool.denied',{'name':name,'reason':'not_in_allowlist'},span_id=call_id,parent_span=self.model_span)
   return ToolMessage(content='工具未授权，未执行。',tool_call_id=call_id,name=name)
  self.tool_count+=1
  if self.tool_count>self.cfg['agent_snapshot']['data']['max_tool_calls']:raise Problem(429,'Agent达到工具调用上限，未执行此工具')
  self.trace.emit('tool','tool.request',{'name':name,'arguments':call.get('args',{})},span_id=call_id,parent_span=self.model_span)
  policy=self.external.get(name)
  if policy:
   if policy.get('asset_id'):
    current=self.registry.get(policy['asset_id'],self.cfg['_actor_id'],'mcp')
    if not current['enabled'] or current['revision']!=policy['asset_revision']:raise Problem(409,'MCP配置已改变，未执行')
    if current['data']['transport'] in ('sse','streamable_http'):
     from .mcp_bridge import validate_remote_url
     await asyncio.to_thread(validate_remote_url,current['data']['url'])
   from .run_policy import mode_now
   full=mode_now(self.store,self.cfg)=='full'
   if policy['approval_required'] and full:
    self.trace.emit('control','approval.auto',{'name':name,'authorized_by':self.cfg['_actor_id'],'permission_mode':'full','scope':'existing_tool_allowlist_this_run'},parent_span=call_id)
   if policy['approval_required'] and not full:
    approval=uid('approval_')
    with self.store.connection(True) as c:c.execute('INSERT INTO team_tool_approvals(id,run_id,tool_name,args_json,requested_at) VALUES(?,?,?,?,?)',(approval,self.cfg['_run_id'],name,dump(redact(call.get('args',{}),self.trace.secrets)),now()))
    self.trace.emit('control','approval.required',{'id':approval,'name':name,'arguments':call.get('args',{}),'expires_in_seconds':60,'scope':'platform' if policy.get('plugin_id') else 'external'},parent_span=call_id)
    until=time.monotonic()+60;decision='pending'
    while time.monotonic()<until:
     self.authorize()
     with self.store.connection() as c:decision=c.execute('SELECT status FROM team_tool_approvals WHERE id=?',(approval,)).fetchone()[0]
     if decision!='pending':break
     await asyncio.sleep(.25)
    if decision!='approved':
     with self.store.connection(True) as c:c.execute("UPDATE team_tool_approvals SET status='expired',decided_at=? WHERE id=? AND status='pending'",(now(),approval))
     self.trace.emit('tool','tool.denied',{'name':name,'reason':decision},span_id=call_id,parent_span=self.model_span)
     return ToolMessage(content='工具没有获得本次批准，未执行。',tool_call_id=call_id,name=name)
  self.authorize()
  if policy and policy.get('approval_required') and full:
   if mode_now(self.store,self.cfg)!='full':raise Problem(409,'免确认授权刚被收回，当前工具未执行；请重新确认后继续')
  start=time.monotonic()
  from .platform_plugins import CALL_ID
  call_token=CALL_ID.set(call_id)
  try:
   result=await asyncio.wait_for(handler(request),timeout=35)
   self.authorize()
   if isinstance(result,ToolMessage):
    content=redact(result.content,self.trace.secrets,limit=200000)
    result=result.model_copy(update={'content':content})
    output={'name':name,'content':content,'elapsed_ms':round((time.monotonic()-start)*1000),'status':getattr(result,'status','success')}
   else:output={'name':name,'result_type':type(result).__name__,'elapsed_ms':round((time.monotonic()-start)*1000)}
   self.trace.emit('tool','tool.result',output,span_id=call_id,parent_span=self.model_span)
   return result
  except asyncio.CancelledError:raise
  except Exception as exc:
   self.trace.emit('tool','tool.error',{'name':name,'error_type':type(exc).__name__},span_id=call_id,parent_span=self.model_span)
   if isinstance(exc,Problem):raise
   return ToolMessage(content='工具执行失败（'+type(exc).__name__+'），未自动重试。',tool_call_id=call_id,name=name,status='error')
  finally:
   CALL_ID.reset(call_token)


async def invoke_agent(server,cfg,messages):
 from .integration import store_for,_base_url
 from .presets import go_headers,is_go,GO_CHAT_MODELS
 from .mcp_bridge import load_tools
 from .skill_library import package_files
 import httpx
 store=store_for(server);registry=AgentRegistry(store);profile=cfg['agent_snapshot'];policy=profile['data']
 p,actor,run_id=cfg['_project_id'],cfg['_actor_id'],cfg['_run_id']
 row=server.services.provider_repo.get_by_name(cfg['provider_name'])
 if row is None or not row.enabled or row.kind!='openai':raise Problem(422,'Agent绑定模型不可用')
 _base_url(row.base_url)
 from .go_models import model_info,protocol_config,safe_model_payload
 if is_go(row.base_url) and not model_info(cfg['model']) and cfg['model'] not in GO_CHAT_MODELS:raise Problem(422,'模型不在已核查的Go目录中')
 protocol,base_url=protocol_config(row.base_url,cfg['model'])
 trace=RunTrace(store,run_id,[row.api_key]);sources=list(cfg.get('_context_sources',[]));extra_tools=[];external={};known_secrets=[row.api_key]
 for asset in ([] if (cfg.get('_lightweight_greeting') or cfg.get('_summary_only')) else cfg.get('mcp_snapshots',[])):
  loaded,secrets=await load_tools(server,registry,asset,actor);known_secrets.extend(secrets)
  for tool,meta in loaded:extra_tools.append(tool);external[tool.name]=meta
 trace.secrets=tuple(known_secrets)
 def add_source(d):
  if not any(s['document_id']==d['document_id'] and s['revision']==d['revision'] for s in sources):sources.append(d)
 async def project_search(query:str)->str:
  """Search only this task's project documents and explicitly published company knowledge. Returns source IDs and versions."""
  from .progressive_context import search_chunks
  hits=search_chunks(store,registry,p,actor,require_text_local(query),4)
  for d in hits:add_source(d)
  return dump(hits)
 async def project_read_document(document_id:str,offset:int=0,length:int=4000)->str:
  """Read a currently visible project document or a company-public snapshot by its exact ID. Never reads arbitrary server paths."""
  d=registry.resolve_document(p,actor,document_id)
  if type(offset) is not int or type(length) is not int or offset<0 or not 1<=length<=24000:raise Problem(422,'读取范围不正确')
  length=min(length,6000);total=len(d['content']);d['content']=d['content'][offset:offset+length];d.update(offset=offset,total_characters=total,has_more=offset+length<total,next_offset=offset+length if offset+length<total else None);add_source(d);return dump(d)
 available={'project_search':project_search,'project_read_document':project_read_document}
 for name in policy['tools']:extra_tools.append(StructuredTool.from_function(coroutine=available[name],name=name))
 from .platform_plugins import build_tools
 plugin_tools,plugin_policies=build_tools(store,registry,cfg)
 extra_tools.extend(plugin_tools);external.update(plugin_policies)
 allowed=set(policy['tools'])|set(external)
 if policy.get('retrieval_mode','automatic')!='disabled':
  from .project_space import build_space_tools
  space_tools=build_space_tools(store,registry,cfg,add_source);extra_tools.extend(space_tools);allowed.update(t.name for t in space_tools)
 if cfg.get('conversation_task_id'):
  from .task_conversation import build_tool
  extra_tools.append(build_tool(store,cfg));allowed.add('task_conversation_read')
 if cfg.get('skill_snapshots'):allowed|={'read_file','ls','glob','grep'}
 from .context_compaction import build_readback
 extra_tools.append(build_readback(store,registry,cfg));allowed.add('tool_result_read')
 if (cfg.get('_lightweight_greeting') or cfg.get('_summary_only')):extra_tools=[];allowed=set();external={}
 guard=TraceGuard(store,registry,cfg,trace,allowed,external)
 async def audit_request(request):
  guard.authorize()
  raw=await request.aread()
  try:payload=json.loads(raw)
  except (ValueError,UnicodeError):raise Problem(502,'模型请求不是预期的JSON协议') from None
  raw_tools=payload.get('tools',[])
  flat_tools=[f for t in raw_tools for f in (t.get('functionDeclarations') or t.get('function_declarations') or [t])]
  names=[tool_name(t) for t in flat_tools]
  if set(names)-allowed:
   trace.emit('control','request.blocked',{'reason':'unexpected_tools','tools':names})
   raise Problem(403,'Harness最后阶段加入了未授权工具，已阻止请求')
  if len(raw)>600000:
   trace.emit('control','request.blocked',{'reason':'input_too_large','bytes':len(raw)})
   raise Problem(422,'最终模型输入过大；请减少历史或引用，不会暗中请求付费压缩')
  safe=safe_model_payload(payload)
  trace.emit('model','model.request',{'protocol':protocol,'model':payload.get('model',cfg['model']),'messages':safe.get('messages',safe.get('input',safe.get('contents',[]))),'system':safe.get('system',safe.get('instructions',safe.get('systemInstruction'))),'tools':safe.get('tools',[]),'stream':payload.get('stream',':streamGenerateContent' in str(request.url)),'max_output_tokens':payload.get('max_completion_tokens',payload.get('max_output_tokens',payload.get('max_tokens',(payload.get('generationConfig') or {}).get('maxOutputTokens')))),'body_sha256':hashlib.sha256(raw).hexdigest(),'body_bytes':len(raw),'headers_included':False},span_id=guard.model_span,parent_span=run_id)

 transport=httpx.AsyncClient(timeout=120.0,follow_redirects=False,limits=httpx.Limits(max_connections=4,max_keepalive_connections=2),event_hooks={'request':[audit_request]})
 usage_by_call={};final_messages=[];partial='';buffer='';last_flush=time.monotonic();harness=None;factory=None
 def aggregate():
  observed=getattr(guard,'usage_by_step',{})
  if len(observed)>len(usage_by_call):usage_by_call.clear();usage_by_call.update({str(k):v for k,v in observed.items()})
  if not usage_by_call:return None
  result={key:sum(int(v.get(key) or 0) for v in usage_by_call.values()) for key in ('input_tokens','output_tokens','total_tokens')}
  result.update(source='provider',model_calls_with_usage=len(usage_by_call),model_steps=guard.steps,complete=len(usage_by_call)==guard.steps)
  for detail in ('input_token_details','output_token_details'):
   keys=set(k for u in usage_by_call.values() for k in (u.get(detail) or {}))
   result[detail]={key:sum(int((u.get(detail) or {}).get(key) or 0) for u in usage_by_call.values()) for key in keys}
  return result
 from langsmith import tracing_context
 with tempfile.TemporaryDirectory(prefix='gongzhi-agent-') as directory, tracing_context(enabled=False):
  try:
   (Path(directory)/'_builtin_skills').mkdir()
   (Path(directory)/'skills').mkdir()
   provider=ProviderConfig(id='project',base_url=base_url,api_key=row.api_key,protocol='anthropic' if protocol=='anthropic' else 'openai',headers=go_headers(row.base_url,cfg['provider_name']+':'+str(cfg.get('conversation_task_id'))),models=[ModelConfig(id=cfg['model'],api_mode='responses' if protocol=='responses' else 'chat_completions',max_output_tokens=policy['max_output_tokens'],max_input_tokens=262144)])
   config=HarnessAgentConfig(name=profile['name'],workspace_dir=directory,backend={'type':'filesystem','root_dir':directory,'virtual_mode':True},providers=[provider],default_model='project/'+cfg['model'],
     system_prompt=messages[0]['content'],memory=[] if (cfg.get('_lightweight_greeting') or cfg.get('_summary_only')) else ['SOUL.md','AGENTS.md'],skills_dir=[] if (cfg.get('_lightweight_greeting') or cfg.get('_summary_only')) else ['/skills'],
     tools=extra_tools,middleware=[SummarizationMiddleware(),guard],memory_enabled=False,checkpointer=False,session_log_enabled=False,
     web_search_tools=False,team_enabled=False,subagents_auto_load=False,subagents=[],ask_user_enabled=False,
     model_retry_enabled=False,todos_enabled=False,media_offload_enabled=False,tool_guard_enabled=True,
     tools_disabled=frozenset({'task','execute','write_file','edit_file','web_fetch','browser_use','desktop_screenshot','write_todos','ask_user_question'}),
     default_timezone='Asia/Shanghai')
   factory=NoRetryFactory([provider],agent_config=config,cap=policy['max_output_tokens'],transport=transport)
   # SDK/TLS client construction can be expensive; never block UI requests.
   await asyncio.to_thread(factory.get_chat_model,'project/'+cfg['model'])
   harness=TaskHarness(config,model_factory=factory,agent_id=profile['id'])
   # Agent-visible content exclusively goes through the native workspace facade.
   harness.workspace.write_text('SOUL.md',policy['soul_md'])
   harness.workspace.write_text('AGENTS.md',policy['agents_md'])
   slugs=[]
   for skill in ([] if (cfg.get('_lightweight_greeting') or cfg.get('_summary_only')) else cfg.get('skill_snapshots',[])):
    slug=skill['data']['slug'];slugs.append(slug)
    for name,content in package_files(registry,skill).items():
     if name.endswith(('.md','.txt','.json','.yaml','.yml','.py','.js','.ts','.sh','.csv')):
      harness.workspace.write_text('skills/'+slug+'/'+name,content.decode('utf8',errors='replace'))
   trace.emit('agent','agent.runtime',{'engine':'octop-harness','version':'1.0.4','agent_id':profile['id'],'revision':profile['revision'],'name':profile['name'],'skill_versions':[{'id':s['id'],'revision':s['revision'],'slug':s['data']['slug']} for s in cfg.get('skill_snapshots',[])],'allowed_tools':sorted(allowed),'memory_source':'current_shared_task_and_authorized_project_data','private_native_memory':False,'platform_plugins':[{'id':x['id'],'version':x['version']} for x in cfg.get('plugin_snapshots',[])]},span_id=run_id)
   request=ChatRequest(messages=messages[1:],thread_id=cfg.get('conversation_task_id') or run_id,user=str(actor),source='gongzhi-shared-task',agent_id=profile['id'],skills=[],recursion_limit=policy['max_model_steps']*16+32, # Graph middleware transitions are not model calls; TraceGuard enforces the paid-call cap.
                       configurable={} if protocol=='google' else {'model_settings':{'max_tokens':policy['max_output_tokens']}})
   async with asyncio.timeout(policy['timeout_seconds']):
    async for event in harness.stream(request):
     guard.authorize();kind=str(event.get('type',''))
     if kind=='token':
      text=event.get('content','');buffer+=text;partial+=text
      if len(partial)>150000:raise Problem(502,'Agent输出超过保存上限')
      if len(buffer)>160 or time.monotonic()-last_flush>.075:
       trace.emit('output','output.delta',{'text':buffer,'model_step':guard.steps},parent_span=guard.model_span);buffer='';last_flush=time.monotonic()
     elif kind=='usage':
      usage_by_call[event.get('call_id') or str(guard.steps)]=event.get('usage') or {};trace.account(aggregate())
     elif kind=='state_snapshot':final_messages=(event.get('data') or {}).get('messages',final_messages)
    if buffer:trace.emit('output','output.delta',{'text':buffer,'model_step':guard.steps},parent_span=guard.model_span)
   guard.authorize();content,metadata=current_model_output(guard.last_model_response);usage=aggregate();trace.account(usage)
   trace.emit('agent','agent.finished',{'model_steps':guard.steps,'tool_calls':guard.tool_count,'usage':usage},parent_span=run_id)
   return {'content':content,'usage':usage,'finish_reason':('length' if str(metadata.get('finish_reason') or metadata.get('stop_reason') or guard.last_finish).upper() in ('MAX_TOKENS','LENGTH') else metadata.get('finish_reason') or metadata.get('stop_reason') or guard.last_finish),'sources':sources,'budget_limited':guard.budget_finalizing}
  except asyncio.CancelledError:
   trace.account(aggregate());trace.emit('control','run.cancelled',{'partial_output_saved_in_trace':True});raise
  except OutputLimitPause:
   usage=aggregate();trace.account(usage);content,_=current_model_output(guard.last_model_response)
   return {'content':content,'usage':usage,'finish_reason':'length','sources':sources,'budget_limited':False}
  except TimeoutError:
   trace.account(aggregate());raise Problem(504,'Agent运行超时；未自动重试，已知用量保留') from None
  except Exception as exc:
   trace.account(aggregate())
   if isinstance(exc,Problem):raise
   trace.emit('agent','agent.error',{'error_type':type(exc).__name__,'http_status':getattr(exc,'status_code',None)})
   raise Problem(502,'Agent运行失败（'+type(exc).__name__+(' / HTTP '+str(exc.status_code) if getattr(exc,'status_code',None) else '')+'）；请展开Trace核查，未自动重试') from None
  finally:
   if harness:
    with contextlib.suppress(Exception):await harness.aclose()
   if factory:
    with contextlib.suppress(Exception):await factory.aclose()
   await transport.aclose()


def require_text_local(query):
 if not isinstance(query,str) or not query.strip() or len(query)>1000:raise Problem(422,'检索词需为1–1000字符')
 return query.strip()
