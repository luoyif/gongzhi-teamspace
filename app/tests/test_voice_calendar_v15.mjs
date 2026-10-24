import test from 'node:test';
import assert from 'node:assert/strict';
import {pcm16WavFromChannels,insertDictation} from '../web/voice-input.mjs';
import {scheduleAt,entriesOnDay,agendaFrom,eventDay,dateKeyInZone} from '../web/calendar-ui.mjs';

test('audio 48kHz to 16kHz mono signed PCM WAV with correct RIFF header',async()=>{
 const samples=Float32Array.from({length:48000},(_,i)=>Math.sin(i*2*Math.PI*250/48000));
 const audio=pcm16WavFromChannels([samples],48000);
 const bytes=await audio.arrayBuffer(),view=new DataView(bytes);
 assert.equal(audio.type,'audio/wav');assert.equal(bytes.byteLength,44+16000*2);
 assert.equal(String.fromCharCode(...new Uint8Array(bytes.slice(0,4))),'RIFF');
 assert.equal(view.getUint32(24,true),16000);assert.equal(view.getUint16(22,true),1);
 assert.equal(view.getUint16(34,true),16);assert.ok(view.getInt16(44+2*20,true)!==0);
});
test('short or inconsistent audio cannot be silently sent',()=>{
 assert.throws(()=>pcm16WavFromChannels([new Float32Array(100)],48000));
 assert.throws(()=>pcm16WavFromChannels([new Float32Array(16000),new Float32Array(10)],16000));
});
test('dictation edits draft and dispatches input without click or submit',()=>{
 let changes=0;
 const textarea={value:'前面内容',selectionStart:4,selectionEnd:4,maxLength:100,
  setRangeText(text,start,end){this.value=this.value.slice(0,start)+text+this.value.slice(end);this.selectionStart=start+text.length;this.selectionEnd=this.selectionStart;},
  dispatchEvent(e){if(e.type==='input')changes++;}
 };
 assert.equal(insertDictation(textarea,'语音转写内容'),true);
 assert.equal(textarea.value,'前面内容\n语音转写内容');
 assert.equal(changes,1);
 assert.throws(()=>insertDictation({...textarea,maxLength:3},'more'));
});
const task=(status,due)=>({kind:'task',title:'测试',status,due_date:due,starts_at:due});
test('doing tasks stay lit each date from today through due only',()=>{
 const today='2026-10-24',item=task('doing','2026-10-27');
 assert.equal(scheduleAt(item,'2026-10-23',today),null);
 assert.equal(scheduleAt(item,today,today).style,'ongoing');
 assert.equal(scheduleAt(item,'2026-10-26',today).style,'ongoing');
 assert.equal(scheduleAt(item,'2026-10-27',today).style,'deadline');
 assert.equal(scheduleAt(item,'2026-10-28',today),null);
});
test('overdue does not highlight days beyond due; done and todo not ongoing',()=>{
 const today='2026-10-24',late=task('doing','2026-10-22');
 assert.equal(scheduleAt(late,'2026-10-22',today).style,'overdue');
 assert.equal(scheduleAt(late,'2026-10-23',today),null);
 assert.equal(scheduleAt(late,today,today),null);
 assert.equal(scheduleAt(task('done','2026-10-29'),'2026-10-29',today).style,'completed');
 assert.equal(scheduleAt(task('todo','2026-10-29'),'2026-10-28',today),null);
 assert.equal(scheduleAt(task('paused','2026-10-29'),'2026-10-29',today),null);
 assert.equal(scheduleAt(task('review','2026-10-29'),'2026-10-29',today).style,'review');
});
test('meeting spans start to end inclusive in project timezone',()=>{
 const meeting={kind:'meeting',title:'会议',status:'active',
  starts_at:'2026-10-23T15:00:00Z',ends_at:'2026-10-25T04:00:00Z'};
 assert.equal(eventDay(meeting.starts_at,'Asia/Shanghai'),'2026-10-23');
 assert.equal(scheduleAt(meeting,'2026-10-24','2026-10-24','Asia/Shanghai').style,'event');
 assert.equal(scheduleAt(meeting,'2026-10-26','2026-10-24','Asia/Shanghai'),null);
});
test('calendar agenda separates overdue from scheduled work',()=>{
 const items=[task('doing','2026-10-22'),task('doing','2026-10-28'),task('done','2026-10-29')];
 const day='2026-10-24';
 const a=agendaFrom(items,day);
 assert.equal(a.overdue.length,1);assert.equal(a.future.length,1);
 const shown=entriesOnDay(items,'2026-10-25',day);
 assert.equal(shown.filter(x=>x.style==='ongoing').length,1);
});
test('timezone-specific today supports China and international teams',()=>{
 const d=new Date('2026-10-24T16:30:00Z');
 assert.equal(dateKeyInZone(d,'Asia/Shanghai'),'2026-10-25');
 assert.equal(dateKeyInZone(d,'America/Los_Angeles'),'2026-10-24');
});
