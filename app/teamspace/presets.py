"""Server-owned provider presets. Keys never enter browser responses or exports."""
from __future__ import annotations
import json
import os
import stat
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from .store import Problem

GO_BASE = 'https://opencode.ai/zen/go/v1'
CLIENT_ID = 'gongzhi-teamspace/0.3.0'
# Reviewed chat/completions models only. Responses/Messages need another adapter.
GO_CHAT_MODELS = frozenset(('deepseek-v4.1-flash','deepseek-v4-pro','glm-5.1','glm-5.2','glm-5.3','glm-5.3-flash','kimi-k2.6','kimi-k2.7-code','kimi-k3','mimo-v2.5','mimo-v2.5-pro','mimo-v2.6-flash','mimo-v2.6-pro','hy3','hy4-preview','longcat-2.0'))

def is_go(base_url):
    from .go_models import is_go_url
    return is_go_url(base_url)

def go_headers(base_url, project_provider):
    if not is_go(base_url): return {}
    # A project currently has one shared conversation; never expose its title/users.
    session=str(uuid.uuid5(uuid.NAMESPACE_URL,'gongzhi-teamspace:'+project_provider))
    return {'User-Agent':CLIENT_ID,'x-opencode-session':session}

def is_site_admin(user):
    return getattr(user.role,'value',str(user.role))=='admin'

def read_preset(server, user):
    if not is_site_admin(user): return None
    folder=Path(server.services.paths.root)/'credentials'
    path=folder/'opencode-go.json'
    if not path.exists(): return None
    try:
        cfg=json.loads(path.read_text(encoding='utf-8'))
        if cfg.get('enabled') is not True: return None
        if cfg.get('base_url') != GO_BASE or cfg.get('model') not in GO_CHAT_MODELS:
            raise ValueError('Unreviewed preset configuration')
        cap=cfg.get('max_output_tokens',4096)
        if type(cap) is not int or not 128<=cap<=8192: raise ValueError('Invalid cap')
        keyfile=folder/'opencode-go.key'
        if os.name=='posix':
            for p in (folder,path,keyfile):
                if stat.S_IMODE(p.stat().st_mode)&0o077: raise ValueError('Unsafe permissions')
        key=keyfile.read_text(encoding='utf-8').strip()
        if not key or len(key)>8192: raise ValueError('Missing credential')
        return {'kind':'openai-compatible','base_url':GO_BASE,'model':cfg['model'],'api_key':key,'max_output_tokens':cap}
    except (OSError,ValueError,TypeError,AttributeError):
        raise Problem(503,'服务器 OpenCode Go 预设不可用，请检查本地凭证和文件权限；未调用模型') from None

def public_preset(server,user):
    cfg=read_preset(server,user)
    return {'available':bool(cfg),'name':'OpenCode Go · 开发助手','model':cfg['model'] if cfg else None,'scope':'coding_agent','automatic_fallback':False}

async def apply_preset(server,project_id,user):
    from .integration import configure_provider,store_for
    if not is_site_admin(user): raise Problem(403,'仅工作空间管理员可以绑定服务器预设凭证')
    s=store_for(server)
    with s.connection() as c: s.require(c,project_id,user.id,owner=True)
    cfg=read_preset(server,user)
    if cfg is None: raise Problem(409,'尚未设置服务器模型预设')
    result=await configure_provider(server,project_id,cfg)
    current=s.settings(project_id,user.id)
    return s.save_settings(project_id,user.id,{'expected_revision':current['revision'],**result,'max_output_tokens':cfg['max_output_tokens']},provider_allowed=True)
