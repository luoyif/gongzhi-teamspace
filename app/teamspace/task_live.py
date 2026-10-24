"""Task-scoped, authenticated live collaboration. Presence is ephemeral, never stored."""
from __future__ import annotations
import asyncio
import json
import secrets
import time
from typing import Any
from fastapi import APIRouter, Depends, Body, Request
from fastapi.responses import StreamingResponse
from octop.api.deps import current_user, get_server
from .api import store_for
from .store import Problem

router = APIRouter()
ROOMS: dict[str, dict[str, tuple[int, asyncio.Queue]]] = {}
TYPING_LAST: dict[tuple[str, int], float] = {}
MAX_CLIENTS = 40

def online_ids(task_id: str) -> list[int]:
    return sorted({uid for uid, _ in ROOMS.get(task_id, {}).values()})

def publish(task_id: str, kind: str, payload: dict | None = None) -> None:
    """Call on the application's event loop only; no text or credentials in events."""
    room = ROOMS.get(task_id, {})
    data = {"type": kind, **(payload or {})}
    for _uid, queue in list(room.values()):
        if queue.full():
            try:
                queue.get_nowait()  # stale notification; the client re-fetches from SQLite
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

def publish_presence(task_id: str) -> None:
    publish(task_id, "presence", {"online_ids": online_ids(task_id)})

def event(kind: str, payload: dict) -> str:
    return "event: " + kind + "\ndata: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n\n"

@router.get("/tasks/{task_id}/live")
async def task_live(task_id: str, request: Request, user: Any = Depends(current_user), server: Any = Depends(get_server)):
    s = store_for(server)
    task = s.object(task_id, user.id, "task")
    project = task["project_id"]

    async def messages():
        room = ROOMS.setdefault(task_id, {})
        if len(room) >= MAX_CLIENTS:
            yield event("error", {"reason": "too_many_viewers"})
            return
        session = secrets.token_urlsafe(18)
        q: asyncio.Queue = asyncio.Queue(maxsize=24)
        room[session] = (user.id, q)
        publish_presence(task_id)
        try:
            yield event("presence", {"online_ids": online_ids(task_id), "scope": "viewing_current_task"})
            while True:
                if await request.is_disconnected():
                    return
                # Permissions are checked periodically even on an idle stream.
                with s.connection() as c:
                    try:
                        s.require(c, project, user.id)
                        current = c.execute("SELECT status FROM team_objects WHERE id=? AND project_id=? AND kind='task'", (task_id, project)).fetchone()
                        if not current or current[0] == 'deleted' or s.deleted(c, task_id):
                            raise Problem(404, "任务已删除")
                    except Problem:
                        yield event("access_revoked", {"reason": "access_changed"})
                        return
                try:
                    notification = await asyncio.wait_for(q.get(), timeout=6.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield event(notification["type"], {k: v for k, v in notification.items() if k != "type"})
        finally:
            room.pop(session, None)
            if not room:
                ROOMS.pop(task_id, None)
            else:
                publish_presence(task_id)

    return StreamingResponse(messages(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store", "X-Accel-Buffering": "no", "X-Content-Type-Options": "nosniff",
    })

@router.post("/tasks/{task_id}/typing")
async def task_typing(task_id: str, body: dict = Body(...), user: Any = Depends(current_user), server: Any = Depends(get_server)):
    s = store_for(server)
    task = s.object(task_id, user.id, "task")
    with s.connection() as c:
        s.require(c, task["project_id"], user.id, write=True)
    active = body.get("active")
    if type(active) is not bool:
        raise Problem(422, "输入状态必须是布尔值")
    k = (task_id, user.id)
    now = time.monotonic()
    if active and now - TYPING_LAST.get(k, 0) < 1.1:
        return {"ok": True, "throttled": True}
    TYPING_LAST[k] = now
    if len(TYPING_LAST) > 400:
        TYPING_LAST.clear()
    publish(task_id, "typing", {"user_id": user.id, "active": active, "expires_ms": 4200})
    return {"ok": True}

__all__ = ["router", "online_ids", "publish", "publish_presence", "event"]
