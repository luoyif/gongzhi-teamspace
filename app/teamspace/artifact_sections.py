"""Small approved sections for large reports. Retry-safe across runs in one task."""
import hashlib,json,re
from .store import Problem,dump,now,require_text

def build(ops):
 async def artifact_section_save(filename:str,section_id:str,content:str,complete:bool=False,expected_revision:int|None=None)->str:
  """Save ONE short section (<=3500 chars) of a long Markdown report. Same task+filename+section_id is idempotent across runs; never overwrite raw/user files. Use distinct section_id for each next section. complete=true marks the assembled draft ready for human review, not adopted. Existing receipts tell which sections already exist."""
  if not isinstance(filename,str) or not re.fullmatch(r'[\w .-]{1,110}\.md',filename) or '..' in filename:raise Problem(422,'分节报告仅支持简单Markdown文件名')
  if not isinstance(section_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',section_id):raise Problem(422,'section_id需为稳定英文/数字标识')
  content=require_text(content,'章节正文',3500,False)
  if type(complete) is not bool:raise Problem(422,'complete必须为布尔值')
  if expected_revision is not None and (type(expected_revision) is not int or expected_revision<1):raise Problem(422,'版本号无效')
  digest=hashlib.sha256(content.encode()).hexdigest()
  def apply(c):
   row=c.execute("SELECT * FROM team_objects WHERE project_id=? AND kind='document' AND title=? AND status='ready' AND json_extract(data_json,'$.task_id')=? ORDER BY created_at DESC LIMIT 1",(ops.p,filename,ops.task_id)).fetchone()
   if row and ops.store.deleted(c,row['id']):row=None
   if row:
    data=json.loads(row['data_json'])
    if data.get('origin')!='agent_sectioned_artifact':raise Problem(409,'同名文件已存在且不是本工具草稿；请引用它或使用新的文件名，不重复创建')
    sections=data.get('sections',[]);previous=next((x for x in sections if x['section_id']==section_id),None)
    if previous:
     if previous['sha256']!=digest:raise Problem(409,'此章节已保存且内容不同；不能用重试覆盖，请核对原文')
     return {'id':row['id'],'title':filename,'revision':row['revision'],'duplicate':True,'section_id':section_id,'sections':[x['section_id'] for x in sections],'draft_complete':data.get('draft_complete',False),'status':'ready'}
    if data.get('draft_complete'):raise Problem(409,'报告已封存为待验收稿；新内容请保存新报告')
    if expected_revision is not None and expected_revision!=row['revision']:raise Problem(409,'报告版本已变化，请回读')
    body=row['body'].rstrip()+'\n\n'+content;oid=row['id'];revision=row['revision']+1
    if len(sections)>=60 or len(body)>150000:raise Problem(422,'报告已超过分节上限，请另存下一卷')
   else:data={**ops.provenance(),'origin':'agent_sectioned_artifact','document_kind':'file','filename':filename};sections=[];body=content;oid=None;revision=1
   sections.append({'section_id':section_id,'sha256':digest,'characters':len(content),'run_id':ops.run_id})
   raw=body.encode();sha=hashlib.sha256(raw).hexdigest();rel='blobs/'+sha;target=ops.store.data_dir/rel
   if not target.exists():target.write_bytes(raw);target.chmod(0o600)
   data.update(sections=sections,draft_complete=complete,blob_path=rel,sha256=sha,bytes=len(raw),adopted=False)
   if oid:
    c.execute('INSERT OR IGNORE INTO team_history(object_id,revision,snapshot_json,created_at) VALUES(?,?,?,?)',(oid,row['revision'],dump(dict(row)),now()))
    c.execute('UPDATE team_objects SET body=?,data_json=?,revision=revision+1,updated_at=? WHERE id=?',(body,dump(data),now(),oid))
   else:oid=ops.store.put_object(c,ops.p,'document',filename,body,ops.actor,data,'ready')
   ops.store.index(c,oid,ops.p,[('分节报告 · '+('待验收' if complete else '尚未写完'),body)],filename)
   return {'id':oid,'title':filename,'revision':revision,'section_id':section_id,'sections':[x['section_id'] for x in sections],'draft_complete':complete,'status':'ready','adopted':False,'sha256':sha,'bytes':len(raw)}
  return ops.mutation('artifact_section_save',{'filename':filename,'section_id':section_id,'content':content,'complete':complete,'expected_revision':expected_revision},apply)
 return artifact_section_save
