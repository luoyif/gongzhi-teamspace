"""Bounded, task-scoped ephemeral fanout; no text or login tokens are persisted."""
import asyncio,json,unittest
from teamspace.task_live import ROOMS,publish,online_ids,event

class LiveSignalTests(unittest.TestCase):
 def tearDown(self):ROOMS.clear()
 def test_deduplicates_online_member_with_multiple_tabs(self):
  q1,q2,q3=(asyncio.Queue() for _ in range(3))
  ROOMS['t1']={'a':(2,q1),'b':(2,q2),'c':(1,q3)}
  self.assertEqual(online_ids('t1'),[1,2])
  self.assertEqual(online_ids('t-other'),[])
 def test_message_only_notifies_exact_task_without_body(self):
  mine,foreign=asyncio.Queue(),asyncio.Queue()
  ROOMS['my-task']={'a':(1,mine)};ROOMS['other-task']={'b':(2,foreign)}
  publish('my-task','message',{'seq':10})
  self.assertEqual(mine.get_nowait(),{'type':'message','seq':10})
  self.assertTrue(foreign.empty())
 def test_queue_overflow_drops_old_signal_not_new_authoritative_notification(self):
  q=asyncio.Queue(maxsize=2);ROOMS['t']={'a':(1,q)}
  for n in range(6):publish('t','message',{'seq':n})
  self.assertEqual([q.get_nowait()['seq'] for _ in range(2)],[4,5])
 def test_event_is_standard_sse_with_no_hidden_credential_or_text(self):
  frame=event('typing',{'user_id':7,'active':True,'expires_ms':4200})
  self.assertIn('event: typing\n',frame)
  self.assertEqual(json.loads(frame.split('data: ')[1].strip())['user_id'],7)
  self.assertNotIn('Bearer',frame)
if __name__=='__main__':unittest.main()
