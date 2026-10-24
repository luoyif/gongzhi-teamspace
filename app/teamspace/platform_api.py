"""Company capability library and project binding APIs; no project clones."""
from __future__ import annotations
import asyncio
import io
import json
import zipfile
from typing import Any
from fastapi import APIRouter,Body,Depends
from fastapi.responses import Response
from octop.api.deps import current_user,get_server
from .platform_registry import PlatformRegistry,HARNESS_DEFAULTS
from .store import Problem,dump,now
from .presets import is_site_admin

router=APIRouter()
_model_lock=asyncio.Lock()


def registry(server):
    from .integration import store_for
    return PlatformRegistry(store_for(server))


@router.get('/workspaces/{w}/platform')
def catalog(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    r=registry(server);result=r.catalog(w,user.id)
    with r.store.connection() as c:role=r.store.workspace_require(c,w,user.id)['role']
    result.update(can_manage=role=='owner',can_manage_mcp=role=='owner' and is_site_admin(user),harness_defaults=HARNESS_DEFAULTS)
    return result


@router.post('/workspaces/{w}/platform/assets',status_code=201)
async def create(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    async with _model_lock:
        return registry(server).save_asset(w,user.id,body.get('kind'),body,site_admin=is_site_admin(user))


@router.patch('/platform/assets/{id}')
async def edit(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    async with _model_lock:
        r=registry(server);a=r.get(id,user.id)
        return r.save_asset(a['workspace_id'],user.id,a['kind'],body,id,site_admin=is_site_admin(user))


@router.get('/platform/assets/{id}/history')
def history(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return {'items':registry(server).history(id,user.id)}


@router.post('/platform/assets/{id}/restore')
async def restore(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    async with _model_lock:
        return registry(server).restore_version(id,user.id,body,is_site_admin(user))


@router.get('/projects/{p}/platform-bindings')
def bindings(p:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    r=registry(server)
    with r.store.connection() as c:w=r.workspace_for_project(c,p,user.id)
    return {'items':r.bindings(p,user.id),'workspace_id':w,'mode':'pinned_dependency_bundle'}


@router.put('/projects/{p}/platform-bindings/{id}')
def bind(p:str,id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    return registry(server).bind(p,user.id,id,body)


@router.get('/platform/assets/{id}/usage')
def usage(id:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    r=registry(server);a=r.require_manage_asset(id,user.id)
    with r.store.connection() as c:
        # Return project names only where the operator has project permission.
        rows=[];count=0
        for raw in c.execute('SELECT * FROM team_platform_bindings WHERE enabled=1'):
            bundle=json.loads(raw['bundle_json'])
            if not any(x['id']==id for x in bundle['assets']):continue
            count+=1
            try:r.store.require(c,raw['project_id'],user.id)
            except Problem:continue
            p=c.execute('SELECT title FROM team_projects WHERE id=?',(raw['project_id'],)).fetchone()
            rows.append({'project_id':raw['project_id'],'project_title':p[0],'root_asset_id':raw['asset_id'],'binding_revision':raw['revision'],'pinned_revision':next(x['revision'] for x in bundle['assets'] if x['id']==id)})
    return {'items':rows,'total_bindings':count,'hidden_project_bindings':count-len(rows)}


async def configure_model(r,server,a,user,body):
    from .integration import configure_provider
    with r.store.connection() as c:
        r.manage(c,a['workspace_id'],user.id);r.store.revision(a,body)
    if a['kind']!='model':raise Problem(422,'只能为模型资产配置连接')
    native_name=a['data'].get('provider_name')
    provider_scope=native_name.removeprefix('team-project-') if native_name else 'platform-'+a['workspace_id']+'-'+a['id']
    result=await configure_provider(server,provider_scope,body)
    row=server.services.provider_repo.get_by_name(result['provider_name'])
    data={'provider_name':row.name,'model':result['model'],'base_url':row.base_url,'configured':True}
    with r.store.connection(True) as c:
        current=r.get(a['id'],user.id,'model',c);r.store.revision(current,body)
        c.execute('INSERT INTO team_platform_versions VALUES(?,?,?,?)',(a['id'],current['revision'],dump(current),now()))
        c.execute('UPDATE team_platform_assets SET data_json=?,enabled=1,revision=revision+1,updated_at=? WHERE id=?',(dump(data),now(),a['id']))
    return r.get(a['id'],user.id)


@router.post('/platform/assets/{id}/model-connection')
async def model_connection(id:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    async with _model_lock:
        r=registry(server);a=r.require_manage_asset(id,user.id)
        return await configure_model(r,server,a,user,body)


@router.put('/workspaces/{w}/platform/default-model')
def default_model(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    r=registry(server)
    with r.store.connection(True) as c:
        r.manage(c,w,user.id);a=r.get(body.get('model_id'),user.id,'model',c)
        if a['workspace_id']!=w or a['visibility']!='workspace' or not a['enabled'] or not a['data'].get('configured'):raise Problem(422,'默认模型必须是本公司已配置的共享模型连接')
        c.execute('INSERT INTO team_platform_defaults VALUES(?,?) ON CONFLICT(workspace_id) DO UPDATE SET model_id=excluded.model_id',(w,a['id']))
    return {'default_model_id':a['id'],'existing_bindings_unchanged':True}


@router.post('/workspaces/{w}/platform/server-model-preset')
async def server_preset(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    from .presets import read_preset
    from .platform_registry import stable
    r=registry(server)
    with r.store.connection() as c:r.manage(c,w,user.id)
    if not is_site_admin(user):raise Problem(403,'绑定服务器预设需系统管理员')
    cfg=read_preset(server,user)
    if not cfg:raise Problem(409,'服务器模型预设不存在')
    async with _model_lock:
        aid=stable('v_',w+':server-model-preset')
        with r.store.connection(True) as c:
            r.manage(c,w,user.id)
            if c.execute('SELECT 1 FROM team_platform_assets WHERE id=?',(aid,)).fetchone():
                return r.get(aid,user.id,c=c)
            r._insert_asset(c,w,user.id,'model','OpenCode Go · 团队开发模型',{'provider_name':'','model':'','base_url':'','configured':False},
                '仅用于供应商允许的开发Agent场景；没有开启自动重试或付费回退。',{'kind':'administrator_server_preset'},aid,False)
        a=r.get(aid,user.id)
        result=await configure_model(r,server,a,user,{**cfg,'expected_revision':a['revision']})
        with r.store.connection(True) as c:c.execute('INSERT INTO team_platform_defaults VALUES(?,?) ON CONFLICT(workspace_id) DO NOTHING',(w,aid))
        return result


@router.get('/workspaces/{w}/platform/skill-catalog')
async def skills(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    from .skill_library import native_catalog
    r=registry(server)
    with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
    rows=await asyncio.to_thread(native_catalog)
    return {'items':[{k:v for k,v in x.items() if k not in ('root','markdown','body')} for x in rows],'scope':'workspace','import_status':'draft_disabled'}


@router.post('/workspaces/{w}/platform/skill-import',status_code=201)
async def import_skill(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
    from .skill_library import import_native
    r=registry(server)
    with r.store.connection() as c:r.manage(c,w,user.id)
    return await asyncio.to_thread(import_native,r,w,user.id,body.get('catalog_id'))


def asset_files(r,a):
    """No credential values are included; callers enforce current library ACL."""
    data=a['data'];root=a['kind']+'/'+a['id']+'/'
    result={root+'ASSET.json':json.dumps(a,ensure_ascii=False,indent=2).encode()}
    if a['kind']=='agent':
        for name,key in [('SYSTEM.md','system_prompt'),('SOUL.md','soul_md'),('AGENTS.md','agents_md'),('SEARCH.md','search_prompt')]:result[root+name]=data.get(key,'').encode()
    if a['kind']=='skill':
        from .skill_library import package_files
        result.update({root+n:b for n,b in package_files(r,a).items()})
    return result


@router.get('/workspaces/{w}/platform/export')
def export_library(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
    r=registry(server)
    with r.store.connection() as c:r.manage(c,w,user.id)
    assets=r.catalog(w,user.id)['items'];buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('README.md','# 公司能力库配置导出\n\n仅配置、版本和Skill附属文件；不包含密钥、原项目对话和数据库。提示词及受限草稿可能包含业务信息，请仅交给授权同事。\n')
        for a in assets:
            for name,b in asset_files(r,a).items():z.writestr(name,b)
    return Response(buf.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="workspace-capabilities.zip"'})
