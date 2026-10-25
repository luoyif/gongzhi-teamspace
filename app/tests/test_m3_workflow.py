"""M3 sequential plan: real evidence gates, bounded calls, idempotence and ACL."""
from __future__ import annotations
import asyncio,json,secrets,unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
import test_platform_v4 as base
from teamspace.store import Problem,now,dump
from teamspace.task_workflows import (
 get_plan,create_plan,revise_plan,start_step,approve_step,retry_step,step_history,reconcile_step,
)

class WorkflowTests(unittest.TestCase):
 def setUp(self):
  base.PlatformTests.setUp(self)
  self.task=self.s.create_task(self.p,1,{"title":"合同审查与产品交付"})
  self.other=self.s.create_task(self.p,1,{"title":"别的任务"})
  self.agent2=self.r.save_asset(self.w,1,"agent",{"name":"工程师","data":{
   **self.agent["data"],"system_prompt":"你是工程师。严格保留证据。"}})
  self.server=NS()
  self.mocks=patch("teamspace.task_workflows.store_for",lambda _:self.s)
  self.mocks.start()
  self.sent=[]
  self.model_run_status="completed"
 def tearDown(self):
  self.mocks.stop()
  base.PlatformTests.tearDown(self)
 def plan_body(self):
  return {"title":"研究→实施→验收","description":"分阶段交付，最终由管理员确认",
          "steps":[
           {"kind":"agent","title":"研究分析","instruction":"检查原始资料并列出可验证结论",
            "agent_id":self.agent["id"]},
           {"kind":"agent","title":"技术设计","instruction":"依据研究结果设计原型并说明未实施部分",
            "agent_id":self.agent2["id"]},
           {"kind":"review","title":"人工验收","instruction":"核对两个Run产物和证据，不自动发布团队知识"},
          ]}
 def create(self,actor=None):
  return create_plan(self.task["id"],self.plan_body(),user=actor or self.a,server=self.server)
 def runstep(self,stepid,actor=None):
  testcase=self
  class MockController:
   def start_run(self,project,user,payload):
    testcase.sent.append(payload)
    rid="workflow_test_run_"+str(len(testcase.sent))
    with testcase.s.connection(True) as c:
     cfg=testcase.r.snapshot(c,project,user.id,{"agent_id":payload["agent_id"]},
                              testcase.s.settings(project,user.id))
     cfg.update(_project_id=project,_actor_id=user.id,_run_id=rid)
     c.execute("""INSERT INTO team_runs
     (id,project_id,actor_id,kind,client_id,status,input_seq,config_json,request_json,created_at)
     VALUES(?,?,?,'chat',?,?,?,?,?,?)""",
     (rid,project,user.id,payload["client_id"],testcase.model_run_status,0,dump(cfg),
      dump({"task_id":testcase.task["id"],"prompt":payload["prompt"],
       "continue_from":payload.get("continue_from")}),now()))
     if testcase.model_run_status=="completed":
      testcase.s.add_message(c,project,0,"被测员工","TEST_RESULT_RUN_"+str(len(testcase.sent)),
        secrets.token_hex(8),"assistant",run_id=rid,meta={"task_id":testcase.task["id"]})
    return {"id":rid}
  with patch("teamspace.task_workflows.controller",lambda _:MockController()):
   return asyncio.run(start_step(self.task["id"],stepid,user=actor or self.a,server=self.server))
 def approve(self,stepid,note="已核对来源和报告，确认进入下一个步骤",actor=None):
  return approve_step(self.task["id"],stepid,{"note":note},user=actor or self.a,server=self.server)
 def test_plan_requires_owner_and_ends_in_manual_review(self):
  self.assertEqual(get_plan(self.task["id"],user=self.a,server=self.server)["status"],"missing")
  with self.assertRaises(Problem):self.create(actor=self.b)
  bad=self.plan_body();bad["steps"][-1]={"kind":"agent","title":"自动结尾","instruction":"写总结","agent_id":self.agent["id"]}
  with self.assertRaises(Problem):create_plan(self.task["id"],bad,user=self.a,server=self.server)
  created=self.create();self.assertEqual(created["status"],"active")
  self.assertEqual(len(created["steps"]),3)
  self.assertTrue(created["sequential_only"]);self.assertFalse(created["automatic_dispatch"])
  self.assertEqual(self.create()["id"],created["id"])
  self.assertEqual(self.sent,[],"Plan construction must not call AI")
 def test_sequential_model_steps_review_gate_and_exactly_once_start(self):
  plan=self.create();one,two,review=[x["id"] for x in plan["steps"]]
  with self.assertRaises(Problem):self.runstep(two)
  started=self.runstep(one)
  self.assertEqual(len(self.sent),1)
  self.assertEqual(started["steps"][0]["effective_status"],"needs_review")
  again=self.runstep(one);self.assertEqual(len(self.sent),1)
  with self.assertRaises(Problem):self.runstep(two)
  with self.assertRaises(Problem):self.approve(one,"太短")
  reviewed=self.approve(one)
  self.assertEqual(reviewed["steps"][0]["status"],"accepted")
  self.assertEqual(reviewed["steps"][0]["approved_by"],self.a.id)
  second=self.runstep(two)
  self.assertEqual(len(self.sent),2)
  self.assertEqual(self.sent[1]["continue_from"],"workflow_test_run_1")
  self.assertEqual(self.sent[1]["run_options"]["permission_mode"],"safe")
  self.approve(two)
  with self.assertRaises(Problem):self.approve(review,"不够")
  done=self.approve(review)
  self.assertEqual(done["status"],"completed")
  self.assertTrue(done["user_approval_required"])
  self.assertFalse(done["knowledge_published"])
  self.assertEqual(self.approve(review)["status"],"completed")
 def test_revision_conflict_and_cannot_replace_started_plan(self):
  plan=self.create()
  revised=self.plan_body();revised["description"]="明确改进后的验收标准"
  with self.assertRaises(Problem):
   revise_plan(self.task["id"],{**revised,"expected_revision":7},user=self.a,server=self.server)
  new=revise_plan(self.task["id"],{**revised,"expected_revision":1},user=self.a,server=self.server)
  self.assertEqual(new["revision"],2)
  self.runstep(new["steps"][0]["id"])
  with self.assertRaises(Problem):
   revise_plan(self.task["id"],{**self.plan_body(),"expected_revision":2},user=self.a,server=self.server)
 def test_model_revision_change_blocks_dispatch(self):
  plan=self.create();sid=plan["steps"][0]["id"]
  self.r.save_asset(self.w,1,"agent",
    {"expected_revision":1,"data":{**self.agent["data"],"system_prompt":"变更后提示词"}},self.agent["id"])
  with self.assertRaises(Problem):self.runstep(sid)
  self.assertEqual(self.sent,[])
 def test_explicit_failed_step_retry_retains_historical_run_and_revision(self):
  plan=self.create();sid=plan["steps"][0]["id"]
  self.model_run_status="failed"
  started=self.runstep(sid)
  self.assertEqual(started["steps"][0]["effective_status"],"blocked")
  with self.assertRaises(Problem):self.approve(sid)
  with self.assertRaises(Problem):
   retry_step(self.task["id"],sid,{"reason":"retry"},user=self.a,server=self.server)
  re=retry_step(self.task["id"],sid,{"reason":"工具输出未完成，已复核 Run，需要明确重试"},user=self.a,server=self.server)
  self.assertEqual(re["steps"][0]["status"],"pending")
  self.assertEqual(re["steps"][0]["revision"],2)
  hist=step_history(self.task["id"],sid,user=self.a,server=self.server)["items"]
  self.assertEqual(hist[0]["old_run_id"],"workflow_test_run_1")
  self.model_run_status="completed"
  after=self.runstep(sid)
  self.assertEqual(after["steps"][0]["run_id"],"workflow_test_run_2")
  self.assertNotEqual(self.sent[0]["client_id"],self.sent[1]["client_id"])
 def test_dispatched_step_can_be_reconciled_without_new_model_call(self):
  plan=self.create();one,two,review=[x["id"] for x in plan["steps"]]
  self.runstep(one)
  prior_count=len(self.sent)
  with self.s.connection(True) as c:
   c.execute("UPDATE team_task_workflow_steps SET status='dispatching',run_id=NULL WHERE id=?",(one,))
  restored=reconcile_step(self.task["id"],one,user=self.a,server=self.server)
  self.assertEqual(restored["steps"][0]["run_id"],"workflow_test_run_1")
  self.assertEqual(restored["steps"][0]["status"],"running")
  self.assertEqual(len(self.sent),prior_count)
  with self.assertRaises(Problem):reconcile_step(self.task["id"],one,user=self.a,server=self.server)
  self.approve(one)
  with self.s.connection(True) as c:
   c.execute("UPDATE team_task_workflow_steps SET status='dispatching' WHERE id=?",(two,))
  result=reconcile_step(self.task["id"],two,user=self.a,server=self.server)
  self.assertEqual(result["steps"][1]["status"],"pending")
  self.assertIsNone(result["steps"][1]["run_id"])
  self.assertEqual(len(self.sent),prior_count)
  self.assertEqual(len(step_history(self.task["id"],one,user=self.a,server=self.server)["items"]),1)
 def test_scope_deleted_task_and_read_only_acl(self):
  plan=self.create()
  with self.assertRaises(Problem):get_plan(self.task["id"],user=self.c,server=self.server)
  with self.assertRaises(Problem):
   approve_step(self.other["id"],plan["steps"][0]["id"],{"note":"确认已核对，但不可访问"},user=self.a,server=self.server)
  self.s.remove_member(self.p,1,2)
  with self.assertRaises(Problem):
   get_plan(self.task["id"],user=self.b,server=self.server)
  with self.s.connection(True) as c:
   c.execute("INSERT INTO team_admin_trash(target_id,workspace_id,project_id,kind,title,previous_json,deleted_at,deleted_by,batch_id) VALUES(?,?,?,?,?,?,?,?,?)",
             (self.task["id"],self.w,self.p,"task","归档流程任务","{}",now(),1,"test_batch"))
  with self.assertRaises(Problem):
   get_plan(self.task["id"],user=self.a,server=self.server)
 def test_manual_step_never_calls_agent_or_publishes_knowledge(self):
  plan=self.create();one,two,review=[x["id"] for x in plan["steps"]]
  self.runstep(one);self.approve(one)
  self.runstep(two);self.approve(two)
  with self.assertRaises(Problem):self.runstep(review)
  result=self.approve(review,"已核对两次真实回复，未授权发布团队知识")
  self.assertEqual(result["status"],"completed")
  self.assertFalse(result["knowledge_published"])
  self.assertEqual(len(self.sent),2)
if __name__=="__main__":unittest.main()
