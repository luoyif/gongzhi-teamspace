"""Company navigation, task threads and explicit public knowledge publication."""
from typing import Any
import asyncio
from fastapi import APIRouter,Depends,Body,Query
from octop.api.deps import current_user,get_server
from .api import store_for,controller
from .store import Problem,require_text
router=APIRouter()

@router.get('/workspaces')
def workspaces(user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {'items':store_for(server).workspaces(user)}

@router.post('/workspaces',status_code=201)
def new_workspace(body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).create_workspace(user,body)

@router.patch('/workspaces/{w}')
def edit_workspace(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).update_workspace(w,user.id,body)

@router.get('/workspaces/{w}/overview')
def overview(w:str,view:str=Query("all"),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    if view in ("calendar","projects"):return s.workspace_navigation(w,user.id,view)
    return s.workspace_overview(w,user.id)

@router.get('/workspaces/{w}/members')
def members(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {'items':store_for(server).workspace_members(w,user.id)}

@router.post('/workspaces/{w}/members')
def add_member(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c:s.workspace_require(c,w,user.id,owner=True)
    target=server.user_manager.get(require_text(body.get('username'),'用户名',64,False))
    if target is None:raise Problem(404,'账号不存在。新同事请先通过项目邀请注册。')
    s.set_workspace_member(w,user.id,target,body.get('role','member'))
    return {'items':s.workspace_members(w,user.id)}

@router.delete('/workspaces/{w}/members/{target}')
def remove_member(w:str,target:int,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    store_for(server).remove_workspace_member(w,user.id,target);return {'ok':True}

@router.get('/tasks/{t}/messages')
def task_messages(t:str,after:int=Query(0,ge=0),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(t,user.id,'task')
    return s.messages(task['project_id'],user.id,after,t)

@router.post('/tasks/{t}/messages',status_code=201)
async def task_send(t:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server);task=s.object(t,user.id,'task')
    result=await asyncio.to_thread(s.send,task['project_id'],user,dict(body,task_id=t))
    from .task_live import publish
    publish(t,'message',{'seq':result['seq']})
    return result

@router.post('/tasks/{t}/runs',status_code=202)
async def task_run(t:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    task=store_for(server).object(t,user.id,'task')
    return controller(server).start_run(task['project_id'],user,dict(body,task_id=t))

@router.get('/workspaces/{w}/knowledge')
def knowledge(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {'items':store_for(server).public_knowledge(w,user.id)}

@router.get('/knowledge/{kid}')
def knowledge_detail(kid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).public_document(kid,user.id)

@router.post('/workspaces/{w}/knowledge/publish',status_code=201)
def publish(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).publish_document(w,body.get('document_id'),user.id,body.get('expected_revision'))

@router.delete('/workspaces/{w}/knowledge/{kid}')
def withdraw(w:str,kid:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).withdraw_knowledge(w,kid,user.id)
