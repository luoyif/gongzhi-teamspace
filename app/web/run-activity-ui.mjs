// Human-readable observed execution only; never model private reasoning.
export const terminalRun = s => !!s && !['queued','running'].includes(s);
export function toolLabel(name='') {
 const names={task_conversation_read:'回看本任务对话',project_files_list:'浏览项目目录',project_file_read:'读取项目文件',project_read_document:'读取资料',project_search:'检索项目资料',platform_overview:'核对项目状态',task_execution_history:'查看已完成步骤',read_file:'读取技能文件',ls:'列出技能目录',glob:'查找技能文件',grep:'搜索技能内容',artifact_section_save:'分节保存报告',tool_result_read:'回读已取得的证据',artifact_save:'保存产物',project_memory_save:'整理项目记忆',knowledge_save:'保存知识草稿',office_docx_create:'生成 Word 文档',code_bundle_save:'保存代码包',python_syntax_check:'检查 Python 语法',task_create:'创建任务',task_update:'更新任务',calendar_create:'创建日程',calendar_update:'修改日程',calendar_cancel:'取消日程',project_plan_update:'更新项目规划'};
 return names[name] || (name.endsWith('_web_search_exa')?'联网检索':name.endsWith('_web_fetch_exa')?'阅读网页':name.includes('microsoft_docs')?'查阅微软文档':name);
}
export function summarizeActivity(events=[]) {
 const tools=new Map();let step=0,modelMs=0,mode=null,finalizing=false,conversation=null;
 for(const e of events){const p=e.payload||{};
  if(e.event==='model.start')step=Math.max(step,Number(p.step)||0);
  if(e.event==='model.end')modelMs+=Number(p.elapsed_ms)||0;
  if(e.event==='input.conversation')conversation=p;
  if(e.event==='permission.changed')mode=p.permission_mode;
  if(e.event==='budget.finalizing')finalizing=true;
  if(e.event==='tool.request')tools.set(e.span_id,{id:e.span_id,name:p.name,label:toolLabel(p.name),args:p.arguments||{},status:'running',seq:e.seq});
  if(e.event==='approval.required'){const t=tools.get(e.parent_span);if(t){t.status='waiting';t.approval=p.id;}}
  if(e.event==='approval.auto'){const t=tools.get(e.parent_span);if(t)t.automatic=true;}
  if(['tool.result','tool.error','tool.denied'].includes(e.event)){const t=tools.get(e.span_id)||{id:e.span_id,name:p.name,label:toolLabel(p.name),seq:e.seq};Object.assign(t,{status:e.event==='tool.denied'?'denied':e.event==='tool.error'||p.status==='error'?'error':'done',receipt:p.receipt||{},preview:p.preview||p.reason||p.error_type||'',elapsedMs:p.elapsed_ms,chars:p.content_chars});tools.set(e.span_id,t);}
 }
 return {step,modelMs,mode,finalizing,conversation,tools:[...tools.values()],completed:[...tools.values()].filter(t=>t.status==='done').length};
}
export function mergeActivity(old=[],incoming=[]) {
 const map=new Map(old.map(e=>[e.seq,e]));for(const e of incoming)if(Number.isInteger(e.seq))map.set(e.seq,e);
 return [...map.values()].sort((a,b)=>a.seq-b.seq).slice(-2000);
}
export function compactToolDetail(t) {
 const a=t.args||{},r=t.receipt||{};
 const label=a.path||a.file_path||a.filename||a.document_id||a.query||r.path||r.title||r.id||'';
 if(['project_file_read','project_read_document','tool_result_read'].includes(t.name)){
  const start=Number.isInteger(a.offset)?a.offset:0,end=Number.isInteger(r.next_offset)?r.next_offset:(r.has_more===false&&Number.isInteger(r.total_characters)?r.total_characters:null);
  return label+' · '+(end!==null?'字符 '+start+'–'+end:'起点 '+start+(Number.isInteger(a.length)?' / 请求 '+a.length+' 字符':''));
 }
 return label;
}
