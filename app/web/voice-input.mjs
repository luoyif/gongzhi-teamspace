/** Speech stays in the input draft; recording is never submitted as a chat message. */
export function pcm16WavFromChannels(channels,sampleRate,targetRate=16000){
 if(!Array.isArray(channels)||!channels.length||!Number.isFinite(sampleRate)||sampleRate<8000||sampleRate>192000)throw Error('音频采样率无效');
 const length=channels[0].length;
 if(!length||channels.some(c=>c.length!==length))throw Error('录音采样数据不完整');
 const size=Math.ceil(length*targetRate/sampleRate);
 if(size<targetRate/4||size>targetRate*121)throw Error('录音需在0.25秒至120秒之间');
 const bytes=new ArrayBuffer(44+size*2),v=new DataView(bytes);
 const label=(pos,text)=>{for(let i=0;i<text.length;i++)v.setUint8(pos+i,text.charCodeAt(i));};
 label(0,'RIFF');v.setUint32(4,36+size*2,true);label(8,'WAVE');label(12,'fmt ');
 v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
 v.setUint32(24,targetRate,true);v.setUint32(28,targetRate*2,true);
 v.setUint16(32,2,true);v.setUint16(34,16,true);label(36,'data');v.setUint32(40,size*2,true);
 const ratio=sampleRate/targetRate;
 for(let i=0;i<size;i++){
  const src=Math.min(length-1,i*ratio),lo=Math.floor(src),hi=Math.min(length-1,lo+1),mix=src-lo;
  let val=0;
  for(const c of channels)val+=((c[lo]||0)*(1-mix)+(c[hi]||0)*mix)/channels.length;
  val=Math.max(-1,Math.min(1,val));
  v.setInt16(44+i*2,val<0?Math.round(val*32768):Math.round(val*32767),true);
 }
 return new Blob([bytes],{type:'audio/wav'});
}
export async function decodeRecordedWav(blob,AudioContextClass=globalThis.AudioContext||globalThis.webkitAudioContext){
 if(!AudioContextClass)throw Error('浏览器不支持音频转换');
 const ctx=new AudioContextClass();
 try{
  const audio=await ctx.decodeAudioData(await blob.arrayBuffer());
  return pcm16WavFromChannels([...Array(audio.numberOfChannels)].map((_,i)=>audio.getChannelData(i)),audio.sampleRate);
 }finally{await ctx.close();}
}
export function insertDictation(textarea,text){
 if(!textarea||typeof textarea.value!=='string'||typeof text!=='string'||!text.trim())return false;
 const start=Number.isInteger(textarea.selectionStart)?textarea.selectionStart:textarea.value.length;
 const end=Number.isInteger(textarea.selectionEnd)?textarea.selectionEnd:start;
 const before=textarea.value.slice(0,start),after=textarea.value.slice(end);
 const sep=before&&!/[\s\n]$/.test(before)?'\n':'';
 const value=sep+text.trim();
 if((textarea.maxLength||-1)>0&&before.length+value.length+after.length>textarea.maxLength)throw Error('识别文字超出输入框长度限制，未修改已有内容');
 if(typeof textarea.setRangeText==='function')textarea.setRangeText(value,start,end,'end');
 else textarea.value=before+value+after;
 textarea.dispatchEvent(new Event('input',{bubbles:true}));
 return true;
}
