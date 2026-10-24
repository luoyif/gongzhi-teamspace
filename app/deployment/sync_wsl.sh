#!/usr/bin/env bash
# Copy only project code/docs into WSL's Linux filesystem. Preserve data/venv.
set -euo pipefail
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST_ROOT="${1:-$HOME/develop/team-ai-shared-context}"
python3 - "$SOURCE_ROOT" "$DEST_ROOT" <<'PY'
import hashlib,json,os,shutil,sys
from pathlib import Path
source,dest=map(lambda x:Path(x).resolve(),sys.argv[1:])
if str(dest).startswith('/mnt/'):
    raise SystemExit('Runtime must live in the Linux filesystem, not /mnt/c or /mnt/e')
dest.mkdir(parents=True,exist_ok=True)
pidfile=dest/'data'/'portal.pid'
if pidfile.exists():
    try:
        pid=int(pidfile.read_text().strip())
        command=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        if str(dest/'.venv/bin/octop') in command:
            raise SystemExit('Stop this project portal before updating its application files')
    except (OSError,ValueError): pass
count=0
for name in ('app','docs','deployment'):
    src=source/name
    if not src.is_dir(): continue
    for f in src.rglob('*'):
        if not f.is_file() or any(p in ('__pycache__','.git','.venv','node_modules') for p in f.parts) or f.suffix in ('.pyc','.log','.zip','.b64'): continue
        relative=f.relative_to(source); target=dest/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(f,target)
        if hashlib.sha256(f.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest(): raise SystemExit('Copy hash mismatch')
        count+=1
for name in ('README.md','AGENTS.md','project-state.json'):
    if (source/name).is_file(): shutil.copyfile(source/name,dest/name);count+=1
(dest/'evidence').mkdir(exist_ok=True)
record={'copied_files':count,'source':str(source),'runtime':str(dest),'data_untouched':True}
(dest/'evidence/windows-code-sync.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
PY
