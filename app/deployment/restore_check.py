#!/usr/bin/env python3
"""Restore into a NEW directory and verify the snapshot, never overwrite live data."""
import argparse
import hashlib
import json
import sqlite3
import tarfile
from pathlib import Path


def restore(archive,target):
    target=Path(target).resolve()
    if target.exists() and any(target.iterdir()): raise SystemExit("恢复目录必须为空；不会覆盖现有数据")
    target.mkdir(parents=True,exist_ok=True)
    target.chmod(0o700)
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            p=Path(member.name)
            if p.is_absolute() or ".." in p.parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()): raise ValueError("归档含不安全路径或类型")
        tar.extractall(target,filter="data")
    # Python's data filter intentionally discards directory permission bits.
    # Reapply the private configuration boundary before loading any preset.
    (target/"data").chmod(0o700)
    credentials=target/"data"/"credentials"
    if credentials.is_dir():
        credentials.chmod(0o700)
        for name in ("opencode-go.json","opencode-go.key","siliconflow-asr.key"):
            if (credentials/name).is_file(): (credentials/name).chmod(0o600)
    manifest=json.loads((target/"manifest.json").read_text())
    failures=[]
    for rel,expected in manifest["files"].items():
        p=target/"data"/rel
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected["sha256"]: failures.append(rel)
    if failures: raise ValueError("恢复文件校验失败: "+", ".join(failures))
    with sqlite3.connect(target/"data"/"octop.db") as db:
        assert db.execute("PRAGMA quick_check").fetchone()[0]=="ok"
        counts={t:db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("team_projects","team_members","team_messages","team_objects","team_runs")}
    result={"restored_to":str(target/"data"),"files_verified":len(manifest["files"]),"sqlite_check":"ok","counts":counts,"live_service_modified":False,"http_login_and_acl_check":"requires_isolated_runtime_test"}
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("archive");p.add_argument("target");a=p.parse_args();restore(a.archive,a.target)
