"""M1: source-linked task summary, cursor, ACL, deterministic invalidation. No model."""
import json,secrets,unittest
from types import SimpleNamespace as NS
import test_platform_v4 as base
from teamspace.task_memory import snapshot,read_snapshot,source_hash
from teamspace.store import Problem,dump,now
from teamspace.agent_controller import AgentController

class TaskMemoryTests(unittest.TestCase):
 def setUp(self):
  base.PlatformTests.setUp(self)
  self.task=self.s.create_task(self.p,1,{'title':'共知长会话测试'})
  self.other_task=self.s.create_task(self.p,1,{'title':'另一个任务'})
  self.config=base.PlatformTests.cfg(self)
  self.config.update(_project_id=self.p,_actor_id=1,_run_id='r_mem1',conversation_task_id=self.task['id'])
  self.config['agent_snapshot']['name']='研究分析师'
 def tearDown(self):base.PlatformTests.tearDown(self)
 def message(self,text,actor=1,kind='human',task=None,project=None):
  with self.s.connection(True) as c:
   return self.s.add_message(c,project or self.p,actor,'甲' if actor==1 else '乙' if actor==2 else '研究分析师',text,
                             secrets.token_hex(6),kind,meta={'task_id':task or self.task['id']})
 def seed(self,count=110):
  first=self.message('我们确认使用方案 A；它是方案而不是已执行，不能自动提交。')
  decision=self.message('必须保留之前的消息来源与原件版本，禁止跨项目读取。',actor=2)
  proposal=self.message('研究分析师表示：报告已完成，但尚无可核验的工具回执。',actor=0,kind='assistant')
  for i in range(count-3):last=self.message('历史讨论 '+str(i)+'：我们在评估版本与成本。',actor=1 if i%2 else 2)
  return first,decision,proposal,last
 def test_long_history_persists_summary_and_cache_reuses_exact_cursor(self):
  first,decision,ai,last=self.seed(130)
  s=snapshot(self.s,self.p,self.task['id'],1,last['seq']-8)
  self.assertFalse(s['reused'])
  self.assertEqual(s['through_seq'],last['seq']-8)
  self.assertIn('确认使用方案 A',s['summary_md'])
  self.assertIn('必须保留',s['summary_md'])
  self.assertIn('乙',s['summary_md'])
  self.assertLessEqual(len(s['summary_md']),3500)
  self.assertNotIn('模型已成功生成报告',s['summary_md'])
  again=snapshot(self.s,self.p,self.task['id'],1,last['seq']-8)
  self.assertEqual(again['revision'],s['revision']);self.assertTrue(again['reused'])
  self.assertEqual(again['source_hash'],s['source_hash'])
  visible=read_snapshot(self.s,self.p,self.task['id'],2)
  self.assertEqual(visible['status'],'ready')
  self.assertIn(first['seq'],[r['seq'] for r in visible['source_refs']])
 def test_incremental_cursor_update_preserves_old_decisions_without_rewriting_source(self):
  self.seed(35)
  first=snapshot(self.s,self.p,self.task['id'],1,25)
  self.assertEqual(first['update_strategy'],'full_rebuild_or_changed_history')
  for i in range(18):
   self.message('新增第 '+str(i)+' 条。每一个阶段的已确认方案需要有出处。',actor=1 if i%2 else 2)
  advanced=snapshot(self.s,self.p,self.task['id'],1,48)
  self.assertEqual(advanced['update_strategy'],'incremental_verified_cursor')
  self.assertGreater(advanced['revision'],first['revision'])
  self.assertIn('方案 A',advanced['summary_md'])
  self.assertIn('新增第',advanced['summary_md'])
  self.assertTrue(snapshot(self.s,self.p,self.task['id'],1,48)['reused'])
  with self.s.connection(True) as c:
   c.execute("UPDATE team_messages SET content='之前的方案已撤回' WHERE project_id=? AND seq=1",(self.p,))
  rebuilt=snapshot(self.s,self.p,self.task['id'],1,48)
  self.assertEqual(rebuilt['update_strategy'],'full_rebuild_or_changed_history')
  self.assertNotEqual(rebuilt['source_hash'],advanced['source_hash'])
 def test_changed_older_message_invalidates_old_snapshot_even_same_length(self):
  self.seed(40);s=snapshot(self.s,self.p,self.task['id'],1,30)
  self.assertEqual(read_snapshot(self.s,self.p,self.task['id'],1)['status'],'ready')
  with self.s.connection(True) as c:
   r=c.execute("SELECT id,content FROM team_messages WHERE project_id=? AND seq=1",(self.p,)).fetchone()
   c.execute("UPDATE team_messages SET content=? WHERE id=?",('X'*len(r['content']),r['id']))
  self.assertEqual(read_snapshot(self.s,self.p,self.task['id'],1)['status'],'stale')
  repaired=snapshot(self.s,self.p,self.task['id'],1,30)
  self.assertGreater(repaired['revision'],s['revision'])
  self.assertNotEqual(repaired['source_hash'],s['source_hash'])
 def test_deleted_message_and_task_scope_recheck(self):
  self.seed(35);snapshot(self.s,self.p,self.task['id'],1,25)
  with self.s.connection(True) as c:c.execute("DELETE FROM team_messages WHERE project_id=? AND seq=2",(self.p,))
  self.assertEqual(read_snapshot(self.s,self.p,self.task['id'],1)['status'],'stale')
  with self.assertRaises(Problem):read_snapshot(self.s,self.p,self.other_task['id'],3)
  self.s.remove_member(self.p,1,2)
  with self.assertRaises(Problem):snapshot(self.s,self.p,self.task['id'],2,25)
  with self.assertRaises(Problem):read_snapshot(self.s,self.p,self.task['id'],2)
 def test_different_task_and_project_are_not_included(self):
  self.seed(50)
  self.message('OTHER_TASK_SECRET_SATURN',task=self.other_task['id'])
  self.message('OTHER_PROJECT_SECRET_NEPTUNE',project=self.p2,task=self.s.create_task(self.p2,1,{'title':'foreign'})['id'])
  s=snapshot(self.s,self.p,self.task['id'],1,45)
  self.assertNotIn('OTHER_TASK_SECRET_SATURN',s['summary_md'])
  self.assertNotIn('OTHER_PROJECT_SECRET_NEPTUNE',s['summary_md'])
  with self.assertRaises(Problem):snapshot(self.s,self.p,self.task['id'],3,45)
 def test_latest_question_still_primary_after_130_messages(self):
  self.seed(125)
  recent=self.message('你是谁？')
  cfg=self.config.copy()
  row=self.insert_run(recent['seq'],cfg,'@研究分析师 你是谁？','r_identity')
  ctr=AgentController(NS(),self.s)
  messages,_,meta=ctr.context(row)
  self.assertIn('本次请求：你是谁？',messages[-1]['content'])
  self.assertNotIn('已经确认使用方案 A',messages[-1]['content'])
  self.assertFalse(meta['conversation'].get('history_snapshot'))
  # When explicitly resuming, old source-linked summary is available.
  with self.s.connection(True) as c:c.execute("UPDATE team_runs SET status='completed' WHERE id='r_identity'")
  current=self.message('按上面的方案 A 继续，先核对已经完成的步骤。')
  row=self.insert_run(current['seq'],cfg,'@研究分析师 按上面的方案 A 继续，先核对已经完成的步骤。','r_resume')
  messages,_,meta=ctr.context(row)
  self.assertTrue(meta['conversation'].get('history_snapshot'))
  self.assertIn('历史任务讨论摘录',messages[0]['content'])
  self.assertIn('本次请求：按上面的方案 A 继续',messages[-1]['content'])
  self.assertLess(sum(len(m['content']) for m in messages),22000)
 def insert_run(self,seq,cfg,prompt,rid):
  cfg=dict(cfg,_run_id=rid)
  with self.s.connection(True) as c:
   c.execute("INSERT INTO team_runs(id,project_id,actor_id,kind,client_id,status,input_seq,config_json,request_json,created_at) VALUES(?,?,1,'chat',?,'running',?,?,?,?)",
             (rid,self.p,rid,seq,dump(cfg),dump({'task_id':self.task['id'],'prompt':prompt}),now()))
   return dict(c.execute('SELECT * FROM team_runs WHERE id=?',(rid,)).fetchone())
if __name__=='__main__':unittest.main()
