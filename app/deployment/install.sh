#!/usr/bin/env bash
# Install only in this project's isolated environment. No system Python changes.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.tools/python"
export UV_PYTHON_BIN_DIR="$PROJECT_ROOT/.tools/bin"
export UV_LINK_MODE=copy
export UV_NATIVE_TLS=true
umask 077
mkdir -p "$PROJECT_ROOT/runtime" "$PROJECT_ROOT/upstream" "$PROJECT_ROOT/evidence"
if [[ -x "$PROJECT_ROOT/.tools/uv" ]]; then UV="$PROJECT_ROOT/.tools/uv";
elif command -v uv >/dev/null 2>&1; then UV="$(command -v uv)";
elif [[ -x /usr/local/bin/uv ]]; then UV=/usr/local/bin/uv;
else
  echo 'uv is required. See docs/06_Windows_WSL_部署与恢复.md for the official install step.' >&2
  exit 1
fi
"$UV" python install 3.12
if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  "$UV" venv --python 3.12 "$PROJECT_ROOT/.venv"
fi
"$PROJECT_ROOT/.venv/bin/python" -c 'import sys; assert sys.version_info[:2] == (3,12), "Project environment must use Python 3.12"'
ARCHIVE="$PROJECT_ROOT/upstream/Octop-dd9dce470844.tar.gz"
if [[ ! -f "$ARCHIVE" && -f "$PROJECT_ROOT/upstream/Octop.tar.gz" ]]; then
  ARCHIVE="$PROJECT_ROOT/upstream/Octop.tar.gz"
fi
if [[ ! -f "$ARCHIVE" ]]; then
  curl --fail --location --connect-timeout 15 --max-time 180 --output "$ARCHIVE.part" \
    https://codeload.github.com/TencentCloud/Octop/tar.gz/dd9dce470844c25d59effb50615bb3c667ea25cd
  mv "$ARCHIVE.part" "$ARCHIVE"
fi
"$PROJECT_ROOT/.venv/bin/python" - "$PROJECT_ROOT" "$ARCHIVE" <<'PY'
import hashlib,sys,tarfile,tempfile,shutil
from pathlib import Path
root,archive=map(Path,sys.argv[1:])
actual=hashlib.sha256(archive.read_bytes()).hexdigest()
expected='d02beb404f890f57fc008d114be7eb0c26ab39bf2b500e00ce03ea10dc6e2727'
if actual != expected: raise SystemExit('Pinned Octop archive SHA256 mismatch')
dest=root/'runtime'/'Octop'
if not dest.exists():
    with tempfile.TemporaryDirectory(dir=root/'runtime') as temp:
        with tarfile.open(archive) as tf: tf.extractall(temp,filter='data')
        src=Path(temp)/'Octop-dd9dce470844c25d59effb50615bb3c667ea25cd'
        if not (src/'pyproject.toml').is_file(): raise SystemExit('Unexpected archive layout')
        shutil.move(str(src),str(dest))
print('PINNED_SOURCE_SHA256_OK', actual)
PY
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/app/deployment/patch_octop.py" "$PROJECT_ROOT/runtime/Octop"
"$UV" pip install --python "$PROJECT_ROOT/.venv/bin/python" --constraint "$PROJECT_ROOT/app/deployment/constraints-tested.txt" -e "$PROJECT_ROOT/runtime/Octop"
"$UV" pip freeze --python "$PROJECT_ROOT/.venv/bin/python" > "$PROJECT_ROOT/evidence/runtime-lock.txt"
PYTHONPATH="$PROJECT_ROOT/app" "$PROJECT_ROOT/.venv/bin/python" -c 'import octop, fastapi, teamspace.integration; print("APPLICATION_IMPORTS_OK")'
echo 'Install complete. Start: bash app/deployment/run.sh'
