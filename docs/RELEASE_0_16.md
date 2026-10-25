# Gongzhi v0.16.0 — source release notes / 中文更新记录

[中文首页](../README.md) · [English](../README.en.md) · [8 张新版截图](SCREENSHOTS_V016.md) · [Compare QM / Ekko](WHY_GONGZHI_EN.md)

## 当前真实已实现

- **公司/项目/任务消息仍是统一入口。** 真人与真人直接聊，显式 `@Agent` 才开始模型 Run；文件/资料/技能/MCP 工具权限仍由后台验证。
- **TaskSummary：**任务旧历史有持久快照、通过消息 ID/seq 锚定，包含来源哈希和发言人；更改/删除旧消息会使原快照失效；新请求优先。
- **人类批准的 Agent 接力：**源 Agent 完成后可提出交接，管理员批准才启动目标员工，独立 Run、明确安全权限、最多两跳、重复批准不重做调用；与项目资料权限绑定。
- **任务内线性计划：**2–8 步分工，支持 Agent 执行+最终真人核验；每个步骤必须明确启动，完成后需人工批准才能进入下一步；失败只能明确重试；可对账“发起中”的既有 Run。
- **UI：**紧凑的单入口、任务侧栏默认折叠、真实 Trace/用量按需展开；统一项目卡、员工、模型/Skill/MCP 分类，深浅主题与手机响应式。
- **保留旧知识链：**原始文件、候选纪要、人工采用的项目知识及公司明确发布的快照具有不同状态；不会因 Agent 自称“完成”便自动成为组织制度。
- **仍为轻量单实例 Web。** Windows WSL2 或 Ubuntu Linux，自托管 SQLite、当前 Octop Harness；不承诺云端多节点容灾。

## What is NOT shipped

- No automatic simultaneous multi-agent swarm or general conditional/DAG graph editor.
- No per-employee durable cloud computer or a Slack bridge (QM is stronger in these areas).
- No unrestricted terminal, arbitrary host execution, or unlimited autonomous writing.
- No claim of comprehensive real-provider correctness/security certification.
- The newer *task evidence-provenance graph* explored against QM is an **experimental branch**, not part of this stable v0.16 source until native WSL/browser gates pass.

## Evidence and how to test

This public source is copied from the **same hashes** as the previously accepted self-hosted v0.16 build, with only explicitly whitelisted modules added or changed. The private release gate passed 340 Python unit checks, 15 isolated Octop/FastAPI HTTP suites, 35 JS tests and 18 Windows Chrome function/design checks. It also verified additive SQLite migration and preexisting file hashes. **Those tests did not all execute on GitHub's infrastructure**, and their coverage is not a substitute for an independent deployment-specific audit.

The public source includes selected relevant tests in `app/tests/test_platform_v4.py` and `test_m1_task_memory.py`, `test_m2_agent_handoff.py`, `test_m3_workflow.py`; see [Test Matrix](TEST_MATRIX_EN.md) for reproducibility and limitations.

## Third-party references

- [QM (MIT)](https://github.com/yc-software/qm): personal/room scopes, durable sandboxes, classified memory, background work.
- [Ekko Studio (BSL 1.1)](https://github.com/EKKOLearnAI/ekko-studio): multi-agent group chat, context snapshots, DAG UX. No restricted Ekko code or art was copied here.
- [Octop (MIT)](https://github.com/TencentCloud/Octop): Gongzhi's underlying fixed harness version, installed independently by the documented deployment process.

## Deployment and data protection

See [Chinese WSL instructions](DEPLOY_ZH.md) / [English instructions](DEPLOY_EN.md). No production database, original user conversations, real API/SSH secrets, deployment hostnames or the original private Git history is included. Operators configure their own models and keys on their own machines.
