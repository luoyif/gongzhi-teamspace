"""Task-local, sequential execution plan with human evidence gates.

No autonomous DAG, implicit paid model retries, or knowledge publication.
Unlike agent handoffs, a plan is authored before execution and each agent step
starts only after project-owner approval. All rows belong to one verified task.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any
from fastapi import APIRouter, Body, Depends
from octop.api.deps import current_user, get_server
from .api import store_for, controller
from .store import Problem, dump, now, uid, require_text
from .task_conversation import require_task
from .platform_registry import PlatformRegistry

router = APIRouter()
MAX_STEPS = 8
SCHEMA = """
CREATE TABLE IF NOT EXISTS team_task_workflow_plans(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,task_id TEXT NOT NULL UNIQUE,
 title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
 input_hash TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'active',
 created_by INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_task_workflow_steps(
 id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,project_id TEXT NOT NULL,task_id TEXT NOT NULL,
 ordinal INTEGER NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,instruction TEXT NOT NULL,
 agent_id TEXT,agent_revision INTEGER,status TEXT NOT NULL DEFAULT 'pending',
 revision INTEGER NOT NULL DEFAULT 1,run_id TEXT,approved_by INTEGER,
 approved_at TEXT,review_note TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
 UNIQUE(plan_id,ordinal)
);
CREATE INDEX IF NOT EXISTS team_workflow_steps_by_task
 ON team_task_workflow_steps(project_id,task_id,ordinal);
CREATE TABLE IF NOT EXISTS team_task_workflow_step_history(
 id TEXT PRIMARY KEY,step_id TEXT NOT NULL,plan_id TEXT NOT NULL,project_id TEXT NOT NULL,
 task_id TEXT NOT NULL,revision INTEGER NOT NULL,old_status TEXT NOT NULL,
 old_run_id TEXT,reason TEXT NOT NULL,actor_id INTEGER NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS team_workflow_step_history_by_step
 ON team_task_workflow_step_history(step_id,created_at);
"""

def _require(s,c,p,tid,actor,owner=False):
    require_task(s,c,p,tid,actor)
    if owner:s.require(c,p,actor,owner=True)

def _plan(c,p,tid):
    row=c.execute("SELECT * FROM team_task_workflow_plans WHERE project_id=? AND task_id=?",(p,tid)).fetchone()
    return dict(row) if row else None

def _step(c,p,tid,step_id):
    row=c.execute("SELECT * FROM team_task_workflow_steps WHERE id=? AND project_id=? AND task_id=?",
                  (step_id,p,tid)).fetchone()
    if not row:raise Problem(404,"流程步骤不存在或不可访问")
    return dict(row)

def _source_run(c,p,tid,runid,finished=False):
    if not isinstance(runid,str) or not runid:
        raise Problem(409,"步骤还没有真实的模型运行回执")
    row=c.execute("SELECT id,status,request_json,config_json,usage_json FROM team_runs WHERE id=? AND project_id=?",
                  (runid,p)).fetchone()
    if not row or json.loads(row["request_json"]).get("task_id")!=tid:
        raise Problem(404,"运行结果不属于当前任务")
    if finished and row["status"]!="completed":
        raise Problem(409,"只有真正完成的运行才能提交人工验收")
    if finished:
        output=c.execute("SELECT 1 FROM team_messages WHERE project_id=? AND run_id=? AND kind='assistant' LIMIT 1",
                         (p,runid)).fetchone()
        if not output:raise Problem(409,"模型没有留下可核对的任务回复")
    return dict(row)

def _public_step(c,p,tid,step):
    result={k:step[k] for k in (
        "id","ordinal","kind","title","instruction","agent_id","agent_revision",
        "status","revision","run_id","approved_by","approved_at","review_note","created_at","updated_at"
    )}
    result["run_status"]=None
    result["effective_status"]=step["status"]
    result["known_total_tokens"]=None
    if step["run_id"]:
        row=_source_run(c,p,tid,step["run_id"])
        result["run_status"]=row["status"]
        usage=json.loads(row["usage_json"] or "{}")
        result["known_total_tokens"]=usage.get("total_tokens")
        if step["status"] in ("running","dispatching"):
            result["effective_status"]=("needs_review" if row["status"]=="completed"
                 else "blocked" if row["status"] in ("failed","interrupted","paused")
                 else "running")
    return result

def _detail(c,p,tid):
    plan=_plan(c,p,tid)
    if not plan:return {"status":"missing","task_id":tid,"steps":[],"sequential_only":True,
                        "user_approval_required":True,"automatic_dispatch":False}
    steps=[_public_step(c,p,tid,dict(r)) for r in c.execute(
        "SELECT * FROM team_task_workflow_steps WHERE plan_id=? ORDER BY ordinal",(plan["id"],))]
    return {"id":plan["id"],"title":plan["title"],"description":plan["description"],
            "status":plan["status"],"revision":plan["revision"],"task_id":tid,
            "steps":steps,"sequential_only":True,"user_approval_required":True,
            "automatic_dispatch":False,"knowledge_published":False}

def _prepare(c,s,p,actor,steps):
    if not isinstance(steps,list) or not 2<=len(steps)<=MAX_STEPS:
        raise Problem(422,"计划必须包含2至8项步骤")
    registry=PlatformRegistry(s)
    project=c.execute("SELECT settings_json FROM team_projects WHERE id=?",(p,)).fetchone()
    if not project:raise Problem(404,"项目不存在")
    settings=json.loads(project["settings_json"])
    data=[]
    for item in steps:
        if not isinstance(item,dict):raise Problem(422,"流程步骤必须为对象")
        kind=item.get("kind")
        if kind not in ("agent","review"):
            raise Problem(422,"步骤仅支持AI执行或人工审核；知识发布需独立采用")
        title=require_text(item.get("title"),"步骤名称",120,False)
        instruction=require_text(item.get("instruction"),"步骤说明",1200,False)
        aid=None;revision=None
        if kind=="agent":
            aid=require_text(item.get("agent_id"),"执行员工",128,False)
            snap=registry.snapshot(c,p,actor,{"agent_id":aid},settings)["agent_snapshot"]
            if snap["id"]!=aid:raise Problem(409,"目标员工无法用于当前任务")
            revision=int(snap["revision"])
        if kind=="review" and item.get("agent_id"):
            raise Problem(422,"人工审核步骤不能设置AI员工")
        data.append({"kind":kind,"title":title,"instruction":instruction,
                     "agent_id":aid,"agent_revision":revision})
    if data[-1]["kind"]!="review":
        raise Problem(422,"最后一个步骤必须是人工审核，避免自动冒充已验收")
    return data

def _before(c,plan_id,ordinal):
    prior=c.execute("SELECT id,status FROM team_task_workflow_steps WHERE plan_id=? AND ordinal<? ORDER BY ordinal",
                    (plan_id,ordinal)).fetchall()
    if any(r["status"]!="accepted" for r in prior):
        raise Problem(409,"请先完成并确认前面的流程步骤")

@router.get("/tasks/{tid}/plan")
def get_plan(tid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    with s.connection() as c:
        _require(s,c,p,tid,user.id)
        return _detail(c,p,tid)

@router.post("/tasks/{tid}/plan",status_code=201)
def create_plan(tid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    title=require_text(body.get("title"),"计划名称",160,False)
    description=require_text(body.get("description",""),"计划简介",1000)
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        steps=_prepare(c,s,p,user.id,body.get("steps"))
        fingerprint=hashlib.sha256(dump([title,description,steps]).encode()).hexdigest()
        old=_plan(c,p,tid)
        if old:
            if old["input_hash"]==fingerprint:return _detail(c,p,tid)
            raise Problem(409,"当前任务已有不同计划，请先查看并明确编辑")
        stamp=now();planid=uid("wf_")
        c.execute("""INSERT INTO team_task_workflow_plans
         (id,project_id,task_id,title,description,input_hash,created_by,created_at,updated_at)
         VALUES(?,?,?,?,?,?,?,?,?)""",(planid,p,tid,title,description,fingerprint,user.id,stamp,stamp))
        for idx,item in enumerate(steps):
            c.execute("""INSERT INTO team_task_workflow_steps
             (id,plan_id,project_id,task_id,ordinal,kind,title,instruction,agent_id,agent_revision,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
             (uid("ws_"),planid,p,tid,idx,item["kind"],item["title"],item["instruction"],
              item["agent_id"],item["agent_revision"],stamp,stamp))
        return _detail(c,p,tid)

@router.put("/tasks/{tid}/plan")
def revise_plan(tid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    title=require_text(body.get("title"),"计划名称",160,False)
    description=require_text(body.get("description",""),"计划简介",1000)
    expected=body.get("expected_revision")
    if type(expected)!=int or expected<1:raise Problem(422,"必须提供期望计划版本")
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        plan=_plan(c,p,tid)
        if not plan:raise Problem(404,"计划不存在")
        if plan["revision"]!=expected:raise Problem(409,"计划已经被其他成员修改")
        old=c.execute("SELECT status FROM team_task_workflow_steps WHERE plan_id=?",(plan["id"],)).fetchall()
        if any(r["status"]!="pending" for r in old):
            raise Problem(409,"流程已开始，不能静默替换历史步骤；请保留审计记录")
        steps=_prepare(c,s,p,user.id,body.get("steps"))
        digest=hashlib.sha256(dump([title,description,steps]).encode()).hexdigest()
        if digest==plan["input_hash"]:return _detail(c,p,tid)
        stamp=now()
        c.execute("DELETE FROM team_task_workflow_steps WHERE plan_id=?",(plan["id"],))
        for idx,item in enumerate(steps):
            c.execute("""INSERT INTO team_task_workflow_steps
             (id,plan_id,project_id,task_id,ordinal,kind,title,instruction,agent_id,agent_revision,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
             (uid("ws_"),plan["id"],p,tid,idx,item["kind"],item["title"],item["instruction"],
              item["agent_id"],item["agent_revision"],stamp,stamp))
        c.execute("""UPDATE team_task_workflow_plans SET title=?,description=?,input_hash=?,
                  revision=revision+1,updated_at=? WHERE id=?""",
                  (title,description,digest,stamp,plan["id"]))
        return _detail(c,p,tid)

@router.post("/tasks/{tid}/plan/steps/{sid}/start")
async def start_step(tid:str,sid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        item=_step(c,p,tid,sid)
        _before(c,item["plan_id"],item["ordinal"])
        if item["kind"]!="agent":raise Problem(409,"这个步骤需要由真人直接审核，不能调用模型")
        if item["status"]=="running" and item["run_id"]:return _detail(c,p,tid)
        if item["status"]!="pending":raise Problem(409,"已开始或结束的步骤不能自动重复执行")
        settings=json.loads(c.execute("SELECT settings_json FROM team_projects WHERE id=?",(p,)).fetchone()["settings_json"])
        current=PlatformRegistry(s).snapshot(c,p,user.id,{"agent_id":item["agent_id"]},settings)["agent_snapshot"]
        if int(current["revision"])!=item["agent_revision"]:
            raise Problem(409,"目标员工配置已变化，请重新审核计划")
        c.execute("UPDATE team_task_workflow_steps SET status='dispatching',updated_at=? WHERE id=?",
                  (now(),sid))
        prev=c.execute("""SELECT run_id FROM team_task_workflow_steps WHERE plan_id=?
            AND ordinal<? AND run_id IS NOT NULL AND status='accepted' ORDER BY ordinal DESC LIMIT 1""",
            (item["plan_id"],item["ordinal"])).fetchone()
        preceding=prev["run_id"] if prev else None
        plan=_plan(c,p,tid)
        instruction=(f"经项目管理员明确批准的任务内流程步骤 {item['ordinal']+1}。"
                     f"计划 {plan['title']}，步骤 {item['title']}：{item['instruction']}。"
                     "请核对现有任务资料和之前已完成的真实Run回执。"
                     "不得把计划视为已经执行，不自动发布知识或修改其他项目。"
                     "执行完应提供可供人工审核的结果及来源。")
    payload={"kind":"chat","task_id":tid,"agent_id":item["agent_id"],
             "agent_revision":item["agent_revision"],"prompt":instruction,
             "client_id":f"workflow-{sid}-v{item['revision']}",
             "run_options":{"budget":"standard","permission_mode":"safe"}}
    if preceding:payload["continue_from"]=preceding
    try:
        run=controller(server).start_run(p,user,payload)
    except Exception:
        with s.connection(True) as c:
            prior=c.execute("SELECT id FROM team_runs WHERE project_id=? AND actor_id=? AND client_id=?",
                            (p,user.id,payload["client_id"])).fetchone()
            if prior:
                c.execute("UPDATE team_task_workflow_steps SET run_id=?,status='running',updated_at=? WHERE id=? AND status='dispatching'",
                          (prior["id"],now(),sid))
            else:
                c.execute("UPDATE team_task_workflow_steps SET status='pending',updated_at=? WHERE id=? AND status='dispatching'",
                          (now(),sid))
        raise
    with s.connection(True) as c:
        c.execute("UPDATE team_task_workflow_steps SET run_id=?,status='running',updated_at=? WHERE id=? AND status='dispatching'",
                  (run["id"],now(),sid))
        return _detail(c,p,tid)

@router.post("/tasks/{tid}/plan/steps/{sid}/approve")
def approve_step(tid:str,sid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    note=require_text(body.get("note"),"验收说明",1200,False)
    if len(note.strip())<8:raise Problem(422,"请写至少8个字的实际核查结果")
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        step=_step(c,p,tid,sid)
        _before(c,step["plan_id"],step["ordinal"])
        if step["status"]=="accepted":return _detail(c,p,tid)
        if step["status"] not in ("running","pending"):
            raise Problem(409,"这个步骤未处于可核验状态")
        if step["kind"]=="agent":
            _source_run(c,p,tid,step["run_id"],finished=True)
        elif step["kind"]=="review":
            if step["status"]!="pending":raise Problem(409,"人工审核步骤的状态不正确")
        stamp=now()
        c.execute("""UPDATE team_task_workflow_steps
            SET status='accepted',approved_by=?,approved_at=?,review_note=?,updated_at=?
            WHERE id=?""",(user.id,stamp,note,stamp,sid))
        remaining=c.execute("SELECT COUNT(*) FROM team_task_workflow_steps WHERE plan_id=? AND status!='accepted'",
                            (step["plan_id"],)).fetchone()[0]
        if remaining==0:
            c.execute("UPDATE team_task_workflow_plans SET status='completed',updated_at=? WHERE id=?",
                      (stamp,step["plan_id"]))
        return _detail(c,p,tid)

@router.post("/tasks/{tid}/plan/steps/{sid}/retry")
def retry_step(tid:str,sid:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    reason=require_text(body.get("reason"),"重试原因",400,False)
    if len(reason.strip())<8:raise Problem(422,"必须说明为什么要重新运行")
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        item=_step(c,p,tid,sid)
        if item["kind"]!="agent" or not item["run_id"]:
            raise Problem(409,"只有已经执行失败的模型步骤允许人工重试")
        r=_source_run(c,p,tid,item["run_id"])
        if r["status"] not in ("failed","paused","interrupted"):
            raise Problem(409,"运行尚未失败或已完成，不允许重新计费")
        c.execute("""INSERT INTO team_task_workflow_step_history
             (id,step_id,plan_id,project_id,task_id,revision,old_status,old_run_id,reason,actor_id,created_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
             (uid("wh_"),sid,item["plan_id"],p,tid,item["revision"],item["status"],
              item["run_id"],reason,user.id,now()))
        c.execute("UPDATE team_task_workflow_steps SET status='pending',run_id=NULL,revision=revision+1,updated_at=? WHERE id=?",
                  (now(),sid))
        return _detail(c,p,tid)

@router.get("/tasks/{tid}/plan/steps/{sid}/history")
def step_history(tid:str,sid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    with s.connection() as c:
        _require(s,c,p,tid,user.id)
        _step(c,p,tid,sid)
        rows=c.execute("""SELECT old_status,old_run_id,revision,reason,actor_id,created_at
            FROM team_task_workflow_step_history WHERE project_id=? AND task_id=? AND step_id=?
            ORDER BY created_at""",(p,tid,sid)).fetchall()
        return {"items":[dict(x) for x in rows]}



@router.post("/tasks/{tid}/plan/steps/{sid}/reconcile")
def reconcile_step(tid:str,sid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    """Human-driven repair after uncertain dispatch. Never makes a model call."""
    s=store_for(server);task=s.object(tid,user.id,"task");p=task["project_id"]
    with s.connection(True) as c:
        _require(s,c,p,tid,user.id,owner=True)
        item=_step(c,p,tid,sid)
        if item["status"]!="dispatching":
            raise Problem(409,"这一步没有需要人工核对的发送中记录")
        client_id=f"workflow-{sid}-v{item['revision']}"
        rows=c.execute("SELECT id,status,request_json,config_json FROM team_runs WHERE project_id=? AND client_id=?",
                       (p,client_id)).fetchall()
        if len(rows)>1:raise Problem(409,"发现不止一项关联运行，需要人工审计")
        if rows:
            run=dict(rows[0]);request=json.loads(run["request_json"])
            cfg=json.loads(run["config_json"])
            agent=cfg.get("agent_snapshot") or {}
            if request.get("task_id")!=tid or agent.get("id")!=item["agent_id"]:
                raise Problem(409,"关联运行与该步骤身份不一致，禁止自动采纳")
            status="running"
            runid=run["id"]
            reason="人工核对：运行已入库，关联原 Run，不发起新的模型请求"
        else:
            status="pending";runid=None
            reason="人工核对：没有持久化 Run，恢复为待开始，不自动运行"
        c.execute("""INSERT INTO team_task_workflow_step_history
                (id,step_id,plan_id,project_id,task_id,revision,old_status,old_run_id,reason,actor_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (uid("wh_"),sid,item["plan_id"],p,tid,item["revision"],item["status"],
                 item["run_id"],reason,user.id,now()))
        c.execute("UPDATE team_task_workflow_steps SET run_id=?,status=?,updated_at=? WHERE id=?",
                  (runid,status,now(),sid))
        return _detail(c,p,tid)
