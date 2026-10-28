"""Gongzhi vs QM/Ekko differentiation acceptance scenarios: real scoped records.

No model, API keys, external data or production state. The benchmark asserts
only Gongzhi's implementation; it does NOT pretend to measure QM/Ekko runtime.
"""
import hashlib
import json
import secrets
import unittest
from unittest.mock import patch

import test_platform_v4 as base
from teamspace.store import Problem,dump,now
from teamspace.task_evidence import task_evidence_graph
from teamspace.agent_trace import RunTrace


class TaskEvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        base.PlatformTests.setUp(self)
        self.t=self.s.create_task(self.p,1,{"title":"知识流转：调研→设计→验收"})["id"]
        self.t2=self.s.create_task(self.p,1,{"title":"同项目的其他任务"})["id"]
        self.patch=patch("teamspace.task_evidence.store_for",lambda _server:self.s)
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
        base.PlatformTests.tearDown(self)
    def graph(self,actor=None,task=None):
        return task_evidence_graph(task or self.t,user=actor or self.a,server=object())
    def message(self,content,actor=1,kind="human",runid=None,task=None,p=None):
        project=p or self.p
        tid=task or self.t
        with self.s.connection(True) as c:
            return self.s.add_message(c,project,actor,"研究员甲" if actor==1 else "设计师乙",
                      content,secrets.token_hex(8),kind,run_id=runid,meta={"task_id":tid})
    def fake_run(self,runid="run_scoped_1",status="completed"):
        cfg=base.PlatformTests.cfg(self)
        cfg["agent_snapshot"]["id"]=self.agent["id"]
        with self.s.connection(True) as c:
            c.execute("""INSERT INTO team_runs
              (id,project_id,actor_id,kind,client_id,status,input_seq,config_json,request_json,created_at)
              VALUES(?,?,1,'chat',?,?,0,?,?,?)""",
              (runid,self.p,runid,status,dump(cfg),dump({"task_id":self.t,"prompt":"研究上面方案"}),now()))
        return runid
    def document(self,title="经审核成果",adopted=True,task=None,seq=None):
        with self.s.connection(True) as c:
            did=self.s.put_object(c,self.p,"document",title,"结论：根据两人讨论决定方案 A",
                    1,data={"task_id":task or self.t,"adopted":adopted,"document_kind":"summary",
                            "source_seq":seq},status="ready")
        return did
    def _ids(self,g,kind):
        return [n for n in g["nodes"] if n["type"]==kind]

    def test_two_humans_and_source_document_are_scoped_and_traceable(self):
        source=self.message("用户甲提交对照资料，要求保留来源哈希",1)
        peer=self.message("设计师乙确认以方案 A 为候选，尚未发布知识",2)
        document=self.document(seq=source["seq"])
        g=self.graph(actor=self.b)
        self.assertEqual(g["source_authority"],"stored_rows_not_model_inference")
        self.assertEqual(g["counts"]["messages"],2)
        self.assertEqual(len(self._ids(g,"document")),1)
        self.assertEqual(self._ids(g,"document")[0]["source_state"],"project_adopted")
        self.assertTrue(any(e["relation"]=="document_derived_from_message" for e in g["edges"]))
        self.assertEqual({x["speaker"] for x in self._ids(g,"message")},{"研究员甲","设计师乙"})
        self.assertEqual(g["partial"],False)
        self.assertNotIn("用户甲提交对照资料",json.dumps(g,ensure_ascii=False))
        self.assertEqual(self._ids(g,"message")[0]["content_sha256"],hashlib.sha256(
                         peer["content"].encode()).hexdigest())

    def test_uploaded_file_and_tool_trace_are_connected_without_raw_payload(self):
        source=self.message("提供原始输入PDF，并授权分析，不代表已经验收。")
        docid=self.document(title="原始项目文件",adopted=False,seq=source["seq"])
        with self.s.connection(True) as c:
            c.execute("""INSERT INTO team_uploads(id,project_id,document_id,uploader_id,origin,source_seq,filename,created_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("upload_ledger_1",self.p,docid,1,"discussion",source["seq"],"市场数据_原始.pdf",now()))
        rid=self.fake_run()
        self.message("模型声称已经分析原件",0,"assistant",runid=rid)
        RunTrace(self.s,rid).emit("tool","tool.request",{"name":"project_file_read","arguments":{"document_id":docid}})
        RunTrace(self.s,rid).emit("tool","tool.result",{"name":"project_file_read","content":"SECRET_TOOL_PAYLOAD"})
        graph=self.graph()
        self.assertEqual(graph["counts"]["uploads"],1)
        self.assertEqual(len(self._ids(graph,"source_upload")),1)
        self.assertEqual(graph["counts"]["tool_events"],2)
        self.assertEqual(len(self._ids(graph,"tool_event")),2)
        rels={x["relation"] for x in graph["edges"]}
        self.assertIn("uploaded_from_message",rels)
        self.assertIn("source_file_for_document",rels)
        self.assertIn("run_contains_tool_event",rels)
        self.assertNotIn("SECRET_TOOL_PAYLOAD",json.dumps(graph,ensure_ascii=False))
        self.assertFalse(graph["source_sensitivity_classification_enabled"])

    def test_tool_history_truncation_advertised_and_never_claimed_complete(self):
        rid=self.fake_run()
        run=RunTrace(self.s,rid)
        for i in range(42):
            run.emit("tool","tool.result",{"name":"project_file_read","content":str(i)})
        graph=self.graph()
        self.assertEqual(graph["counts"]["tool_events"],42)
        self.assertTrue(graph["partial"])
        self.assertIn("tool_events",graph["partial_categories"])
        self.assertEqual(len(self._ids(graph,"tool_event")),36)

    def test_model_says_finished_is_not_accepted_or_published(self):
        rid=self.fake_run()
        self.message("研究报告已经完成，我保证没有问题！",0,"assistant",runid=rid)
        g=self.graph()
        self.assertEqual(len(self._ids(g,"run")),1)
        self.assertEqual(self._ids(g,"run")[0]["source_state"],"execution_record_not_adoption")
        self.assertEqual(self._ids(g,"document"),[])
        self.assertEqual(self._ids(g,"published_knowledge"),[])
        self.assertFalse(any(n.get("source_state") in ("human_accepted_step","explicitly_published_snapshot")
                             for n in g["nodes"]))
        self.assertTrue(any(e["relation"]=="produced_message" for e in g["edges"]))

    def test_explicit_published_snapshot_retracts_without_deleting_original(self):
        src=self.message("请采用经确认的版本作为团队知识",1)
        doc=self.document(seq=src["seq"])
        # Company publication is already an owner-only, adopted-only operation.
        result=self.s.publish_document(self.w,doc,1,1)
        before=self.graph()
        self.assertEqual(before["counts"]["publications"],1)
        pub=self._ids(before,"published_knowledge")
        self.assertEqual(pub[0]["source_state"],"explicitly_published_snapshot")
        self.assertEqual(pub[0]["source_document_id"],doc)
        self.assertTrue(any(e["relation"]=="explicit_company_publication" for e in before["edges"]))
        self.assertEqual(len(self._ids(before,"document")),1)
        self.s.withdraw_knowledge(self.w,result["id"],1)
        after=self.graph()
        self.assertEqual(self._ids(after,"published_knowledge"),[])
        self.assertEqual(len(self._ids(after,"document")),1)
        self.assertEqual(after["counts"]["publications"],0)

    def test_non_adopted_candidate_never_becomes_published_knowledge(self):
        doc=self.document(adopted=False)
        with self.assertRaises(Problem) as err:self.s.publish_document(self.w,doc,1,1)
        self.assertEqual(err.exception.status,422)
        g=self.graph()
        self.assertEqual(self._ids(g,"document")[0]["source_state"],"not_adopted")
        self.assertEqual(self._ids(g,"published_knowledge"),[])

    def test_sibling_task_and_cross_project_do_not_leak(self):
        self.message("SECRET_ALTAIR",task=self.t2)
        other=self.s.create_task(self.p2,1,{"title":"外部团队的任务"})["id"]
        self.message("SECRET_PROCYON",p=self.p2,task=other)
        self.document(title="other",task=self.t2)
        self.message("only this task content")
        g=self.graph(actor=self.b)
        self.assertEqual(g["counts"]["messages"],1)
        self.assertEqual(g["counts"]["documents"],0)
        self.assertFalse(any("SECRET" in json.dumps(n) for n in g["nodes"]))
        with self.assertRaises(Problem):
            self.graph(actor=self.b,task=other)
        with self.assertRaises(Problem):
            self.graph(actor=self.c)

    def test_revoked_team_member_fails_closed(self):
        self.message("read allowed while a member",actor=2)
        self.assertEqual(self.graph(actor=self.b)["counts"]["messages"],1)
        self.s.remove_member(self.p,1,2)
        with self.assertRaises(Problem):self.graph(actor=self.b)

    def test_large_task_marks_partial_not_complete(self):
        for i in range(94):self.message("long history "+str(i))
        g=self.graph()
        self.assertTrue(g["partial"])
        self.assertIn("messages",g["partial_categories"])
        self.assertEqual(g["counts"]["messages"],94)
        self.assertEqual(len(self._ids(g,"message")),90)
        self.assertLess(len(g["nodes"]),180)

    def test_traces_only_real_approved_workflow_records(self):
        rid=self.fake_run()
        self.message("模型输出了可复核内容；不是组织发布结果。",0,"assistant",rid)
        with self.s.connection(True) as c:
            stamp=now()
            c.execute("""INSERT INTO team_task_workflow_plans
                (id,project_id,task_id,title,description,input_hash,status,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,1,?,?)""",
                ("wf_1",self.p,self.t,"科研到验收","一步验收","hash","active",stamp,stamp))
            c.execute("""INSERT INTO team_task_workflow_steps
                (id,plan_id,project_id,task_id,ordinal,kind,title,instruction,agent_id,
                 agent_revision,status,run_id,approved_by,approved_at,review_note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("ws_1","wf_1",self.p,self.t,0,"agent","研究核验","依据来源核查",
                 self.agent["id"],1,"accepted",rid,1,stamp,"人工检查来源与实际模型结果",stamp,stamp))
        g=self.graph()
        step=self._ids(g,"review_step")[0]
        self.assertTrue(step["approval_recorded"])
        self.assertEqual(step["source_state"],"human_accepted_step")
        self.assertIsNotNone(step["review_note_sha256"])
        self.assertEqual(self._ids(g,"published_knowledge"),[])
        self.assertTrue(any(e["relation"]=="run_reviewed_in_step" for e in g["edges"]))
        self.assertNotIn("人工检查来源与实际模型结果",json.dumps(g,ensure_ascii=False))

if __name__=="__main__":
    unittest.main()
