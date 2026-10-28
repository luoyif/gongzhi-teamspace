"""The new avatar blobs must survive the existing private backup/restore workflow."""
from pathlib import Path
from types import SimpleNamespace as NS
import base64,contextlib,hashlib,importlib.util,io,json,sqlite3,tarfile,tempfile,unittest
from PIL import Image
from teamspace.workspace import WorkspaceStore
from teamspace.platform_registry import PlatformRegistry
from teamspace.avatars import save_avatar
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location('test12_'+name,ROOT/'deployment'/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class AvatarBackupTests(unittest.TestCase):
 def cycle(self,upload):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'data';root.mkdir();s=WorkspaceStore(root/'octop.db',root/'teamspace');actor=NS(id=1,username='backup_owner',display_name='备份验收',role='admin');w=s.create_workspace(actor,{'name':'Avatar backup fixture'})['id'];registry=PlatformRegistry(s);body={'expected_revision':0,'preset':3}
   if upload:
    buf=io.BytesIO();Image.new('RGB',(200,180)).save(buf,format='PNG');body={'expected_revision':0,'image_base64':base64.b64encode(buf.getvalue()).decode()}
   before=save_avatar(s,registry,w,1,'human','1',body)
   credentials=root/'credentials';credentials.mkdir(mode=0o700)
   secret=credentials/'siliconflow-asr.key';secret.write_text('sk-fixture-never-real',encoding='utf8');secret.chmod(0o600)
   with contextlib.redirect_stdout(io.StringIO()):archive=load('backup').backup(root,Path(td)/'backups');result=load('restore_check').restore(archive['path'],Path(td)/'restored')
   recovered=Path(result['restored_to']);self.assertEqual(result['sqlite_check'],'ok')
   restored_secret=recovered/'credentials'/'siliconflow-asr.key'
   self.assertEqual(restored_secret.read_text(encoding='utf8'),'sk-fixture-never-real')
   self.assertEqual(restored_secret.stat().st_mode & 0o077,0)
   with sqlite3.connect(recovered/'octop.db') as c:row=c.execute("SELECT preset,blob_path FROM team_avatars WHERE subject_type='human' AND subject_id='1'").fetchone()
   if upload:
    raw=(recovered/'teamspace'/row[1]).read_bytes();self.assertEqual(raw,base64.b64decode(before['image_data'].split(',')[1]));self.assertEqual(hashlib.sha256(raw).hexdigest(),Path(row[1]).stem)
   else:self.assertEqual(row,(3,None))
 def test_uploaded_avatar_and_metadata_restore_together(self):self.cycle(True)
 def test_preset_only_avatar_restores_without_fake_file(self):self.cycle(False)
 def test_wal_database_backup_is_closed_and_restorable(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'data';root.mkdir();s=WorkspaceStore(root/'octop.db',root/'teamspace')
   actor=NS(id=1,username='backup_owner',display_name='备份验收',role='admin')
   s.create_workspace(actor,{'name':'WAL backup fixture'})
   with contextlib.closing(sqlite3.connect(root/'octop.db')) as live:
    live.execute('PRAGMA journal_mode=WAL');live.execute('CREATE TABLE backup_marker (value TEXT)');live.execute("INSERT INTO backup_marker VALUES ('preserved')");live.commit()
    with contextlib.redirect_stdout(io.StringIO()):
     archive=load('backup').backup(root,Path(td)/'backups')
     result=load('restore_check').restore(archive['path'],Path(td)/'restored')
    with tarfile.open(archive['path']) as tar:
     names=tar.getnames();self.assertNotIn('data/octop.db-wal',names);self.assertNotIn('data/octop.db-shm',names)
    with sqlite3.connect(Path(result['restored_to'])/'octop.db') as restored:
     self.assertEqual(restored.execute('SELECT value FROM backup_marker').fetchone()[0],'preserved')
