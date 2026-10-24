"""Authenticated local avatars: stable assigned presets or sanitized image uploads."""
from __future__ import annotations
import base64,hashlib,io,json
from typing import Any
from fastapi import APIRouter,Depends,Body,Query
from octop.api.deps import current_user,get_server
from .store import Problem,now
router=APIRouter()
PRESETS={'human':['🙂','🦊','🐼','🐱','🐻','🐨','🐯','🦉','🐸','🐧','🐰','🦁'],'agent':['🤖','💻','🎨','🔬','📄','🧪','🧠','🛰️']}
SCHEMA='CREATE TABLE IF NOT EXISTS team_avatars(subject_type TEXT NOT NULL,subject_id TEXT NOT NULL,preset INTEGER,blob_path TEXT,revision INTEGER NOT NULL,updated_by INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(subject_type,subject_id))'
def ensure(store):
 if getattr(store,'_avatars_ready',False):return
 with store.schema_lock:
  if getattr(store,'_avatars_ready',False):return
  with store.connection() as c:c.execute(SCHEMA)
  store._avatars_ready=True

def authorize(store,registry,c,w,actor,kind,sid,write=False):
 membership=store.workspace_require(c,w,actor)
 if kind=='human':
  if not str(sid).isdigit() or not c.execute('SELECT 1 FROM team_workspace_members WHERE workspace_id=? AND user_id=?',(w,int(sid))).fetchone():raise Problem(404,'成员不可见')
  if write and str(actor)!=str(sid) and membership['role']!='owner':raise Problem(403,'只能设置自己的头像')
 elif kind=='agent':
  a=registry.get(sid,actor,'agent',c)
  if a['workspace_id']!=w:raise Problem(404,'员工不属于此团队')
  if write:registry.manage(c,w,actor)
 else:raise Problem(422,'头像主体无效')

def assigned(kind,sid):
 value=2166136261
 for ch in kind+':'+str(sid):value=((value^ord(ch))*16777619)&0xffffffff
 return value%len(PRESETS[kind])
def read_avatar(store,registry,w,actor,kind,sid):
 ensure(store)
 with store.connection() as c:
  authorize(store,registry,c,w,actor,kind,sid);row=c.execute('SELECT * FROM team_avatars WHERE subject_type=? AND subject_id=?',(kind,str(sid))).fetchone()
 data={'kind':kind,'id':str(sid),'preset':row['preset'] if row and row['preset'] is not None else assigned(kind,sid),'revision':row['revision'] if row else 0,'default_assigned':not bool(row)}
 data['emoji']=PRESETS[kind][data['preset']]
 if row and row['blob_path']:
  file=(store.data_dir/row['blob_path']).resolve();root=(store.data_dir/'avatars').resolve()
  if not file.is_relative_to(root):raise Problem(503,'头像路径异常')
  if file.is_file():data['image_data']='data:image/png;base64,'+base64.b64encode(file.read_bytes()).decode()
 return data

def sanitize_image(encoded):
 from PIL import Image,ImageOps,UnidentifiedImageError
 if not isinstance(encoded,str) or len(encoded)>3_000_000:raise Problem(422,'头像限2MB PNG/JPEG/WebP')
 try:
  raw=base64.b64decode(encoded,validate=True)
  if len(raw)>2*1024*1024:raise ValueError()
  with Image.open(io.BytesIO(raw)) as im:
   if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>12_000_000 or getattr(im,'n_frames',1)!=1:raise ValueError()
   im.load();im=ImageOps.exif_transpose(im);im=ImageOps.fit(im.convert('RGB'),(160,160));buf=io.BytesIO();im.save(buf,format='PNG',optimize=True);out=buf.getvalue()
   if len(out)>100000:raise ValueError()
   return out
 except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):raise Problem(422,'头像图片无效、过大或不支持；SVG和动画不能上传') from None

def save_avatar(store,registry,w,actor,kind,sid,body):
 ensure(store);preset=body.get('preset');raw=None
 if 'image_base64' in body:raw=sanitize_image(body['image_base64'])
 elif type(preset) is not int or not 0<=preset<len(PRESETS.get(kind,[])):raise Problem(422,'请选择有效头像')
 with store.connection(True) as c:
  authorize(store,registry,c,w,actor,kind,sid,True);row=c.execute('SELECT revision FROM team_avatars WHERE subject_type=? AND subject_id=?',(kind,str(sid))).fetchone();rev=row[0] if row else 0
  if type(body.get('expected_revision')) is not int or body['expected_revision']!=rev:raise Problem(409,'头像已更新，请刷新')
  relative=None
  if raw:
   folder=store.data_dir/'avatars';folder.mkdir(mode=0o700,exist_ok=True);relative='avatars/'+hashlib.sha256(raw).hexdigest()+'.png';path=store.data_dir/relative
   if not path.exists():path.write_bytes(raw);path.chmod(0o600)
  c.execute('INSERT INTO team_avatars VALUES(?,?,?,?,?,?,?) ON CONFLICT(subject_type,subject_id) DO UPDATE SET preset=excluded.preset,blob_path=excluded.blob_path,revision=excluded.revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at',(kind,str(sid),preset if raw is None else None,relative,rev+1,actor,now()))
 return read_avatar(store,registry,w,actor,kind,sid)

def services(server):
 from .integration import store_for
 from .platform_registry import PlatformRegistry
 s=store_for(server);return s,PlatformRegistry(s)
@router.get('/workspaces/{w}/avatars')
def avatars(w:str,subjects:str=Query('',max_length=8000),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s,r=services(server);out=[]
 for key in subjects.split(',')[:60]:
  if not key:continue
  kind,sep,sid=key.partition(':')
  if not sep:raise Problem(422,'头像查询格式无效')
  try:out.append(read_avatar(s,r,w,user.id,kind,sid))
  except Problem as e:
   if e.status!=404:raise
 return {'items':out,'presets':PRESETS}
@router.put('/workspaces/{w}/avatars/{kind}/{sid}')
def update(w:str,kind:str,sid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 s,r=services(server);return save_avatar(s,r,w,user.id,kind,sid,body)
