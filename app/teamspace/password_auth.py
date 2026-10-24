"""Portal password login, intentionally without a CAPTCHA dependency.

Keeps native password verification, account lockout, JWT and audit behavior.
This router is mounted only in the restricted Teamspace application.
"""
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from octop.api.deps import get_server, sign_token
from octop.api.routers.auth import _user_json
from octop.infra.errors import ErrorCode, OctopError

router = APIRouter()

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)

@router.get('/captcha')
def captcha_status():
    return {'provider': 'none', 'required': False}

@router.post('/login')
async def password_login(body: LoginBody, server: Any = Depends(get_server)):
    if server.user_manager.count() == 0:
        raise OctopError(ErrorCode.SETUP_REQUIRED, 'initial admin not created')
    server.user_manager.raise_if_login_locked(body.username)
    user = await server.user_manager.authenticate(body.username, body.password)
    if user is None:
        raise OctopError(ErrorCode.AUTH_FAILED, 'invalid credentials')
    ttl = server.services.config.access_token_ttl_seconds
    token = sign_token(server.services.secret_repo.get('jwt'), sub=user.id,
                       uname=user.username, role=user.role, ttl_seconds=ttl)
    return {'access_token': token, 'token_type': 'Bearer', 'expires_in': ttl,
            'user': _user_json(user, locale=user.locale)}
