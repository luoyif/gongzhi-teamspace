"""Rebuildable project exports of pinned capability bundles, never credentials."""
import json,os,shutil,tempfile
from pathlib import Path
from .store import dump


def export_project_platform(store,p):
    with store.connection() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='team_platform_bindings'").fetchone():return
        bindings=[dict(x) for x in c.execute('SELECT * FROM team_platform_bindings WHERE project_id=?',(p,))]
    root=store.data_dir/'exports'/p
    def write(rel,content):
        target=root/rel;target.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(content if isinstance(content,bytes) else content.encode('utf8'));f.flush();os.fsync(f.fileno())
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    for folder in ('capabilities','skills'):
        if (root/folder).exists():shutil.rmtree(root/folder)
    from .platform_registry import PlatformRegistry
    from .platform_api import asset_files
    registry=PlatformRegistry.__new__(PlatformRegistry);registry.store=store
    for binding in bindings:
        bundle=json.loads(binding.pop('bundle_json'))
        write('capabilities/'+binding['asset_id']+'/BINDING.json',dump({**binding,'assets':[{'id':a['id'],'kind':a['kind'],'revision':a['revision']} for a in bundle['assets']]}))
        for a in bundle['assets']:
            for name,b in asset_files(registry,a).items():write('capabilities/'+binding['asset_id']+'/'+name,b)
    write('CAPABILITIES.md','# 已固定的公司能力配置\n\n这些文件是项目绑定的只读导出。配置权威在公司能力中心；不应在导出目录直接编辑。启用不共享其他项目的聊天、文件或模型密钥。\n')
