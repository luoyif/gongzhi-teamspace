#!/usr/bin/env python3
"""Manage only this project's local portal process; never stop a WSL distro."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.environ.get("TEAMAI_DATA_ROOT",str(ROOT/"data"))).resolve()
PID=DATA/"portal.pid"
URL="http://127.0.0.1:"+os.environ.get("TEAMAI_PORT","47821")


def owned_process():
    try:
        pid=int(PID.read_text().strip())
        if pid<=1: return None
        if Path(f"/proc/{pid}/cmdline").exists():
            command=Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0",b" ").decode(errors="replace")
        else:
            command=subprocess.check_output(["ps","-p",str(pid),"-o","command="],text=True,stderr=subprocess.DEVNULL).strip()
        expected=str(ROOT/".venv"/"bin"/"octop")
        return pid if expected in command and " run " in " "+command+" " else None
    except (OSError,ValueError,subprocess.CalledProcessError):
        return None


def health():
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(URL+"/api/health",timeout=2) as response:
            data=json.loads(response.read())
            return response.status==200 and data.get("product")=="teamspace" and data.get("ok")
    except Exception: return False


def main(action):
    os.umask(0o077)
    DATA.mkdir(parents=True,exist_ok=True)
    pid=owned_process()
    if action=="status":
        ready=health()
        print(json.dumps({"owned_pid":pid,"http_ready":bool(ready),"url":URL,"data":str(DATA)}))
        return 0 if pid and ready else 1
    if action=="stop":
        if not pid:
            print("No matching project process; no unrelated process was stopped.")
            return 0
        os.kill(pid,signal.SIGTERM)
        for _ in range(60):
            if not owned_process():
                PID.unlink(missing_ok=True)
                print("Project portal stopped.")
                return 0
            time.sleep(0.25)
        print("Project process did not stop in 15 seconds; inspect it before forcing termination.",file=sys.stderr)
        return 1
    if pid:
        print(json.dumps({"already_started":True,"pid":pid,"http_ready":bool(health()),"url":URL}))
        return 0 if health() else 1
    if health():
        print("A Teamspace service already answers on this port but has no matching PID file; inspect it before starting another.",file=sys.stderr)
        return 1
    logs=DATA/"logs";logs.mkdir(exist_ok=True)
    logfile=logs/"portal.log"
    if logfile.exists() and logfile.stat().st_size>10*1024*1024:
        logfile.replace(logs/"portal.previous.log")
    with logfile.open("ab") as output:
        process=subprocess.Popen(["bash",str(ROOT/"app"/"deployment"/"run.sh")],cwd=ROOT,
                                 stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    PID.write_text(str(process.pid)+"\n")
    for _ in range(180):
        if process.poll() is not None:
            PID.unlink(missing_ok=True)
            print("Project startup failed; inspect "+str(logfile),file=sys.stderr)
            return 1
        if health():
            print(json.dumps({"started":True,"pid":process.pid,"url":URL,"data":str(DATA)}))
            return 0
        time.sleep(0.25)
    print("Process started but readiness is pending; inspect "+str(logfile),file=sys.stderr)
    return 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("start","stop","status"))
    raise SystemExit(main(parser.parse_args().action))
