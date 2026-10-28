"""Gongzhi knowledge-flow evidence ledger — read-only and task scoped.

The ledger is NOT a model-generated graph. Each node comes from an actual
database row and each edge from an explicit foreign key or task/source ID.
A model's output is never labelled human-accepted or organization-published
unless the corresponding authoritative review/publication row exists.

Scope checks are performed on *every* read. No cross-project artifact is
included just because the same AI employee or author participated elsewhere.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from fastapi import APIRouter, Depends
from octop.api.deps import current_user, get_server
from .api import store_for
from .task_conversation import require_task

router = APIRouter()
MAX_MESSAGES = 90
MAX_RUNS = 24
MAX_DOCUMENTS = 30
MAX_STEPS = 12
MAX_HANDOFFS = 12
MAX_PUBLICATIONS = 20
MAX_UPLOADS = 35
MAX_TOOL_EVENTS = 36


def _json(value, default=None):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return default if default is not None else {}
    return parsed if isinstance(parsed, dict) else (default if default is not None else {})


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _task_graph(s, c, p: str, tid: str, actor: int) -> dict:
    require_task(s, c, p, tid, actor)
    task = c.execute("SELECT id,title,revision FROM team_objects "
                     "WHERE project_id=? AND kind='task' AND id=? AND status!='deleted'",
                     (p, tid)).fetchone()
    nodes: list[dict] = []
    edges: list[dict] = []
    ids: set[str] = set()
    seen_edges: set[tuple] = set()
    counts: dict[str, int] = {}
    partial: list[str] = []

    def node(kind: str, raw_id: str, **fields) -> str:
        key = f"{kind}:{raw_id}"
        if key not in ids:
            ids.add(key)
            nodes.append({"id": key, "type": kind, **fields})
        return key

    def edge(src: str, dest: str, relation: str) -> None:
        key = (src, dest, relation)
        if src in ids and dest in ids and key not in seen_edges:
            seen_edges.add(key)
            edges.append({"from": src, "to": dest, "relation": relation})

    root = node("task", tid, title=task["title"], revision=task["revision"],
                scope="project", project_id=p)
    def load(label, sql, args, limit):
        count = c.execute("SELECT COUNT(*) FROM (" + sql + ")", args).fetchone()[0]
        counts[label] = count
        if count > limit:
            partial.append(label)
        return list(c.execute(sql+" LIMIT ?", (*args, limit)))

    messages = load("messages",
        "SELECT id,seq,author_name,author_id,kind,content,run_id,meta_json FROM team_messages "
        "WHERE project_id=? AND json_extract(meta_json,'$.task_id')=? ORDER BY seq DESC",
        (p,tid),MAX_MESSAGES)
    # Message bodies do not leave this API, only stable SHA-256 and identity.
    msg_by_id = {}
    msg_by_seq = {}
    for m in messages:
        msgid = node("message",m["id"],seq=m["seq"],speaker=m["author_name"],
          role="agent" if m["kind"]=="assistant" else "human",
          content_sha256=_sha(m["content"]),source_state="recorded_not_verified",
          scope="task",audience="task",sensitivity_status="unclassified")
        msg_by_id[m["id"]] = msgid
        msg_by_seq[m["seq"]] = msgid
        edge(root,msgid,"contains_message")
    runs = load("runs",
        "SELECT id,kind,status,actor_id,input_seq,request_json,created_at,finished_at "
        "FROM team_runs WHERE project_id=? AND json_extract(request_json,'$.task_id')=? "
        "ORDER BY created_at DESC",(p,tid),MAX_RUNS)
    run_by_id={}
    for r in runs:
        rnode=node("run",r["id"],status=r["status"],run_kind=r["kind"],created_at=r["created_at"],
                   completed_at=r["finished_at"],source_state="execution_record_not_adoption",
                   scope="task",audience="task",sensitivity_status="unclassified")
        run_by_id[r["id"]]=rnode
        edge(root,rnode,"contains_run")
        if r["input_seq"] in msg_by_seq:
            edge(msg_by_seq[r["input_seq"]],rnode,"triggered_run")
    for m in messages:
        if m["run_id"] and m["run_id"] in run_by_id:
            edge(run_by_id[m["run_id"]],msg_by_id[m["id"]],"produced_message")
    docs = load("documents",
        "SELECT id,title,body,status,revision,data_json FROM team_objects "
        "WHERE project_id=? AND kind='document' AND status!='deleted' "
        "AND json_extract(data_json,'$.task_id')=? ORDER BY updated_at DESC",
        (p,tid),MAX_DOCUMENTS)
    doc_by_id={}
    for d in docs:
        data=_json(d["data_json"])
        adopted=bool(data.get("adopted")) and d["status"]=="ready" 
        docnode=node("document",d["id"],title=d["title"],revision=d["revision"],
          status=d["status"],adopted=adopted,
          source_state="project_adopted" if adopted else "not_adopted",
          body_sha256=_sha(d["body"]),project_id=p,scope="project",audience="project",
          sensitivity_status="unclassified")
        doc_by_id[d["id"]]=docnode
        edge(root,docnode,"contains_document")
        if data.get("source_seq") in msg_by_seq:
            edge(msg_by_seq[data["source_seq"]],docnode,"document_derived_from_message")
    # Uploads are distinct provenance events, not the contents of file bytes.
    if docs:
        selected_ids=[d["id"] for d in docs]
        placeholders=",".join("?" for _ in selected_ids)
        upload_query=(
           "SELECT id,document_id,filename,origin,source_seq,created_at "
           "FROM team_uploads WHERE project_id=? AND document_id IN ("+placeholders+") "
           "ORDER BY created_at DESC")
        uploads=load("uploads",upload_query,(p,*selected_ids),MAX_UPLOADS)
        for upload in uploads:
            upnode=node("source_upload",upload["id"],title=upload["filename"],
                source_kind=upload["origin"],created_at=upload["created_at"],
                source_state="original_upload_record",scope="project",audience="project",
                sensitivity_status="unclassified")
            if upload["document_id"] in doc_by_id:
                edge(upnode,doc_by_id[upload["document_id"]],"source_file_for_document")
            if upload["source_seq"] in msg_by_seq:
                edge(msg_by_seq[upload["source_seq"]],upnode,"uploaded_from_message")
    else:
        counts["uploads"]=0

    # A tool event is a receipt trail, never proof of the underlying factual claim.
    # Do not return raw Trace payloads; they may include private prompts or tool args.
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='team_run_events'").fetchone()
    if runs and exists:
        run_ids=list(run_by_id)
        placeholders=",".join("?" for _ in run_ids)
        tool_sql=("SELECT run_id,seq,event,created_at FROM team_run_events "
                  "WHERE run_id IN ("+placeholders+") "
                  "AND event IN ('tool.request','tool.result','tool.error','tool.denied') "
                  "ORDER BY created_at DESC,seq DESC")
        receipts=load("tool_events",tool_sql,tuple(run_ids),MAX_TOOL_EVENTS)
        for item in receipts:
            event_id=item["run_id"]+":"+str(item["seq"])
            enode=node("tool_event",event_id,event=item["event"],
                trace_seq=item["seq"],created_at=item["created_at"],scope="task",
                audience="task",sensitivity_status="unclassified",
                source_state="trace_event_recorded_not_independent_verification")
            edge(run_by_id[item["run_id"]],enode,"run_contains_tool_event")
    else:
        counts["tool_events"]=0

    workflow_steps=load("workflow_steps",
        "SELECT id,plan_id,ordinal,kind,title,status,run_id,approved_by,approved_at,review_note,revision "
        "FROM team_task_workflow_steps WHERE project_id=? AND task_id=? ORDER BY ordinal",
        (p,tid),MAX_STEPS)
    for st in workflow_steps:
        # Accepted step is a human decision, NOT proof that the model's claim was true.
        human_accepted=st["status"]=="accepted" and st["approved_by"] is not None
        stnode=node("review_step",st["id"],title=st["title"],ordinal=st["ordinal"],
          status=st["status"],run_id=st["run_id"],approved_by=st["approved_by"],
          review_note_sha256=_sha(st["review_note"]) if st["review_note"] else None,
          review_note_present=bool(st["review_note"]),
          approval_recorded=human_accepted,scope="task",audience="task",sensitivity_status="unclassified",
          source_state="human_accepted_step" if human_accepted else "not_human_accepted")
        edge(root,stnode,"has_workflow_step")
        if st["run_id"] in run_by_id:
            edge(run_by_id[st["run_id"]],stnode,"run_reviewed_in_step")
    handoffs=load("handoffs",
        "SELECT id,status,hop,source_run_id,target_run_id,source_message_id,approved_by FROM team_task_agent_handoffs "
        "WHERE project_id=? AND task_id=? ORDER BY created_at DESC",
        (p,tid),MAX_HANDOFFS)
    for h in handoffs:
        hn=node("handoff",h["id"],status=h["status"],hop=h["hop"],
                approved_by=h["approved_by"],scope="task",audience="task",
                sensitivity_status="unclassified",source_state="operator_authorized" if h["approved_by"] is not None else "pending")
        edge(root,hn,"has_handoff")
        if h["source_run_id"] in run_by_id:
            edge(run_by_id[h["source_run_id"]],hn,"handoff_from_run")
        if h["target_run_id"] in run_by_id:
            edge(hn,run_by_id[h["target_run_id"]],"handoff_to_run")
    mapping=c.execute("SELECT workspace_id FROM team_project_workspace WHERE project_id=?",(p,)).fetchone()
    public=[]
    if mapping:
        # A publication is a NEW company-facing snapshot, not a copy of an
        # arbitrary private note. Only documents explicitly bound to this task qualify.
        public=load("publications",
         "SELECT id,title,status,published_by,source_json,revision,created_at "
         "FROM team_public_knowledge WHERE workspace_id=? AND status='published' "
         "AND json_extract(source_json,'$.project_id')=? "
         "AND json_extract(source_json,'$.task_id')=? ORDER BY created_at DESC",
         (mapping["workspace_id"],p,tid),MAX_PUBLICATIONS)
        for pub in public:
            origin=_json(pub["source_json"])
            source_id=origin.get("document_id")
            # Source document can have been deleted: keep the provenance
            # citation only if the source still exists and is readable here.
            pubnode=node("published_knowledge",pub["id"],title=pub["title"],
                         revision=pub["revision"],published_by=pub["published_by"],
                         source_document_id=source_id,source_revision=origin.get("document_revision"),
                         scope="workspace",audience="workspace",
                         sensitivity_status="unclassified",
                         source_state="explicitly_published_snapshot")
            edge(root,pubnode,"includes_published_snapshot")
            if source_id in doc_by_id:
                edge(doc_by_id[source_id],pubnode,"explicit_company_publication")
    else:
        counts["publications"]=0
    return {
        "task_id":tid,"project_id":p,"scope":"task","nodes":nodes,"edges":edges,
        "counts":counts,"partial":bool(partial),"partial_categories":partial,
        "source_authority":"stored_rows_not_model_inference",
        "human_adoption_distinct_from_model_completion":True,
        "history_snapshots_not_treated_as_adopted_knowledge":True,
        "no_implicit_cross_project_access":True,
        "source_sensitivity_classification_enabled":False,
        "warning":"本图是来源与操作回执索引；Agent完成不等于事实正确，管理员验收也不等于公司公开发布。"
    }


@router.get("/tasks/{tid}/evidence-graph")
def task_evidence_graph(tid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    task=s.object(tid,user.id,"task")
    p=task["project_id"]
    with s.connection() as c:
        return _task_graph(s,c,p,tid,user.id)
