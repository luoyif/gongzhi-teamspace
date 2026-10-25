"""Independent library lifecycle, pinning and ACL tests. No model/network calls."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from teamspace.workspace import WorkspaceStore
from teamspace.platform_registry import PlatformRegistry,HARNESS_DEFAULTS
from teamspace.agent_registry import AgentRegistry as Legacy
from teamspace.store import Problem,dump

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();r=Path(self.tmp.name);self.s=WorkspaceStore(r/'db',r/'data')
        self.a=NS(id=1,username='alice',display_name='甲',role='admin');self.b=NS(id=2,username='bob',display_name='乙',role='user');self.c=NS(id=3,username='carol',display_name='丙',role='user')
        self.w=self.s.create_workspace(self.a,{'name':'公司甲'})['id'];self.other=self.s.create_workspace(self.c,{'name':'公司乙'})['id']
        self.r=PlatformRegistry(self.s);self.assets=self.r.catalog(self.w,1)['items']
        self.agent=next(a for a in self.assets if a['kind']=='agent');self.h=next(a for a in self.assets if a['kind']=='harness');self.skill=next(a for a in self.assets if a['kind']=='skill')
        self.p=self.s.create_project(self.a,{'title':'P1','workspace_id':self.w})['id'];self.p2=self.s.create_project(self.a,{'title':'P2','workspace_id':self.w})['id']
        self.s.set_member(self.p,1,self.b,'member')
        with self.s.connection(True) as c:
            self.mid=self.r._insert_asset(c,self.w,1,'model','离线模型',{'provider_name':'team-project-test','model':'mock','base_url':'https://example.com/v1','configured':True})
            c.execute('INSERT INTO team_platform_defaults VALUES(?,?)',(self.w,self.mid))
    def tearDown(self):self.tmp.cleanup()
    def fail(self,code,fn,*a,**kw):
        with self.assertRaises(Problem) as e:fn(*a,**kw)
        self.assertEqual(code,e.exception.status,str(e.exception))
    def bind(self,p=None):return self.r.bind(p or self.p,1,self.agent['id'],{'asset_revision':self.agent['revision'],'expected_binding_revision':0,'pin_version':True})
    def cfg(self,p=None):
        p=p or self.p
        with self.s.connection() as c:out=self.r.snapshot(c,p,1,{'agent_id':self.agent['id']},self.s.settings(p,1))
        return {**out,'_project_id':p,'_actor_id':1}
    def test_library_exists_without_any_project_owned_records(self):
        self.assertTrue(all('workspace_id' in a and 'project_id' not in a for a in self.assets))
        self.assertTrue(self.r.list(self.p,1,'agent'));self.assertEqual([],self.r.bindings(self.p,1))
        with self.s.connection() as c:self.assertEqual(0,c.execute('SELECT COUNT(*) FROM team_capabilities').fetchone()[0])
    def test_one_asset_reused_in_two_projects_without_cloning(self):
        self.bind();self.bind(self.p2)
        a=self.r.list(self.p,1,'agent')[0];b=self.r.list(self.p2,1,'agent')[0]
        self.assertEqual(a['id'],b['id']);self.assertEqual(a['id'],self.agent['id'])
    def test_project_member_cannot_edit_or_bind(self):
        self.fail(403,self.r.save_asset,self.w,2,'agent',{'name':'bad','data':self.agent['data']})
        self.fail(403,self.r.bind,self.p,2,self.agent['id'],{'asset_revision':1})
    def test_other_workspace_catalog_and_binding_denied(self):
        self.fail(404,self.r.catalog,self.w,3)
        foreign=self.r.catalog(self.other,3)['items'][0]
        self.fail(404,self.r.bind,self.p,1,foreign['id'],{'asset_revision':foreign['revision']})
    def test_global_edit_does_not_change_existing_binding(self):
        self.bind();self.bind(self.p2);old=self.cfg()['agent_snapshot']
        current=self.r.save_asset(self.w,1,'agent',{'expected_revision':1,'data':{**self.agent['data'],'system_prompt':'new global prompt'}},self.agent['id'])
        self.assertEqual(1,self.cfg()['agent_snapshot']['revision']);self.assertEqual(old,self.cfg()['agent_snapshot'])
        self.r.bind(self.p,1,current['id'],{'expected_binding_revision':1,'asset_revision':2,'pin_version':True})
        self.assertEqual('new global prompt',self.cfg()['agent_snapshot']['data']['system_prompt'])
        self.assertEqual(1,self.cfg(self.p2)['agent_snapshot']['revision'])
    def test_dependency_edit_is_pinned_until_explicit_upgrade(self):
        self.bind();before=self.cfg()['harness_snapshot']
        self.r.save_asset(self.w,1,'harness',{'expected_revision':1,'data':{**self.h['data'],'max_model_steps':2,'retrieval_mode':'explicit'}},self.h['id'])
        self.assertEqual(before,self.cfg()['harness_snapshot'])
        self.r.bind(self.p,1,self.agent['id'],{'expected_binding_revision':1,'asset_revision':1,'pin_version':True})
        self.assertEqual(2,self.cfg()['agent_snapshot']['data']['max_model_steps']);self.assertEqual('explicit',self.cfg()['retrieval_mode'])
    def test_disable_central_agent_stops_all_bound_projects(self):
        self.bind();self.bind(self.p2);cfg=self.cfg()
        self.r.save_asset(self.w,1,'agent',{'expected_revision':1,'enabled':False},self.agent['id'])
        self.fail(409,self.r.assert_run_scope,cfg);self.fail(409,self.cfg,self.p2)
    def test_project_unbind_does_not_disable_other_projects(self):
        self.bind();self.bind(self.p2);cfg=self.cfg()
        self.r.bind(self.p,1,self.agent['id'],{'expected_binding_revision':1,'enabled':False})
        self.fail(404,self.r.assert_run_scope,cfg);self.assertTrue(self.cfg(self.p2)['agent_snapshot']['enabled'])
    def test_stale_binding_write_rejected(self):
        self.bind();self.fail(409,self.r.bind,self.p,1,self.agent['id'],{'expected_binding_revision':0,'asset_revision':1})
    def test_draft_skill_never_mounts(self):
        sk=self.r.save_asset(self.w,1,'skill',{'name':'草稿','enabled':False,'data':{'slug':'draft','body':'# draft','status':'draft'}})
        self.fail(409,self.r.bind,self.p,1,sk['id'],{'asset_revision':1})
        self.fail(422,self.r.save_asset,self.w,1,'agent',{'expected_revision':1,'data':{**self.agent['data'],'skill_ids':[sk['id']]}},self.agent['id'])
    def test_harness_rejects_fake_switches_and_invalid_limits(self):
        for patch in ({'automatic_retry':True},{'stream':False},{'execution_mode':'multi_agent'},{'max_model_steps':True},{'max_model_steps':100},{'tools':['execute']}):
            self.fail(422,self.r.save_asset,self.w,1,'harness',{'name':'bad','data':patch})
    def test_harness_context_and_document_limits_are_real_snapshot_fields(self):
        self.r.save_asset(self.w,1,'harness',{'expected_revision':1,'data':{'max_context_chars':11000,'max_documents':1,'max_document_chars':1000,'history_limit':8}},self.h['id'])
        self.bind();d1=self.s.create_note(self.p,1,{'title':'D1','body':'x'*1100});d2=self.s.create_note(self.p,1,{'title':'D2','body':'text'})
        with self.s.connection() as c:
            cfg=self.r.snapshot(c,self.p,1,{'agent_id':self.agent['id'],'document_ids':[d1['id']]},self.s.settings(self.p,1))
            self.assertEqual(1000,len(cfg['explicit_documents'][0]['content']));self.assertTrue(cfg['explicit_documents'][0]['truncated']);self.assertEqual(8,cfg['history_limit'])
            self.fail(422,self.r.snapshot,c,self.p,1,{'agent_id':self.agent['id'],'document_ids':[d1['id'],d2['id']]},self.s.settings(self.p,1))
    def test_same_agent_does_not_grant_other_project_documents(self):
        self.bind();self.bind(self.p2);secret=self.s.create_note(self.p2,1,{'title':'secret','body':'PRIVATE'})
        self.fail(404,self.r.resolve_document,self.p,1,secret['id'])
        self.fail(404,self.r.resolve_document,self.p,2,secret['id'])
    def test_skill_from_knowledge_is_global_restricted_disabled_draft(self):
        doc=self.s.create_note(self.p,1,{'title':'lesson','body':'project private workflow'})
        a=self.r.draft_skill_from_document(self.p,1,doc['id']);self.assertEqual(self.w,a['workspace_id']);self.assertNotIn('project_id',a)
        self.assertEqual('restricted',a['visibility']);self.assertFalse(a['enabled']);self.assertEqual(doc['id'],a['source']['document_id'])
        self.fail(422,self.r.save_asset,self.w,1,'skill',{'expected_revision':1,'visibility':'workspace'},a['id'])
    def test_restore_creates_new_revision_leaves_pinned_version(self):
        self.bind();a=self.r.save_asset(self.w,1,'agent',{'expected_revision':1,'data':{**self.agent['data'],'system_prompt':'changed'}},self.agent['id'])
        restored=self.r.restore_version(a['id'],1,{'expected_revision':2,'restore_revision':1})
        self.assertEqual(3,restored['revision']);self.assertEqual(self.agent['data'],restored['data']);self.assertEqual(1,self.cfg()['agent_snapshot']['revision'])
    def test_migration_retains_legacy_ids_configs_history_and_is_idempotent(self):
        # Separate pre-v4 DB, with a real private project configuration.
        root=Path(self.tmp.name)/'legacy';root.mkdir();s=WorkspaceStore(root/'db',root/'data');p=s.create_project(self.a,{'title':'旧项目'})['id'];l=Legacy(s);l.ensure_defaults(p,1)
        before=[x['id'] for x in l.list(p,1)];old=l.default_agent(p,1)
        with s.connection() as c:rows=[tuple(x) for x in c.execute('SELECT * FROM team_capabilities ORDER BY id')]
        migrated=PlatformRegistry(s);p2=s.create_project(self.a,{'title':'新项目'})['id']
        new=migrated.get(old['id'],1);self.assertEqual('restricted',new['visibility']);self.assertEqual(old['data']['system_prompt'],new['data']['system_prompt'])
        self.assertEqual(old['id'],migrated.list(p,1,'agent')[0]['id'] if len(migrated.list(p,1,'agent'))==1 else migrated.bound_agent(p,1,old['id'])['id'])
        self.fail(403,migrated.bind,p2,1,old['id'],{'asset_revision':old['revision']})
        PlatformRegistry(s)
        with s.connection() as c:self.assertEqual(rows,[tuple(x) for x in c.execute('SELECT * FROM team_capabilities ORDER BY id')])
        for aid in before:self.assertEqual(aid,migrated.get(aid,1)['id'])
    def test_workspace_owner_cannot_read_unshared_project_configuration(self):
        doc=self.s.create_note(self.p,1,{'title':'private','body':'PRIVATE_CONFIG'})
        a=self.r.draft_skill_from_document(self.p,1,doc['id'])
        self.s.set_workspace_member(self.w,1,self.c,'owner')
        self.fail(404,self.r.get,a['id'],3)
        self.assertNotIn(a['id'],[x['id'] for x in self.r.catalog(self.w,3)['items']])
    def test_new_project_agent_requires_configured_company_model(self):
        with self.s.connection(True) as c:c.execute('DELETE FROM team_platform_defaults WHERE workspace_id=?',(self.w,))
        self.fail(422,self.bind)
    def test_migration_preserves_both_project_and_agent_instructions(self):
        root=Path(self.tmp.name)/'legacy-prompts';root.mkdir();s=WorkspaceStore(root/'db',root/'data')
        p=s.create_project(self.a,{'title':'旧提示词项目'})['id'];cfg=s.settings(p,1)
        s.save_settings(p,1,{'expected_revision':cfg['revision'],'system_prompt':'PROJECT_POLICY_KEEP'})
        l=Legacy(s);l.ensure_defaults(p,1);a=next(x for x in l.list(p,1,'agent') if x['name']=='资料核查员')
        migrated=PlatformRegistry(s).get(a['id'],1)
        self.assertIn('PROJECT_POLICY_KEEP',migrated['data']['system_prompt'])
        self.assertIn(a['data']['system_prompt'],migrated['data']['system_prompt'])
    def test_mcp_credential_rotation_changes_version_without_exposing_secret(self):
        from unittest.mock import patch
        from teamspace.mcp_bridge import save_headers
        m=self.r.save_asset(self.w,1,'mcp',{'name':'remote-header-test','enabled':True,'data':{'transport':'streamable_http','url':'https://example.com/mcp','allowed_tools':['read']}},site_admin=True)
        a=self.r.save_asset(self.w,1,'agent',{'expected_revision':1,'data':{**self.agent['data'],'mcp_ids':[m['id']]}},self.agent['id'])
        self.agent=a;self.bind();cfg=self.cfg()
        with patch('octop.infra.auth.sso.crypto.encrypt_secret',return_value=b'ciphertext-fixture'):
            save_headers(NS(services=NS(secret_repo=object())),self.r,m['id'],self.a,{'Authorization':'Bearer UNIT_ONLY_VALUE'})
        updated=self.r.get(m['id'],1);self.assertEqual(2,updated['revision'])
        self.assertNotIn('UNIT_ONLY_VALUE',dump(updated));self.assertNotIn('UNIT_ONLY_VALUE',dump(self.r.history(m['id'],1)))
        self.fail(409,self.r.assert_run_scope,cfg)
    def test_legacy_project_mutation_refuses_new_project_owned_asset(self):
        self.fail(409,self.r.save,self.p,1,'skill',{'name':'not allowed'})
    def test_shared_agent_cannot_expose_restricted_dependency(self):
        sk=self.r.save_asset(self.w,1,'skill',{'name':'private','visibility':'restricted','enabled':True,'data':{'slug':'private','body':'private rule','status':'published'}})
        self.fail(422,self.r.save_asset,self.w,1,'agent',{'expected_revision':1,'data':{**self.agent['data'],'skill_ids':[sk['id']]}},self.agent['id'])
    def test_connection_revision_change_requires_project_upgrade(self):
        self.bind();cfg=self.cfg()
        with self.s.connection(True) as c:c.execute('UPDATE team_platform_assets SET revision=revision+1 WHERE id=?',(self.mid,))
        self.fail(409,self.r.assert_run_scope,cfg)

if __name__=='__main__':unittest.main(verbosity=2)
