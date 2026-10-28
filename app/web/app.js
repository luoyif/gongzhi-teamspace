import {evidenceGraphProjection,EVIDENCE_TYPE_LABELS} from './knowledge-flow-layout.mjs';
import {attachSpeechInput} from './voice-ui.mjs';
import {dateKeyInZone,entriesOnDay,agendaFrom} from './calendar-ui.mjs';
import {PRESET_AVATARS,messageSide,avatarNode,updateAvatar} from './persona-ui.mjs';
import {terminalRun,toolLabel,summarizeActivity,mergeActivity,compactToolDetail} from './run-activity-ui.mjs';
import {nextMentionIndex, SSEFrames, traceOverview} from './agent-ui-utils.mjs';
const API = '/api/team';
const $ = (s, root = document) => root.querySelector(s);
const app = $('#app');
const notifyRoot = $('#notifications');
const SESSION = 'teamspace.access_token';
const state = {
  token: sessionStorage.getItem(SESSION), user: null, projects: [], project: null,
  tab: 'discussion', messages: [], lastSeq: 0, running: null, members: [], tasks: [],
  calendar: [], documents: [], proposals: [], runs: [], settings: null,
  controller: null, generation: 0, polling: false, timer: null, draft: '',
  messageClient: crypto.randomUUID(), runClient: crypto.randomUUID(), pendingRunPayload: null, search: '',
  month: new Date(new Date().getFullYear(), new Date().getMonth(), 1), online: true
};
const labels = {
  todo: '待办', doing: '进行中', review: '待验收', done: '已完成', paused: '已暂停', cancelled: '已取消',
  human: '人工', ai: 'AI', collab: '人机协作', owner: '管理员', member: '成员', viewer: '只读',
  file: '文件', note: '知识', summary: '纪要', decision: '决定', result: '验收成果',
  uploaded: '待解析', parsing: '解析中', ready: '可检索', unindexed: '仅存原件', failed: '失败',
  queued: '排队中', running: '运行中', completed: '已完成', interrupted: '已中断',
  chat: '对话', task: '任务执行', pending: '待确认', adopted: '已采用', dismissed: '已忽略',
  meeting: '会议', milestone: '里程碑', active: '有效', superseded: '已有新版本'
};
const iconPaths = {
  chat: 'M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5Z',
  tasks: 'M9 5h11M9 12h11M9 19h11M3 5l1 1 2-2M3 12l1 1 2-2M3 19l1 1 2-2',
  calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z',
  files: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6M8 13h8M8 17h5',
  plus: 'M12 5v14M5 12h14', close: 'M6 6l12 12M18 6 6 18',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2',
  plan: 'M4 4h16v16H4ZM8 8h8M8 12h8M8 16h5',
  arrow: 'M12 19V5M5 12l7-7 7 7', clip: 'm21 11-8 8a6 6 0 0 1-8-8l9-9a4 4 0 0 1 6 6l-9 9a2 2 0 0 1-3-3l8-8',
  spark: 'm12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3ZM20 2v4M18 4h4',
  search: 'M21 21l-5-5M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14',
  chevron: 'm9 5 7 7-7 7', back: 'm15 5-7 7 7 7',
  download: 'M12 3v12M6 9l6 6 6-6M4 17v4h16v-4',
  upload: 'M12 16V4M6 10l6-6 6 6M4 17v4h16v-4',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8M17 4a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.9',
  moon: 'M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1',
  logout: 'M9 4H4v16h5M9 12h12M17 8l4 4-4 4',
  menu: 'M3 6h18M3 12h18M3 18h18', check: 'm5 12 4 4L19 6',
  edit: 'm15 4 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14Z',
  link: 'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',
  refresh: 'M20 7V3l-4 4M4 17v4l4-4M20 7A8 8 0 0 0 6 5M4 17a8 8 0 0 0 14 2',
  clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 6v6l4 2'
};
function el(tag, props = {}, ...children) {
  const n = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') n.className = value;
    else if (key.startsWith('on') && typeof value === 'function') n.addEventListener(key.slice(2), value);
    else if (key === 'value') n.value = value;
    else if (['disabled', 'checked', 'selected', 'required', 'multiple', 'open'].includes(key)) n[key] = !!value;
    else n.setAttribute(key, value === true ? '' : String(value));
  }
  children.flat(Infinity).forEach(c => {
    if (c == null || c === false) return;
    n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  });
  return n;
}
function icon(name, size = 17) {
  const n = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  Object.entries({viewBox:'0 0 24 24',width:size,height:size,fill:'none',stroke:'currentColor','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}).forEach(([k,v])=>n.setAttribute(k,String(v)));
  const p = document.createElementNS(n.namespaceURI, 'path');
  p.setAttribute('d', iconPaths[name] || iconPaths.files); n.append(p); return n;
}
function button(text, action, options = {}) {
  return el('button', {type:'button',class:'btn ' + (options.class || ''),onclick:action,disabled:options.disabled,title:options.title},options.icon && icon(options.icon),text);
}
function iconButton(name, label, action) {return el('button',{type:'button',class:'icon-btn',title:label,'aria-label':label,onclick:action},icon(name));}
function badge(value, style='') {return el('span',{class:'badge '+style},labels[value]||value);}
function avatar(name, ai=false) {return el('span',{class:'avatar'+(ai?' ai':''),'aria-hidden':'true'},ai?icon('spark',16):(name||'?').slice(0,1).toUpperCase());}
function stamp(value, options={}) {
  if (!value) return '—';
  try{return new Intl.DateTimeFormat('zh-CN',{timeZone:state.project?.timezone||'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,...options}).format(new Date(value));}
  catch{return String(value);}
}
function datePart(value) {
  if (!value) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  try{return new Intl.DateTimeFormat('sv-SE',{timeZone:state.project?.timezone||'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}catch{return value.slice(0,10);}
}
function canWrite(){return state.project?.role !== 'viewer';}
function isOwner(){return state.project?.role === 'owner';}
function projectPath(suffix=''){return '/projects/'+encodeURIComponent(state.project.id)+suffix;}
function memberName(id){return state.members.find(m=>Number(m.user_id)===Number(id))?.display_name || (id?'成员 #'+id:'未分配');}
function toast(text,error=false) {
  const n=el('div',{class:'toast'+(error?' error':''),role:error?'alert':'status'},icon(error?'close':'check',15),el('span',{class:'grow'},text),iconButton('close','关闭提示',()=>n.remove()));
  notifyRoot.append(n);setTimeout(()=>n.remove(),error?9000:4500);
}
function errorText(data) {
  const v=data?.detail??data?.error?.message??data?.message;
  if(Array.isArray(v))return v.map(x=>x.msg||String(x)).join('；');
  const code=data?.error?.code??data?.code;
  let text=typeof v==='string'?v:(code==='LOGIN_LOCKED'?'登录暂时锁定，请稍后再试':'请求未完成，请稍后重试');
  const detail=data?.error?.details??data?.details??{};
  const minutes=detail.remaining_minutes??data?.remaining_minutes??data?.error?.remaining_minutes;
  const seconds=detail.retry_after??detail.retry_after_seconds??data?.retry_after??data?.retry_after_seconds??data?.error?.retry_after;
  if(Number.isFinite(Number(minutes))&&minutes!=null)text+='（请在 '+Math.ceil(Number(minutes))+' 分钟后重试）';
  else if(Number.isFinite(Number(seconds))&&seconds!=null)text+='（请在 '+Math.max(1,Math.ceil(Number(seconds)/60))+' 分钟后重试）';
  return text;
}
async function api(path, {method='GET',body,signal,raw=false,team=true}={}) {
  const headers={};
  if(state.token)headers.Authorization='Bearer '+state.token;
  if(body != null && !(body instanceof FormData)){headers['Content-Type']='application/json';body=JSON.stringify(body);}
  let response;
  try{response=await fetch((team?API:'')+path,{method,headers,body,signal,cache:'no-store',credentials:'same-origin'});}
  catch(e){if(e.name==='AbortError')throw e;throw new Error('连接暂时中断，请检查服务是否运行后重试。');}
  if(!response.ok){
    let data;try{data=await response.json();}catch{data={detail:'请求失败（'+response.status+'）'};}
    const e=new Error(errorText(data));e.status=response.status;
    if(response.status===401 && state.user){logout(false);toast('登录已过期，请重新登录',true);}
    throw e;
  }
  const renewed=response.headers.get('X-Octop-Access-Token');
  if(renewed){state.token=renewed;sessionStorage.setItem(SESSION,renewed);}
  return raw?response:(response.status===204?{}:response.json());
}
function handle(e){if(e?.name!=='AbortError')toast(e.message||String(e),true);}
function safeHref(href) {
  try{const u=new URL(href,location.origin);return ['http:','https:','mailto:'].includes(u.protocol)?u.href:null;}catch{return null;}
}
function inline(text) {
  const frag=document.createDocumentFragment();
  const re=/(\x60[^\x60]+\x60|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let from=0,m;
  while((m=re.exec(text))){
    frag.append(document.createTextNode(text.slice(from,m.index)));
    const token=m[0];
    if(token[0]===String.fromCharCode(96))frag.append(el('code',{},token.slice(1,-1)));
    else if(token.startsWith('**'))frag.append(el('strong',{},token.slice(2,-2)));
    else{const parts=/^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);const url=safeHref(parts[2]);frag.append(url?el('a',{href:url,target:'_blank',rel:'noopener noreferrer'},parts[1]):document.createTextNode(parts[1]));}
    from=re.lastIndex;
  }
  frag.append(document.createTextNode(text.slice(from)));return frag;
}
function markdown(text) {
  const root=el('div',{class:'markdown'});
  const lines=String(text||'').replace(/\r/g,'').split('\n');let i=0;
  while(i<lines.length){
    const line=lines[i];
    if(line.startsWith(String.fromCharCode(96).repeat(3))){
      i++;const code=[];while(i<lines.length&&!lines[i].startsWith(String.fromCharCode(96).repeat(3)))code.push(lines[i++]);
      root.append(el('pre',{},el('code',{},code.join('\n'))));i++;continue;
    }
    if(!line.trim()){i++;continue;}
    const heading=/^(#{1,4})\s+(.+)$/.exec(line);
    if(heading){root.append(el('h'+heading[1].length,{},inline(heading[2])));i++;continue;}
    if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i+1])){
      const cells=value=>value.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
      const headings=cells(line),table=el('table',{},el('thead',{},el('tr',{},headings.map(x=>el('th',{},inline(x))))));
      const body=el('tbody');i+=2;
      while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){const row=cells(lines[i++]);body.append(el('tr',{},headings.map((_,j)=>el('td',{},inline(row[j]||'')))));}
      table.append(body);root.append(el('div',{class:'table-scroll'},table));continue;
    }
    if(/^---+$/.test(line.trim())){root.append(el('hr'));i++;continue;}
    if(/^>\s?/.test(line)){root.append(el('blockquote',{},inline(line.replace(/^>\s?/,''))));i++;continue;}
    if(/^([-*]\s|\d+\.\s)/.test(line)){
      const ordered=/^\d+\./.test(line),list=el(ordered?'ol':'ul');
      while(i<lines.length&&/^([-*]\s|\d+\.\s)/.test(lines[i]))list.append(el('li',{},inline(lines[i++].replace(/^([-*]\s|\d+\.\s)/,''))));
      root.append(list);continue;
    }
    const para=[line];i++;
    while(i<lines.length&&lines[i].trim()&&!/^(#{1,4}\s|[-*]\s|\d+\.\s|>\s?)/.test(lines[i])&&!lines[i].startsWith(String.fromCharCode(96).repeat(3)))para.push(lines[i++]);
    root.append(el('p',{},inline(para.join('\n'))));
  }
  return root;
}
function empty(title,description,iconName='files',action=null) {return el('div',{class:'empty'},el('div',{class:'empty-icon'},icon(iconName,23)),el('h2',{},title),el('p',{},description),action);}
function field(name,label,type='text',value='',options={}) {
  const id='field-'+crypto.randomUUID();
  let input;
  if(type==='textarea')input=el('textarea',{id,name,value,...options.attrs});
  else if(type==='select')input=el('select',{id,name,...options.attrs},...(options.choices||[]).map(([v,t])=>el('option',{value:v,selected:String(v)===String(value??'')},t)));
  else input=el('input',{id,name,type,value:value??'',...options.attrs});
  const wrapper=el('div',{class:'field'},el('label',{for:id},label),input,options.help&&el('div',{class:'help'},options.help));
  wrapper.control=input;return wrapper;
}
function values(form){return Object.fromEntries(new FormData(form).entries());}
function formError(form,error){$('.form-error',form)?.remove();if(error)form.append(el('div',{class:'form-error',role:'alert'},error.message||String(error)));}
function openDialog(title,content,{description='',wide=false,actions=[]}={}) {
  const previous=document.activeElement;
  const d=el('dialog',{class:'modal'+(wide?' wide':''),'aria-label':title});
  const body=el('div',{class:'modal-body'},content),footer=el('div',{class:'modal-footer'},actions);
  const close=()=>{d.close();d.remove();if(previous?.isConnected)previous.focus();};
  d.append(el('div',{class:'modal-shell'},el('div',{class:'modal-head'},el('div',{},el('h2',{},title),description&&el('p',{class:'modal-description'},description)),iconButton('close','关闭',close)),body,actions.length?footer:null));
  d.addEventListener('cancel',e=>{e.preventDefault();close();});
  d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}});
  document.body.append(d);d.showModal();
  return {dialog:d,body,footer,close};
}
function formDialog(title,fields,onSubmit,{description='',wide=false,submit='保存',extra=[]}={}) {
  const id='form-'+crypto.randomUUID(),form=el('form',{id},fields);
  const save=el('button',{type:'submit',form:id,class:'btn primary'},submit);
  const dlg=openDialog(title,form,{description,wide,actions:[...extra,button('取消',()=>dlg.close()),save]});
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(!form.reportValidity())return;
    save.disabled=true;formError(form,null);
    try{await onSubmit(values(form),form,dlg);dlg.close();}
    catch(err){if(err.name!=='AbortError')formError(form,err);}
    finally{save.disabled=false;}
  });
  return {...dlg,form,save};
}
function confirmAction(title,description,onConfirm,{label='确认',danger=false}={}) {
  const form=el('div',{},el('p',{class:'muted'},description));
  const b=button(label,async()=>{b.disabled=true;try{await onConfirm();d.close();}catch(e){handle(e);b.disabled=false;}},{class:danger?'danger':'primary'});
  const d=openDialog(title,form,{actions:[button('取消',()=>d.close()),b]});return d;
}
function setTheme(theme) {
  document.documentElement.dataset.theme=theme;localStorage.setItem('teamspace.theme',theme);
  document.querySelector('meta[name="theme-color"]').content=theme==='dark'?'#1c1e21':'#f7f6f3';
}
setTheme(localStorage.getItem('teamspace.theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
function toggleTheme(){setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');}
function brand(){return el('div',{class:'brand'},el('div',{class:'brand-mark','aria-hidden':'true'},'共'),el('div',{},el('div',{class:'brand-name'},'共知'),el('div',{class:'brand-caption'},'TEAM WORKSPACE')));}
function invitation(){return new URLSearchParams(location.search).get('invite');}
function storeSession(result) {
  state.token=result.access_token;sessionStorage.setItem(SESSION,state.token);state.user=result.user||null;
}
function logout(show=true) {
  state.controller?.abort();clearTimeout(state.timer);state.generation++;state.token=null;state.user=null;state.project=null;state.messages=[];state.draft='';
  sessionStorage.removeItem(SESSION);document.querySelectorAll('dialog').forEach(d=>d.remove());renderAuth(false);if(show)toast('已退出登录');
}
async function bootstrap() {
  try{
    if(state.token){
      const result=await api('/api/auth/me',{team:false});state.user=result.user||result;
      await loadProjects();
      const invite=invitation();
      if(invite)confirmAction('接受项目邀请','使用当前账号加入邀请对应的项目。',async()=>{const joined=await api('/invites/join',{method:'POST',body:{token:invite}});history.replaceState({},'',location.pathname);await loadProjects(joined.project_id);toast('已加入项目');},{label:'接受邀请'});
      return;
    }
    const setup=await api('/api/setup/status',{team:false});
    state.setupPasswordRequired=!!setup.require_setup_password;
    renderAuth(!!(setup.setup_required??setup.needs_setup??setup.needs_initialization??false));
  }catch(e){
    if(state.token){sessionStorage.removeItem(SESSION);state.token=null;state.user=null;return bootstrap();}
    app.replaceChildren(empty('暂时无法连接服务',e.message,'refresh',button('重新连接',bootstrap,{icon:'refresh'})));
  }
}
function renderAuth(setup,loginExisting=false) {
  clearTimeout(state.timer);
  const invite=invitation(),register=setup||(invite&&!loginExisting);
  const form=el('form');
  const errors=el('div');
  const title=setup?'创建工作空间管理员':register?'加入共同的项目':'欢迎回来';
  const intro=el('section',{class:'auth-intro'},brand(),el('div',{},el('h1',{},el('span',{class:'auth-title-line'},'让讨论有'),el('span',{class:'auth-title-line'},'共同的上下文。')),el('p',{},'从一个项目开始。一起讨论，把计划变成任务，把结果留在团队里。'),el('div',{class:'auth-tags'},['共同讨论','任务与日历','团队资料'].map(x=>el('span',{},x)))),el('div',{class:'auth-foot'},'共知 · 团队 AI 协作工作空间'));
  if(register)form.append(field('display_name','你的姓名','text','',{attrs:{required:true,maxlength:80,autocomplete:'name'}}));
  form.append(field('username','用户名','text','',{attrs:{required:true,minlength:3,maxlength:64,pattern:'[A-Za-z0-9][A-Za-z0-9_.-]{2,63}',autocomplete:'username',spellcheck:'false'},help:register?'3–64 位字母、数字、点、下划线或短横线':null}));
  form.append(field('password','密码','password','',{attrs:{required:true,minlength:register?12:1,maxlength:200,autocomplete:register?'new-password':'current-password'},help:register?'至少 12 个字符。请使用独立的强密码。':null}));
  if(setup&&state.setupPasswordRequired)form.append(field('setup_password','初始化口令','password','',{attrs:{required:true},help:'请填写安装时生成的初始化口令，见部署记录。'}));
  form.append(errors);
  const submit=el('button',{type:'submit',class:'btn primary submit'},register?(setup?'创建并进入':'接受邀请并加入'):'登录');
  form.append(submit);
  form.addEventListener('submit',async e=>{
    e.preventDefault();submit.disabled=true;errors.replaceChildren();
    try{
      const v=values(form);let result;
      if(setup)result=await api('/api/setup/team/init',{team:false,method:'POST',body:v});
      else if(register)result=await api('/api/setup/team/redeem',{team:false,method:'POST',body:{...v,token:invite}});
      else result=await api('/api/auth/login',{team:false,method:'POST',body:{username:v.username,password:v.password}});
      storeSession(result);
      if(invite&&!register)await api('/invites/join',{method:'POST',body:{token:invite}});
      if(invite)history.replaceState({},'',location.pathname);
      if(!state.user){const me=await api('/api/auth/me',{team:false});state.user=me.user||me;}
      await loadProjects(result.project_id);
    }catch(err){errors.append(el('div',{class:'form-error',role:'alert'},err.message));}
    finally{submit.disabled=false;}
  });
  const info=setup?'首次启动，建立你的管理员账号。':register?'此邀请链接只能使用一次。注册后，你将加入邀请对应的项目。':invite?'登录现有账号后，将接受当前项目邀请。':'用你的团队账号登录。账号由管理员创建或通过项目邀请加入。';
  const card=el('div',{class:'auth-card'},el('h2',{},title),el('p',{class:'muted'},info),form);
  if(invite&&!setup)card.append(el('div',{class:'auth-bottom'},button(loginExisting?'创建新账号加入':'已有账号，登录加入',()=>renderAuth(false,!loginExisting),{class:'ghost'})));
  app.replaceChildren(el('main',{class:'auth-page',id:'workspace'},intro,el('section',{class:'auth-form-side'},card)));
}
async function loadProjects(preferred) {
  const result=await api('/projects');state.projects=result.items||[];
  const hash=new URLSearchParams(location.hash.slice(1));
  const id=preferred||hash.get('project')||state.project?.id||state.projects[0]?.id;
  state.tab=['discussion','tasks','calendar','documents'].includes(hash.get('tab'))?hash.get('tab'):state.tab;
  state.project=state.projects.find(p=>p.id===id)||state.projects[0]||null;
  renderShell();
  if(state.project)await selectProject(state.project.id);
}
function renderShell() {
  const sidebar=el('aside',{class:'sidebar','aria-label':'项目导航'},brand(),button('新建项目',newProject,{icon:'plus'}),el('div',{class:'sidebar-caption'},'我的项目'),el('div',{class:'project-list',id:'project-list'}),el('div',{class:'sidebar-footer'},el('div',{class:'row'},avatar(state.user?.display_name||state.user?.username),el('div',{class:'grow account-name'},state.user?.display_name||state.user?.username||'团队成员'),iconButton('moon','切换明暗外观',toggleTheme),iconButton('logout','退出登录',()=>logout())),el('p',{class:'sidebar-note'},'每次讨论，都成为下一次的起点。')));
  const shell=el('div',{class:'app-shell'},sidebar,el('div',{class:'sidebar-scrim',onclick:()=>shell.classList.remove('sidebar-open')}),el('main',{class:'workspace',id:'workspace',tabindex:'-1'}));
  app.replaceChildren(shell);renderProjectList();
  if(!state.project)$('#workspace').append(empty('从一个共同的项目开始','创建项目后，邀请成员一起讨论、安排任务，并沉淀团队资料。','plan',button('创建第一个项目',newProject,{class:'primary',icon:'plus'})));
}
function renderProjectList() {
  const container=$('#project-list');if(!container)return;
  container.replaceChildren(...state.projects.map(p=>el('button',{type:'button',class:'project-button'+(p.id===state.project?.id?' active':''),'aria-current':p.id===state.project?.id?'page':null,onclick:()=>selectProject(p.id).catch(handle)},el('span',{class:'project-symbol'},p.title.slice(0,1)),el('span',{},p.title))));
}
function header() {
  const p=state.project;
  const tabs=[['discussion','讨论','chat'],['tasks','任务','tasks'],['calendar','日历','calendar'],['documents','资料','files']];
  return el('header',{class:'project-header'},el('div',{class:'eyebrow'},'PROJECT WORKSPACE'),
    el('div',{class:'project-title-row'},el('div',{class:'row grow'},iconButton('menu','打开项目导航',toggleLeftSidebar),el('h1',{},p.title)),
      el('div',{class:'row'},button(el('span',{class:'desktop-text'},'项目规划'),planDialog,{class:'ghost',icon:'plan',title:'项目规划'}),button(el('span',{class:'desktop-text'},'设置'),()=>settingsDialog(),{class:'ghost',icon:'settings',title:'项目设置'}))),
    el('p',{class:'project-goal'},p.goal||'写下共同目标，让讨论围绕同一个方向。'),
    el('nav',{class:'tabs','aria-label':'项目内容'},tabs.map(([id,name,ic])=>el('button',{type:'button',class:'tab'+(state.tab===id?' active':''),'aria-current':state.tab===id?'page':null,onclick:()=>switchTab(id)},icon(ic,16),name)),
      el('div',{class:'tab-extra'},el('span',{class:'dot',id:'connection-dot'}),el('span',{class:'connection-label',id:'connection-label'},'同步中'),badge(p.role))));
}
async function selectProject(id) {
  state.controller?.abort();clearTimeout(state.timer);const generation=++state.generation;
  state.controller=new AbortController();state.project=state.projects.find(p=>p.id===id)||{id,title:'正在加载…'};
  state.messages=[];state.lastSeq=0;state.running=null;state.tasks=[];state.calendar=[];state.documents=[];state.proposals=[];state.members=[];state.runs=[];state.settings=null;state.draft='';state.search='';state.messageClient=crypto.randomUUID();state.runClient=crypto.randomUUID();state.pendingRunPayload=null;
  document.querySelectorAll('dialog').forEach(d=>d.remove());$('.app-shell')?.classList.remove('sidebar-open');renderProjectList();
  const workspace=$('#workspace');workspace.replaceChildren(header(),el('section',{class:'content',id:'content'},el('div',{class:'inline-loading'},'正在载入项目…')));
  try{
    const p=await api('/projects/'+encodeURIComponent(id),{signal:state.controller.signal});if(generation!==state.generation)return;
    state.project=p;workspace.replaceChildren(header(),el('section',{class:'content',id:'content'}));fixMobileMenu();
    await initialData(generation);if(generation!==state.generation)return;
    renderView();updateHash();schedulePoll();
  }catch(e){
    if(e.name==='AbortError')return;
    $('#content')?.replaceChildren(empty('项目暂时不可用',e.message,'refresh',button('返回项目列表',()=>loadProjects().catch(handle),{icon:'back'})));handle(e);
  }
}
function fixMobileMenu(){$('.project-title-row .icon-btn')?.classList.add('mobile-menu');}
async function initialData(generation) {
  const signal=state.controller.signal;
  const endpoints=['/members','/tasks','/calendar','/documents','/proposals','/settings','/runs'];
  const responses=await Promise.all(endpoints.map(x=>api(projectPath(x),{signal})));
  if(generation!==state.generation)return;
  [state.members,state.tasks,state.calendar,state.documents,state.proposals,state.settings,state.runs]=responses.map((r,i)=>i===5?r:r.items||[]);
  await fetchMessages(generation);setConnection(true);
}
async function fetchMessages(generation=state.generation) {
  let more=true,guard=0;
  while(more&&guard++<20){
    const result=await api(projectPath('/messages?after='+state.lastSeq),{signal:state.controller.signal});
    if(generation!==state.generation)return;
    const oldIds=new Set(state.messages.map(m=>m.id));
    const incoming=(result.items||[]).filter(m=>!oldIds.has(m.id));
    state.messages.push(...incoming);state.lastSeq=state.messages.reduce((n,m)=>Math.max(n,m.seq),state.lastSeq);state.running=result.running||null;
    if(state.tab==='discussion')appendMessages(incoming);
    more=result.has_more;
  }
}
function updateHash(){if(state.project)history.replaceState({},'','#project='+encodeURIComponent(state.project.id)+'&tab='+state.tab);}
function switchTab(tab) {
  if(state.tab===tab)return;state.tab=tab;updateHash();
  $('.project-header')?.replaceWith(header());fixMobileMenu();renderView();
}
function renderView() {
  const content=$('#content');if(!content)return;
  content.className='content'+(state.tab==='discussion'?' discussion-content':'');
  content.replaceChildren();
  if(state.tab==='discussion')renderDiscussion(content);
  if(state.tab==='tasks')renderTasks(content);
  if(state.tab==='calendar')renderCalendar(content);
  if(state.tab==='documents')renderDocuments(content);
  fixMobileMenu();
}
function setConnection(ok) {
  state.online=ok;const label=$('#connection-label'),dot=$('#connection-dot');
  if(label)label.textContent=ok?'已同步':'正在重连';if(dot)dot.style.background=ok?'var(--success)':'var(--warning)';
  const banner=$('#network-banner');
  if(ok)banner?.remove();
  else if(!banner)$('#content')?.prepend(el('div',{class:'network-banner',id:'network-banner'},'连接暂时中断，正在重试。请保留当前页面。'));
}
function schedulePoll(){clearTimeout(state.timer);state.timer=setTimeout(poll,2800);}
async function poll() {
  if(!state.project||!state.token)return;
  if(document.hidden){schedulePoll();return;}
  if(state.polling){schedulePoll();return;}
  state.polling=true;const generation=state.generation;
  try{
    await fetchMessages(generation);
    const results=await Promise.all(['/runs','/proposals','/'+({tasks:'tasks',calendar:'calendar',documents:'documents'}[state.tab]||'members')].map(path=>api(projectPath(path),{signal:state.controller.signal})));
    if(generation!==state.generation)return;
    const oldRuns=JSON.stringify(state.runs),oldProposals=JSON.stringify(state.proposals);
    state.runs=results[0].items||[];state.proposals=results[1].items||[];
    const key={tasks:'tasks',calendar:'calendar',documents:'documents'}[state.tab]||'members';
    const changed=JSON.stringify(state[key])!==JSON.stringify(results[2].items||[]);state[key]=results[2].items||[];
    if(changed&&state.tab!=='discussion'&&!(state.tab==='documents'&&state.search))renderView();
    if(state.tab==='discussion'){
      renderRunning();if(oldProposals!==JSON.stringify(state.proposals))renderProposalBar();
      if(oldRuns!==JSON.stringify(state.runs)){const previous=JSON.parse(oldRuns);const failure=state.runs.find(r=>r.status==='failed'&&previous.some(x=>x.id===r.id&&['queued','running'].includes(x.status))&&(!state.task||r.request?.task_id===state.task.id)&&!poll.seen?.has(r.id));poll.seen??=new Set();if(failure){poll.seen.add(failure.id);toast('AI '+(labels[failure.status]||failure.status)+'：'+(failure.error||'请在用量记录查看详情'),true);}}
    }
    setConnection(true);
  }catch(e){
    if(e.name==='AbortError')return;
    if(e.status===403||e.status===404){state.controller.abort();state.generation++;clearTimeout(state.timer);state.project=null;state.messages=[];document.querySelectorAll('dialog').forEach(d=>d.remove());await loadProjects();toast('当前项目访问权限已变化，已刷新项目列表',true);return;}
    setConnection(false);
  }finally{state.polling=false;if(generation===state.generation)schedulePoll();}
}
async function refresh() {
  if(!state.project)return;
  const gen=state.generation;await initialData(gen);if(gen!==state.generation)return;
  const p=await api(projectPath(),{signal:state.controller.signal});if(gen!==state.generation)return;
  state.project=p;const at=state.projects.findIndex(x=>x.id===p.id);if(at>=0)state.projects[at]=p;renderProjectList();
  $('.project-header')?.replaceWith(header());renderView();fixMobileMenu();
}
function newProject() {
  formDialog('新建项目',[
    field('title','项目名称','text','',{attrs:{required:true,maxlength:120,placeholder:'例如：团队协作空间首版'}}),
    field('goal','共同目标','textarea','',{attrs:{maxlength:4000,placeholder:'这个项目最终希望达成什么？'}}),
    field('timezone','项目时区','select','Asia/Shanghai',{choices:[['Asia/Shanghai','北京时间 · Asia/Shanghai'],['UTC','UTC'],['Asia/Hong_Kong','香港 · Asia/Hong_Kong'],['Asia/Singapore','新加坡 · Asia/Singapore'],['America/Los_Angeles','洛杉矶 · America/Los_Angeles']]})
  ],async v=>{const p=await api('/projects',{method:'POST',body:v});state.projects.unshift(p);if(!$('#content'))renderShell();await selectProject(p.id);toast('项目已创建');},{submit:'创建项目',description:'先把方向说清楚，具体计划可以在项目里逐步完善。'});
}
function planDialog() {
  const p=state.project;
  if(!canWrite()){openDialog('项目规划',el('div',{class:'stack'},el('h3',{},p.goal||'尚未填写目标'),markdown(p.plan||'尚未填写规划。')),{description:'项目时区：'+p.timezone,wide:true});return;}
  formDialog('项目规划',[
    field('title','项目名称','text',p.title,{attrs:{required:true,maxlength:120}}),
    field('goal','共同目标','textarea',p.goal,{attrs:{maxlength:4000}}),
    field('plan','规划、里程碑与关键指标','textarea',p.plan,{attrs:{class:'text-area-large',maxlength:80000,placeholder:'## 阶段目标\n\n## 里程碑\n\n## 关键指标\n\n## 当前优先事项'},help:'支持 Markdown。任务截止日期在日历中自动出现。'}),
    field('timezone','项目时区','text',p.timezone,{attrs:{required:true},help:'使用 IANA 时区，例如 Asia/Shanghai。日历按项目时区显示。'})
  ],async v=>{await api(projectPath(),{method:'PATCH',body:{...v,expected_revision:p.revision}});await refresh();toast('项目规划已保存');},{wide:true,description:'围绕同一个目标，保持一份共同计划。'});
}
function messageElement(m) {
  const isAI=m.kind==='assistant';
  const body=el('div',{class:'message-body'},el('div',{class:'message-meta'},el('span',{class:'message-name'},m.author_name||(isAI?'团队 AI':'团队成员')),isAI&&badge('AI','accent'),m.demo&&badge('示例','warning'),el('time',{class:'message-time',datetime:m.created_at,title:m.created_at},stamp(m.created_at)),el('span',{class:'message-time'},'#'+m.seq)),markdown(m.content));
  if(m.attachments?.length)body.append(el('div',{},m.attachments.map(a=>button(a.title||'附件',()=>documentDialog(a.id),{class:'attachment',icon:'files'}))));
  const sources=m.citations||m.sources||[];
  if(sources.length)body.append(el('div',{class:'sources'},sources.map((s,i)=>el('button',{type:'button',class:'source-button',onclick:()=>documentDialog(s.document_id)},'资料 '+(i+1)+' · '+s.title+' · '+s.location))));
  if(canWrite())body.append(el('div',{class:'message-actions'},el('button',{type:'button',onclick:()=>taskDialog(null,{source_seq:m.seq,body:m.content})},'转成任务'),el('button',{type:'button',onclick:()=>noteDialog(null,{source_seq:m.seq,body:m.content})},'保存知识')));
  return el('article',{class:'message',id:'message-'+m.id,'data-seq':m.seq},avatar(m.author_name,isAI),body);
}
function appendMessages(incoming) {
  const list=$('#messages');if(!list)return;
  const near=list.scrollHeight-list.scrollTop-list.clientHeight<150;
  if(incoming.length){$('.empty',list)?.remove();incoming.forEach(m=>{if(!$('#message-'+m.id,list))list.append(messageElement(m));});if(near)list.scrollTop=list.scrollHeight;}
  renderRunning();
}
function renderDiscussion(content) {
  const list=el('div',{class:'messages',id:'messages','aria-live':'polite','aria-relevant':'additions'});
  if(state.messages.length)state.messages.forEach(m=>list.append(messageElement(m)));
  else list.append(empty('从第一句讨论开始','这里是项目成员共同的讨论空间。消息会持续保留，AI 只在你请求时参与。','chat'));
  const textarea=el('textarea',{'aria-label':'讨论内容',placeholder:canWrite()?'与团队分享想法、提出问题…':'你以只读身份查看此项目',value:state.draft,disabled:!canWrite(),maxlength:30000});
  textarea.addEventListener('input',()=>{state.draft=textarea.value;});
  const send=button('发送',()=>sendMessage(false),{class:'primary',icon:'arrow',disabled:!canWrite()});
  const ask=button('请 AI 回答',()=>sendMessage(true),{icon:'spark',disabled:!canWrite()});
  textarea.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();sendMessage(false);}});
  const upload=iconButton('clip','上传文件并存入项目资料',()=>chooseUpload('chat'));upload.disabled=!canWrite();
  const composer=el('div',{class:'composer-wrap'},el('div',{class:'composer'},textarea,el('div',{class:'composer-bottom'},upload,el('span',{class:'composer-hint'},'Markdown · Ctrl / ⌘ + Enter 发送'),el('span',{class:'grow'}),ask,send)),el('p',{class:'composer-footnote'},'聊天附件自动归档到本项目资料 · 重要决定与任务需确认采用'));
  content.append(el('div',{class:'discussion-top'},el('span',{},state.members.length+' 位成员 · 一条持续的共同讨论'),button('整理本轮讨论',()=>startRun('summary'),{class:'small',icon:'spark',disabled:!canWrite(),title:'将尚未整理的消息生成纪要和候选任务、安排、决定'})),el('div',{id:'proposal-slot'}),list,el('div',{id:'run-slot'}),composer);
  renderProposalBar();renderRunning();requestAnimationFrame(()=>{list.scrollTop=list.scrollHeight;});
}
async function sendMessage(withAI) {
  const text=state.draft.trim();if(!text&&!withAI)return;
  const gen=state.generation,p=state.project.id;
  const controls=$('.composer');const buttons=[...controls.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  let request=null;
  try{
    if(text){await api('/projects/'+p+'/messages',{method:'POST',body:{content:text,client_id:state.messageClient}});if(gen!==state.generation)return;state.draft='';$('.composer textarea').value='';state.messageClient=crypto.randomUUID();await fetchMessages(gen);}
    if(withAI){request=state.pendingRunPayload&&!text?state.pendingRunPayload:{kind:'chat',prompt:text,client_id:crypto.randomUUID()};state.pendingRunPayload=request;await api('/projects/'+p+'/runs',{method:'POST',body:request});if(gen!==state.generation)return;state.pendingRunPayload=null;state.runClient=crypto.randomUUID();toast('AI 已开始处理，完成后回复到共同讨论');await fetchMessages(gen);}
  }catch(e){if(request&&e.status&&e.status<500&&gen===state.generation)state.pendingRunPayload=null;handle(e);}finally{if(gen===state.generation)buttons.forEach(b=>b.disabled=!canWrite());}
}
async function startRun(kind,taskId=null,prompt='') {
  const gen=state.generation;const request={kind,task_id:taskId,prompt,client_id:crypto.randomUUID()};
  try{await api(projectPath('/runs'),{method:'POST',body:request});if(gen!==state.generation)return;toast(kind==='summary'?'正在整理讨论，完成后会生成待确认结果卡':'AI 已开始执行，成果将进入待验收');await refresh();}
  catch(e){if(e.message.includes('配置模型')){toast(e.message,true);settingsDialog('ai');}else handle(e);}
}
function renderRunning() {
  const slot=$('#run-slot');if(!slot)return;
  slot.replaceChildren();
  if(state.running)slot.append(el('div',{class:'run-banner'},el('span',{class:'spinner','aria-hidden':'true'}),'AI 正在'+(state.running.kind==='summary'?'整理讨论':state.running.kind==='task'?'生成任务成果':'思考')+'…',el('span',{class:'grow'}),el('span',{},'你可以继续发言')));
}
function renderProposalBar() {
  const slot=$('#proposal-slot');if(!slot)return;slot.replaceChildren();
  const pending=state.proposals.filter(p=>p.status==='pending'&&(!state.task||p.task_id===state.task.id));
  if(pending.length)slot.append(el('div',{class:'proposal-bar'},icon('spark',16),el('span',{class:'grow'},'有 '+pending.length+' 张整理结果待确认'),button('查看并采用',proposalDialog,{class:'small'})));
}
function renderTasks(content) {
  content.append(el('div',{class:'view-head'},el('div',{},el('h2',{},'把下一步安排清楚'),el('p',{},'任务从讨论中来，产物经确认后成为共同知识。')),canWrite()&&button('新建任务',()=>taskDialog(),{class:'primary',icon:'plus'})));
  if(!state.tasks.length){content.append(empty('还没有任务','你可以直接新建任务，也可以把讨论中的一条消息转成任务。','tasks',canWrite()?button('创建任务',()=>taskDialog(),{icon:'plus'}):null));return;}
  const grid=el('div',{class:'kanban'});
  for(const status of ['todo','doing','review','done']){
    const tasks=state.tasks.filter(t=>t.status===status);
    const col=el('section',{class:'kanban-column','aria-label':labels[status]},el('div',{class:'column-title'},el('span',{class:'dot',style:'background:'+({todo:'var(--muted)',doing:'var(--accent)',review:'var(--warning)',done:'var(--success)'}[status])}),labels[status],el('span',{class:'count'},tasks.length)),...tasks.map(taskCard));
    if(!tasks.length)col.append(el('div',{class:'column-empty'},'暂无任务'));grid.append(col);
  }content.append(grid);
  const archived=state.tasks.filter(t=>['paused','cancelled'].includes(t.status));
  if(archived.length)content.append(el('details',{class:'task-archived'},el('summary',{},'已暂停与已取消 · '+archived.length),el('div',{class:'doc-grid',style:'margin-top:14px'},archived.map(taskCard))));
}
function taskCard(t) {
  const overdue=t.due_date&&t.due_date<datePart(new Date().toISOString())&&!['done','cancelled'].includes(t.status);
  return el('button',{type:'button',class:'task-card',onclick:()=>taskDialog(t)},el('div',{class:'row wrap'},badge(t.executor,t.executor==='ai'?'accent':''),t.blocked&&badge('阻塞','warning'),t.parent_id&&badge('子任务')),el('div',{class:'task-title'},t.title),el('div',{class:'task-card-meta'},el('span',{},memberName(t.assignee_id)),el('span',{style:overdue?'color:var(--danger)':null},t.due_date||'无截止日期')));
}
function taskDialog(task=null,preset={}) {
  const t=task||{title:'',body:'',status:'todo',executor:'human',blocked:false,criteria:'',result:'',review_note:'',...preset};
  if(!canWrite()){openDialog(t.title,el('div',{class:'stack'},el('div',{class:'row wrap'},badge(t.status),badge(t.executor)),markdown(t.body),el('h3',{},'验收标准'),markdown(t.criteria||'未填写'),el('h3',{},'产物'),markdown(t.result||'尚无产物'),el('h3',{},'验收意见'),markdown(t.review_note||'尚未验收')),{wide:true});return;}
  const statusChoices=['todo','doing','review','done','paused','cancelled'].map(s=>[s,labels[s]]);
  const fields=[
    field('title','任务名称','text',t.title,{attrs:{required:true,maxlength:200}}),
    field('body','任务说明','textarea',t.body,{attrs:{maxlength:30000}}),
    el('div',{class:'field-row'},field('assignee_id','负责人','select',t.assignee_id||'',{choices:[['','待分配'],...state.members.map(m=>[m.user_id,m.display_name])]}),field('executor','执行方式','select',t.executor,{choices:[['human','人工'],['ai','AI'],['collab','人机协作']]})),
    el('div',{class:'field-row'},field('status','状态','select',t.status,{choices:statusChoices}),field('due_date','截止日期','date',t.due_date||'')),
    field('criteria','验收标准','textarea',t.criteria,{attrs:{maxlength:30000,placeholder:'什么结果算完成？'},help:'AI 执行前，需要明确的人类负责人和验收标准。'}),
    field('result','任务产物','textarea',t.result,{attrs:{maxlength:30000,placeholder:'记录结果，或写下产物链接。'}}),
    field('review_note','验收意见','textarea',t.review_note,{attrs:{maxlength:30000},help:'先提交待验收，再填写产物和验收意见后设为已完成。验收成果自动存入资料。'}),
    el('div',{class:'field-row'},field('parent_id','所属父任务','select',t.parent_id||'',{choices:[['','无'],...state.tasks.filter(x=>x.id!==t.id).map(x=>[x.id,x.title])]}),field('source_seq','来源消息序号','number',t.source_seq||'',{attrs:{min:1,step:1},help:'可选，用于追溯到共同讨论。'})),
    el('label',{class:'field-check'},el('input',{type:'checkbox',name:'blocked',checked:t.blocked}),'任务受阻，需要团队协助')
  ];
  const extras=[];
  if(task&&canManageProject())extras.push(button('删除任务',()=>deleteRecord(task,'任务'),{class:'danger left'}));
  if(task&&!['done','review','paused','cancelled'].includes(task.status))extras.push(button('交给 AI 执行',async()=>{dlg.close();await startRun('task',task.id);},{icon:'spark',class:'left'}));
  const dlg=formDialog(task?'任务详情':'新建任务',fields,async(v,form)=>{
    const body={...v,assignee_id:v.assignee_id?Number(v.assignee_id):null,source_seq:v.source_seq?Number(v.source_seq):null,parent_id:v.parent_id||null,due_date:v.due_date||null,blocked:!!form.elements.blocked.checked};
    if(task)body.expected_revision=task.revision;
    await api(task?'/tasks/'+task.id:projectPath('/tasks'),{method:task?'PATCH':'POST',body});await refresh();toast('任务已保存');
  },{wide:true,extra:extras,description:task?'负责人对最终验收负责。AI 产物不会自动标为完成。':'一个明确行动，一位负责人，一份验收标准。'});
}
function renderCalendar(content) {
  const month=state.month;
  const monthName=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long'}).format(month);
  content.append(el('div',{class:'view-head'},el('div',{},el('h2',{},'把重要节点放在一起'),el('p',{},'任务截止日期自动同步 · '+state.project.timezone)),canWrite()&&button('新增安排',()=>eventDialog(),{class:'primary',icon:'plus'})));
  const controls=el('div',{class:'row spread',style:'margin-bottom:16px'},el('h3',{style:'margin:0'},monthName),el('div',{class:'row'},iconButton('back','上个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()-1,1);renderView();}),button('本月',()=>{state.month=new Date(new Date().getFullYear(),new Date().getMonth(),1);renderView();},{class:'small ghost'}),iconButton('chevron','下个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()+1,1);renderView();})));
  const grid=el('div',{class:'calendar-grid'},['一','二','三','四','五','六','日'].map(d=>el('div',{class:'calendar-day-name'},d)));
  const start=new Date(month.getFullYear(),month.getMonth(),1);start.setDate(start.getDate()-(start.getDay()+6)%7);
  const today=datePart(new Date().toISOString());
  for(let i=0;i<42;i++){
    const day=new Date(start);day.setDate(start.getDate()+i);
    const key=day.getFullYear()+'-'+String(day.getMonth()+1).padStart(2,'0')+'-'+String(day.getDate()).padStart(2,'0');
    const items=state.calendar.filter(x=>datePart(x.starts_at)===key);
    const cell=el('div',{class:'calendar-day'+(day.getMonth()!==month.getMonth()?' other-month':'')},el('span',{class:'calendar-date'+(key===today?' today':'')},day.getDate()),items.slice(0,3).map(item=>el('button',{type:'button',class:'calendar-event'+(item.kind==='task'?' task':''),title:item.title,onclick:()=>calendarItem(item)},item.title)));
    if(items.length>3)cell.append(el('span',{class:'muted'},'另有 '+(items.length-3)+' 项'));grid.append(cell);
  }
  const agenda=el('div',{class:'panel agenda'},el('h3',{},'近期安排'));
  const upcoming=state.calendar.filter(x=>datePart(x.starts_at)>=today).slice(0,25);
  if(!upcoming.length)agenda.append(el('p',{class:'muted',style:'font-size:12px'},'还没有接下来的安排。你可以添加会议、里程碑，或为任务设置截止日期。'));
  upcoming.forEach(item=>{const d=datePart(item.starts_at);agenda.append(el('div',{class:'list-row'},el('div',{class:'date-chip'},d.slice(5,7)+'月',el('strong',{},d.slice(8,10))),el('div',{class:'grow'},el('button',{type:'button',class:'text-button',onclick:()=>calendarItem(item)},el('h3',{},item.title)),el('p',{},(labels[item.kind]||item.kind)+' · '+(item.all_day?'全天':stamp(item.starts_at)))),badge(item.status)));});
  content.append(el('div',{class:'calendar-layout'},el('section',{class:'panel'},controls,grid),agenda));
}
function calendarItem(item){if(item.kind==='task')taskDialog(state.tasks.find(t=>t.id===item.id)||item);else eventDialog(item);}
function localDateTime(value) {
  if(!value)return '';
  const d=new Date(value);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
function eventDialog(event=null,preset={}) {
  const t=event||{title:'',body:'',kind:'meeting',starts_at:'',ends_at:'',...preset};
  if(!canWrite()){openDialog(t.title,el('div',{},el('p',{class:'muted'},stamp(t.starts_at)+' — '+(t.ends_at?stamp(t.ends_at):'无结束时间')),markdown(t.body)));return;}
  const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  const fields=[
    field('title','安排名称','text',t.title,{attrs:{required:true,maxlength:200}}),
    field('kind','安排类型','select',t.event_kind||t.kind,{choices:[['meeting','会议'],['milestone','里程碑']]}),
    el('div',{class:'field-row'},field('starts_at','开始时间','datetime-local',localDateTime(t.starts_at),{attrs:{required:true}}),field('ends_at','结束时间','datetime-local',localDateTime(t.ends_at))),
    el('p',{class:'notice neutral'},'此表单按浏览器时区 '+timezone+' 输入；保存后日历按项目时区 '+state.project.timezone+' 显示。'),
    field('body','安排说明','textarea',t.body,{attrs:{maxlength:20000}}),
    field('source_seq','来源消息序号','number',t.source_seq||'',{attrs:{min:1}})
  ];
  if(event)fields.push(field('status','状态','select',t.status,{choices:[['active','有效'],['cancelled','已取消']]}));
  formDialog(event?'安排详情':'新增安排',fields,async v=>{
    const body={...v,starts_at:new Date(v.starts_at).toISOString(),ends_at:v.ends_at?new Date(v.ends_at).toISOString():null,source_seq:v.source_seq?Number(v.source_seq):null};
    if(event)body.expected_revision=event.revision;
    await api(event?'/events/'+event.id:projectPath('/events'),{method:event?'PATCH':'POST',body});await refresh();toast('安排已保存');
  },{description:'任务的截止日期请在任务详情中修改，这里不会创建重复副本。',extra:event&&canManageProject()?[button('删除日程',()=>deleteRecord(event,'日程'),{class:'danger left'})]:[]});
}
function renderDocuments(content) {
  content.append(el('div',{class:'view-head'},el('div',{},el('h2',{},'团队共同的资料与知识'),el('p',{},'聊天附件与主动上传进入同一处。原件保留，知识可追溯。')),canWrite()&&button('上传文件',()=>chooseUpload('library'),{class:'primary',icon:'upload'})));
  const input=el('input',{type:'search',value:state.search,placeholder:'检索本项目资料…','aria-label':'检索项目资料'});
  input.addEventListener('input',()=>{state.search=input.value;});
  const search=()=>{state.search=input.value.trim();searchDocuments();};
  const searchBox=el('form',{class:'search-box',onsubmit:e=>{e.preventDefault();search();}},icon('search',16),input,el('button',{type:'submit',class:'btn ghost small'},'检索'));
  const tools=el('div',{class:'doc-tools'},searchBox,canWrite()&&button('写知识',()=>noteDialog(),{icon:'plus'}),button('导出 Markdown',()=>download(projectPath('/export'),state.project.title+'-Markdown.zip'),{icon:'download'}));
  content.append(tools);
  if(canWrite()){
    const zone=el('div',{class:'drop-zone',tabindex:'0',role:'button','aria-label':'选择或拖入文件上传',onclick:()=>chooseUpload('library'),onkeydown:e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseUpload('library');}}},icon('upload',20),el('p',{style:'margin:8px 0 0'},'拖入文件，或点击选择'),el('small',{},'单个文件最大 20 MB · 相同原件自动识别，不重复保存'));
    zone.addEventListener('dragover',e=>{e.preventDefault();zone.classList.add('dragging');});
    zone.addEventListener('dragleave',()=>zone.classList.remove('dragging'));
    zone.addEventListener('drop',e=>{e.preventDefault();zone.classList.remove('dragging');uploadFiles([...e.dataTransfer.files],'library');});content.append(zone);
  }
  content.append(el('div',{id:'document-results'}));if(state.search)searchDocuments();else renderDocumentList();
}
function renderDocumentList() {
  const root=$('#document-results');if(!root)return;
  if(!state.documents.length){root.replaceChildren(empty('把团队资料放在这里','上传文档、记录知识，或整理一轮讨论。下一次请求 AI 时，会检索本项目中可用的资料。','files'));return;}
  root.replaceChildren(el('div',{class:'doc-grid'},state.documents.map(d=>el('button',{type:'button',class:'doc-card',onclick:()=>documentDialog(d.id)},el('div',{class:'row spread'},icon(d.kind==='file'?'files':'plan',19),badge(d.status,d.status==='ready'?'success':d.status==='failed'?'danger':'')),el('h3',{},d.title),el('div',{class:'doc-card-preview'},d.body?.slice(0,200)||(d.status==='ready'?'已归档，可在项目内检索。':d.status==='uploaded'?'原件已保存，正在等待解析。':d.status==='unindexed'?'原件已保留，此类型暂未提取文本。':'原件已保留，查看详情了解处理状态。')),el('div',{class:'row wrap'},badge(d.kind),d.adopted&&badge('已采用','accent'),d.supersedes_id&&badge('新版本')),el('div',{class:'doc-card-meta'},el('span',{},'v'+d.revision),el('span',{},stamp(d.updated_at||d.created_at)))))));
}
async function searchDocuments() {
  const q=state.search,gen=state.generation,root=$('#document-results');if(!root)return;
  if(!q){renderDocumentList();return;}
  root.replaceChildren(el('div',{class:'inline-loading'},'正在检索项目资料…'));
  try{
    const result=await api(projectPath('/search?q='+encodeURIComponent(q)),{signal:state.controller.signal});
    if(gen!==state.generation||q!==state.search||!root.isConnected)return;
    const items=result.items||[];
    root.replaceChildren(el('div',{class:'row spread',style:'margin-bottom:15px'},el('span',{class:'muted',style:'font-size:12px'},'找到 '+items.length+' 个相关片段'),button('返回全部资料',()=>{state.search='';renderView();},{class:'small ghost'})));
    if(!items.length)root.append(empty('没有找到相关片段','试试资料中的名称或关键词；尚未解析的文件不会出现在检索结果中。','search'));
    else items.forEach(s=>root.append(el('article',{class:'search-result'},el('h3',{},el('button',{type:'button',class:'text-button',onclick:()=>documentDialog(s.document_id)},s.title)),el('div',{class:'search-meta'},s.location+' · v'+s.revision+(s.adopted?' · 已采用':'')),el('p',{},s.content))));
  }catch(e){if(e.name!=='AbortError'&&root.isConnected)root.replaceChildren(el('div',{class:'form-error'},e.message));}
}
function chooseUpload(origin) {
  const input=el('input',{type:'file',multiple:true,class:'visually-hidden'});document.body.append(input);
  input.addEventListener('change',()=>{const files=[...input.files];input.remove();uploadFiles(files,origin);},{once:true});
  input.addEventListener('cancel',()=>input.remove(),{once:true});input.click();
}
async function uploadFiles(files,origin) {
  if(!files.length)return;
  const p=state.project.id,gen=state.generation;let uploaded=0,duplicates=0;
  for(const file of files){
    if(file.size>20*1024*1024){toast(file.name+' 超过 20 MB，未上传',true);continue;}
    if(!file.size){toast(file.name+' 是空文件，未上传',true);continue;}
    const form=new FormData();form.set('file',file);form.set('origin',origin);if(state.task)form.set('task_id',state.task.id);if(state.task)form.set('task_id',state.task.id);
    try{const result=await api('/projects/'+p+'/uploads',{method:'POST',body:form});uploaded++;if(result.duplicate)duplicates++;}
    catch(e){handle(e);}
  }
  if(gen===state.generation){await refresh();if(uploaded)toast(uploaded+' 个文件已归档'+(duplicates?'，其中 '+duplicates+' 个为相同原件':'')+'。解析完成后可检索。');}
}
async function download(path,filename) {
  try{
    const response=await api(path,{raw:true}),blob=await response.blob(),url=URL.createObjectURL(blob);
    const a=el('a',{href:url,download:filename||'download'});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){handle(e);}
}
async function documentDialog(id) {
  try{
    const gen=state.generation,d=await api('/documents/'+encodeURIComponent(id),{signal:state.controller.signal});if(gen!==state.generation)return;
    const content=el('div',{},el('div',{class:'document-detail-meta'},badge(d.kind),badge(d.status),badge('v'+d.revision),d.adopted&&badge('已采用','accent')),d.status!=='ready'&&el('p',{class:'notice'},d.parse_error||d.error||(d.status==='unindexed'?'原件已保留，当前类型未提取可检索文本。':d.status==='uploaded'?'原件已保存，后台正在等待解析。':d.status==='superseded'?'此条目已有新版本。历史原件仍保留。':'解析尚未完成，原件仍保留。')),el('div',{class:'document-detail-body'},markdown(d.body||'此文件暂无可显示的文本。')),d.source_seq&&el('div',{class:'source-line'},'来自共同讨论 #'+d.source_seq),d.sha256&&el('div',{class:'source-line'},'SHA-256 · '+d.sha256),d.uploads?.length&&el('div',{class:'source-line'},'上传来源 · '+d.uploads.map(u=>(u.origin==='chat'?'讨论':'资料')+' '+stamp(u.created_at)).join('；')));
    const actions=[];
    if(canManageProject()){actions.push(button('删除资料',()=>deleteRecord(d,'资料'),{class:'danger'}));if(d.kind==='file')actions.push(button('重命名',()=>renameDocument(d),{class:'ghost'}));}
    if(d.kind==='file')actions.push(button('下载原件',()=>download('/documents/'+d.id+'/download',d.title),{icon:'download',class:'left'}));
    if(canWrite()){
      if(['failed','unindexed'].includes(d.status))actions.push(button('重试解析',async()=>{await api('/documents/'+d.id+'/retry',{method:'POST'});dlg.close();toast('已请求重新解析');await refresh();},{icon:'refresh'}));
      if(d.kind!=='file')actions.push(button('编辑',()=>{dlg.close();noteDialog(d);},{icon:'edit'}));
      if(d.status==='ready')actions.push(button(d.adopted?'取消采用':'标记采用',async()=>{try{await api('/documents/'+d.id,{method:'PATCH',body:{expected_revision:d.revision,adopted:!d.adopted}});dlg.close();await refresh();toast('采用状态已更新');}catch(e){handle(e);}}));
      if(d.status!=='superseded'&&state.documents.some(x=>x.id!==d.id&&x.status==='ready'))actions.push(button('指定新版本',()=>{dlg.close();supersedeDialog(d);}));
    }
    const dlg=openDialog(d.title,content,{description:stamp(d.created_at)+' · '+(d.kind==='file'?'原件保持不变':'正文支持 Markdown'),wide:true,actions});
  }catch(e){handle(e);}
}
function supersedeDialog(d) {
  formDialog('用新版本替代',[
    el('p',{class:'notice'},'旧版本仍保留。请确认两个条目属于同一份知识，不能把内容矛盾当成重复删除。'),
    field('replacement_id','选择已经核对的新版本','select','',{choices:[['','请选择'],...state.documents.filter(x=>x.id!==d.id&&x.status==='ready').map(x=>[x.id,x.title])],attrs:{required:true}})
  ],async v=>{await api('/documents/'+d.id+'/supersede',{method:'POST',body:{expected_revision:d.revision,replacement_id:v.replacement_id}});await refresh();toast('版本关系已保存');},{description:'旧版本：'+d.title,submit:'确认替代'});
}
function noteDialog(doc=null,preset={}) {
  const d=doc||{title:'',body:'',...preset};
  formDialog(doc?'编辑知识':'写一条共同知识',[
    field('title','标题','text',d.title,{attrs:{required:true,maxlength:200}}),
    field('body','正文','textarea',d.body,{attrs:{required:true,maxlength:100000,class:'text-area-large',placeholder:'写下结论、依据和适用范围…'},help:'支持 Markdown。知识保留来源，未来讨论可以检索。'}),
    !doc&&field('source_seq','来源消息序号','number',d.source_seq||'',{attrs:{min:1}})
  ],async v=>{
    const body={title:v.title,body:v.body};
    if(doc)body.expected_revision=doc.revision;else {body.source_seq=v.source_seq?Number(v.source_seq):null;body.task_id=state.task?.id||null;}
    await api(doc?'/documents/'+doc.id:projectPath('/notes'),{method:doc?'PATCH':'POST',body});await refresh();toast('知识已保存');
  },{wide:true,submit:'保存知识'});
}
async function settingsDialog(active='ai') {
  const gen=state.generation;
  try{
    const [cfg,providers,members,runs]=await Promise.all(['/settings','/providers','/members','/runs'].map(x=>api(projectPath(x),{signal:state.controller.signal})));
    if(gen!==state.generation)return;
    state.settings=cfg;state.members=members.items||[];state.runs=runs.items||[];
    const tabs=el('div',{class:'settings-tabs','aria-label':'设置分类'}),panel=el('div');
    const wrapper=el('div',{},tabs,panel);
    const dlg=openDialog('项目设置',wrapper,{description:'模型、协作成员和使用记录，集中放在这里。',wide:true});
    const show=name=>{
      active=name;tabs.replaceChildren(...[['ai','团队 AI'],['members','成员'],['usage','用量'],['rules','沉淀规则']].map(([id,label])=>el('button',{type:'button',class:id===name?'active':'','aria-current':id===name?'page':null,onclick:()=>show(id)},label)));
      panel.replaceChildren();
      if(name==='ai')renderAISettings(panel,cfg,providers,async()=>{dlg.close();await refresh();settingsDialog('ai');});
      if(name==='members')renderMemberSettings(panel,async()=>{dlg.close();await refresh();await settingsDialog('members');});
      if(name==='usage')renderUsage(panel);
      if(name==='rules')renderRules(panel);
    };
    show(active);
  }catch(e){handle(e);}
}
function renderAISettings(root,cfg,providers,onSaved) {
  const provider=providers.items?.[0];
  if(providers.server_preset?.available && isOwner()){
    root.append(el('div',{class:'notice neutral'},'OpenCode Go 开发助手已预设；新建项目自动绑定。仅发送开发相关请求，不自动切换到按量付费接口。'),button('绑定预设 OpenCode Go',async()=>{try{await api(projectPath('/provider-preset'),{method:'POST',body:{}});toast('预设已绑定');await onSaved();}catch(e){handle(e);}},{class:'small'}));
  }
  root.append(el('div',{class:'notice'+(providers.configured?' neutral':'')},providers.configured?'团队 AI 已配置。所有请求使用本项目共同的讨论、规划和可检索资料。':'先配置一个模型，即可请求 AI 回答、整理讨论或产出任务成果。人工协作与资料管理现在就可使用。'));
  if(!isOwner()){
    root.append(el('div',{class:'settings-section',style:'margin-top:20px'},el('h3',{},'当前模型'),el('p',{},cfg.model||'尚未配置'),el('h3',{},'预设提示词'),markdown(cfg.system_prompt)),el('h3',{},'项目技能'));
    cfg.skills?.forEach(s=>root.append(el('div',{class:'skill-card'},el('div',{class:'row spread'},el('strong',{},s.name),badge(s.enabled?'已启用':'已停用')),markdown(s.body),el('small',{},'v'+s.revision))));
    root.append(el('p',{class:'muted',style:'font-size:12px'},'模型与技能配置由项目管理员维护。'));return;
  }
  const form=el('form',{style:'margin-top:22px'});
  const modelFields=el('section',{class:'settings-section'},el('h3',{},'模型连接'),
    field('base_url','API 地址','url',provider?.base_url||'',{attrs:{placeholder:'https://api.example.com/v1',maxlength:1000},help:'支持 OpenAI 兼容接口。模型提供方将接收提交的项目上下文。'}),
    field('model','模型名称','text',cfg.model||'',{attrs:{maxlength:200,placeholder:'填写提供方的模型 ID'}}),
    field('api_key','API Key','password','',{attrs:{autocomplete:'new-password',maxlength:8192,placeholder:provider?.has_api_key?'已保存；留空保留当前凭证':'填写本项目使用的 API Key'},help:'凭证保存在服务器，不会回显到页面。更改 API 地址时需重新填写。'}));
  const skills=el('div',{id:'skills-editor'});
  const addSkill=(s={name:'',body:'',enabled:true,revision:1})=>{
    if(skills.children.length>=12){toast('最多配置 12 个技能',true);return;}
    const row=el('div',{class:'skill-card','data-skill':'true'});
    row.append(el('div',{class:'row spread',style:'margin-bottom:10px'},el('label',{class:'field-check'},el('input',{type:'checkbox','data-name':'enabled',checked:s.enabled}),'启用技能'),el('div',{class:'row'},badge('v'+(s.revision||1)),iconButton('close','移除此技能',()=>row.remove()))),
      field('skill_name','技能名称','text',s.name,{attrs:{required:true,maxlength:80,'data-name':'name'}}),
      field('skill_body','技能规则','textarea',s.body,{attrs:{maxlength:6000,'data-name':'body',placeholder:'描述具体做法、输出要求和边界…'}}));
    skills.append(row);
  };
  (cfg.skills||[]).forEach(addSkill);
  form.append(modelFields,el('hr',{class:'divider'}),el('section',{class:'settings-section'},el('h3',{},'行为与上下文'),
    field('system_prompt','预设提示词','textarea',cfg.system_prompt,{attrs:{maxlength:16000,class:'text-area-large'},help:'描述团队 AI 的角色、输出习惯与工作边界。'}),
    el('div',{class:'field-row'},field('max_output_tokens','单次最大输出 token','number',cfg.max_output_tokens,{attrs:{required:true,min:128,max:8192,step:1}}),field('history_limit','普通对话的历史消息上限','number',cfg.history_limit,{attrs:{required:true,min:5,max:200,step:1}})),
    el('p',{class:'help muted',style:'font-size:11px'},'每个项目同时运行一个 AI 请求，每天最多 100 次。整理按明确的消息区间处理。')),
    el('hr',{class:'divider'}),el('section',{class:'settings-section'},el('div',{class:'row spread',style:'margin-bottom:12px'},el('h3',{style:'margin:0'},'项目技能'),button('添加技能',()=>addSkill(),{icon:'plus',class:'small'})),skills,el('p',{class:'muted',style:'font-size:11px'},'技能是可版本追溯的 Markdown 规则，首版用于约束回答和产出。')));
  const save=el('button',{type:'submit',class:'btn primary'},'保存 AI 设置');form.append(save);
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(!form.reportValidity())return;save.disabled=true;formError(form,null);
    try{
      const v=values(form);let current=cfg;
      const wantProvider=!!(v.base_url.trim()||v.api_key.trim()||v.model.trim());
      if(wantProvider){
        if(!v.model.trim()||!v.base_url.trim())throw new Error('请同时填写 API 地址与模型名称');
        if(!provider||v.base_url.trim()!==provider.base_url||v.model.trim()!==cfg.model||v.api_key.trim())
          current=await api(projectPath('/provider'),{method:'POST',body:{base_url:v.base_url.trim(),model:v.model.trim(),api_key:v.api_key,kind:'openai-compatible'}});
      }
      const skillList=[...skills.children].map(row=>({name:$('[data-name="name"]',row).value.trim(),body:$('[data-name="body"]',row).value,enabled:$('[data-name="enabled"]',row).checked}));
      const names=skillList.map(x=>x.name);if(new Set(names).size!==names.length)throw new Error('技能名称不能重复');
      await api(projectPath('/settings'),{method:'PATCH',body:{expected_revision:current.revision,model:current.model,system_prompt:v.system_prompt,max_output_tokens:Number(v.max_output_tokens),history_limit:Number(v.history_limit),skills:skillList}});
      form.elements.api_key.value='';toast('AI 设置已保存。首次请求会使用真实模型。');await onSaved();
    }catch(err){formError(form,err);}finally{save.disabled=false;}
  });
  root.append(form);
}
function renderMemberSettings(root,reload) {
  root.append(el('p',{class:'muted',style:'font-size:12px'},'管理员维护配置与成员；成员参与协作；只读成员可以查看项目内容。'));
  const list=el('div');
  for(const m of state.members){
    const details=el('div',{class:'grow'},el('h3',{},m.display_name),el('p',{},m.username));
    const row=el('div',{class:'list-row'},avatar(m.display_name),details,badge(m.role));
    if(isOwner()){
      const role=el('select',{class:'input','aria-label':'设置 '+m.display_name+' 的角色',style:'width:100px;font-size:12px'},['owner','member','viewer'].map(r=>el('option',{value:r,selected:m.role===r},labels[r])));
      role.addEventListener('change',()=>confirmAction('变更成员角色','将 '+m.display_name+' 设为'+labels[role.value]+'。',async()=>{
        await api(projectPath('/members'),{method:'POST',body:{username:m.username,role:role.value}});await reload();toast('成员角色已更新');
      }));
      row.append(role,iconButton('close','移除 '+m.display_name,()=>confirmAction('移除项目成员','移除后，'+m.display_name+' 将无法继续访问此项目。历史发言会保留。',async()=>{
        await api(projectPath('/members/'+m.user_id),{method:'DELETE'});await reload();toast('成员已移除');
      },{label:'移除成员',danger:true})));
    }list.append(row);
  }root.append(list);
  if(!isOwner())return;
  root.append(el('hr',{class:'divider'}),el('h3',{},'邀请新成员'));
  const role=field('invite_role','邀请角色','select','member',{choices:[['member','成员 · 可协作'],['viewer','只读 · 可查看']]});
  const result=el('div');
  const inviteButton=button('生成邀请链接',async()=>{
    inviteButton.disabled=true;
    try{
      const invitation=await api(projectPath('/invites'),{method:'POST',body:{role:role.control.value}});
      const url=new URL(location.pathname,location.origin);url.searchParams.set('invite',invitation.token);
      const input=el('input',{class:'input',value:url.href,readonly:true,'aria-label':'邀请链接',onclick:e=>e.target.select()});
      result.replaceChildren(el('div',{class:'invite-result'},input,el('p',{style:'margin:8px 0;font-size:11px'},'单次使用 · 72 小时有效 · 到期 '+stamp(invitation.expires_at)),button('复制邀请链接',async()=>{try{await navigator.clipboard.writeText(url.href);toast('邀请链接已复制');}catch{input.select();toast('请复制选中的邀请链接');}},{icon:'link',class:'small'})));
    }catch(e){handle(e);}finally{inviteButton.disabled=false;}
  },{icon:'link'});
  root.append(role,inviteButton,result,el('hr',{class:'divider'}),el('h3',{},'添加已有账号'));
  const form=el('form',{},el('div',{class:'field-row'},field('username','用户名','text','',{attrs:{required:true}}),field('role','项目角色','select','member',{choices:[['member','成员'],['viewer','只读'],['owner','管理员']]})));
  const add=el('button',{type:'submit',class:'btn'},'添加到项目');form.append(add);
  form.addEventListener('submit',async e=>{e.preventDefault();add.disabled=true;formError(form,null);try{await api(projectPath('/members'),{method:'POST',body:values(form)});await reload();toast('成员已添加');}catch(err){formError(form,err);}finally{add.disabled=false;}});
  root.append(form);
}
function renderUsage(root) {
  const runs=state.runs,known=runs.filter(r=>Number.isFinite(r.usage?.total_tokens)||(Number.isFinite(r.usage?.input_tokens)&&Number.isFinite(r.usage?.output_tokens)));
  const total=known.reduce((n,r)=>n+(r.usage.total_tokens??r.usage.input_tokens+r.usage.output_tokens),0),unknown=runs.filter(r=>!r.usage).length;
  root.append(el('div',{class:'usage-grid'},
    el('div',{class:'stat-card'},el('small',{},'近期运行'),el('strong',{class:'stat-value'},runs.length),el('small',{},'最多显示最近 100 次')),
    el('div',{class:'stat-card'},el('small',{},'已知 token 合计'),el('strong',{class:'stat-value'},known.length?total.toLocaleString():'未知'),el('small',{},unknown+' 次未返回用量')),
    el('div',{class:'stat-card'},el('small',{},'费用'),el('strong',{class:'stat-value'},'待核对'),el('small',{},'以模型提供方账单为准'))),
    el('p',{class:'notice neutral'},'缓存与推理 token 是用量明细，不再次叠加。模型未返回用量时显示“未知”，不会记为 0。'));
  if(!runs.length){root.append(empty('还没有 AI 运行记录','配置模型后，发起一次回答、整理或任务执行，即可在这里查看结果与用量。','spark'));return;}
  const list=el('div',{style:'margin-top:20px'});
  for(const r of runs){
    const usage=r.usage;
    const usageText=usage?'输入 '+(usage.input_tokens??'未知')+' · 输出 '+(usage.output_tokens??'未知')+' · 合计 '+(usage.total_tokens??((Number.isFinite(usage.input_tokens)&&Number.isFinite(usage.output_tokens))?usage.input_tokens+usage.output_tokens:'未知')):'提供方未返回 token 用量';
    const row=el('div',{class:'run-row'},el('div',{class:'row spread'},el('div',{class:'row'},icon('spark',15),el('strong',{style:'font-size:12px'},labels[r.kind]||r.kind),badge(r.status,['failed','interrupted'].includes(r.status)?'danger':r.status==='completed'?'success':'accent')),el('time',{class:'muted',style:'font-size:10px'},stamp(r.created_at))),el('div',{class:'run-usage'},(r.model||'未指定模型')+' · 配置 v'+r.config_revision+' · 输入至消息 #'+r.input_seq),el('div',{class:'run-usage'},usageText));
    if(usage?.input_token_details?.cache_read!=null)row.append(el('div',{class:'run-usage'},'其中缓存读取 '+usage.input_token_details.cache_read));
    if(usage?.output_token_details?.reasoning!=null)row.append(el('div',{class:'run-usage'},'其中推理 '+usage.output_token_details.reasoning));
    if(r.error)row.append(el('div',{class:'run-error'},r.error));
    if(r.request?.prompt)row.append(el('details',{style:'margin-top:7px;font-size:11px;color:var(--muted)'},el('summary',{},'查看请求'),el('p',{style:'white-space:pre-wrap;margin-top:8px'},r.request.prompt)));
    list.append(row);
  }root.append(list);
}
function renderRules(root) {
  const rules=[
    ['原话保留','所有成员发言立即保存。没有结论的讨论、分歧和未决事项也会保留，不用摘要替换原始消息。'],
    ['上传即归档','聊天与资料页上传进入同一项目。原件保留，相同文件按内容校验识别；解析完成后可以检索。'],
    ['整理一次，集中确认','点击“整理本轮讨论”，AI 生成纪要及候选任务、安排和决定。你可以修改、取消勾选，再一次采用。'],
    ['结果经过验收','AI 任务完成后进入待验收。人填写产物和验收意见，确认完成，验收成果自动回到资料。'],
    ['新知识保留来处','知识记录来源消息与版本。内容矛盾需要核对，不自动删除或覆盖；旧版本仍可追溯。'],
    ['同一个项目，同一份上下文','AI 使用这个项目共同可见的讨论、规划、技能和检索资料。每次运行记录模型、输入范围与用量。'],
    ['随时带走成果','项目正文、任务、安排与知识可导出 Markdown。上传原件单独保留，可从资料详情下载。']
  ];
  root.append(el('div',{style:'padding-top:6px'},rules.map(([title,text],i)=>el('div',{class:'rule-row'},el('span',{class:'rule-number'},i+1),el('div',{},el('h3',{},title),el('p',{},text))))));
}
function proposalDialog() {
  const pending=state.proposals.filter(p=>p.status==='pending'&&(!state.task||p.task_id===state.task.id));
  const root=el('div');
  const dlg=openDialog('确认本轮整理',root,{description:'纪要已经保留。下面的正式任务、安排与决定，确认后才会写入项目。',wide:true});
  if(!pending.length){root.append(empty('没有待确认结果','整理新的讨论后，会在这里出现候选任务、安排和决定。','check'));return;}
  for(const proposal of pending){
    const copy={...proposal,tasks:(proposal.tasks||[]).map(x=>({...x})),events:(proposal.events||[]).map(x=>({...x})),decisions:(proposal.decisions||[]).map(x=>({...x}))};
    const checked=new Map();
    const card=el('article',{class:'proposal-card'},el('div',{class:'row spread'},el('h3',{},proposal.title),badge('pending','warning')),el('p',{class:'source-line'},'讨论范围 #'+proposal.from_seq+' — #'+proposal.to_seq),markdown(proposal.body));
    const rows=el('div');card.append(rows);
    const renderRows=()=>{
      rows.replaceChildren();
      for(const [key,title] of [['tasks','候选任务'],['events','候选安排'],['decisions','候选决定']]){
        if(!copy[key]?.length)continue;
        const section=el('section',{class:'proposal-section'},el('h4',{},title+' · '+copy[key].length));
        copy[key].forEach((item,index)=>{
          const itemKey=key+index;if(!checked.has(itemKey))checked.set(itemKey,true);
          const check=el('input',{type:'checkbox',checked:checked.get(itemKey),'aria-label':'采用 '+item.title,disabled:!canWrite(),onchange:e=>checked.set(itemKey,e.target.checked)});
          section.append(el('div',{class:'proposal-item'},el('div',{class:'row'},canWrite()&&el('label',{class:'field-check'},check),el('strong',{class:'grow'},item.title||'未命名候选'),canWrite()&&button('修改',()=>editProposalItem(key,item,edited=>{copy[key][index]=edited;renderRows();}),{class:'small ghost',icon:'edit'})),item.body&&el('p',{},item.body),key==='tasks'&&item.criteria&&el('p',{},'验收：'+item.criteria),key==='tasks'&&item.due_date&&el('p',{},'截止：'+item.due_date),key==='events'&&el('p',{},stamp(item.starts_at)),item.source_seq&&el('p',{},'来源消息 #'+item.source_seq)));
        });rows.append(section);
      }
      if(copy.conflicts?.length)rows.append(el('section',{class:'proposal-section'},el('h4',{},'待核实冲突'),copy.conflicts.map(x=>el('p',{class:'notice'},x.description||JSON.stringify(x)))));
      if(!copy.tasks.length&&!copy.events.length&&!copy.decisions.length)rows.append(el('p',{class:'notice neutral',style:'margin-top:14px'},'本轮没有提取到明确的任务、安排或决定。纪要已保留，确认后将收起此卡。'));
    };renderRows();
    if(canWrite()){
      const error=el('div');
      const adopt=button('采用勾选内容',async()=>{
        adopt.disabled=true;ignore.disabled=true;error.replaceChildren();
        try{
          const body={expected_revision:copy.revision};
          for(const key of ['tasks','events','decisions'])body[key]=copy[key].filter((_,i)=>checked.get(key+i));
          const updated=await api('/proposals/'+copy.id,{method:'PATCH',body});copy.revision=updated.revision;
          await api('/proposals/'+copy.id+'/adopt',{method:'POST',body:{expected_revision:copy.revision}});
          dlg.close();await refresh();toast('已采用，任务、安排与决定已写入项目');
        }catch(e){error.append(el('div',{class:'form-error'},e.message));adopt.disabled=false;ignore.disabled=false;}
      },{class:'primary',icon:'check'});
      const ignore=button('仅保留纪要',async()=>{
        ignore.disabled=true;adopt.disabled=true;
        try{await api('/proposals/'+copy.id,{method:'PATCH',body:{expected_revision:copy.revision,status:'dismissed'}});dlg.close();await refresh();toast('纪要已保留，候选项未创建');}
        catch(e){error.append(el('div',{class:'form-error'},e.message));ignore.disabled=false;adopt.disabled=false;}
      });
      card.append(error,el('div',{class:'row wrap',style:'margin-top:20px'},adopt,ignore));
    }root.append(card);
  }
}
function editProposalItem(kind,item,onSave) {
  const fields=[field('title','标题','text',item.title||'',{attrs:{required:true,maxlength:200}}),field('body','内容与依据','textarea',item.body||'',{attrs:{maxlength:30000}})];
  if(kind==='tasks')fields.push(field('criteria','验收标准','textarea',item.criteria||''),el('div',{class:'field-row'},field('executor','执行方式','select',item.executor||'human',{choices:[['human','人工'],['ai','AI'],['collab','人机协作']]}),field('due_date','截止日期','date',item.due_date||'')));
  if(kind==='events')fields.push(field('kind','安排类型','select',item.kind||'meeting',{choices:[['meeting','会议'],['milestone','里程碑']]}),field('starts_at','开始时间（包含时区）','text',item.starts_at||'',{attrs:{required:true},help:'例如 2026-10-23T10:00:00+08:00'}),field('ends_at','结束时间（包含时区，可留空）','text',item.ends_at||''));
  fields.push(field('source_seq','来源消息序号','number',item.source_seq||'',{attrs:{min:1}}));
  formDialog('修改候选'+({tasks:'任务',events:'安排',decisions:'决定'}[kind]),fields,async v=>{
    const result={...item,...v,source_seq:v.source_seq?Number(v.source_seq):null};
    if(kind==='tasks')result.due_date=v.due_date||null;
    if(kind==='events')result.ends_at=v.ends_at||null;
    onSave(result);
  },{submit:'保留修改',description:'修改会在采用整张结果卡时一并保存。'});
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.project){clearTimeout(state.timer);poll();}});
window.addEventListener('online',()=>{if(state.project){clearTimeout(state.timer);poll();}});
window.addEventListener('unhandledrejection',e=>{if(e.reason?.name==='AbortError'){e.preventDefault();return;}console.error(e.reason);toast(e.reason?.message||'操作未完成，请重试',true);});
// Workspace 0.2: task rooms with people, one assistant, context and outputs.
const oldTaskDialog=taskDialog,oldRenderView=renderView,oldDocumentDialog=documentDialog,oldRefresh=refresh;
Object.assign(state,{workspaces:[],workspace:null,screen:'company',companyView:'overview',task:null,overview:null,knowledgeFilter:'all'});
const companyViews=[['overview','工作台','plan'],['projects','项目','tasks'],['calendar','日程','calendar'],['knowledge','知识与记忆','files']];
const companyPath=s=>'/workspaces/'+encodeURIComponent(state.workspace.id)+(s||'');
const taskPath=s=>'/tasks/'+encodeURIComponent(state.task.id)+(s||'');
function companyOwner(){return state.workspace?.role==='owner';}
function companyProjects(){return state.projects.filter(p=>p.workspace_id===state.workspace?.id);}
function closeDialogs(){document.querySelectorAll('dialog').forEach(d=>d.remove());}
function resetView(){state.controller?.abort();clearTimeout(state.timer);state.controller=new AbortController();state.generation++;state.task=null;state.messages=[];state.lastSeq=0;state.running=null;state.draft='';state.search='';closeDialogs();}
loadProjects=async function(preferred){
 const [ws,ps]=await Promise.all([api('/workspaces'),api('/projects')]);state.workspaces=ws.items;state.projects=ps.items;
 const hash=new URLSearchParams(location.hash.slice(1)),pid=preferred||hash.get('project'),p=state.projects.find(x=>x.id===pid);
 state.workspace=state.workspaces.find(w=>w.id===(p?.workspace_id||hash.get('workspace')||state.workspace?.id))||state.workspaces[0];renderShell();
 if(p){await selectProject(p.id);if(hash.get('task'))await openTask(hash.get('task'),p.id);}else await showCompany(hash.get('view')||'overview');
};
renderShell=function(){
 const picker=el('select',{class:'workspace-switch','aria-label':'当前公司或团队',onchange:async e=>{state.workspace=state.workspaces.find(w=>w.id===e.target.value);await showCompany('overview');}},state.workspaces.map(w=>el('option',{value:w.id,selected:w.id===state.workspace?.id},w.name)));
 const sidebar=el('aside',{class:'sidebar','aria-label':'公司导航'},brand(),el('div',{class:'company-picker'},el('small',{},'公司 / 团队'),picker),el('nav',{class:'company-nav','aria-label':'公司功能'},companyViews.map(([id,label,ic])=>el('button',{type:'button','data-company-view':id,class:'company-link',onclick:()=>showCompany(id).catch(handle)},icon(ic),label))),el('div',{class:'row spread sidebar-caption'},el('span',{},'项目'),iconButton('plus','新建项目',newProject)),el('div',{class:'project-list',id:'project-list'}),el('div',{class:'sidebar-footer'},button('团队设置',companySettings,{icon:'users',class:'ghost'}),el('div',{class:'row'},avatar(state.user?.display_name||state.user?.username),el('span',{class:'grow account-name'},state.user?.display_name||state.user?.username),iconButton('moon','切换明暗外观',toggleTheme),iconButton('logout','退出登录',()=>logout())),el('p',{class:'sidebar-note'},'一起讨论，让团队记住。')));
 const shell=el('div',{class:'app-shell'},sidebar,el('div',{class:'sidebar-scrim',onclick:()=>shell.classList.remove('sidebar-open')}),el('main',{class:'workspace',id:'workspace',tabindex:'-1'}));app.replaceChildren(shell);renderProjectList();
};
renderProjectList=function(){
 const node=$('#project-list');if(!node)return;
 node.replaceChildren(...companyProjects().map(p=>el('button',{class:'project-button'+(state.screen==='project'&&state.project?.id===p.id?' active':''),type:'button',onclick:()=>selectProject(p.id).catch(handle)},icon('plan',15),el('span',{},p.title))));
 if(!companyProjects().length)node.append(el('p',{class:'muted',style:'padding:0 12px;font-size:12px'},'还没有项目'));
 document.querySelectorAll('[data-company-view]').forEach(n=>n.classList.toggle('active',state.screen==='company'&&n.dataset.companyView===state.companyView));
};
function companyHeader(title,description){return el('header',{class:'project-header'},el('div',{class:'eyebrow'},state.workspace.name+' / 团队工作空间'),el('div',{class:'project-title-row'},el('div',{class:'row grow'},iconButton('menu','打开公司导航',toggleLeftSidebar),el('h1',{},title)),button('刷新',()=>showCompany(state.companyView),{icon:'refresh',class:'ghost'})),el('p',{class:'project-goal'},description));}
async function showCompany(view='overview'){
 if(!companyViews.some(v=>v[0]===view))view='overview';resetView();state.screen='company';state.companyView=view;state.project=null;state.tab='tasks';renderShell();
 const gen=state.generation,title=companyViews.find(v=>v[0]===view)[1],descriptions={overview:'以公司为边界管理项目，以任务为入口展开人和 AI 的协作。',projects:'先明确项目目标，再进入任务讨论。',calendar:'汇总你有权访问的项目期限、会议与里程碑。',knowledge:'对话不是终点：让决定、成果与依据成为下一次工作的起点。'};
 $('#workspace').append(companyHeader(title,descriptions[view]),el('section',{class:'content',id:'content'},el('p',{class:'muted'},'正在载入…')));history.replaceState({},'','#workspace='+state.workspace.id+'&view='+view);
 try{const data=await api(companyPath('/overview?view='+view),{signal:state.controller.signal});if(gen!==state.generation)return;state.overview=data;renderCompanyContent();}catch(e){if(e.name!=='AbortError')$('#content')?.replaceChildren(el('div',{class:'form-error'},e.message));}
}
function projectTile(p){const tasks=state.overview?.tasks.filter(t=>t.project_id===p.id)||[];return el('button',{type:'button',class:'project-tile',onclick:()=>selectProject(p.id).catch(handle)},el('div',{class:'row spread'},icon('plan',20),p.title.includes('示例')&&badge('示例','warning')),el('h3',{},p.title),el('p',{},p.goal||'从一个明确目标开始'),el('small',{},tasks.length+' 个任务 · '+tasks.filter(t=>t.status==='done').length+' 个已完成'));}
function memoryTile(d){return el('button',{type:'button',class:'doc-card',onclick:()=>openKnowledge(d).catch(handle)},el('div',{class:'row spread'},badge(d.kind==='company'?'公司公共知识':d.kind),badge(d.adopted?'已采用':'待核对',d.adopted?'success':'')),el('h3',{},d.title),el('div',{class:'doc-card-preview'},d.body?.slice(0,160)||'原件已保存，等待解析'),el('div',{class:'doc-card-meta'},el('span',{},d.project_title||state.project?.title||'公司公共库'),el('span',{},'v'+d.revision)),(d.task_id||d.source?.task_id)&&el('small',{class:'source-line'},'可追溯到来源任务'));}
function taskRow(t){return el('button',{class:'work-row',type:'button',onclick:()=>openTask(t.id,t.project_id).catch(handle)},icon('tasks'),el('div',{class:'grow'},el('strong',{},t.title),el('small',{},t.project_title||state.project?.title||'')),badge(t.status),el('small',{},t.due_date||'未设期限'));}
function renderCompanyContent(){
 const d=state.overview,c=$('#content');c.replaceChildren();
 if(state.companyView==='projects'){c.append(el('div',{class:'view-head'},el('h2',{},'公司的项目'),button('新建项目',newProject,{class:'primary',icon:'plus'})),el('div',{class:'project-grid'},d.projects.map(projectTile)));if(!d.projects.length)c.append(empty('创建第一个项目','公司可以有多个项目。具体讨论始终归属任务。','plan',button('新建项目',newProject,{class:'primary'})));return;}
 if(state.companyView==='calendar'){renderCompanyCalendar(c,d.calendar);return;}
 if(state.companyView==='knowledge'){renderCompanyKnowledge(c,d);return;}
 c.append(el('div',{class:'dashboard-stats'},[['项目',d.counts.projects],['任务',d.counts.tasks],['待验收',d.counts.pending_review],['已采用记忆',d.counts.memories]].map(([label,num])=>el('div',{class:'stat-card'},el('small',{},label),el('strong',{class:'stat-value'},num)))));
 c.append(el('div',{class:'view-head'},el('h2',{},'正在推进的项目'),button('新建项目',newProject,{icon:'plus',class:'primary'})),el('div',{class:'project-grid'},d.projects.slice(0,6).map(projectTile)));
 if(!d.projects.length)c.append(empty('先创建项目，再围绕任务讨论','你已属于 '+state.workspace.name+'。可在团队设置中修改公司名称。','plan'));
 c.append(el('div',{class:'dashboard-columns'},el('section',{class:'panel'},el('h3',{},'接下来做什么'),d.tasks.filter(t=>!['done','cancelled'].includes(t.status)).slice(0,8).map(taskRow),!d.tasks.length&&el('p',{class:'muted'},'项目任务会在这里汇总。')),el('section',{class:'panel'},el('h3',{},'团队最近记住了什么'),d.documents.filter(x=>x.adopted).slice(0,4).map(x=>el('button',{type:'button',class:'work-row',onclick:()=>openKnowledge(x).catch(handle)},icon('files'),el('div',{class:'grow'},el('strong',{},x.title),el('small',{},x.project_title)),badge(x.kind))),button('查看知识与记忆',()=>showCompany('knowledge'),{class:'ghost'}))));
}
function renderCompanyCalendar(c,items){
 const month=state.month,start=new Date(month.getFullYear(),month.getMonth(),1);start.setDate(start.getDate()-(start.getDay()+6)%7);
 c.append(el('div',{class:'view-head'},el('h2',{},new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long'}).format(month)),el('div',{class:'row'},iconButton('back','上个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()-1,1);renderCompanyContent();}),button('本月',()=>{state.month=new Date();renderCompanyContent();},{class:'ghost'}),iconButton('chevron','下个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()+1,1);renderCompanyContent();}))));
 const grid=el('div',{class:'calendar-grid'},['一','二','三','四','五','六','日'].map(x=>el('div',{class:'calendar-day-name'},x)));
 for(let i=0;i<42;i++){const day=new Date(start);day.setDate(day.getDate()+i);const key=day.getFullYear()+'-'+String(day.getMonth()+1).padStart(2,'0')+'-'+String(day.getDate()).padStart(2,'0');const cell=el('div',{class:'calendar-day'+(day.getMonth()!==month.getMonth()?' other-month':'')},el('span',{class:'calendar-date'},day.getDate()));items.filter(x=>datePart(x.starts_at)===key).slice(0,4).forEach(x=>cell.append(el('button',{class:'calendar-event',title:x.project_title+' · '+x.title,onclick:()=>openSchedule(x)},x.title)));grid.append(cell);}
 c.append(el('section',{class:'panel'},grid),el('h3',{style:'margin-top:24px'},'跨项目安排'),el('section',{class:'panel'},items.slice(0,30).map(x=>el('button',{type:'button',class:'work-row',onclick:()=>openSchedule(x)},icon('calendar'),el('div',{class:'grow'},el('strong',{},x.title),el('small',{},x.project_title+' · '+x.starts_at)),badge(x.kind)))));
 if(!items.length)c.append(empty('暂无安排','在项目任务中填写截止日期，或添加会议和里程碑，即会汇总到这里。','calendar'));
}
async function openSchedule(x){await selectProject(x.project_id);if(x.kind==='task')await openTask(x.id,x.project_id);else eventDialog(x);}
function renderCompanyKnowledge(c,d){
 c.append(el('div',{class:'knowledge-pipeline'},[['原始资料',d.counts.files],['讨论纪要',d.counts.summaries],['验收与采用记忆',d.counts.memories],['公司公共知识',d.counts.public_knowledge]].map(([title,n],i)=>el('div',{},el('small',{},String(i+1).padStart(2,'0')+' / '+title),el('strong',{},n)))));
 c.append(el('p',{class:'notice neutral'},'原件自动归档，纪要保留分歧，确认后的决定与验收成果成为项目记忆。只有明确发布的快照才进入公司公共库；不把所有人的私有聊天混在一起。'));
 const search=el('input',{class:'input',type:'search',placeholder:'按标题、正文或项目查找…','aria-label':'搜索团队知识'}),filters=el('div',{class:'row wrap'}),results=el('div',{class:'doc-grid'});
 const render=()=>{const q=search.value.trim().toLowerCase(),choices={all:[...d.public_knowledge,...d.documents],memory:d.documents.filter(x=>x.adopted&&x.status==='ready'),summary:d.documents.filter(x=>x.kind==='summary'),company:d.public_knowledge},rows=choices[state.knowledgeFilter]||choices.all;results.replaceChildren(...rows.filter(x=>(x.title+' '+x.body+' '+(x.project_title||'')).toLowerCase().includes(q)).map(memoryTile));if(!results.children.length)results.append(empty('暂无匹配内容','先上传资料，或在任务中完成一次整理和验收。','files'));};
 for(const [v,l] of [['all','全部资料'],['memory','项目记忆'],['summary','讨论纪要'],['company','公司公共知识']])filters.append(button(l,()=>{state.knowledgeFilter=v;filters.querySelectorAll('button').forEach(n=>n.classList.toggle('primary',n.textContent===l));render();},{class:state.knowledgeFilter===v?'primary':'ghost'}));
 search.addEventListener('input',render);c.append(el('div',{class:'knowledge-toolbar'},filters,search),results);render();
}
async function openKnowledge(d){
 if(d.kind==='company'||d.id.startsWith('k_')){const doc=await api('/knowledge/'+d.id),content=el('div',{},el('div',{class:'row wrap'},badge('公司公共知识','accent'),badge('v'+doc.revision),badge('已明确发布')),el('p',{class:'source-line'},'独立快照 · 发布后不随原项目静默改写'),markdown(doc.body));const actions=[];
 const p=state.projects.find(x=>x.id===doc.source?.project_id);if(p&&doc.source?.task_id)actions.push(button('回到来源任务',()=>{dlg.close();openTask(doc.source.task_id,p.id).catch(handle);},{icon:'link'}));
 if(companyOwner())actions.push(button('撤回公开',()=>confirmAction('撤回公司公共知识','新检索将不再使用这条快照；原项目资料保留。',async()=>{await api(companyPath('/knowledge/'+doc.id),{method:'DELETE'});dlg.close();await showCompany('knowledge');}),{class:'danger'}));
 const dlg=openDialog(doc.title,content,{wide:true,actions});return;}
 if(!state.project||state.project.id!==d.project_id)await selectProject(d.project_id);await documentDialog(d.id);
}
selectProject=async function(id){
 resetView();state.screen='project';state.tab='tasks';const gen=state.generation,project=await api('/projects/'+encodeURIComponent(id),{signal:state.controller.signal});if(gen!==state.generation)return;state.project=project;state.workspace=state.workspaces.find(w=>w.id===state.project.workspace_id)||state.workspace;renderShell();
 $('#workspace').append(header(),el('section',{class:'content',id:'content'}));await initialData(gen);if(gen!==state.generation)return;renderView();updateHash();schedulePoll();
};
header=function(){
 const p=state.project,t=state.task,tabs=t?[['discussion','任务讨论','chat'],['task-memory','相关沉淀','files']]:[['tasks','项目任务','tasks'],['calendar','项目日程','calendar'],['documents','项目资料','files']];
 return el('header',{class:'project-header'},el('div',{class:'breadcrumbs'},button(state.workspace.name,()=>showCompany('overview'),{class:'ghost small'}),el('span',{},'/'),button(p.title,()=>selectProject(p.id),{class:'ghost small'}),t&&el('span',{},'/ 任务')),
 el('div',{class:'project-title-row'},el('div',{class:'row grow'},iconButton('menu','打开公司导航',toggleLeftSidebar),el('h1',{},t?t.title:p.title)),el('div',{class:'row'},t?button('任务详情',()=>oldTaskDialog(state.task),{icon:'edit',class:'ghost'}):button('项目规划',planDialog,{icon:'plan',class:'ghost'}),button('设置',()=>settingsDialog(),{icon:'settings',class:'ghost',title:'项目设置'}))),
 el('p',{class:'project-goal'},t?'所属项目：'+p.title+' · '+(labels[t.status]||t.status)+' · 负责人：'+memberName(t.assignee_id)+(t.due_date?' · 截止 '+t.due_date:''):p.goal||'先明确项目目标，再拆分任务。'),
 el('nav',{class:'tabs','aria-label':'项目内容'},tabs.map(([id,label,ic])=>el('button',{type:'button',class:'tab'+(state.tab===id?' active':''),onclick:()=>switchTab(id)},icon(ic,16),label)),el('div',{class:'tab-extra'},el('span',{class:'dot',id:'connection-dot'}),el('span',{id:'connection-label',class:'connection-label'},'已同步'),badge(p.role))));
};
async function openTask(id,projectId){
 if(!state.project||state.project.id!==projectId){await selectProject(projectId);if(state.project?.id!==projectId||state.screen!=='project')return;}
 state.controller?.abort();clearTimeout(state.timer);state.controller=new AbortController();state.generation++;closeDialogs();
 const gen=state.generation,signal=state.controller.signal;state.task=null;
 const task=await api('/tasks/'+id,{signal});if(gen!==state.generation||state.project?.id!==projectId)return;
 state.task=task;state.tab='discussion';state.messages=[];state.lastSeq=0;state.draft='';state.pendingRunPayload=null;state.messageClient=crypto.randomUUID();state.running=null;
 $('.project-header')?.replaceWith(header());renderView();await fetchMessages(gen);if(gen!==state.generation)return;updateHash();schedulePoll();
}
fetchMessages=async function(generation=state.generation){
 if(!state.task)return;const tid=state.task.id;let more=true,guard=0;
 while(more&&guard++<20){const result=await api('/tasks/'+tid+'/messages?after='+state.lastSeq,{signal:state.controller.signal});if(generation!==state.generation)return;const old=new Set(state.messages.map(m=>m.id)),incoming=result.items.filter(m=>!old.has(m.id));state.messages.push(...incoming);state.lastSeq=state.messages.reduce((n,m)=>Math.max(n,m.seq),state.lastSeq);state.running=result.running;if(state.tab==='discussion')appendMessages(incoming);more=result.has_more;}
};
updateHash=function(){if(state.project)history.replaceState({},'','#workspace='+state.workspace.id+'&project='+state.project.id+(state.task?'&task='+state.task.id:'')+'&tab='+state.tab);};
renderView=function(){
 if(state.screen!=='project')return;const c=$('#content');if(!c)return;if(state.tab==='discussion'&&!state.task)state.tab='tasks';
 if(state.tab==='task-memory'){c.className='content';c.replaceChildren(el('div',{class:'view-head'},el('div',{},el('h2',{},'这项任务留下了什么'),el('p',{},'原始资料、纪要、决定和验收结果都保留来源。'))));const docs=state.documents.filter(d=>d.task_id===state.task?.id||d.task_ids?.includes(state.task?.id));c.append(el('div',{class:'doc-grid'},docs.map(memoryTile)));if(!docs.length)c.append(empty('这项任务尚未沉淀内容','上传附件、整理讨论或完成任务验收后，会出现在这里。','files'));return;}
 oldRenderView();if(state.tab==='discussion'&&state.task){const t=state.task,left=el('section',{class:'task-chat'});while(c.firstChild)left.append(c.firstChild);c.append(el('div',{class:'task-room'},left,taskContextPanel()));$('.discussion-top span',left).textContent=state.members.length+' 位项目成员 + 项目助手';$('.discussion-top button',left).textContent='整理任务讨论';}
};
function taskContextPanel(){
 const t=state.task,docs=state.documents.filter(d=>d.task_id===t.id||d.task_ids?.includes(t.id)),pending=state.proposals.filter(p=>p.status==='pending'&&p.task_id===t.id);
 return el('aside',{class:'task-context','aria-label':'任务上下文与记忆'},el('div',{class:'context-section'},el('h3',{},'一起协作'),el('div',{class:'participants'},state.members.map(m=>el('span',{class:'participant',title:m.display_name},avatar(m.display_name),el('small',{},m.display_name))),el('span',{class:'participant'},avatar('AI',true),el('small',{},'项目助手'))),el('p',{class:'help'},'AI 在请求时参与；不会自动替你确认决定。')),
 el('div',{class:'context-section'},el('h3',{},'当前任务'),badge(t.status),el('p',{},t.body||'尚未填写说明'),el('small',{},'验收标准'),el('p',{},t.criteria||'请补充可核对的验收标准'),button('编辑任务',()=>oldTaskDialog(t),{class:'small ghost',icon:'edit'})),
 el('div',{class:'context-section'},el('h3',{},'共同记忆与产物'),docs.slice(0,5).map(d=>el('button',{class:'context-memory',type:'button',onclick:()=>documentDialog(d.id)},icon('files',14),el('span',{},d.title),badge(d.kind))),!docs.length&&el('p',{class:'muted'},'从一次上传、整理或验收开始。'),pending.length>0&&button('待采用结果 · '+pending.length,proposalDialog,{class:'small'}),button('查看全部沉淀',()=>switchTab('task-memory'),{class:'ghost small'})),
 el('div',{class:'context-section'},el('h3',{},'助手上下文'),el('p',{},'当前任务讨论 + 项目资料 + 已发布公司知识'),el('small',{},state.settings?.model||'尚未配置模型'),el('div',{class:'row wrap'},(state.settings?.skills||[]).filter(s=>s.enabled).map(s=>badge(s.name+' v'+s.revision)))));
}
taskCard=function(t){return el('button',{type:'button',class:'task-card',onclick:()=>openTask(t.id,t.project_id).catch(handle)},el('div',{class:'row wrap'},badge(t.executor||'human'),t.blocked&&badge('阻塞','warning'),t.parent_id&&badge('子任务'),t.system_thread&&badge('历史兼容')),el('div',{class:'task-title'},t.title),el('div',{class:'task-card-meta'},el('span',{},memberName(t.assignee_id)),el('span',{},t.due_date||'无截止日期')),el('small',{class:'task-open-hint'},'打开任务与讨论 →'));};
newProject=function(){if(!state.workspace)return;formDialog('新建项目',[field('title','项目名称','text','',{attrs:{required:true,maxlength:120}}),field('goal','共同目标','textarea','',{attrs:{maxlength:4000}})],async v=>{const p=await api('/projects',{method:'POST',body:{...v,workspace_id:state.workspace.id,timezone:'Asia/Shanghai'}});state.projects.unshift(p);await selectProject(p.id);toast('项目已创建，请添加具体任务');},{submit:'创建项目',description:'属于 '+state.workspace.name+'。项目下的任务承载实际讨论与产物。'});};
refresh=async function(){if(state.screen==='company'){await showCompany(state.companyView);return;}await oldRefresh();if(state.task){state.task=state.tasks.find(t=>t.id===state.task.id)||state.task;$('.project-header')?.replaceWith(header());renderView();}};
sendMessage=async function(withAI){
 if(!state.task){toast('请先进入一个具体任务',true);return;}const text=state.draft.trim();if(!text&&!withAI)return;const gen=state.generation,tid=state.task.id,controls=$('.composer'),buttons=[...controls.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);let request=null;
 try{if(text){await api('/tasks/'+tid+'/messages',{method:'POST',body:{content:text,client_id:state.messageClient}});if(gen!==state.generation)return;state.draft='';$('.composer textarea').value='';state.messageClient=crypto.randomUUID();await fetchMessages(gen);}
 if(withAI){request=state.pendingRunPayload&&!text?state.pendingRunPayload:{kind:'chat',prompt:text,client_id:crypto.randomUUID()};state.pendingRunPayload=request;await api('/tasks/'+tid+'/runs',{method:'POST',body:request});if(gen!==state.generation)return;state.pendingRunPayload=null;toast('项目助手正在处理，回复会留在此任务讨论里');await fetchMessages(gen);}}
 catch(e){if(request&&e.status&&e.status<500)state.pendingRunPayload=null;handle(e);}finally{if(gen===state.generation)buttons.forEach(b=>b.disabled=!canWrite());}
};
startRun=async function(kind,taskId=null,prompt=''){
 const tid=taskId||state.task?.id;if(!tid){toast('请先打开一个任务，再请求 AI',true);return;}
 try{await api('/tasks/'+tid+'/runs',{method:'POST',body:{kind,task_id:tid,prompt,client_id:crypto.randomUUID()}});toast(kind==='summary'?'正在整理当前任务；正式变更仍待采用':'AI 已开始执行，产物先进入待验收');await refresh();}catch(e){handle(e);}
};
documentDialog=async function(id){
 if(id.startsWith('k_')){await openKnowledge({id,kind:'company'});return;}
 await oldDocumentDialog(id);const d=state.documents.find(x=>x.id===id),dialog=document.querySelector('dialog[open]');if(!d||!dialog)return;
 const extra=el('div',{class:'source-chain'},el('strong',{},'沉淀来处'),el('span',{},state.project.title+' → '+(d.task_id?'任务':'项目资料')+' → '+(labels[d.kind]||d.kind)+(d.adopted?' → 已采用':'')));
 if(d.task_id)extra.append(button('回到来源任务',()=>openTask(d.task_id,d.project_id).catch(handle),{class:'small',icon:'link'}));
 if(d.adopted&&d.status==='ready'&&companyOwner()&&isOwner())extra.append(button('发布到公司知识',()=>confirmAction('发布给整个公司／团队','发布当前正文快照。团队其他成员即使不属于原项目，也可读取这份快照；原项目附件不会一并开放。',async()=>{await api(companyPath('/knowledge/publish'),{method:'POST',body:{document_id:d.id,expected_revision:d.revision}});toast('已发布公司公共知识，可在其他项目检索');}),{class:'small',icon:'users'}));
 const target=dialog.querySelector('.document-detail-body')?.parentElement||dialog;target.append(extra);
};
async function companySettings(){
 try{const w=state.workspace,list=await api(companyPath('/members')),content=el('div',{},el('p',{class:'notice neutral'},'账号可以加入公司／团队；项目仍保持独立成员权限。公司成员不会自动获得全部项目的读取权。'),el('h3',{},w.name));
 list.items.forEach(m=>content.append(el('div',{class:'list-row'},avatar(m.display_name),el('div',{class:'grow'},el('strong',{},m.display_name),el('small',{},m.username)),badge(m.role))));
 const actions=[button('创建另一个团队',()=>{dlg.close();formDialog('创建公司／团队',[field('name','公司／团队名称','text','',{attrs:{required:true}})],async v=>{const nw=await api('/workspaces',{method:'POST',body:v});state.workspaces.push(nw);state.workspace=nw;await showCompany('overview');},{submit:'创建团队'});},{class:'ghost'})];
 if(companyOwner())actions.push(button('修改团队名称',()=>{dlg.close();formDialog('公司／团队设置',[field('name','公司／团队名称','text',w.name,{attrs:{required:true,maxlength:120}}),field('description','简介','textarea',w.description||'')],async v=>{const nw=await api(companyPath(),{method:'PATCH',body:{...v,expected_revision:w.revision}});Object.assign(state.workspace,nw);await showCompany('overview');});},{class:'primary'}));
 const dlg=openDialog('团队设置',content,{wide:true,actions});}catch(e){handle(e);}
}

// Agent 0.3: explicit identity selection, typed mentions, native streaming + trace.
Object.assign(state,{capabilities:[],agentId:null,mentionDocs:[],agentLive:null,agentSSE:null,mentionIndex:0,mentionItems:[]});
const agentBaseInitial=initialData,agentBaseReset=resetView,agentBaseOpenTask=openTask,agentBaseContext=taskContextPanel,agentBaseDiscussion=renderDiscussion,agentBaseRunning=renderRunning,agentBaseMessage=messageElement,agentBaseDocument=documentDialog;
const agentNames={agent:'Agent',skill:'Skill',mcp:'MCP'};
const agentBaseLogout=logout;logout=function(show=true){abortAgentStream();agentBaseLogout(show);};
const selectedAgent=()=>state.capabilities.find(a=>a.id===state.agentId&&a.enabled);
async function reloadCapabilities(){if(!state.project)return;const p=state.project.id;const r=await api('/projects/'+p+'/capabilities');if(state.project?.id===p){state.capabilities=r.items||[];if(!selectedAgent())state.agentId=null;}}
initialData=async function(gen){await agentBaseInitial(gen);if(gen!==state.generation)return;await reloadCapabilities();};
function abortAgentStream(){state.agentSSE?.abort();state.agentSSE=null;state.agentLive=null;}
resetView=function(){hideMentionPicker();abortAgentStream();state.agentId=null;state.mentionDocs=[];state.capabilities=[];agentBaseReset();};
openTask=async function(id,p){hideMentionPicker();abortAgentStream();state.agentId=null;state.mentionDocs=[];await agentBaseOpenTask(id,p);};
function refreshAgentControls(){
 const chips=$('#agent-mention-chips'),a=selectedAgent();if(chips){chips.replaceChildren();if(a)chips.append(el('span',{class:'mention-chip agent'},icon('spark',13),'@'+a.name,iconButton('close','取消选择Agent',()=>{state.agentId=null;refreshAgentControls();})));for(const d of state.mentionDocs)chips.append(el('span',{class:'mention-chip'},icon('files',13),d.title+' · v'+d.revision,iconButton('close','移除引用 '+d.title,()=>{state.mentionDocs=state.mentionDocs.filter(x=>x.id!==d.id);refreshAgentControls();})));}
 const send=$('#agent-send-button');if(send)send.textContent=a?'发送给 @'+a.name:'发送';
 const select=$('#task-agent-select');if(select)select.value=a?.id||'';
 const people=$('.participants');if(people){const seen=new Map();for(const m of state.messages)if(m.agent_id)seen.set(m.agent_id,m.agent_name||m.author_name);if(a)seen.set(a.id,a.name);people.replaceChildren(...state.members.map(m=>el('span',{class:'participant',title:m.display_name},avatar(m.display_name),el('small',{},m.display_name))),...[...seen].slice(-4).map(([id,name])=>el('span',{class:'participant',title:name},avatar(name,true),el('small',{},name))));}
 const top=$('.discussion-top>span');if(top)top.textContent=state.members.length+' 位成员 · 通过 @ 邀请 AI 员工';
 const detail=$('#agent-current-info');if(detail)detail.textContent=a?((a.data.model||state.settings?.model||'未绑定模型')+' · v'+a.revision+' · '+a.data.skill_ids.length+' Skills · '+a.data.mcp_ids.length+' MCP'):'通过 @ 或此处邀请一位 AI 员工';
}
function pickAgent(id){state.agentId=id||null;refreshAgentControls();}
taskContextPanel=function(){
 const panel=agentBaseContext();panel.lastElementChild?.remove();
 const section=el('section',{class:'context-section agent-config-section'},el('div',{class:'row spread'},el('h3',{},'参与本次任务的 Agent'),badge('单 Agent')));
 const select=el('select',{class:'input',id:'task-agent-select','aria-label':'选择任务Agent',onchange:e=>pickAgent(e.target.value)},el('option',{value:''},'@ 选择一个 Agent…'),state.capabilities.filter(a=>a.kind==='agent'&&a.enabled).map(a=>el('option',{value:a.id,selected:a.id===state.agentId},a.name)));
 section.append(select,el('p',{id:'agent-current-info',class:'help',style:'margin:10px 0'},selectedAgent()?.data.model||'提示词、模型、技能和执行权限分别配置'),el('div',{class:'row wrap'},button('配置 Agent',()=>selectedAgent()?agentEditor(selectedAgent()):capabilityLibrary('agent'),{class:'small',icon:'settings'}),button('能力库',()=>capabilityLibrary('agent'),{class:'small ghost',icon:'plan'})),el('p',{class:'help'},'没有选择 Agent 时，只发送真人消息。每次执行保留所用配置版本。'));
 panel.prepend(section);
 const advanced=el('details',{class:'context-section trace-advanced'},el('summary',{},'高级 · 执行 Trace'),el('p',{class:'help'},'真人 → 输入 → Agent → 模型 → 工具 → 产物。仅记录可审核执行事件，不展示隐藏推理。'),el('div',{id:'task-trace-list'}));panel.append(advanced);queueMicrotask(()=>{refreshAgentControls();refreshTraceList();});return panel;
};
renderDiscussion=function(content){
 agentBaseDiscussion(content);const composer=$('.composer',content);if(!composer)return;
 [...composer.querySelectorAll('button')].find(b=>b.textContent==='请 AI 回答')?.remove();
 const send=[...composer.querySelectorAll('button')].find(b=>b.textContent==='发送');if(send)send.id='agent-send-button';
 const chips=el('div',{id:'agent-mention-chips',class:'mention-chips'}),picker=el('div',{id:'mention-picker',class:'mention-picker',hidden:true,role:'listbox','aria-label':'选择Agent或文件'});
 composer.prepend(chips);composer.append(picker);$('.composer-bottom',composer)?.prepend(iconButton('settings','打开Agent能力库',()=>capabilityLibrary('agent')));$('.composer-bottom',composer)?.prepend(button('@',()=>showMentionPicker('',null),{class:'small mention-open',title:'@选择 Agent 或资料'}));
 const textarea=$('textarea',composer);textarea.placeholder='输入 @ 选择 Agent 或文件；不选择 Agent 就是团队留言';
 textarea.addEventListener('input',e=>{if(e.isComposing)return;const before=textarea.value.slice(0,textarea.selectionStart),match=before.match(/(?:^|\s)@([^\s@]*)$/);if(match)showMentionPicker(match[1],{start:before.length-match[1].length-1,end:before.length});else hideMentionPicker();});
 textarea.addEventListener('compositionend',()=>textarea.dispatchEvent(new Event('input')));
 textarea.addEventListener('keydown',handleMentionKeys,true);
 queueMicrotask(refreshAgentControls);
};
let mentionVersion=0,mentionRange=null;
function hideMentionPicker(){mentionVersion++;const box=$('#mention-picker');if(box)box.hidden=true;for(const n of document.querySelectorAll('[aria-controls="mention-picker"]')){n.setAttribute('aria-expanded','false');n.removeAttribute('aria-activedescendant');}}
function handleMentionKeys(e){
 const box=$('#mention-picker');if(!box||box.hidden||e.isComposing||e.keyCode===229)return;
 if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();hideMentionPicker();return;}
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();e.stopImmediatePropagation();state.mentionIndex=nextMentionIndex(state.mentionItems,state.mentionIndex,e.key==='ArrowDown'?1:-1);renderMentionResults();return;}
 if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.stopImmediatePropagation();selectMention(state.mentionItems[state.mentionIndex]);}
}
async function showMentionPicker(q='',range=null){
 const box=$('#mention-picker');if(!box||!state.task)return;
 const version=++mentionVersion,gen=state.generation,p=state.project.id,mode=range===null?'search':'inline';mentionRange=range;box.hidden=false;state.mentionItems=[];state.mentionIndex=-1;
 if(box.dataset.mode!==mode||!$('.mention-results',box)){
  box.dataset.mode=mode;box.replaceChildren();
  if(mode==='search'){
   const search=el('input',{class:'input',type:'search','aria-label':'搜索Agent或文件',placeholder:'输入名称查找…',value:q,'aria-controls':'mention-picker','aria-expanded':'true'});
   search.addEventListener('input',e=>{if(!e.isComposing)showMentionPicker(search.value,null);});search.addEventListener('compositionend',()=>showMentionPicker(search.value,null));search.addEventListener('keydown',handleMentionKeys,true);box.append(search);
  }
  box.append(el('div',{class:'mention-results'}));
 }
 const search=$('input',box);if(mode==='search'&&document.activeElement!==search){search.value=q;search.focus();}
 $('.mention-results',box).replaceChildren(el('p',{class:'muted'},'搜索 Agent 与项目资料…'));
 const control=mode==='search'?search:$('.composer textarea');control?.setAttribute('aria-controls','mention-picker');control?.setAttribute('aria-expanded','true');
 try{
  state.mentionFetch?.abort();const controller=new AbortController();state.mentionFetch=controller;const cancel=()=>controller.abort();state.controller.signal.addEventListener('abort',cancel,{once:true});let r;try{r=await api('/projects/'+p+'/mention-options?q='+encodeURIComponent(q),{signal:controller.signal});}finally{state.controller.signal.removeEventListener('abort',cancel);}
  if(version!==mentionVersion||gen!==state.generation||!box.isConnected)return;
  state.mentionItems=[...r.agents.map(a=>({...a,type:'agent',label:a.name})),...r.documents.map(d=>({...d,type:'document',label:d.title}))].slice(0,200);
  state.mentionIndex=nextMentionIndex(state.mentionItems,-1,1);renderMentionResults();
 }catch(e){if(e.name!=='AbortError'&&version===mentionVersion&&gen===state.generation&&box.isConnected)$('.mention-results',box)?.replaceChildren(el('p',{class:'form-error'},e.message));}
}
function renderMentionResults(){
 const root=$('.mention-results');if(!root)return;
 root.replaceChildren(...state.mentionItems.map((item,i)=>el('button',{type:'button',id:'mention-option-'+i,role:'option','aria-selected':i===state.mentionIndex,class:'mention-option'+(i===state.mentionIndex?' selected':''),disabled:item.type==='document'&&!item.usable,onmousedown:e=>e.preventDefault(),onclick:()=>selectMention(item)},icon(item.type==='agent'?'spark':'files',15),el('div',{class:'grow'},el('strong',{},item.label),el('small',{},item.type==='agent'?'Agent · v'+item.revision:((item.scope==='company'?'公司知识':'项目资料')+' · v'+item.revision+' · '+(item.usable?'可引用':labels[item.status]||item.status)+' · '+item.id.slice(-6)+(item.aliases?.filter(n=>n!==item.title).length?' · 又名：'+item.aliases.filter(n=>n!==item.title).join('、'):'')))))));
 if(!state.mentionItems.length)root.append(el('p',{class:'muted'},'没有匹配项；仅搜索当前项目和已发布公司资料。'));
 if(state.mentionItems.length>=60)root.append(el('p',{class:'help'},'候选较多，可继续输入名称缩小范围。'));
 const active=root.querySelector('.selected');active?.scrollIntoView({block:'nearest'});
 for(const n of document.querySelectorAll('[aria-controls="mention-picker"]')){if(active)n.setAttribute('aria-activedescendant',active.id);else n.removeAttribute('aria-activedescendant');}
}
function selectMention(item){if(!item)return;if(item.type==='document'&&!item.usable)return;
 if(item.type==='agent')state.agentId=item.id;else if(!state.mentionDocs.some(x=>x.id===item.id)){if(state.mentionDocs.length>=6){toast('一次最多明确引用六份资料',true);return;}state.mentionDocs.push(item);}
 const text=$('.composer textarea');if(text&&mentionRange){text.setRangeText('@'+item.label+' ',mentionRange.start,mentionRange.end,'end');state.draft=text.value;}hideMentionPicker();refreshAgentControls();text?.focus();}
function runSelection(){const a=selectedAgent();if(!a)throw new Error('请先用 @ 选择一个 Agent');return {agent_id:a.id,agent_revision:a.revision,document_ids:state.mentionDocs.map(d=>d.id),document_revisions:Object.fromEntries(state.mentionDocs.map(d=>[d.id,d.revision]))};}
sendMessage=async function(){
 if(!state.task)return;const text=state.draft.trim(),a=selectedAgent();if(!text&&!a)return;const gen=state.generation,tid=state.task.id,controls=$('.composer'),buttons=[...controls.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);let request=null;
 try{const selection=a?runSelection():null,mentions=[...(a?[{type:'agent',id:a.id}]:[]),...state.mentionDocs.map(d=>({type:'document',id:d.id}))];
 if(text){await api('/tasks/'+tid+'/messages',{method:'POST',body:{content:text,client_id:state.messageClient,mentions}});if(gen!==state.generation)return;state.draft='';$('.composer textarea').value='';state.messageClient=crypto.randomUUID();await fetchMessages(gen);}
 if(a){request=state.pendingRunPayload&&!text?state.pendingRunPayload:{kind:'chat',prompt:text,client_id:crypto.randomUUID(),...selection};state.pendingRunPayload=request;const run=await api('/tasks/'+tid+'/runs',{method:'POST',body:request});if(gen!==state.generation)return;state.pendingRunPayload=null;rememberStartedRun(run);followAgentRun(run.id);toast('@'+a.name+' 已开始执行');}
 state.agentId=null;state.mentionDocs=[];refreshAgentControls();await fetchMessages(gen);
 }catch(e){if(request&&e.status&&e.status<500)state.pendingRunPayload=null;handle(e);}finally{if(gen===state.generation)buttons.forEach(b=>b.disabled=!canWrite());}
};
startRun=async function(kind,taskId=null,prompt=''){
 const gen=state.generation,p=state.project?.id;
 try{const tid=taskId||state.task?.id;if(!tid)throw new Error('请先进入任务');const selection=runSelection();const r=await api('/tasks/'+tid+'/runs',{method:'POST',body:{kind,task_id:tid,prompt,client_id:crypto.randomUUID(),...selection}});if(gen!==state.generation||state.project?.id!==p||state.task?.id!==tid)return;rememberStartedRun(r);followAgentRun(r.id);toast('Agent 已开始'+(kind==='summary'?'整理当前任务':'产出待验收成果'));await fetchMessages(gen);}catch(e){if(gen!==state.generation)return;handle(e);if(e.message.includes('@'))showMentionPicker('',null);}
};
function refreshTraceList(){const root=$('#task-trace-list');if(!root||!state.task)return;const rows=state.runs.filter(r=>r.request?.task_id===state.task.id);root.replaceChildren(...rows.slice(0,8).map(r=>button((r.agent_name||'历史助手')+' · '+(labels[r.status]||r.status),()=>openTrace(r.id),{class:'trace-run small ghost',icon:'plan'})));if(!rows.length)root.append(el('p',{class:'help'},'选择 Agent 运行后，执行轨迹会出现在这里。'));}
renderRunning=function(){agentBaseRunning();refreshAgentControls();refreshTraceList();if(state.running&&state.task&&state.agentLive?.id!==state.running.id)followAgentRun(state.running.id);renderAgentLive();};
function renderAgentLive(){
 const slot=$('#run-slot');if(!slot)return;slot.querySelector('.live-agent-panel')?.remove();const live=state.agentLive;if(!live||live.task!==state.task?.id)return;
 const panel=el('div',{class:'live-agent-panel'},el('div',{class:'row spread'},el('strong',{},(live.name||'Agent')+' · '+(live.status||'执行中')),el('div',{class:'row'},button('Trace',()=>openTrace(live.id),{class:'small ghost'}),!live.done&&canWrite()&&(isOwner()||Number(live.actor)===Number(state.user?.id))&&button('停止',()=>confirmAction('停止本次 Agent','停止后不自动重发；已发生的模型用量仍然保留。',async()=>{await api(projectPath('/runs/'+live.id+'/cancel'),{method:'POST'});}),{class:'small danger'}))));
 if(live.text)panel.append(el('div',{class:'live-agent-text'},markdown(live.text)));
 for(const a of live.approvals.values())panel.append(el('div',{class:'tool-approval'},el('strong',{},'工具待批准：'+a.name),el('pre',{},JSON.stringify(a.arguments,null,2)),el('p',{class:'help'},a.scope==='platform'?'将按上述参数修改当前项目；确认仅针对这一次操作。':'外部工具将接收上述参数；允许只针对这一次调用。'),(isOwner()||Number(live.actor)===Number(state.user?.id))?button('允许本次',()=>approveTool(live.id,a.id,true),{class:'small primary'}):el('span',{class:'help'},'等待发起人或项目管理员确认'),(isOwner()||Number(live.actor)===Number(state.user?.id))&&button('拒绝',()=>approveTool(live.id,a.id,false),{class:'small'})));
 slot.append(panel);
}
async function approveTool(rid,id,approve){try{await api(projectPath('/runs/'+rid+'/approvals/'+id),{method:'POST',body:{approve}});state.agentLive?.approvals.delete(id);renderAgentLive();}catch(e){handle(e);}}
async function followAgentRun(id){
 if(!state.task||state.agentLive?.id===id)return;
 state.agentSSE?.abort();const control=new AbortController();state.agentSSE=control;
 const gen=state.generation,p=state.project.id,task=state.task.id;
 const live={id,task,actor:state.runs.find(r=>r.id===id)?.actor_id,name:state.runs.find(r=>r.id===id)?.agent_name||selectedAgent()?.name||'Agent',text:'',cursor:0,step:0,status:'正在连接流式输出',approvals:new Map(),done:false};state.agentLive=live;
 const current=()=>!control.signal.aborted&&gen===state.generation&&state.project?.id===p&&state.task?.id===task&&state.agentLive===live;
 for(let attempt=0;attempt<4&&current();attempt++){
  let reader=null;
  try{
   const response=await fetch(API+'/projects/'+p+'/runs/'+id+'/events?after='+live.cursor,{headers:{Authorization:'Bearer '+state.token,Accept:'text/event-stream'},signal:control.signal});
   if(!current())return;
   if([401,403,404].includes(response.status)){control.abort();state.agentLive=null;renderAgentLive();toast('运行访问权限已变化，请重新打开任务',true);return;}
   if(!response.ok)throw new Error('流式连接 HTTP '+response.status);
   reader=response.body.getReader();const decoder=new TextDecoder(),frames=new SSEFrames();let terminal=false;
   while(current()){
    const {value,done}=await reader.read();if(!current())return;if(done)break;
    for(const frame of frames.push(decoder.decode(value,{stream:true}))){
     const event=JSON.parse(frame.data),type=frame.event;
     if(type==='access_revoked'){control.abort();state.agentLive=null;renderAgentLive();await loadProjects();return;}
     if(type==='terminal'){live.done=true;live.approvals.clear();live.status=labels[event.status]||event.status;terminal=true;continue;}
     if(type!=='trace'||!Number.isInteger(event.seq)||event.seq<=live.cursor)continue;
     live.cursor=event.seq;const x=event.payload||{};
     if(event.event==='run.start')live.actor=x.actor_id;
     if(event.event==='agent.runtime'){live.name=x.name;live.status='Agent 已启动';}
     if(event.event==='model.start'){live.step=x.step;live.text='';live.status='模型步骤 '+x.step;}
     if(event.event==='output.delta'){live.text+=x.text||'';live.status='正在流式输出';}
     if(event.event==='tool.request')live.status='调用工具：'+x.name;
     if(event.event==='approval.required'){live.approvals.set(x.id,{...x,call_id:event.parent_span});live.status='等待工具批准';}
     if(event.event==='approval.decision')live.approvals.delete(x.approval_id);
     if(['tool.result','tool.denied','tool.error'].includes(event.event))for(const [aid,a] of live.approvals)if(a.call_id===event.span_id)live.approvals.delete(aid);
     if(event.event==='run.end')live.approvals.clear();
    }
    renderAgentLive();if(terminal)break;
   }
   if(terminal&&current()){
    await fetchMessages(gen);if(!current())return;
    const rr=await api('/projects/'+p+'/runs',{signal:control.signal});if(!current())return;
    state.runs=rr.items;state.agentLive=null;state.agentSSE=null;renderAgentLive();refreshTraceList();return;
   }
  }catch(e){if(!current())return;live.status='连接暂断，恢复流式记录中';renderAgentLive();}
  finally{if(reader){try{await reader.cancel();}catch{}reader.releaseLock();}}
  if(current())await new Promise(resolve=>setTimeout(resolve,500*(attempt+1)));
 }
 if(current()){live.status='流式连接已暂停；任务仍在服务端执行，可展开Trace或刷新查看';renderAgentLive();}
}
messageElement=function(m){const node=agentBaseMessage(m);if(m.agent_name)node.querySelector('.message-meta')?.append(badge('Agent v'+m.agent_revision,'accent'));if(m.mentions?.length)node.querySelector('.message-body')?.append(el('div',{class:'mention-chips'},m.mentions.map(x=>el('span',{class:'badge'},'@'+x.name+' · v'+x.revision))));if(m.run_id)node.querySelector('.message-actions')?.append(el('button',{type:'button',onclick:()=>openTrace(m.run_id)},'执行 Trace'));return node;};
async function openTrace(id){
 const p=state.project?.id;if(!p)return;
 const content=el('div'),summary=el('div',{class:'trace-overview'}),list=el('div',{class:'trace-events'}),filters=el('select',{class:'input','aria-label':'筛选Trace层级'},[['all','全部层级'],['human','真人'],['input','Input'],['agent','Agent'],['model','Model'],['tool','Tool'],['output','Output'],['control','状态与审批']].map(([v,label])=>el('option',{value:v},label)));
 let all=[],status='',loading=false;const layers={human:'真人',input:'Input',agent:'Agent',model:'Model',tool:'Tool',output:'Output',control:'状态'};
 const exportButton=button('导出 Trace JSON',()=>{
  if(!all.length)return;const blob=new Blob([JSON.stringify({schema:'gongzhi-trace-export-v1',project_id:p,run_id:id,status,exported_at:new Date().toISOString(),includes_business_context:true,contains_hidden_reasoning:false,events:all},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=el('a',{href:url,download:id+'-trace.json'});document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 },{class:'small',icon:'download',disabled:true});
 const refreshButton=button('刷新轨迹',()=>load(),{class:'small ghost',icon:'refresh'});
 content.append(el('p',{class:'notice neutral'},'实际执行事件，不包含隐藏推理。导出会包含当前任务的业务输入和资料，请只分享给有权限的同事。'),summary,el('div',{class:'trace-toolbar'},filters,refreshButton,exportButton),list);
 const dlg=openDialog('执行 Trace',content,{wide:true,description:'人类 · Input · Agent · Model · Tool · Output'});
 function render(){
  const info=traceOverview(all);summary.replaceChildren(el('strong',{},info.agent+(info.revision?' · v'+info.revision:'')),el('p',{},info.model+' · '+(labels[status]||status||info.status)),el('div',{class:'row wrap'},badge(info.humanMessages+' 条真人输入'),badge(info.modelSteps+' 个模型步骤'),badge(info.toolResults+' 次工具返回'),badge(info.usage?.total_tokens!=null?info.usage.total_tokens+' token':'用量未知')));
  list.replaceChildren();const outputs=new Map();
  for(const e of all){
   if(e.event==='output.delta'){const key=e.payload?.model_step||e.parent_span||'未标记步骤';if(!outputs.has(key))outputs.set(key,[]);outputs.get(key).push(e);continue;}
   if(filters.value!=='all'&&filters.value!==e.layer)continue;
   list.append(el('details',{class:'trace-event trace-'+e.layer},el('summary',{},badge(layers[e.layer]||e.layer),el('strong',{},e.event),el('small',{},stamp(e.created_at))),el('p',{class:'help'},'事件 #'+e.seq+' · span '+e.span_id+(e.parent_span?' ← '+e.parent_span:'')),el('pre',{},JSON.stringify(e.payload,null,2))));
  }
  if(filters.value==='all'||filters.value==='output')for(const [step,events] of outputs)list.append(el('details',{class:'trace-event trace-output'},el('summary',{},'模型步骤 '+step+' · 流式输出 · '+events.length+' 段'),el('pre',{},events.map(e=>e.payload.text||'').join(''))));
  if(!all.length)list.append(el('p',{class:'muted'},'此运行尚无分层 Trace，或来自旧版本；不会补造执行事件。'));
  else if(!list.children.length)list.append(el('p',{class:'muted'},'此运行在所选层级没有事件。'));
 }
 async function load(){
  if(loading)return;loading=true;refreshButton.disabled=true;exportButton.disabled=true;
  try{
   let cursor=0,next=[],runStatus='';
   for(let page=0;page<25;page++){
    const r=await api('/projects/'+p+'/runs/'+id+'/trace?after='+cursor);if(!dlg.dialog.isConnected)return;
    next.push(...r.items);runStatus=r.status;if(!r.has_more)break;if(!r.items.length)throw Error('Trace分页未前进');cursor=r.items.at(-1).seq;
   }
   all=next;status=runStatus;render();exportButton.disabled=!all.length;
  }catch(e){if(dlg.dialog.isConnected){all=[];summary.replaceChildren();list.replaceChildren(el('p',{class:'form-error'},e.message));}}
  finally{loading=false;refreshButton.disabled=false;}
 }
 filters.addEventListener('change',render);await load();
}
function selectMany(name,label,items,values=[]){return field(name,label,'select','',{attrs:{multiple:true,size:Math.min(5,Math.max(2,items.length))},choices:items.map(x=>[x.id,x.name+' · v'+x.revision])});}
function chosen(form,name){return [...form.elements[name].selectedOptions].map(x=>x.value);}
async function capabilityLibrary(kind='agent'){
 try{await reloadCapabilities();const content=el('div'),nav=el('div',{class:'settings-tabs'}),rows=el('div');content.append(nav,rows);const dlg=openDialog('项目能力库',content,{wide:true,description:'Agent 身份、版本化 Skill 与已授权 MCP，分别管理。'});
 const show=k=>{kind=k;nav.replaceChildren(...Object.keys(agentNames).map(x=>button(agentNames[x],()=>show(x),{class:x===k?'primary':'ghost'})));rows.replaceChildren(el('div',{class:'row spread'},el('h3',{},agentNames[k]+' 库'),isOwner()&&button('新建 '+agentNames[k],()=>{dlg.close();assetEditor(k);},{class:'primary',icon:'plus'})));
 if(k==='skill'&&isOwner())rows.append(button('浏览 Octop 内置技能',()=>{dlg.close();nativeSkills();},{class:'small',icon:'download'}));
 for(const a of state.capabilities.filter(x=>x.kind===k))rows.append(el('div',{class:'list-row'},icon(k==='agent'?'spark':k==='skill'?'plan':'link'),el('div',{class:'grow'},el('strong',{},a.name),el('p',{},a.description),el('small',{},'v'+a.revision+' · '+(a.enabled?'已启用':'已停用')+(k==='skill'?' · '+(a.data.status==='draft'?'待审核草稿':'已发布'):''))),button(isOwner()?'配置':'查看',()=>{dlg.close();assetEditor(k,a);},{class:'small'}),button('导出',()=>download('/capabilities/'+a.id+'/export',a.name+(k==='skill'?'.zip':'.md')),{class:'small ghost'}),k==='mcp'&&isOwner()&&button('测试连接',()=>testMCP(a),{class:'small'})));
 };show(kind);}catch(e){handle(e);}
}
function assetEditor(kind,a=null){if(kind==='agent')agentEditor(a);else if(kind==='skill')skillEditor(a);else mcpEditor(a);}
function agentEditor(a=null){
 if(!isOwner()){openDialog(a?.name||'Agent',el('pre',{},JSON.stringify(a?.data||{},null,2)),{wide:true});return;}
 const d=a?.data||{system_prompt:'你是团队任务助手。根据当前任务与授权资料协作，区分事实与建议。',soul_md:'# SOUL\n诚实、清楚、协作。',agents_md:'# AGENTS\n不扩大工具权限；产物先待验收。',search_prompt:'先核对 @ 指定资料，再检索项目知识。',model:'',provider_name:'',skill_ids:[],mcp_ids:[],tools:['project_search','project_read_document'],max_model_steps:4,max_tool_calls:8,timeout_seconds:180,max_output_tokens:4096};
 const skills=state.capabilities.filter(x=>x.kind==='skill'&&x.enabled&&x.data.status==='published'),mcps=state.capabilities.filter(x=>x.kind==='mcp'&&x.enabled);
 const advanced=el('details',{class:'config-details'},el('summary',{},'人格、工作指令与检索规范'),field('soul_md','SOUL.md','textarea',d.soul_md),field('agents_md','AGENTS.md','textarea',d.agents_md),field('search_prompt','检索提示词','textarea',d.search_prompt));
 const limits=el('details',{class:'config-details'},el('summary',{},'执行逻辑与边界'),el('p',{class:'notice neutral'},'使用原生 Octop Harness 的单 Agent 模型—工具循环。不开启任意 shell、桌面、子 Agent。外部 MCP 每次调用需批准；不会自动重试付费模型。'),el('div',{class:'field-row'},field('max_model_steps','最多模型步骤','number',d.max_model_steps,{attrs:{min:1,max:8}}),field('max_tool_calls','最多工具调用','number',d.max_tool_calls,{attrs:{min:0,max:16}})),el('div',{class:'field-row'},field('timeout_seconds','最长秒数','number',d.timeout_seconds,{attrs:{min:30,max:180}}),field('max_output_tokens','每步最大输出 token','number',d.max_output_tokens,{attrs:{min:128,max:8192}})),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'allow_search',checked:d.tools.includes('project_search')}),'项目知识检索'),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'allow_read',checked:d.tools.includes('project_read_document')}),'按 ID 阅读项目资料'));
 const fields=[field('name','Agent名称','text',a?.name||'',{attrs:{required:true,maxlength:80}}),field('description','用途说明','text',a?.description||'',{attrs:{maxlength:2000}}),field('system_prompt','系统提示词','textarea',d.system_prompt,{attrs:{maxlength:16000,class:'text-area-large'}}),advanced,
 field('model','绑定模型 ID（留空继承项目）','text',d.model,{help:'项目默认：'+(state.settings?.model||'尚未配置')+'。独立接口或密钥用下方“独立模型连接”配置。'}),field('provider_name','模型凭证来源','select',d.provider_name,{choices:[['','继承当前项目'],...(d.provider_name&&d.provider_name!==state.settings?.provider_name?[[d.provider_name,'Agent 独立连接']]:[])]}),
 selectMany('skill_ids','启用的 Skills（Ctrl／⌘ 多选）',skills),selectMany('mcp_ids','挂载的 MCP（Ctrl／⌘ 多选）',mcps),limits,el('label',{class:'field-check'},el('input',{type:'checkbox',name:'enabled',checked:a?.enabled!==false}),'启用此 Agent')];
 const extra=a?[button('独立模型连接',()=>{dlg.close();agentProvider(a);},{class:'left'}),button('版本记录',()=>assetHistory(a),{class:'ghost'})]:[];
 const dlg=formDialog(a?'配置 Agent · '+a.name:'新建 Agent',fields,async(v,form)=>{const data={...d,system_prompt:v.system_prompt,soul_md:v.soul_md,agents_md:v.agents_md,search_prompt:v.search_prompt,model:v.model.trim(),provider_name:v.provider_name,skill_ids:chosen(form,'skill_ids'),mcp_ids:chosen(form,'mcp_ids'),tools:[...(form.elements.allow_search.checked?['project_search']:[]),...(form.elements.allow_read.checked?['project_read_document']:[])]};for(const k of ['max_model_steps','max_tool_calls','timeout_seconds','max_output_tokens'])data[k]=Number(v[k]);const saved=await api(a?'/capabilities/'+a.id:projectPath('/capabilities'),{method:a?'PATCH':'POST',body:{kind:'agent',name:v.name,description:v.description,enabled:form.elements.enabled.checked,expected_revision:a?.revision,data}});await reloadCapabilities();state.agentId=saved.id;refreshAgentControls();toast('Agent配置已保存；新运行使用新版本');},{wide:true,submit:'保存 Agent',extra,description:'当前项目权限内的一位可配置协作者。运行时会冻结提示词、模型与技能版本。'});
 const form=dlg.dialog?.querySelector?.('form')||document.querySelector('dialog[open] form');if(form)for(const [key,ids] of [['skill_ids',d.skill_ids],['mcp_ids',d.mcp_ids]])for(const opt of form.elements[key].options)opt.selected=ids.includes(opt.value);
}
function agentProvider(a){formDialog('Agent 独立模型连接',[field('base_url','API 地址','url','',{attrs:{required:true},help:'使用 HTTPS。密钥只存服务端，不回显。'}),field('model','模型 ID','text',a.data.model||state.settings?.model||'',{attrs:{required:true}}),field('api_key','API Key','password','',{attrs:{autocomplete:'new-password'}})],async v=>{await api('/capabilities/'+a.id+'/provider',{method:'POST',body:{...v,expected_revision:a.revision}});await reloadCapabilities();toast('Agent独立模型已绑定');},{description:'更换接口地址需要重新提供密钥。此操作不发送模型测试请求。',submit:'保存连接'});}
function skillEditor(a=null){
 if(!isOwner()){openDialog(a.name,markdown(a.data.body),{wide:true});return;}
 const d=a?.data||{slug:'new-skill',body:'# 用途\n\n# 输入\n\n# 执行步骤\n\n# 验收与边界\n',status:'draft'};
 formDialog(a?'配置 Skill · '+a.name:'创建 Skill 草稿',[field('name','技能名称','text',a?.name||'',{attrs:{required:true}}),field('description','技能描述','textarea',a?.description||'',{attrs:{maxlength:2000}}),a?.source?.document_id&&el('p',{class:'source-line'},'来源：'+a.source.document_id+' · v'+a.source.document_revision),a?.source?.catalog_id&&el('p',{class:'source-line'},'Octop 原包：'+a.source.catalog_id+' · 导入后待人工审核'),field('slug','技能标识','text',d.slug,{attrs:{required:true,pattern:'[a-z0-9][a-z0-9_-]*'}}),field('body','SKILL.md 正文','textarea',d.body,{attrs:{required:true,class:'text-area-large',maxlength:100000}}),field('status','审核状态','select',d.status,{choices:[['draft','待审核草稿'],['published','已人工审核并发布']]}),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'enabled',checked:!!a?.enabled}),'启用（还需在 Agent 配置中显式挂载）'),el('p',{class:'notice neutral'},'导入的附件与脚本会随原包保留，但本版不自动执行脚本。未审核草稿不能挂载给Agent。')],async(v,form)=>{if(v.status==='draft'&&form.elements.enabled.checked)throw new Error('请先审核发布，再启用');await api(a?'/capabilities/'+a.id:projectPath('/capabilities'),{method:a?'PATCH':'POST',body:{kind:'skill',name:v.name,description:v.description,enabled:form.elements.enabled.checked,expected_revision:a?.revision,data:{slug:v.slug,body:v.body,status:v.status}}});await reloadCapabilities();toast('Skill版本已保存');},{wide:true,submit:'保存 Skill',extra:a?[button('版本记录',()=>assetHistory(a),{class:'ghost'})]:[]});
}
function mcpEditor(a=null){
 if(!isOwner()){openDialog(a.name,el('pre',{},JSON.stringify(a.data,null,2)),{wide:true});return;}
 const d=a?.data||{transport:'streamable_http',url:'',allowed_tools:[],command:'',args:[],approval_required:true};
 formDialog(a?'配置 MCP · '+a.name:'新增 MCP',[field('name','MCP名称','text',a?.name||'',{attrs:{required:true}}),field('description','用途说明','text',a?.description||''),field('transport','传输方式','select',d.transport,{choices:[['streamable_http','Streamable HTTP · HTTPS'],['sse','SSE · HTTPS'],['stdio','本机 stdio · 信任的程序'],...(d.transport==='builtin'?[['builtin','内置只读 MCP']]:[])]}),field('url','HTTPS 地址','url',d.url||''),field('command','stdio 可执行文件绝对路径','text',d.command||'',{help:'WSL/Linux 路径；不接受 shell 命令字符串，不代为下载外部程序。'}),field('args','stdio 参数 JSON 数组','textarea',JSON.stringify(d.args||[])),field('allowed_tools','允许的工具名（逗号分隔）','text',d.allowed_tools.join(', '),{help:'只挂载明确列出的工具。测试连接会列出远端实际工具。'}),field('auth_headers','认证头 JSON（留空保留，不回显）','textarea','',{help:'如需认证，填写 Authorization 等头；由服务端加密保存。不要把密钥写进URL。'}),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'acknowledge_host_execution'}),'我确认：stdio会以应用账户启动受信任程序，不是操作系统沙箱'),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'enabled',checked:!!a?.enabled}),'启用连接'),el('p',{class:'notice'},'仅系统管理员可以维护MCP。外部工具的实际调用每次仍需发起人或项目管理员批准。')],async(v,form)=>{const data={transport:v.transport,url:v.url,command:v.command,args:JSON.parse(v.args||'[]'),allowed_tools:v.allowed_tools.split(',').map(x=>x.trim()).filter(Boolean)};const saved=await api(a?'/capabilities/'+a.id:projectPath('/capabilities'),{method:a?'PATCH':'POST',body:{kind:'mcp',name:v.name,description:v.description,expected_revision:a?.revision,enabled:form.elements.enabled.checked,data,acknowledge_host_execution:form.elements.acknowledge_host_execution.checked}});if(v.auth_headers.trim())await api('/capabilities/'+saved.id+'/mcp-credentials',{method:'POST',body:{headers:JSON.parse(v.auth_headers)}});await reloadCapabilities();toast('MCP配置已保存，尚未执行任何业务工具');},{wide:true,submit:'保存 MCP'});
}
async function testMCP(a){const run=async()=>{const result=await api('/capabilities/'+a.id+'/mcp-test',{method:'POST',body:{acknowledge_host_execution:a.data.transport==='stdio'}});openDialog('MCP 连接与工具',el('div',{},el('p',{class:'notice neutral'},'已连接；只发现工具，未调用业务工具。'),...result.tools.map(t=>el('details',{class:'trace-event'},el('summary',{},t.name, badge(t.allowed?'已允许':'未允许')),el('p',{},t.description),el('pre',{},JSON.stringify(t.input_schema,null,2))))),{wide:true});};if(a.data.transport==='stdio')confirmAction('启动已配置的 MCP 程序','连接测试将以应用账户启动该程序。这不是沙箱；请确认可执行文件可信。',run);else try{await run();}catch(e){handle(e);}}
async function nativeSkills(){try{const result=await api(projectPath('/skill-catalog')),root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索内置技能…','aria-label':'搜索Octop内置技能'}),list=el('div');root.append(el('p',{class:'notice neutral'},'来源：当前安装的 Octop Harness。完整文件包导入后默认停用、待审核；不会自动执行其中脚本。'),search,list);const dlg=openDialog('Octop 内置技能库',root,{wide:true});const render=()=>{const q=search.value.toLowerCase();list.replaceChildren(...result.items.filter(x=>(x.name+' '+x.description+' '+x.id).toLowerCase().includes(q)).slice(0,40).map(x=>el('div',{class:'list-row'},el('div',{class:'grow'},el('strong',{},x.name),el('p',{},x.description),el('small',{},x.id)),button('导入待审',async()=>{try{const a=await api(projectPath('/skill-import'),{method:'POST',body:{catalog_id:x.id}});await reloadCapabilities();dlg.close();skillEditor(a);}catch(e){handle(e);}},{class:'small'}))));};search.addEventListener('input',render);render();}catch(e){handle(e);}}
async function assetHistory(a){try{const r=await api('/capabilities/'+a.id+'/history');openDialog(a.name+' · 版本记录',el('div',{},el('p',{class:'help'},'当前 v'+a.revision+'；以下为保存前的历史快照。'),r.items.map(x=>el('details',{class:'trace-event'},el('summary',{},'v'+x.revision+' · '+stamp(x.updated_at)),el('pre',{},JSON.stringify(x.data,null,2))))),{wide:true});}catch(e){handle(e);}}
documentDialog=async function(id){await agentBaseDocument(id);const doc=state.documents.find(d=>d.id===id),dialog=document.querySelector('dialog[open]');if(doc?.adopted&&doc.status==='ready'&&isOwner()&&dialog){dialog.querySelector('.modal-body')?.append(button('沉淀为 Skill 草稿',async()=>{try{const a=await api(projectPath('/skill-from-knowledge'),{method:'POST',body:{document_id:id}});dialog.close();dialog.remove();await reloadCapabilities();skillEditor(a);}catch(e){handle(e);}},{icon:'plan'}));}};

// Platform 0.4: one company library; projects contain only pinned enablements.
companyViews.push(['platform','能力中心','spark']);
const platformKinds={agent:'Agent',skill:'Skill',mcp:'MCP',harness:'Harness',model:'模型连接'};
const platformState={catalog:null,tab:'agent',query:'',legacy:false};
const platformBaseShowCompany=showCompany,platformBaseTaskContext=taskContextPanel,platformBaseRunSelection=runSelection;
const platformURL=(w,s='')=>'/workspaces/'+encodeURIComponent(w)+'/platform'+s;
showCompany=async function(view='overview'){
 if(view!=='platform')return platformBaseShowCompany(view);
 resetView();state.screen='company';state.companyView='platform';state.project=null;state.tab='tasks';renderShell();
 const gen=state.generation,w=state.workspace.id;
 $('#workspace').append(companyHeader('能力中心','在公司统一配置，在项目按需启用。配置共享，不共享项目的私有讨论与资料。'),el('section',{class:'content',id:'content'},el('p',{class:'muted'},'正在载入能力库…')));
 history.replaceState({},'','#workspace='+w+'&view=platform');
 try{const data=await api(platformURL(w),{signal:state.controller.signal});if(gen!==state.generation)return;platformState.catalog=data;renderPlatform();}
 catch(e){if(gen===state.generation&&e.name!=='AbortError')$('#content')?.replaceChildren(el('div',{class:'form-error'},e.message));}
};
async function platformReload(w=state.workspace.id){
 const data=await api(platformURL(w));if(w!==state.workspace?.id)return;platformState.catalog=data;
 if(state.screen==='company'&&state.companyView==='platform')renderPlatform();
}
function platformAssetSummary(a){
 const d=a.data;
 if(a.kind==='agent')return '绑定 Harness · '+d.skill_ids.length+' Skills · '+d.mcp_ids.length+' MCP';
 if(a.kind==='harness')return d.max_model_steps+' 个模型步骤 · '+d.max_tool_calls+' 次工具 · '+d.timeout_seconds+' 秒 · 流式';
 if(a.kind==='model')return (d.model||'待配置')+' · '+(d.configured?'连接已保存':'尚未配置凭证');
 if(a.kind==='mcp')return d.transport+' · '+d.allowed_tools.length+' 个允许工具 · '+(d.approval_required?'逐次批准':'内置只读');
 return (d.status==='published'?'已审核发布':'待审核草稿')+' · '+d.slug;
}
function renderPlatform(){
 const c=$('#content'),data=platformState.catalog;if(!c||!data)return;c.replaceChildren();
 const w=state.workspace.id,can=data.can_manage;
 c.append(el('div',{class:'platform-flow'},...['模型连接','Harness 执行规则','Skill / MCP','Agent 组合','项目启用'].map((x,i)=>el('span',{},String(i+1).padStart(2,'0')+' '+x))));
 c.append(el('p',{class:'notice neutral'},'先在此配置模型、执行规则和工具，再组合成 Agent。项目只选择版本与授权；库中更新不会静默覆盖项目绑定。'));
 const nav=el('nav',{class:'settings-tabs platform-tabs','aria-label':'能力分类'},Object.entries(platformKinds).map(([k,label])=>button(label,()=>{platformState.tab=k;renderPlatform();},{class:platformState.tab===k?'primary':'ghost'})));
 const search=el('input',{class:'input',type:'search',value:platformState.query,placeholder:'搜索名称或说明…','aria-label':'搜索公司能力'});
 const legacy=el('input',{type:'checkbox',checked:platformState.legacy,'aria-label':'显示迁移配置'});
 const rows=el('div',{class:'platform-grid'}),toolbar=el('div',{class:'platform-toolbar'},search,el('label',{class:'field-check'},legacy,'显示原项目迁移配置'));
 const actions=el('div',{class:'row wrap'});
 if(can)actions.append(button('新建 '+platformKinds[platformState.tab],()=>platformEditor(platformState.tab),{class:'primary',icon:'plus'}));
 
 if(can&&platformState.tab==='model')actions.append(button('绑定服务器模型预设',async()=>{try{await api(platformURL(w,'/server-model-preset'),{method:'POST'});await platformReload(w);toast('模型预设已保存到公司能力中心；未调用模型');}catch(e){handle(e);}},{icon:'link'}));
 if(can)actions.append(button('导出能力库',()=>download(platformURL(w,'/export'),'公司能力库.zip'),{class:'ghost',icon:'download'}));
 c.append(nav,el('div',{class:'view-head'},el('h2',{},platformKinds[platformState.tab]+' 库'),actions),toolbar,rows);
 const renderRows=()=>{
  const q=platformState.query.toLowerCase(),all=data.items.filter(a=>a.kind===platformState.tab),items=all.filter(a=>(platformState.legacy||a.source?.kind!=='legacy_project_migration')&&(a.name+' '+a.description).toLowerCase().includes(q));
  rows.replaceChildren(...items.map(a=>{
   const controls=el('div',{class:'row wrap'},button(can?'配置':'查看',()=>platformEditor(a.kind,a),{class:'small'}),button('导出',()=>download('/capabilities/'+a.id+'/export',a.name+(a.kind==='skill'?'.zip':'.md')),{class:'small ghost'}));
   if(can)controls.append(button('版本与影响',()=>platformHistory(a),{class:'small ghost'}));
   if(can&&a.kind==='model'){controls.append(button('配置连接',()=>platformModelConnection(a),{class:'small',icon:'link'}));if(a.data.configured&&a.visibility==='workspace')controls.append(button(data.default_model_id===a.id?'公司默认':'设为默认',async()=>{try{await api(platformURL(w,'/default-model'),{method:'PUT',body:{model_id:a.id}});await platformReload(w);toast('默认模型已更新；现有项目绑定未改变');}catch(e){handle(e);}},{class:'small ghost',disabled:data.default_model_id===a.id}));}
   if(can&&a.kind==='mcp'&&data.can_manage_mcp)controls.append(button('测试连接',()=>testMCP(a),{class:'small'}));
   return el('article',{class:'platform-card','data-asset-id':a.id},el('div',{class:'row spread'},badge(a.kind==='harness'?'Harness':platformKinds[a.kind]),badge(a.enabled?'已启用':'已停用',a.enabled?'success':'')),el('h3',{},a.name),el('p',{},a.description||'暂无说明'),el('p',{class:'help'},platformAssetSummary(a)),el('div',{class:'row wrap'},badge('v'+a.revision),badge(a.visibility==='workspace'?'公司共享':'受限资产'),a.used_by_projects>0&&badge(a.used_by_projects+' 项绑定'),a.source?.kind==='legacy_project_migration'&&badge('原项目迁移','warning')),controls);
  }));
  if(!items.length)rows.append(empty('暂无 '+platformKinds[platformState.tab],all.length?'可打开“显示原项目迁移配置”查看保留的旧配置。':'配置完成后可被多个项目复用，不必先创建项目。','spark'));
 };
 search.addEventListener('input',()=>{platformState.query=search.value;renderRows();});legacy.addEventListener('change',()=>{platformState.legacy=legacy.checked;renderRows();});renderRows();
}
async function platformEditor(kind,a=null){
 const w=state.workspace.id;if(!platformState.catalog||state.screen!=='company')await platformReload(w);
 const catalog=platformState.catalog,can=catalog.can_manage;
 if(!can){openDialog(a?.name||platformKinds[kind],el('pre',{},JSON.stringify(a?.data||{},null,2)),{wide:true,description:'公司能力配置 · 只读'});return;}
 if(kind==='mcp'&&!catalog.can_manage_mcp){toast('MCP连接需系统管理员配置',true);return;}
 const items=catalog.items,enabled=(type)=>items.filter(x=>x.kind===type&&x.enabled&&(type!=='skill'||x.data.status==='published'));
 const d=a?.data||{},fields=[field('name','名称','text',a?.name||'',{attrs:{required:true,maxlength:80}}),field('description','用途说明','textarea',a?.description||'',{attrs:{maxlength:2000}})];
 const multi=[];
 if(kind==='agent'){
  fields.push(field('system_prompt','系统提示词','textarea',d.system_prompt||'用中文协作，区分事实、建议和未决事项；引用授权资料。',{attrs:{maxlength:40000,class:'text-area-large'}}),el('details',{class:'config-details'},el('summary',{},'SOUL.md · AGENTS.md · 检索规则'),field('soul_md','SOUL.md','textarea',d.soul_md||'# SOUL\n诚实、清楚、协作。'),field('agents_md','AGENTS.md','textarea',d.agents_md||'# AGENTS\n只使用授权工具，成果先待验收。'),field('search_prompt','检索提示词','textarea',d.search_prompt||'优先核对用户 @ 的文件，保留来源和版本。')),
   field('harness_id','执行规则 Harness','select',d.harness_id||enabled('harness')[0]?.id||'',{choices:[['','请选择 Harness'],...enabled('harness').map(x=>[x.id,x.name+' · v'+x.revision])],attrs:{required:true},help:'步骤、工具、检索、上下文和时间限制由独立Harness维护。'}),
   field('model_id','绑定模型连接','select',d.model_id||'',{choices:[['','启用时使用公司默认模型'],...enabled('model').map(x=>[x.id,x.name+' · '+(x.data.model||'未配置')])],help:'项目启用会固定模型连接版本，不复制或回显密钥。'}),selectMany('skill_ids','挂载 Skills（Ctrl／⌘ 多选）',enabled('skill')),selectMany('mcp_ids','挂载 MCP（Ctrl／⌘ 多选）',enabled('mcp')));
  multi.push(['skill_ids',d.skill_ids||[]],['mcp_ids',d.mcp_ids||[]]);
 }
 if(kind==='skill')fields.push(field('slug','技能标识','text',d.slug||'new-skill',{attrs:{required:true,pattern:'[a-z0-9][a-z0-9_-]*'}}),field('body','SKILL.md 正文','textarea',d.body||'# 用途\n\n# 输入\n\n# 执行步骤\n\n# 验收与失败处理\n\n# 权限边界\n',{attrs:{required:true,maxlength:100000,class:'text-area-large'}}),field('status','审核状态','select',d.status||'draft',{choices:[['draft','待审核草稿'],['published','已人工审核发布']]}),el('p',{class:'notice neutral'},'原包附属文件保留；本版不自动执行Skill中的脚本。草稿不可挂载。'));
 if(kind==='harness'){
  const v={...catalog.harness_defaults,...d};
  fields.push(el('p',{class:'notice neutral'},'固定使用 Octop Harness 单Agent流式模型—工具循环。不做隐式付费重试；外部MCP逐次批准，业务结果由人验收。以下参数会进入实际运行，不是说明性开关。'));
  for(const [k,label,min,max] of [['max_model_steps','最多模型步骤',1,24],['max_tool_calls','最多工具调用',0,64],['timeout_seconds','最长运行秒数',30,900],['max_output_tokens','每步最大输出 token',128,8192],['history_limit','历史消息条数',5,200],['max_context_chars','任务原话字符上限',10000,120000],['max_documents','最多 @ 资料数',0,6],['max_document_chars','每份 @ 资料字符上限',1000,30000]])fields.push(field(k,label,'number',v[k],{attrs:{required:true,min,max,step:1}}));
  fields.push(field('retrieval_mode','资料装配方式','select',v.retrieval_mode,{choices:[['automatic','自动检索 + @明确文件'],['explicit','仅@文件自动入上下文；工具仍按授权可用'],['disabled','禁用项目资料检索及@文件']]}),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'allow_search',checked:v.tools.includes('project_search')}),'允许项目知识检索工具'),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'allow_read',checked:v.tools.includes('project_read_document')}),'允许按ID读取授权资料'));
 }
 if(kind==='mcp')fields.push(field('transport','传输方式','select',d.transport||'streamable_http',{choices:[['streamable_http','Streamable HTTP · HTTPS'],['sse','SSE · HTTPS'],['stdio','本机 stdio · 可信宿主程序'],...(d.transport==='builtin'?[['builtin','内置只读 MCP']]:[])]}),field('url','HTTPS 地址','url',d.url||''),field('command','stdio 可执行文件绝对路径','text',d.command||'',{help:'WSL/Linux绝对路径，不接收shell命令串；不会下载外部程序。'}),field('args','stdio 参数 JSON 数组','textarea',JSON.stringify(d.args||[])),field('allowed_tools','允许的工具名（逗号分隔）','text',(d.allowed_tools||[]).join(', ')),field('auth_headers','认证头 JSON（留空保留）','textarea','',{help:'服务端加密保存，不回显。更换地址后旧认证会清除。'}),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'acknowledge_host_execution'}),'我确认：stdio会启动受信任宿主程序，不是操作系统沙箱'),el('p',{class:'notice'},'连接发现不调用业务工具；外部工具实际运行时仍逐次批准。'));
 if(kind==='model')fields.push(el('p',{class:'notice neutral'},'此处维护模型资产名称和共享范围。保存后使用“配置连接”填写地址、模型ID与密钥；密钥不进入配置正文和导出。'));
 fields.push(field('visibility','共享范围','select',a?.visibility||'workspace',{choices:[['workspace','公司共享配置'],['restricted','受限配置／待发布']]}),a?.visibility==='restricted'&&el('label',{class:'field-check'},el('input',{type:'checkbox',name:'acknowledge_sharing'}),'已核对正文和附属文件，确认可发布给整个公司'),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'enabled',checked:a?a.enabled:!['skill','mcp','model'].includes(kind)}),'启用该资产（项目仍需单独启用）'));
 if(a?.source?.origin_project_id)fields.push(el('p',{class:'source-line'},'来源项目ID：'+a.source.origin_project_id+'。迁移保留原配置，不自动公开原项目数据。'));
 const dlg=formDialog(a?'配置 '+platformKinds[kind]+' · '+a.name:'新建 '+platformKinds[kind],fields,async(v,form)=>{
  let data={...d};
  if(kind==='agent')data={system_prompt:v.system_prompt,soul_md:v.soul_md,agents_md:v.agents_md,search_prompt:v.search_prompt,harness_id:v.harness_id,model_id:v.model_id,skill_ids:chosen(form,'skill_ids'),mcp_ids:chosen(form,'mcp_ids')};
  if(kind==='skill')data={slug:v.slug,body:v.body,status:v.status};
  if(kind==='harness'){data={...catalog.harness_defaults,...d,retrieval_mode:v.retrieval_mode,tools:[...(form.elements.allow_search.checked?['project_search']:[]),...(form.elements.allow_read.checked?['project_read_document']:[])]};for(const key of ['max_model_steps','max_tool_calls','timeout_seconds','max_output_tokens','history_limit','max_context_chars','max_documents','max_document_chars'])data[key]=Number(v[key]);}
  if(kind==='mcp')data={transport:v.transport,url:v.url,command:v.command,args:JSON.parse(v.args||'[]'),allowed_tools:v.allowed_tools.split(',').map(x=>x.trim()).filter(Boolean)};
  const headers=kind==='mcp'&&v.auth_headers.trim()?JSON.parse(v.auth_headers):null;
  const saved=await api(a?'/platform/assets/'+a.id:platformURL(w,'/assets'),{method:a?'PATCH':'POST',body:{kind,name:v.name,description:v.description,enabled:form.elements.enabled.checked,visibility:v.visibility,data,expected_revision:a?.revision,acknowledge_sharing:!!form.elements.acknowledge_sharing?.checked,acknowledge_host_execution:!!form.elements.acknowledge_host_execution?.checked}});
  if(headers)await api('/capabilities/'+saved.id+'/mcp-credentials',{method:'POST',body:{headers}});
  await platformReload(w);toast('能力中心已保存 v'+saved.revision+'；项目绑定未自动更新');
 },{wide:true,submit:'保存 '+platformKinds[kind],description:'独立于项目的公司级配置。修改产生新版本；项目显式启用或升级。'});
 for(const [key,ids] of multi)for(const option of dlg.form.elements[key].options)option.selected=ids.includes(option.value);
}
async function platformModelConnection(a){
 const w=a.workspace_id;
 formDialog('配置模型连接 · '+a.name,[field('base_url','API 地址','url',a.data.base_url||'',{attrs:{required:true},help:'远程模型使用HTTPS；本地服务须部署管理员明确授权。'}),field('model','模型 ID','text',a.data.model||'',{attrs:{required:true}}),field('api_key','API Key','password','',{attrs:{autocomplete:'new-password'},help:a.data.configured?'已保存，留空保留；更换地址须重新提供。':'仅保存于服务端，页面不回显。'})],async v=>{await api('/platform/assets/'+a.id+'/model-connection',{method:'POST',body:{...v,expected_revision:a.revision}});await platformReload(w);toast('模型连接已配置；现有绑定需要明确升级。未发送模型请求。');},{wide:true,submit:'保存连接'});
}
async function platformHistory(a){
 try{const [history,impact]=await Promise.all([api('/platform/assets/'+a.id+'/history'),api('/platform/assets/'+a.id+'/usage')]);
  const root=el('div',{},el('p',{class:'notice neutral'},'当前版本 v'+a.revision+'；'+impact.total_bindings+' 个项目绑定引用此资产。项目继续使用各自固定版本。停用资产会阻止新执行。'),...impact.items.map(x=>el('p',{},x.project_title+' · 固定 v'+x.pinned_revision+' · 绑定 v'+x.binding_revision)),impact.hidden_project_bindings>0&&el('p',{class:'help'},'另有 '+impact.hidden_project_bindings+' 项绑定，其项目内容不在你的访问范围。'));
  for(const old of history.items)root.append(el('details',{class:'trace-event'},el('summary',{},'历史 v'+old.revision+' · '+stamp(old.updated_at)),el('pre',{},JSON.stringify(old.data,null,2)),a.kind!=='model'&&button('恢复此配置为新版本',()=>confirmAction('恢复配置','生成新版本，不改写历史快照，不自动升级项目绑定。',async()=>{await api('/platform/assets/'+a.id+'/restore',{method:'POST',body:{restore_revision:old.revision,expected_revision:a.revision,acknowledge_sharing:old.visibility===a.visibility,acknowledge_host_execution:false}});closeDialogs();await platformReload(a.workspace_id);toast('已恢复为新版本');}),{class:'small'})));
  if(!history.items.length)root.append(el('p',{class:'muted'},'尚无历史版本。'));
  openDialog(a.name+' · 版本与影响',root,{wide:true});
 }catch(e){handle(e);}
}
async function platformNativeSkills(){
 const w=state.workspace.id;
 try{const result=await api(platformURL(w,'/skill-catalog')),root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索内置技能…','aria-label':'搜索Octop内置技能'}),list=el('div');root.append(el('p',{class:'notice neutral'},'完整技能包导入公司能力中心，初始为停用草稿，不绑定任何项目、不执行脚本。'),search,list);const dlg=openDialog('Octop 内置技能库',root,{wide:true});
 const draw=()=>{const q=search.value.toLowerCase();list.replaceChildren(...result.items.filter(x=>(x.name+' '+x.description+' '+x.id).toLowerCase().includes(q)).map(x=>el('div',{class:'list-row'},el('div',{class:'grow'},el('strong',{},x.name),el('p',{},x.description),el('small',{},x.id)),button('导入待审',async()=>{try{const a=await api(platformURL(w,'/skill-import'),{method:'POST',body:{catalog_id:x.id}});await platformReload(w);dlg.close();platformEditor('skill',a);}catch(e){handle(e);}},{class:'small'}))));};search.addEventListener('input',draw);draw();
 }catch(e){handle(e);}
}
async function openProjectBindings(){
 if(!state.project){await showCompany('platform');return;}
 const p=state.project.id,w=state.project.workspace_id,gen=state.generation;
 try{const [library,result]=await Promise.all([api(platformURL(w)),api('/projects/'+p+'/platform-bindings')]);if(gen!==state.generation)return;
  const root=el('div',{},el('p',{class:'notice neutral'},'这里仅启用、升级或停用，不编辑能力。启用Agent会固定本次所选的Harness、模型、Skills和MCP版本；后续库更新需要再次确认。'));
  const tabs=el('div',{class:'settings-tabs'}),search=el('input',{class:'input',type:'search','aria-label':'搜索可启用能力',placeholder:'搜索公司能力…'}),rows=el('div');root.append(tabs,search,rows);let kind='agent';
  const dlg=openDialog('项目启用能力',root,{wide:true,actions:[button('前往公司能力中心',()=>{dlg.close();showCompany('platform');},{icon:'spark'})]});
  const draw=()=>{tabs.replaceChildren(...Object.entries(platformKinds).map(([k,v])=>button(v,()=>{kind=k;draw();},{class:k===kind?'primary':'ghost'})));rows.replaceChildren();
   for(const a of library.items.filter(x=>x.kind===kind&&(x.name+' '+x.description).toLowerCase().includes(search.value.toLowerCase()))){
    const b=result.items.find(x=>x.asset_id===a.id),current=b?.bundle.assets.find(x=>x.id===a.id),blocked=a.visibility==='restricted'&&a.source?.origin_project_id!==p;
    const details=el('details',{},el('summary',{},b?'已固定依赖版本':'待启用配置'),el('pre',{},JSON.stringify(b?{binding_revision:b.revision,versions:b.bundle.assets.map(x=>({kind:x.kind,name:x.name,revision:x.revision})),updates:b.updates,unavailable:b.unavailable}:a.data,null,2)));
    const controls=el('div',{class:'row wrap'});
    const apply=async enabled=>{try{await api('/projects/'+p+'/platform-bindings/'+a.id,{method:'PUT',body:{expected_binding_revision:b?.revision||0,asset_revision:a.revision,enabled}});dlg.close();if(state.project?.id===p){await reloadCapabilities();renderView();}toast(enabled?'已固定并启用所选能力版本':'已停用本项目绑定，其他项目不变');await openProjectBindings();}catch(e){handle(e);}};
    if(isOwner()){controls.append(button(b?.enabled?'明确升级／刷新依赖':'启用到本项目',()=>confirmAction('确认项目能力版本','将使用能力中心当前版本及列出的依赖。连接更新后会使用新的连接配置；不会带入其他项目的聊天。',()=>apply(true)),{class:'small primary',disabled:!a.enabled||blocked||(a.kind==='skill'&&a.data.status!=='published')}));if(b?.enabled)controls.append(button('停用',()=>apply(false),{class:'small danger'}));}
    rows.append(el('article',{class:'binding-card','data-binding-id':a.id},el('div',{class:'row spread'},el('h3',{},a.name),badge(b?.enabled?'项目已启用':'未启用',b?.enabled?'success':'')),el('p',{class:'help'},'能力中心 v'+a.revision+(current?' · 项目固定 v'+current.revision:'')+(blocked?' · 受原项目限制，先经公司管理员发布':'')),a.kind!=='agent'&&el('p',{class:'help'},'单独启用此资产不会自动加入Agent；依赖关系在公司能力中心配置。'),details,controls));
   }
   if(!rows.children.length)rows.append(empty('暂无可用配置','先在公司能力中心配置，然后回到项目启用。','spark'));
  };search.addEventListener('input',draw);draw();
 }catch(e){handle(e);}
}
capabilityLibrary=async function(){return openProjectBindings();};
agentEditor=function(a){
 if(!a){openProjectBindings();return;}
 const content=el('div',{},el('p',{class:'notice neutral'},'此处是当前项目的固定配置快照。编辑在公司能力中心完成，不修改项目副本。'),el('pre',{},JSON.stringify({name:a.name,agent_revision:a.revision,binding_revision:a.binding_revision,data:a.data},null,2)));
 const dlg=openDialog('已启用 Agent · '+a.name,content,{wide:true,actions:[button('管理项目启用',()=>{dlg.close();openProjectBindings();}),button('前往公司能力中心',()=>{dlg.close();showCompany('platform');},{icon:'spark'})]});
};
taskContextPanel=function(){const panel=platformBaseTaskContext();const title=panel.querySelector('.agent-config-section h3');if(title)title.textContent='本项目已启用的 Agent';panel.querySelectorAll('.agent-config-section button').forEach(b=>{if(b.textContent.includes('配置 Agent'))b.textContent='查看配置';else if(b.textContent==='能力库')b.textContent='启用管理';});const help=panel.querySelector('.agent-config-section p.help:last-child');if(help)help.textContent='能力在公司统一配置；此项目仅使用固定版本。通过 @ 选择本次参与者。';return panel;};
runSelection=function(){const result=platformBaseRunSelection(),a=selectedAgent();if(a?.binding_revision)result.binding_revision=a.binding_revision;return result;};
renderAISettings=function(root){root.append(el('p',{class:'notice neutral'},'模型、Agent、Skill、MCP与Harness已独立到公司能力中心。项目只启用配置版本，不再维护另一份提示词或模型密钥。'),button('项目启用能力',()=>{closeDialogs();openProjectBindings();},{class:'primary',icon:'link'}),button('公司能力中心',()=>{closeDialogs();showCompany('platform');},{class:'ghost',icon:'spark'}));};

skillEditor=function(a){return platformEditor("skill",a);};

// 0.5 — people-first workspace, separate AI employees, explicit tools and invitations.
const ui5OldShow=showCompany,ui5OldPlatformEditor=platformEditor,ui5OldRenderDiscussion=renderDiscussion,ui5OldRenderView=renderView,ui5OldHeader=header,ui5OldBootstrap=bootstrap;
const ui5={models:[],staffQuery:'',showLegacy:false,resourceTab:'skill',contextCollapsed:localStorage.getItem('gongzhi.context-collapsed')==='1',skills:[]};
companyViews.splice(0,companyViews.length,['overview','工作台','plan'],['projects','项目','tasks'],['employees','AI 员工','spark'],['knowledge','知识与记忆','files'],['calendar','日程','calendar'],['people','团队成员','users'],['integrations','技能与连接','link']);
Object.assign(platformKinds,{agent:'AI 员工',skill:'技能',mcp:'MCP 连接',harness:'高级执行规则',model:'模型连接'});
async function ui5LoadLibrary(){const w=state.workspace.id;const [c,m]=await Promise.all([api(platformURL(w)),api('/workspaces/'+w+'/go-models')]);if(state.workspace?.id!==w)return;platformState.catalog=c;ui5.models=m.items||[];}
showCompany=async function(view='overview'){
 if(view==='platform')view='integrations';
 if(!['employees','integrations','people'].includes(view))return ui5OldShow(view);
 resetView();state.screen='company';state.companyView=view;state.project=null;renderShell();const gen=state.generation;
 const names={employees:['AI 员工','为团队配置专家，在需要时邀请他们加入任务。'],integrations:['技能与连接','团队共用的技能、数据来源和模型。'],people:['团队成员','邀请同事与学员，为他们分配合适的项目权限。']};
 $('#workspace').append(companyHeader(...names[view]),el('section',{class:'content hub-content',id:'content'},el('p',{class:'muted'},'正在载入…')));history.replaceState({},'','#workspace='+state.workspace.id+'&view='+view);
 try{if(view==='people'){await renderPeople();return;}await ui5LoadLibrary();if(gen!==state.generation)return;if(view==='employees')renderEmployees();else renderResources();}catch(e){if(gen===state.generation)$('#content')?.replaceChildren(el('div',{class:'form-error'},e.message));}
};
platformReload=async function(w=state.workspace.id){if(w!==state.workspace?.id)return;await ui5LoadLibrary();if(state.screen==='company'){if(state.companyView==='employees')renderEmployees();if(state.companyView==='integrations')renderResources();}};
function employeeModel(a){const d=platformState.catalog;return d?.items.find(x=>x.id===(a.data.model_id||d.default_model_id));}
function visibleStaff(){return (platformState.catalog?.items||[]).filter(a=>a.kind==='agent'&&(ui5.showLegacy||a.source?.kind!=='legacy_project_migration'));}
function renderEmployees(){
 const c=$('#content'),data=platformState.catalog;if(!c||!data)return;
 const search=el('input',{class:'input',type:'search',value:ui5.staffQuery,placeholder:'搜索员工名称或专长','aria-label':'搜索AI员工'}),grid=el('div',{class:'employee-grid'}),legacy=el('input',{type:'checkbox',checked:ui5.showLegacy});
 c.replaceChildren(el('div',{class:'hub-toolbar'},search,el('span',{class:'grow'}),data.can_manage&&button('新建 AI 员工',()=>employeeEditor(),{class:'primary',icon:'plus'})),el('label',{class:'field-check legacy-filter'},legacy,'显示历史项目专属员工'),grid);
 const draw=()=>{const q=ui5.staffQuery.toLowerCase(),items=visibleStaff().filter(x=>(x.name+' '+x.description).toLowerCase().includes(q));grid.replaceChildren(...items.map(a=>{const m=employeeModel(a);return el('article',{class:'employee-card','data-employee-id':a.id},el('div',{class:'row spread'},el('div',{class:'employee-avatar'},a.name.replace(/^团队/,'').slice(0,2)),badge(a.enabled?'可加入任务':'已停用',a.enabled?'success':'')),el('h2',{},a.name),el('p',{class:'employee-description'},a.description||'团队的自定义专家'),el('div',{class:'employee-model'},icon('spark',14),m?.data?.model||'使用公司默认模型'),el('div',{class:'employee-meta'},el('span',{},a.data.skill_ids.length+' 项技能'),el('span',{},a.data.mcp_ids.length+' 个数据连接'),el('span',{},'v'+a.revision)),el('div',{class:'employee-actions'},button(data.can_manage?'配置员工':'查看员工',()=>employeeEditor(a),{class:'small',icon:'settings'}),button('分配项目',()=>assignEmployee(a),{class:'small primary',icon:'plus',disabled:!a.enabled}),data.can_manage&&button('删除员工',()=>deleteCapability(a),{class:'small danger'})));}));if(!items.length)grid.append(empty('还没有匹配的 AI 员工','新建员工，选择模型并勾选需要的技能与连接。','spark'));};search.addEventListener('input',()=>{ui5.staffQuery=search.value;draw();});legacy.addEventListener('change',()=>{ui5.showLegacy=legacy.checked;draw();});draw();
}
function checkboxCards(name,items,selected=[],emptyText='暂无可用项'){
 const root=el('fieldset',{class:'checkbox-library','data-checkbox-library':name}),search=el('input',{type:'search',class:'input',placeholder:'按名称搜索…','aria-label':'搜索 '+name}),status=el('span',{class:'help'}),list=el('div',{class:'checkbox-grid'});
 root.append(el('div',{class:'selection-tools'},search,status,button('取消全部',()=>{root.querySelectorAll('input[type=checkbox]').forEach(n=>n.checked=false);update();},{class:'small ghost'})),list);
 const update=()=>status.textContent='已选 '+root.querySelectorAll('input[type=checkbox]:checked').length+' 项';
 for(const item of items){const input=el('input',{type:'checkbox',name,value:item.id,checked:selected.includes(item.id),onchange:update});list.append(el('label',{class:'checkbox-card','data-search':(item.name+' '+(item.description||'')).toLowerCase()},input,el('div',{class:'grow'},el('strong',{},item.name),el('small',{},item.description||'版本 '+(item.revision||1)))));}
 if(!items.length)list.append(el('p',{class:'muted'},emptyText));search.addEventListener('input',()=>{list.querySelectorAll('.checkbox-card').forEach(n=>n.hidden=!n.dataset.search.includes(search.value.toLowerCase()));});update();return root;
}
const ui5Checked=(form,name)=>[...form.querySelectorAll('input[name="'+name+'"]:checked')].map(n=>n.value);
async function employeeEditor(a=null){
 await ui5LoadLibrary();const c=platformState.catalog,w=state.workspace.id;
 const pluginCatalog=await api('/workspaces/'+w+'/plugins');
 if(!c.can_manage){openDialog(a.name,markdown(a.data.system_prompt),{wide:true});return;}
 const d=a?.data||{},items=c.items,active=k=>items.filter(x=>x.kind===k&&x.enabled&&(k!=='skill'||x.data.status==='published')&&(k!=='mcp'||x.data.transport!=='builtin'));
 const top=el('div',{class:'employee-editor-title'},el('div',{class:'employee-avatar'},a?.name?.slice(0,2)||'AI'),el('div',{class:'grow'},field('name','员工名称','text',a?.name||'',{attrs:{required:true,maxlength:80}}),field('description','专长与职责','text',a?.description||'',{attrs:{maxlength:2000}})));
 const nav=el('nav',{class:'editor-tabs','aria-label':'员工配置分类'}),panels=el('div',{class:'editor-panels'}),sections={};
 sections.role=el('section',{'data-panel':'role'},field('system_prompt','工作指令','textarea',d.system_prompt||'根据当前任务和授权资料协作。区分事实与建议，引用来源，重要结果交由成员验收。',{attrs:{class:'employee-prompt',maxlength:40000}}),el('p',{class:'help'},'描述这位员工负责什么、如何回答，以及什么情况需要交给人确认。'));
 const modelValue=el('input',{type:'hidden',name:'model_id',value:d.model_id||''}),modelBox=el('div',{class:'selected-model-card'});
 const drawModel=()=>{const model=items.find(x=>x.id===modelValue.value)||items.find(x=>x.id===c.default_model_id);modelBox.replaceChildren(el('div',{class:'row spread'},el('div',{},el('small',{class:'muted'},'当前模型'),el('h3',{},model?.data?.model||'公司默认模型')),button('选择模型',()=>chooseEmployeeModel(modelValue.value,choice=>{modelValue.value=choice.id||'';if(choice.id&&!items.some(x=>x.id===choice.id))items.push(choice);drawModel();}),{icon:'spark'})));if(model?.source?.contributor)modelBox.append(el('p',{class:'notice'},'此 Contributor 模型可能使用输入和输出训练。不要用于未获授权的敏感资料。'));};drawModel();
 sections.model=el('section',{'data-panel':'model',hidden:true},modelValue,modelBox,el('p',{class:'help'},'Go 模型按官方协议接入；可查看本机测试状态。模型连接在团队层共用，不需要为员工重复填写密钥。'));
 sections.skills=el('section',{'data-panel':'skills',hidden:true},el('div',{class:'section-intro'},el('h3',{},'选择这位员工会用的技能'),el('p',{},'直接勾选，可多选；取消勾选即可移除。')),checkboxCards('skill_ids',active('skill'),d.skill_ids||[],'还没有已审核技能，可先到「技能与连接」导入或创建。'));
 sections.tools=el('section',{'data-panel':'tools',hidden:true},el('div',{class:'section-intro'},el('h3',{},'连接真实数据与工具'),el('p',{},'只显示已启用的真实服务；未完成授权的连接不会自动可用。')),checkboxCards('mcp_ids',active('mcp'),d.mcp_ids||[],'暂无已启用连接。先从 MCP 广场选择服务并完成授权。'),button('浏览 MCP 广场',()=>mcpDirectory(),{class:'ghost',icon:'link'}));
 sections.plugins=el('section',{'data-panel':'plugins',hidden:true},el('h3',{},'平台操作插件'),el('p',{class:'help'},'勾选后员工才获得相应工具。写入按本次权限模式确认。团队共享员工的新配置从下次运行生效；当前运行保留原快照，权限和停用实时检查。'),checkboxCards('plugin_ids',pluginCatalog.items,d.plugin_ids||[]));
 sections.knowledge=el('section',{'data-panel':'knowledge',hidden:true},el('h3',{},'继承当前项目的知识与记忆'),el('p',{class:'notice neutral'},'先理解问题和近期讨论，再按需检索相关片段。问候不读文档；技能只先提供名称与简介。已完成操作和旧记录可回读，不读取其他项目的私有材料。'),el('p',{},'读：项目文件、PLAN.md、MEMORY.md、明确发布的公司知识。写：勾选平台插件后，经逐次确认，另存知识／记忆草稿。原件不覆盖。'),el('p',{class:'help'},'工作目录 exports/<项目ID>/space 是可重建 Markdown 副本。页面、@文件和员工工具均以数据库当前版本为准。'),el('p',{class:'help'},'同一任务的执行步骤与工具回执会保存；中断后可以核对再继续。当前一次执行一位员工，尚未开放两个员工并行互相协作。'));
 sections.advanced=el('section',{'data-panel':'advanced',hidden:true},field('soul_md','沟通风格 · SOUL.md','textarea',d.soul_md||'# SOUL\n清楚、诚实、协作。'),field('agents_md','操作规范 · AGENTS.md','textarea',d.agents_md||'# AGENTS\n遵守任务权限，业务结果先待验收。'),field('search_prompt','资料检索规则','textarea',d.search_prompt||'优先核对明确引用的资料，保留出处与版本。'),el('details',{class:'config-details'},el('summary',{},'高级执行限制'),field('harness_id','执行规则','select',d.harness_id||active('harness').find(x=>x.visibility==='workspace')?.id||active('harness')[0]?.id||'',{choices:active('harness').map(x=>[x.id,x.name]),help:'步骤、时间和工具边界使用团队配置。通常无需修改。'}),button('管理执行限制',()=>{dlg.close();ui5.resourceTab='harness';showCompany('integrations');},{class:'small ghost'})),field('visibility','可见范围','select',a?.visibility||'workspace',{choices:[['workspace','团队共享'],['restricted','仅原授权范围']]}),a?.visibility==='restricted'&&el('label',{class:'field-check'},el('input',{type:'checkbox',name:'acknowledge_sharing'}),'已核对配置内容，可共享给整个团队'),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'enabled',checked:a?.enabled!==false}),'启用这位员工'));
 function tab(k){for(const [id,n] of Object.entries(sections))n.hidden=id!==k;nav.querySelectorAll('button').forEach(n=>n.classList.toggle('active',n.dataset.tab===k));}
 for(const [k,label] of [['role','职责'],['model','模型'],['skills','技能'],['knowledge','知识与记忆'],['plugins','平台插件'],['tools','数据连接'],['advanced','高级']])nav.append(el('button',{type:'button','data-tab':k,class:k==='role'?'active':'',onclick:()=>tab(k)},label));panels.append(...Object.values(sections));
 const dlg=formDialog(a?'配置员工 · '+a.name:'新建 AI 员工',[top,nav,panels],async(v,form)=>{const data={system_prompt:v.system_prompt,soul_md:v.soul_md,agents_md:v.agents_md,search_prompt:v.search_prompt,model_id:v.model_id,harness_id:v.harness_id,skill_ids:ui5Checked(form,'skill_ids'),mcp_ids:ui5Checked(form,'mcp_ids'),plugin_ids:ui5Checked(form,'plugin_ids')};await api(a?'/platform/assets/'+a.id:platformURL(w,'/assets'),{method:a?'PATCH':'POST',body:{kind:'agent',name:v.name,description:v.description,data,visibility:v.visibility,enabled:form.elements.enabled.checked,expected_revision:a?.revision,acknowledge_sharing:!!form.elements.acknowledge_sharing?.checked}});await platformReload(w);toast('员工配置已保存，项目可按需更新版本');},{wide:true,submit:'保存员工'});dlg.dialog.classList.add('employee-editor');
}
async function chooseEmployeeModel(current,onSelect){
 const w=state.workspace.id;await ui5LoadLibrary();const c=platformState.catalog,root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索模型名称…','aria-label':'搜索模型'}),list=el('div',{class:'model-choice-grid'});root.append(search,list);const dlg=openDialog('选择模型',root,{wide:true,description:'官方 Go 模型目录 · 本机验证状态与供应方协议分开显示'});
 const choose=async m=>{try{let a=c.items.find(x=>x.kind==='model'&&x.data.model===m.id&&x.data.configured);if(!a)a=await api('/workspaces/'+w+'/go-models/prepare',{method:'POST',body:{model_id:m.id}});onSelect(a);dlg.close();}catch(e){handle(e);}};
 const draw=()=>{const q=search.value.toLowerCase();list.replaceChildren(button('使用公司默认模型',()=>{onSelect({id:''});dlg.close();},{class:'model-default'}));for(const m of ui5.models.filter(m=>(m.name+' '+m.id).toLowerCase().includes(q))){const status=m.verification?.status||'not_tested',pass=status==='passed';list.append(el('button',{type:'button',class:'model-choice','data-model-id':m.id,onclick:()=>choose(m)},el('div',{class:'row spread'},el('strong',{},m.name),badge(pass?'本机通过':status==='not_tested'?'待验证':'查看测试结果',pass?'success':'warning')),el('small',{},m.id),el('span',{class:'help'},m.protocol+(m.contributor?' · 可能用于供应商训练':'')),m.verification?.error&&el('small',{class:'muted'},m.verification.error)));}for(const a of c.items.filter(a=>a.kind==='model'&&a.data.configured&&!ui5.models.some(m=>m.id===a.data.model)&&(a.name+' '+a.data.model).toLowerCase().includes(q)))list.append(button(a.name+' · '+a.data.model,()=>{onSelect(a);dlg.close();},{class:'model-choice'}));};search.addEventListener('input',draw);draw();search.focus();
}
async function assignEmployee(a){
 const projects=companyProjects().filter(p=>p.role==='owner');if(!projects.length){toast('请先创建项目，或由项目管理员分配员工');return;}
 const states=await Promise.all(projects.map(p=>api('/projects/'+p.id+'/platform-bindings'))),existing=Object.fromEntries(projects.map((p,i)=>[p.id,states[i].items.find(b=>b.asset_id===a.id)]));
 const dlg=formDialog('分配项目 · '+a.name,[el('p',{class:'help'},'同一员工可参与多个项目；各项目的聊天与资料仍然独立。已勾选的项目不会静默升级。'),checkboxCards('project_ids',projects.map(p=>({id:p.id,name:p.title,description:existing[p.id]?.enabled?'当前已启用':'尚未启用'})),projects.filter(p=>existing[p.id]?.enabled).map(p=>p.id)),el('label',{class:'field-check'},el('input',{type:'checkbox',name:'upgrade'}),'同时将已勾选项目更新到当前员工配置')],async(v,form)=>{const wanted=new Set(ui5Checked(form,'project_ids'));for(const p of projects){const old=existing[p.id],enabled=wanted.has(p.id);if(enabled===!!old?.enabled&&!form.elements.upgrade.checked)continue;if(!enabled&&!old)continue;await api('/projects/'+p.id+'/platform-bindings/'+a.id,{method:'PUT',body:{expected_binding_revision:old?.revision||0,asset_revision:a.revision,enabled}});}if(state.project)await reloadCapabilities();toast('项目分配已更新');},{wide:true,submit:'保存分配'});
}

function renderResources(){
 const c=$('#content'),data=platformState.catalog,k=ui5.resourceTab;const titles={skill:'技能库',mcp:'MCP 数据连接',model:'模型连接',harness:'高级执行规则'};
 const tabs=el('nav',{class:'resource-tabs'},...['skill','mcp','model'].map(key=>button(titles[key],()=>{ui5.resourceTab=key;renderResources();},{class:k===key?'active':'ghost'})));if(k==='harness')tabs.append(button('返回技能库',()=>{ui5.resourceTab='skill';renderResources();},{class:'ghost'}));
 const actions=el('div',{class:'row wrap'});if(data.can_manage){if(k==='mcp')actions.append(button('浏览 MCP 广场',mcpDirectory,{class:'primary',icon:'plus'}));else if(k==='skill')actions.append(button('上传本地技能',uploadLocalSkill,{class:'primary',icon:'upload'}));else if(k==='model')actions.append(button('浏览 Go 模型',()=>chooseEmployeeModel('',()=>platformReload()),{class:'primary',icon:'spark'}));actions.append(button('自定义'+(k==='mcp'?'连接':k==='model'?'模型':k==='harness'?'规则':'技能'),()=>ui5OldPlatformEditor(k),{icon:'plus'}));}
 const search=el('input',{class:'input',type:'search',placeholder:'搜索名称…','aria-label':'搜索资源'}),rows=el('div',{class:'resource-grid'});c.replaceChildren(tabs,el('div',{class:'hub-toolbar'},search,el('span',{class:'grow'}),actions),rows);
 const draw=()=>{const items=data.items.filter(a=>a.kind===k&&(k!=='mcp'||a.data.transport!=='builtin')&&a.source?.kind!=='legacy_project_migration'&&(a.name+' '+a.description).toLowerCase().includes(search.value.toLowerCase()));rows.replaceChildren(...items.map(a=>el('article',{class:'resource-card','data-asset-id':a.id},el('div',{class:'row spread'},icon(k==='mcp'?'link':k==='skill'?'plan':'spark',20),badge(a.enabled?(k==='skill'?'已发布':'可用'):(k==='mcp'?'待连接／授权':'未启用'),a.enabled?'success':'')),el('h3',{},a.name),el('p',{},a.description||platformAssetSummary(a)),el('small',{class:'muted'},a.source?.publisher||a.source?.catalog_id||(a.data.model||'v'+a.revision)),el('div',{class:'row wrap'},button(k==='mcp'?'配置连接':'配置',()=>k==='mcp'?mcpConnectionEditor(a):ui5OldPlatformEditor(k,a),{class:'small'}),k==='model'&&button('修改连接',()=>platformModelConnection(a),{class:'small ghost'}),k==='skill'&&button('查看内容',()=>viewLocalSkill(a),{class:'small ghost'}),data.can_manage&&button('删除',()=>deleteCapability(a),{class:'small danger'}),button('版本',()=>platformHistory(a),{class:'small ghost'}),button('导出',()=>download('/capabilities/'+a.id+'/export',a.name+(k==='skill'?'.zip':'.md')),{class:'small ghost'})))));if(!items.length)rows.append(empty('还没有配置','从官方目录接入，或创建团队自己的配置。','link'));};search.addEventListener('input',draw);draw();
}
platformEditor=function(kind,a){return kind==='agent'?employeeEditor(a):kind==='mcp'&&a?mcpConnectionEditor(a):ui5OldPlatformEditor(kind,a);};
async function mcpDirectory(){
 const w=state.workspace.id,root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索数据库、知识源或服务名称','aria-label':'搜索MCP广场'}),rows=el('div',{class:'directory-grid'}),error=el('p',{class:'help'});root.append(el('p',{class:'notice neutral'},'来源：供应商官方文档与 MCP 官方 Registry。数据库需要自己的账号授权；目录收录不等于安全审计或已经连接。'),el('div',{class:'row'},search,button('搜索',()=>load(search.value),{icon:'search'})),error,rows);const dlg=openDialog('MCP 广场',root,{wide:true});let seq=0;
 async function load(q=''){const n=++seq;rows.replaceChildren(el('p',{class:'muted'},'正在读取官方目录…'));try{const result=await api('/workspaces/'+w+'/mcp-directory?q='+encodeURIComponent(q));if(n!==seq||!dlg.dialog.isConnected)return;error.textContent=result.warning||'';rows.replaceChildren(...result.items.map(x=>el('article',{class:'directory-card'},el('div',{class:'row spread'},badge(x.category),el('small',{class:'muted'},x.publisher)),el('h3',{},x.name),el('p',{},x.description),el('a',{href:x.documentation,target:'_blank',rel:'noopener noreferrer'},'供应商接入说明 ↗'),el('small',{},x.authentication==='none'?'无需账号认证':'需要自己的账户授权'),button('添加连接',async()=>{try{const a=await api('/workspaces/'+w+'/mcp-directory/import',{method:'POST',body:{catalog_id:x.id}});await platformReload(w);dlg.close();mcpConnectionEditor(a);}catch(e){handle(e);}},{class:'primary small',icon:'plus'}))));if(!result.items.length)rows.append(el('p',{class:'muted'},'没有匹配的远程服务；可在供应商文档中检查接入方式。'));}catch(e){rows.replaceChildren(el('p',{class:'form-error'},e.message));}}
 search.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();load(search.value);}});await load();
}
async function mcpConnectionEditor(a){
 const w=a.workspace_id;await ui5LoadLibrary();if(!platformState.catalog.can_manage_mcp){openDialog(a.name,el('p',{},a.description),{wide:true});return;}
 let current=a,tools=a.data.allowed_tools.map(name=>({id:name,name,description:'当前允许的工具'}));const root=el('div'),status=el('p',{class:'notice neutral'},'未执行连接检查。保存配置不代表已连接。'),headers=field('headers','认证头（需要时填写；不回显已保存凭证）','textarea','',{help:'仅填写此服务要求的认证信息。OAuth 交互式登录尚未接入，不会假装已授权。'}),toolbox=el('div'),enabled=el('input',{type:'checkbox',name:'enabled',checked:!!a.enabled});
 root.append(el('p',{class:'muted'},a.description),el('p',{class:'source-line'},a.data.url||a.data.command),a.source?.documentation&&el('a',{href:a.source.documentation,target:'_blank',rel:'noopener noreferrer'},'打开官方接入说明 ↗'),headers,status,el('div',{class:'row wrap'},button('连接并读取工具列表',probe,{icon:'refresh'})),toolbox,el('label',{class:'field-check'},enabled,'启用连接（仍需在 AI 员工中勾选）'));
 function draw(selected){toolbox.replaceChildren(el('h3',{style:'margin-top:20px'},'允许员工使用的工具'),checkboxCards('allowed_tools',tools,selected,'先连接服务读取真实工具列表。'));}
 async function probe(){if(a.data.transport==='stdio'&&!window.confirm('此连接将启动管理员配置的本机程序，确认该程序可信后继续。'))return;status.textContent='正在连接真实服务…';try{const text=$('textarea',headers).value.trim();if(text){await api('/capabilities/'+a.id+'/mcp-credentials',{method:'POST',body:{headers:JSON.parse(text)}});await ui5LoadLibrary();current=platformState.catalog.items.find(x=>x.id===a.id);$('textarea',headers).value='';}const r=await api('/capabilities/'+a.id+'/mcp-test',{method:'POST',body:{acknowledge_host_execution:a.data.transport==='stdio'}});tools=r.tools.map(t=>({id:t.name,name:t.name,description:t.description}));draw(current.data.allowed_tools);status.textContent='已连接，发现 '+tools.length+' 个真实工具。尚未执行数据库查询或业务操作。';}catch(e){status.textContent='连接未完成：'+e.message;}}
 const dlg=openDialog('数据连接 · '+a.name,root,{wide:true,actions:[button('保存选择',async()=>{try{const selected=[...toolbox.querySelectorAll('input[name="allowed_tools"]:checked')].map(x=>x.value);await api('/platform/assets/'+a.id,{method:'PATCH',body:{expected_revision:current.revision,data:{...current.data,allowed_tools:selected},enabled:enabled.checked,acknowledge_host_execution:a.data.transport==='stdio'}});await platformReload(w);dlg.close();toast('连接与工具权限已保存');}catch(e){handle(e);}},{class:'primary'})]});draw(a.data.allowed_tools);
}
// Keep @ above the composer in a fixed portal: zero participation in chat layout.
const ui5OldPicker=showMentionPicker,ui5OldAgentControls=refreshAgentControls,ui5OldRunSelection=runSelection,ui5OldSend=sendMessage;
function positionMentionPopup(){const box=$('#mention-picker'),composer=$('.composer');if(!box||box.hidden||!composer)return;const r=composer.getBoundingClientRect();box.style.left=Math.max(12,Math.min(r.left,innerWidth-320))+'px';box.style.width=Math.min(r.width,640,innerWidth-24)+'px';box.style.bottom=Math.max(12,innerHeight-r.top+8)+'px';box.style.maxHeight=Math.max(120,Math.min(360,r.top-70))+'px';}
showMentionPicker=async function(q='',range=null){const box=$('#mention-picker');if(box){box.classList.add('mention-popup');positionMentionPopup();}await ui5OldPicker(q,range);positionMentionPopup();};
renderDiscussion=function(content){$('#mention-picker')?.remove();ui5OldRenderDiscussion(content);const box=$('#mention-picker');if(box){box.classList.add('mention-popup');document.body.append(box);}const textarea=$('.composer textarea');if(textarea)textarea.placeholder='和团队讨论，输入 @ 邀请 AI 员工或引用文件';$('.composer-bottom')?.prepend(button('技能',openRunSkills,{class:'small ghost',icon:'plan'}));};
window.addEventListener('resize',positionMentionPopup);document.addEventListener('scroll',positionMentionPopup,true);document.addEventListener('pointerdown',e=>{if(!e.target.closest?.('#mention-picker,.composer'))hideMentionPicker();});
function openRunSkills(){const items=state.capabilities.filter(a=>a.kind==='skill'&&a.enabled&&a.data.status==='published');const dlg=formDialog('本次使用的技能',[el('p',{class:'help'},'只选本项目已授权的技能。选择技能不会触发 AI，仍需 @ 一位员工。员工固定配置的技能会继续生效。'),checkboxCards('run_skills',items,ui5.skills)],async(v,form)=>{ui5.skills=ui5Checked(form,'run_skills');refreshAgentControls();},{submit:'应用选择',wide:true});}
runSelection=function(){return {...ui5OldRunSelection(),selected_skill_ids:[...ui5.skills]};};
refreshAgentControls=function(){ui5OldAgentControls();const chips=$('#agent-mention-chips');for(const id of ui5.skills){const s=state.capabilities.find(x=>x.id===id);if(s)chips?.append(el('span',{class:'mention-chip skill'},icon('plan',13),s.name,iconButton('close','移除技能 '+s.name,()=>{ui5.skills=ui5.skills.filter(x=>x!==id);refreshAgentControls();})));}const card=$('#selected-employee-card'),a=selectedAgent();if(card)card.replaceChildren(el('div',{class:'employee-avatar small'},a?.name?.slice(0,2)||'AI'),el('div',{class:'grow'},el('strong',{},a?.name||'邀请 AI 员工'),el('small',{},a?.data?.model||'仅在选择后参与本次讨论')));const b=$('#agent-send-button');if(b&&!a)b.textContent='发送';};
sendMessage=async function(){await ui5OldSend();if(!state.draft&&!state.pendingRunPayload)ui5.skills=[];refreshAgentControls();};
const ui5OldReset=resetView;resetView=function(){hideMentionPicker();ui5.skills=[];ui5OldReset();};
function chooseTaskEmployee(){const employees=state.capabilities.filter(a=>a.kind==='agent'&&a.enabled);const root=el('div',{class:'employee-grid compact'});const dlg=openDialog('邀请 AI 员工参与本次讨论',root,{wide:true,actions:[button('从团队分配更多员工',()=>{dlg.close();openProjectBindings();},{icon:'plus'})]});root.append(button('不选择 AI，仅与成员聊天',()=>{pickAgent(null);dlg.close();},{class:'employee-card plain'}));for(const a of employees)root.append(el('button',{type:'button',class:'employee-card',onclick:()=>{pickAgent(a.id);dlg.close();}},el('div',{class:'employee-avatar'},a.name.slice(0,2)),el('h3',{},a.name),el('p',{},a.description),el('small',{},a.data.model||'项目已绑定模型')));}
const ui5OldTaskContext=taskContextPanel;
taskContextPanel=function(){const panel=ui5OldTaskContext(),section=panel.querySelector('.agent-config-section'),select=section?.querySelector('select');if(select)select.hidden=true;if(section){section.querySelector('h3').textContent='AI 员工';section.insertBefore(el('button',{type:'button',id:'selected-employee-card',class:'employee-picker-card',onclick:chooseTaskEmployee}),select);section.querySelectorAll('button').forEach(b=>{if(b.textContent==='查看配置')b.textContent='员工详情';if(b.textContent==='启用管理')b.textContent='分配员工';});}panel.prepend(iconButton('close','关闭任务侧栏',toggleContext));return panel;};
agentEditor=async function(a){if(!a)return chooseTaskEmployee();await ui5LoadLibrary();const actual=platformState.catalog.items.find(x=>x.id===a.id);if(actual)return employeeEditor(actual);openDialog(a.name,markdown(a.data.system_prompt),{wide:true});};
function toggleContext(){if(innerWidth<=760)ui5.mobileContext=!ui5.mobileContext;else{ui5.contextCollapsed=!ui5.contextCollapsed;localStorage.setItem('gongzhi.context-collapsed',ui5.contextCollapsed?'1':'0');}applyContextState();}
function applyContextState(){const room=$('.task-room');room?.classList.toggle('context-collapsed',ui5.contextCollapsed);room?.classList.toggle('show-context-mobile',!!ui5.mobileContext);const b=$('#toggle-task-context');if(b){const collapsed=innerWidth<=760?!ui5.mobileContext:ui5.contextCollapsed;b.setAttribute('aria-label',collapsed?'展开任务侧栏':'收起任务侧栏');b.title=collapsed?'展开任务侧栏':'收起任务侧栏';b.setAttribute('aria-expanded',String(!collapsed));}queueMicrotask(refreshAgentControls);}
header=function(){const h=ui5OldHeader();if(state.task){const b=iconButton('plan','收起任务侧栏',toggleContext);b.id='toggle-task-context';h.querySelector('.project-title-row')?.append(b);}return h;};
renderView=function(){ui5OldRenderView();applyContextState();};
capabilityLibrary=function(){return chooseTaskEmployee();};

async function renderPeople(){
 const w=state.workspace.id,gen=state.generation,result=await api('/workspaces/'+w+'/people',{signal:state.controller.signal});if(gen!==state.generation)return;const c=$('#content'),rows=el('div',{class:'people-list'});
 c.replaceChildren(el('div',{class:'hub-toolbar'},el('h2',{},result.items.length+' 位团队成员'),el('span',{class:'grow'}),result.can_manage&&button('创建账号',()=>newMemberForm(false),{class:'primary',icon:'plus'}),result.can_manage&&button('邀请加入',()=>newMemberForm(true),{icon:'link'}),result.can_manage&&button('添加已有账号',addExistingMember,{class:'ghost'})),rows);
 for(const m of result.items){const actions=el('div',{class:'row wrap'});if(result.can_manage){actions.append(button('分配项目',()=>assignMember(m),{class:'small'}),button('修改权限',()=>editMemberRole(m),{class:'small ghost'}));if(Number(m.user_id)!==Number(state.user.id))actions.append(button('移出团队',()=>confirmAction('移出 '+m.display_name,'将撤销此成员在本团队和所属项目的权限，不删除历史消息和作者身份。',async()=>{await api('/workspaces/'+w+'/members/'+m.user_id,{method:'DELETE'});await renderPeople();}),{class:'small danger'}));}rows.append(el('article',{class:'person-row'},avatar(m.display_name),el('div',{class:'grow'},el('div',{class:'row wrap'},el('strong',{},m.display_name),m.category==='learner'&&badge('学员'),badge(labels[m.role]||m.role),Number(m.user_id)===Number(state.user.id)&&badge('你')),el('small',{},m.username),el('div',{class:'row wrap'},m.projects.map(p=>badge(p.title)))),actions));}
 if(result.can_manage){const invitations=el('section',{class:'invitation-list'},el('h3',{},'邀请记录'));for(const i of result.invitations.slice(0,12))invitations.append(el('div',{class:'list-row'},icon('link',16),el('div',{class:'grow'},el('strong',{},i.category==='learner'?'学员邀请':'成员邀请'),el('small',{},'到期 '+stamp(i.expires_at))),badge(({pending:'待加入',used:'已加入',revoked:'已撤回',expired:'已过期'})[i.status]),i.status==='pending'&&button('撤回',async()=>{await api('/workspaces/'+w+'/company-invites/'+i.id,{method:'DELETE'});await renderPeople();},{class:'small ghost'})));if(!result.invitations.length)invitations.append(el('p',{class:'muted'},'尚未发出邀请。链接一次有效，不会自动发送邮件。'));c.append(invitations);}
 c.append(el('p',{class:'help'},'成员加入团队后，需被分配到项目，才能进入任务与同事共同聊天。普通消息不会触发 AI；只有明确选择 AI 员工才会调用模型。'));
}
function memberProjectChoices(){return companyProjects().filter(p=>p.role==='owner').map(p=>({id:p.id,name:p.title,description:p.goal||'可分配的项目'}));}
function newMemberForm(inviteMode){
 const fields=[];if(!inviteMode)fields.push(field('display_name','姓名','text','',{attrs:{required:true,maxlength:80}}),field('username','登录用户名','text','',{attrs:{required:true,minlength:3,pattern:'[A-Za-z0-9][A-Za-z0-9_.-]{2,63}'}}),field('password','初始密码','password','',{attrs:{required:true,minlength:12,maxlength:200,autocomplete:'new-password'},help:'至少12位，建议包含大小写字母、数字和符号；不会在保存结果中回显。'}));
 fields.push(el('div',{class:'field-row'},field('category','成员类型','select','member',{choices:[['member','团队成员'],['learner','学员']]}),field('role','访问权限','select','member',{choices:[['member','可讨论与协作'],['viewer','只读查看']]})),el('h3',{},'同时加入这些项目'),checkboxCards('project_ids',memberProjectChoices(),[]));
 if(inviteMode)fields.push(field('invite_origin','团队访问地址','url',location.origin,{attrs:{required:true},help:'跨电脑访问需要已部署的团队域名。本机127.0.0.1链接不能被另一台电脑访问。'}));
 formDialog(inviteMode?'邀请成员加入':'创建团队账号',fields,async(v,form)=>{const w=state.workspace.id,payload={...v,project_ids:ui5Checked(form,'project_ids')};delete payload.invite_origin;const result=await api('/workspaces/'+w+(inviteMode?'/company-invites':'/accounts'),{method:'POST',body:payload});await renderPeople();if(inviteMode){const u=new URL(v.invite_origin);if(!['https:','http:'].includes(u.protocol))throw new Error('邀请地址必须是HTTP或HTTPS');const link=u.origin+'/?team_invite='+encodeURIComponent(result.token);openDialog('邀请链接已生成',el('div',{},el('p',{},'有效期72小时，一次使用。可以撤回；不会自动发送消息。'),el('input',{class:'input',value:link,readOnly:true,'aria-label':'团队邀请链接',onclick:e=>e.target.select()}),['localhost','127.0.0.1'].includes(u.hostname)&&el('p',{class:'notice'},'当前仍是本机访问地址。请先配置团队可访问的 HTTPS 入口，再把链接发给其他电脑。')),{actions:[button('复制链接',async()=>{try{await navigator.clipboard.writeText(link);toast('链接已复制');}catch{toast('请选中链接后复制');}},{icon:'link'})]});}else toast('账号已创建，请安全告知该成员登录信息');},{wide:true,submit:inviteMode?'生成邀请链接':'创建账号'});
}
function addExistingMember(){formDialog('添加已有账号',[field('username','已注册用户名','text','',{attrs:{required:true}}),field('role','团队权限','select','member',{choices:[['member','成员'],['viewer','只读']]} )],async v=>{await api(companyPath('/members'),{method:'POST',body:v});await renderPeople();toast('已有账号已加入团队，请按需分配项目');},{submit:'添加成员'});}
function assignMember(m){formDialog('给 '+m.display_name+' 分配项目',[el('p',{class:'help'},'这里只新增项目权限，不会覆盖已有角色或删除历史记录。'),checkboxCards('project_ids',memberProjectChoices(),m.projects.map(p=>p.id)),field('role','新增项目权限','select',m.role==='viewer'?'viewer':'member',{choices:[['member','可讨论与协作'],['viewer','只读']]} )],async(v,form)=>{await api(companyPath('/people/'+m.user_id+'/projects'),{method:'PUT',body:{role:v.role,project_ids:ui5Checked(form,'project_ids')}});await renderPeople();},{wide:true,submit:'保存项目分配'});}
function editMemberRole(m){formDialog('修改团队权限',[field('role','角色','select',m.role,{choices:[['owner','团队管理员'],['member','成员'],['viewer','只读']]}),el('p',{class:'help'},'团队管理员不等于系统管理员。只读成员不能发言或触发 AI；项目仍保留独立访问权限。')],async v=>{await api(companyPath('/members'),{method:'POST',body:{username:m.username,role:v.role}});const ws=await api('/workspaces');state.workspaces=ws.items;state.workspace=ws.items.find(w=>w.id===state.workspace.id);await renderPeople();},{submit:'保存权限'});}
companySettings=async function(){const w=state.workspace;const root=el('div',{},el('h3',{},w.name),el('p',{class:'muted'},w.description||'团队工作空间'));const actions=[button('管理团队成员',()=>{dlg.close();showCompany('people');},{icon:'users',class:'primary'})];if(companyOwner())actions.push(button('修改团队信息',()=>{dlg.close();formDialog('团队信息',[field('name','团队名称','text',w.name,{attrs:{required:true,maxlength:120}}),field('description','简介','textarea',w.description||'')],async v=>{const updated=await api(companyPath(),{method:'PATCH',body:{...v,expected_revision:w.revision}});Object.assign(state.workspace,updated);await showCompany('overview');});}));const dlg=openDialog('团队设置',root,{actions});};
function renderTeamInvitation(existing=false){
 const token=new URLSearchParams(location.search).get('team_invite'),form=el('form'),error=el('div');if(!existing)form.append(field('display_name','姓名','text','',{attrs:{required:true}}));form.append(field('username','用户名','text','',{attrs:{required:true,autocomplete:'username'}}),field('password',existing?'密码':'设置密码','password','',{attrs:{required:true,minlength:existing?1:12,autocomplete:existing?'current-password':'new-password'}}),error);const submit=el('button',{type:'submit',class:'btn primary submit'},existing?'登录并加入团队':'接受邀请并加入团队');form.append(submit);form.addEventListener('submit',async e=>{e.preventDefault();submit.disabled=true;error.replaceChildren();try{const v=values(form);let result;if(existing){result=await api('/api/auth/login',{team:false,method:'POST',body:v});storeSession(result);result=await api('/workspace-invites/join',{method:'POST',body:{token}});}else{result=await api('/api/setup/team/workspace-redeem',{team:false,method:'POST',body:{...v,token}});storeSession(result);}history.replaceState({},'',location.pathname+'#workspace='+result.workspace_id);await loadProjects();}catch(e){error.append(el('p',{class:'form-error'},e.message));}finally{submit.disabled=false;}});app.replaceChildren(el('main',{class:'team-invite-page'},el('section',{class:'auth-card'},brand(),el('h1',{},'加入共同的工作空间'),el('p',{class:'muted'},'和同事一起讨论，在需要时邀请 AI 员工。无需验证码。'),form,button(existing?'创建新账号加入':'已有账号，登录加入',()=>renderTeamInvitation(!existing),{class:'ghost'}))));
}
bootstrap=async function(){const token=new URLSearchParams(location.search).get('team_invite');if(!token)return ui5OldBootstrap();if(!state.token){renderTeamInvitation();return;}try{const me=await api('/api/auth/me',{team:false});state.user=me.user||me;await loadProjects();confirmAction('接受团队邀请','使用当前账号加入邀请指定的团队和项目。',async()=>{const r=await api('/workspace-invites/join',{method:'POST',body:{token}});history.replaceState({},'',location.pathname+'#workspace='+r.workspace_id);await loadProjects();},{label:'接受邀请'});}catch(e){sessionStorage.removeItem(SESSION);state.token=null;renderTeamInvitation(true);}};

// 0.6: no provider network requests while opening a workspace page.
const v6={libraryFlight:null,modelGroups:[],modelSelected:new Map(),plugins:[],loadGeneration:0};
ui5LoadLibrary=async function(){
 const w=state.workspace.id,key=w+':'+state.user?.id+':'+state.generation;
 if(v6.libraryFlight?.key===key)return v6.libraryFlight.promise;
 const generation=state.generation,signal=state.controller?.signal;
 const promise=(async()=>{try{const c=await api(platformURL(w),{signal});if(w===state.workspace?.id&&generation===state.generation)platformState.catalog=c;return c;}finally{if(v6.libraryFlight?.key===key)v6.libraryFlight=null;}})();
 v6.libraryFlight={key,promise};return promise;
};
const v6OldResource=renderResources;
renderResources=function(){
 if(ui5.resourceTab==='model'){renderProviderGroups().catch(handle);return;}
 if(ui5.resourceTab==='plugin'){renderPluginLibrary().catch(handle);return;}
 v6OldResource();const nav=$('.resource-tabs');nav?.replaceWith(resourceNavigation(ui5.resourceTab));
 if(ui5.resourceTab==='skill'&&platformState.catalog?.can_manage){$('.hub-toolbar .row')?.append(button('添加协作技能包',openStarterSkills,{class:'small'}));}
};
function resourceNavigation(active){return el('nav',{class:'resource-tabs'},...[['skill','技能库'],['plugin','平台插件'],['mcp','MCP 数据连接'],['model','模型厂商']].map(([key,label])=>button(label,()=>{ui5.resourceTab=key;renderResources();},{class:key===active?'active':'ghost'})));}
async function renderPluginLibrary(){
 const w=state.workspace.id,gen=state.generation,c=$('#content');c.replaceChildren(resourceNavigation('plugin'),el('p',{class:'muted'},'载入插件…'));
 const result=await api('/workspaces/'+w+'/plugins',{signal:state.controller.signal});if(gen!==state.generation||state.screen!=='company'||state.companyView!=='integrations'||ui5.resourceTab!=='plugin')return;v6.plugins=result.items;
 c.replaceChildren(resourceNavigation('plugin'),el('div',{class:'section-intro'},el('h2',{},'让员工真正操作项目'),el('p',{},'技能说明怎么做；插件决定能做什么。在员工配置中勾选，再明确更新项目授权。写入操作逐次确认。')),el('div',{class:'resource-grid'},result.items.map(p=>el('article',{class:'resource-card'},el('div',{class:'row spread'},icon('tasks',22),badge(p.write?'写入前确认':'只读','success')),el('h3',{},p.name),el('p',{},p.description),el('details',{},el('summary',{},p.tools.length+' 项真实工具'),el('pre',{},p.tools.join('\n')))))),el('p',{class:'notice neutral'},'当前支持项目规划、日程、任务、知识、技能草稿和受限文件产出。插件不等于任意控制电脑；没有开放系统账号、密钥、任意命令或跨项目操作。'));
}
async function openStarterSkills(){
 const w=state.workspace.id,r=await api('/workspaces/'+w+'/skill-starters');formDialog('团队协作技能包',[el('p',{class:'help'},'这些是有明确操作步骤的协作规范，不会自动授予插件权限或挂载到员工。'),checkboxCards('starter_ids',r.items,r.items.map(x=>x.id))],async(v,f)=>{await api('/workspaces/'+w+'/skill-starters/import',{method:'POST',body:{ids:ui5Checked(f,'starter_ids')}});await platformReload(w);toast('技能包已加入团队，可在员工中勾选');},{wide:true,submit:'添加所选技能'});
}
async function loadModelGroups(){const w=state.workspace.id,r=await api('/workspaces/'+w+'/model-providers',{signal:state.controller.signal});if(w===state.workspace?.id)v6.modelGroups=r.items;return r;}
function modelStatus(a){const s=a.verification?.status;return a.archived?'已移除':s==='passed'?'测试通过':s==='failed'?'测试失败':s==='needs_review'?'响应待检查':a.enabled?'未测试':'已停用';}
async function renderProviderGroups(){
 const c=$('#content'),w=state.workspace.id,gen=state.generation;c.replaceChildren(resourceNavigation('model'),el('p',{class:'muted'},'加载已保存厂商…'));
 const data=await loadModelGroups();if(gen!==state.generation||state.screen!=='company'||state.companyView!=='integrations'||ui5.resourceTab!=='model')return;
 const search=el('input',{class:'input',type:'search',placeholder:'搜索厂商或模型 ID','aria-label':'搜索模型厂商'}),list=el('div',{class:'provider-groups'});
 c.replaceChildren(resourceNavigation('model'),el('div',{class:'hub-toolbar'},search,el('span',{class:'grow'}),data.can_manage&&button('添加厂商',()=>providerForm(),{class:'primary',icon:'plus'})),el('p',{class:'help'},'一次保存厂商接口和密钥，发现并勾选多个模型。目录可见不代表账号可调用；测试结果逐项保留。移除仅影响本站配置，不删除供应方模型。'),list);
 const draw=()=>{const q=search.value.toLowerCase();list.replaceChildren();for(const vendor of data.items){const models=vendor.models.filter(a=>!a.archived&&(vendor.name+' '+a.name+' '+a.data.model).toLowerCase().includes(q));if(q&&!models.length)continue;
  const selected=v6.modelSelected.get(vendor.id)||new Set();v6.modelSelected.set(vendor.id,selected);
  const controls=el('div',{class:'row wrap'});if(data.can_manage)controls.append(button('发现模型',()=>discoverModels(vendor),{class:'small',icon:'refresh'}),button('手动添加',()=>manualModels(vendor),{class:'small ghost'}),button('编辑连接',()=>providerForm(vendor),{class:'small ghost'}),button('删除厂商',()=>deleteVendor(vendor),{class:'small danger'}));
  const table=el('div',{class:'provider-models'}),checkAll=el('input',{type:'checkbox','aria-label':'全选 '+vendor.name});checkAll.addEventListener('change',()=>{for(const a of models){if(checkAll.checked)selected.add(a.id);else selected.delete(a.id);}draw();});checkAll.checked=models.length>0&&models.every(a=>selected.has(a.id));
  const group=el('section',{class:'provider-group','data-provider-id':vendor.id},el('div',{class:'provider-heading'},el('div',{class:'grow'},el('h2',{},vendor.name),el('small',{class:'muted'},vendor.family==='opencode-go'?'OpenCode Go 订阅模型':vendor.family==='opencode'?'OpenCode 独立计费连接':'OpenAI Chat Completions 兼容'),el('p',{class:'help'},vendor.base_url)),controls),el('div',{class:'provider-selection row wrap'},el('label',{class:'field-check'},checkAll,'选择全部'),el('span',{class:'help'},'已选 '+selected.size+' / '+models.length),data.can_manage&&button('测试所选连接',()=>startProviderProbe(vendor,[...selected]),{class:'small',disabled:!selected.size}),data.can_manage&&button('移除所选模型',()=>archiveModels(vendor,[...selected]),{class:'small danger',disabled:!selected.size})),table);
  for(const a of models){const checkbox=el('input',{type:'checkbox',checked:selected.has(a.id),'aria-label':'选择模型 '+a.data.model,onchange:e=>{if(e.target.checked)selected.add(a.id);else selected.delete(a.id);draw();}});table.append(el('div',{class:'provider-model-row','data-model-asset':a.id},checkbox,el('div',{class:'grow'},el('strong',{},a.name),el('small',{},a.data.model)),badge(modelStatus(a),a.verification?.status==='passed'?'success':a.verification?.status==='failed'?'warning':''),a.referenced&&badge('使用中'),a.verification?.at&&el('small',{class:'muted'},stamp(a.verification.at)),data.can_manage&&button('测试',()=>startProviderProbe(vendor,[a.id]),{class:'small ghost'}),data.can_manage&&button('移除',()=>archiveModels(vendor,[a.id]),{class:'small ghost'})));}
  if(!models.length)table.append(el('p',{class:'muted'},'尚未添加模型；先发现目录，或手动填写模型 ID。'));if(vendor.last_error)group.append(el('p',{class:'notice'},vendor.last_error));list.append(group);
 }if(!list.children.length)list.append(empty('暂无匹配厂商','添加兼容接口，然后从模型目录选择需要的模型。','spark'));};search.addEventListener('input',draw);draw();
}
function providerForm(vendor=null){
 const w=state.workspace.id;formDialog(vendor?'编辑厂商 · '+vendor.name:'添加模型厂商',[field('name','厂商／连接名称','text',vendor?.name||'',{attrs:{required:true,maxlength:80},help:'例如 OpenCode Go、OpenCode、公司网关；不同账号可分别命名。'}),field('base_url','API Base URL','url',vendor?.base_url||'',{attrs:{required:true},help:'OpenAI Chat Completions 兼容地址，通常以 /v1 结尾；不填写 /chat/completions。'}),field('models_url','模型目录 URL（留空使用 Base URL/models）','url',vendor?.models_url||'',{help:'必须与API同一主机。供应方不提供目录时，可以手动添加模型ID。'}),field('api_key','API Key','password','',{attrs:{required:!vendor,autocomplete:'new-password'},help:vendor?'留空保留；更换API地址必须重新提供。':'只存服务器，不在模型清单和导出中回显。'})],async v=>{const body={...v,expected_revision:vendor?.revision};if(!body.models_url)delete body.models_url;const saved=await api(vendor?'/model-providers/'+vendor.id:'/workspaces/'+w+'/model-providers',{method:vendor?'PATCH':'POST',body});await ui5LoadLibrary();await renderProviderGroups();toast('厂商连接已保存，尚未调用模型');},{wide:true,submit:'保存厂商'});
}
async function discoverModels(vendor){
 const root=el('div',{},el('p',{class:'muted'},'正在请求供应方 /models；不会进行模型生成…'));const dlg=openDialog('发现模型 · '+vendor.name,root,{wide:true});
 try{const r=await api('/model-providers/'+vendor.id+'/discover',{method:'POST'});if(!dlg.dialog.isConnected)return;const existing=new Set(vendor.models.filter(a=>!a.archived).map(a=>a.data.model));const choices=r.items.map(m=>({id:m.id,name:m.name||m.id,description:(existing.has(m.id)?'本站已添加 · ':'')+m.id}));root.replaceChildren(el('p',{class:'help'},'从供应方实时读取 '+choices.length+' 项；仅添加你勾选的模型。'),checkboxCards('discovered_model_ids',choices,[]),button('添加勾选模型',async()=>{try{const ids=ui5Checked(root,'discovered_model_ids');if(!ids.length)throw new Error('请至少选择一个模型');await api('/model-providers/'+vendor.id+'/models',{method:'POST',body:{model_ids:ids}});dlg.close();await ui5LoadLibrary();await renderProviderGroups();}catch(e){handle(e);}},{class:'primary'}));}catch(e){root.replaceChildren(el('p',{class:'form-error'},e.message),button('改为手动添加',()=>{dlg.close();manualModels(vendor);},{class:'ghost'}));}
}
function manualModels(vendor){formDialog('手动添加模型 · '+vendor.name,[field('model_ids','模型 ID（每行一个）','textarea','',{attrs:{required:true},help:'使用供应方准确的模型ID，不填写展示名称。'})],async v=>{const ids=v.model_ids.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);await api('/model-providers/'+vendor.id+'/models',{method:'POST',body:{model_ids:ids}});await ui5LoadLibrary();await renderProviderGroups();},{wide:true,submit:'添加模型'});}
function archiveModels(vendor,ids){if(!ids.length)return;confirmAction('移除 '+ids.length+' 个模型','只从本站清单移除，历史记录保留。默认模型或仍被员工／项目使用的模型会阻止移除，请先更换绑定。',async()=>{const r=await api('/model-providers/'+vendor.id+'/models/archive',{method:'POST',body:{asset_ids:ids}});v6.modelSelected.delete(vendor.id);await ui5LoadLibrary();await renderProviderGroups();const blocked=r.results.filter(x=>x.status==='blocked_in_use').length;toast('已移除 '+(r.results.length-blocked)+' 项'+(blocked?'；'+blocked+' 项仍在使用，未移除':''));},{danger:true,label:'确认移除'});}
function startProviderProbe(vendor,ids){if(!ids.length)return;confirmAction('测试 '+ids.length+' 个模型','每个模型发送一次简短代码请求，最多输出512 token；可能消耗供应方额度。不会自动重试。',async()=>{const job=await api('/model-providers/'+vendor.id+'/test',{method:'POST',body:{asset_ids:ids}});const progress=el('p',{class:'notice neutral'},'测试已开始'),rows=el('div');const dlg=openDialog('模型连接测试 · '+vendor.name,el('div',{},progress,rows),{wide:true,actions:[button('停止后续测试',async()=>{await api('/model-probes/'+job.id+'/cancel',{method:'POST'});progress.textContent='已请求停止；正在进行的单次调用可能仍会产生用量。';},{class:'danger'})]});
 async function poll(){if(!dlg.dialog.isConnected)return;try{const r=await api('/model-probes/'+job.id);progress.textContent='已完成 '+r.results.length+' / '+r.selected+' · '+r.status;rows.replaceChildren(...r.results.map(x=>el('div',{class:'list-row'},el('strong',{class:'grow'},x.model_id),badge(x.status==='passed'?'通过':x.status==='failed'?'失败':'待核对',x.status==='passed'?'success':'warning'),el('small',{},x.error_type||x.usage?.total_tokens&&x.usage.total_tokens+' token'||''))));if(r.status==='running')setTimeout(poll,900);else{await ui5LoadLibrary();if(state.companyView==='integrations'&&ui5.resourceTab==='model')await renderProviderGroups();}}catch(e){progress.textContent=e.message;}}poll();},{label:'开始测试'});}
chooseEmployeeModel=async function(current,onSelect){
 const result=await loadModelGroups(),root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索厂商或模型','aria-label':'搜索模型'}),list=el('div',{class:'grouped-model-picker'});root.append(search,list);const dlg=openDialog('选择模型',root,{wide:true,description:'按厂商分组，仅显示本站已添加且启用的模型。'});
 const draw=()=>{const q=search.value.toLowerCase();list.replaceChildren(button('使用公司默认模型',()=>{onSelect({id:''});dlg.close();},{class:'model-default'}));for(const v of result.items){const models=v.models.filter(a=>!a.archived&&a.enabled&&(v.name+' '+a.name+' '+a.data.model).toLowerCase().includes(q));if(!models.length)continue;list.append(el('h3',{class:'model-group-title'},v.name),el('div',{class:'model-choice-grid'},models.map(a=>el('button',{type:'button',class:'model-choice','data-model-id':a.data.model,onclick:()=>{onSelect(a);dlg.close();}},el('strong',{},a.name),el('small',{},a.data.model),badge(modelStatus(a),a.verification?.status==='passed'?'success':'')))));}if(list.children.length===1)list.append(el('p',{class:'muted'},'没有匹配模型，请到「技能与连接 → 模型厂商」添加。'));};search.addEventListener('input',draw);draw();search.focus();
};

const v6OriginalApi=api;
api=async function(path,options={}){
 if((options.method||'GET').toUpperCase()!=='GET')return v6OriginalApi(path,options);
 const control=new AbortController(),relay=()=>control.abort(),timer=setTimeout(()=>control.abort('timeout'),18000);
 if(options.signal?.aborted)control.abort();else options.signal?.addEventListener('abort',relay,{once:true});
 try{return await v6OriginalApi(path,{...options,signal:control.signal});}
 catch(e){if(control.signal.aborted&&!options.signal?.aborted){const error=new Error('读取超时，请刷新重试；服务端已记录慢请求。');error.name='TimeoutError';throw error;}throw e;}
 finally{clearTimeout(timer);options.signal?.removeEventListener('abort',relay);}
};

// 0.7: stable navigation, project knowledge workspace and explicit marketplace access.
const v7={spaceRequest:0,previewRequest:0,executionRequest:0};
const RESOURCE_TABS=Object.freeze([['skill','技能库'],['plugin','平台插件'],['mcp','MCP 数据连接'],['model','模型厂商']].map(Object.freeze));
resourceNavigation=function(active){return el('nav',{class:'resource-tabs','aria-label':'技能与连接分类'},...RESOURCE_TABS.map(([key,label])=>el('button',{type:'button','data-resource-tab':key,class:'btn '+(key===active?'active':'ghost'),'aria-selected':String(key===active),onclick:()=>{ui5.resourceTab=key;renderResources();}},label)));};
const v7Resources=renderResources;
renderResources=function(){v7Resources();if(ui5.resourceTab==='skill')$('.hub-toolbar .row')?.prepend(button('技能广场',openSkillMarket,{class:'primary',icon:'search'}));};
const v7TaskPanel=taskContextPanel;
taskContextPanel=function(){const panel=v7TaskPanel(),box=el('section',{class:'context-section project-memory-panel','data-project-memory-panel':''},el('div',{class:'row spread'},el('h3',{},'知识与记忆'),button('全部文件',openProjectSpace,{class:'small ghost'})),el('p',{class:'help'},'当前项目共享目录 · 原件保留 · 记忆有来源'),el('div',{class:'project-memory-list'},'正在读取项目目录…'),el('div',{class:'row wrap'},button('整理项目资料',prepareKnowledgeTask,{class:'small'}),button('执行过程',openExecutionProgress,{class:'small ghost'})));panel.insertBefore(box,panel.querySelector('.context-section')?.nextSibling||null);queueMicrotask(()=>loadPanelFiles(box));return panel;};
async function loadPanelFiles(box){const p=state.project?.id,gen=state.generation;if(!p)return;try{const r=await api('/projects/'+p+'/space?limit=12',{signal:state.controller.signal});if(gen!==state.generation||!box.isConnected)return;const list=$('.project-memory-list',box);list.replaceChildren(...r.items.map(x=>el('button',{type:'button',class:'project-file-mini',title:x.path,onclick:()=>previewProjectFile(x,p)},icon('files',14),el('span',{class:'grow'},x.title),el('small',{},x.readable?(x.adopted?'已确认':'待核对'):'待解析'))));}catch(e){if(e.name!=='AbortError'&&box.isConnected)$('.project-memory-list',box).textContent=e.message;}}
function prepareKnowledgeTask(){if(!state.task){toast('请先进入具体任务，再邀请员工整理项目资料');return;}const a=selectedAgent();if(!a){chooseTaskEmployee();toast('先选择本次员工，再点「整理项目资料」');return;}const text='请先用 project_files_list 查看当前项目目录，再按需读取文件。整理原始资料、已确认记忆、冲突和缺口，保留文件ID与版本；不要覆盖原件。需要写入时提出带来源的 Markdown 记忆草稿，等待确认后保存。';state.draft=text;const field=$('.composer textarea');if(field){field.value=text;field.focus();}toast('整理请求已放入输入框，发送后开始');}
async function openProjectSpace(){if(!state.project)return;const p=state.project.id,root=el('div'),search=el('input',{class:'input',type:'search',placeholder:'搜索资料名、文件名或路径','aria-label':'搜索项目文件'}),list=el('div',{class:'project-space-list'}),message=el('p',{class:'help'});let offset=0,query='',seq=0,more=null;const dlg=openDialog('项目文件 · '+state.project.title,root,{wide:true,description:'你与本项目 AI 员工使用同一份权限受控目录；Markdown 是数据库生成的可读副本，原件不会覆盖。'});const loadMore=button('加载更多',()=>load(false),{class:'ghost'});root.append(search,message,list,loadMore);async function load(reset=true){const n=++seq;if(reset){offset=0;list.replaceChildren();}message.textContent='正在读取…';try{const r=await api('/projects/'+p+'/space?q='+encodeURIComponent(query)+'&offset='+offset+'&limit=60');if(n!==seq||!dlg.dialog.isConnected)return;message.textContent='共 '+r.total+' 个目录项 · '+r.directory;for(const f of r.items)list.append(el('button',{type:'button',class:'project-file-row',onclick:()=>previewProjectFile(f,p)},icon('files'),el('div',{class:'grow'},el('strong',{},f.title),el('small',{},f.path)),badge(f.readable?(f.adopted?'已确认':'待核对'):'未解析'),el('small',{},f.kind==='company'?'公司公开快照':'项目文件')));more=r.has_more;offset=r.next_offset;loadMore.hidden=!more;if(!r.items.length&&reset)list.append(empty('没有匹配文件','上传到项目资料或聊天附件，解析后会出现在同一目录。','files'));}catch(e){message.textContent=e.message;}}let timer;search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{query=search.value;load();},250);});await load();}
function closeFilePreview(){++v7.previewRequest;$('#project-file-preview')?.remove();}
async function previewProjectFile(file,projectId=state.project?.id){
 if(!projectId)return;closeFilePreview();const n=++v7.previewRequest,gen=state.generation;const title=file.title||file.path,body=el('div',{class:'file-preview-body'},el('p',{class:'muted'},'读取中…')),footer=el('div',{class:'file-preview-footer'}),meta=el('p',{class:'help'},file.path);const pane=el('aside',{id:'project-file-preview',class:'file-preview-drawer',role:'dialog','aria-label':'项目文件预览',tabindex:'-1'},el('header',{},el('div',{class:'grow'},el('h2',{},title),meta),iconButton('close','关闭文件预览',closeFilePreview)),body,footer);const openModal=[...document.querySelectorAll('dialog[open]')].at(-1);(openModal||document.body).append(pane);pane.focus();let text='',offset=0,sha=null;
 async function read(){try{const r=await api('/projects/'+projectId+'/space/read?path='+encodeURIComponent(file.path)+'&offset='+offset+'&length=16000');if(n!==v7.previewRequest||gen!==state.generation||!pane.isConnected)return;if(sha&&sha!==r.sha256){body.replaceChildren(el('p',{class:'form-error'},'文件已被更新，请关闭后重新预览，避免混合版本。'));footer.replaceChildren();return;}sha=r.sha256;text+=r.content;offset=r.next_offset;body.replaceChildren(markdown(text));meta.textContent=file.path+' · '+(r.revision?'v'+r.revision:'动态汇总')+' · '+(r.adopted?'已确认':'待核对')+' · '+r.total_characters+' 字符';footer.replaceChildren();if(r.has_more)footer.append(button('读取后续内容',read,{class:'small'}));if(r.document_id&&state.task&&state.project?.id===projectId)footer.append(button('引用到本次讨论',()=>{const item={id:r.document_id,revision:r.revision,type:'document',title:r.title,label:r.title,usable:true};if(!state.mentionDocs.some(d=>d.id===item.id)&&state.mentionDocs.length<6)state.mentionDocs.push(item);refreshAgentControls();closeFilePreview();closeDialogs();$('.composer textarea')?.focus();toast('已引用资料；未选择员工时仅发送真人消息');},{class:'small primary',icon:'link'}));if(r.document_id&&!r.document_id.startsWith('k_')&&canManageProject()&&state.project?.id===projectId)footer.append(button('管理资料',()=>{closeFilePreview();closeDialogs();documentDialog(r.document_id);},{class:'small ghost'}));if(r.has_original)footer.append(button('下载原件',()=>download('/documents/'+r.document_id+'/download',r.filename||r.title),{class:'small ghost',icon:'download'}),el('small',{class:'help'},'此处为解析文本；原始附件保留不变。'));}catch(e){if(pane.isConnected)body.replaceChildren(el('p',{class:'form-error'},e.message));}}
 pane.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeFilePreview();}});await read();
}
async function openExecutionProgress(){if(!state.task)return;const t=state.task.id,p=state.project.id,root=el('div'),status=el('p',{class:'help'}),rows=el('div');const dlg=openDialog('执行过程 · '+state.task.title,root,{wide:true,description:'显示真实模型与工具事件，不显示模型私有思考。当前一次执行一位员工；不会将多人并行冒充已经实现。'});root.append(el('p',{class:'notice neutral'},'当前任务 + 项目文件目录 → 按需读文件 → 模型判断 → 工具调用 → 写入确认 → 实际结果与来源。中断后先看已完成步骤，再由人决定继续，不自动重发。'),button('刷新执行过程',draw,{class:'small',icon:'refresh'}),status,rows);async function draw(){try{const r=await api('/tasks/'+t+'/execution');if(!dlg.dialog.isConnected)return;rows.replaceChildren();status.textContent=r.items.length?'最近 '+r.items.length+' 次执行':'此任务尚无 AI 执行。';for(const run of r.items){const card=el('section',{class:'execution-card'},el('div',{class:'row spread'},el('h3',{},run.agent_name),badge(run.stage)),el('p',{class:'help'},run.model+' · 模型步骤 '+run.model_steps+'/'+(run.max_model_steps||'?')+' · 时限 '+(run.timeout_seconds||'?')+' 秒'),run.error&&el('p',{class:'form-error'},run.error));for(const step of run.steps)card.append(el('div',{class:'execution-step'},badge(step.event==='tool.result'?'工具返回':step.event==='tool.request'?'请求工具':step.event==='approval.required'?'等待确认':step.event==='input.project_workspace'?'目录已注入':step.event),el('span',{},step.tool||'项目知识'),step.receipt?.id&&el('code',{},step.receipt.id),step.receipt?.status&&el('small',{},step.receipt.status)));rows.append(card);}}catch(e){status.textContent=e.message;}}await draw();}
const v7Reset=resetView;resetView=function(){closeFilePreview();++v7.spaceRequest;v7Reset();};
const v7Header=header;header=function(){const h=v7Header();if(state.project)h.querySelector('.project-title-row')?.append(button('项目文件',openProjectSpace,{class:'ghost small',icon:'files'}));return h;};

async function openSkillMarket(){
 const w=state.workspace.id,root=el('div'),nav=el('nav',{class:'resource-tabs','aria-label':'技能来源'}),search=el('input',{class:'input',type:'search',placeholder:'搜索技能名称、用途，例如 planning / 会议纪要','aria-label':'搜索外部技能'}),status=el('p',{class:'help'}),rows=el('div',{class:'directory-grid'});let source='skillhub',seq=0,page=1,cursor='';const dlg=openDialog('技能广场',root,{wide:true,description:'公开技能仅作为待审内容。来源收录、热度和下载量均不代表安全审计；不会自动执行脚本。'});const more=button('下一页',()=>load(false),{class:'ghost'});more.hidden=true;root.append(nav,el('div',{class:'row'},search,button('搜索',()=>load(true),{icon:'search'})),status,rows,more);function tabs(){nav.replaceChildren(...[['skillhub','腾讯 SkillHub'],['clawhub','ClawHub']].map(([id,label])=>button(label,()=>{source=id;tabs();load(true);},{class:source===id?'active':'ghost'})));}
 async function load(reset=true){const n=++seq;if(reset){page=1;cursor='';}status.textContent='正在读取 '+(source==='skillhub'?'SkillHub':'ClawHub')+'，不会调用模型…';more.hidden=true;try{const r=await api('/workspaces/'+w+'/skill-market?source='+source+'&q='+encodeURIComponent(search.value)+'&page='+page+'&cursor='+encodeURIComponent(cursor));if(n!==seq||!dlg.dialog.isConnected)return;status.textContent=r.source_name+' · '+r.items.length+' 项'+(r.total?' / 共 '+r.total:'')+(r.cached?' · 近期缓存':' · 实时结果')+' · 第三方能力仍需配置自身依赖';rows.replaceChildren(...r.items.map(item=>el('article',{class:'directory-card'},el('div',{class:'row spread'},badge(r.source_name),el('small',{},item.owner||'社区作者')),el('h3',{},item.name),el('p',{},item.description),el('small',{},item.version?'v'+item.version:'精确版本在预览中核验'),el('div',{class:'row wrap'},button('预览并导入',()=>previewMarketSkill(item),{class:'small primary'}),el('a',{href:item.url,target:'_blank',rel:'noopener noreferrer'},'来源页面 ↗')))));page=r.next_page||page;cursor=r.next_cursor||'';more.hidden=!r.next_page&&!r.next_cursor;if(!r.items.length)rows.append(empty('未找到匹配技能','可尝试英文关键词，或切换另一个来源。','search'));}catch(e){status.textContent='读取未完成：'+e.message;rows.replaceChildren(el('p',{class:'notice'},'未把旧数据伪装成实时结果；本地技能与聊天仍可使用。'));}}
 search.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();load(true);}});tabs();await load(true);
}
async function previewMarketSkill(item){const w=state.workspace.id,root=el('div',{},el('p',{},'核验版本并读取完整技能包…'));const dlg=openDialog('预览 · '+item.name,root,{wide:true});try{const d=await api('/workspaces/'+w+'/skill-market/preview',{method:'POST',body:{source:item.source,slug:item.slug,owner:item.owner||'',version:item.version||''}});if(!dlg.dialog.isConnected)return;root.replaceChildren(el('p',{class:'notice neutral'},'来源 '+d.source+' · 作者 '+d.owner+' · v'+d.version+' · '+d.files.length+' 个文件。导入后为停用草稿，不自动挂载。'),d.script_files.length?el('p',{class:'notice'},'包含脚本／程序：'+d.script_files.join('、')+'。本平台不会自动运行；审核时需核对依赖和权限。'):el('p',{class:'help'},'未发现常见脚本扩展名；这不是安全保证。'),el('details',{},el('summary',{},'文件清单与校验值'),el('pre',{},d.files.map(f=>f.path+' · '+f.bytes+' B · '+f.sha256).join('\n'))),markdown(d.body));if(platformState.catalog?.can_manage)root.prepend(button('导入停用草稿',()=>confirmAction('导入待审核技能','只保存当前核验版本和附属文件，不执行安装命令，不启用，不分配给员工。',async()=>{await api('/workspaces/'+w+'/skill-market/import',{method:'POST',body:{source:d.source,slug:d.slug,owner:d.owner,version:d.version,expected_sha256:d.sha256,acknowledge_review:true}});dlg.close();await platformReload(w);toast('已导入停用草稿，请审核后发布');}),{class:'primary'}));}catch(e){root.replaceChildren(el('p',{class:'form-error'},e.message));}}
const v7OldMCPDirectory=mcpDirectory;
mcpDirectory=async function(){const w=state.workspace.id,root=el('div',{},el('p',{class:'help'},'目录来源、账号授权、工具启用是三步。国内广场需要使用自己的账号生成服务配置；本应用不代为开通收费服务。')),grid=el('div',{class:'directory-grid'});root.append(grid);const dlg=openDialog('MCP 广场与来源',root,{wide:true});try{const r=await api('/workspaces/'+w+'/mcp-markets');if(!dlg.dialog.isConnected)return;for(const m of r.items)grid.append(el('article',{class:'directory-card'},badge(m.mode==='in_app_search'?'本应用内搜索':'官方目录 · 需本人授权'),el('h3',{},m.name),el('p',{},m.description),el('div',{class:'row wrap'},m.mode==='in_app_search'?button('搜索服务',()=>{dlg.close();v7OldMCPDirectory();},{class:'small primary'}):el('a',{href:m.url,target:'_blank',rel:'noopener noreferrer'},'打开官方广场 ↗'),m.mode!=='in_app_search'&&button('导入远程配置',()=>importMCPConfiguration(m),{class:'small'})),m.documentation&&el('a',{href:m.documentation,target:'_blank',rel:'noopener noreferrer'},'官方接入说明 ↗')));}catch(e){grid.append(el('p',{class:'form-error'},e.message));}};
function importMCPConfiguration(source){const w=state.workspace.id;formDialog('导入 '+source.name+' 远程配置',[field('name','本站连接名称','text','',{attrs:{required:true,maxlength:80}}),field('server_name','配置中服务名称（仅多服务时必填）','text',''),field('config','MCP JSON 配置','textarea','',{attrs:{required:true,autocomplete:'off',spellcheck:'false'},help:'支持 mcpServers 或单条 url/type/headers。专属URL和认证头加密保存，不进入导出和Trace。仅远程HTTP/SSE，不执行本机命令。'}),el('p',{class:'notice'},'保存后仍未连接、未启用。需测试实际服务、选允许工具，再在员工中勾选。授权到期后请重新配置。')],async v=>{let config;try{config=JSON.parse(v.config);}catch{throw new Error('请输入有效 JSON');}const a=await api('/workspaces/'+w+'/mcp-config-import',{method:'POST',body:{source:source.id,name:v.name,server_name:v.server_name||undefined,config}});await platformReload(w);toast('已加密保存，尚未启用；请到数据连接中测试并选择工具');},{wide:true,submit:'保存待配置连接'});}

// 0.8: one navigation path, cancellable reads, and local skill packages.
showCompany=async function(view='overview'){
 if(view==='platform')view='integrations';
 if(!companyViews.some(x=>x[0]===view))view='overview';
 const started=performance.now();resetView();state.screen='company';state.companyView=view;state.project=null;state.tab='tasks';
 // Preserve the sidebar DOM; changing the main panel is immediate, even during reads.
 const shell=$('.app-shell');
 if(!shell||!$('#workspace'))renderShell();else{shell.classList.remove('sidebar-open');$('#workspace').replaceChildren();renderProjectList();}
 document.querySelectorAll('[data-company-view]').forEach(n=>{n.classList.toggle('active',n.dataset.companyView===view);n.setAttribute('aria-current',n.dataset.companyView===view?'page':'false');});
 const names={overview:'以项目和任务组织共同工作。',projects:'先明确目标，再进入任务讨论。',calendar:'你的项目期限、会议与里程碑。',knowledge:'共享资料、记忆和可追溯的成果。',employees:'为团队配置专家，在需要时邀请他们加入任务。',integrations:'团队共用的技能、插件、数据连接与模型。',people:'邀请同事与学员，管理项目访问。'};
 const gen=state.generation,w=state.workspace.id,controller=state.controller;
 const content=el('section',{class:'content hub-content',id:'content','aria-busy':'true'},el('div',{class:'loading-skeleton','aria-label':'正在加载'},el('span',{},'正在读取最新数据…')));
 $('#workspace').append(companyHeader(companyViews.find(x=>x[0]===view)[1],names[view]),content);
 history.replaceState({},'','#workspace='+w+'&view='+view);
 const isCurrent=()=>gen===state.generation&&state.workspace?.id===w&&content.isConnected;
 const timer=setTimeout(()=>{if(isCurrent())controller.abort('navigation-timeout');},7000);
 try{
  if(view==='people')await renderPeople();
  else if(view==='employees'||view==='integrations'){
   await ui5LoadLibrary();if(!isCurrent())return;
   if(view==='employees')renderEmployees();else renderResources();
  }else{
   const data=await api(companyPath('/overview?view='+view),{signal:controller.signal});
   if(!isCurrent())return;state.overview=data;renderCompanyContent();
  }
  if(isCurrent()){content.setAttribute('aria-busy','false');content.dataset.loadedView=view;performance.mark('gongzhi-nav:'+view);const ms=Math.round(performance.now()-started);content.dataset.loadMs=String(ms);}
 }catch(e){
  if(!isCurrent())return;
  const message=controller.signal.reason==='navigation-timeout'?'本次读取超过 7 秒，请重试；不会重复发送消息或运行 AI。':e.message;
  if(e.name!=='AbortError'||controller.signal.reason==='navigation-timeout')content.replaceChildren(el('div',{class:'form-error',role:'alert'},message),button('重新加载',()=>showCompany(view),{class:'primary',icon:'refresh'}));
 }finally{clearTimeout(timer);}
};

function uploadLocalSkill(){
 const w=state.workspace.id,input=el('input',{type:'file',accept:'.zip,application/zip','aria-label':'选择本地Skill压缩包'}),status=el('p',{class:'help'},'ZIP ≤ 5 MB，包含一份 SKILL.md；可放在根目录或单个技能文件夹内。'),preview=el('div'),root=el('div',{},input,status,preview);
 const dlg=openDialog('上传本地技能',root,{wide:true,description:'先检查文件结构和正文，再确认导入。任何脚本都不会自动安装或执行。'});let selected=null,inspection=null,seq=0;
 input.addEventListener('change',async()=>{
  const n=++seq;selected=input.files[0];inspection=null;preview.replaceChildren();if(!selected)return;
  if(selected.size>5*1024*1024){status.textContent='压缩包超过 5 MB，请精简后上传。';return;}
  status.textContent='正在读取压缩包并校验文件…';
  try{
   const form=new FormData();form.set('file',selected);
   const d=await api('/workspaces/'+w+'/local-skills/preview',{method:'POST',body:form});
   if(n!==seq||!dlg.dialog.isConnected)return;inspection=d;status.textContent=d.name+' · '+d.files.length+' 个文件 · SHA-256 '+d.sha256.slice(0,16)+'…';
   const agree=el('input',{type:'checkbox','aria-label':'确认导入为停用草稿'}),save=button('导入停用草稿',async()=>{
    if(!agree.checked||!inspection)return;save.disabled=true;input.disabled=true;
    try{const f=new FormData();f.set('file',selected);f.set('expected_sha256',inspection.sha256);f.set('acknowledge_review','true');const a=await api('/workspaces/'+w+'/local-skills/import',{method:'POST',body:f});dlg.close();await platformReload(w);toast(a.duplicate?'这个压缩包已导入，保留原技能':'已保存停用草稿；尚未挂载给员工');await viewLocalSkill(a);}
    catch(e){status.textContent=e.message;save.disabled=false;input.disabled=false;}
   },{class:'primary',disabled:true});agree.addEventListener('change',()=>save.disabled=!agree.checked);
   preview.replaceChildren(...[d.script_files.length&&el('p',{class:'notice'},'包内含脚本：'+d.script_files.join('、')+'。仅保存和预览，不执行。'),...d.warnings.map(x=>el('p',{class:'notice'},x)),el('details',{},el('summary',{},'完整文件清单'),el('pre',{},d.files.map(x=>x.path+' · '+x.bytes+' B').join('\n'))),el('h3',{},'SKILL.md'),markdown(d.body),el('label',{class:'field-check'},agree,'我确认仅导入停用草稿，审核后再发布和绑定员工'),save].filter(Boolean));
  }catch(e){if(n===seq)status.textContent='不能导入：'+e.message;}
 });
}

async function viewLocalSkill(a){
 const root=el('div',{class:'skill-browser'}),list=el('nav',{class:'skill-file-tree','aria-label':'技能文件列表'}),body=el('section',{class:'skill-file-content'},el('p',{class:'muted'},'正在读取技能…'));
 root.append(list,body);const dlg=openDialog('技能内容 · '+a.name,root,{wide:true,description:'查看实际保存的 SKILL.md 和附属文件。预览不会执行脚本；修改请使用「配置」。'});let seq=0;
 try{
  const r=await api('/skills/'+a.id+'/files');if(!dlg.dialog.isConnected)return;
  async function show(f){const n=++seq;body.replaceChildren(el('p',{class:'muted'},'读取 '+f.path+'…'));list.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.path===f.path));
   try{const d=await api('/skills/'+a.id+'/file?path='+encodeURIComponent(f.path)+'&revision='+r.revision);if(n!==seq||!dlg.dialog.isConnected)return;body.replaceChildren(el('h3',{},f.path),el('p',{class:'help'},'v'+d.revision+' · SHA-256 '+d.sha256.slice(0,16)+'…'),d.format==='markdown'?markdown(d.content):el('pre',{class:'source-code'},d.content));}
   catch(e){if(n===seq)body.replaceChildren(el('p',{class:'notice'},e.message),button('导出完整技能包',()=>download('/capabilities/'+a.id+'/export',a.name+'.zip'),{class:'small'}));}}
  list.append(el('p',{class:'help'},r.files.length+' 个文件 · '+(r.enabled?'已启用':'未启用')),...r.files.map(f=>el('button',{type:'button','data-path':f.path,class:'skill-file-button',onclick:()=>show(f)},f.path)));
  const first=r.files.find(x=>x.path==='SKILL.md')||r.files[0];if(first)await show(first);
 }catch(e){body.replaceChildren(el('p',{class:'form-error'},e.message));}
}
// 0.8.1: persistent left navigation and administrator-controlled reversible deletion.
const leftNav={collapsed:localStorage.getItem('gongzhi.left-collapsed')==='1'};
function applyLeftSidebar(){const shell=$('.app-shell');if(!shell)return;shell.classList.toggle('left-collapsed',leftNav.collapsed);for(const b of document.querySelectorAll('[data-left-nav-toggle]')){const expanded=innerWidth<=760?shell.classList.contains('sidebar-open'):!leftNav.collapsed;b.setAttribute('aria-expanded',String(expanded));b.setAttribute('aria-label',expanded?'收起左侧栏':'展开左侧栏');b.title=expanded?'收起左侧栏':'展开左侧栏';}}
function toggleLeftSidebar(){const shell=$('.app-shell');if(!shell)return;if(innerWidth<=760)shell.classList.toggle('sidebar-open');else{leftNav.collapsed=!leftNav.collapsed;localStorage.setItem('gongzhi.left-collapsed',leftNav.collapsed?'1':'0');}applyLeftSidebar();}
function decorateLeftButton(root){const b=root.querySelector('.project-title-row .icon-btn');if(b){b.dataset.leftNavToggle='true';b.setAttribute('aria-label',leftNav.collapsed?'展开左侧栏':'收起左侧栏');b.title=leftNav.collapsed?'展开左侧栏':'收起左侧栏';b.setAttribute('aria-expanded',String(!leftNav.collapsed));}}
const v81Shell=renderShell;renderShell=function(){v81Shell();const sidebar=$('.sidebar'),brandNode=sidebar?.querySelector('.brand');if(brandNode){const row=el('div',{class:'sidebar-brand-row'});brandNode.replaceWith(row);row.append(brandNode,el('button',{type:'button',class:'icon-btn','data-left-nav-toggle':'true',onclick:toggleLeftSidebar},icon('menu')));}const footer=sidebar?.querySelector('.sidebar-footer');if(footer&&(companyOwner()||companyProjects().some(p=>p.role==='owner')))footer.prepend(button('回收站',()=>openTrash(),{class:'ghost trash-entry',icon:'files'}));applyLeftSidebar();};
const v81CompanyHeader=companyHeader;companyHeader=function(...a){const node=v81CompanyHeader(...a);decorateLeftButton(node);return node;};
const v81Header=header;header=function(){const node=v81Header();decorateLeftButton(node);if(state.project&&canManageProject())node.querySelector('.project-title-row')?.append(button('管理项目',()=>manageProject(state.project),{class:'small ghost',icon:'settings'}));return node;};
window.addEventListener('resize',applyLeftSidebar);
function canManageProject(p=state.project){return !!p&&(p.role==='owner'||(companyOwner()&&companyProjects().some(x=>x.id===p.id)));}
const v81Tile=projectTile;projectTile=function(p){const tile=v81Tile(p);if(!canManageProject(p))return tile;const box=el('article',{class:'managed-project','data-managed-project':p.id},tile,el('div',{class:'project-admin-actions'},button('编辑',()=>manageProject(p),{class:'small ghost',icon:'edit'}),button('删除',()=>deleteProjectDialog(p),{class:'small danger'})));return box;};
async function reloadProjectIndex(){const r=await api('/projects');state.projects=r.items||[];renderProjectList();}
function manageProject(p){formDialog('管理项目 · '+p.title,[field('title','项目名称','text',p.title,{attrs:{required:true,maxlength:120}}),field('goal','项目目标','textarea',p.goal||'',{attrs:{maxlength:4000}}),field('timezone','时区','text',p.timezone||'Asia/Shanghai',{attrs:{required:true}})],async v=>{await api('/projects/'+p.id,{method:'PATCH',body:{...v,expected_revision:p.revision}});await reloadProjectIndex();if(state.project?.id===p.id)await selectProject(p.id);else await showCompany('projects');toast('项目已更新');},{submit:'保存项目',extra:[button('删除项目',()=>deleteProjectDialog(p),{class:'danger left'})]});}
function deleteProjectDialog(p){formDialog('删除项目 · '+p.title,[el('p',{class:'notice'},'项目及其任务、讨论和资料将从正常页面移除，可在回收站恢复。原件与历史不会物理销毁；此项目已发布的公司知识会撤回，恢复项目后不会自动重新公开。'),field('confirm_title','输入完整项目名称确认','text','',{attrs:{required:true},help:p.title})],async v=>{await api('/projects/'+p.id,{method:'DELETE',body:{expected_revision:p.revision,confirm_title:v.confirm_title}});closeDialogs();await reloadProjectIndex();await showCompany('projects');toast('项目已移入回收站');},{submit:'确认删除',wide:true});}
function deleteRecord(record,label){const p=state.project?.id,taskId=state.task?.id;confirmAction('删除'+label+' · '+record.title,label==='任务'?'任务与子任务将移入回收站，讨论历史保留。项目共享资料不随任务单独删除。':'将移入回收站并停止新的检索与读取，原件和历史保留。已发布的相关公司知识会撤回，恢复后不自动公开。',async()=>{await api('/records/'+record.id,{method:'DELETE',body:{expected_revision:record.revision}});closeDialogs();if(label==='任务'&&taskId===record.id)await selectProject(p);else await refresh();toast(label+'已移入回收站');},{danger:true,label:'确认删除'});}
function renameDocument(d){formDialog('重命名资料',[field('title','显示名称','text',d.title,{attrs:{required:true,maxlength:200}}),el('p',{class:'help'},'仅修改显示名称，不改写上传原件。')],async v=>{await api('/documents/'+d.id,{method:'PATCH',body:{title:v.title,expected_revision:d.revision}});closeDialogs();await refresh();toast('资料名称已更新');},{submit:'保存名称'});}
function deleteCapability(a){const label=a.kind==='agent'?'AI 员工':'配置';confirmAction('删除'+label+' · '+a.name,a.kind==='agent'?'将停用并移除这位员工及其项目分配，历史回复与 Trace 保留。正在执行的任务会阻止删除。恢复后仍是停用状态，需重新分配。':'配置将移入回收站。仍被员工、项目或默认模型引用时会阻止删除；请先解除引用。恢复后保持停用，不自动运行。',async()=>{await api('/platform/assets/'+a.id,{method:'DELETE',body:{expected_revision:a.revision,detach_projects:true}});closeDialogs();await platformReload();toast(label+'已移入回收站');},{danger:true,label:'确认删除'});}
function deleteVendor(v){confirmAction('删除厂商 · '+v.name,'请先移除该厂商下的模型。只删除本站连接入口，保留历史，不注销供应方账号或改变套餐。',async()=>{await api('/model-providers/'+v.id,{method:'DELETE',body:{expected_revision:v.revision}});await renderProviderGroups();toast('厂商已移入回收站');},{danger:true,label:'确认删除'});}
async function openTrash(){const w=state.workspace.id,root=el('div',{},el('p',{class:'notice neutral'},'这里只显示你有权管理的已删除记录。恢复不会自动启用 AI 员工、工具或重新公开公司知识。当前不提供不可逆清空，防止误删历史与审计记录。')),list=el('div',{class:'trash-list'},'正在读取…');root.append(list);const dlg=openDialog('回收站',root,{wide:true});try{const r=await api('/workspaces/'+w+'/trash');if(!dlg.dialog.isConnected)return;list.replaceChildren();const names={project:'项目',task:'任务',event:'日程',document:'资料',proposal:'候选项',asset:'员工／配置',provider:'模型厂商'};for(const x of r.items)list.append(el('div',{class:'list-row','data-trash-id':x.target_id},el('div',{class:'grow'},el('strong',{},x.title),el('small',{},(names[x.kind]||x.kind)+' · 删除于 '+stamp(x.deleted_at))),button('恢复',async()=>{try{await api('/trash/'+x.target_id+'/restore',{method:'POST'});await reloadProjectIndex();dlg.close();if(state.screen==='company')await showCompany(state.companyView);else await refresh();toast('已恢复；配置需重新启用，公司知识需重新发布');await openTrash();}catch(e){handle(e);}},{class:'small'})));if(!r.items.length)list.append(empty('回收站为空','删除项目、任务或配置后，可在这里恢复。','files'));}catch(e){list.replaceChildren(el('p',{class:'form-error'},e.message));}}

// 0.9: shared folder browser, native previews, and complete skill package intake.
const files9={folders:new Map(),previewControl:null,urls:new Set()};
function fileTree(nav,files,onSelect){
 const tree={};for(const f of files){let node=tree;const parts=f.path.split('/');parts.forEach((p,i)=>{if(i===parts.length-1)node[p]={file:f};else node=node[p]||(node[p]={});});}
 function add(parent,node){for(const [name,value] of Object.entries(node).sort(([a],[b])=>a.localeCompare(b))){if(value.file)parent.append(el('button',{type:'button',class:'skill-file-button','data-path':value.file.path,onclick:()=>onSelect(value.file)},name));else{const d=el('details',{open:true},el('summary',{},'▸ '+name));add(d,value);parent.append(d);}}}add(nav,tree);
}
async function authBlob(path,options={}){const r=await fetch(API+path,{method:options.body?'POST':'GET',headers:{Authorization:'Bearer '+state.token,...(options.body?{'Content-Type':'application/json'}:{})},body:options.body?JSON.stringify(options.body):undefined,signal:options.signal,cache:'no-store'});if(!r.ok){let d;try{d=await r.json();}catch{d={detail:'读取失败 '+r.status};}throw Error(errorText(d));}return r.blob();}
function saveBlob(blob,name){const url=URL.createObjectURL(blob),a=el('a',{href:url,download:name});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function drawFilePreview(node,d,page,blobLoader,urls){
 node.replaceChildren();node.dataset.previewFormat=d.format;
 if(d.notice)node.append(el('p',{class:'notice neutral'},d.notice));
 if(d.format==='word'){
  const paper=el('article',{class:'word-preview'});for(const block of d.blocks){if(block.type==='table'){const t=el('table',{},el('tbody',{},block.rows.map(row=>el('tr',{},row.map(c=>el('td',{},c))))));paper.append(el('div',{class:'table-scroll'},t));if(block.truncated)paper.append(el('p',{class:'notice'},'此表格只预览前150行'));}else if(block.type==='image'){paper.append(el('img',{src:'data:'+block.mime+';base64,'+block.base64,alt:'文档内嵌图片'}));}else{const p=el(block.heading?'h'+block.heading:'p',{},block.list?'• ':'');if(block.runs?.map(x=>x.text).join('')===block.text){for(const run of block.runs)p.append(el('span',{style:(run.bold?'font-weight:700;':'')+(run.italic?'font-style:italic;':'')+(run.underline?'text-decoration:underline;':'')},run.text));}else p.append(document.createTextNode(block.text));paper.append(p);}}node.append(paper);if(d.truncated)node.append(el('p',{class:'notice'},'内容超过预览上限，完整内容请下载原件'));return;
 }
 if(d.format==='table'){
  const controls=el('div',{class:'preview-table-controls'},el('select',{class:'input','aria-label':'工作表',onchange:e=>page({sheet:Number(e.target.value),offset:0,col:0})},d.sheets.map((name,i)=>el('option',{value:i,selected:i===d.sheet},name))),el('span',{class:'help'},'行 '+(d.row_offset+1)+'–'+(d.row_offset+d.rows.length)+' · 列 '+(d.col_offset+1)+' 起'));
  const t=el('table',{class:'sheet-preview'},el('tbody',{},d.rows.map((row,i)=>el('tr',{},el('th',{},String(d.row_offset+i+1)),row.map(c=>el('td',{},c))))));
  node.append(controls,el('div',{class:'table-scroll'},t),el('div',{class:'row wrap'},d.row_offset>0&&button('上一页行',()=>page({sheet:d.sheet,offset:Math.max(0,d.row_offset-100),col:d.col_offset}),{class:'small'}),d.has_more_rows&&button('下一页行',()=>page({sheet:d.sheet,offset:d.row_offset+100,col:d.col_offset}),{class:'small'}),d.col_offset>0&&button('左侧列',()=>page({sheet:d.sheet,offset:d.row_offset,col:Math.max(0,d.col_offset-40)}),{class:'small'}),d.has_more_cols&&button('右侧列',()=>page({sheet:d.sheet,offset:d.row_offset,col:d.col_offset+40}),{class:'small'})),el('p',{class:'help'},d.formula_policy));return;
 }
 if(['pdf','image','audio','video'].includes(d.format)){
  let blob;if(d.binary_base64){const bytes=Uint8Array.from(atob(d.binary_base64),c=>c.charCodeAt(0));blob=new Blob([bytes],{type:d.mime});}else blob=await blobLoader();
  if(!node.isConnected)return;const url=URL.createObjectURL(blob);urls.add(url);
  if(d.format==='pdf')node.append(el('object',{data:url,type:'application/pdf',class:'pdf-preview','aria-label':'PDF文档预览'},el('p',{},'当前浏览器不能显示PDF，请下载原件。')));
  else if(d.format==='image')node.append(el('img',{src:url,alt:d.title||'文件预览',class:'image-preview'}));
  else node.append(el(d.format,{src:url,controls:true,preload:'metadata',class:'media-preview'}));return;
 }
 if(d.content!==undefined){node.append(d.format==='markdown'?markdown(d.content):el('pre',{class:'source-code'},d.content));if(d.has_more)node.append(button('读取下一段',()=>page({sheet:0,offset:d.next_offset,col:0}),{class:'small'}));}
 if(d.format==='unsupported'||d.format==='error')node.append(el('p',{class:'help'},'原件未改变；不支持的格式不会伪装成解析成功。'));
}
const v9ClosePreview=closeFilePreview;closeFilePreview=function(){files9.previewControl?.abort();files9.previewControl=null;for(const url of files9.urls)URL.revokeObjectURL(url);files9.urls.clear();v9ClosePreview();};
const v9Details=documentDialog,v9OldPreview=previewProjectFile;
async function previewDocument(id){
 closeFilePreview();const gen=state.generation,control=new AbortController();files9.previewControl=control;
 const title=el('h2',{},'文件预览'),meta=el('p',{class:'help'}),body=el('section',{class:'file-preview-body'},'正在读取原件…'),footer=el('footer',{class:'file-preview-footer'});
 const pane=el('aside',{id:'project-file-preview',class:'file-preview-drawer enhanced-preview',role:'dialog','aria-label':'项目文件预览',tabindex:'-1'},el('header',{},el('div',{class:'grow'},title,meta),iconButton('close','关闭文件预览',closeFilePreview)),body,footer);([...document.querySelectorAll('dialog[open]')].at(-1)||document.body).append(pane);pane.focus();let seq=0;
 const current=()=>pane.isConnected&&gen===state.generation&&!control.signal.aborted;
 async function load(opts={sheet:0,offset:0,col:0}){const n=++seq;body.replaceChildren(el('p',{class:'muted'},'正在本地预览…'));try{const d=await api('/documents/'+id+'/preview?'+new URLSearchParams(opts),{signal:control.signal});if(!current()||n!==seq)return;title.textContent=d.title;meta.textContent='v'+d.revision+' · '+(d.adopted?'已确认':'待核对')+' · '+(d.status==='ready'?'AI文本可读取':'原件预览 · 文本未索引');footer.replaceChildren(d.filename?button('下载原件',()=>download('/documents/'+id+'/download',d.filename),{class:'small',icon:'download'}):button('下载 Markdown',async()=>{const full=await api('/documents/'+id);saveBlob(new Blob([full.body||''],{type:'text/markdown;charset=utf-8'}),full.title+'.md');},{class:'small',icon:'download'}),button('管理资料',()=>{closeFilePreview();v9Details(id);},{class:'small ghost'}));if(d.status==='ready'&&state.task)footer.prepend(button('引用到本次讨论',()=>{if(!state.mentionDocs.some(x=>x.id===id)&&state.mentionDocs.length<6)state.mentionDocs.push({id,revision:d.revision,title:d.title,type:'document',usable:true});refreshAgentControls();closeFilePreview();closeDialogs();$('.composer textarea')?.focus();},{class:'small primary'}));await drawFilePreview(body,d,load,()=>authBlob(d.source_url,{signal:control.signal}),files9.urls);}catch(e){if(current()&&n===seq&&e.name!=='AbortError')body.replaceChildren(el('p',{class:'form-error'},e.message));}}
 await load();
}
previewProjectFile=function(file,p=state.project?.id){return (file.document_id||file.id)&&!(file.document_id||file.id).startsWith('k_')?previewDocument(file.document_id||file.id):v9OldPreview(file,p);};
documentDialog=function(id){return previewDocument(id);};

async function renderFileBrowser(root,p,initial=''){
 const gen=state.generation,selected=new Map();let folderId=files9.folders.get(p)||initial,q='',offset=0,seq=0,data=null,refreshTimer=null;
 const toolbar=el('div',{class:'file-browser-toolbar'}),tree=el('nav',{class:'folder-tree','aria-label':'项目文件夹'}),main=el('div',{class:'file-browser-main'}),crumb=el('nav',{class:'file-breadcrumb','aria-label':'文件位置'}),status=el('p',{class:'help'}),list=el('div',{class:'file-list','aria-label':'文件列表'}),rootPanel=el('div',{class:'file-browser-layout'},tree,main);root.replaceChildren(toolbar,rootPanel);main.append(crumb,status,list);
 const alive=()=>root.isConnected&&gen===state.generation&&state.project?.id===p;
 const mutate=fn=>Promise.resolve().then(fn).catch(handle);
 function navigate(id){folderId=id;files9.folders.set(p,id);q='';offset=0;selected.clear();load();}
 function folderForm(f=null){const choices=[['','项目根目录'],...(data?.folders||[]).filter(x=>x.id!==f?.id).map(x=>[x.id,x.path])];formDialog(f?'修改文件夹':'新建文件夹',[field('name','文件夹名称','text',f?.name||'',{attrs:{required:true,maxlength:64}}),field('parent_id','上级目录','select',f?f.parent_id:folderId,{choices})],async v=>{await api('/projects/'+p+'/folders'+(f?'/'+f.id:''),{method:f?'PATCH':'POST',body:{...v,...(f?{expected_revision:f.revision}:{})}});await load();},{submit:f?'保存文件夹':'创建文件夹'});}
 function moveFiles(items=[...selected.values()],target){if(!items.length){toast('请先选择文件');return;}const commit=async f=>{await api('/projects/'+p+'/files/move',{method:'POST',body:{folder_id:f,items:items.map(x=>({id:x.id,location_revision:x.location_revision}))}});selected.clear();await load();toast('文件已移动，原件与引用ID保持不变');};if(target!==undefined)return mutate(()=>commit(target));formDialog('移动 '+items.length+' 个文件',[field('folder_id','目标文件夹','select',folderId,{choices:[['','项目根目录'],...data.folders.map(x=>[x.id,x.path])]}),el('p',{class:'help'},'批量移动只修改位置，不重新上传或丢失版本。')],v=>commit(v.folder_id),{submit:'确认移动'});}
 function dropTarget(node,id){node.addEventListener('dragover',e=>{e.preventDefault();node.classList.add('drop-active');});node.addEventListener('dragleave',()=>node.classList.remove('drop-active'));node.addEventListener('drop',e=>{e.preventDefault();node.classList.remove('drop-active');if(!data?.can_write)return;if(e.dataTransfer.files.length)upload([...e.dataTransfer.files],id);else{try{const ids=JSON.parse(e.dataTransfer.getData('application/x-gongzhi-files'));moveFiles(data.items.filter(x=>ids.includes(x.id)),id);}catch{}}});}
 async function upload(files,target=folderId){if(!files.length)return;let duplicates=0;for(const file of files){if(file.size>20*1024*1024){toast(file.name+' 超过20MB',true);continue;}const f=new FormData();f.set('file',file);f.set('origin','library');f.set('folder_id',target);if(state.task)f.set('task_id',state.task.id);try{const d=await api('/projects/'+p+'/uploads',{method:'POST',body:f});if(d.duplicate)duplicates++;}catch(e){handle(e);}}if(alive()){await load();toast(duplicates?'上传完成；重复文件保留原位置，可手动移动':'文件已保存到当前目录，正在解析');}}
 function choose(){const input=el('input',{type:'file',multiple:true,class:'visually-hidden','aria-label':'上传到当前文件夹'});document.body.append(input);input.addEventListener('change',()=>{const files=[...input.files];input.remove();upload(files);},{once:true});input.addEventListener('cancel',()=>input.remove(),{once:true});input.click();}
 function draw(){
  const focusSearch=document.activeElement?.getAttribute('aria-label')==='搜索项目文件';const caret=focusSearch?document.activeElement.selectionStart:null;
  toolbar.replaceChildren(el('h3',{},'项目资料'),el('span',{class:'grow'}),data.can_write&&button('新建文件夹',()=>folderForm(),{icon:'plus'}),data.can_write&&button('上传文件',choose,{class:'primary',icon:'upload'}),data.can_write&&button('移动所选',()=>moveFiles(),{class:'ghost'}),button('刷新',()=>load(),{class:'ghost',icon:'refresh'}));
  const search=el('input',{type:'search',class:'input',value:q,placeholder:'搜索整个项目的文件名或路径','aria-label':'搜索项目文件'});toolbar.prepend(search);let timer;search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{q=search.value;offset=0;load();},300);});if(focusSearch){search.focus();try{search.setSelectionRange(caret,caret);}catch{}}
  tree.replaceChildren();const all=button('项目根目录',()=>navigate(''),{class:!folderId?'active folder-nav':'folder-nav'});tree.append(all);dropTarget(all,'');
  for(const f of data.folders.sort((a,b)=>a.path.localeCompare(b.path))){const b=el('button',{type:'button',class:'folder-nav'+(f.id===folderId?' active':''),'data-folder-id':f.id,title:f.path,style:'padding-left:'+(12+(f.path.split('/').length-1)*14)+'px',onclick:()=>navigate(f.id)},'▸ '+f.name);tree.append(b);dropTarget(b,f.id);}
  crumb.replaceChildren(button('项目资料',()=>navigate(''),{class:'small ghost'}),...data.breadcrumbs.flatMap(f=>[el('span',{},'/'),button(f.name,()=>navigate(f.id),{class:'small ghost'})]));
  const current=data.folders.find(x=>x.id===folderId);if(current&&data.can_write)crumb.append(button('修改文件夹',()=>folderForm(current),{class:'small ghost'}));if(current&&data.can_delete)crumb.append(button('删除空文件夹',()=>confirmAction('删除文件夹','仅删除空文件夹，不会递归删除任何资料。',async()=>{await api('/projects/'+p+'/folders/'+current.id,{method:'DELETE',body:{expected_revision:current.revision}});navigate(current.parent_id);},{danger:true}),{class:'small danger'}));
  list.replaceChildren();if(!q)for(const f of data.folders.filter(x=>x.parent_id===folderId)){const b=el('button',{type:'button',class:'file-row folder-row','data-folder-row':f.id,onclick:()=>navigate(f.id)},el('span',{class:'file-type-icon'},'▸'),el('strong',{class:'grow'},f.name),el('small',{},'文件夹'));dropTarget(b,f.id);list.append(b);}
  const selectAll=el('input',{type:'checkbox','aria-label':'选择当前页全部文件',onchange:e=>{for(const d of data.items)e.target.checked?selected.set(d.id,d):selected.delete(d.id);list.querySelectorAll('input[data-file-select]').forEach(c=>c.checked=selected.has(c.dataset.fileSelect));}});
  if(data.items.length)list.append(el('div',{class:'file-row file-heading'},data.can_write&&selectAll,el('span',{class:'grow'},'名称'),el('small',{},'状态 / 版本')));
  for(const d of data.items){const box=el('input',{type:'checkbox','data-file-select':d.id,'aria-label':'选择 '+d.title,checked:selected.has(d.id),onchange:e=>e.target.checked?selected.set(d.id,d):selected.delete(d.id)});const row=el('div',{class:'file-row','data-file-id':d.id,draggable:data.can_write},data.can_write&&box,el('button',{type:'button',class:'file-open grow',onclick:()=>previewDocument(d.id)},el('strong',{},d.title),el('small',{},q?d.display_path:(d.filename||d.kind))),badge(({ready:'可读取',uploaded:'待解析',parsing:'解析中',unindexed:'未索引',failed:'解析失败'})[d.status]||d.status,d.status==='ready'?'success':''),el('small',{},'v'+d.revision),data.can_write&&button('移动',()=>moveFiles([d]),{class:'small ghost'}));row.addEventListener('dragstart',e=>{e.dataTransfer.setData('application/x-gongzhi-files',JSON.stringify(selected.has(d.id)?[...selected.keys()]:[d.id]));});list.append(row);}
  if(!list.children.length)list.append(empty('此文件夹还没有文件','上传文件，或从其他位置批量移动到这里。','files'));
  status.textContent=(q?'全项目搜索 · ':'')+data.total+' 个文件 · 文件位置与 AI 目录同步';const pager=el('div',{class:'row wrap'},offset>0&&button('上一页',()=>{offset=Math.max(0,offset-100);load();},{class:'small'}),data.has_more&&button('下一页',()=>{offset+=100;load();},{class:'small'}));list.append(pager);dropTarget(list,folderId);
 }
 async function load(){const n=++seq;clearTimeout(refreshTimer);status.textContent='读取文件目录…';try{const r=await api('/projects/'+p+'/file-browser?'+new URLSearchParams({folder_id:folderId,q,offset,limit:100}),{signal:state.controller.signal});if(!alive()||n!==seq)return;data=r;draw();if(r.items.some(x=>['uploaded','parsing'].includes(x.status)))refreshTimer=setTimeout(()=>{if(alive())load();},2000);}catch(e){if(alive()&&n===seq&&e.name!=='AbortError'){status.textContent=e.message;if(e.status===404&&folderId){folderId='';files9.folders.delete(p);load();}}}}
 await load();
}
renderDocuments=function(content){content.append(el('p',{class:'help'},'目录、资料和知识共用一套项目权限。移动文件不改变 ID，原件保留；可直接拖入文件。'));const root=el('section',{class:'project-file-browser'});content.append(root);renderFileBrowser(root,state.project.id).catch(handle);};
openProjectSpace=async function(){if(!state.project)return;const root=el('section',{class:'project-file-browser'}),dlg=openDialog('项目文件 · '+state.project.title,root,{wide:true});dlg.dialog.classList.add('file-manager-modal');await renderFileBrowser(root,state.project.id);};

async function skillPackageViewer(title,loadInfo,readEntry,actions){
 const root=el('div'),toolbar=el('div',{class:'row wrap'}),layout=el('div',{class:'skill-browser'}),tree=el('nav',{class:'skill-file-tree','aria-label':'技能文件列表'}),body=el('section',{class:'skill-file-content'},'正在读取技能包…'),urls=new Set();root.append(toolbar,layout);layout.append(tree,body);const dlg=openDialog(title,root,{wide:true,description:'完整文件树 · 直接导入本站 · 脚本只展示、不执行'});dlg.dialog.classList.add('file-manager-modal');let seq=0;dlg.dialog.addEventListener('close',()=>{for(const u of urls)URL.revokeObjectURL(u);});
 try{const d=await loadInfo();if(!dlg.dialog.isConnected)return;toolbar.append(el('p',{class:'help grow'},(typeof d.source==='string'?d.source:'本站技能')+(d.owner?' · @'+d.owner:'')+' · '+d.files.length+' 个文件 · '+(d.version?'v'+d.version:'v'+d.revision)));if(actions)actions(toolbar,d,dlg);
  async function show(f,opts={sheet:0,offset:0,col:0}){const n=++seq;tree.querySelectorAll('.skill-file-button').forEach(b=>b.classList.toggle('active',b.dataset.path===f.path));body.replaceChildren(el('h3',{},f.path),el('p',{class:'muted'},'正在读取…'));try{const r=await readEntry(d,f,opts);if(n!==seq||!dlg.dialog.isConnected)return;body.replaceChildren(el('h3',{},f.path));const rendered=el('div',{class:'skill-preview-render'});body.append(rendered);await drawFilePreview(rendered,r,o=>show(f,o),()=>Promise.reject(Error('该原件未返回预览数据')),urls);}catch(e){if(n===seq)body.replaceChildren(el('h3',{},f.path),el('p',{class:'form-error'},e.message));}}
  fileTree(tree,d.files,f=>show(f));const first=d.files.find(x=>x.path==='SKILL.md')||d.files[0];if(first)await show(first);
 }catch(e){body.replaceChildren(el('p',{class:'form-error'},e.message));}return dlg;
}
viewLocalSkill=function(a){return skillPackageViewer('技能内容 · '+a.name,()=>api('/skills/'+a.id+'/files'),(d,f,opts)=>api('/skills/'+a.id+'/preview?'+new URLSearchParams({path:f.path,revision:d.revision,...opts})),bar=>bar.append(button('下载完整ZIP',()=>download('/capabilities/'+a.id+'/export',a.name+'.zip'),{class:'small',icon:'download'})));};
previewMarketSkill=function(item){const w=state.workspace.id;return skillPackageViewer('预览并导入 · '+(item.name||item.slug),()=>api('/workspaces/'+w+'/skill-market/preview',{method:'POST',body:{source:item.source,slug:item.slug,owner:item.owner||'',version:item.version||''}}),(d,f,opts)=>api('/workspaces/'+w+'/skill-market/file',{method:'POST',body:{source:d.source,slug:d.slug,owner:d.owner,version:d.version,expected_sha256:d.sha256,path:f.path,...opts}}),(bar,d,dlg)=>{
 const args={source:d.source,slug:d.slug,owner:d.owner,version:d.version,expected_sha256:d.sha256};bar.append(button('下载技能ZIP',async()=>{try{saveBlob(await authBlob('/workspaces/'+w+'/skill-market/download',{body:args}),d.slug+'.zip');}catch(e){handle(e);}},{class:'small',icon:'download'}));
 if(companyOwner())bar.append(button('直接导入本站',async e=>{const b=e.currentTarget;b.disabled=true;try{const a=await api('/workspaces/'+w+'/skill-market/import',{method:'POST',body:{...args,acknowledge_review:true}});dlg.close();await platformReload(w);await viewLocalSkill(a);toast(a.duplicate?'此版本已在本站，已打开':'完整技能包已直接保存为停用草稿，请审核后启用');}catch(err){handle(err);b.disabled=false;}},{class:'primary',icon:'plus'}));bar.append(el('p',{class:'notice neutral'},'导入会保留完整文件和来源，初始停用，不执行脚本、不自动绑定员工。'));
 });};
function importSkillLink(){formDialog('从技能链接导入',[field('url','SkillHub / ClawHub 详情链接','url','',{attrs:{required:true},help:'例如 skillhub.cn/skills/名称 或 clawhub.ai/作者/skills/名称；不支持任意下载站。'})],async v=>{const item=await api('/workspaces/'+state.workspace.id+'/skill-market/resolve',{method:'POST',body:{url:v.url}});await previewMarketSkill(item);},{submit:'读取技能包'});}
const v9Market=openSkillMarket;openSkillMarket=async function(){const pending=v9Market();const dialog=[...document.querySelectorAll('dialog[open]')].at(-1);dialog?.querySelector('.modal-body')?.prepend(button('粘贴技能链接',importSkillLink,{class:'ghost',icon:'link'}));await pending;};
const v9Resources=renderResources;renderResources=function(){v9Resources();if(ui5.resourceTab==='skill'&&companyOwner())$('.hub-toolbar .row')?.append(button('从链接导入',importSkillLink,{class:'ghost',icon:'link'}));};

// 0.11: collapsible in-chat execution, explicit per-run grants and budgets.
const execution11={records:new Map(),loading:new Set(),permission:'safe',ack:false,budget:'standard',paintTimer:null};
function runOptions11(){return {permission_mode:execution11.permission,budget:execution11.budget,acknowledge_full_access:execution11.permission==='full'&&execution11.ack};}
function rememberStartedRun(run){state.runs=[run,...state.runs.filter(x=>x.id!==run.id)];state.running=run;execution11.permission='safe';execution11.ack=false;updateRunOptions11();}
const previousRunSelection11=runSelection;
runSelection=function(){return {...previousRunSelection11(),run_options:runOptions11()};};
function updateRunOptions11(){const a=selectedAgent();if(execution11.permission==='full'&&execution11.fullAgentKey!==JSON.stringify([a?.id,a?.revision,a?.binding_revision])){execution11.permission='safe';execution11.ack=false;}const b=$('#run-options-button');if(!b)return;b.hidden=!a;b.textContent=(execution11.permission==='full'?'完全权限':'安全模式')+' · '+(execution11.budget==='extended'?'48步':execution11.budget==='configured'?(a?.data?.max_model_steps||'?')+'步':'24步');b.classList.toggle('permission-full',execution11.permission==='full');}
function openRunOptions11(){
 const a=selectedAgent(),plugins=a?.data?.plugin_ids||[],mcps=(a?.data?.mcp_ids||[]).map(id=>state.capabilities.find(x=>x.id===id)?.name||id);
 const mode=el('select',{class:'input',name:'permission','aria-label':'本次权限模式'},el('option',{value:'safe'},'安全模式 · 写入与外部调用逐次确认'),el('option',{value:'full',disabled:!isOwner()},'完全权限 · 本次已授权工具免逐次确认'));mode.value=execution11.permission;
 const budget=el('select',{class:'input',name:'budget','aria-label':'本次执行预算'},el('option',{value:'standard'},'标准任务 · 24步 / 64次工具 / 15分钟 / 单步输出8192'),el('option',{value:'extended'},'长任务 · 48步 / 128次工具 / 30分钟 / 单步输出8192'),el('option',{value:'configured'},'沿用员工配置 · '+(a?.data?.max_model_steps||'?')+'步'));budget.value=execution11.budget;
 const ack=el('input',{type:'checkbox','aria-label':'确认本次完全权限',checked:execution11.ack}),warning=el('div',{class:'full-access-warning'},el('p',{},'仅限当前任务、所选员工已授权的平台插件和 MCP。可能修改项目内容、发送参数给外部服务；不提供其他项目、密钥、任意电脑命令或额外工具的权限。'),el('p',{class:'help'},plugins.length+' 个平台插件；MCP：'+(mcps.join('、')||'无')),el('label',{class:'field-check'},ack,'我确认本次免逐次确认；执行中可切回安全模式。'));
 const root=el('div',{class:'stack'},el('label',{class:'field'},el('span',{},'权限模式'),mode),warning,!isOwner()&&el('p',{class:'help'},'只有项目管理员可授权完全权限。'),el('label',{class:'field'},el('span',{},'执行预算'),budget),el('p',{class:'help'},'最后一步预留收尾。步数增加可能增加模型用量；不会自动续跑或重试，任务成果仍需人工验收。'));
 const save=button('应用到本次',()=>{if(mode.value==='full'&&!ack.checked){toast('请先确认本次完全权限的范围',true);return;}execution11.permission=mode.value;execution11.ack=mode.value==='full'&&ack.checked;execution11.fullAgentKey=JSON.stringify([a?.id,a?.revision,a?.binding_revision]);execution11.budget=budget.value;dlg.close();updateRunOptions11();},{class:'primary'});
 const dlg=openDialog('本次执行设置',root,{actions:[button('取消',()=>dlg.close()),save]});const change=()=>{warning.hidden=mode.value!=='full';save.disabled=mode.value==='full'&&!ack.checked;};mode.addEventListener('change',change);ack.addEventListener('change',change);change();
}
const previousAgentControls11=refreshAgentControls;
refreshAgentControls=function(){previousAgentControls11();updateRunOptions11();};
const previousDiscussion11=renderDiscussion;
renderDiscussion=function(content){previousDiscussion11(content);const composer=$('.composer');if(composer&&!$('#run-options-button')){const b=button('安全模式 · 24步',openRunOptions11,{class:'small ghost run-options'});b.id='run-options-button';b.setAttribute('aria-label','本次执行设置');$('.composer-bottom',composer)?.prepend(b);}updateRunOptions11();syncInlineRuns11();};
const previousReset11=resetView;
resetView=function(){clearTimeout(execution11.paintTimer);execution11.paintTimer=null;execution11.records.clear();execution11.loading.clear();execution11.permission='safe';execution11.ack=false;previousReset11();};
function runRecord11(run){let r=execution11.records.get(run.id);if(!r){r={id:run.id,task:run.request?.task_id||run.task_id||state.task?.id,events:[],cursor:0,text:'',approvals:new Map(),step:0,loaded:false,meta:run};execution11.records.set(run.id,r);}else r.meta={...r.meta,...run};return r;}
function foldedKey11(rid){return 'gongzhi.folded:'+state.user?.id+':'+rid;}
function activityCard11(record){
 const card=el('article',{class:'inline-run-card','data-inline-run':record.id}),heading=el('div',{class:'inline-run-heading'}),details=el('details',{class:'inline-run-details'}),summary=el('summary',{class:'inline-run-summary'}),steps=el('div',{class:'inline-run-steps'}),error=el('div',{class:'inline-run-error'}),approval=el('div',{class:'inline-run-approvals'}),text=el('div',{class:'inline-run-output'}),actions=el('div',{class:'inline-run-actions row wrap'});
 details.append(summary,steps);card.append(heading,details,error,approval,text,actions);
 const saved=sessionStorage.getItem(foldedKey11(record.id));details.open=saved!==null?saved==='open':!terminalRun(record.meta.status);
 summary.addEventListener('click',()=>{details.dataset.manual='1';});details.addEventListener('toggle',()=>{if(details.dataset.manual){sessionStorage.setItem(foldedKey11(record.id),details.open?'open':'closed');}if(details.open){loadActivity11(record);paintInlineRun11(record);}});
 card.parts={heading,details,summary,steps,error,approval,text,actions};return card;
}
function positionCard11(card,record,list){
 const reply=state.messages.find(m=>m.run_id===record.id);if(reply){const node=$('#message-'+reply.id,list);if(node&&card.nextSibling!==node)list.insertBefore(card,node);return;}
 // Anchor after the triggering input and before later messages, including human replies.
 const after=state.messages.find(m=>Number(m.seq)>Number(record.meta.input_seq??Infinity));const node=after&&$('#message-'+after.id,list);
 if(node){if(card.nextSibling!==node)list.insertBefore(card,node);}else if(card.parentNode!==list)list.append(card);
}
function syncInlineRuns11(){
 const list=$('#messages');if(!list||!state.task)return;
 const rows=state.runs.filter(r=>r.request?.task_id===state.task.id||r.task_id===state.task.id).slice(0,40).reverse();
 if(state.agentLive&&!rows.some(r=>r.id===state.agentLive.id))rows.push({id:state.agentLive.id,task_id:state.task.id,agent_name:state.agentLive.name,actor_id:state.agentLive.actor,status:'running'});
 const near=list.scrollHeight-list.scrollTop-list.clientHeight<120;
 for(const row of rows){const record=runRecord11(row);let card=list.querySelector('[data-inline-run="'+row.id+'"]');if(!card){card=activityCard11(record);$('.empty',list)?.remove();list.append(card);}positionCard11(card,record,list);paintInlineRun11(record);}
 if(near)list.scrollTop=list.scrollHeight;
}
function paintInlineRun11(record){
 if(record.task!==state.task?.id)return;const card=$('[data-inline-run="'+record.id+'"]');if(!card)return;
 const {heading,details,summary,steps,error,approval,text,actions}=card.parts,m=record.meta,info=summarizeActivity(record.events),status=m.status||'running',finished=terminalRun(status),mode=info.mode||m.permission_mode||m.execution_policy?.permission_mode||'safe',limit=m.limits?.max_model_steps||m.execution_policy?.effective_limits?.max_model_steps||'?';
 record.step=info.step||record.step||0;
 const progress=record.approvals.size?'等待确认':finished?(status==='paused'?'预算已用完 · 可续接':labels[status]||status):info.finalizing?'预算收尾':(record.statusText||'正在执行');
 heading.replaceChildren(avatar(m.agent_name||record.name||'AI',true),el('strong',{},m.agent_name||record.name||'AI 员工'),badge(mode==='full'?'完全权限':'安全模式',mode==='full'?'warning':''),el('span',{class:'grow'}),el('small',{},stamp(m.created_at)));
 summary.replaceChildren(...[!finished&&el('span',{class:'spinner','aria-hidden':'true'}),el('strong',{},'执行过程'),el('span',{class:'inline-run-status'},progress),el('small',{},record.loaded?'步骤 '+record.step+'/'+limit+' · '+info.completed+' 次工具返回':'点击查看记录 · 上限 '+limit+' 步'),icon('chevron',14)].filter(Boolean));
 if(finished&&!details.dataset.manual&&sessionStorage.getItem(foldedKey11(record.id))===null)details.open=false;
 if(details.open){
  const key=record.cursor+':'+record.loaded+':'+status;
  if(steps.dataset.key!==key){steps.dataset.key=key;steps.replaceChildren();if(!record.loaded&&!record.events.length)steps.append(el('p',{class:'help'},'正在读取执行记录…'));
   if(info.conversation){const c=info.conversation;steps.append(el('p',{class:'notice neutral context-loaded'},'已读入本任务 '+c.included_messages+' 条历史（真人 '+c.human_messages+' / AI '+c.assistant_messages+'）'+(c.instruction_mode==='prior_human'?' · 接续消息#'+c.instruction_source?.seq:'')+(c.omitted_messages?'；另有 '+c.omitted_messages+' 条可按需回看':'')));}
   for(const t of info.tools.slice(-120)){
    const row=el('details',{class:'inline-tool '+t.status},el('summary',{},el('span',{class:'tool-state','aria-label':t.status},{running:'进行中',waiting:'待确认',done:'已完成',denied:'未批准',error:'失败'}[t.status]),el('strong',{},t.label),el('span',{class:'tool-detail'},compactToolDetail(t)),t.automatic&&badge('已授权'),t.elapsedMs!=null&&el('small',{},(t.elapsedMs/1000).toFixed(2)+'s')),el('pre',{class:'source-code'},JSON.stringify({tool:t.name,arguments:t.args,result:t.receipt,preview:t.preview},null,2)));steps.append(row);
   }
   if(info.tools.length>120)steps.prepend(el('p',{class:'help'},'显示最近120项，完整记录可在 Trace 查看。'));
   if(record.loaded&&!info.tools.length)steps.append(el('p',{class:'help'},'尚无工具调用；模型步骤和文本会实时更新。'));
  }
 }
 error.replaceChildren();if(m.error)error.append(el('p',{class:'form-error'},m.error));if(status==='paused')error.append(el('p',{class:'notice neutral'},'已保留阶段性结果与已执行操作。需要继续时发起新运行，不会自动重做。'));
 const approvalKey=[...record.approvals.keys()].join(',')+':'+m.actor_id;
 if(approval.dataset.key!==approvalKey){approval.dataset.key=approvalKey;approval.replaceChildren();for(const a of record.approvals.values()){
  const can=isOwner()||Number(m.actor_id||record.actor)===Number(state.user?.id);
  approval.append(el('section',{class:'tool-approval'},el('strong',{},'待确认：'+toolLabel(a.name||a.tool_name)),el('details',{},el('summary',{},'查看本次操作参数'),el('pre',{class:'source-code'},JSON.stringify(a.arguments||{},null,2))),el('p',{class:'help'},'确认只针对本次操作，拒绝后不会执行。'),can&&button('允许本次',()=>approveTool(record.id,a.id,true),{class:'small primary'}),can&&button('拒绝',()=>approveTool(record.id,a.id,false),{class:'small'}),!can&&el('span',{class:'help'},'等待发起人或项目管理员确认')));
 }}
 const showText=!finished&&record.text;if(text.textContent!==(showText||''))text.textContent=showText||'';text.hidden=!showText;
 const actionKey=status+':'+mode+':'+!!canWrite();if(actions.dataset.key!==actionKey){actions.dataset.key=actionKey;actions.replaceChildren(button('完整 Trace',()=>openTrace(record.id),{class:'small ghost'}));
  if(!finished&&canWrite()&&(isOwner()||Number(m.actor_id||record.actor)===Number(state.user?.id))){actions.append(button('停止',async()=>{try{await api(projectPath('/runs/'+record.id+'/cancel'),{method:'POST'});}catch(e){handle(e);}},{class:'small danger'}));if(mode==='full')actions.append(button('切回安全模式',async()=>{try{await api(projectPath('/runs/'+record.id+'/permission-mode'),{method:'POST',body:{permission_mode:'safe'}});record.meta.permission_mode='safe';toast('后续操作恢复逐次确认；已经执行的操作不回滚');paintInlineRun11(record);}catch(e){handle(e);}},{class:'small'}));}
  if(finished&&canWrite()&&['failed','interrupted','paused'].includes(status))actions.append(button('继续处理',()=>continueRun11(record),{class:'small primary'}));
 }
 if(m.usage?.total_tokens!=null){let usage=card.querySelector('.inline-run-usage');if(!usage){usage=el('small',{class:'inline-run-usage'});card.append(usage);}usage.textContent='已知用量 '+Number(m.usage.total_tokens).toLocaleString()+' token';}
}
async function loadActivity11(record){
 if(record.loaded||execution11.loading.has(record.id)||!state.project)return;const gen=state.generation,p=state.project.id;execution11.loading.add(record.id);
 try{let more=true,guard=0;while(more&&guard++<30){const d=await api('/projects/'+p+'/runs/'+record.id+'/activity?after='+record.cursor,{signal:state.controller.signal});if(gen!==state.generation||record.task!==state.task?.id)return;record.events=mergeActivity(record.events,d.items);record.cursor=Math.max(record.cursor,d.cursor||0);record.meta={...record.meta,...d.run};record.approvals=new Map(d.approvals.map(a=>[a.id,{...a,name:a.tool_name}]));more=d.has_more;}record.loaded=true;paintInlineRun11(record);}catch(e){if(e.name!=='AbortError'&&gen===state.generation){const card=$('[data-inline-run="'+record.id+'"]');card?.parts.steps.replaceChildren(el('p',{class:'form-error'},e.message),button('重试读取',()=>loadActivity11(record),{class:'small'}));}}finally{execution11.loading.delete(record.id);}
}
renderAgentLive=function(){
 if(execution11.paintTimer)return;execution11.paintTimer=setTimeout(()=>{execution11.paintTimer=null;syncInlineRuns11();if(state.agentLive){const r=execution11.records.get(state.agentLive.id);if(r)paintInlineRun11(r);}},70);
}
renderRunning=function(){const slot=$('#run-slot');if(slot)slot.replaceChildren();refreshAgentControls();refreshTraceList();syncInlineRuns11();if(state.running&&state.task&&state.agentLive?.id!==state.running.id)followAgentRun(state.running.id);};
approveTool=async function(rid,id,approve){try{await api(projectPath('/runs/'+rid+'/approvals/'+id),{method:'POST',body:{approve}});const r=execution11.records.get(rid);r?.approvals.delete(id);if(r)paintInlineRun11(r);}catch(e){handle(e);}};
followAgentRun=async function(id){
 if(!state.task||state.agentLive?.id===id)return;state.agentSSE?.abort();const control=new AbortController();state.agentSSE=control;const gen=state.generation,p=state.project.id,task=state.task.id;
 const record=runRecord11(state.runs.find(r=>r.id===id)||{id,task_id:task,status:'running',agent_name:selectedAgent()?.name});record.loaded=true;const live={id,task,actor:record.meta.actor_id,name:record.meta.agent_name,record};state.agentLive=live;
 const current=()=>!control.signal.aborted&&gen===state.generation&&state.project?.id===p&&state.task?.id===task&&state.agentLive===live;
 for(let attempt=0;attempt<4&&current();attempt++){let reader=null;try{
  const response=await fetch(API+'/projects/'+p+'/runs/'+id+'/events?view=activity&after='+record.cursor,{headers:{Authorization:'Bearer '+state.token,Accept:'text/event-stream'},signal:control.signal});if(!current())return;
  if([401,403,404].includes(response.status)){control.abort();execution11.records.delete(id);state.agentLive=null;await loadProjects();return;}if(!response.ok)throw Error('流式连接 HTTP '+response.status);
  reader=response.body.getReader();const decoder=new TextDecoder(),frames=new SSEFrames();let terminal=false;
  while(current()){const {value,done}=await reader.read();if(!current())return;if(done)break;for(const frame of frames.push(decoder.decode(value,{stream:true}))){const x=JSON.parse(frame.data);
   if(frame.event==='access_revoked'){control.abort();execution11.records.delete(id);state.agentLive=null;await loadProjects();return;}
   if(frame.event==='run_info'){record.meta={...record.meta,...x};continue;}
   if(frame.event==='cursor'){record.cursor=Math.max(record.cursor,x.cursor||0);continue;}
   if(frame.event==='terminal'){record.meta.status=x.status;record.approvals.clear();terminal=true;continue;}
   if(frame.event!=='trace'||!Number.isInteger(x.seq)||x.seq<=record.cursor)continue;record.cursor=x.seq;record.events=mergeActivity(record.events,[x]);const d=x.payload||{};
   if(x.event==='run.start'){record.actor=d.actor_id;record.meta.actor_id=d.actor_id;record.meta.agent_name=d.agent_name||record.meta.agent_name;}
   if(x.event==='model.start'){record.step=d.step;record.text='';record.statusText='模型处理';}
   if(x.event==='output.delta'){record.text+=d.text||'';record.statusText='正在输出';}
   if(x.event==='tool.request')record.statusText=toolLabel(d.name);
   if(x.event==='approval.required')record.approvals.set(d.id,{...d,call_id:x.parent_span});
   if(x.event==='approval.decision')record.approvals.delete(d.approval_id);
   if(['tool.result','tool.denied','tool.error'].includes(x.event))for(const [aid,a] of record.approvals)if(a.call_id===x.span_id)record.approvals.delete(aid);
   if(x.event==='run.end'){record.meta={...record.meta,status:d.status,error:d.error,usage:d.usage};record.approvals.clear();}
  }renderAgentLive();if(terminal)break;}
  if(terminal&&current()){await fetchMessages(gen);if(!current())return;const rr=await api('/projects/'+p+'/runs',{signal:control.signal});if(!current())return;state.runs=rr.items;const r=state.runs.find(x=>x.id===id);if(r)record.meta={...record.meta,...r};state.agentLive=null;state.agentSSE=null;syncInlineRuns11();refreshTraceList();return;}
 }catch(e){if(!current())return;record.statusText='连接暂断，正在续读已有记录';renderAgentLive();}finally{if(reader){try{await reader.cancel();}catch{}reader.releaseLock();}}if(current())await new Promise(r=>setTimeout(r,500*(attempt+1)));}
 if(current()){record.statusText='连接已暂停，服务端运行未重发';renderAgentLive();}
};
function continueRun11(record){
 const a=state.capabilities.find(a=>a.id===record.meta.agent_id&&a.enabled&&a.kind==='agent');if(!a){toast('原员工未启用，请重新选择员工后说明要续接的任务',true);return;}
 const gen=state.generation,p=state.project.id,t=state.task.id;
 confirmAction('接续这次任务','将开启新的安全模式运行（24步），先核对已有文件与操作回执，不自动重做或回滚。会产生新的模型用量。',async()=>{
  const prior=record.meta.request?.prompt||'';const r=await api('/tasks/'+t+'/runs',{method:'POST',body:{kind:'chat',prompt:'请接续上次任务，先核对已经完成的操作，避免重复写入。上次请求：'+prior.slice(0,10000),agent_id:a.id,agent_revision:a.revision,binding_revision:a.binding_revision,continue_from:record.id,client_id:crypto.randomUUID(),run_options:{permission_mode:'safe',budget:'standard'}}});if(gen!==state.generation||state.project?.id!==p||state.task?.id!==t)return;rememberStartedRun(r);followAgentRun(r.id);syncInlineRuns11();
 },{label:'确认续接'});
}

// Local profile presentation; all reads/writes use the authenticated application API.
const profiles12=new Map();let profileLoading12=false;
async function loadProfiles12(){
 if(!state.workspace||profileLoading12)return;const w=state.workspace.id;
 if(profileScope12!==w){profiles12.clear();profileRequested12.clear();profileScope12=w;}
 const subjects=new Set();for(const n of document.querySelectorAll('[data-avatar-kind][data-avatar-id]')){const key=n.dataset.avatarKind+':'+n.dataset.avatarId;if(!profileRequested12.has(key)&&!profiles12.has(key))subjects.add(key);}
 if(!subjects.size)return;for(const key of [...subjects].slice(0,60))profileRequested12.add(key);
 profileLoading12=true;try{const d=await api('/workspaces/'+w+'/avatars?subjects='+encodeURIComponent([...subjects].slice(0,60).join(',')));if(state.workspace?.id!==w)return;for(const p of d.items)profiles12.set(p.kind+':'+p.id,p);refreshProfileNodes12();}catch(e){console.warn('Avatar profile not available; refresh to retry.');}finally{profileLoading12=false;if([...document.querySelectorAll('[data-avatar-kind][data-avatar-id]')].some(n=>!profileRequested12.has(n.dataset.avatarKind+':'+n.dataset.avatarId))&&!profileTimer12)profileTimer12=setTimeout(()=>{profileTimer12=null;loadProfiles12();},100);}
}
function refreshProfileNodes12(){for(const n of document.querySelectorAll('[data-avatar-kind][data-avatar-id]'))updateAvatar(n,profiles12.get(n.dataset.avatarKind+':'+n.dataset.avatarId));}
let profileTimer12=null;const profileRequested12=new Set();let profileScope12=null;
function personAvatar12(kind,id,name){const key=kind+':'+id,n=avatarNode(kind,id,name,profiles12.get(key));if(!profiles12.has(key)&&!profileRequested12.has(key)&&!profileTimer12)profileTimer12=setTimeout(()=>{profileTimer12=null;loadProfiles12();},60);return n;}

const priorMessage12=messageElement;
messageElement=function(message){const n=priorMessage12(message),side=messageSide(message,state.user?.id);n.classList.add('message-'+side);n.dataset.authorType=side;const kind=side==='agent'?'agent':'human',id=kind==='agent'?(message.agent_id||'legacy-'+message.author_name):message.author_id;n.querySelector(':scope > .avatar')?.replaceWith(personAvatar12(kind,id,message.author_name));if(side==='self')n.querySelector('.message-meta')?.append(badge('你'));return n;};
async function profileDialog12(kind,id,name){
 const w=state.workspace.id,d=await api('/workspaces/'+w+'/avatars?subjects='+encodeURIComponent(kind+':'+id)),current=d.items[0];if(!current)return toast('头像对象不可见',true);
 let preset=current.preset,image=null;const preview=personAvatar12(kind,id,name),grid=el('div',{class:'avatar-presets'}),error=el('p',{class:'help'}),upload=el('input',{type:'file',accept:'image/png,image/jpeg,image/webp','aria-label':'上传头像'});preview.classList.add('large');
 const draw=()=>grid.replaceChildren(...PRESET_AVATARS[kind].map((emoji,index)=>button(emoji,()=>{preset=index;image=null;preview.textContent=emoji;draw();},{class:'avatar-preset'+(preset===index&&!image?' selected':''),title:'头像 '+(index+1)})));draw();
 upload.addEventListener('change',()=>{const file=upload.files[0];if(!file)return;if(file.size>2097152){error.textContent='图片不能超过2MB';return;}const reader=new FileReader();reader.onload=()=>{image=String(reader.result).split(',')[1];error.textContent='已选择 '+file.name+'，保存时会校验并清除图片元数据。';};reader.readAsDataURL(file);});
 const save=button('保存头像',async()=>{save.disabled=true;try{const body={expected_revision:current.revision};if(image)body.image_base64=image;else body.preset=preset;const p=await api('/workspaces/'+w+'/avatars/'+kind+'/'+id,{method:'PUT',body});profiles12.set(kind+':'+id,p);refreshProfileNodes12();dlg.close();toast('头像已保存');}catch(e){error.textContent=e.message;}finally{save.disabled=false;}},{class:'primary'});
 const dlg=openDialog('设置头像 · '+name,el('div',{class:'stack'},preview,el('p',{},kind==='agent'?'选择员工头像':'选择你的头像'),grid,el('label',{class:'field'},'或上传 PNG / JPEG / WebP（最大2MB）',upload),error),{actions:[button('取消',()=>dlg.close()),save]});
}
const priorDiscussion12=renderDiscussion;renderDiscussion=function(content){priorDiscussion12(content);queueMicrotask(loadProfiles12);};
const priorShell12=renderShell;renderShell=function(){priorShell12();if(state.user&&!$('#self-avatar-button')){const b=button('我的头像',()=>profileDialog12('human',state.user.id,state.user.display_name||state.user.username),{class:'small ghost'});b.id='self-avatar-button';$('.sidebar')?.append(b);}};
const priorStaff12=renderEmployees;renderEmployees=function(){priorStaff12();for(const card of document.querySelectorAll('.employee-card[data-employee-id]')){const a=platformState.catalog.items.find(x=>x.id===card.dataset.employeeId);if(!a)continue;const old=card.querySelector('.employee-avatar'),av=personAvatar12('agent',a.id,a.name);av.classList.add('employee-avatar');old?.replaceWith(av);const actions=card.querySelector('.employee-actions');if(platformState.catalog.can_manage)actions?.append(button('头像',()=>profileDialog12('agent',a.id,a.name),{class:'small ghost'}));const assign=[...card.querySelectorAll('button')].find(b=>b.textContent==='分配项目');if(assign){assign.textContent='使用说明';assign.onclick=null;assign.replaceWith(el('span',{class:'badge'},a.visibility==='workspace'?'团队共享 · 直接 @':'项目专属'));}}queueMicrotask(loadProfiles12);};
const priorTaskContext12=taskContextPanel;taskContextPanel=function(){const panel=priorTaskContext12();const assignment=[...panel.querySelectorAll('.agent-config-section button')].find(b=>b.textContent==='分配员工');assignment?.replaceWith(button('选择员工',chooseTaskEmployee,{class:'small ghost'}));const note=panel.querySelector('.agent-config-section .help');if(note)note.textContent='团队共享员工可以直接 @；只读取本次任务所在项目，不创建独立项目空间。';return panel;};
chooseTaskEmployee=function(){const root=el('div',{class:'employee-grid compact'}),dlg=openDialog('选择 AI 员工',root,{wide:true,description:'共享员工来自团队配置，无需重复分配到项目。'});root.append(button('不选择 AI，仅与成员聊天',()=>{pickAgent(null);dlg.close();},{class:'employee-card plain'}));for(const a of state.capabilities.filter(x=>x.kind==='agent'&&x.enabled))root.append(el('button',{class:'employee-card',type:'button',onclick:()=>{pickAgent(a.id);dlg.close();}},personAvatar12('agent',a.id,a.name),el('h3',{},a.name),el('p',{},a.description)));queueMicrotask(loadProfiles12);};
const priorPaint12=paintInlineRun11;paintInlineRun11=function(record){priorPaint12(record);const card=$('[data-inline-run="'+record.id+'"]');if(!card)return;const event=record.events.find(x=>x.event==='input.progressive_context'),last=record.events.filter(x=>x.event==='context.compacted').at(-1);let note=card.querySelector('.progressive-context-note');if(event||last){if(!note){note=el('p',{class:'help progressive-context-note'});card.querySelector('.inline-run-details').after(note);}note.textContent=(event?.payload.mode==='greeting'?'轻量问候 · 无文件/工具调用':'资料按需检索 · 技能渐进加载')+(last?' · 本轮压缩 '+last.payload.compressed_messages+' 条上下文，原文保留':'');}};


const previousLogout12=logout;logout=function(show=true){clearTimeout(profileTimer12);profileTimer12=null;profileRequested12.clear();profiles12.clear();profileScope12=null;previousLogout12(show);};
const avatarPaint12=paintInlineRun11;paintInlineRun11=function(record){avatarPaint12(record);const card=$('[data-inline-run="'+record.id+'"]'),id=record.meta.agent_id;if(card&&id)card.querySelector('.inline-run-heading > .avatar')?.replaceWith(personAvatar12('agent',id,record.meta.agent_name||'AI'));};


const scopePanel12=taskContextPanel;taskContextPanel=function(){const p=scopePanel12();for(const n of p.querySelectorAll('p'))if(n.textContent.includes('固定版'))n.textContent='员工在团队统一配置；直接 @ 即可使用，只读取当前任务和项目。';return p;};
const outputPause12=paintInlineRun11;paintInlineRun11=function(r){outputPause12(r);if(r.meta.status==='paused'&&r.events.some(x=>x.event==='output.truncated')){const c=$('[data-inline-run="'+r.id+'"]');const status=c?.querySelector('.inline-run-status');if(status)status.textContent='输出达到上限 · 已暂停，未执行残缺参数';}};

// 0.13: one account-settings entry; the collapsed desktop rail remains usable.
const shellBefore13=renderShell;
renderShell=function(){shellBefore13();const side=$('.sidebar');if(!side)return;$('#self-avatar-button')?.remove();
 for(const n of side.querySelectorAll('.company-link')){const v=companyViews.find(x=>x[0]===n.dataset.companyView),label=v?.[1]||n.textContent;n.setAttribute('aria-label',label);n.title=label;for(const child of [...n.childNodes])if(child.nodeType===Node.TEXT_NODE){const span=el('span',{class:'rail-label'},child.textContent);child.replaceWith(span);}}
 const footer=side.querySelector('.sidebar-footer');if(footer){const trash=footer.querySelector('.trash-entry');footer.replaceChildren();if(trash){trash.title='回收站';trash.setAttribute('aria-label','回收站');for(const child of [...trash.childNodes])if(child.nodeType===Node.TEXT_NODE)child.replaceWith(el('span',{class:'rail-label'},child.textContent));footer.append(trash);}
 const name=state.user.display_name||state.user.username;footer.append(el('button',{type:'button',id:'account-settings-button',class:'account-entry',title:'个人与团队设置','aria-label':'个人与团队设置',onclick:()=>openAccountSettings13().catch(handle)},personAvatar12('human',state.user.id,name),el('span',{class:'account-text rail-label'},el('strong',{class:'account-name'},name),el('small',{},'个人与团队设置')),el('span',{class:'rail-label'},'⋯')));}
 const picker=side.querySelector('.company-picker');picker?.after(el('button',{type:'button',class:'rail-team-switch icon-btn',title:state.workspace?.name||'切换团队','aria-label':'切换团队',onclick:chooseWorkspace13},icon('users')));applyLeftSidebar();queueMicrotask(loadProfiles12);
};
function chooseWorkspace13(){const rows=el('div',{class:'stack'}),dlg=openDialog('切换团队',rows);for(const w of state.workspaces)rows.append(button(w.name,async()=>{dlg.close();state.workspace=w;await showCompany('overview');},{class:w.id===state.workspace?.id?'primary':'ghost'}));}
async function openAccountSettings13(initial='profile'){
 const workspace=state.workspace,w=workspace.id,me=await api('/account');if(state.workspace?.id!==w)return;state.user={...state.user,...me.user};
 const root=el('div',{class:'account-settings-layout'}),tabs=el('nav',{class:'account-tabs','aria-label':'设置分类'}),panels=el('div',{class:'account-panels'});root.append(tabs,panels);const dlg=openDialog('个人与团队设置',root,{wide:true});let generation=0;
 async function draw(tab){const gen=++generation;tabs.replaceChildren(...[['profile','个人资料','users'],['security','账号安全','settings'],['team','团队设置','tasks']].map(([id,label,ic])=>button(label,()=>draw(id).catch(handle),{class:tab===id?'active':'ghost',icon:ic})));panels.replaceChildren();
 if(tab==='profile'){
  const avatarArea=el('section',{class:'account-avatar-area'},el('h3',{},'头像')),form=el('form',{class:'stack'},field('display_name','显示名称','text',state.user.display_name||state.user.username,{attrs:{required:true,maxlength:80}}),el('p',{class:'help'},'登录账号：'+state.user.username+'。改名不会改写以前消息的作者记录。')),error=el('p',{class:'form-error',role:'status'}),save=el('button',{type:'submit',class:'btn primary'},'保存名称');form.append(error,save);panels.append(el('h2',{},'个人资料'),avatarArea,form,el('hr',{class:'divider'}),el('div',{class:'row spread'},el('span',{},'外观'),button('切换明暗外观',toggleTheme,{class:'ghost',icon:'moon'})));
  form.addEventListener('submit',async e=>{e.preventDefault();if(!form.reportValidity())return;save.disabled=true;error.textContent='';try{const r=await api('/account',{method:'PATCH',body:{display_name:form.elements.display_name.value.trim()}});state.user={...state.user,...r.user};document.querySelectorAll('.account-name').forEach(n=>n.textContent=state.user.display_name);toast('名称已保存；历史消息保持原作者记录');}catch(e){error.textContent=e.message;}finally{save.disabled=false;}});
  const data=await api('/workspaces/'+w+'/avatars?subjects=human:'+state.user.id);if(gen!==generation||!dlg.dialog.isConnected)return;const current=data.items[0];if(!current)return;let preset=current.preset,image=null;const preview=personAvatar12('human',state.user.id,state.user.display_name),grid=el('div',{class:'avatar-presets'}),note=el('p',{class:'help',role:'status'}),upload=el('input',{type:'file',accept:'image/png,image/jpeg,image/webp','aria-label':'上传个人头像'});preview.classList.add('large');
  const drawAv=()=>grid.replaceChildren(...PRESET_AVATARS.human.map((emoji,index)=>button(emoji,()=>{preset=index;image=null;preview.replaceChildren(emoji);drawAv();},{class:'avatar-preset'+(preset===index&&!image?' selected':''),title:'个人头像 '+(index+1)})));drawAv();
  upload.addEventListener('change',()=>{const file=upload.files[0];if(!file)return;if(file.size>2097152){note.textContent='图片不能超过2MB';return;}const reader=new FileReader();reader.onload=()=>{image=String(reader.result).split(',')[1];note.textContent='已选择 '+file.name+'；保存时在本机校验并去除元数据。';};reader.readAsDataURL(file);});
  const saveAv=button('保存头像',async()=>{saveAv.disabled=true;try{const p=await api('/workspaces/'+w+'/avatars/human/'+state.user.id,{method:'PUT',body:{expected_revision:current.revision,...(image?{image_base64:image}:{preset})}});Object.assign(current,p);profiles12.set('human:'+state.user.id,p);refreshProfileNodes12();note.textContent='头像已保存';}catch(e){note.textContent=e.message;}finally{saveAv.disabled=false;}},{class:'small'});avatarArea.append(el('div',{class:'row'},preview,el('p',{class:'help'},'选择预设，或上传不超过2MB的PNG、JPEG、WebP。')),grid,upload,note,saveAv);
 }else if(tab==='security'){
  const f=el('form',{class:'stack'},el('h2',{},'账号安全'),field('old_password','当前密码','password','',{attrs:{required:true,maxlength:200,autocomplete:'current-password'}}),field('new_password','新密码','password','',{attrs:{required:true,minlength:12,maxlength:200,autocomplete:'new-password'},help:'至少12位，包含大小写字母、数字和符号；不能与旧密码相同。'}),field('confirm_password','确认新密码','password','',{attrs:{required:true,minlength:12,maxlength:200,autocomplete:'new-password'}})),error=el('p',{class:'form-error',role:'status'}),save=el('button',{type:'submit',class:'btn primary',disabled:!me.has_password},'更新密码并重新登录');f.append(error,save,el('p',{class:'help'},'仅修改当前账号。保存后退出本浏览器；其他设备的既有会话按原有效期失效，不会批量重置团队密钥。'));f.addEventListener('submit',async e=>{e.preventDefault();if(!f.reportValidity())return;save.disabled=true;error.textContent='';try{const v=values(f);if(v.new_password!==v.confirm_password)throw Error('两次新密码不一致');await api('/account/password',{method:'POST',body:v});f.reset();dlg.close();logout();toast('密码已更新，请使用新密码登录');}catch(e){error.textContent=e.message;}finally{save.disabled=false;}});panels.append(f,el('hr',{class:'divider'}),button('退出当前登录',()=>{dlg.close();logout();},{class:'danger',icon:'logout'}));
 }else{
  panels.append(el('h2',{},'团队设置'),el('p',{class:'help'},'当前团队：'+workspace.name+'。团队权限与个人资料分开；成员不会因修改个人设置获得管理权限。'));
  if(companyOwner()){
   const f=el('form',{class:'stack'},field('name','团队名称','text',workspace.name,{attrs:{required:true,maxlength:120}}),field('description','团队简介','textarea',workspace.description||'',{attrs:{maxlength:4000}})),error=el('p',{class:'form-error',role:'status'}),save=el('button',{type:'submit',class:'btn primary'},'保存团队设置');f.append(error,save);f.addEventListener('submit',async e=>{e.preventDefault();if(!f.reportValidity())return;save.disabled=true;try{const updated=await api('/workspaces/'+w,{method:'PATCH',body:{...values(f),expected_revision:workspace.revision}});Object.assign(workspace,updated);const actual=state.workspaces.find(x=>x.id===w);if(actual)Object.assign(actual,updated);const option=document.querySelector('.workspace-switch option[value="'+CSS.escape(w)+'"]');if(option)option.textContent=updated.name;toast('团队设置已保存');}catch(e){error.textContent=e.message;}finally{save.disabled=false;}});panels.append(f);
  }else panels.append(el('p',{class:'notice neutral'},'你可以查看当前团队；名称和权限由团队管理员维护。'));
  panels.append(el('div',{class:'row wrap'},button('管理团队成员',()=>{dlg.close();showCompany('people').catch(handle);},{icon:'users'}),button('切换团队',()=>{dlg.close();chooseWorkspace13();},{class:'ghost'})));
 }
 }
 await draw(initial);
}
companySettings=function(){return openAccountSettings13('team').catch(handle);};
const progressBefore13=paintInlineRun11;paintInlineRun11=function(record){progressBefore13(record);const note=$('[data-inline-run="'+record.id+'"] .progressive-context-note'),event=record.events.find(x=>x.event==='input.progressive_context');if(note&&event?.payload.focus_mode)note.textContent=(['identity','greeting'].includes(event.payload.focus_mode)?'轻量问答 · 当前问题优先 · 不启动旧任务':'当前问题优先 · 历史仅作背景，缺失内容按需回读')+(record.events.some(x=>x.event==='context.compacted')?' · 工作上下文已压缩，原文保留':'');};


// 0.14: compact discussion, run trace within the reply, task-scoped live presence.
const collaboration14={abort:null,task:null,project:null,online:new Set(),typing:new Map(),retry:0,live:false,lastTyping:0,typingTimer:null,refreshing:false};

function closeCollaboration14(){
 collaboration14.abort?.abort();collaboration14.abort=null;collaboration14.task=null;collaboration14.project=null;
 collaboration14.online.clear();collaboration14.typing.clear();collaboration14.retry=0;collaboration14.live=false;
 clearTimeout(collaboration14.typingTimer);collaboration14.typingTimer=null;
}
function presenceView14(){
 if(!state.task)return;
 const count=collaboration14.online.size,total=state.members.length,top=$('.discussion-top>span');
 if(top)top.textContent=(collaboration14.live?count+' 在线 / '+total+' 位成员':'实时连接中 · '+total+' 位成员')+' · @ 邀请 AI';
 const people=$('.participants');if(people){
  people.replaceChildren(...state.members.map(m=>{
   const active=collaboration14.online.has(Number(m.user_id));
   return el('span',{class:'participant human-presence',title:active?'正在查看当前任务':'未在查看当前任务'},
    personAvatar12('human',m.user_id,m.display_name),
    el('span',{class:'presence-dot '+(active?'is-online':'is-away'),'aria-label':active?'在线':'未在此任务在线'}),
    el('small',{},m.display_name));
  }));
 }
 const indicator=$('.typing-indicator');
 if(indicator){
  const now=Date.now();
  for(const [uid,entry] of collaboration14.typing)if(entry.until<now)collaboration14.typing.delete(uid);
  const names=[...collaboration14.typing].filter(([uid])=>uid!==Number(state.user?.id)).map(([uid])=>memberName(uid));
  indicator.textContent=names.length?(names.slice(0,2).join('、')+' 正在输入…'):'';
  indicator.hidden=!names.length;
 }
}
async function refreshFromLive14(){
 if(collaboration14.refreshing||!state.task)return;
 collaboration14.refreshing=true;const generation=state.generation;
 try{await fetchMessages(generation);if(generation===state.generation){setConnection(true);syncInlineRuns11();}}
 catch(e){if(e.name!=='AbortError'&&e.status!==403&&e.status!==404)setConnection(false);}
 finally{collaboration14.refreshing=false;}
}
async function connectCollaboration14(taskId,projectId){
 closeCollaboration14();
 if(!taskId||!projectId||!state.token)return;
 const controller=new AbortController();collaboration14.abort=controller;collaboration14.task=taskId;collaboration14.project=projectId;
 const current=()=>!controller.signal.aborted&&state.task?.id===taskId&&state.project?.id===projectId&&collaboration14.abort===controller;
 for(let attempt=0;attempt<100&&current();attempt++){
  let reader=null;
  try{
   const response=await fetch(API+'/tasks/'+encodeURIComponent(taskId)+'/live',{
    method:'GET',headers:{Authorization:'Bearer '+state.token,Accept:'text/event-stream'},
    cache:'no-store',signal:controller.signal,
   });
   if(!current())break;
   if([401,403,404].includes(response.status)){collaboration14.live=false;presenceView14();break;}
   if(!response.ok||!response.body)throw Error('Live stream '+response.status);
   collaboration14.live=true;collaboration14.retry=0;presenceView14();
   reader=response.body.getReader();
   const decoder=new TextDecoder(),frames=new SSEFrames();
   while(current()){
    const {done,value}=await reader.read();if(done||!current())break;
    for(const frame of frames.push(decoder.decode(value,{stream:true}))){
     let payload;try{payload=JSON.parse(frame.data||'{}');}catch{continue;}
     if(frame.event==='access_revoked'){controller.abort();collaboration14.live=false;presenceView14();break;}
     if(frame.event==='presence'){
      collaboration14.online=new Set((payload.online_ids||[]).map(Number));presenceView14();
     }else if(frame.event==='message'){
      // Notifications never carry message bodies; read exact authorized messages.
      refreshFromLive14();
     }else if(frame.event==='typing'){
      const uid=Number(payload.user_id);
      if(payload.active)collaboration14.typing.set(uid,{until:Date.now()+Math.min(4500,Number(payload.expires_ms)||4200)});
      else collaboration14.typing.delete(uid);
      presenceView14();
      clearTimeout(collaboration14.typingTimer);
      collaboration14.typingTimer=setTimeout(presenceView14,4600);
     }
    }
   }
  }catch(e){if(!current())break;collaboration14.live=false;presenceView14();}
  finally{if(reader){try{await reader.cancel();}catch{}reader.releaseLock();}}
  if(!current())break;
  collaboration14.online.clear();collaboration14.live=false;presenceView14();
  await new Promise(resolve=>setTimeout(resolve,Math.min(7000,700*Math.pow(1.5,Math.min(attempt,6)))));
 }
}
function reportTyping14(active){
 if(!state.task||!canWrite()||!collaboration14.live)return;
 const now=Date.now();if(active&&now-collaboration14.lastTyping<1600)return;
 collaboration14.lastTyping=now;
 const tid=state.task.id;
 api('/tasks/'+tid+'/typing',{method:'POST',body:{active}}).catch(()=>{});
}

// Run activity is a subordinate disclosure within its own AI response.
const buildActivity14=activityCard11;
activityCard11=function(record){
 const card=buildActivity14(record);
 if(sessionStorage.getItem(foldedKey11(record.id))===null)card.parts.details.open=false;
 return card;
};
positionCard11=function(card,record,list){
 const response=state.messages.find(m=>m.run_id===record.id);
 const message=response&&list.querySelector('#message-'+CSS.escape(response.id));
 const existing=list.querySelector('[data-run-shell="'+record.id+'"]');
 if(message){
  message.querySelector('.message-body')?.append(card);
  existing?.remove();
  card.classList.add('run-in-reply');
  return;
 }
 let shell=existing;
 if(!shell){
  const profile=personAvatar12('agent',record.meta.agent_id||'run:'+record.id,record.meta.agent_name||'AI 员工');
  shell=el('article',{class:'message message-agent message-run-shell','data-run-shell':record.id},
   profile,el('div',{class:'message-body'},el('div',{class:'message-meta'},el('strong',{},record.meta.agent_name||'AI 员工'),el('small',{},'执行中或未生成最终回复'))));
 }
 shell.querySelector('.message-body').append(card);
 const anchor=state.messages.find(m=>Number(m.seq)>Number(record.meta.input_seq??Infinity));
 const next=anchor&&list.querySelector('#message-'+CSS.escape(anchor.id));
 if(next){if(shell.nextSibling!==next)list.insertBefore(shell,next);}
 else if(shell.parentNode!==list)list.append(shell);
 card.classList.remove('run-in-reply');
};
const oldPaint14=paintInlineRun11;
paintInlineRun11=function(record){
 oldPaint14(record);
 const card=document.querySelector('[data-inline-run="'+record.id+'"]');if(!card||!card.parts)return;
 const {heading,details,actions}=card.parts;
 heading.hidden=true; // Parent AI bubble (or temporary AI shell) owns the avatar and name.
 const note=card.querySelector('.progressive-context-note');
 if(note&&note.parentNode!==details)details.append(note);
 const usage=card.querySelector('.inline-run-usage');if(usage&&usage.parentNode!==details)details.append(usage);
 if(actions.parentNode!==details)details.append(actions);
 card.dataset.terminal=String(terminalRun(record.meta.status));
 card.dataset.containsReply=String(!!state.messages.find(m=>m.run_id===record.id));
};
// The existing stream/render cycle calls positionCard11, so already saved runs
// are reparented under their replies on load without rewriting any message row.
const priorDiscussion14=renderDiscussion;
renderDiscussion=function(content){
 priorDiscussion14(content);
 if(!state.task)return;
 const composer=content.querySelector('.composer-wrap');
 if(composer&&!content.querySelector('.typing-indicator')){
  const typing=el('div',{class:'typing-indicator',role:'status','aria-live':'polite',hidden:true});
  composer.before(typing);
 }
 const textarea=content.querySelector('.composer textarea');
 textarea?.addEventListener('input',()=>reportTyping14(!!textarea.value.trim()),{passive:true});
 presenceView14();
};
const priorContext14=taskContextPanel;
taskContextPanel=function(){
 const panel=priorContext14();
 panel.querySelector('.agent-config-section')?.remove();
 panel.querySelector('.trace-advanced')?.remove();
 const title=panel.querySelector('.context-section h3');
 if(title)title.textContent='当前任务成员';
 for(const p of panel.querySelectorAll('p'))if(p.textContent.includes('AI 在请求时参与'))p.textContent='这里仅显示正在查看此任务的真人成员；AI 员工通过聊天框 @ 选择。';
 queueMicrotask(presenceView14);
 return panel;
};
const priorControls14=refreshAgentControls;
refreshAgentControls=function(){priorControls14();presenceView14();};
const priorOpenTask14=openTask;
openTask=async function(...args){
 closeCollaboration14();
 await priorOpenTask14(...args);
 if(state.task)connectCollaboration14(state.task.id,state.project.id);
};
const priorReset14=resetView;
resetView=function(){closeCollaboration14();priorReset14();};
const priorLogout14=logout;
logout=function(...args){closeCollaboration14();return priorLogout14(...args);};
const priorSend14=sendMessage;
sendMessage=async function(...args){reportTyping14(false);return priorSend14(...args);};

// The discussion summarizer must state which employee and which interval it uses.
function openSummary14(){
 if(!state.task)return toast('请先进入任务讨论',true);
 const agents=state.capabilities.filter(a=>a.kind==='agent'&&a.enabled);
 const tid=state.task.id;
 const summaries=state.runs.filter(r=>r.kind==='summary'&&r.status==='completed'&&r.request?.task_id===tid);
 const last=summaries.reduce((n,r)=>Math.max(n,Number(r.input_seq)||0),0);
 const items=state.messages.filter(m=>m.seq>last);
 if(!agents.length)return toast('团队尚无可用的 AI 员工，请先在 AI 员工中启用一位',true);
 if(!items.length)return toast('当前任务没有新增讨论需要整理');
 const selected=el('select',{class:'input','aria-label':'本次整理使用的AI员工'},agents.map(a=>el('option',{value:a.id,selected:a.id===state.agentId},a.name)));
 const detail=el('div',{class:'summary-agent-detail notice neutral'});
 const draw=()=>{
  const a=agents.find(x=>x.id===selected.value)||agents[0];
  detail.textContent='执行者：'+a.name+' · 模型：'+(a.data?.model||state.settings?.model||'团队默认')+' · 最多2步 · 本次不使用 MCP、平台写入或文件工具。';
 };
 selected.addEventListener('change',draw);draw();
 const root=el('div',{class:'stack'},el('p',{},'把当前任务新增的真人和 AI 对话整理为待确认纪要、任务、日程和决定。'),el('p',{class:'help'},'消息范围：#'+items[0].seq+'–#'+items.at(-1).seq+'，共 '+items.length+' 条。只读取这段对话，不会自动改变任务、日程或发布知识。'),el('label',{class:'field'},'本次使用哪位 AI 员工',selected),detail,el('p',{class:'help'},'整理会调用所选员工的模型，可能产生用量。结果会保存在「待采用」中，必须由成员核对。'));
 const dlg=openDialog('整理任务讨论 · 执行规则',root,{wide:true});
 dlg.dialog.querySelector('.modal-shell').append(dlg.footer);
 const go=button('使用所选员工整理',async()=>{
  const a=agents.find(x=>x.id===selected.value);
  go.disabled=true;
  try{
   const body={kind:'summary',agent_id:a.id,agent_revision:a.revision,client_id:crypto.randomUUID(),
    from_seq:items[0].seq,to_seq:items.at(-1).seq,
    run_options:{permission_mode:'safe',budget:'configured'}};
   if(a.binding_revision)body.binding_revision=a.binding_revision;
   const r=await api('/tasks/'+tid+'/runs',{method:'POST',body});
   dlg.close();rememberStartedRun(r);followAgentRun(r.id);syncInlineRuns11();
   toast('已由 '+a.name+' 开始整理；只生成待确认候选');
  }catch(e){handle(e);go.disabled=false;}
 },{class:'primary'});
 dlg.footer.append(button('取消',()=>dlg.close()),go);
}
const previousStartRun14=startRun;
startRun=async function(kind,...args){
 if(kind==='summary')return openSummary14();
 return previousStartRun14(kind,...args);
};


// 0.15 · Browser-based dictation -> text draft only; shared task/calendar display.
const priorVoiceField15=field;
field=function(...args){
 const wrapper=priorVoiceField15(...args);
 if(args[2]==='textarea'&&!wrapper.control.disabled)
  attachSpeechInput(wrapper.control,wrapper,{getToken:()=>state.token,notify:toast});
 return wrapper;
};
const priorVoiceDiscussion15=renderDiscussion;
renderDiscussion=function(content){
 priorVoiceDiscussion15(content);
 const box=content.querySelector('.composer textarea'),host=content.querySelector('.composer-bottom');
 if(box&&host)attachSpeechInput(box,host,{getToken:()=>state.token,notify:toast,compact:true});
};

function scheduleZone15(item,project){
 return project?.timezone||state.overview?.projects?.find(p=>p.id===item.project_id)?.timezone||'Asia/Shanghai';
}
function currentDayFor15(item,project){
 return dateKeyInZone(new Date(),scheduleZone15(item,project));
}
function monthGrid15(items,context='company'){
 const project=context==='project'?state.project:null;
 const zoneFor=item=>scheduleZone15(item,project);
 const today=dateKeyInZone(new Date(),project?.timezone||'Asia/Shanghai');
 const month=state.month,start=new Date(month.getFullYear(),month.getMonth(),1);
 start.setDate(start.getDate()-(start.getDay()+6)%7);
 const rerender=()=>context==='project'?renderView():renderCompanyContent();
 const title=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long'}).format(month);
 const controls=el('div',{class:'row spread month-controls'},el('h3',{},title),
 el('div',{class:'row'},iconButton('back','上个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()-1,1);rerender();}),
 button('本月',()=>{const now=new Date();state.month=new Date(now.getFullYear(),now.getMonth(),1);rerender();},{class:'small ghost'}),
 iconButton('chevron','下个月',()=>{state.month=new Date(month.getFullYear(),month.getMonth()+1,1);rerender();})));
 const grid=el('div',{class:'calendar-grid'},['一','二','三','四','五','六','日'].map(d=>el('div',{class:'calendar-day-name'},d)));
 const open=item=>context==='project'?calendarItem(item):openSchedule(item);
 for(let i=0;i<42;i++){
  const day=new Date(start);day.setDate(start.getDate()+i);
  const key=day.getFullYear()+'-'+String(day.getMonth()+1).padStart(2,'0')+'-'+String(day.getDate()).padStart(2,'0');
  const matches=entriesOnDay(items,key,item=>currentDayFor15(item,project),zoneFor);
  const cell=el('div',{class:'calendar-day'+(day.getMonth()!==month.getMonth()?' other-month':'')+(key===today?' is-today':''),'data-calendar-date':key},
   el('span',{class:'calendar-date'+(key===today?' today':'')},day.getDate()));
  for(const item of matches.slice(0,3)){
   const title=(item.project_title?item.project_title+' · ':'')+item.title+' · '+({ongoing:'进行中',deadline:'截止日',overdue:'逾期',completed:'已完成',review:'待验收',event:'安排',past:'已过去'}[item.style]||'日程');
   cell.append(el('button',{type:'button',class:'calendar-event calendar-'+item.style,title,onclick:()=>open(item)},item.title));
  }
  if(matches.length>3)cell.append(el('span',{class:'calendar-more'},'另有 '+(matches.length-3)+' 项'));
  grid.append(cell);
 }
 const {future,overdue}=agendaFrom(items,item=>currentDayFor15(item,project),zoneFor);
 const agenda=el('aside',{class:'panel agenda'},el('h3',{},'近期安排'));
 if(overdue.length){
  const section=el('div',{class:'calendar-overdue-list'},el('h4',{},'已逾期 · '+overdue.length));
  overdue.slice(0,5).forEach(item=>section.append(el('button',{type:'button',class:'calendar-agenda-row',onclick:()=>open(item)},el('span',{class:'overdue-mark'},'逾期'),el('span',{},item.title),el('small',{},item.sortDate))));
  agenda.append(section);
 }
 if(!future.length&&!overdue.length)agenda.append(el('p',{class:'muted'},'暂无后续安排，设置任务截止日期或创建会议即可展示。'));
 for(const item of future.slice(0,14)){
  const kind=item.kind==='task'?(item.status==='doing'?'进行中':'任务'):'日程';
  agenda.append(el('button',{type:'button',class:'calendar-agenda-row',onclick:()=>open(item)},
   el('span',{class:'agenda-date'},item.sortDate?.slice(5)||''),el('span',{class:'grow'},item.title),el('small',{},kind)));
 }
 const section=el('section',{class:'calendar-widget '+(context==='overview'?'home-calendar':'')},
  controls,el('div',{class:'calendar-layout'},el('section',{class:'panel'},grid),agenda));
 return section;
}
renderCalendar=function(content){
 const tz=state.project?.timezone||'Asia/Shanghai';
 content.append(el('div',{class:'view-head'},el('div',{},el('h2',{},'项目日程'),el('p',{},'进行中任务从今天持续显示至截止日；逾期后不继续高亮 · '+tz)),
 canWrite()&&button('新增安排',()=>eventDialog(),{class:'primary',icon:'plus'})),monthGrid15(state.calendar,'project'));
};
renderCompanyCalendar=function(container,items){
 container.replaceChildren(el('div',{class:'view-head'},el('div',{},el('h2',{},'团队日程'),el('p',{},'跨项目的进行中任务、截止日期与会议'))),monthGrid15(items,'company'));
};
const oldCompanyContent15=renderCompanyContent;
renderCompanyContent=function(){
 oldCompanyContent15();
 if(state.companyView!=='overview'||!state.overview)return;
 const content=$('#content');if(!content)return;
 const section=el('section',{class:'dashboard-calendar'},el('div',{class:'view-head'},el('h2',{},'团队日历'),button('全部日程',()=>showCompany('calendar'),{class:'ghost small',icon:'calendar'})),monthGrid15(state.overview.calendar||[],'overview'));
 const anchor=content.querySelector('.dashboard-columns');
 if(anchor)anchor.before(section);else content.append(section);
};


// Gongzhi Fusion: original task-centered workflow + optional, bounded Agent handoffs.
// Reference: general information hierarchy and compact progress affordances, never Ekko code.
document.body.classList.add('gongzhi-fusion');
const fusion16 = { panel:null, task:null, generation:0, loading:false };

function fusionName(id){
 const asset=state.capabilities?.find(a=>a.id===id);
 return asset?.name || (id?'已停用/历史员工':'未配置');
}
function fusionTaskCurrent(id,gen){
 return !!id&&state.task?.id===id&&state.generation===gen;
}
async function fusionLoadPanels(panel,taskId,generation){
 if(!panel?.isConnected || !fusionTaskCurrent(taskId,generation))return;
 const summaryBody=panel.querySelector('[data-fusion-summary]');
 const workflowBody=panel.querySelector('[data-fusion-workflow]');
 if(!summaryBody||!workflowBody)return;
 try{
  const [summary,flow,handoffs]=await Promise.all([
   api('/tasks/'+taskId+'/context-summary'),
   api('/tasks/'+taskId+'/workflow'),
   api('/tasks/'+taskId+'/handoffs')
  ]);
  if(!panel.isConnected||!fusionTaskCurrent(taskId,generation))return;
  fusionRenderSummary(summaryBody,summary,taskId);
  fusionRenderWorkflow(workflowBody,flow,handoffs.items||[],taskId);
 }catch(e){
  if(!panel.isConnected||!fusionTaskCurrent(taskId,generation))return;
  summaryBody.replaceChildren(el('p',{class:'form-error'},'读取上下文失败，请检查任务权限。'));
  workflowBody.replaceChildren(el('p',{class:'form-error'},'读取流程失败：'+(e?.message||'网络错误')));
 }
}
function fusionRenderSummary(root,data,taskId){
 const host=root.closest('.fusion-card'),label=host?.querySelector('[data-fusion-summary-label]');
 root.replaceChildren();
 if(label)label.textContent=data.status==='ready'?'覆盖 '+data.source_count+' 条历史 · v'+data.revision:'按需生成';
 if(data.status==='ready'){
  root.append(
   el('p',{class:'fusion-hint'},'这些是较早讨论的来源摘录，不是新的指令，也不是自动采用的知识。'),
   el('pre',{class:'fusion-summary-text'},data.summary),
   el('p',{class:'fusion-hint'},'游标：消息 #'+data.through_seq+' · 版本 '+data.revision+' · 可按消息编号回读原话')
  );
 }else{
  root.append(el('p',{class:'fusion-hint'},data.status==='stale'?'旧摘要对应的消息已变化，需要重新提取。':
    '当前任务暂未产生足够的早期讨论；最新提问不需要为此等待或调用模型。'));
 }
 if(canWrite()){
  const btn=button('刷新来源摘要（不调用模型）',async()=>{
   btn.disabled=true;
   try{
    const revised=await api('/tasks/'+taskId+'/context-summary',{method:'POST',body:{}});
    if(state.task?.id===taskId)fusionRenderSummary(root,revised,taskId);
   }catch(e){handle(e);}finally{btn.disabled=false;}
  },{class:'small ghost',icon:'refresh'});
  root.append(btn);
 }
}
function fusionRenderWorkflow(root,flow,items,taskId){
 const host=root.closest('.fusion-card'),label=host?.querySelector('[data-fusion-flow-label]');
 root.replaceChildren();
 if(label)label.textContent=items.length?items.length+' 次交接 · 最多 2 跳':'当前任务暂无交接';
 root.append(el('p',{class:'fusion-hint'},
  '研究/执行 Run → 人工批准 → 下一位员工 Run → 人工验收。所有阶段都归属本任务。流程是已发生操作的视图，不会自动发布知识或启动更多员工。'));
 if(!items.length){
  root.append(el('p',{class:'fusion-empty'},'从某位 AI 员工已经完成的回复下方，点击「转交另一位员工」开始。'));
  return;
 }
 const nodes=new Map((flow.nodes||[]).map(n=>[n.handoff_id,n]));
 for(const item of [...items].reverse()){
  const node=nodes.get(item.id),stateText={
   pending:'等待管理员批准',approved:'已批准，目标运行 '+(node?.target_run_status||'已安排'),
   rejected:'已拒绝',cancelled:'已取消',dispatching:'正在确认执行状态'
  }[item.status]||item.status;
  const row=el('section',{class:'fusion-flow-item'},
   el('div',{class:'fusion-flow-top'},el('span',{class:'fusion-flow-hop'},'第 '+item.hop+' 跳'),
    el('strong',{},fusionName(item.source_agent_id)+' → '+fusionName(item.target_agent_id)),
    el('span',{class:'grow'}),badge(stateText)),
   el('p',{class:'fusion-flow-request'},item.instruction),
   el('small',{class:'fusion-hint'},'源 Run '+item.source_run_id.slice(0,12)+' · 始终保留人工审批与来源'),
   el('div',{class:'fusion-flow-actions row wrap'})
  );
  const actions=row.querySelector('.fusion-flow-actions');
  actions.append(button('查看来源',()=>openTrace(item.source_run_id),{class:'small ghost'}));
  if(item.target_run_id)actions.append(button('查看接力结果',()=>openTrace(item.target_run_id),{class:'small ghost'}));
  if(item.status==='pending'){
   if(isOwner()){
    actions.append(button('批准并运行',()=>fusionApprove(taskId,item),{class:'small primary'}));
    actions.append(button('拒绝',()=>fusionReject(taskId,item.id),{class:'small ghost'}));
   }else if(Number(item.requested_by)===Number(state.user?.id)){
    actions.append(button('撤销申请',()=>fusionCancel(taskId,item.id),{class:'small ghost'}));
   }else{
    actions.append(el('span',{class:'fusion-hint'},'等待项目管理员操作'));
   }
  }else if(item.status==='dispatching'){
   actions.append(el('small',{class:'fusion-hint'},'不自动重发；请核对源 Run 与目标 Run 后人工处理'));
   if(isOwner())actions.append(button('核对发送状态',()=>confirmAction('核对接力发送中记录','只检查持久化的相同 Run，不会创建新模型请求。',async()=>{
    try{await api('/tasks/'+taskId+'/handoffs/'+item.id+'/reconcile',{method:'POST',body:{}});await fusionReloadPanels();toast('接力发送状态已核对，未自动重发模型');}
    catch(e){handle(e);await fusionReloadPanels();}
   }),{class:'small ghost'}));
  }
  root.append(row);
 }
}
async function fusionReloadPanels(){
 const panel=fusion16.panel;
 if(panel&&fusionTaskCurrent(fusion16.task,fusion16.generation))
  await fusionLoadPanels(panel,fusion16.task,fusion16.generation);
}
async function fusionApprove(taskId,item){
 confirmAction('批准跨员工任务交接',
  '将创建一条新的安全模式 Agent Run。目标员工只使用当前项目权限和历史来源回执；可能消耗模型额度，拒绝或断网不会自动重发。',
  async()=>{
   try{
    const out=await api('/tasks/'+taskId+'/handoffs/'+item.id+'/approve',{method:'POST',body:{}});
    toast('已启动目标 AI 员工，正在保存独立执行回执。');
    await fusionReloadPanels();
    if(out.target_run_id&&state.task?.id===taskId){
     const runs=await api(projectPath('/runs'));
     state.runs=runs.items;
     followAgentRun(out.target_run_id);
     syncInlineRuns11();
    }
   }catch(e){handle(e);await fusionReloadPanels();}
  });
}
function fusionReject(taskId,id){
 confirmAction('拒绝接力申请','这次申请不会调用模型，源运行和聊天历史仍保留。',async()=>{
  try{await api('/tasks/'+taskId+'/handoffs/'+id+'/reject',{method:'POST',body:{}});await fusionReloadPanels();toast('交接已拒绝');}catch(e){handle(e);}
 });
}
function fusionCancel(taskId,id){
 confirmAction('撤销交接申请','仅撤销尚未被批准的请求，不修改原始 Run。',async()=>{
  try{await api('/tasks/'+taskId+'/handoffs/'+id+'/cancel',{method:'POST',body:{}});await fusionReloadPanels();toast('已撤销');}catch(e){handle(e);}
 });
}
function fusionOpenHandoff(record){
 if(!state.task||record.meta.status!=='completed')return;
 const agents=(state.capabilities||[]).filter(a=>a.kind==='agent'&&a.enabled&&a.id!==record.meta.agent_id);
 if(!agents.length){toast('需要先在 AI 员工中启用第二位可用专家',true);return;}
 const taskId=state.task.id;
 const selector=el('select',{class:'input','aria-label':'目标AI员工'},
  agents.map(a=>el('option',{value:a.id},a.name)));
 const instruction=el('textarea',{class:'input',rows:4,maxlength:1500,
  'aria-label':'交接目标',placeholder:'明确说明要请第二位员工完成什么、如何验收，避免重复写入已有成果。'});
 const help=el('p',{class:'fusion-hint'},
  '仅当前任务、当前授权范围。一次接力最多两跳；必须由项目管理员批准后才调用目标模型。源 Run 的工具回执和资料版本可核查。');
 const root=el('div',{class:'stack'},
  el('div',{class:'fusion-flow-brief'},el('strong',{},'来源：'+fusionName(record.meta.agent_id)),
   el('small',{},' Run '+record.id.slice(0,16)+' · 已完成但产物仍待人工验收')),
  el('label',{class:'field'},'接收的 AI 员工',selector),
  el('label',{class:'field'},'本次交接目标',instruction),help);
 const dialog=openDialog('向另一位 AI 员工交接 · 当前任务',root,{wide:true});
 dialog.dialog.querySelector('.modal-shell')?.append(dialog.footer);
 const submit=button('提交人工审批',async()=>{
  const text=instruction.value.trim();
  if(!text){toast('请明确写出本次交接目标',true);instruction.focus();return;}
  submit.disabled=true;
  try{
   await api('/tasks/'+taskId+'/handoffs',{method:'POST',
    body:{source_run_id:record.id,target_agent_id:selector.value,instruction:text}});
   dialog.close();toast('交接请求已记录，等待管理员批准；不会自动调用模型');
   await fusionReloadPanels();
  }catch(e){handle(e);submit.disabled=false;}
 },{class:'primary'});
 dialog.footer.append(button('取消',()=>dialog.close(),{class:'ghost'}),submit);
}
const previousTaskContextFusion=taskContextPanel;
taskContextPanel=function(){
 const panel=previousTaskContextFusion();
 if(!state.task)return panel;
 // Keep the right rail task-centric. Agent management stays in the global Employee page.
 for(const section of panel.querySelectorAll('.context-section')){
  if(section.querySelector('h3')?.textContent==='助手上下文')section.remove();
 }
 const wrapper=el('div',{class:'fusion-panel-wrap'});
 const summary=el('details',{class:'fusion-card'},
  el('summary',{},icon('files',15),el('strong',{},'持续上下文'),
   el('small',{'data-fusion-summary-label':''},'读取状态'),icon('chevron',14)),
  el('div',{class:'fusion-card-body','data-fusion-summary':''},el('p',{class:'muted'},'正在读取来源状态…')));
 const workflow=el('details',{class:'fusion-card'},
  el('summary',{},icon('plan',15),el('strong',{},'员工接力与任务流程'),
   el('small',{'data-fusion-flow-label':''},'读取记录'),icon('chevron',14)),
  el('div',{class:'fusion-card-body','data-fusion-workflow':''},el('p',{class:'muted'},'正在读取真实执行记录…')));
 const refresh=iconButton('refresh','刷新上下文与接力',()=>fusionReloadPanels());
 wrapper.append(el('div',{class:'fusion-panel-title'},el('span',{},'任务执行与知识'),refresh),summary,workflow);
 panel.insertBefore(wrapper,panel.querySelector('.context-section:nth-of-type(2)')||panel.firstChild);
 fusion16.panel=panel;fusion16.task=state.task.id;fusion16.generation=state.generation;
 queueMicrotask(()=>fusionLoadPanels(panel,fusion16.task,fusion16.generation));
 return panel;
};
const previousPaintFusion=paintInlineRun11;
paintInlineRun11=function(record){
 previousPaintFusion(record);
 const card=document.querySelector('[data-inline-run="'+record.id+'"]');
 if(!card)return;
 let action=card.parentElement?.querySelector('[data-fusion-handoff="'+record.id+'"]');
 const reply=state.messages.find(m=>m.run_id===record.id);
 const parent=card.closest('.message-body');
 if(record.meta.status==='completed'&&record.meta.agent_id&&reply&&parent&&canWrite()){
  if(!action){
   action=button('转交给另一位 AI 员工',()=>fusionOpenHandoff(record),{class:'fusion-handoff-btn small ghost',icon:'users'});
   action.setAttribute('data-fusion-handoff',record.id);
   parent.append(action);
  }
 }else action?.remove();
};
// The live SSE sends tiny notifications; re-fetch only handoff metadata.
const previousRefreshFromLiveFusion=refreshFromLive14;
refreshFromLive14=async function(){
 await previousRefreshFromLiveFusion();
 // The task data panel is on demand; only refresh it when user expanded it.
 if(fusion16.panel?.querySelector('.fusion-card[open]'))fusionReloadPanels().catch(()=>{});
};


// Fusion M3: real, task-local, user-controlled sequential plan, not a fake DAG.
function fusionSafeOwner(){return !!state.task&&isOwner();}
function fusionPlanUrl(taskId){return '/tasks/'+encodeURIComponent(taskId)+'/plan';}
const fusionPlanLabels={
 pending:'待开始',dispatching:'正在准备执行',running:'执行中',
 needs_review:'待核验',accepted:'已人工核验',blocked:'失败 / 已暂停',
 rejected:'已拒绝'
};
async function fusionLoadPlan(host,tid,generation){
 if(!host?.isConnected||!fusionTaskCurrent(tid,generation))return;
 try{
  const plan=await api(fusionPlanUrl(tid));
  if(host.isConnected&&fusionTaskCurrent(tid,generation))
   fusionRenderPlan(host,plan,tid);
 }catch(e){
  if(host.isConnected&&fusionTaskCurrent(tid,generation))
   host.replaceChildren(el('p',{class:'form-error'},'读取任务执行计划失败，请检查网络与权限。'));
 }
}
function fusionPlanRefresh(){
 const host=fusion16.panel?.querySelector('[data-fusion-plan]');
 if(host&&fusion16.task&&fusion16.generation===state.generation)
   return fusionLoadPlan(host,fusion16.task,fusion16.generation);
}
function fusionPlanDialog(previous=null){
 if(!state.task)return;
 if(!fusionSafeOwner()){toast('只有当前项目管理员能创建或修改流程计划',true);return;}
 const agents=(state.capabilities||[]).filter(x=>x.kind==='agent'&&x.enabled);
 if(!agents.length){toast('请先在公司「AI 员工」中启用一位专家',true);return;}
 const steps=previous?.steps?.map(x=>({
   kind:x.kind,title:x.title,instruction:x.instruction,agent_id:x.agent_id
 }))||[
  {kind:'agent',title:'研究与资料核查',instruction:'阅读授权资料，提炼有来源的事实、限制与未决问题。',agent_id:agents[0].id},
  {kind:'agent',title:'设计或开发方案',instruction:'结合上一步已核验结果形成可审阅的实施方案，不重复写入业务对象。',agent_id:agents[1]?.id||agents[0].id},
  {kind:'review',title:'人工核验成果',instruction:'核对模型输出、文件版本和真实工具回执；未经人工批准不宣布已完成。'}
 ];
 const title=el('input',{class:'input',maxlength:160,required:true,value:previous?.title||'研究 → 方案 → 人工审核',
  'aria-label':'流程名称'});
 const description=el('textarea',{class:'input',rows:2,maxlength:1000,
  'aria-label':'流程目标',placeholder:'说明本次计划的目标、交付边界和验收对象。',
  value:previous?.description||'所有步骤都归属当前任务；每次调用模型前需人明确确认。'});
 const list=el('div',{class:'fusion-editor-steps'});
 const draw=()=>{
  list.replaceChildren();
  steps.forEach((s,index)=>{
   const kind=el('select',{class:'input','aria-label':'步骤类型'+(index+1)},[
    el('option',{value:'agent',selected:s.kind==='agent'},'AI 员工执行'),
    el('option',{value:'review',selected:s.kind==='review'},'真人验收')
   ]);
   const name=el('input',{class:'input',value:s.title,maxlength:120,'aria-label':'步骤名称'+(index+1)});
   const instruction=el('textarea',{class:'input',rows:3,maxlength:1200,
       'aria-label':'步骤要求'+(index+1)},s.instruction);
   const who=el('select',{class:'input','aria-label':'步骤执行员工'+(index+1)},
    agents.map(a=>el('option',{value:a.id,selected:a.id===s.agent_id},a.name)));
   const fields=el('div',{class:'fusion-editor-fields'},
    el('label',{class:'field'},'类型',kind),
    el('label',{class:'field'},'名称',name),
    el('label',{class:'field'},'执行员工',who),
    el('label',{class:'field fusion-editor-prompt'},'目标与验收要求',instruction));
   who.disabled=s.kind==='review';who.closest('label').hidden=s.kind==='review';
   kind.addEventListener('change',()=>{
    s.kind=kind.value;s.agent_id=s.kind==='agent'?(s.agent_id||agents[0].id):null;
    draw();
   });
   name.addEventListener('input',()=>s.title=name.value);
   instruction.addEventListener('input',()=>s.instruction=instruction.value);
   who.addEventListener('change',()=>s.agent_id=who.value);
   const actions=el('div',{class:'fusion-editor-step-actions'});
   if(steps.length>2 && index!==steps.length-1)
    actions.append(button('移除',()=>{steps.splice(index,1);draw();},{class:'small ghost'}));
   list.append(el('section',{class:'fusion-editor-step'},
    el('div',{class:'fusion-editor-step-head'},el('strong',{},'步骤 '+(index+1)),actions),fields));
  });
 };
 draw();
 const add=button('增加执行步骤',()=>{
  if(steps.length>=8){toast('最多支持8项受控步骤',true);return;}
  steps.splice(steps.length-1,0,{kind:'agent',title:'追加核查',instruction:'核对前一阶段的已验收成果，输出可核对的结论。',agent_id:agents[0].id});
  draw();
 },{class:'small ghost',icon:'plus'});
 const content=el('div',{class:'stack'},el('p',{class:'fusion-hint'},
   '这不是无约束自动运行的流程图：每个 Agent 步骤必须由管理员点击启动，成功后由真人核验；最后一项始终为人工审核。'),
  el('label',{class:'field'},'流程名称',title),
  el('label',{class:'field'},'目标说明',description),
  list,add,
  el('p',{class:'fusion-hint'},'创建/编辑计划不会调用大模型、不会修改已采用知识，历史已有运行不能被静默替换。'));
 const dlg=openDialog(previous?'编辑未开始的执行计划':'制定任务执行计划',content,{wide:true});
 dlg.dialog.querySelector('.modal-shell').append(dlg.footer);
 const submit=button(previous?'保存修订':'创建计划',async()=>{
  const body={title:title.value.trim(),description:description.value.trim(),
    steps:steps.map(x=>({kind:x.kind,title:x.title.trim(),instruction:x.instruction.trim(),
      ...(x.kind==='agent'?{agent_id:x.agent_id}: {})}))};
  if(!body.title||body.steps.some(s=>!s.title||!s.instruction)){toast('步骤名称和说明均不能为空',true);return;}
  if(body.steps.at(-1).kind!=='review'){toast('最后一步必须由真人审核',true);return;}
  submit.disabled=true;
  try{
   if(previous)body.expected_revision=previous.revision;
   await api(fusionPlanUrl(state.task.id),{method:previous?'PUT':'POST',body});
   dlg.close();await fusionPlanRefresh();
   toast('任务流程已保存。启动每一步仍须管理员确认。');
  }catch(e){handle(e);submit.disabled=false;}
 },{class:'primary'});
 dlg.footer.append(button('取消',()=>dlg.close(),{class:'ghost'}),submit);
}
async function fusionTriggerPlan(tid,sid,kind){
 const endpoint=fusionPlanUrl(tid)+'/steps/'+sid+'/'+kind;
 let note='';
 if(kind==='start'){
  confirmAction('启动本阶段 AI 员工',
   '启动后将运行真实模型，可能消耗额度。仍使用该员工已配置的权限与安全审批，失败不会自动重试。',async()=>{
    try{
     const result=await api(endpoint,{method:'POST',body:{}});
     await fusionPlanRefresh();
     const step=result.steps.find(x=>x.id===sid);
     if(step?.run_id)followAgentRun(step.run_id);
     toast('已启动独立 Run，执行过程留在本任务讨论。');
    }catch(e){handle(e);await fusionPlanRefresh();}
   });
  return;
 }
 if(kind==='reconcile'){
  confirmAction('人工核对发送中步骤','系统只查询本任务已入库的同一 Run，不会调用模型；如果尚无 Run，会恢复为待开始，仍需你再次确认启动。',async()=>{
   try{await api(endpoint,{method:'POST',body:{}});await fusionPlanRefresh();toast('发送状态已人工核对，未自动重发模型请求。');}
   catch(e){handle(e);await fusionPlanRefresh();}
  });
  return;
 }
 const messages={approve:'请写明实际核查到的内容与验收结果，不得直接将模型建议冒充完成。',
  retry:'旧失败记录会保留；再次执行可能消耗模型额度。必须写明复跑原因。'};
 const text=el('textarea',{class:'input',rows:4,maxlength:1200,
  'aria-label':kind==='approve'?'人工核验说明':'重新执行原因',
  placeholder:kind==='approve'?'核查了哪些 Run、文件和交付物？为何允许下一步？':'上一轮出了什么问题，为什么明确允许再次运行？'});
 const dlg=openDialog(kind==='approve'?'人工核验步骤':'确认重试失败步骤',
  el('div',{class:'stack'},el('p',{class:'fusion-hint'},messages[kind]),text),{wide:true});
 dlg.dialog.querySelector('.modal-shell').append(dlg.footer);
 const go=button(kind==='approve'?'确认步骤已核验':'记录原因并准备重试',async()=>{
  if(text.value.trim().length<8){toast('请填写至少8个字的检查记录',true);return;}
  go.disabled=true;
  try{
   await api(endpoint,{method:'POST',body:kind==='approve'?{note:text.value.trim()}:{reason:text.value.trim()}});
   dlg.close();await fusionPlanRefresh();
   toast(kind==='approve'?'此步骤已由管理员核验；并不自动发布团队知识。':'失败步骤已重置为待开始，不会自动发起模型调用。');
  }catch(e){handle(e);go.disabled=false;}
 },{class:'primary'});
 dlg.footer.append(button('取消',()=>dlg.close(),{class:'ghost'}),go);
}
function fusionRenderPlan(root,plan,tid){
 const container=root.closest('.fusion-card');
 const caption=container?.querySelector('[data-fusion-plan-caption]');
 root.replaceChildren();
 if(caption)caption.textContent=plan.status==='missing'?'未创建':(plan.status==='completed'?'已核验完成':plan.steps.filter(s=>s.status==='accepted').length+'/'+plan.steps.length+' 步完成');
 if(plan.status==='missing'){
  root.append(el('p',{class:'fusion-hint'},'为复杂工作建立明确的执行步骤，每次模型执行和人工核验都附着在当前任务。'));
  if(fusionSafeOwner())root.append(button('制定执行计划',()=>fusionPlanDialog(),{class:'small primary',icon:'plus'}));
  return;
 }
 root.append(el('div',{class:'fusion-plan-meta'},el('strong',{},plan.title),
  el('small',{},'计划 v'+plan.revision+' · '+plan.steps.length+' 步 · '+(plan.status==='completed'?'全部已核验':'等待逐步执行'))));
 if(plan.description)root.append(el('p',{class:'fusion-hint'},plan.description));
 const allPending=plan.steps.every(s=>s.status==='pending');
 if(fusionSafeOwner()&&allPending)
  root.append(button('编辑计划',()=>fusionPlanDialog(plan),{class:'small ghost',icon:'edit'}));
 for(let i=0;i<plan.steps.length;i++){
  const step=plan.steps[i],status=step.effective_status||step.status;
  const previousReady=i===0||plan.steps.slice(0,i).every(x=>x.status==='accepted');
  const card=el('section',{class:'fusion-flow-item fusion-planned-step'},
   el('div',{class:'fusion-flow-top'},
    el('span',{class:'fusion-plan-stepnum'},String(i+1)),
    el('strong',{},step.title),
    el('span',{class:'grow'}),
    badge(fusionPlanLabels[status]||status)),
   el('p',{class:'fusion-flow-request'},step.instruction),
   el('small',{class:'fusion-hint'},step.kind==='agent'
    ?('AI · '+fusionName(step.agent_id)+' · Agent配置 v'+step.agent_revision)
    :'真人审核（不自动发布知识）'),
   el('div',{class:'fusion-flow-actions row wrap'}));
  const actions=card.querySelector('.fusion-flow-actions');
  if(step.run_id){
   actions.append(button('查看 Run',()=>openTrace(step.run_id),{class:'small ghost'}));
   if(step.known_total_tokens!=null)actions.append(el('small',{class:'fusion-hint'},'已知累计 '+step.known_total_tokens+' token'));
  }
  if(step.review_note)actions.append(el('small',{class:'fusion-hint'},'人工记录：'+step.review_note));
  if(fusionSafeOwner()&&previousReady){
   if(step.kind==='agent'&&step.status==='pending')
    actions.append(button('启动员工执行',()=>fusionTriggerPlan(tid,step.id,'start'),{class:'small primary'}));
   if(status==='needs_review'||(step.kind==='review'&&step.status==='pending'))
    actions.append(button('人工核验',()=>fusionTriggerPlan(tid,step.id,'approve'),{class:'small primary'}));
   if(status==='blocked')
    actions.append(button('明确重试',()=>fusionTriggerPlan(tid,step.id,'retry'),{class:'small ghost'}));
   if(status==='dispatching')
    actions.append(button('人工核对发送状态',()=>fusionTriggerPlan(tid,step.id,'reconcile'),{class:'small ghost'}));
  }else if(!previousReady)actions.append(el('small',{class:'fusion-hint'},'前面的步骤尚未核验完成'));
  root.append(card);
 }
 root.append(el('p',{class:'fusion-hint'},'⚑ 当前为有界的线性流程；不会自动开始下一步，也不会自行将知识发布到公司。复杂分支 DAG 仍是后续阶段。'));
}
const fusionOriginalLoadPanels= fusionLoadPanels;
fusionLoadPanels=async function(panel,tid,generation){
 await fusionOriginalLoadPanels(panel,tid,generation);
 const host=panel?.querySelector('[data-fusion-plan]');
 if(host)await fusionLoadPlan(host,tid,generation);
};
const fusionOriginalTaskPanel=taskContextPanel;
taskContextPanel=function(){
 const panel=fusionOriginalTaskPanel();
 if(!state.task)return panel;
 const root=panel.querySelector('.fusion-panel-wrap');
 if(root){
  const plan=el('details',{class:'fusion-card'},
   el('summary',{},icon('plan',15),el('strong',{},'任务执行计划'),
    el('small',{'data-fusion-plan-caption':''},'读取计划'),icon('chevron',14)),
   el('div',{class:'fusion-card-body','data-fusion-plan':''},
    el('p',{class:'fusion-hint'},'正在读取执行步骤…')));
  root.insertBefore(plan,root.querySelector('.fusion-card:nth-of-type(2)'));
 }
 return panel;
};

// M4 responsiveness: no context/workflow fetch until the member opens that panel.
function fusionVisibleCurrent(panel,tid,generation){
 return !!panel?.isConnected&&fusionTaskCurrent(tid,generation);
}
fusionLoadPanels=async function(panel,tid,generation){
 if(!fusionVisibleCurrent(panel,tid,generation))return;
 const tasks=[];
 const summary=panel.querySelector('.fusion-card:has([data-fusion-summary])');
 if(summary?.open){
  const body=summary.querySelector('[data-fusion-summary]');
  tasks.push(api('/tasks/'+tid+'/context-summary').then(data=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&summary.open)fusionRenderSummary(body,data,tid);
  }).catch(e=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&summary.open)
    body.replaceChildren(el('p',{class:'form-error'},'读取历史来源失败，可关闭后重新展开。'));
  }));
 }
 const workflow=panel.querySelector('.fusion-card:has([data-fusion-workflow])');
 if(workflow?.open){
  const body=workflow.querySelector('[data-fusion-workflow]');
  tasks.push(Promise.all([api('/tasks/'+tid+'/workflow'),api('/tasks/'+tid+'/handoffs')]).then(([data,handoffs])=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&workflow.open)
    fusionRenderWorkflow(body,data,handoffs.items||[],tid);
  }).catch(e=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&workflow.open)
    body.replaceChildren(el('p',{class:'form-error'},'读取员工接力失败，可重新展开查看。'));
  }));
 }
 const plan=panel.querySelector('.fusion-card:has([data-fusion-plan])');
 if(plan?.open){
  const body=plan.querySelector('[data-fusion-plan]');
  tasks.push(api(fusionPlanUrl(tid)).then(data=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&plan.open)
    fusionRenderPlan(body,data,tid);
  }).catch(e=>{
   if(fusionVisibleCurrent(panel,tid,generation)&&plan.open)
    body.replaceChildren(el('p',{class:'form-error'},'读取执行计划失败，请刷新重试。'));
  }));
 }
 await Promise.all(tasks);
};
const fusionTaskPanelBeforeLazy=taskContextPanel;
taskContextPanel=function(){
 const panel=fusionTaskPanelBeforeLazy();
 if(state.task){
  const tid=state.task.id,generation=state.generation;
  for(const detail of panel.querySelectorAll('details.fusion-card')){
   detail.addEventListener('toggle',()=>{
    if(detail.open)fusionLoadPanels(panel,tid,generation).catch(()=>{});
   });
  }
 }
 return panel;
};

// Gongzhi Evidence Flow: task-bound provenance view, independently implemented.
// Queries happen ONLY when the member expands this task's panel. Stored rows
// are evidence; model text is never displayed as a verified company decision.
const evidenceFlowText={
 message:'讨论',run:'执行',document:'项目资料',review_step:'人工审核',
 handoff:'员工接力',published_knowledge:'团队知识',task:'当前任务'
};
const evidenceFlowStateText={
 recorded_not_verified:'历史记录',execution_record_not_adoption:'已记录运行',
 project_adopted:'项目已采用',not_adopted:'尚未采用',
 human_accepted_step:'真人已核验',not_human_accepted:'等待核验',
 operator_authorized:'已批准交接',pending:'待审批',
 explicitly_published_snapshot:'公司已发布'
};
function renderEvidenceFlow(container,data,taskId){
 container.replaceChildren();
 if(data.scope!=='task'||data.task_id!==taskId){
  container.append(el('p',{class:'form-error'},'证据范围异常，请刷新任务后重试'));return;
 }
 const caption=container.closest('.fusion-card')?.querySelector('[data-evidence-count]');
 if(caption)caption.textContent='讨论 '+(data.counts?.messages||0)+' · 审核 '+(data.counts?.workflow_steps||0);
 const docs=(data.nodes||[]).filter(x=>x.type==='document');
 const publications=(data.nodes||[]).filter(x=>x.type==='published_knowledge');
 const approvals=(data.nodes||[]).filter(x=>x.type==='review_step'&&x.approval_recorded);
 const messages=(data.nodes||[]).filter(x=>x.type==='message');
 const runs=(data.nodes||[]).filter(x=>x.type==='run');
 const blocks=[
  {label:'① 原始讨论',count:data.counts?.messages||0,note:'真人与 AI 原话保存在同一任务，内容哈希可回查。'},
  {label:'② Agent 执行',count:data.counts?.runs||0,note:'只有持久化 Run 和真实回复才展示；模型声称完成并非已验收。'},
  {label:'③ 人工核验',count:approvals.length,note:'管理员已审查并记录审批；这是人类采纳行为，不等于外部事实一定正确。'},
  {label:'④ 项目资料',count:data.counts?.documents||0,note:'文件按项目保存，采用状态与版本独立管理。'},
  {label:'⑤ 团队公开知识',count:data.counts?.publications||0,note:'仅展示明确发布且当前有效的公司知识快照。'}
 ];
 const flow=el('div',{class:'evidence-flow-stages'});
 for(const stage of blocks)
  flow.append(el('div',{class:'evidence-flow-stage'},
   el('div',{class:'row spread'},el('strong',{},stage.label),
    el('span',{class:'evidence-flow-number'},stage.count)),
   el('small',{},stage.note)));
 container.append(flow);
 if(data.partial)container.append(el('p',{class:'evidence-flow-alert'},
  '较长任务：仅展示最近部分来源节点。全量历史仍保存在数据库，不能把图视作完整记录。'));
 const trace=el('details',{class:'evidence-flow-details'},
  el('summary',{},'可核对的来源节点 · '+(data.nodes?.length||0)+' 项'),
  el('div',{class:'evidence-flow-details-list'}));
 const body=trace.querySelector('.evidence-flow-details-list');
 const selected=[...publications,...approvals,...docs,...runs,...messages.slice(0,12)];
 const max=40;
 for(const node of selected.slice(0,max)){
  const label=evidenceFlowText[node.type]||node.type;
  let title=node.title||node.speaker||node.id;
  if(node.type==='message')title='消息 #'+node.seq+' · '+(node.speaker||'');
  if(node.type==='run')title='Run '+node.id.slice(4,19);
  if(node.type==='review_step')title=node.title||'流程审批';
  const status=evidenceFlowStateText[node.source_state]||node.source_state||'';
  const row=el('div',{class:'evidence-flow-item'},
   el('span',{class:'evidence-flow-kind'},label),
   el('div',{class:'evidence-flow-description'},
    el('strong',{},title),
    el('small',{},status+' · '+node.id.slice(0,35))));
  if(node.type==='run'&&typeof openTrace==='function'){
   row.append(button('Trace',()=>openTrace(node.id.slice(4)),{class:'small ghost'}));
  }
  body.append(row);
 }
 if(selected.length>max)body.append(el('small',{class:'fusion-hint'},'还有来源可通过任务消息或资料页继续查看。'));
 container.append(trace);
 const relations=el('details',{class:'evidence-flow-details'},
  el('summary',{},'来源关系 · '+(data.edges?.length||0)+' 条'),
  el('div',{class:'evidence-flow-details-list'}));
 const table=relations.querySelector('.evidence-flow-details-list');
 for(const item of (data.edges||[]).slice(0,32)){
  table.append(el('div',{class:'evidence-flow-relation'},
   el('code',{},item.from.slice(0,22)),el('span',{},' → '+item.relation+' → '),
   el('code',{},item.to.slice(0,22))));
 }
 if((data.edges?.length||0)>32)table.append(el('small',{class:'fusion-hint'},'仅展示部分关系，完整图仍由后台按当前权限返回。'));
 container.append(relations,
  el('p',{class:'fusion-hint'},'证据依据是数据库记录和项目 ACL；不使用 AI 猜测关系。权限撤回、来源变更后的下一次请求将重新校验。'));
}
const evidenceFlowOriginalTaskPanel=taskContextPanel;
taskContextPanel=function(){
 const panel=evidenceFlowOriginalTaskPanel();
 if(!state.task)return panel;
 const root=panel.querySelector('.fusion-panel-wrap');
 if(!root)return panel;
 const taskId=state.task.id,generation=state.generation;
 const detail=el('details',{class:'fusion-card evidence-flow-card'},
  el('summary',{},icon('files',15),el('strong',{},'知识流转与证据'),
   el('small',{'data-evidence-count':''},'按需读取'),icon('chevron',14)),
  el('div',{class:'fusion-card-body','data-evidence-flow':''},
   el('p',{class:'fusion-hint'},'展开后按当前任务和权限读取真实来源。')));
 const flowbody=detail.querySelector('[data-evidence-flow]');
 const load=async()=>{
  if(!detail.isConnected || !detail.open || state.task?.id!==taskId || state.generation!==generation)return;
  flowbody.replaceChildren(el('p',{class:'fusion-hint'},'核验来源、审批与公司发布记录…'));
  try{
   const info=await api('/tasks/'+taskId+'/evidence-graph');
   if(detail.isConnected && detail.open && state.task?.id===taskId && state.generation===generation)
    renderEvidenceFlow(flowbody,info,taskId);
  }catch(e){
   if(detail.isConnected && detail.open && state.task?.id===taskId && state.generation===generation)
    flowbody.replaceChildren(el('p',{class:'form-error'},'读取证据失败，请检查项目权限后重新展开。'));
  }
 };
 detail.addEventListener('toggle',()=>{if(detail.open)load();});
 root.append(detail);
 return panel;
};

// Original knowledge provenance graph UI for Gongzhi.
// This visualizes only backend-verified edges; an LLM never invents relationships.
const evidenceGraphLabels={
 ...EVIDENCE_TYPE_LABELS,
};
const evidenceStates={
 recorded_not_verified:'有记录，未独立核验',
 execution_record_not_adoption:'Run已记录，未采用',
 project_adopted:'项目已人工采用',
 not_adopted:'尚未被采用',
 original_upload_record:'真实上传来源',
 trace_event_recorded_not_independent_verification:'Trace事件已记录',
 human_accepted_step:'真人确认此步骤',
 not_human_accepted:'未完成真人验收',
 operator_authorized:'人工批准交接',
 pending:'仍待授权',
 explicitly_published_snapshot:'团队已明确发布',
 source_document_accessible_not_automatically_published:'来源文件可读，非自动公开',
 original_project_task:'来源任务',
};
function evidenceSvg(tag,attrs={},textValue){
 const node=document.createElementNS('http://www.w3.org/2000/svg',tag);
 for(const [k,v] of Object.entries(attrs)) if(v!==undefined&&v!==null)node.setAttribute(k,String(v));
 if(textValue!==undefined)node.textContent=String(textValue);
 return node;
}
function evidenceTrim(str,n=19){
 const chars=Array.from(String(str||''));
 return chars.length<=n?chars.join(''):chars.slice(0,n-1).join('')+'…';
}
function evidenceVisibleLabel(item){
 if(item.type==='message')return '消息 #'+(item.seq??'?')+' · '+(item.speaker||'成员');
 if(item.type==='run')return 'Run '+item.id.slice(4,16);
 if(item.type==='tool_event')return (item.event||'工具事件')+' #'+(item.trace_seq||0);
 return item.title||item.speaker||item.id;
}
function evidenceTone(type){
 return {
  workspace:'var(--accent)',project:'var(--accent)',task:'var(--accent)',
  message:'var(--muted)',run:'var(--accent)',handoff:'var(--accent)',
  tool_event:'var(--muted)',source_upload:'var(--muted)',
  document:'var(--accent)',review_step:'var(--accent)',
  published_knowledge:'var(--accent)'
 }[type]||'var(--muted)';
}
function evidenceInspector(panel,item,graph,dialog){
 panel.replaceChildren();
 if(!item){
  panel.append(el('p',{class:'fusion-hint'},'选择任意节点查看来源、审批与版本信息。'));
  return;
 }
 const name=evidenceVisibleLabel(item);
 panel.append(el('div',{class:'evidence-map-inspect-head'},badge(evidenceGraphLabels[item.type]||item.type),
  el('strong',{},name)));
 const rows=[
  ['状态',evidenceStates[item.source_state]||item.source_state||item.status||'有记录'],
  ['可见范围',item.audience||item.scope||graph.audience||'任务范围'],
  ['版本',item.revision!=null?'v'+item.revision:null],
  ['来源可读',item.source_visibility==='restricted'?'无来源项目访问权':item.source_visibility==='authorized'?'当前有来源项目权限':null],
  ['消息序号',item.seq!=null?'#'+item.seq:null],
  ['核验人',item.approved_by!=null?'成员 #'+item.approved_by:null],
  ['发布人',item.published_by!=null?'成员 #'+item.published_by:null],
  ['来源文件版本',item.published_source_revision!=null?'v'+item.published_source_revision:null],
  ['当前与发布版本一致',item.current_matches_published_revision===false?'否（原件后来已变化）':item.current_matches_published_revision===true?'是':null],
  ['来源正文哈希',item.content_sha256||item.body_sha256||item.review_note_sha256||null],
  ['敏感度',item.sensitivity_status==='unclassified'?'尚无分类标签，不代表公开/安全':null]
 ].filter(([,v])=>v!==null&&v!==undefined);
 for(const [name,value] of rows)panel.append(el('div',{class:'evidence-map-inspect-row'},
  el('span',{},name),el('strong',{title:String(value)},String(value))));
 if(item.source_visibility==='restricted')panel.append(el('p',{class:'evidence-map-source-restricted'},
  '你可以阅读明确发布的公司快照，但没有来源项目的权限。不会显示原始文件、任务名称及其ID。'));
 const raw=item.id.slice(item.id.indexOf(':')+1);
 const actions=el('div',{class:'row wrap'});
 if(item.type==='run'&&graph.task_id){
  actions.append(button('查看执行 Trace',()=>{dialog.close();openTrace(raw);},{class:'small ghost',icon:'plan'}));
 }
 if(item.type==='published_knowledge'){
  actions.append(button('阅读已发布快照',()=>{dialog.close();openKnowledge({id:raw,kind:'company'}).catch(handle);},{class:'small ghost',icon:'files'}));
 }
 if(item.type==='task'&&item.project_id){
  actions.append(button('回到来源任务',()=>{dialog.close();openTask(raw,item.project_id).catch(handle);},{class:'small ghost',icon:'tasks'}));
 }
 if(item.type==='document'&&item.project_id){
  actions.append(button('查看来源资料',async()=>{
   dialog.close();
   try{
    if(!state.project||state.project.id!==item.project_id)await selectProject(item.project_id);
    await documentDialog(raw);
   }catch(e){handle(e);}
  },{class:'small ghost',icon:'files'}));
 }
 actions.append(button('复制来源编号',async()=>{
  try{await navigator.clipboard.writeText(raw);toast('来源编号已复制');}
  catch(e){toast('复制失败，请检查浏览器权限',true);}
 },{class:'small ghost',icon:'clip'}));
 panel.append(actions);
}
function buildEvidenceCanvas(host,graph,filter,inspect,dialog){
 host.replaceChildren();
 const projected=evidenceGraphProjection(graph,{filter});
 const byId=new Map(projected.nodes.map(n=>[n.id,n]));
 if(!projected.nodes.length){
  host.append(el('p',{class:'fusion-hint'},'当前筛选没有可展示的来源对象。'));return;
 }
 const frame=el('div',{class:'evidence-map-scroll',tabindex:0,'aria-label':'可横向滚动的任务来源关系图'});
 const svg=evidenceSvg('svg',{viewBox:'0 0 '+projected.width+' '+projected.height,
  width:projected.width,height:projected.height,'aria-label':'真实来源、执行、审核和发布关系图',
  role:'group',class:'evidence-map-svg'});
 const defs=evidenceSvg('defs');
 const marker=evidenceSvg('marker',{id:'evidence-flow-arrow',markerWidth:9,markerHeight:9,refX:7,refY:4.5,orient:'auto'});
 marker.append(evidenceSvg('path',{d:'M1 1 L7 4.5 L1 8 z',fill:'var(--muted)'}));
 defs.append(marker);svg.append(defs);
 for(const type of projected.types){
  const item=projected.nodes.find(n=>n.type===type);
  if(!item)continue;
  const x=item.layout_x;
  svg.append(evidenceSvg('rect',{x:x-8,y:37,width:180,height:projected.height-51,rx:13,
   fill:'var(--surface)',stroke:'var(--line)','stroke-width':0.75,opacity:.7}));
  svg.append(evidenceSvg('text',{x:x+2,y:24,'font-size':12,'font-weight':650,fill:'var(--text)'},
    evidenceGraphLabels[type]||type));
  const extra=projected.displayCounts[type];
  svg.append(evidenceSvg('text',{x:x+154,y:24,'font-size':10,'text-anchor':'end',fill:'var(--muted)'},
    extra.visible===extra.total?String(extra.total):extra.visible+'/'+extra.total));
 }
 const relationNodes=[];
 for(const e of projected.edges){
  const start=byId.get(e.from),end=byId.get(e.to);
  if(!start||!end)continue;
  const x1=start.layout_x+(end.layout_col>start.layout_col?163:0);
  const x2=end.layout_x+(end.layout_col<=start.layout_col?163:0);
  const y1=start.layout_y, y2=end.layout_y;
  const diff=Math.max(38,Math.abs(x2-x1)*.42);
  const sgn=x2>=x1?1:-1;
  const d='M '+x1+' '+y1+' C '+(x1+sgn*diff)+' '+y1+', '+(x2-sgn*diff)+' '+y2+', '+x2+' '+y2;
  const isContainer=/^(?:contains_|has_|project_contains_|workspace_published)/.test(e.relation);
  const line=evidenceSvg('path',{d,fill:'none',stroke:'var(--muted)',
   'stroke-width':isContainer?1:1.6,'stroke-opacity':isContainer?.21:.56,
   'marker-end':'url(#evidence-flow-arrow)',
   'data-source':e.from,'data-target':e.to});
  relationNodes.push(line);svg.append(line);
 }
 const groupNodes=[];
 function selectNode(n){
  evidenceInspector(inspect,n,graph,dialog);
  for(const {id,group} of groupNodes)group.classList.toggle('is-selected',id===n.id);
  for(const line of relationNodes){
   const connected=line.dataset.source===n.id||line.dataset.target===n.id;
   line.setAttribute('stroke-opacity',connected?.96:.1);
   line.setAttribute('stroke-width',connected?2.5:1);
  }
 }
 for(const n of projected.nodes){
  const group=evidenceSvg('g',{class:'evidence-map-node',role:'button',tabindex:0,
    'aria-label':(evidenceGraphLabels[n.type]||n.type)+'：'+evidenceVisibleLabel(n),
    transform:'translate('+n.layout_x+','+(n.layout_y-25)+')'});
  group.append(evidenceSvg('rect',{width:163,height:51,rx:9,fill:'var(--sidebar)',
    stroke:evidenceTone(n.type),'stroke-width':1.25}));
  group.append(evidenceSvg('text',{x:10,y:16,'font-size':9,fill:'var(--muted)',class:'evidence-map-node-kind'},
    evidenceGraphLabels[n.type]||n.type));
  group.append(evidenceSvg('text',{x:10,y:35,'font-size':11,'font-weight':650,fill:'var(--text)'},
    evidenceTrim(evidenceVisibleLabel(n),19)));
  group.append(evidenceSvg('title',{},evidenceVisibleLabel(n)+' · '+(n.source_state||'')));
  group.addEventListener('click',()=>selectNode(n));
  group.addEventListener('keydown',evt=>{
   if(evt.key==='Enter'||evt.key===' '){evt.preventDefault();selectNode(n);}
  });
  svg.append(group);groupNodes.push({id:n.id,group});
 }
 frame.append(svg);
 host.append(frame,el('div',{class:'evidence-map-footnote'},
  el('small',{},'节点 '+projected.nodes.length+'/'+projected.totalNodes+' · 显示关系 '+projected.edges.length+'/'+projected.totalEdges),
  projected.partial&&el('small',{class:'evidence-map-truncated'},'内容较多：这里只展示部分节点。完整来源应通过任务记录核对。')));
 const first=projected.nodes.find(n=>n.type==='published_knowledge')
  || projected.nodes.find(n=>n.type==='review_step'&&n.approval_recorded)
  || projected.nodes[0];
 selectNode(first);
}
function openKnowledgeGraph(graph,title){
 // Rejected/partial/missing data should not be filled in with inferred edges.
 if(!graph||!Array.isArray(graph.nodes)||!Array.isArray(graph.edges)){
  toast('当前没有可核对的关系数据',true);return;
 }
 const inspect=el('aside',{class:'evidence-map-inspector','aria-label':'选中来源的核查详情'});
 const stage=el('div',{class:'evidence-map-graph'});
 const choice=el('select',{class:'input','aria-label':'关系显示范围'},[
  el('option',{value:'all'},'全部关系'),
  el('option',{value:'origin'},'只看源文件与执行'),
  el('option',{value:'reviewed'},'只看审批与已发布知识')
 ]);
 const expl=el('p',{class:'evidence-map-intro'},
  graph.audience==='workspace'
   ?'公司共享知识只展示已正式发布的快照；原始项目来源只有具备项目权限的人可以展开。'
   :'任务知识关系仅展示数据库真实消息、来源文件、Run、人工验收和发布事件。模型文本不能伪造边。');
 const content=el('div',{class:'evidence-map-modal'},
  expl,el('div',{class:'evidence-map-toolbar'},el('label',{},'视图',choice),
   el('small',{},graph.partial?'数据已截断，按需核查原始记录':'当前可见关系已加载')),
  el('div',{class:'evidence-map-panels'},stage,inspect));
 const dlg=openDialog(title,content,{wide:true});
 const draw=()=>buildEvidenceCanvas(stage,graph,choice.value,inspect,dlg);
 choice.addEventListener('change',draw);
 draw();
}
const evidenceFlowRenderBeforeGraph=renderEvidenceFlow;
renderEvidenceFlow=function(container,data,tid){
 evidenceFlowRenderBeforeGraph(container,data,tid);
 const action=button('查看完整知识关系图',async()=>{
  action.disabled=true;
  try{
   const refreshed=await api('/tasks/'+tid+'/evidence-graph');
   if(state.task?.id!==tid)return;
   openKnowledgeGraph(refreshed,'任务知识图谱 · '+(state.task.title||'当前任务'));
  }catch(e){handle(e);}finally{action.disabled=false;}
 },{class:'small primary',icon:'plan'});
 container.insertBefore(el('div',{class:'evidence-map-cta'},
  el('div',{},el('strong',{},'这项任务的知识从哪里来？'),
  el('small',{},'查看资料、真人讨论、真实 Run、人工核验与已发布快照的关系')),
  action),container.firstChild);
};
const renderCompanyKnowledgeBeforeGraph=renderCompanyKnowledge;
renderCompanyKnowledge=function(container,data){
 renderCompanyKnowledgeBeforeGraph(container,data);
 const workspace=state.workspace;
 if(!workspace)return;
 const banner=el('section',{class:'evidence-map-hero'},
  el('div',{class:'evidence-map-hero-content'},
   el('strong',{},'团队知识图谱 · 只展示真实授权范围'),
   el('p',{},'哪些知识已成为公司共享资产？哪些仍只属于原项目？查看来源、修订与共享边界。')),
  button('查看团队知识图谱',async()=>{
   const id=workspace.id;
   try{
    const view=await api('/workspaces/'+id+'/knowledge-graph');
    if(state.workspace?.id!==id)return;
    openKnowledgeGraph(view,'团队知识图谱 · '+(workspace.name||'当前团队'));
   }catch(e){handle(e);}
  },{class:'primary',icon:'files'}));
 container.insertBefore(banner,container.firstChild);
};

bootstrap();
