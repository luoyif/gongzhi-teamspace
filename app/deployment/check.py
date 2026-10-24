#!/usr/bin/env python3
"""Read-only local deployment checks; pending external gates are never PASS."""
import argparse
import datetime as dt
import hashlib
import json
import platform
import sqlite3
import sys
import urllib.request
from pathlib import Path


def check(root,url,data=None):
    root=Path(root).resolve(); results=[]
    data=Path(data).resolve() if data else root/"data"
    def record(name,status,detail): results.append({"check":name,"status":status,"detail":detail})
    try:
        with urllib.request.urlopen(url+"/api/health",timeout=10) as response:
            record("http_health","pass" if response.status==200 else "fail",json.loads(response.read()))
    except Exception as exc: record("http_health","fail",type(exc).__name__)
    try:
        with urllib.request.urlopen(url+"/api/setup/status",timeout=10) as response:
            status=json.loads(response.read());record("account_initialized","pending" if status.get("setup_required") else "pass",{"setup_required":status.get("setup_required")})
    except Exception as exc: record("setup_status","fail",type(exc).__name__)
    db=data/"octop.db"
    if db.exists():
        try:
            with sqlite3.connect(f"file:{db}?mode=ro",uri=True) as c:
                ok=c.execute("PRAGMA quick_check").fetchone()[0]
                record("sqlite_integrity","pass" if ok=="ok" else "fail",ok)
                record("sqlite_location","pass" if not str(db).startswith("/mnt/") else "warn",str(db))
                dirty=c.execute("SELECT COUNT(*) FROM team_outbox WHERE revision>exported_revision").fetchone()[0]
                record("markdown_outbox","pending" if dirty else "pass",{"pending_projects":dirty})
                providers=c.execute("SELECT COUNT(*) FROM providers WHERE name LIKE 'team-project-%' AND enabled=1").fetchone()[0]
                record("model_configured","pass" if providers else "pending",{"project_providers":providers})
                real=c.execute("SELECT COUNT(*) FROM team_runs WHERE status='completed'").fetchone()[0]
                record("model_run_history","pass" if real else "pending",{"completed_runs":real,"does_not_prove_external_model_quality":True})
                missing=[]
                for (raw,) in c.execute("SELECT data_json FROM team_objects WHERE kind='document'"):
                    d=json.loads(raw)
                    if d.get("blob_path"):
                        path=data/"teamspace"/d["blob_path"]
                        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=d["sha256"]: missing.append(d.get("filename"))
                record("original_file_hashes","fail" if missing else "pass",{"failures":missing})
        except Exception as exc: record("database_checks","fail",type(exc).__name__)
    else: record("database_exists","fail",str(db))
    record("windows_reboot_sleep_recovery","not_tested","需在用户允许的实际重启/休眠窗口验证；未自动重启电脑")
    record("public_https","not_configured","当前服务为本机入口；需要实际域名及入口主机后验证")
    record("external_model_quality","not_tested","需要配置实际模型后完成真实回答与整理验收")
    return {"checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),"platform":platform.platform(),"python":platform.python_version(),"url":url,"checks":results,"blocking_failures":sum(x["status"]=="fail" for x in results)}


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(Path(__file__).resolve().parents[2]));p.add_argument("--data");p.add_argument("--url",default="http://127.0.0.1:47821");p.add_argument("--output");a=p.parse_args()
    result=check(a.root,a.url,a.data);text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(text+"\n",encoding="utf-8")
    print(text);sys.exit(bool(result["blocking_failures"]))
