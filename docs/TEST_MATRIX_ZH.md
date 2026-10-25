# 证据驱动的三方测试矩阵：Gongzhi / QM / Ekko

[产品差异](WHY_GONGZHI_ZH.md) · [English](TEST_MATRIX_EN.md)

**比较时间：2026-10-25。** 固定源码：QM `095a4bcc`、Ekko `a2a5e876`、共知已验收正式版本 `0.16.0 / cb0aa32`。这是一份**测试覆盖与能力边界报告**，不是用单元测试数进行产品排行榜。

## 实际跑过的测试

| 项目 | 验证环境、范围 | 结果 | 明确没有验证 |
|---|---|---|---|
| QM | Windows Node 25.9 / npm 11.12，`npm ci --ignore-scripts`；memory disclosure、cross-scope、recall delta、ACL 存储四项测试文件 | **31 项 PASS** | 云部署、真实沙箱、Slack/模型交互和所有安全边界 |
| Ekko | 固定提交静态代码与原始文档审查；group-chat、context compressor、workflow manager | **SOURCE_REVIEWED** | **RUNTIME_NOT_RUN**：不记为失败或通过 |
| 共知 0.16.0 | WSL 的 Python/Octop/SQLite，浏览器真实 Windows Chrome，模拟模型，无生产业务写入 | **340 Python + 15 HTTP 套件 + 35 JS + 18 Chrome 项 PASS** | 所有付费模型与厂商、生产并发、复杂 DAG |
| 新“任务证据图”候选 | Windows Python 3.12 隔离运行，只替身注入 HTTP 依赖，真实项目 SQLite/权限/版本逻辑 | **8 项专项 PASS** | **WSL 原生 HTTP/浏览器 NOT_RUN**；因此不含在0.16公开版 |

**严禁把 31、340、35 作为跨项目优劣名次。** 覆盖范围和测试深度不一样，未运行的项目不得被算成 FAIL。

## 同一业务任务的对照标准

| 场景 | 共知实际结果 | QM已有近邻能力 | Ekko已有近邻能力 |
|---|---|---|---|
| 两真人同任务保持归属 | 已验收，消息有task_id和作者，普通真人聊天不唤醒模型 | Person/Room隔离Scope + Web/Slack | Group Room多真人 |
| 最新任务 vs 旧上下文 | 已验收：最新明确问题优先，“继续”可回读历史和来源 | 记忆记录/权限回查/增量召回 | Snapshot+尾段历史 |
| 两 Agent 有界接力 | 已验收：源Run→人批准→目标独立Run，最多2跳、幂等 | Durable子会话/Swarm | Group @ / handoff depth |
| 项目流程从研究走到审核 | 已验收：2–8项顺序步骤，真人逐步通过 | 后台/持久任务和审批 | 完整DAG与审批 |
| 文件结论成为公司知识 | 已实现：项目候选→人采用→明确发布的组织快照，撤回只取消共享 | 带敏感度/来源Scope的记忆和Skill治理 | Profile/Room记忆与Journey |
| 未授权跨任务/撤权 | 已验收：不同项目成员不能直接读取私有任务文件/摘要 | QM专项31测试涵盖受众/撤权 | Group Room访问控制 |
| “AI说完成”不能当验收 | 已验收：运行状态、人工审核、公司发布明确分离 | 工具审计和人类授权 | Workflow/Trace |
| 专用云电脑与后台常驻 | **未实现** | QM显著领先：Sandbox/crons/Swarm | 多Runtime与桌面能力 |
| 条件并行流程图 | **未实现**：只有手动门控的顺序流程 | 有持久任务与Swarm | Ekko DAG |
| 任务可核查证据图 | 新候选 Windows 8项单测通过，**未达到WSL发布门** | QM事实来源与范围标签 | Ekko Journey |

## 已有公开测试与命令

共知可参考本仓库 `app/tests/test_platform_v4.py` 和 `test_m1_task_memory.py`、`test_m2_agent_handoff.py`、`test_m3_workflow.py`。部署依赖安装完成后，使用隔离临时SQLite、无真实模型密钥执行：

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m1_task_memory.py' -v
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m2_agent_handoff.py' -v
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m3_workflow.py' -v
```

QM 本次实际命令：

```bash
npm ci --ignore-scripts --no-audit --no-fund
node --experimental-test-module-mocks --test \
  test/memory-disclosure.test.ts \
  test/cross-scope-memory.test.ts \
  test/memory-recall-delta.test.ts \
  test/acl-store.test.ts
```

注意：对方的四项源码测试不等于与共知实现了相同的测试逻辑。

## 公平的下一轮对照应怎样设计？

统一合成资料、用户权限、模型预算和操作授权，分别测：（1）任务完成率、（2）正确来源引用比例、（3）越权读取/跨项目泄漏次数、（4）相同写操作重复次数、（5）人工审核与撤回一致性、（6）真实Token/费用、（7）p50/p95延迟、（8）断线恢复。没有运行的数值保持 `NOT_RUN`；不能凭功能列表虚构性能胜负。

**关键原则：**Agent共享不代表资料共享；模型自述完成不等于运行回执；人类验收不等于组织发布；真正的权限要后端验证，不交给LLM自律。

固定来源：[QM 测试](https://github.com/yc-software/qm/tree/095a4bcc719058162a041258e246a58b1329f19e/test) · [QM 记忆记录](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/memory-records.md) · [Ekko 架构](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/ARCHITECTURE.md)。
