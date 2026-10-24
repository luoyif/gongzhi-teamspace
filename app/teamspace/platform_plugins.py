"""Native, project-scoped platform plugins. Mutations require per-call approval.
Not shell/desktop control: plugins share the existing database, revisions, ACL,
review workflow and outbox. Every mutation has an atomic idempotent receipt.
"""
from __future__ import annotations
import contextvars,hashlib,json,re
from .store import Problem,dump,now,uid,require_text
CALL_ID=contextvars.ContextVar('gongzhi_tool_call_id',default='')
CATALOG=[
 {'id':'platform.read','name':'项目工作台','description':'读取当前项目规划、成员、任务、日程和资料目录，不读取其他私有项目。','tools':['platform_overview'],'write':False},
 {'id':'calendar.manage','name':'日程管理','description':'查询、新建、改期和取消当前项目日程；写入前逐次确认，保留历史。','tools':['calendar_list','calendar_create','calendar_update','calendar_cancel'],'write':True},
 {'id':'tasks.manage','name':'任务与子任务','description':'拆分任务、设置期限和负责人、提交待验收成果；不替人确认完成。','tools':['task_list','task_create','task_update'],'write':True},
 {'id':'knowledge.manage','name':'知识整理','description':'建立和修订项目知识草稿、归档旧条目，保留来源；不自动发布公司知识。','tools':['knowledge_list','knowledge_save','knowledge_update','knowledge_archive'],'write':True},
 {'id':'project.plan','name':'项目规划','description':'读取并修订当前项目规划；版本冲突停止，修改需确认。','tools':['project_plan_get','project_plan_update'],'write':True},
 {'id':'skill.draft','name':'经验转技能','description':'从已确认知识生成可复用技能草稿；初始受限、停用，审核后才能发布。','tools':['skill_draft_create'],'write':True},
 {'id':'artifacts.write','name':'任务文件产出','description':'保存 Markdown、JSON、CSV、文本产物到当前项目资料，供下载和 @ 引用；不执行任意代码。','tools':['artifact_save','artifact_section_save'],'write':True},
]
CATALOG.append({'id':'memory.manage','name':'项目记忆整理','description':'从项目资料整理带来源的 Markdown 记忆草稿；原始附件不覆盖，写入前确认。','tools':['project_memory_save'],'write':True})
from .professional_tools import CATALOG as PROFESSIONAL_CATALOG
CATALOG.extend(PROFESSIONAL_CATALOG)
READ_TOOLS={'python_syntax_check','platform_overview','calendar_list','task_list','knowledge_list','project_plan_get'}
BY_ID={x['id']:dict(x,version=1) for x in CATALOG}
SCHEMA='''CREATE TABLE IF NOT EXISTS team_plugin_receipts(
 run_id TEXT NOT NULL,operation_key TEXT NOT NULL,tool_name TEXT NOT NULL,
 payload_hash TEXT NOT NULL,result_json TEXT NOT NULL,actor_id INTEGER NOT NULL,
 created_at TEXT NOT NULL,PRIMARY KEY(run_id,operation_key));'''

def ensure_schema(store):
 with store.schema_lock:
  if getattr(store,'_plugin_schema_ready',False):return
  with store.connection() as c:c.executescript(SCHEMA)
  store._plugin_schema_ready=True

def selected_plugins(value):
 if not isinstance(value,list) or len(value)>len(CATALOG) or any(not isinstance(x,str) or x not in BY_ID for x in value):raise Problem(422,'平台插件选择无效')
 return list(dict.fromkeys(value))

class PlatformOperations:
 def __init__(self,store,registry,cfg):
  self.store,self.registry,self.cfg=store,registry,cfg
  self.p,self.actor,self.run_id=cfg['_project_id'],cfg['_actor_id'],cfg['_run_id']
  self.task_id=cfg.get('conversation_task_id');ensure_schema(store)
 def authorize(self,c,write=False):
  self.store.require(c,self.p,self.actor,write=write)
  run=c.execute('SELECT status FROM team_runs WHERE id=? AND project_id=?',(self.run_id,self.p)).fetchone()
  if not run or run[0]!='running':raise Problem(409,'执行已停止，未操作项目')
  binding=self.cfg.get('platform_binding')
  if binding and binding.get('implicit'):
   from .workspace_staff import assert_implicit
   assert_implicit(self.registry,c,self.cfg);return
  if binding:
   current=self.registry.binding(c,self.p,binding['asset_id'],self.actor)
   if current['revision']!=binding['binding_revision']:raise Problem(409,'员工授权版本已变化，未继续操作')
   for frozen in current['bundle']['assets']:
    a=self.registry._raw(c,frozen['id']);self.registry._usable_in(c,a,self.p,self.actor)
    if a['kind'] in ('model','mcp') and a['revision']!=frozen['revision']:raise Problem(409,'连接版本已变化')
 def row(self,c,id,kind):
  row=self.store.object_row(c,id,self.actor,True,kind)
  if row['project_id']!=self.p:raise Problem(404,'对象不属于当前项目')
  return row
 def provenance(self):return {'run_id':self.run_id,'task_id':self.task_id,'agent_id':self.cfg['agent_snapshot']['id'],'origin':'approved_platform_plugin','adopted':False}
 def source(self,c,seq):
  if seq is not None:
   if type(seq) is not int:raise Problem(422,'来源消息需为整数')
   row=c.execute('SELECT meta_json FROM team_messages WHERE project_id=? AND seq=?',(self.p,seq)).fetchone()
   if not row or json.loads(row[0]).get('task_id')!=self.task_id:raise Problem(422,'来源必须在当前任务讨论中')
 def mutation(self,name,payload,fn):
  if name not in {t for plugin in self.cfg.get('plugin_snapshots',[]) for t in plugin['tools']}:raise Problem(403,'此员工没有该平台插件权限')
  key=CALL_ID.get()
  if not key:raise Problem(403,'写入只能在已审批的运行工具上下文中执行')
  encoded=dump(payload);digest=hashlib.sha256(encoded.encode()).hexdigest()
  with self.store.connection(True) as c:
   self.authorize(c,True)
   receipt=c.execute('SELECT * FROM team_plugin_receipts WHERE run_id=? AND operation_key=?',(self.run_id,key)).fetchone()
   if receipt:
    if receipt['payload_hash']!=digest or receipt['tool_name']!=name:raise Problem(409,'同一工具请求被用于不同变更')
    return dump({**json.loads(receipt['result_json']),'duplicate':True})
   result=fn(c);result.update(operation=name,run_id=self.run_id,project_id=self.p)
   c.execute('INSERT INTO team_plugin_receipts VALUES(?,?,?,?,?,?,?)',(self.run_id,key,name,digest,dump(result),self.actor,now()))
   self.store.touch(c,self.p)
  return dump(result)
 def overview(self):
  with self.store.connection() as c:
   self.authorize(c);p=dict(c.execute('SELECT id,title,goal,plan,timezone,revision FROM team_projects WHERE id=?',(self.p,)).fetchone());members=[dict(r) for r in c.execute('SELECT user_id,display_name,role FROM team_members WHERE project_id=?',(self.p,))]
  return dump({'project':p,'members':members,'current_task_id':self.task_id})
 def listing(self,kind):
  with self.store.connection() as c:
   self.authorize(c);rows=c.execute("SELECT * FROM team_objects WHERE project_id=? AND kind=? AND status!='deleted' ORDER BY updated_at DESC LIMIT 100",(self.p,kind)).fetchall()
   items=[self.store.object_json(r) for r in rows]
  if kind=='document':items=[{k:d.get(k) for k in ('id','title','status','revision','task_id','adopted','document_kind')} for d in items]
  return dump({'items':items,'limit':100,'project_id':self.p})
 def event_create(self,body):
  def apply(c):
   title,text,data=self.store.validate_event(body);self.source(c,data.get('source_seq'));data.update(self.provenance());id=self.store.put_object(c,self.p,'event',title,text,self.actor,data)
   return {'id':id,'revision':1,'status':'active','title':title}
  return self.mutation('calendar_create',body,apply)
 def event_update(self,id,revision,patch,cancel=False):
  if type(revision) is not int or revision<1:raise Problem(422,'对象版本需为正整数')
  def apply(c):
   row=self.row(c,id,'event');self.store.revision(row,{'expected_revision':revision});old=self.store.object_json(row)
   if row['status']=='cancelled':raise Problem(409,'日程已经取消')
   if cancel:title,text,data=row['title'],row['body'],json.loads(row['data_json'])
   else:
    if set(patch)-{'title','body','starts_at','ends_at','event_kind','source_seq'}:raise Problem(422,'不支持的日程字段')
    vals={**old,**patch};vals['kind']=vals.get('event_kind','meeting');title,text,data=self.store.validate_event(vals);self.source(c,data.get('source_seq'))
   data.update(self.provenance());status='cancelled' if cancel else row['status']
   c.execute('UPDATE team_objects SET title=?,body=?,data_json=?,status=?,revision=revision+1,updated_at=? WHERE id=?',(title,text,dump(data),status,now(),id))
   return {'id':id,'revision':revision+1,'status':status,'title':title}
  return self.mutation('calendar_cancel' if cancel else 'calendar_update',{'id':id,'revision':revision,'patch':patch},apply)
 def task_change(self,body,id=None,revision=None):
  if id and (type(revision) is not int or revision<1):raise Problem(422,'对象版本需为正整数')
  def apply(c):
   if set(body)-{'title','body','assignee_id','executor','status','blocked','due_date','criteria','result','parent_id','source_seq'}:raise Problem(422,'不支持的任务字段')
   if body.get('status')=='done':raise Problem(403,'AI只能提交待验收，不能替成员确认完成')
   old=None
   if id:
    row=self.row(c,id,'task');self.store.revision(row,{'expected_revision':revision});old=self.store.object_json(row)
    if row['status']=='done':raise Problem(409,'已验收任务需先由成员重新打开')
   vals=self.store.validate_task(c,self.p,body,old);self.source(c,vals.get('source_seq'));title,text,status=vals.pop('title'),vals.pop('body'),vals.pop('status');vals.update({'origin_run_id':self.run_id})
   if id:
    c.execute('UPDATE team_objects SET title=?,body=?,status=?,data_json=?,revision=revision+1,updated_at=? WHERE id=?',(title,text,status,dump(vals),now(),id));target=id
   else:target=self.store.put_object(c,self.p,'task',title,text,self.actor,vals,status)
   return {'id':target,'revision':revision+1 if id else 1,'title':title,'status':status}
  return self.mutation('task_update' if id else 'task_create',{'id':id,'revision':revision,'body':body},apply)
 def knowledge(self,title,body,id=None,revision=None,source_seq=None,archive=False):
  if id and (type(revision) is not int or revision<1):raise Problem(422,'对象版本需为正整数')
  title=require_text(title,'知识标题',200,False);body=require_text(body,'知识正文',100000,archive)
  def apply(c):
   self.source(c,source_seq);data={**self.provenance(),'document_kind':'note','source_seq':source_seq}
   if id:
    row=self.row(c,id,'document');self.store.revision(row,{'expected_revision':revision});old=json.loads(row['data_json'])
    if old.get('blob_path') and not archive:raise Problem(409,'原始附件不可覆盖，请另存修订知识')
    data={**old,**data};status='archived' if archive else 'ready'
    c.execute('UPDATE team_objects SET title=?,body=?,status=?,data_json=?,revision=revision+1,updated_at=? WHERE id=?',(title,body,status,dump(data),now(),id));target=id
   else:target=self.store.put_object(c,self.p,'document',title,body,self.actor,data,'ready');status='ready'
   self.store.index(c,target,self.p,[] if archive else [('员工整理 · 待核对',body)],title)
   return {'id':target,'revision':revision+1 if id else 1,'status':status,'adopted':False,'title':title}
  return self.mutation('knowledge_archive' if archive else 'knowledge_update' if id else 'knowledge_save',{'id':id,'revision':revision,'title':title,'body':body,'source_seq':source_seq},apply)
 def plan_update(self,revision,plan):
  if type(revision) is not int or revision<1:raise Problem(422,'对象版本需为正整数')
  plan=require_text(plan,'项目规划',80000)
  def apply(c):
   row=c.execute('SELECT * FROM team_projects WHERE id=?',(self.p,)).fetchone();self.store.revision(row,{'expected_revision':revision})
   c.execute('UPDATE team_projects SET plan=?,revision=revision+1,updated_at=? WHERE id=?',(plan,now(),self.p));return {'id':self.p,'revision':revision+1,'status':'updated'}
  return self.mutation('project_plan_update',{'revision':revision,'plan':plan},apply)
 def skill_draft(self,document_id,name,slug,body):
  name=require_text(name,'技能名称',80,False);body=require_text(body,'SKILL.md',100000,False)
  if not re.fullmatch('[a-z0-9][a-z0-9_-]{0,79}',slug):raise Problem(422,'技能标识格式无效')
  def apply(c):
   self.store.require(c,self.p,self.actor,owner=True);d=self.registry.resolve_document(self.p,self.actor,document_id,c)
   if not d['adopted']:raise Problem(422,'先由成员采用来源知识，再沉淀技能')
   w=self.registry.workspace_for_project(c,self.p,self.actor);aid=self.registry._insert_asset(c,w,self.actor,'skill',name,{'slug':slug,'body':body,'status':'draft'},source={'kind':'project_knowledge_draft','origin_project_id':self.p,'document_id':d['id'],'document_revision':d['revision'],'run_id':self.run_id,'review_before_sharing':True},enabled=False,visibility='restricted');c.execute('INSERT INTO team_platform_grants VALUES(?,?)',(aid,self.p));return {'id':aid,'revision':1,'status':'draft','enabled':False}
  return self.mutation('skill_draft_create',{'document_id':document_id,'name':name,'slug':slug,'body':body},apply)
 def memory(self,title,content,document_ids):
  title=require_text(title,'记忆标题',200,False);content=require_text(content,'记忆正文',100000,False)
  from .agent_registry import identifiers
  ids=identifiers(document_ids,'来源文件',20)
  if not ids:raise Problem(422,'项目记忆须至少保留一个来源文件')
  def apply(c):
   refs=[]
   for id in ids:
    d=self.registry.resolve_document(self.p,self.actor,id,c);refs.append({'document_id':id,'revision':d['revision'],'title':d['title']})
   body=content+'\n\n## 来源\n'+'\n'.join('- '+x['title']+' · '+x['document_id']+' · v'+str(x['revision']) for x in refs)
   data={**self.provenance(),'document_kind':'memory','source_documents':refs}
   target=self.store.put_object(c,self.p,'document',title,body,self.actor,data,'ready');self.store.index(c,target,self.p,[('记忆草稿 · 待核对',body)],title)
   return {'id':target,'revision':1,'title':title,'status':'ready','adopted':False,'path':'memory/'+target+'.md'}
  return self.mutation('project_memory_save',{'title':title,'content':content,'document_ids':ids},apply)
 def artifact(self,filename,content):
  if not isinstance(filename,str) or not re.fullmatch(r'[\w .-]{1,120}\.(md|txt|json|csv)',filename) or '..' in filename:raise Problem(422,'只允许简单文件名与 md/txt/json/csv 格式')
  content=require_text(content,'产物正文',100000,False)
  if filename.endswith('.json'):
   try:json.loads(content)
   except ValueError:raise Problem(422,'JSON产物格式无效') from None
  raw=content.encode();sha=hashlib.sha256(raw).hexdigest();relative='blobs/'+sha
  def apply(c):
   existing=c.execute("SELECT id,title,revision,data_json FROM team_objects WHERE project_id=? AND kind='document' AND title=? AND status='ready' AND json_extract(data_json,'$.task_id')=? ORDER BY created_at DESC LIMIT 1",(self.p,filename,self.task_id)).fetchone()
   if existing and not self.store.deleted(c,existing['id']):
    old=json.loads(existing['data_json'])
    if old.get('sha256')==sha:return {'id':existing['id'],'title':filename,'revision':existing['revision'],'sha256':sha,'status':'ready','duplicate':True,'adopted':bool(old.get('adopted'))}
    raise Problem(409,'同任务已存在同名产物；请回读核对，不重复创建。长报告使用artifact_section_save分节保存')
   target=self.store.data_dir/relative
   if not target.exists():target.write_bytes(raw);target.chmod(0o600)
   data={**self.provenance(),'document_kind':'file','filename':filename,'blob_path':relative,'sha256':sha,'bytes':len(raw),'origin':'agent_artifact'}
   id=self.store.put_object(c,self.p,'document',filename,content,self.actor,data,'ready');self.store.index(c,id,self.p,[('待验收任务文件',content)],filename)
   return {'id':id,'title':filename,'status':'ready','adopted':False,'sha256':sha,'revision':1}
  return self.mutation('artifact_save',{'filename':filename,'content':content},apply)

def build_tools(store,registry,cfg):
 from langchain_core.tools import StructuredTool
 ops=PlatformOperations(store,registry,cfg)
 async def platform_overview()->str:
  """Read current project plan, timezone, revision and member IDs before planning actions."""
  return ops.overview()
 async def calendar_list()->str:
  """List current project calendar events with IDs, dates and revisions; cancelled entries are labelled."""
  return ops.listing('event')
 async def calendar_create(title:str,starts_at:str,ends_at:str|None=None,body:str='',event_kind:str='meeting')->str:
  """Create an event AFTER human approval. Dates require ISO8601 timezone. Do not invent dates."""
  return ops.event_create(dict(title=title,starts_at=starts_at,ends_at=ends_at,body=body,kind=event_kind))
 async def calendar_update(event_id:str,expected_revision:int,changes:dict)->str:
  """Update an event AFTER approval; use latest revision from calendar_list. Changes: title/body/starts_at/ends_at/event_kind."""
  return ops.event_update(event_id,expected_revision,changes)
 async def calendar_cancel(event_id:str,expected_revision:int)->str:
  """Cancel an event AFTER approval, preserving its history. Never cancels another project's event."""
  return ops.event_update(event_id,expected_revision,{},True)
 async def task_list()->str:
  """List current project's tasks, owners, revisions and acceptance criteria."""
  return ops.listing('task')
 async def task_create(title:str,body:str='',criteria:str='',assignee_id:int|None=None,due_date:str|None=None,parent_id:str|None=None)->str:
  """Create a task/subtask AFTER approval. Owner must be a current member. due_date is YYYY-MM-DD or null."""
  return ops.task_change(dict(title=title,body=body,criteria=criteria,assignee_id=assignee_id,due_date=due_date,parent_id=parent_id))
 async def task_update(task_id:str,expected_revision:int,changes:dict)->str:
  """Update a task AFTER approval. Can submit result/status=review or cancel; may NOT mark done or accept on behalf of humans."""
  return ops.task_change(changes,task_id,expected_revision)
 async def knowledge_list()->str:
  """List authorized project knowledge/document IDs and review status."""
  return ops.listing('document')
 async def knowledge_save(title:str,body:str,source_seq:int|None=None)->str:
  """Save a Markdown knowledge draft AFTER approval. Not adopted or company-published; retain current task source."""
  return ops.knowledge(title,body,source_seq=source_seq)
 async def knowledge_update(document_id:str,expected_revision:int,title:str,body:str)->str:
  """Revise a knowledge note AFTER approval; does not overwrite original attachments. New text needs review."""
  return ops.knowledge(title,body,document_id,expected_revision)
 async def knowledge_archive(document_id:str,expected_revision:int)->str:
  """Archive a project note AFTER approval; preserve original/version, exclude from new retrieval."""
  with store.connection() as c:ops.authorize(c);r=ops.row(c,document_id,'document');title,body=r['title'],r['body']
  return ops.knowledge(title,body,document_id,expected_revision,archive=True)
 async def project_plan_get()->str:
  """Read the current project plan and revision before proposing an update."""
  return ops.overview()
 async def project_plan_update(expected_revision:int,plan:str)->str:
  """Replace the current project Markdown plan AFTER human approval with optimistic revision protection."""
  return ops.plan_update(expected_revision,plan)
 async def skill_draft_create(document_id:str,name:str,slug:str,body:str)->str:
  """Create a disabled restricted SKILL.md draft from adopted project knowledge AFTER approval. Requires project owner."""
  return ops.skill_draft(document_id,name,slug,body)
 async def artifact_save(filename:str,content:str)->str:
  """Save a downloadable md/txt/json/csv task artifact AFTER approval. No arbitrary file paths or code execution."""
  return ops.artifact(filename,content)
 async def project_memory_save(title:str,content:str,source_document_ids:list[str])->str:
  """Create a source-linked project Markdown memory draft AFTER explicit approval. Never adopts it, publishes to company, or overwrites raw files."""
  return ops.memory(title,content,source_document_ids)
 functions={f.__name__:f for f in (project_memory_save,platform_overview,calendar_list,calendar_create,calendar_update,calendar_cancel,task_list,task_create,task_update,knowledge_list,knowledge_save,knowledge_update,knowledge_archive,project_plan_get,project_plan_update,skill_draft_create,artifact_save)}
 from .professional_tools import functions as professional_functions
 functions.update(professional_functions(ops))
 from .artifact_sections import build as section_tool
 functions['artifact_section_save']=section_tool(ops)
 tools=[];policies={}
 for plugin in cfg.get('plugin_snapshots',[]):
  for name in plugin['tools']:
   tools.append(StructuredTool.from_function(coroutine=functions[name],name=name));policies[name]={'plugin_id':plugin['id'],'approval_required':name not in READ_TOOLS}
 return tools,policies
