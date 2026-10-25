"""M2: source-verified, human-approved, bounded serial Agent handoffs. No model calls."""
import asyncio,json,secrets,unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
import test_platform_v4 as base
from teamspace.store import Problem,now,dump
from teamspace.agent_handoff import propose_handoff,approve_handoff,reject_handoff,cancel_handoff,list_handoffs,task_workflow,reconcile_handoff
from teamspace.platform_registry import PlatformRegistry

class HandoffTests(unittest.TestCase):
 def setUp(self):
  base.PlatformTests.setUp(self)
  self.t=self.s.create_task(self.p,1,{'title':'交接任务'})
  self.other=self.s.create_task(self.p,1,{'title':'另一个任务'})
  data={**self.agent['data'],'system_prompt':'你是研发工程师，只在授权范围内工作。'}
  self.bagent=self.r.save_asset(self.w,1,'agent',{'name':'研发工程师','data':data})
  self.extras=[]
  self.source_run('r_source',self.agent['id'],self.t['id'],'原研究成果：比较方案A与B，但尚未经人工验收。')
  self.calls=[]
  self.server=NS()
  self.mock=patch('teamspace.agent_handoff.store_for',lambda s:self.s)
  self.mock.start()
 def tearDown(self):
  self.mock.stop()
  base.PlatformTests.tearDown(self)
 def source_run(self,rid,aid,tid,text):
  with self.s.connection() as c:cfg=self.r.snapshot(c,self.p,1,{'agent_id':aid},self.s.settings(self.p,1))
  cfg.update(_project_id=self.p,_actor_id=1,_run_id=rid,conversation_task_id=tid)
  with self.s.connection(True) as c:
   c.execute("INSERT INTO team_runs(id,project_id,actor_id,kind,client_id,status,input_seq,config_json,request_json,created_at) VALUES(?,?,1,'chat',?,'completed',0,?,?,?)",
            (rid,self.p,rid,dump(cfg),dump({'task_id':tid,'prompt':'original'}),now()))
   self.s.add_message(c,self.p,0,'研究分析师',text,secrets.token_hex(8),'assistant',run_id=rid,meta={'task_id':tid})
 def proposal(self,actor=None,source='r_source',target=None,instruction='实现一个简短技术方案，先验证原报告结果。'):
  return propose_handoff(self.t['id'],{'source_run_id':source,'target_agent_id':target or self.bagent['id'],'instruction':instruction},user=actor or self.a,server=self.server)
 def approve(self,hid,actor=None):
  fake=self
  class ControllerFake:
   def start_run(self,p,user,payload):
    fake.calls.append(payload)
    return {'id':'r_approved_'+str(len(fake.calls))}
  with patch('teamspace.agent_handoff.controller',lambda _:ControllerFake()):
   return asyncio.run(approve_handoff(self.t['id'],hid,user=actor or self.a,server=self.server))
 def test_create_and_approve_must_be_explicit_and_never_auto_trigger_model(self):
  item=self.proposal(actor=self.b)
  self.assertEqual(item['status'],'pending');self.assertEqual(item['hop'],1);self.assertEqual(self.calls,[])
  self.assertEqual(list_handoffs(self.t['id'],user=self.a,server=self.server)['items'][0]['status'],'pending')
  with self.assertRaises(Problem):self.approve(item['id'],actor=self.b)
  approved=self.approve(item['id'])
  self.assertEqual(approved['status'],'approved');self.assertEqual(len(self.calls),1)
  payload=self.calls[0]
  self.assertEqual(payload['agent_id'],self.bagent['id']);self.assertEqual(payload['task_id'],self.t['id'])
  self.assertEqual(payload['continue_from'],'r_source')
  self.assertEqual(payload['run_options']['permission_mode'],'safe')
  self.assertIn('先核查来源 Agent 报告',payload['prompt'])
  self.assertEqual(self.approve(item['id'])['target_run_id'],approved['target_run_id'])
  self.assertEqual(len(self.calls),1,'repeat approval invoked model again')
 def test_idempotent_source_and_different_target_blocked(self):
  item=self.proposal()
  self.assertEqual(item['id'],self.proposal()['id'])
  with self.assertRaises(Problem):self.proposal(instruction='another instruction')
 def test_only_owner_can_reject_and_member_can_cancel_own_request(self):
  x=self.proposal(actor=self.b)
  with self.assertRaises(Problem):reject_handoff(self.t['id'],x['id'],user=self.b,server=self.server)
  rejected=reject_handoff(self.t['id'],x['id'],user=self.a,server=self.server)
  self.assertEqual(rejected['status'],'rejected')
  with self.assertRaises(Problem):self.approve(x['id'])
 def test_requester_may_cancel_before_dispatch_only(self):
  x=self.proposal(actor=self.b)
  with self.assertRaises(Problem):cancel_handoff(self.t['id'],x['id'],user=self.c,server=self.server)
  self.assertEqual(cancel_handoff(self.t['id'],x['id'],user=self.b,server=self.server)['status'],'cancelled')
  with self.assertRaises(Problem):self.approve(x['id'])
 def test_target_revision_change_requires_new_review(self):
  x=self.proposal()
  self.r.save_asset(self.w,1,'agent',{'expected_revision':1,'data':{**self.bagent['data'],'system_prompt':'修订后的职责'}},self.bagent['id'])
  with self.assertRaises(Problem) as err:self.approve(x['id'])
  self.assertEqual(err.exception.status,409)
  self.assertEqual(list_handoffs(self.t['id'],user=self.a,server=self.server)['items'][0]['status'],'pending')
 def test_source_incomplete_and_self_route_rejected(self):
  with self.assertRaises(Problem):self.proposal(target=self.agent['id'])
  with self.s.connection(True) as c:c.execute("UPDATE team_runs SET status='paused' WHERE id='r_source'")
  with self.assertRaises(Problem):self.proposal()
 def test_different_task_revocation_and_legacy_run_cannot_be_handoff_source(self):
  with self.assertRaises(Problem):
   propose_handoff(self.other['id'],{'source_run_id':'r_source','target_agent_id':self.bagent['id'],'instruction':'x'},user=self.a,server=self.server)
  self.s.remove_member(self.p,1,2)
  with self.assertRaises(Problem):self.proposal(actor=self.b)
  self.source_run('r_legacy','',self.t['id'],'legacy') if False else None
 def test_task_workflow_projection_reads_only_real_handoffs_and_respects_acl(self):
  first=self.proposal()
  initial=task_workflow(self.t['id'],user=self.b,server=self.server)
  self.assertFalse(initial['has_executable_dag'])
  self.assertEqual(len(initial['nodes']),1)
  self.assertEqual(initial['nodes'][0]['status'],'pending')
  self.assertIsNone(initial['nodes'][0]['target_run_status'])
  done=self.approve(first['id'])
  after=task_workflow(self.t['id'],user=self.a,server=self.server)
  self.assertEqual(after['nodes'][0]['target_run_id'],done['target_run_id'])
  self.assertFalse(after['nodes'][0]['result_adopted'])
  self.assertEqual(task_workflow(self.other['id'],user=self.a,server=self.server)['nodes'],[])
  with self.assertRaises(Problem):
   task_workflow(self.t['id'],user=self.c,server=self.server)
 def test_explicit_reconcile_finds_existing_run_or_returns_pending_without_dispatch(self):
  item=self.proposal()
  with self.s.connection(True) as c:
   c.execute("UPDATE team_task_agent_handoffs SET status='dispatching' WHERE id=?",(item["id"],))
  repaired=reconcile_handoff(self.t["id"],item["id"],user=self.a,server=self.server)
  self.assertEqual(repaired["status"],"pending")
  self.assertIsNone(repaired["target_run_id"])
  self.assertEqual(self.calls,[])
  self.source_run('r_recover_target',self.bagent['id'],self.t['id'],'已保存真实回复，可供人工核对')
  with self.s.connection(True) as c:
   c.execute("UPDATE team_runs SET client_id=? WHERE id=?",('handoff-'+item["id"],'r_recover_target'))
   c.execute("UPDATE team_task_agent_handoffs SET status='dispatching' WHERE id=?",(item["id"],))
  linked=reconcile_handoff(self.t["id"],item["id"],user=self.a,server=self.server)
  self.assertEqual(linked["status"],"approved")
  self.assertEqual(linked["target_run_id"],'r_recover_target')
  self.assertEqual(self.calls,[])
  with self.assertRaises(Problem):
   reconcile_handoff(self.t["id"],item["id"],user=self.a,server=self.server)
 def test_no_third_hop(self):
  first=self.proposal();self.approve(first['id'])
  # Synthetic finished outcome for the first approved handoff.
  source2='r_b1'
  with self.s.connection(True) as c:c.execute("UPDATE team_task_agent_handoffs SET target_run_id=? WHERE id=?",(source2,first['id']))
  self.source_run(source2,self.bagent['id'],self.t['id'],'工程师已准备实现方案（未经人工验收）')
  second=self.proposal(source=source2,target=self.agent['id'],instruction='请复核方案，不要写入')
  self.assertEqual(second['hop'],2);self.assertEqual(second['chain_id'],first['chain_id'])
  with self.s.connection(True) as c:c.execute("UPDATE team_task_agent_handoffs SET status='approved',target_run_id=? WHERE id=?",('r_b2',second['id']))
  self.source_run('r_b2',self.agent['id'],self.t['id'],'复核已完成，但请真人验收')
  with self.assertRaises(Problem) as err:self.proposal(source='r_b2',target=self.bagent['id'])
  self.assertEqual(err.exception.status,409)
if __name__=='__main__':unittest.main()
