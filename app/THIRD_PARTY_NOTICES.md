# 上游与修改记录

本项目的协作门户使用 TencentCloud/Octop 的账号、身份认证、服务容器、SQLite 连接信息、模型供应方记录及模型构造入口。协作项目、成员权限、共同消息、统一资料摄取、词法检索、任务、日历、结果卡、运行记录与前端为本目录中的独立模块。

- 官方源码：https://github.com/TencentCloud/Octop
- 固定提交：`dd9dce470844c25d59effb50615bb3c667ea25cd`
- 上游版本：1.0.2
- 上游许可：MIT，Copyright (c) 2026 Octop
- 原始压缩包 SHA-256：`d02beb404f890f57fc008d114be7eb0c26ab39bf2b500e00ce03ea10dc6e2727`
- 原始 `src/octop/api/app.py` SHA-256：`58a1cb9715f1239ef0e6044de731d3c7b9eec9f5533d690eca74d01d5fc8ecdf`

`deployment/patch_octop.py` 只在独立 `runtime/Octop` 中增加一个由 `OCTOP_TEAMSPACE=1` 启用的应用工厂入口，支持校验与还原。`upstream/Octop` 和官方压缩包保留作为原始审查快照。项目没有 Git 上游历史，不把压缩包解压称为完整克隆。生产启动时只挂载协作入口与必要认证路由。

界面借鉴简洁的项目工作区结构，没有使用 Octop 的商标、图标或页面资源包；当前产品名称为“共知”。静态前端全部在 `web/`，没有运行时 CDN 依赖。

完整 Octop MIT 许可保留在 `upstream/Octop/LICENSE` 及运行副本中；分发包含上游的副本时需继续保留。其他 Python 依赖各自的许可证保留在对应包中，实际安装版本在 `evidence/runtime-lock*.txt`。Sugabots 只作为本地调研与备选源码，不参与当前应用运行。

## 0.3.0 原生Agent接入

实际复用octop-harness 1.0.4的HarnessAgent、ChatRequest、ChatModelFactory、workspace、技能中间件和stream，底层由deepagents/LangGraph运行。MCP复用langchain_mcp_adapters。固定依赖升级须重新验收受限工具装配。内置技能按完整包导入待审，不自动执行附件脚本。各依赖许可证保留在已安装包中；包含依赖源码的分发须保留原许可。本代码ZIP不打包依赖目录。

DeepSeek Harness仅为Trace理念参考；多人权限、分层事件和SSE是本项目适配，不宣称完整复制其实现。
