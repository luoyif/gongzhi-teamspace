"""The only project API surface. Every resource resolves current membership."""
from __future__ import annotations
import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter,BackgroundTasks,Body,Depends,File,Form,Query,Request,UploadFile
from fastapi.responses import FileResponse,JSONResponse
from octop.api.deps import current_user,get_server,sign_token
from octop.infra.users.identity import Role

from .store import Problem,dump,now,require_text,uid
from .jobs import Controller

router=APIRouter()
setup_router=APIRouter()
_account_lock=asyncio.Lock()


def store_for(server):
    from .integration import store_for as get
    return get(server)


def controller(server):
    if not hasattr(server,"teamspace_controller"):
        from .agent_controller import AgentController
        server.teamspace_controller=AgentController(server,store_for(server))
    server.teamspace_controller.start()
    return server.teamspace_controller


def install_lifecycle(app,server):
    @app.exception_handler(Problem)
    async def problem(_request,exc):
        return JSONResponse(status_code=exc.status,content={"detail":exc.detail})
    @app.on_event("startup")
    async def startup():
        if server.database_bound: controller(server)
    @app.on_event("shutdown")
    async def shutdown():
        pending=list(getattr(server,'team_model_jobs',set()))
        for job in pending: job.cancel()
        if pending: await asyncio.gather(*pending,return_exceptions=True)
        if hasattr(server,"teamspace_controller"): await server.teamspace_controller.close()


def profile(user):
    return {"id":user.id,"username":user.username,"display_name":user.display_name or user.username,"role":str(user.role)}


def session(server,user):
    ttl=server.services.config.access_token_ttl_seconds
    token=sign_token(server.services.secret_repo.get("jwt"),sub=user.id,uname=user.username,role=user.role,ttl_seconds=ttl)
    return {"access_token":token,"token_type":"Bearer","expires_in":ttl,"user":profile(user)}


def account_fields(body):
    username=require_text(body.get("username"),"用户名",64,False)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}",username): raise Problem(422,"用户名用3–64位字母、数字、点、下划线或短横线")
    password=body.get("password")
    if not isinstance(password,str) or not 12<=len(password)<=200: raise Problem(422,"密码需12–200个字符")
    name=require_text(body.get("display_name") or username,"显示名称",80,False)
    return username,password,name


@setup_router.post("/init",status_code=201)
async def initialize(body:dict=Body(...),server:Any=Depends(get_server)):
    username,password,name=account_fields(body)
    async with _account_lock:
        if not server.database_bound or server.user_manager is None: raise Problem(503,"数据库未初始化，请运行部署检查")
        if server.user_manager.count()!=0: raise Problem(410,"初始化已完成，请登录")
        if server.services.config.require_setup_password:
            from octop.infra.setup import password_file
            expected=password_file.read_password(Path.home())
            if not expected or not secrets.compare_digest(str(body.get("setup_password","")),expected): raise Problem(403,"请提供安装时生成的初始化口令")
        user=await server.user_manager.create(username=username,password=password,role=Role.ADMIN,display_name=name,locale="zh")
        return session(server,user)


def invite_row(c,token):
    if not isinstance(token,str) or len(token)>256: raise Problem(404,"邀请不存在或已失效")
    key=hashlib.sha256(token.encode()).hexdigest()
    row=c.execute("SELECT * FROM team_invites WHERE token_hash=?",(key,)).fetchone()
    if not row or row["used_at"] or row["expires_at"]<now(): raise Problem(404,"邀请不存在或已失效")
    creator=c.execute("SELECT role FROM team_members WHERE project_id=? AND user_id=?",(row["project_id"],row["created_by"])).fetchone()
    if not creator or creator[0]!="owner": raise Problem(404,"邀请已失效")
    return row


@setup_router.post("/redeem",status_code=201)
async def redeem(body:dict=Body(...),server:Any=Depends(get_server)):
    username,password,name=account_fields(body)
    s=store_for(server)
    async with _account_lock:
        with s.connection() as c: invitation=dict(invite_row(c,body.get("token")))
        if server.user_manager.get(username) is not None: raise Problem(409,"此用户名已存在；请用该账号登录后接受邀请")
        user=await server.user_manager.create(username=username,password=password,role=Role.USER,display_name=name,locale="zh")
        with s.connection(True) as c:
            invite_row(c,body.get("token"))
            c.execute("INSERT INTO team_members VALUES(?,?,?,?,?)",(invitation["project_id"],user.id,user.username,user.display_name or user.username,invitation["role"]))
            c.execute("UPDATE team_invites SET used_at=? WHERE token_hash=?",(now(),invitation["token_hash"]))
            s.enrol_project_member(c,invitation["project_id"],user)
            s.touch(c,invitation["project_id"])
        return dict(session(server,user),project_id=invitation["project_id"])


@router.post("/invites/join")
async def join_invite(body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    async with _account_lock:
        with s.connection(True) as c:
            invitation=invite_row(c,body.get("token"))
            c.execute("INSERT OR IGNORE INTO team_members VALUES(?,?,?,?,?)",(invitation["project_id"],user.id,user.username,user.display_name or user.username,invitation["role"]))
            c.execute("UPDATE team_invites SET used_at=? WHERE token_hash=?",(now(),invitation["token_hash"]))
            s.enrol_project_member(c,invitation["project_id"],user)
            s.touch(c,invitation["project_id"])
            return {"project_id":invitation["project_id"]}


@router.get("/projects")
def projects(user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).projects(user.id)}


@router.post("/projects",status_code=201)
async def create_project(body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).create_project(user,body)


@router.get("/projects/{p}")
def project(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).project(p,user.id)


@router.patch("/projects/{p}")
def patch_project(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).update_project(p,user.id,body)


@router.get("/projects/{p}/messages")
def messages(p:str,after:int=Query(0,ge=0),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).messages(p,user.id,after)


@router.post("/projects/{p}/messages",status_code=201)
def send(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).send(p,user,body)


@router.get("/projects/{p}/members")
def members(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).members(p,user.id)}


@router.post("/projects/{p}/members")
def member(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c: s.require(c,p,user.id,owner=True)
    target=server.user_manager.get(require_text(body.get("username"),"用户名",64,False))
    if target is None: raise Problem(404,"账号不存在，请先创建邀请链接")
    s.set_member(p,user.id,target,body.get("role","member"))
    return {"items":s.members(p,user.id)}


@router.delete("/projects/{p}/members/{target}")
def remove_member(p:str,target:int,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    store_for(server).remove_member(p,user.id,target)
    return {"ok":True}


@router.post("/projects/{p}/invites",status_code=201)
def invite(p:str,body:dict=Body(default={}),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    role=body.get("role","member")
    if role not in ("member","viewer"): raise Problem(422,"邀请角色只能为成员或只读")
    token=secrets.token_urlsafe(32)
    expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=72)).isoformat(timespec="milliseconds")
    s=store_for(server)
    with s.connection(True) as c:
        s.require(c,p,user.id,owner=True)
        c.execute("INSERT INTO team_invites(token_hash,project_id,role,created_by,created_at,expires_at) VALUES(?,?,?,?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),p,role,user.id,now(),expires))
    return {"token":token,"expires_at":expires,"role":role,"single_use":True}


@router.get("/projects/{p}/tasks")
def tasks(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).objects(p,user.id,"task")}


@router.post("/projects/{p}/tasks",status_code=201)
def create_task(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).create_task(p,user.id,body)


@router.get("/tasks/{id}")
def task(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).object(id,user.id,"task")


@router.patch("/tasks/{id}")
def patch_task(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).update_task(id,user.id,body)


@router.get("/projects/{p}/calendar")
def calendar(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).calendar(p,user.id)}


@router.post("/projects/{p}/events",status_code=201)
def event(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).create_event(p,user.id,body)


@router.patch("/events/{id}")
def patch_event(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection(True) as c:
        row=s.object_row(c,id,user.id,True,"event"); s.revision(row,body)
        old=s.object_json(row); values=dict(old); values.update(body)
        values["kind"]=body.get("kind",old.get("event_kind","meeting"))
        title,text,data=s.validate_event(values)
        seq=data.get("source_seq")
        if seq is not None and not c.execute("SELECT 1 FROM team_messages WHERE project_id=? AND seq=?",(row["project_id"],seq)).fetchone(): raise Problem(422,"安排引用了不存在的项目消息")
        status=body.get("status",row["status"])
        if status not in ("active","cancelled"): raise Problem(422,"安排状态无效")
        c.execute("UPDATE team_objects SET title=?,body=?,data_json=?,status=?,revision=revision+1,updated_at=? WHERE id=?",(title,text,dump(data),status,now(),id)); s.touch(c,row["project_id"])
    return s.object(id,user.id,"event")


@router.get("/projects/{p}/documents")
def documents(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).objects(p,user.id,"document")}


@router.get("/documents/{id}")
def document(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).object(id,user.id,"document")


@router.get("/documents/{id}/download")
def download(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    path,name=store_for(server).blob(id,user.id)
    return FileResponse(path,filename=name,media_type="application/octet-stream",headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})


@router.post("/projects/{p}/uploads",status_code=201)
async def upload(p:str,file:UploadFile=File(...),origin:str=Form("library"),source_seq:int|None=Form(None),task_id:str|None=Form(None),folder_id:str|None=Form(None),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c: s.require(c,p,user.id,write=True)
    with s.connection(True) as c:
        s.require(c,p,user.id,write=True)
        if task_id is not None or origin=="chat": task_id=s.conversation_task(c,p,task_id)
    pieces=[]; count=0
    while chunk:=await file.read(1024*1024):
        count+=len(chunk)
        if count>20*1024*1024: raise Problem(413,"单个文件最大20MB")
        pieces.append(chunk)
    if not count: raise Problem(422,"文件不能为空")
    filename=re.sub(r"[\x00-\x1f\x7f]","",(file.filename or "attachment").replace("\\","/").split("/")[-1])[:240] or "attachment"
    result=s.register_upload(p,user.id,filename,b"".join(pieces),origin,source_seq,folder_id)
    if task_id:
        with s.connection(True) as c:
            row=s.object_row(c,result['id'],user.id,True,'document')
            d=json.loads(row['data_json']);d['task_ids']=list(dict.fromkeys(d.get('task_ids',[])+[task_id]));d.setdefault('task_id',task_id)
            c.execute('UPDATE team_objects SET data_json=? WHERE id=?',(dump(d),result['id']));s.touch(c,p)
    if origin=="chat":
        with s.connection(True) as c:
            s.require(c,p,user.id,write=True)
            s.add_message(c,p,user.id,user.display_name or user.username,("再次上传：" if result["duplicate"] else "上传资料：")+filename,"upload:"+uid(),"human",meta={"task_id":task_id,"attachments":[{"id":result["id"],"title":filename,"duplicate":result["duplicate"]}]})
    controller(server)
    return result


@router.post("/projects/{p}/notes",status_code=201)
def note(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).create_note(p,user.id,body)


@router.patch("/documents/{id}")
def patch_document(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection(True) as c:
        row=s.object_row(c,id,user.id,True,"document"); s.revision(row,body)
        data=json.loads(row["data_json"])
        if data.get("document_kind","file")=="file" and "body" in body: raise Problem(422,"上传原件不可改写；请创建新版本或知识条目")
        title=require_text(body.get("title",row["title"]),"标题",240,False)
        text=require_text(body.get("body",row["body"]),"正文",500000)
        if "adopted" in body: data["adopted"]=bool(body["adopted"])
        c.execute("UPDATE team_objects SET title=?,body=?,data_json=?,revision=revision+1,updated_at=? WHERE id=?",(title,text,dump(data),now(),id))
        if row["status"]=="ready": s.index(c,id,row["project_id"],[("正文",text)],title)
        s.touch(c,row["project_id"])
    return s.object(id,user.id,"document")


@router.post("/documents/{id}/supersede")
def supersede(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).supersede(id,user.id,body.get("replacement_id"),body.get("expected_revision"))


@router.post("/documents/{id}/retry")
def retry_parse(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection(True) as c:
        row=s.object_row(c,id,user.id,True,"document")
        if row["status"] not in ("failed","unindexed"): raise Problem(409,"当前资料不需要重试")
        c.execute("UPDATE team_objects SET status='uploaded',updated_at=? WHERE id=?",(now(),id))
    return {"ok":True}


@router.get("/projects/{p}/search")
def search(p:str,q:str=Query("",max_length=1000),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).search(p,user.id,q,12),"retrieval":"project_scoped_lexical"}


@router.get("/projects/{p}/settings")
def settings(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return store_for(server).settings(p,user.id)


@router.put("/projects/{p}/settings")
@router.patch("/projects/{p}/settings")
def save_settings(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c:s.require(c,p,user.id,owner=True)
    raise Problem(409,'提示词、模型、Skills和执行限制请在公司能力中心维护')


@router.get("/projects/{p}/providers")
def providers(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    from .integration import list_provider
    cfg=store_for(server).settings(p,user.id)
    from .presets import public_preset
    result=list_provider(server,cfg)
    result["server_preset"]=public_preset(server,user)
    return result


@router.post("/projects/{p}/provider-preset")
async def bind_preset(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    from .presets import apply_preset
    s=store_for(server)
    with s.connection() as c:s.require(c,p,user.id,owner=True)
    raise Problem(409,'服务器模型预设请在公司能力中心绑定')


@router.post("/projects/{p}/provider")
async def configure_provider(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c:s.require(c,p,user.id,owner=True)
    raise Problem(409,'模型连接已移至公司能力中心，项目只启用能力版本')


@router.get("/projects/{p}/runs")
async def runs(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":controller(server).runs(p,user.id)}


@router.post("/projects/{p}/runs",status_code=202)
async def run(p:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return controller(server).start_run(p,user,body)


@router.get("/projects/{p}/proposals")
def proposals(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {"items":store_for(server).objects(p,user.id,"proposal")}


@router.patch("/proposals/{id}")
def patch_proposal(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection(True) as c:
        row=s.object_row(c,id,user.id,True,"proposal"); s.revision(row,body)
        if row["status"]!="pending": raise Problem(409,"此结果卡已处理")
        data=json.loads(row["data_json"])
        for key in ("tasks","events","decisions"):
            if key in body:
                if not isinstance(body[key],list) or len(body[key])>10 or any(not isinstance(x,dict) for x in body[key]): raise Problem(422,"每类候选项最多10条")
                data[key]=body[key]
        if len(dump(data))>100000: raise Problem(422,"结果卡内容过大")
        status=body.get("status",row["status"])
        if status not in ("pending","dismissed"): raise Problem(422,"无效处理状态")
        c.execute("UPDATE team_objects SET data_json=?,status=?,revision=revision+1,updated_at=? WHERE id=?",(dump(data),status,now(),id)); s.touch(c,row["project_id"])
    return s.object(id,user.id,"proposal")


@router.post("/proposals/{id}/adopt")
async def adopt(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return controller(server).adopt(id,user.id,body)


@router.get("/projects/{p}/export")
async def export(p:str,background_tasks:BackgroundTasks,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server); s.project(p,user.id)
    def build():
        with s.export_lock:
            s.export_project(p)
            fd,path=tempfile.mkstemp(suffix=".zip"); os.close(fd)
            root=s.data_dir/"exports"/p
            try:
                with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
                    for f in root.rglob("*"):
                        if f.is_file(): z.write(f,str(f.relative_to(root)))
            except BaseException:
                os.unlink(path); raise
            return path
    path=await asyncio.to_thread(build)
    try: s.project(p,user.id)
    except BaseException:
        os.unlink(path); raise
    background_tasks.add_task(os.unlink,path)
    return FileResponse(path,filename=f"{p}-markdown.zip",media_type="application/zip",background=background_tasks,headers={"Cache-Control":"no-store"})


@router.get("/records/{id}/history")
def history(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    s=store_for(server)
    with s.connection() as c:
        s.object_row(c,id,user.id)
        return {"items":[{"revision":x["revision"],"created_at":x["created_at"],"snapshot":json.loads(x["snapshot_json"])} for x in c.execute("SELECT * FROM team_history WHERE object_id=? ORDER BY revision DESC",(id,))]}
