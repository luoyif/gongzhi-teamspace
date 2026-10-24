"""Plugin discovery and reviewed built-in operational skill pack."""
from typing import Any
from fastapi import APIRouter,Body,Depends
from octop.api.deps import current_user,get_server
from .platform_api import registry
from .platform_plugins import CATALOG
from .store import Problem
router=APIRouter()
STARTERS=[
 ('schedule-coordinator','日程安排与冲突核查','先读取项目时区和现有日程；核对明确日期、结束时间及冲突。日期有歧义时询问。创建或改期必须调用日程插件并等待本次确认。成功后报告真实日程ID和时间；拒绝、冲突或失败不能声称已安排。','calendar.manage'),
 ('task-breakdown','任务拆解与跟进','读取规划、当前任务与团队成员。拆成可验收子任务，保留来源和依赖。未确定负责人或期限留空，不编造承诺。调用任务插件创建、改期或提交产物；完成先进入待验收，不替人签字。','tasks.manage'),
 ('meeting-to-actions','会议纪要与行动项','保留原话来源、结论、分歧、未决事项。将明确的行动、日程、知识分别列为候选。经成员确认后调用相应插件逐项写入，核对返回ID。不给缺日期的意向编排虚假会议。','knowledge.manage'),
 ('knowledge-quality','知识核查与版本修订','先核对引用文件ID、版本、采用状态。将事实与建议分开，矛盾资料并列标注。修改知识时先读取当前版本，经确认写入新版本；原件不覆盖，旧知识仅归档。禁止把项目资料自动公开给公司。','knowledge.manage'),
 ('plan-review','项目规划评审','读取项目现有目标与规划，说明建议变化及依据。计划更新必须携带当前revision，冲突后重新读取而非覆盖。给出执行顺序、依赖、验收标准和未决问题，不添加无来源的业务指标。','project.plan'),
 ('reusable-skill','验收经验沉淀技能','从已经人工采用或验收的项目资料开始。形成用途、输入、分步操作、检查、失败处理和权限边界。调用技能草稿插件保留来源。输出应停用且待审，不自行启用脚本、授予权限或发布公司技能。','skill.draft'),
 ('deliverable-builder','结构化任务产物','将讨论结论整理为Markdown、JSON或CSV。先校验内容与格式，再调用任务文件插件保存。明确给出文件ID和来源，供后续@引用；不得假装已在任意宿主目录运行代码。','artifacts.write'),
]
def starter_items():
 return [{'id':slug,'name':name,'description':text,'recommended_plugin':plugin,'body':'# '+name+'\n\n## 用途\n用于团队任务内的可审核协作。\n\n## 操作流程\n'+text+'\n\n## 验收\n核对实际工具结果、对象ID、版本和来源。只用当前项目授权信息。\n\n## 失败处理\n遇到权限撤销、版本冲突或工具失败立即停止相关写入并说明实际结果，不伪造成功。\n','source':'gongzhi_reviewed_operating_guide_v1'} for slug,name,text,plugin in STARTERS]
@router.get('/workspaces/{w}/plugins')
def plugins(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return {'items':[{**x,'version':1,'approval':'per_write' if x['write'] else 'read_only'} for x in CATALOG],'automatic_enable':False,'engine':'octop-harness','execution':'model_tool_loop','host_shell_enabled':False}
@router.get('/workspaces/{w}/skill-starters')
def starters(w:str,user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.store.workspace_require(c,w,user.id)
 return {'items':starter_items()}
@router.post('/workspaces/{w}/skill-starters/import')
def import_starters(w:str,body:dict=Body(...),user:Any=Depends(current_user),server:Any=Depends(get_server)):
 r=registry(server)
 with r.store.connection() as c:r.manage(c,w,user.id)
 ids=body.get('ids',[]);known={x['id']:x for x in starter_items()}
 if not isinstance(ids,list) or not ids or any(x not in known for x in ids):raise Problem(422,'技能包选择无效')
 items=[]
 for id in dict.fromkeys(ids):
  existing=next((a for a in r.catalog(w,user.id)['items'] if a['kind']=='skill' and a['source'].get('starter_id')==id),None)
  if existing:items.append(existing);continue
  item=known[id];items.append(r.save_asset(w,user.id,'skill',{'name':item['name'],'description':item['description'],'enabled':True,'data':{'slug':id,'body':item['body'],'status':'published'}},source={'kind':item['source'],'starter_id':id,'recommended_plugin':item['recommended_plugin'],'scripts_included':False}))
 return {'items':items,'automatically_mounted':False}
