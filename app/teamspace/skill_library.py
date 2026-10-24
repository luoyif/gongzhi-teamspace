"""Import/export native SKILL.md packages without executing their code."""
from __future__ import annotations
import hashlib,io,json,re,zipfile
from pathlib import Path
from .store import Problem,dump


def native_catalog():
 import octop_harness
 from octop_harness.skills.catalog import _parse_skill_frontmatter
 root=Path(octop_harness.__file__).parent/'builtin'/'skills';items=[]
 for p in sorted(root.glob('*/**/SKILL.md')):
  if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):continue
  raw=p.read_text(encoding='utf8');meta,body=_parse_skill_frontmatter(raw)
  if not body.strip():continue
  relative=p.parent.relative_to(root).as_posix()
  items.append({'id':relative,'name':str(meta.get('name') or p.parent.name),'description':str(meta.get('description') or '')[:2000],'language':relative.split('/')[0],'sha256':hashlib.sha256(raw.encode()).hexdigest(),'root':p.parent,'markdown':raw,'body':body})
 return items


def ensure_file_table(registry):
 store=registry.store
 if getattr(store,'_skill_files_ready',False):return
 with store.schema_lock:
  if getattr(store,'_skill_files_ready',False):return
  with store.connection() as c:c.execute('CREATE TABLE IF NOT EXISTS team_skill_files(asset_id TEXT NOT NULL,relative_path TEXT NOT NULL,content BLOB NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(asset_id,relative_path))')
  store._skill_files_ready=True


def import_native(registry,p,actor,catalog_id):
 candidate=next((x for x in native_catalog() if x['id']==catalog_id),None)
 if not candidate:raise Problem(404,'内置技能不存在')
 files=[];total=0
 for f in candidate['root'].rglob('*'):
  if not f.is_file():continue
  if f.is_symlink() or not f.resolve().is_relative_to(candidate['root'].resolve()):raise Problem(422,'技能包包含符号链接，不导入')
  b=f.read_bytes();total+=len(b)
  if total>5*1024*1024 or len(files)>=150:raise Problem(422,'技能包超过导入限制')
  files.append((f.relative_to(candidate['root']).as_posix(),b,hashlib.sha256(b).hexdigest()))
 slug=re.sub('[^a-z0-9_-]','-',candidate['root'].name.lower())[:70]
 asset=registry.save(p,actor,'skill',{'name':candidate['name'][:80],'description':candidate['description'],'enabled':False,'data':{'slug':slug,'body':candidate['body'],'status':'draft'}},source={'kind':'octop_harness_builtin','catalog_id':catalog_id,'package_sha256':hashlib.sha256(dump([(n,h) for n,_,h in sorted(files)]).encode()).hexdigest(),'requires_review':True,'scripts_auto_executed':False})
 ensure_file_table(registry)
 with registry.store.connection(True) as c:
  c.executemany('INSERT INTO team_skill_files VALUES(?,?,?,?)',[(asset['id'],n,b,h) for n,b,h in files])
 return asset


def package_files(registry,asset):
 ensure_file_table(registry)
 import yaml
 header={'name':asset['data']['slug'],'description':asset['description'] or asset['name']}
 markdown='---\n'+yaml.safe_dump(header,allow_unicode=True,sort_keys=False)+'---\n\n'+asset['data']['body']+'\n'
 out={'SKILL.md':markdown.encode('utf8')}
 with registry.store.connection() as c:
  for row in c.execute('SELECT relative_path,content,sha256 FROM team_skill_files WHERE asset_id=?',(asset['id'],)):
   path=Path(row['relative_path']);b=bytes(row['content'])
   if path.is_absolute() or '..' in path.parts or '\\' in row['relative_path']:raise Problem(503,'技能包路径异常')
   if hashlib.sha256(b).hexdigest()!=row['sha256']:raise Problem(503,'技能包内容校验失败')
   if row['relative_path']!='SKILL.md':out[row['relative_path']]=b
 return out


def export_zip(registry,asset):
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for name,b in package_files(registry,asset).items():z.writestr(asset['data']['slug']+'/'+name,b)
  z.writestr(asset['data']['slug']+'/GONGZHI-PROVENANCE.json',dump({'id':asset['id'],'revision':asset['revision'],'source':asset['source'],'automatic_execution':False}))
 return buf.getvalue()
