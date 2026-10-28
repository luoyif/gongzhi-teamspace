"""A narrow Octop integration: identity, one database and stateless model calls.

This module deliberately never opens a private Octop chat, agent workspace,
tool runtime or instance-wide knowledge base on behalf of a project member.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .store import Problem, require_text
from .workspace import WorkspaceStore as Store

_store_init_lock = threading.Lock()


def store_for(server: Any) -> Store:
    """Use Octop's real SQLite file; project exports and blobs live beside it."""
    existing = getattr(server, "teamspace_store", None)
    if existing is not None:
        return existing
    # Sync FastAPI endpoints can first enter from different worker threads.
    # Store initialization marks stale runs interrupted, so it must happen once.
    with _store_init_lock:
        existing = getattr(server, "teamspace_store", None)
        if existing is not None:
            return existing
        if not server.database_bound:
            raise Problem(503, "数据库未初始化，请运行部署检查")
        db_path = getattr(server.services.db, "path", None)
        if not db_path:
            raise Problem(503, "第一阶段使用 SQLite，请勿配置 PostgreSQL 数据库")
        root = Path(server.services.paths.root)
        data_dir = root / "teamspace"
        data_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(data_dir, 0o700)
            for path in (Path(db_path), Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
                if path.exists():
                    os.chmod(path, 0o600)
        result = Store(db_path, data_dir)
        server.teamspace_store = result
        return result


def _provider_name(project_id: str) -> str:
    return "team-project-" + project_id


def _base_url(value: Any) -> str:
    text = require_text(value or "https://api.openai.com/v1", "模型地址", 1000, False).rstrip("/")
    parsed = urlsplit(text)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise Problem(422, "模型地址需为不含账号、查询参数或片段的完整 URL")
    local = parsed.hostname.lower() == "localhost"
    try:
        ip = ipaddress.ip_address(parsed.hostname)
        local = ip.is_loopback
        if not ip.is_global and not local:
            raise Problem(422, "模型地址不能指向私网或链路本地地址")
    except ValueError:
        pass
    if local:
        if os.environ.get("TEAMSPACE_ALLOW_LOCAL_MODELS") != "1":
            raise Problem(422, "本地模型需由部署管理员启用 TEAMSPACE_ALLOW_LOCAL_MODELS=1")
        if parsed.scheme not in ("http", "https"):
            raise Problem(422, "本地模型地址只支持 HTTP 或 HTTPS")
    elif parsed.scheme != "https":
        raise Problem(422, "远程模型地址必须使用 HTTPS")
    return text


def list_provider(server: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Only expose the provider already bound to this authorized project."""
    name = config.get("provider_name", "")
    row = server.services.provider_repo.get_by_name(name) if name else None
    if row is None or not name.startswith("team-project-"):
        return {"items": [], "configured": False}
    return {
        "items": [{"name": row.name, "kind": row.kind, "base_url": row.base_url,
                   "models": row.get_models(), "has_api_key": bool(row.api_key),
                   "enabled": bool(row.enabled)}],
        "configured": bool(row.enabled and config.get("model")),
    }


async def configure_provider(server: Any, project_id: str, body: dict[str, Any]) -> dict[str, str]:
    """Store a project-specific OpenAI-compatible provider without a billable probe.

The API adapter must check project-owner permission before calling this function.
Empty API-key input retains this project's existing key; changing the endpoint
requires entering the key again. Keys are never returned or included in errors.
"""
    kind = body.get("kind", "openai")
    if kind not in ("openai", "openai-compatible"):
        raise Problem(422, "第一阶段支持 OpenAI 兼容接口")
    model = require_text(body.get("model"), "模型名称", 200, False)
    name = _provider_name(project_id)
    repo = server.services.provider_repo
    old = repo.get_by_name(name)
    base_url = _base_url(body.get("base_url") or (old.base_url if old else None))
    supplied = body.get("api_key")
    if supplied is not None and (not isinstance(supplied, str) or len(supplied) > 8192):
        raise Problem(422, "API Key 格式不正确")
    key = supplied.strip() if isinstance(supplied, str) else ""
    from .presets import is_go
    if not key and old and old.base_url and old.base_url.rstrip("/") != base_url and not (is_go(old.base_url) and is_go(base_url)):
        raise Problem(422, "更改模型地址时请重新提供 API Key，避免误传旧凭证")
    if not key:
        key = old.api_key if old else None
    if not key:
        raise Problem(422, "请填写此项目的 API Key；无需认证的本地兼容服务可填写 local")
    from .presets import is_go, go_headers, GO_CHAT_MODELS
    if is_go(base_url):
        model = model.removeprefix("opencode-go/")
        from .go_models import model_info
        info=model_info(model)
        if info: base_url=info['base_url']
        elif model not in GO_CHAT_MODELS: raise Problem(422,"模型不在已核查的 Go 官方目录中，请刷新目录")
    values = {"kind": "openai", "base_url": base_url, "api_key": key,
              "extra_json": json.dumps({"headers": go_headers(base_url, name)}),
              "models_json": json.dumps([{"id": model, "name": model}], ensure_ascii=False),
              "note": "Teamspace project " + project_id}
    if old:
        repo.update(old.id, **values, enabled=True)
    else:
        repo.create(name=name, **values)
    store_for(server)  # Enforce data-file permissions after first configuration.
    return {"provider_name": name, "model": model}


def _usage(result: Any) -> dict[str, Any] | None:
    raw = getattr(result, "usage_metadata", None)
    if not isinstance(raw, dict):
        return None
    output: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            output[key] = value
    for key in ("input_token_details", "output_token_details"):
        details = raw.get(key)
        if isinstance(details, dict):
            output[key] = {k: v for k, v in details.items()
                           if isinstance(v, int) and not isinstance(v, bool) and v >= 0}
    # Cache/reasoning breakdowns are subsets; callers must not add them again.
    return dict(output, source="provider") if output else None


async def invoke_model(server: Any, config: dict[str, Any], messages: list[dict[str, str]]) -> dict[str, Any]:
    """Call the native Octop model factory, with no agent tools or private memory."""
    from octop.infra.agents.providers.probe import build_probe_chat_model
    import httpx

    name = config.get("provider_name", "")
    if not isinstance(name, str) or not name.startswith("team-project-"):
        raise Problem(422, "请先配置此项目的模型")
    row = server.services.provider_repo.get_by_name(name)
    if row is None or not row.enabled or row.kind != "openai":
        raise Problem(422, "项目模型配置不可用，请检查设置")
    _base_url(row.base_url)
    cap = config.get("max_output_tokens", 2048)
    if not isinstance(cap, int) or isinstance(cap, bool) or not 128 <= cap <= 8192:
        raise Problem(422, "模型输出上限应在 128–8192 token 之间")
    chat = build_probe_chat_model(row, model_id=config.get("model"))
    # The supported native OpenAI adapter owns an AsyncOpenAI client. Override
    # its retries before requesting: an ambiguous timeout must not silently
    # start additional paid generations. max_tokens remains a request limit.
    root_client = getattr(chat, "root_async_client", None)
    if root_client is None or not hasattr(root_client, "with_options"):
        raise Problem(503, "当前 Octop 模型适配器不支持第一阶段的请求限制，请检查固定依赖")
    # LangChain caches its default HTTP pools across newly built model objects.
    # Closing the factory's pool after one run breaks the next call. Give this
    # run an explicitly owned pool and close only that pool, never the cached
    # sync/async factory clients. Keep normal environment proxy handling.
    owned_transport = httpx.AsyncClient(timeout=120.0,follow_redirects=False,
        limits=httpx.Limits(max_connections=4,max_keepalive_connections=2))
    try:
        from .presets import go_headers
        chat.root_async_client = root_client.with_options(max_retries=0, timeout=120.0,http_client=owned_transport,default_headers=go_headers(row.base_url,name+(":"+config["conversation_task_id"] if config.get("conversation_task_id") else "")))
        chat.async_client = chat.root_async_client.chat.completions
        chat.max_tokens = cap
        result = await asyncio.wait_for(chat.ainvoke(messages), timeout=150.0)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise Problem(504, "模型请求超时；未自动重试，请确认用量后再发起") from None
    except Exception as exc:
        # Provider exceptions may contain endpoints, request data or secrets.
        raise Problem(502, "模型请求失败（" + type(exc).__name__ + "），请检查地址、模型和凭证") from None
    finally:
        await owned_transport.aclose()
    content = getattr(result, "content", "")
    if isinstance(content, list):
        content = "\n".join(item.get("text", "") for item in content
                            if isinstance(item, dict) and item.get("type") == "text")
    # Return accounting even for empty/truncated output; the controller records
    # usage before rejecting the business result. Never discard consumed tokens.
    metadata = getattr(result, "response_metadata", {}) or {}
    return {"content": content, "usage": _usage(result), "finish_reason": metadata.get("finish_reason")}


def build_team_app(server: Any):
    """Replace the wide Octop HTTP surface with the collaboration portal."""
    from fastapi import APIRouter, FastAPI, HTTPException
    from fastapi.responses import FileResponse
    from octop.api.app import _install_exception_handlers
    from octop.api.middleware.jwt_auth import install as install_jwt_auth
    from octop.api.middleware.setup_lockdown import install as install_setup_lockdown
    from octop.api.routers import auth

    from . import api

    app = FastAPI(title="共知 · Teamspace", version="0.16.1", docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.state.octop_server = server
    _install_exception_handlers(app)
    # Same-origin only; no wildcard CORS and no native shell/agent/workspace API.
    install_jwt_auth(app, server)
    install_setup_lockdown(app, server)
    identity = APIRouter()
    allowed = {("/logout", "POST"), ("/me", "GET"),
               ("/me", "PATCH"), ("/change-password", "POST")}
    for route in auth.router.routes:
        if any((getattr(route, "path", ""), method) in allowed
               for method in getattr(route, "methods", set())):
            identity.routes.append(route)
    from .password_auth import router as password_router
    app.include_router(password_router, prefix="/api/auth")
    app.include_router(identity, prefix="/api/auth")
    app.include_router(api.router, prefix="/api/team")
    from .file_folders import router as file_folder_router
    from .file_preview import router as file_preview_router
    from .skill_market_browser import router as skill_browser_router
    app.include_router(file_folder_router,prefix="/api/team")
    app.include_router(file_preview_router,prefix="/api/team")
    app.include_router(skill_browser_router,prefix="/api/team")
    from .local_skills import router as local_skill_router
    app.include_router(local_skill_router, prefix="/api/team")
    from .workspace_api import router as workspace_router
    app.include_router(workspace_router, prefix="/api/team")
    from .agent_api import router as agent_router
    app.include_router(agent_router, prefix="/api/team")
    from .platform_api import router as platform_router
    app.include_router(platform_router, prefix="/api/team")
    from .team_membership import router as people_router, public_router as people_setup
    from .integration_catalog import router as catalog_router
    app.include_router(people_router,prefix="/api/team")
    app.include_router(catalog_router,prefix="/api/team")
    from .model_providers import router as providers_router
    from .plugin_api import router as plugins_router
    app.include_router(providers_router,prefix="/api/team")
    app.include_router(plugins_router,prefix="/api/team")
    app.include_router(people_setup,prefix="/api/setup/team")
    app.include_router(api.setup_router, prefix="/api/setup/team")
    from .project_space import router as space_router
    from .skill_markets import router as skill_market_router
    from .mcp_markets import router as mcp_market_router
    app.include_router(space_router,prefix='/api/team')
    app.include_router(skill_market_router,prefix='/api/team')
    app.include_router(mcp_market_router,prefix='/api/team')
    from .admin_lifecycle import router as admin_router
    app.include_router(admin_router,prefix="/api/team")
    from .run_policy import router as run_policy_router
    from .run_activity import router as run_activity_router
    app.include_router(run_policy_router,prefix='/api/team')
    app.include_router(run_activity_router,prefix='/api/team')
    from .account_settings import router as account_router
    app.include_router(account_router,prefix='/api/team')
    from .avatars import router as avatar_router
    app.include_router(avatar_router,prefix='/api/team')
    from .task_live import router as task_live_router
    app.include_router(task_live_router,prefix='/api/team')
    from .speech_input import router as speech_router
    app.include_router(speech_router,prefix='/api/team')
    from .agent_handoff import router as handoff_router
    app.include_router(handoff_router,prefix='/api/team')
    from .task_workflows import router as task_workflow_router
    app.include_router(task_workflow_router,prefix='/api/team')
    from .task_evidence import router as task_evidence_router
    app.include_router(task_evidence_router,prefix='/api/team')
    from .company_evidence import router as company_evidence_router
    app.include_router(company_evidence_router,prefix='/api/team')
    api.install_lifecycle(app, server)

    @app.get("/api/setup/status")
    def setup_status():
        manager = server.user_manager
        cfg = server.services.config if server.services else getattr(server, "config", None)
        return {"setup_required": manager is None or manager.count() == 0,
                "database_bound": bool(server.database_bound),
                "require_setup_password": bool(getattr(cfg, "require_setup_password", True)),
                "product": "teamspace", "version": "0.16.1"}

    @app.get("/api/health")
    def health():
        if not server.database_bound:
            raise HTTPException(503, "database not ready")
        return {"ok": True, "product": "teamspace", "version": "0.16.1"}

    @app.middleware("http")
    async def response_headers(request, call_next):
        import time,logging
        started=time.perf_counter()
        response = await call_next(request)
        elapsed=(time.perf_counter()-started)*1000
        response.headers["Server-Timing"] = "app;dur="+str(round(elapsed,2))
        if request.url.path.startswith("/api/") and elapsed>800:
            logging.getLogger("teamspace.performance").warning("slow_request method=%s path=%s status=%s ms=%.1f",request.method,request.url.path,response.status_code,elapsed)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    web_dir = (Path(__file__).resolve().parent.parent / "web").resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def portal(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(404, "Not Found")
        relative = Path(full_path or "index.html")
        if relative.is_absolute() or any(part.startswith(".") for part in relative.parts):
            raise HTTPException(404, "Not Found")
        candidate = (web_dir / relative).resolve()
        if not candidate.is_relative_to(web_dir) or not candidate.is_file():
            raise HTTPException(404, "Not Found")
        response = FileResponse(candidate)
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app
