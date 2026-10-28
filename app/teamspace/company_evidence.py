"""Company knowledge provenance, with separate project-source disclosure.

Company membership gives access to explicitly published snapshots ONLY.
Original project/file/task metadata is revealed only after an independent,
fresh check of membership in that source project.

No LLM inference, no shared Agent's credentials, no raw documents or secrets.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends
from octop.api.deps import current_user, get_server
from .api import store_for

router=APIRouter()
MAX_COMPANY_PUBLICATIONS=100
MAX_ACCESSIBLE_PROJECTS=80


def _fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _source(raw):
    try:
        value=json.loads(raw or "{}")
    except (ValueError,TypeError):
        return {}
    return value if isinstance(value,dict) else {}


def _company_graph(s,c,w,actor):
    # Never infer org authority from a project-level Agent configuration.
    s.workspace_require(c,w,actor)
    workspace=c.execute("SELECT id,name FROM team_workspaces WHERE id=?",(w,)).fetchone()
    seen=set();edges=[];edge_keys=set();nodes=[]
    def add(kind,raw_id,**fields):
        key=f"{kind}:{raw_id}"
        if key not in seen:
            seen.add(key)
            nodes.append({"id":key,"type":kind,**fields})
        return key
    def connect(a,b,relation):
        tag=(a,b,relation)
        if a in seen and b in seen and tag not in edge_keys:
            edge_keys.add(tag)
            edges.append({"from":a,"to":b,"relation":relation})
    root=add("workspace",w,title=workspace["name"],audience="workspace")
    projects=c.execute("""SELECT p.id,p.title,p.revision
       FROM team_project_workspace link
       JOIN team_projects p ON p.id=link.project_id
       JOIN team_members m ON m.project_id=p.id AND m.user_id=?
       WHERE link.workspace_id=?
       AND NOT EXISTS (SELECT 1 FROM team_admin_trash tr WHERE tr.target_id=p.id AND tr.restored_at IS NULL)
       ORDER BY p.updated_at DESC LIMIT ?""",
       (actor,w,MAX_ACCESSIBLE_PROJECTS+1)).fetchall()
    project_partial=len(projects)>MAX_ACCESSIBLE_PROJECTS
    visible={}
    for proj in projects[:MAX_ACCESSIBLE_PROJECTS]:
        # Checking both project membership and workspace membership is required.
        s.require(c,proj["id"],actor)
        visible[proj["id"]]=add("project",proj["id"],title=proj["title"],
            revision=proj["revision"],audience="project")
    # Count before projection, so the UI can mark partial results accurately.
    total=c.execute("SELECT COUNT(*) FROM team_public_knowledge "
                    "WHERE workspace_id=? AND status='published'",(w,)).fetchone()[0]
    pubs=c.execute("SELECT id,title,body,source_json,revision,published_by,created_at "
        "FROM team_public_knowledge WHERE workspace_id=? AND status='published' "
        "ORDER BY updated_at DESC LIMIT ?",(w,MAX_COMPANY_PUBLICATIONS)).fetchall()
    allowed=0; restricted=0; stale=0
    for pub in pubs:
        origin=_source(pub["source_json"])
        source_project=origin.get("project_id")
        has_access=source_project in visible
        # Do not return source IDs, source title or message IDs when inaccessible.
        source_visibility="authorized" if has_access else "restricted"
        if has_access:allowed+=1
        else:restricted+=1
        knode=add("published_knowledge",pub["id"],
            title=pub["title"],revision=pub["revision"],
            body_sha256=_fingerprint(pub["body"]),published_by=pub["published_by"],
            published_at=pub["created_at"],audience="workspace",
            source_visibility=source_visibility,
            source_state="explicitly_published_snapshot",
            sensitivity_status="unclassified")
        connect(root,knode,"workspace_published_snapshot")
        if not has_access:
            continue
        source_document=origin.get("document_id")
        if not isinstance(source_document,str) or not source_document:continue
        row=c.execute("""SELECT id,project_id,title,revision,status,body,data_json
                         FROM team_objects WHERE id=? AND project_id=? AND kind='document'
                         AND status!='deleted'""",
                      (source_document,source_project)).fetchone()
        if not row:
            stale+=1
            continue
        # This published snapshot is immutable with respect to later private edits.
        dnode=add("document",row["id"],title=row["title"],
            revision=row["revision"],published_source_revision=origin.get("document_revision"),
            current_matches_published_revision=(row["revision"]==origin.get("document_revision")),
            status=row["status"],project_id=source_project,body_sha256=_fingerprint(row["body"]),
            audience="project",sensitivity_status="unclassified",
            source_state="source_document_accessible_not_automatically_published")
        connect(dnode,knode,"document_explicitly_published_as_snapshot")
        connect(visible[source_project],dnode,"project_contains_source")
        data=_source(row["data_json"])
        tid=origin.get("task_id")
        if not isinstance(tid,str) or not tid:continue
        task=c.execute("""SELECT id,title,revision FROM team_objects
              WHERE project_id=? AND id=? AND kind='task' AND status!='deleted'""",
              (source_project,tid)).fetchone()
        if task:
            tasknode=add("task",task["id"],title=task["title"],revision=task["revision"],project_id=source_project,
                         audience="project",source_state="original_project_task")
            connect(visible[source_project],tasknode,"project_contains_task")
            connect(tasknode,dnode,"task_contains_adopted_document")
    return {
      "workspace_id":w,"audience":"workspace",
      "nodes":nodes,"edges":edges,
      "counts":{"published_total":total,"published_shown":len(pubs),
                "visible_source_count":allowed,
                "restricted_source_count":restricted,"missing_or_deleted_sources":stale,
                "accessible_projects":len(visible)},
      "partial":project_partial or total>MAX_COMPANY_PUBLICATIONS,
      "partial_categories":[x for x,enabled in (
          ("projects",project_partial),("published_knowledge",total>MAX_COMPANY_PUBLICATIONS)) if enabled],
      "authorization":"workspace_publications_and_independently_authorized_project_sources",
      "sensitivity_classification_enabled":False,
      "note":"团队成员可查看已发布知识快照；原始任务和文件来源只向当前拥有项目访问权的成员展示。"
    }


@router.get("/workspaces/{w}/knowledge-graph")
def workspace_knowledge_graph(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c:
        return _company_graph(s,c,w,user.id)
