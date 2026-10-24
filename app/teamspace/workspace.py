"""Additive company/workspace model and task-bound conversations.

Project ACLs remain authoritative: company membership never grants access to
another project. Only explicitly published snapshots cross project boundaries.
"""
from __future__ import annotations
import json
from types import SimpleNamespace
from .store import Store as BaseStore, Problem, dump, now, uid, require_text, tokenize

SCHEMA = '''
CREATE TABLE IF NOT EXISTS team_workspaces(
 id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
 revision INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_workspace_members(
 workspace_id TEXT NOT NULL REFERENCES team_workspaces(id),user_id INTEGER NOT NULL,
 username TEXT NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL,
 PRIMARY KEY(workspace_id,user_id));
CREATE TABLE IF NOT EXISTS team_project_workspace(
 project_id TEXT PRIMARY KEY REFERENCES team_projects(id),
 workspace_id TEXT NOT NULL REFERENCES team_workspaces(id));
CREATE TABLE IF NOT EXISTS team_public_knowledge(
 id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL REFERENCES team_workspaces(id),
 title TEXT NOT NULL,body TEXT NOT NULL,source_json TEXT NOT NULL DEFAULT '{}',
 revision INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'published',
 published_by INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS team_workspace_migrations(name TEXT PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS team_message_task ON team_messages(project_id,json_extract(meta_json,'$.task_id'),seq);
CREATE INDEX IF NOT EXISTS team_workspace_projects ON team_project_workspace(workspace_id);
'''

class WorkspaceStore(BaseStore):
    def __init__(self,db_path,data_dir):
        super().__init__(db_path,data_dir)
        with self.connection() as c: c.executescript(SCHEMA)
        self.migrate_workspaces()

    def workspace_require(self,c,w,actor,owner=False,write=False):
        m=c.execute('SELECT * FROM team_workspace_members WHERE workspace_id=? AND user_id=?',(w,actor)).fetchone()
        if m is None: raise Problem(404,'公司／团队不存在或你没有访问权限')
        if owner and m['role']!='owner': raise Problem(403,'需要公司／团队管理员权限')
        if write and m['role']=='viewer': raise Problem(403,'只读成员不能修改团队内容')
        return dict(m)

    def _ensure_workspace_member(self,c,w,user,role='member'):
        c.execute('INSERT OR IGNORE INTO team_workspace_members VALUES(?,?,?,?,?)',
                  (w,user.id,user.username,user.display_name or user.username,role))

    def _personal_workspace(self,c,user):
        row=c.execute("SELECT workspace_id FROM team_workspace_members WHERE user_id=? AND role='owner' ORDER BY workspace_id LIMIT 1",(user.id,)).fetchone()
        if row:return row[0]
        w='w_user_'+str(user.id)
        c.execute('INSERT OR IGNORE INTO team_workspaces(id,name,created_at) VALUES(?,?,?)',(w,'我的团队',now()))
        self._ensure_workspace_member(c,w,user,'owner')
        return w

    def migrate_workspaces(self):
        # One-time metadata additions; preserves account passwords, message IDs,
        # original text, project membership, files and model configuration.
        with self.connection(True) as c:
            if c.execute("SELECT 1 FROM team_workspace_migrations WHERE name='workspace-v2'").fetchone():return
            for p in c.execute('SELECT id FROM team_projects ORDER BY created_at').fetchall():
                pid=p[0];members=c.execute("SELECT * FROM team_members WHERE project_id=? ORDER BY CASE WHEN role='owner' THEN 0 ELSE 1 END,user_id",(pid,)).fetchall()
                if not members:continue
                owner=SimpleNamespace(id=members[0]['user_id'],username=members[0]['username'],display_name=members[0]['display_name'])
                w=self._personal_workspace(c,owner)
                c.execute('INSERT OR IGNORE INTO team_project_workspace VALUES(?,?)',(pid,w))
                for m in members:
                    u=SimpleNamespace(id=m['user_id'],username=m['username'],display_name=m['display_name'])
                    self._ensure_workspace_member(c,w,u,'owner' if m['role']=='owner' else m['role'])
                if c.execute("SELECT 1 FROM team_messages WHERE project_id=? AND json_extract(meta_json,'$.task_id') IS NULL",(pid,)).fetchone():
                    tid=self._coordination_task(c,pid)
                    c.execute("UPDATE team_messages SET meta_json=json_set(meta_json,'$.task_id',?) WHERE project_id=? AND json_extract(meta_json,'$.task_id') IS NULL",(tid,pid))
                    self.touch(c,pid)
            c.execute("INSERT INTO team_workspace_migrations VALUES('workspace-v2',?)",(now(),))

    def require(self,c,project_id,user_id,write=False,owner=False):
        member=super().require(c,project_id,user_id,write,owner)
        link=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(project_id,)).fetchone()
        if link:self.workspace_require(c,link[0],user_id,write=write or owner)
        return member

    def project(self,pid,actor):
        result=super().project(pid,actor)
        with self.connection() as c:
            w=c.execute('SELECT w.id,w.name FROM team_workspaces w JOIN team_project_workspace p ON p.workspace_id=w.id WHERE p.project_id=?',(pid,)).fetchone()
            result.update(workspace_id=w['id'] if w else None,workspace_name=w['name'] if w else None)
        return result

    def projects(self,actor):
        with self.connection() as c:
            rows=c.execute('''SELECT p.*,m.role,w.workspace_id FROM team_projects p
                JOIN team_members m ON m.project_id=p.id
                JOIN team_project_workspace w ON w.project_id=p.id
                JOIN team_workspace_members wm ON wm.workspace_id=w.workspace_id AND wm.user_id=m.user_id
                WHERE m.user_id=? AND NOT EXISTS (SELECT 1 FROM team_admin_trash tr WHERE tr.target_id=p.id AND tr.restored_at IS NULL) ORDER BY p.updated_at DESC''',(actor,)).fetchall()
            return [self.row_project(x) for x in rows]

    def workspaces(self,user):
        with self.connection(True) as c:
            if not c.execute('SELECT 1 FROM team_workspace_members WHERE user_id=?',(user.id,)).fetchone():
                self._personal_workspace(c,user)
            return [dict(x) for x in c.execute('SELECT w.*,m.role FROM team_workspaces w JOIN team_workspace_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created_at,w.id',(user.id,))]

    def create_workspace(self,user,body):
        name=require_text(body.get('name'),'公司／团队名称',120,False)
        w=uid('w_')
        with self.connection(True) as c:
            c.execute('INSERT INTO team_workspaces(id,name,description,created_at) VALUES(?,?,?,?)',(w,name,require_text(body.get('description',''),'简介',4000),now()))
            self._ensure_workspace_member(c,w,user,'owner')
        return next(x for x in self.workspaces(user) if x['id']==w)

    def update_workspace(self,w,actor,body):
        with self.connection(True) as c:
            self.workspace_require(c,w,actor,owner=True)
            old=c.execute('SELECT * FROM team_workspaces WHERE id=?',(w,)).fetchone();self.revision(old,body)
            name=require_text(body.get('name',old['name']),'公司／团队名称',120,False)
            desc=require_text(body.get('description',old['description']),'简介',4000)
            c.execute('UPDATE team_workspaces SET name=?,description=?,revision=revision+1 WHERE id=?',(name,desc,w))
            return dict(c.execute('SELECT * FROM team_workspaces WHERE id=?',(w,)).fetchone())

    def create_project(self,user,body):
        with self.connection(True) as c:
            w=body.get('workspace_id')
            if w:self.workspace_require(c,w,user.id,write=True)
            else:w=self._personal_workspace(c,user)
        # Base implementation returns before the mapping exists; mapping is
        # inserted immediately and creation never exposes another user's data.
        p=super().create_project(user,body)
        with self.connection(True) as c:
            self.workspace_require(c,w,user.id,write=True)
            c.execute('INSERT INTO team_project_workspace VALUES(?,?)',(p['id'],w))
        return self.project(p['id'],user.id)

    def set_member(self,p,actor,user,role):
        super().set_member(p,actor,user,role)
        with self.connection(True) as c:self.enrol_project_member(c,p,user)

    def enrol_project_member(self,c,p,user):
        link=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(p,)).fetchone()
        if link:self._ensure_workspace_member(c,link[0],user,'member')

    def workspace_members(self,w,actor):
        with self.connection() as c:
            self.workspace_require(c,w,actor)
            return [dict(x) for x in c.execute('SELECT * FROM team_workspace_members WHERE workspace_id=? ORDER BY role,user_id',(w,))]

    def set_workspace_member(self,w,actor,user,role):
        if role not in ('owner','member','viewer'):raise Problem(422,'无效成员角色')
        with self.connection(True) as c:
            self.workspace_require(c,w,actor,owner=True)
            old=c.execute('SELECT role FROM team_workspace_members WHERE workspace_id=? AND user_id=?',(w,user.id)).fetchone()
            if old and old[0]=='owner' and role!='owner': self._other_workspace_owner(c,w,user.id)
            c.execute('INSERT INTO team_workspace_members VALUES(?,?,?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=excluded.role',
                      (w,user.id,user.username,user.display_name or user.username,role))

    def _other_workspace_owner(self,c,w,target):
        if not c.execute("SELECT 1 FROM team_workspace_members WHERE workspace_id=? AND user_id!=? AND role='owner'",(w,target)).fetchone():
            raise Problem(409,'团队必须保留至少一名管理员')

    def remove_workspace_member(self,w,actor,target):
        with self.connection(True) as c:
            self.workspace_require(c,w,actor,owner=True)
            old=c.execute('SELECT role FROM team_workspace_members WHERE workspace_id=? AND user_id=?',(w,target)).fetchone()
            if old and old[0]=='owner':self._other_workspace_owner(c,w,target)
            projects=[x[0] for x in c.execute('SELECT project_id FROM team_project_workspace WHERE workspace_id=?',(w,))]
            for p in projects:
                pm=c.execute('SELECT role FROM team_members WHERE project_id=? AND user_id=?',(p,target)).fetchone()
                if pm and pm[0]=='owner': self.ensure_other_owner(c,p,target)
            for p in projects:
                c.execute('DELETE FROM team_members WHERE project_id=? AND user_id=?',(p,target))
                c.execute("UPDATE team_runs SET status='interrupted',error='团队权限已撤销',finished_at=? WHERE project_id=? AND actor_id=? AND status IN ('queued','running')",(now(),p,target))
                self.touch(c,p)
            c.execute('DELETE FROM team_workspace_members WHERE workspace_id=? AND user_id=?',(w,target))

    def _coordination_task(self,c,p):
        tid='t_coord_'+p
        if self.deleted(c,tid):raise Problem(404,'协调任务已删除，请进入其他任务或从回收站恢复')
        if not c.execute('SELECT 1 FROM team_objects WHERE id=?',(tid,)).fetchone():
            owner=c.execute("SELECT user_id FROM team_members WHERE project_id=? AND role='owner' ORDER BY user_id LIMIT 1",(p,)).fetchone()
            self.put_object(c,p,'task','项目规划与协调','用于承接旧版项目讨论。新讨论请进入具体任务。',owner[0] if owner else 0,
                            {'system_thread':True,'executor':'human','criteria':'明确项目范围和下一步任务','assignee_id':None},'todo',tid)
        return tid

    def conversation_task(self,c,p,task_id=None):
        if task_id is None:return self._coordination_task(c,p)
        if not isinstance(task_id,str):raise Problem(422,'任务编号格式无效')
        row=c.execute("SELECT id FROM team_objects WHERE id=? AND project_id=? AND kind='task' AND status!='deleted'",(task_id,p)).fetchone()
        if not row:raise Problem(404,'讨论任务不存在或不属于此项目')
        return row[0]

    def add_message(self,c,p,actor,name,content,client_id,kind='human',run_id=None,meta=None):
        meta=dict(meta or {});meta['task_id']=self.conversation_task(c,p,meta.get('task_id'))
        old=c.execute('SELECT content,meta_json FROM team_messages WHERE project_id=? AND author_id=? AND client_id=?',(p,actor,client_id)).fetchone()
        if old and (json.loads(old['meta_json']).get('task_id')!=meta['task_id'] or json.loads(old['meta_json']).get('mentions',[])!=meta.get('mentions',[])):raise Problem(409,'请求编号已用于不同任务或引用的消息')
        return super().add_message(c,p,actor,name,content,client_id,kind,run_id,meta)

    def send(self,p,user,body):
        content=require_text(body.get('content'),'消息',30000,False);client=require_text(body.get('client_id'),'请求编号',128,False)
        with self.connection(True) as c:
            self.require(c,p,user.id,write=True)
            meta={'task_id':body.get('task_id')}
            if body.get('mentions'):
                from .platform_registry import PlatformRegistry as AgentRegistry
                reg=AgentRegistry.__new__(AgentRegistry);reg.store=self
                mentions=body['mentions']
                if not isinstance(mentions,list) or len(mentions)>7:raise Problem(422,'最多一个Agent和六份资料')
                resolved=[];agents=0
                for m in mentions:
                    if not isinstance(m,dict):raise Problem(422,'引用格式无效')
                    if m.get('type')=='agent':
                        a=reg.bound_agent(p,user.id,m.get('id'),c)
                        if not a['enabled']:raise Problem(404,'Agent不可用')
                        agents+=1;resolved.append({'id':a['id'],'type':'agent','name':a['name'],'revision':a['revision']})
                    elif m.get('type')=='document':
                        d=reg.resolve_document(p,user.id,m.get('id'),c);resolved.append({'id':d['id'],'type':'document','name':d['title'],'revision':d['revision']})
                    else:raise Problem(422,'未知引用类型')
                if agents>1:raise Problem(422,'一次只选择一个Agent')
                meta['mentions']=resolved
            return self.add_message(c,p,user.id,user.display_name or user.username,content,client,meta=meta)

    def messages(self,p,actor,after=0,task_id=None):
        with self.connection() as c:
            self.require(c,p,actor)
            if task_id is None:
                tid='t_coord_'+p
                if not c.execute('SELECT 1 FROM team_objects WHERE id=?',(tid,)).fetchone():
                    return {'items':[],'latest_seq':0,'running':None,'task_id':None,'has_more':False}
            else:tid=self.conversation_task(c,p,task_id)
            if self.deleted(c,tid):raise Problem(404,'讨论任务已移入回收站')
            rows=c.execute("SELECT * FROM team_messages WHERE project_id=? AND json_extract(meta_json,'$.task_id')=? AND seq>? ORDER BY seq LIMIT 200",(p,tid,after)).fetchall()
            latest=c.execute("SELECT COALESCE(MAX(seq),0) FROM team_messages WHERE project_id=? AND json_extract(meta_json,'$.task_id')=?",(p,tid)).fetchone()[0]
            run=c.execute("SELECT id,status,kind,input_seq FROM team_runs WHERE project_id=? AND json_extract(request_json,'$.task_id')=? AND status IN ('queued','running')",(p,tid)).fetchone()
            return {'items':[self.message_json(x) for x in rows],'latest_seq':latest,'running':dict(run) if run else None,'task_id':tid,'has_more':bool(rows and rows[-1]['seq']<latest)}

    def create_note(self,p,actor,body):
        tid=body.get('task_id')
        if tid:
            with self.connection() as c:
                self.require(c,p,actor,write=True);self.conversation_task(c,p,tid)
        result=super().create_note(p,actor,body)
        with self.connection(True) as c:
            if tid:tid=self.conversation_task(c,p,tid)
            elif body.get('source_seq'):
                m=c.execute('SELECT meta_json FROM team_messages WHERE project_id=? AND seq=?',(p,body['source_seq'])).fetchone()
                if m:tid=json.loads(m[0]).get('task_id')
            if tid:
                c.execute("UPDATE team_objects SET data_json=json_set(data_json,'$.task_id',?) WHERE id=?",(tid,result['id']))
        return self.object(result['id'],actor,'document')

    def workspace_navigation(self,w,actor,view):
        # One snapshot and scoped JOINs; calendar never loads knowledge bodies.
        with self.connection() as c:
            self.workspace_require(c,w,actor)
            projects=[self.row_project(x) for x in c.execute("SELECT p.*,m.role,pw.workspace_id FROM team_projects p JOIN team_project_workspace pw ON pw.project_id=p.id JOIN team_members m ON m.project_id=p.id WHERE pw.workspace_id=? AND m.user_id=? AND NOT EXISTS (SELECT 1 FROM team_admin_trash tr WHERE tr.target_id=p.id AND tr.restored_at IS NULL) ORDER BY p.updated_at DESC",(w,actor))]
            rows=c.execute("SELECT o.*,p.title AS project_title FROM team_objects o JOIN team_projects p ON p.id=o.project_id JOIN team_project_workspace pw ON pw.project_id=p.id JOIN team_members m ON m.project_id=p.id WHERE pw.workspace_id=? AND m.user_id=? AND o.kind IN ('task','event') AND o.status!='deleted' AND NOT EXISTS (SELECT 1 FROM team_admin_trash tr WHERE tr.target_id=p.id AND tr.restored_at IS NULL)",(w,actor)).fetchall()
            objects=[self.object_json(row) for row in rows]
        tasks=[x for x in objects if x['kind']=='task'];events=[dict(x,kind=x.get('event_kind','meeting'),all_day=False) for x in objects if x['kind']=='event' and x['status']!='cancelled']
        calendar=[dict(x,starts_at=x['due_date'],all_day=True) for x in tasks if x.get('due_date') and x['status'] not in ('cancelled','paused')]+events
        return {'projects':projects,'tasks':tasks,'calendar':sorted(calendar,key=lambda x:x['starts_at']),'documents':[],'public_knowledge':[],'counts':{'projects':len(projects),'tasks':len(tasks)},'view':view}

    def workspace_overview(self,w,actor):
        with self.connection() as c:self.workspace_require(c,w,actor)
        projects=[p for p in self.projects(actor) if p['workspace_id']==w]
        tasks=[];calendar=[];documents=[]
        for p in projects:
            extra={'project_title':p['title'],'workspace_id':w}
            tasks.extend(dict(x,**extra) for x in self.objects(p['id'],actor,'task'))
            calendar.extend(dict(x,**extra) for x in self.calendar(p['id'],actor))
            documents.extend(dict(x,**extra) for x in self.objects(p['id'],actor,'document'))
        public=self.public_knowledge(w,actor)
        return {'projects':projects,'tasks':tasks,'calendar':sorted(calendar,key=lambda x:x['starts_at']),
                'documents':documents,'public_knowledge':public,'counts':{
                'projects':len(projects),'tasks':len(tasks),'pending_review':sum(x['status']=='review' for x in tasks),
                'files':sum(x['kind']=='file' for x in documents),'summaries':sum(x['kind']=='summary' for x in documents),
                'memories':sum(bool(x.get('adopted')) and x['status']=='ready' for x in documents),'public_knowledge':len(public)}}

    def public_knowledge(self,w,actor):
        with self.connection() as c:
            self.workspace_require(c,w,actor)
            out=[]
            for r in c.execute("SELECT * FROM team_public_knowledge WHERE workspace_id=? AND status='published' ORDER BY updated_at DESC",(w,)):
                d=dict(r);d['source']=json.loads(d.pop('source_json'));d['kind']='company';d['adopted']=True;out.append(d)
            return out

    def publish_document(self,w,docid,actor,expected_revision):
        with self.connection(True) as c:
            self.workspace_require(c,w,actor,owner=True)
            row=self.object_row(c,docid,actor,True,'document')
            self.require(c,row['project_id'],actor,owner=True)
            self.revision(row,{'expected_revision':expected_revision})
            mapping=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(row['project_id'],)).fetchone()
            data=json.loads(row['data_json'])
            if not mapping or mapping[0]!=w:raise Problem(422,'不能跨公司发布项目资料')
            if row['status']!='ready' or not data.get('adopted'):raise Problem(422,'请先核对并采用这条知识，再发布到公司')
            source={'project_id':row['project_id'],'document_id':docid,'document_revision':row['revision'],
                    'task_id':data.get('task_id'),'source_seq':data.get('source_seq'),'original_kind':data.get('document_kind')}
            old=c.execute('SELECT id,source_json FROM team_public_knowledge WHERE workspace_id=? AND json_extract(source_json,\'$.document_id\')=? AND status=\'published\'',(w,docid)).fetchone()
            if old and json.loads(old['source_json']).get('document_revision')==row['revision']:return {'id':old['id'],'duplicate':True}
            kid=uid('k_');stamp=now()
            c.execute('INSERT INTO team_public_knowledge(id,workspace_id,title,body,source_json,published_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                      (kid,w,row['title'],row['body'],dump(source),actor,stamp,stamp))
            if old:c.execute("UPDATE team_public_knowledge SET status='superseded',updated_at=? WHERE id=?",(stamp,old['id']))
            self.touch(c,row['project_id'])
            return {'id':kid,'duplicate':False}

    def withdraw_knowledge(self,w,kid,actor):
        with self.connection(True) as c:
            self.workspace_require(c,w,actor,owner=True)
            n=c.execute("UPDATE team_public_knowledge SET status='withdrawn',updated_at=? WHERE id=? AND workspace_id=? AND status='published'",(now(),kid,w)).rowcount
            if not n:raise Problem(404,'公共知识不存在或已撤回')
        return {'ok':True}

    def search(self,p,actor,query,limit=6):
        project_hits=super().search(p,actor,query,limit)
        with self.connection() as c:
            self.require(c,p,actor)
            link=c.execute('SELECT workspace_id FROM team_project_workspace WHERE project_id=?',(p,)).fetchone()
        if not link:return project_hits
        terms=set(tokenize(query));public=[]
        for k in self.public_knowledge(link[0],actor):
            score=len(terms.intersection(tokenize(k['title']+' '+k['body'])))
            if score:public.append((score,{'id':k['id'],'document_id':k['id'],'title':k['title'],'revision':k['revision'],
                'location':'公司公共知识 · 明确发布快照','content':k['body'][:1600],'adopted':True,'scope':'workspace','workspace_id':link[0]}))
        public.sort(key=lambda x:x[0],reverse=True)
        return (project_hits[:max(0,limit-min(2,len(public)))]+[x[1] for x in public[:min(2,limit)]])[:limit]

    def public_document(self,kid,actor):
        with self.connection() as c:
            row=c.execute("SELECT * FROM team_public_knowledge WHERE id=? AND status='published'",(kid,)).fetchone()
            if not row:raise Problem(404,'公共知识不存在或已撤回')
            self.workspace_require(c,row['workspace_id'],actor)
            result=dict(row);result['source']=json.loads(result.pop('source_json'));result['kind']='company';result['adopted']=True
            return result

    def _export_project(self,p):
        with self.connection() as c:
            deleted=self.deleted(c,p)
        if deleted:
            with self.connection(True) as c:c.execute('UPDATE team_outbox SET exported_revision=revision,error=NULL WHERE project_id=?',(p,))
            return
        # Remove only stale generated projections; originals and DB history stay intact.
        with self.connection() as c:
            removed=c.execute("SELECT id,kind FROM team_objects WHERE project_id=? AND status='deleted'",(p,)).fetchall()
        root=self.data_dir/'exports'/p
        for old in removed:
            if not old['id'].replace('_','').isalnum():continue
            (root/old['kind']/(old['id']+'.md')).unlink(missing_ok=True)
            if old['kind']=='task':(root/'task-discussions'/(old['id']+'.md')).unlink(missing_ok=True)
        from .project_space import export_space
        export_space(self,p)
        super()._export_project(p)
        from .platform_export import export_project_platform
        export_project_platform(self,p)
        # All-message export remains for compatibility, but each task gets its
        # own readable transcript; no public or private cross-project dumping.
        with self.connection() as c:
            rows=c.execute("SELECT m.* FROM team_messages m WHERE m.project_id=? AND NOT EXISTS (SELECT 1 FROM team_objects t WHERE t.id=json_extract(m.meta_json,'$.task_id') AND t.status='deleted') ORDER BY m.seq",(p,)).fetchall()
        groups={}
        for row in rows:
            m=self.message_json(row);tid=m.get('task_id')
            if tid:groups.setdefault(tid,[]).append(m)
        for tid,items in groups.items():
            if not tid.replace('_','').isalnum():continue
            folder=self.data_dir/'exports'/p/'task-discussions';folder.mkdir(exist_ok=True)
            text='---\n'+dump({'project_id':p,'task_id':tid})+'\n---\n\n'+'\n\n'.join(f"## #{m['seq']} · {m['author_name']}\n\n{m['content']}" for m in items)
            temp=folder/(tid+'.md.tmp');temp.write_text(text,encoding='utf-8');temp.replace(folder/(tid+'.md'))
