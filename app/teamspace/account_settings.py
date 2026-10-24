"""Self-service profile settings using native password hashing and lockout.
Never accepts a target user ID, role, username or model credential. Existing
chat authorship snapshots are retained; membership labels follow the new name.
"""
from typing import Any
from fastapi import APIRouter,Depends
from pydantic import BaseModel,Field,ConfigDict,field_validator
from octop.api.deps import current_user,get_server
from octop.api.routers.auth import _user_json
from .store import Problem
router=APIRouter()

class NameBody(BaseModel):
 model_config=ConfigDict(extra='forbid')
 display_name:str=Field(min_length=1,max_length=80)
 @field_validator('display_name')
 @classmethod
 def clean(cls,value):
  value=value.strip()
  if not value or any(ord(c)<32 for c in value):raise ValueError('请填写1–80字的显示名称，不含控制字符')
  return value

class PasswordBody(BaseModel):
 model_config=ConfigDict(extra='forbid')
 old_password:str=Field(min_length=1,max_length=200)
 new_password:str=Field(min_length=12,max_length=200)
 confirm_password:str=Field(min_length=12,max_length=200)

@router.get('/account')
def read_account(user:Any=Depends(current_user),server:Any=Depends(get_server)):
 row=server.user_manager.get_row(user.id)
 return {'user':_user_json(user,locale=user.locale),'has_password':bool(row and row.password_hash),'login_name_editable':False}

@router.patch('/account')
async def update_account(body:NameBody,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 await server.user_manager.set_display_name(user.username,body.display_name)
 from .integration import store_for
 store=store_for(server)
 with store.connection(True) as c:
  # Only denormalized membership labels, never old messages or author IDs.
  for table in ('team_members','team_workspace_members'):
   cols={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
   if {'user_id','display_name'}<=cols:c.execute('UPDATE '+table+' SET display_name=? WHERE user_id=?',(body.display_name,user.id))
 fresh=server.user_manager.get(user.username)
 return {'user':_user_json(fresh,locale=fresh.locale),'historical_messages_unchanged':True}

@router.post('/account/password')
async def update_password(body:PasswordBody,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 if body.new_password!=body.confirm_password:raise Problem(422,'两次新密码不一致')
 if body.new_password==body.old_password:raise Problem(422,'新密码不能与当前密码相同')
 server.user_manager.raise_if_login_locked(user.username)
 verified=await server.user_manager.authenticate(user.username,body.old_password)
 if verified is None:raise Problem(422,'当前密码不正确；连续失败会触发账号保护')
 await server.user_manager.change_password(user.username,body.old_password,body.new_password)
 # Native JWT is stateless. The UI clears its current session; do not claim all
 # other sessions were revoked or rotate the shared signing key globally.
 return {'changed':True,'relogin_required':True,'other_sessions_revoked':False}
