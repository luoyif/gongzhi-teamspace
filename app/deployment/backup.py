#!/usr/bin/env python3
"""Consistent SQLite snapshot + immutable originals. Backups contain credentials."""
import argparse
from contextlib import closing
import datetime as dt
import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from pathlib import Path


def backup(root,destination):
    root=Path(root).resolve(); destination=Path(destination).resolve()
    source=root/"octop.db"
    if not source.is_file(): raise SystemExit("业务数据库不存在，不能生成空备份")
    destination.mkdir(parents=True,exist_ok=True)
    os.chmod(destination,0o700)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    target=destination/f"team-ai-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="team-ai-backup-") as temp:
        stage=Path(temp)/"data"; stage.mkdir()
        # Close both connections before hashing and archiving. A connection
        # context manager commits but does not close, so SQLite WAL/SHM files
        # could otherwise change between manifest creation and tar creation.
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(stage/"octop.db")) as dst:
            src.backup(dst)
            assert dst.execute("PRAGMA quick_check").fetchone()[0]=="ok"
            references=[]
            for r in dst.execute("SELECT data_json FROM team_objects WHERE kind='document'"):
                d=json.loads(r[0])
                if d.get("blob_path"): references.append(d)
            avatar_paths=[]
            if dst.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='team_avatars'").fetchone():
                avatar_paths=[r[0] for r in dst.execute("SELECT DISTINCT blob_path FROM team_avatars WHERE blob_path IS NOT NULL")]
        for relative in avatar_paths:
            rel=Path(relative)
            if rel.is_absolute() or ".." in rel.parts or len(rel.parts)!=2 or rel.parts[0]!="avatars" or rel.suffix!=".png":raise ValueError("非法头像路径")
            src=root/"teamspace"/rel
            if hashlib.sha256(src.read_bytes()).hexdigest()!=rel.stem:raise ValueError("头像原件校验失败")
            target_avatar=stage/"teamspace"/rel;target_avatar.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target_avatar);target_avatar.chmod(0o600)
        for info in references:
            relative=Path(info["blob_path"])
            if relative.is_absolute() or ".." in relative.parts: raise ValueError("非法原件路径")
            src=root/"teamspace"/relative
            if hashlib.sha256(src.read_bytes()).hexdigest()!=info["sha256"]: raise ValueError("原件校验失败")
            dst=stage/"teamspace"/relative; dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        for name in ("config.json",".env","network-policy.json"):
            if (root/name).is_file(): shutil.copy2(root/name,stage/name)
        # The administrator-installed model preset is server configuration too.
        for name in ("opencode-go.json","opencode-go.key","siliconflow-asr.key"):
            src=root/"credentials"/name
            if src.is_file():
                folder=stage/"credentials";folder.mkdir(mode=0o700,exist_ok=True)
                shutil.copy2(src,folder/name);os.chmod(folder/name,0o600)
        # Octop JWT/API secrets are in the business DB; include an extension
        # encryption key if future deployments choose to create one.
        for name in ("master.key","secrets.key"):
            if (root/"teamspace"/name).is_file():
                (stage/"teamspace").mkdir(exist_ok=True)
                shutil.copy2(root/"teamspace"/name,stage/"teamspace"/name)
        manifest={str(p.relative_to(stage)):{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in stage.rglob("*") if p.is_file()}
        record={"version":1,"created_at":stamp,"sqlite_consistent_snapshot":True,"originals":len(references),"avatars":len(avatar_paths),"files":manifest,"contains_credentials":True,"exports_rebuildable":True}
        (Path(temp)/"manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2))
        with tarfile.open(target,"w:gz") as tar:
            tar.add(stage,arcname="data")
            tar.add(Path(temp)/"manifest.json",arcname="manifest.json")
    os.chmod(target,0o600)
    result={"path":str(target),"bytes":target.stat().st_size,"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"originals":len(references),"contains_credentials":True}
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    project=Path(__file__).resolve().parents[2]
    parser.add_argument("--data",default=str(project/"data"))
    parser.add_argument("--destination",default=str(project/"backups"))
    args=parser.parse_args(); backup(args.data,args.destination)
