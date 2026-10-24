import {decodeRecordedWav,insertDictation} from './voice-input.mjs';

/** One microphone session at a time; never sends a chat message automatically. */
let active=null;
function micGlyph(state='idle'){
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
 svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','21');svg.setAttribute('height','21');
 svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');
 svg.setAttribute('stroke-width','1.8');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');
 svg.setAttribute('aria-hidden','true');
 if(state==='recording'){
  const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
  for(const [k,v] of Object.entries({x:'7',y:'7',width:'10',height:'10',rx:'2',fill:'currentColor',stroke:'none'}))rect.setAttribute(k,v);
  svg.append(rect);
 }else if(state==='busy'){
  const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');
  for(const [k,v] of Object.entries({cx:'12',cy:'12',r:'8','stroke-dasharray':'30 18'}))circle.setAttribute(k,v);
  svg.append(circle);
 }else{
  const shapes=[['rect',{x:'9',y:'2',width:'6',height:'12',rx:'3'}],['path',{d:'M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8'}]];
  for(const [tag,attrs] of shapes){
   const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
   for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);
   svg.append(node);
  }
 }
 return svg;
}
function showMic(button,state='idle'){button.replaceChildren(micGlyph(state));}


function supportedMime(){
 if(typeof MediaRecorder==='undefined')return '';
 for(const type of ['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus','audio/webm'])
  if(MediaRecorder.isTypeSupported(type))return type;
 return '';
}
function clean(session){
 clearTimeout(session.limitTimer);
 session.stream?.getTracks().forEach(t=>t.stop());
 session.button.disabled=false;
 session.button.classList.remove('recording','recognizing');
 showMic(session.button);
 session.button.setAttribute('aria-label','语音输入');
 session.button.title='点击录音；再点一次结束，识别文字填入输入框（不发送）';
 session.cancel.hidden=true;
 session.status.textContent='';
 if(active===session)active=null;
}
function errorText(response,body){
 if(response.status===429)return '识别服务繁忙，请稍后再试';
 if(response.status===401)return '当前登录已失效，请重新登录';
 const text=body?.detail;
 return typeof text==='string'&&text.length<200?text:'语音识别失败，请重试';
}
export function attachSpeechInput(textarea,host,{getToken,notify=()=>{},compact=false}={}){
 if(!textarea||textarea.dataset.voiceMounted)return;
 textarea.dataset.voiceMounted='1';
 const row=document.createElement('span');row.className='voice-input-controls'+(compact?' compact':'');
 const button=document.createElement('button');button.type='button';button.className='voice-mic-button';
 showMic(button);button.setAttribute('aria-label','语音输入');
 button.title='点击录音；再点一次结束，识别文字填入输入框（不发送）';
 const cancel=document.createElement('button');cancel.type='button';cancel.className='voice-cancel-btn';cancel.textContent='取消';cancel.hidden=true;
 const status=document.createElement('span');status.className='voice-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 row.append(button,cancel,status);host.append(row);
 const end=discard=>{
  const s=active;if(!s||s.button!==button)return;
  s.discard=!!discard;
  if(s.controller&&discard)s.controller.abort();
  if(s.recorder?.state==='recording')s.recorder.stop();
  if(!s.recorder||s.recorder.state==='inactive'){
   s.stream?.getTracks().forEach(t=>t.stop());
   if(discard&&active===s)clean(s);
  }
 };
 cancel.addEventListener('click',()=>end(true));
 button.addEventListener('click',async()=>{
  if(active){
   if(active.button===button&&active.recorder?.state==='recording'){end(false);return;}
   notify('请先结束当前录音');return;
  }
  if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==='undefined'){
   notify('当前浏览器不支持录音；请在 HTTPS 页面使用 Chrome、Edge 或 Safari');return;
  }
  if(textarea.disabled||!textarea.isConnected){notify('当前输入框不可用');return;}
  const session={button,cancel,status,stream:null,recorder:null,controller:null,discard:false,chunks:[],limitTimer:null};
  active=session;button.classList.add('recording');showMic(button,'busy');button.setAttribute('aria-label','正在申请麦克风权限');status.textContent='正在申请麦克风…';cancel.hidden=false;
  try{
   session.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
   if(active!==session){session.stream.getTracks().forEach(t=>t.stop());return;}
   const type=supportedMime(),recorder=type?new MediaRecorder(session.stream,{mimeType:type}):new MediaRecorder(session.stream);
   session.recorder=recorder;session.chunks=[];
   recorder.ondataavailable=e=>{if(e.data?.size)session.chunks.push(e.data);};
   recorder.onerror=()=>{notify('录音出现错误');session.discard=true;if(recorder.state==='recording')recorder.stop();};
   recorder.onstop=async()=>{
    session.stream?.getTracks().forEach(t=>t.stop());
    if(session.discard||active!==session||!textarea.isConnected){clean(session);return;}
    button.classList.remove('recording');button.classList.add('recognizing');showMic(button,'busy');button.setAttribute('aria-label','正在识别语音');status.textContent='正在转写（不会发送）…';
    const audio=new Blob(session.chunks,{type:recorder.mimeType||'audio/webm'});
    session.chunks.length=0;
    try{
     if(!audio.size)throw Error('没有录到声音');
     const wav=await decodeRecordedWav(audio);
     if(wav.size>8*1024*1024)throw Error('音频过大，请缩短录音');
     const form=new FormData();form.append('file',wav,'dictation.wav');
     const ctl=new AbortController();session.controller=ctl;
     const response=await fetch('/api/team/asr/transcriptions',{method:'POST',headers:{Authorization:'Bearer '+(getToken?.()||'')},body:form,signal:ctl.signal});
     let data;try{data=await response.json();}catch{data=null;}
     if(!response.ok)throw Error(errorText(response,data));
     if(!data?.text?.trim())throw Error('没有识别到清晰语音，请重新录制');
     if(!textarea.isConnected)return;
     if(!insertDictation(textarea,data.text))throw Error('识别结果无法填入输入框');
     textarea.focus();notify('语音已转为文字，请检查后自行发送');
    }catch(err){if(err.name!=='AbortError')notify(err.message||'语音识别失败');}
    finally{clean(session);}
   };
   recorder.start(600);
   button.classList.add('recording');showMic(button,'recording');button.setAttribute('aria-label','结束录音并识别');status.textContent='录音中 · 再点一次结束';
   session.limitTimer=setTimeout(()=>end(false),120000);
  }catch(err){
   if(active===session){notify(err.name==='NotAllowedError'?'需要允许浏览器访问麦克风':(err.message||'无法开启麦克风'));clean(session);}
  }
 });
 return row;
}
