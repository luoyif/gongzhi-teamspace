"""Workspace capability control plane; projects only hold version-pinned bindings.

Legacy tables are never rewritten. Migration retains IDs, provider rows, skill
files and MCP ciphertext. A binding is an immutable dependency bundle; it does
not carry chat history, filesystem access, or another project's authority.
"""
from __future__ import annotations
import hashlib
import json
from .agent_registry import AgentRegistry as LegacyRegistry, AGENT_DEFAULTS, identifiers, integer
from .store import Problem, dump, now, uid, require_text

SCHEMA = '''
CREATE TABLE IF NOT EXISTS team_platform_assets(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES team_workspaces(id),
 kind TEXT NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
 enabled INTEGER NOT NULL DEFAULT 1,revision INTEGER NOT NULL DEFAULT 1,
 visibility TEXT NOT NULL DEFAULT 'workspace',data_json TEXT NOT NULL,
 source_json TEXT NOT NULL DEFAULT '{}',created_by INTEGER NOT NULL,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS team_platform_workspace ON team_platform_assets(workspace_id,kind);
CREATE TABLE IF NOT EXISTS team_platform_versions(
 asset_id TEXT NOT NULL,revision INTEGER NOT NULL,snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL,PRIMARY KEY(asset_id,revision));
CREATE TABLE IF NOT EXISTS team_platform_grants(
 asset_id TEXT NOT NULL,project_id TEXT NOT NULL REFERENCES team_projects(id),
 PRIMARY KEY(asset_id,project_id));
CREATE TABLE IF NOT EXISTS team_platform_bindings(
 project_id TEXT NOT NULL REFERENCES team_projects(id),asset_id TEXT NOT NULL,
 asset_revision INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1,
 enabled INTEGER NOT NULL DEFAULT 1,bundle_json TEXT NOT NULL,
 created_by INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(project_id,asset_id));
CREATE TABLE IF NOT EXISTS team_platform_binding_history(
 project_id TEXT NOT NULL,asset_id TEXT NOT NULL,revision INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL,changed_at TEXT NOT NULL,
 PRIMARY KEY(project_id,asset_id,revision));
CREATE TABLE IF NOT EXISTS team_platform_bootstrap(workspace_id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_platform_migrations(name TEXT PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_platform_defaults(workspace_id TEXT PRIMARY KEY,model_id TEXT);
'''

HARNESS_DEFAULTS = {
    'engine':'octop-harness','engine_version':'1.0.4','execution_mode':'single_agent',
    'max_model_steps':4,'max_tool_calls':8,'timeout_seconds':180,'max_output_tokens':4096,
    'history_limit':60,'max_context_chars':60000,'max_documents':6,'max_document_chars':30000,
    'tools':['project_search','project_read_document'],'retrieval_mode':'automatic',
    'stream':True,'automatic_retry':False,'external_tool_approval':'per_call',
    'memory_scope':'task_project_published_company','result_policy':'human_review',
}
PROMPTS = ('system_prompt','soul_md','agents_md','search_prompt')
KINDS = ('agent','skill','mcp','harness','model')


def stable(prefix, value):
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:24]


class PlatformRegistry(LegacyRegistry):
    def __init__(self,store):
        super().__init__(store)
        with store.schema_lock:
            if not getattr(store,'_platform_schema_ready',False):
                with store.connection() as c:c.executescript(SCHEMA)
                self.migrate()
                store._platform_schema_ready=True

    def workspace_for_project(self,c,p,actor=None,owner=False):
        if actor is not None:self.store.require(c,p,actor,owner=owner)
        row=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(p,)).fetchone()
        if not row:raise Problem(404,'项目未归属公司／团队')
        return row[0]

    def manage(self,c,w,actor):
        return self.store.workspace_require(c,w,actor,owner=True)

    def _insert_asset(self,c,w,actor,kind,name,data,description='',source=None,id=None,
                      enabled=True,visibility='workspace',revision=1):
        aid=id or uid({'agent':'a_','skill':'s_','mcp':'x_','harness':'h_','model':'v_'}[kind])
        stamp=now()
        c.execute('INSERT INTO team_platform_assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (aid,w,kind,name,description,int(enabled),revision,visibility,dump(data),dump(source or {}),actor,stamp,stamp))
        return aid

    def _raw(self,c,aid):
        r=c.execute('SELECT * FROM team_platform_assets WHERE id=?',(aid,)).fetchone()
        if not r:raise Problem(404,'能力资产不存在或无权访问')
        return self.row(r)

    def _visible(self,c,a,actor):
        if self.store.deleted(c,a['id']):raise Problem(404,'配置已移入回收站')
        member=self.store.workspace_require(c,a['workspace_id'],actor)
        if a['visibility']=='workspace':return
        has_grants=c.execute('SELECT 1 FROM team_platform_grants WHERE asset_id=?',(a['id'],)).fetchone()
        if not has_grants and member['role']=='owner' and not a['source'].get('origin_project_id'):return
        if not c.execute('''SELECT 1 FROM team_platform_grants g JOIN team_members m
            ON m.project_id=g.project_id WHERE g.asset_id=? AND m.user_id=?''',(a['id'],actor)).fetchone():
            raise Problem(404,'能力资产不存在或无权访问')

    def get(self,id,actor,kind=None,c=None):
        if c is None:
            with self.store.connection() as conn:return self.get(id,actor,kind,conn)
        a=self._raw(c,id);self._visible(c,a,actor)
        if kind and a['kind']!=kind:raise Problem(404,'能力类型不匹配')
        return a

    def require_manage_asset(self,aid,actor):
        with self.store.connection() as c:
            a=self.get(aid,actor,c=c);self.manage(c,a['workspace_id'],actor)
            return a

    def _usable_in(self,c,a,p,actor):
        w=self.workspace_for_project(c,p,actor)
        if a['workspace_id']!=w:raise Problem(404,'不能跨公司启用能力')
        self._visible(c,a,actor)
        if a['visibility']!='workspace' and not c.execute('SELECT 1 FROM team_platform_grants WHERE asset_id=? AND project_id=?',(a['id'],p)).fetchone():
            raise Problem(403,'此能力含原项目专用配置；请公司管理员明确发布后再用于其他项目')
        if not a['enabled']:raise Problem(409,'能力已停用：'+a['name'])
        if a['kind']=='skill' and a['data'].get('status')!='published':raise Problem(409,'Skill尚未审核发布')

    def ensure_defaults(self,p,actor):
        # Compatibility name only: never auto-install capabilities into projects.
        with self.store.connection() as c:w=self.workspace_for_project(c,p,actor)
        self.ensure_workspace(w,actor)

    def ensure_workspace(self,w,actor):
        with self.store.connection() as c:
            self.store.workspace_require(c,w,actor)
            if c.execute('SELECT 1 FROM team_platform_bootstrap WHERE workspace_id=?',(w,)).fetchone():return
        with self.store.connection(True) as c:
            self.store.workspace_require(c,w,actor)
            if c.execute('SELECT 1 FROM team_platform_bootstrap WHERE workspace_id=?',(w,)).fetchone():return
            owner=c.execute("SELECT user_id FROM team_workspace_members WHERE workspace_id=? AND role='owner' ORDER BY user_id LIMIT 1",(w,)).fetchone()[0]
            h=stable('h_',w+':default-harness');s=stable('s_',w+':default-skill');m=stable('x_',w+':default-mcp')
            self._insert_asset(c,w,owner,'harness','标准任务执行',dict(HARNESS_DEFAULTS),
                '单Agent、流式、受限工具循环；外部工具逐次批准，业务成果人工验收。',{'kind':'platform_template'},h)
            self._insert_asset(c,w,owner,'skill','核查与沉淀规范',{'slug':'evidence-and-review','status':'published','body':'# 核查与沉淀\n\n先核对指定资料和当前任务；区分事实、建议、未决事项。\n提供来源及版本。业务变更和技能发布先经人确认。'},
                '可跨项目挂载的基础协作规则。',{'kind':'platform_template'},s)
            self._insert_asset(c,w,owner,'mcp','内置只读工具',{'transport':'builtin','allowed_tools':['utc_now','text_metrics'],'approval_required':False},
                '官方MCP协议；仅时间与文本统计。配置不自动挂载到Agent。',{'kind':'platform_template'},m)
            for i,(name,prompt) in enumerate((('团队协作助手',AGENT_DEFAULTS['system_prompt']),('团队资料核查员','先核对明确指定的文件，标明来源、矛盾和证据不足，不编造事实。'),('团队技能整理员','把已验收经验整理为SKILL.md草稿：用途、输入、步骤、核查、失败处理和权限；不自动发布。'))):
                data={k:AGENT_DEFAULTS[k] for k in PROMPTS};data.update(system_prompt=prompt,harness_id=h,model_id='',skill_ids=[s],mcp_ids=[],plugin_ids=[])
                self._insert_asset(c,w,owner,'agent',name,data,'在任意已授权项目启用，任务上下文互相隔离。',{'kind':'platform_template'},stable('a_',w+':default-agent:'+str(i)))
            c.execute('INSERT INTO team_platform_bootstrap VALUES(?,?)',(w,now()))

    def migrate(self):
        with self.store.connection(True) as c:
            if c.execute("SELECT 1 FROM team_platform_migrations WHERE name='workspace-capabilities-v4'").fetchone():return
            rows=c.execute('''SELECT a.*,pw.workspace_id FROM team_capabilities a
                JOIN team_project_workspace pw ON pw.project_id=a.project_id ORDER BY a.created_at,a.id''').fetchall()
            for row in rows:
                a=self.row(row);p=a['project_id'];data=a['data'];w=a['workspace_id']
                source={'kind':'legacy_project_migration','origin_project_id':p,'legacy_source':a['source'],'legacy_revision':a['revision'],'review_before_sharing':True}
                if a['kind']=='agent':
                    hid=stable('h_','migrated:'+a['id']);policy={**HARNESS_DEFAULTS,**{k:v for k,v in data.items() if k in HARNESS_DEFAULTS}}
                    cfg=json.loads(c.execute('SELECT settings_json FROM team_projects WHERE id=?',(p,)).fetchone()[0])
                    policy['history_limit']=cfg.get('history_limit',60)
                    self._insert_asset(c,w,a['created_by'],'harness',a['name']+' · 迁移执行配置',policy,source=source,id=hid,visibility='restricted')
                    c.execute('INSERT INTO team_platform_grants VALUES(?,?)',(hid,p))
                    provider=data.get('provider_name') or cfg.get('provider_name','');model=data.get('model') or cfg.get('model','');mid=stable('v_',p+':'+provider+':'+model)
                    if not c.execute('SELECT 1 FROM team_platform_assets WHERE id=?',(mid,)).fetchone():
                        table=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='providers'").fetchone()
                        prov=c.execute('SELECT base_url FROM providers WHERE name=?',(provider,)).fetchone() if table else None
                        self._insert_asset(c,w,a['created_by'],'model','迁移模型 · '+(model or '待配置'),{'provider_name':provider,'model':model,'base_url':prov[0] if prov else '', 'configured':bool(provider and model)},source=source,id=mid,visibility='restricted')
                        c.execute('INSERT INTO team_platform_grants VALUES(?,?)',(mid,p))
                    data={k:data.get(k,AGENT_DEFAULTS[k]) for k in PROMPTS}|{'harness_id':hid,'model_id':mid,'skill_ids':data.get('skill_ids',[]),'mcp_ids':data.get('mcp_ids',[])}
                    base_prompt=(cfg.get('system_prompt') or '').strip()
                    if base_prompt and base_prompt!=data['system_prompt'].strip():
                        data['system_prompt']=base_prompt+'\n\n## 原Agent专用规则\n'+data['system_prompt']
                self._insert_asset(c,w,a['created_by'],a['kind'],a['name'],data,a['description'],source,a['id'],a['enabled'],'restricted',a['revision'])
                c.execute('INSERT INTO team_platform_grants VALUES(?,?)',(a['id'],p))
            # Freeze complete dependencies only after all records exist.
            for row in rows:
                a=self._raw(c,row['id']);p=row['project_id'];actor=row['created_by']
                bundle=self._bundle(c,a,p,None,validate=False)
                c.execute('INSERT INTO team_platform_bindings VALUES(?,?,?,1,?,?,?,?)',(p,a['id'],a['revision'],int(a['enabled']),dump(bundle),actor,now()))
            for p in {row['project_id'] for row in rows}:self.store.touch(c,p)
            c.execute("INSERT INTO team_platform_migrations VALUES('workspace-capabilities-v4',?)",(now(),))

    def catalog(self,w,actor,kind=None):
        self.ensure_workspace(w,actor)
        with self.store.connection() as c:
            self.store.workspace_require(c,w,actor);out=[]
            for row in c.execute('SELECT * FROM team_platform_assets WHERE workspace_id=? ORDER BY kind,created_at,id',(w,)):
                a=self.row(row)
                if kind and a['kind']!=kind:continue
                try:self._visible(c,a,actor)
                except Problem:continue
                a['used_by_projects']=c.execute('SELECT COUNT(*) FROM team_platform_bindings WHERE asset_id=? AND enabled=1',(a['id'],)).fetchone()[0]
                out.append(a)
            default=c.execute('SELECT model_id FROM team_platform_defaults WHERE workspace_id=?',(w,)).fetchone()
        return {'items':out,'default_model_id':default[0] if default else None,'scope':'workspace','project_independent':True}

    def history(self,id,actor):
        self.require_manage_asset(id,actor)
        with self.store.connection() as c:return [json.loads(r[0]) for r in c.execute('SELECT snapshot_json FROM team_platform_versions WHERE asset_id=? ORDER BY revision DESC',(id,))]

    def validate_platform_data(self,c,w,actor,kind,body,old=None,site_admin=False):
        old=old or {};data=body.get('data',old.get('data',{}))
        if not isinstance(data,dict):raise Problem(422,'配置必须是对象')
        if kind=='agent':
            data={**(old.get('data') or {}),**data};out={}
            for key,limit in [('system_prompt',40000),('soul_md',16000),('agents_md',16000),('search_prompt',6000)]:
                out[key]=require_text(data.get(key,AGENT_DEFAULTS[key]),key,limit)
            for key,k in [('harness_id','harness'),('model_id','model')]:
                aid=data.get(key,'')
                if not isinstance(aid,str):raise Problem(422,key+'需为能力ID')
                if key=='harness_id' and not aid:raise Problem(422,'请先在能力中心创建并选择Harness')
                if aid:
                    a=self.get(aid,actor,k,c)
                    if a['workspace_id']!=w:raise Problem(404,'不能引用其他公司的能力')
                    if not a['enabled']:raise Problem(409,'引用的配置已停用')
                out[key]=aid
            for key,k in [('skill_ids','skill'),('mcp_ids','mcp')]:
                out[key]=identifiers(data.get(key,[]),key)
                for aid in out[key]:
                    a=self.get(aid,actor,k,c)
                    if a['workspace_id']!=w:raise Problem(404,'不能跨公司挂载能力')
                    if not a['enabled'] or (k=='skill' and a['data'].get('status')!='published'):raise Problem(422,'只能挂载已启用且已审核的能力')
            from .platform_plugins import selected_plugins
            out['plugin_ids']=selected_plugins(data.get('plugin_ids',[]))
            slugs=[self.get(aid,actor,'skill',c)['data']['slug'] for aid in out['skill_ids']]
            if len(slugs)!=len(set(slugs)):raise Problem(422,'技能标识重复，会覆盖同一SKILL目录')
            return out
        if kind=='harness':
            data={**HARNESS_DEFAULTS,**data};out={}
            fixed={'engine':'octop-harness','engine_version':'1.0.4','execution_mode':'single_agent','stream':True,'automatic_retry':False,'external_tool_approval':'per_call','memory_scope':'task_project_published_company','result_policy':'human_review'}
            for key,value in fixed.items():
                if data.get(key)!=value or type(data.get(key))!=type(value):raise Problem(422,'当前Harness不支持修改 '+key+'；不会保存无效开关')
                out[key]=value
            for key,lo,hi in [('max_model_steps',1,64),('max_tool_calls',0,160),('timeout_seconds',30,1800),('max_output_tokens',128,8192),('history_limit',5,200),('max_context_chars',10000,120000),('max_documents',0,6),('max_document_chars',1000,30000)]:
                out[key]=integer(data[key],key,lo,hi)
            out['tools']=identifiers(data.get('tools',[]),'内置工具',2)
            if set(out['tools'])-{'project_search','project_read_document'}:raise Problem(422,'未注册的内置工具')
            out['retrieval_mode']=data.get('retrieval_mode','automatic')
            if out['retrieval_mode'] not in ('automatic','explicit','disabled'):raise Problem(422,'检索方式不支持')
            if out['retrieval_mode']=='disabled':out['tools']=[];out['max_documents']=0
            return out
        if kind=='model':
            # Only the authenticated connection endpoint may assign provider rows.
            allowed={'model','base_url','provider_name','configured'}
            if set(data)-allowed:raise Problem(422,'模型资产只保存连接元数据，密钥使用专门接口')
            previous=old.get('data') or {'provider_name':'','model':'','base_url':'','configured':False}
            if any(data.get(k,previous.get(k))!=previous.get(k) for k in ('provider_name','base_url','configured')):raise Problem(422,'请用“配置模型连接”保存地址和凭证')
            return dict(previous)
        return super().validate_data(c,w,actor,kind,body,old,site_admin)

    @staticmethod
    def dependency_ids(a):
        if a['kind']!='agent':return []
        d=a['data'];return [x for x in [d.get('harness_id'),d.get('model_id'),*d.get('skill_ids',[]),*d.get('mcp_ids',[])] if x]

    def save(self,scope,actor,kind,body,id=None,site_admin=False,source=None):
        # Keep imports' registry interface, but there is no project-owned write.
        with self.store.connection() as c:
            if not c.execute('SELECT 1 FROM team_workspaces WHERE id=?',(scope,)).fetchone():
                raise Problem(409,'能力配置已迁至公司能力中心；项目仅启用或停用')
        return self.save_asset(scope,actor,kind,body,id,site_admin,source)

    def save_asset(self,w,actor,kind,body,id=None,site_admin=False,source=None):
        if kind not in KINDS:raise Problem(422,'不支持的能力类型')
        self.ensure_workspace(w,actor)
        with self.store.connection(True) as c:
            self.manage(c,w,actor);old=self.get(id,actor,kind,c) if id else None
            if old and old['workspace_id']!=w:raise Problem(404,'能力不属于此公司')
            if old:self.store.revision(old,body)
            name=require_text(body.get('name',old['name'] if old else ''),'名称',80,False)
            desc=require_text(body.get('description',old['description'] if old else ''),'用途说明',2000)
            enabled=body.get('enabled',old['enabled'] if old else kind not in ('skill','mcp','model'))
            if type(enabled) is not bool:raise Problem(422,'启用状态必须是布尔值')
            visibility=body.get('visibility',old['visibility'] if old else 'workspace')
            if visibility not in ('workspace','restricted'):raise Problem(422,'可见范围无效')
            if visibility=='workspace' and old and old['visibility']=='restricted' and body.get('acknowledge_sharing') is not True:
                raise Problem(422,'请确认：配置正文及附属文件将对整个公司可见；原项目聊天不会共享')
            data=self.validate_platform_data(c,w,actor,kind,body,old,site_admin)
            if kind=='skill' and data['status']=='draft' and enabled:raise Problem(422,'Skill草稿不能启用')
            candidate={'kind':kind,'data':data}
            if visibility=='workspace':
                for dep in self.dependency_ids(candidate):
                    if self.get(dep,actor,c=c)['visibility']!='workspace':raise Problem(422,'共享Agent不能引用受限依赖；请先审核并发布依赖，或将Agent设为受限')
            if (not old or name!=old['name']) and c.execute('SELECT 1 FROM team_platform_assets WHERE workspace_id=? AND kind=? AND name=? AND id!=?',(w,kind,name,id or '')).fetchone():
                raise Problem(409,'能力中心已存在同名资产')
            if old:
                c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(id,old['revision'],dump(old),now()))
                if kind=='mcp' and any(old['data'].get(k)!=data.get(k) for k in ('transport','url','command','args')):
                    c.execute('DELETE FROM team_mcp_credentials WHERE asset_id=?',(id,))
                c.execute('UPDATE team_platform_assets SET name=?,description=?,enabled=?,visibility=?,data_json=?,revision=revision+1,updated_at=? WHERE id=?',(name,desc,int(enabled),visibility,dump(data),now(),id))
            else:id=self._insert_asset(c,w,actor,kind,name,data,desc,source,id,enabled,visibility)
        return self.get(id,actor,kind)

    def restore_version(self,id,actor,body,site_admin=False):
        current=self.get(id,actor);version=integer(body.get('restore_revision'),'历史版本',1,100000)
        with self.store.connection() as c:
            self.manage(c,current['workspace_id'],actor)
            row=c.execute('SELECT snapshot_json FROM team_platform_versions WHERE asset_id=? AND revision=?',(id,version)).fetchone()
            if not row:raise Problem(404,'历史配置版本不存在')
            previous=json.loads(row[0])
        # Restores config as a NEW revision, never rewrites already referenced vN.
        if current['kind']=='model':raise Problem(409,'模型凭证不可从历史快照恢复；请重新配置连接')
        patch={k:previous[k] for k in ('name','description','enabled','visibility','data')}
        patch.update(expected_revision=body.get('expected_revision'),acknowledge_sharing=body.get('acknowledge_sharing'),acknowledge_host_execution=body.get('acknowledge_host_execution'))
        return self.save_asset(current['workspace_id'],actor,current['kind'],patch,id,site_admin)

    def _bundle(self,c,root,p,actor,validate=True):
        assets=[root];d=root['data']
        if root['kind']=='agent':
            deps=self.dependency_ids(root)
            if not d.get('model_id'):
                default=c.execute('SELECT model_id FROM team_platform_defaults WHERE workspace_id=?',(root['workspace_id'],)).fetchone()
                if default and default[0]:deps.append(default[0])
            assets.extend(self._raw(c,aid) for aid in dict.fromkeys(deps))
        if validate:
            for a in assets:self._usable_in(c,a,p,actor)
            slugs=[a['data']['slug'] for a in assets if a['kind']=='skill']
            if len(slugs)!=len(set(slugs)):raise Problem(409,'依赖技能存在重复标识')
            if root['kind']=='agent' and not any(a['kind']=='harness' for a in assets):raise Problem(422,'Agent缺少Harness')
            if root['kind']=='agent' and not any(a['kind']=='model' and a['data'].get('configured') for a in assets):raise Problem(422,'请先在公司能力中心配置模型连接，再启用Agent')
        return {'root_id':root['id'],'workspace_id':root['workspace_id'],'assets':assets,'frozen_at':now(),'scope':'configuration_only','project_context_included':False}

    def binding(self,c,p,aid,actor,active=True):
        self.store.require(c,p,actor)
        row=c.execute('SELECT * FROM team_platform_bindings WHERE project_id=? AND asset_id=?',(p,aid)).fetchone()
        if not row:
            from .workspace_staff import implicit_binding
            return implicit_binding(self,c,p,aid,actor)
        if active and not row['enabled']:raise Problem(404,'此能力已在项目中停用')
        b=dict(row);b['bundle']=json.loads(b.pop('bundle_json'))
        root=self._raw(c,aid)
        if active and root['kind']=='agent' and root['visibility']=='workspace' and not b['bundle'].get('pin_version',False):
            from .workspace_staff import implicit_binding
            shared=implicit_binding(self,c,p,aid,actor);shared['revision']=b['revision'];return shared
        return b

    def bind(self,p,actor,aid,body):
        with self.store.connection(True) as c:
            w=self.workspace_for_project(c,p,actor,owner=True)
            a=self.get(aid,actor,c=c)
            if a['workspace_id']!=w:raise Problem(404,'能力属于另一个公司')
            old=c.execute('SELECT * FROM team_platform_bindings WHERE project_id=? AND asset_id=?',(p,aid)).fetchone()
            expected=body.get('expected_binding_revision',0)
            if type(expected) is not int or expected!=(old['revision'] if old else 0):raise Problem(409,'项目启用状态已变化，请刷新')
            enabled=body.get('enabled',True)
            if type(enabled) is not bool:raise Problem(422,'启用状态必须为布尔值')
            if enabled:
                if type(body.get('asset_revision')) is not int or body['asset_revision']!=a['revision']:raise Problem(409,'能力中心已有新版本，请检查后重新启用')
                bundle=self._bundle(c,a,p,actor)
                if type(body.get('pin_version',False)) is not bool:raise Problem(422,'固定版本选项无效')
                bundle['pin_version']=body.get('pin_version',False)
            else:
                if not old:raise Problem(404,'没有可停用的绑定')
                bundle=json.loads(old['bundle_json'])
            if old:
                c.execute('INSERT INTO team_platform_binding_history VALUES(?,?,?,?,?)',(p,aid,old['revision'],dump(dict(old)),now()))
                c.execute('UPDATE team_platform_bindings SET asset_revision=?,revision=revision+1,enabled=?,bundle_json=?,updated_at=? WHERE project_id=? AND asset_id=?',(a['revision'] if enabled else old['asset_revision'],int(enabled),dump(bundle),now(),p,aid))
            else:c.execute('INSERT INTO team_platform_bindings VALUES(?,?,?,1,?,?,?,?)',(p,aid,a['revision'],int(enabled),dump(bundle),actor,now()))
            self.store.touch(c,p)
            return self.binding(c,p,aid,actor,active=False)

    def bindings(self,p,actor):
        with self.store.connection() as c:
            self.store.require(c,p,actor);out=[]
            for raw in c.execute('SELECT * FROM team_platform_bindings WHERE project_id=? ORDER BY updated_at DESC',(p,)):
                b=dict(raw);b['bundle']=json.loads(b.pop('bundle_json'));updates=[];unavailable=[]
                for frozen in b['bundle']['assets']:
                    current=self._raw(c,frozen['id'])
                    if current['revision']!=frozen['revision']:updates.append({'id':current['id'],'name':current['name'],'pinned':frozen['revision'],'latest':current['revision']})
                    try:self._usable_in(c,current,p,actor)
                    except Problem:unavailable.append(current['name'])
                b.update(updates=updates,unavailable=unavailable);out.append(b)
            return out

    @staticmethod
    def effective_agent(bundle):
        root=next(a for a in bundle['assets'] if a['id']==bundle['root_id'])
        if root['kind']!='agent':return root
        harness=next((a for a in bundle['assets'] if a['kind']=='harness'),None)
        model=next((a for a in bundle['assets'] if a['kind']=='model'),None)
        data={**root['data'],**(harness['data'] if harness else HARNESS_DEFAULTS),
              'model':model['data'].get('model','') if model else '',
              'provider_name':model['data'].get('provider_name','') if model else ''}
        return {**root,'data':data,'canonical_scope':'workspace','harness_revision':harness['revision'] if harness else None,'model_revision':model['revision'] if model else None}

    def bound_agent(self,p,actor,aid,c=None):
        if c is None:
            with self.store.connection() as conn:return self.bound_agent(p,actor,aid,conn)
        b=self.binding(c,p,aid,actor);a=self.effective_agent(b['bundle'])
        if a['kind']!='agent':raise Problem(404,'选择的不是Agent')
        self._usable_in(c,self._raw(c,aid),p,actor)
        a['binding_revision']=b['revision'];return a

    def list(self,p,actor,kind=None):
        # Project view consists only of explicitly bound snapshots, never clones.
        out={}
        with self.store.connection() as c:
            self.store.require(c,p,actor)
            for stored in c.execute('SELECT * FROM team_platform_bindings WHERE project_id=? AND enabled=1',(p,)):
                try:b=self.binding(c,p,stored['asset_id'],actor)
                except Problem:continue
                bundle=b['bundle']
                for frozen in bundle['assets']:
                    a=self.effective_agent(bundle) if frozen['id']==bundle['root_id'] and frozen['kind']=='agent' else dict(frozen)
                    if kind and a['kind']!=kind:continue
                    current=self._raw(c,a['id']);a['enabled']=bool(current['enabled'])
                    a.update(binding_revision=b['revision'],canonical_scope='workspace',latest_revision=current['revision'],update_available=current['revision']!=a['revision'])
                    if a['kind']=='agent' and a['id']!=bundle['root_id']:continue
                    out.setdefault(a['id'],a)
            from .workspace_staff import extend_staff
            extend_staff(self,c,p,actor,out,kind)
        return list(out.values())

    def default_agent(self,p,actor):
        agents=[a for a in self.list(p,actor,'agent') if a['enabled']]
        if not agents:raise Problem(409,'请先从公司能力中心启用一个Agent，再通过 @ 选择')
        return agents[0]

    def assert_run_scope(self,cfg):
        p,actor=cfg['_project_id'],cfg['_actor_id'];info=cfg.get('platform_binding')
        if not info:return
        if info.get('implicit'):
            from .workspace_staff import assert_implicit
            with self.store.connection() as c:assert_implicit(self,c,cfg)
            return
        with self.store.connection() as c:
            for extra in cfg.get('extra_skill_bindings',[]):
                skill_binding=self.binding(c,p,extra['asset_id'],actor)
                if skill_binding['revision']!=extra['binding_revision']:raise Problem(409,'本次所选技能的项目授权已变化')
                for dep in skill_binding['bundle']['assets']:self._usable_in(c,self._raw(c,dep['id']),p,actor)
            b=self.binding(c,p,info['asset_id'],actor)
            if b['revision']!=info['binding_revision']:raise Problem(409,'项目能力绑定已更改，当前运行停止；请重新确认后发起')
            for frozen in b['bundle']['assets']:
                current=self._raw(c,frozen['id']);self._usable_in(c,current,p,actor)
                if current['kind'] in ('mcp','model') and current['revision']!=frozen['revision']:
                    raise Problem(409,'连接配置已更新；项目需要明确升级绑定后才能继续使用')

    def snapshot(self,c,p,actor,body,cfg):
        b=self.binding(c,p,body['agent_id'],actor);bundle=b['bundle'];a=self.bound_agent(p,actor,body['agent_id'],c)
        if body.get('agent_revision') is not None and body['agent_revision']!=a['revision']:raise Problem(409,'Agent绑定版本已改变，请重新选择')
        if body.get('binding_revision') is not None and body['binding_revision']!=b['revision']:raise Problem(409,'项目能力绑定已更新')
        for frozen in bundle['assets']:
            current=self._raw(c,frozen['id']);self._usable_in(c,current,p,actor)
            if current['kind'] in ('mcp','model') and current['revision']!=frozen['revision']:raise Problem(409,'连接配置已更新，请在项目能力页升级绑定')
        policy=a['data'];docs=[];ids=identifiers(body.get('document_ids',[]),'@资料',policy['max_documents'])
        for aid in ids:
            d=self.resolve_document(p,actor,aid,c);expected=body.get('document_revisions',{}).get(aid)
            if expected is not None and (type(expected) is not int or expected<1):raise Problem(422,'资料版本需为正整数')
            if expected is not None and expected!=d['revision']:raise Problem(409,'资料已更新，请重新选择')
            if len(d['content'])>policy['max_document_chars']:d.update(content=d['content'][:policy['max_document_chars']],truncated=True)
            d['snapshot_sha256']=hashlib.sha256(d['content'].encode()).hexdigest();docs.append(d)
        harness=next(x for x in bundle['assets'] if x['kind']=='harness')
        model=next((x for x in bundle['assets'] if x['kind']=='model'),None)
        if not model or not model['data'].get('configured'):raise Problem(409,'请在公司能力中心配置模型，再升级本项目绑定')
        selected=[];extra_bindings=[]
        if b.get('implicit') and set(body.get('selected_skill_ids',[]))-{x['id'] for x in bundle['assets'] if x['kind']=='skill'}:
            raise Problem(422,'团队员工模式请先在员工配置中勾选额外技能，再发起任务')
        for sid in identifiers(body.get('selected_skill_ids',[]),'本次技能',12):
            if any(x['id']==sid for x in bundle['assets']):continue
            found=None
            for raw in c.execute('SELECT * FROM team_platform_bindings WHERE project_id=? AND enabled=1',(p,)):
                other=json.loads(raw['bundle_json'])
                match=next((x for x in other['assets'] if x['id']==sid and x['kind']=='skill'),None)
                if match:
                    for asset in other['assets']:self._usable_in(c,self._raw(c,asset['id']),p,actor)
                    found=match;extra_bindings.append({'asset_id':raw['asset_id'],'binding_revision':raw['revision'],'skill_id':sid});break
            if found is None:raise Problem(404,'所选额外技能未通过本任务员工配置授权；请在团队员工配置中勾选')
            selected.append(found)
        skill_snapshots=[x for x in bundle['assets'] if x['kind']=='skill']+selected
        if len(skill_snapshots)>12 or len({x['data']['slug'] for x in skill_snapshots})!=len(skill_snapshots):raise Problem(422,'技能数量超过上限或标识重复')
        return {**cfg,'extra_skill_bindings':extra_bindings,'system_prompt':'','skills':[], 'model':policy['model'],'provider_name':policy['provider_name'],
                **{k:policy[k] for k in ('history_limit','max_output_tokens','max_context_chars','retrieval_mode')},
                'agent_snapshot':a,'harness_snapshot':harness,'model_snapshot':model,
                'plugin_snapshots':[dict(__import__('teamspace.platform_plugins',fromlist=['BY_ID']).BY_ID[x]) for x in policy.get('plugin_ids',[])],
                'skill_snapshots':skill_snapshots,
                'mcp_snapshots':[x for x in bundle['assets'] if x['kind']=='mcp'],
                'explicit_documents':docs,'platform_binding':{'asset_id':a['id'],'binding_revision':b['revision'],'workspace_id':a['workspace_id'],'implicit':bool(b.get('implicit')),
                'versions':{x['id']:x['revision'] for x in bundle['assets']}}}

    def draft_skill_from_document(self,p,actor,document_id):
        d=self.resolve_document(p,actor,document_id)
        if not d['adopted']:raise Problem(422,'请先采用知识或验收成果')
        with self.store.connection(True) as c:
            w=self.workspace_for_project(c,p,actor,owner=True)
            body='# 用途\n请补充可复用场景。\n\n# 已确认来源\n'+d['content'][:50000]+'\n\n# 输入、步骤、验收与失败处理\n请编辑为可执行规范；仅供审核，不自动启用。'
            aid=self._insert_asset(c,w,actor,'skill',('经验技能 · '+d['title'])[:80],{'slug':'learned-'+uid()[:10],'body':body,'status':'draft'},
                source={'kind':'project_knowledge_draft','origin_project_id':p,'document_id':d['id'],'document_revision':d['revision'],'snapshot_sha256':hashlib.sha256(d['content'].encode()).hexdigest(),'review_before_sharing':True},enabled=False,visibility='restricted')
            c.execute('INSERT INTO team_platform_grants VALUES(?,?)',(aid,p))
        return self.get(aid,actor,'skill')


    def documents(self,p,actor,q=''):
        import unicodedata
        clean=lambda x:' '.join(unicodedata.normalize('NFKC',str(x)).casefold().split())
        terms=clean(q).lstrip('@').split();project=self.store.project(p,actor)
        rows=self.store.objects(p,actor,'document')
        rows+=self.store.public_knowledge(project['workspace_id'],actor)
        with self.store.connection() as c:
            self.store.require(c,p,actor);aliases={}
            for r in c.execute('SELECT document_id,filename FROM team_uploads WHERE project_id=?',(p,)):aliases.setdefault(r[0],set()).add(r[1])
        from .file_folders import paths,document_locations
        with self.store.connection() as c:folder_paths=paths(c,p);locations=document_locations(c,p)
        out=[]
        for d in rows:
            folder_path=folder_paths.get((locations.get(d['id']) or {}).get('folder_id',''),'')
            names=sorted(aliases.get(d['id'],set()))
            searchable=clean(' '.join([d['title'],d.get('filename',''),folder_path,*names,d['id']]))
            if not all(x in searchable for x in terms):continue
            out.append({'id':d['id'],'title':d['title'],'folder_path':folder_path,'aliases':names,'revision':d['revision'],'kind':d['kind'],'status':d['status'],'scope':'company' if d['kind']=='company' else 'project','usable':d['status'] in ('ready','published')})
        return sorted(out,key=lambda d:(not d['usable'],clean(d['title'])))[:200]
