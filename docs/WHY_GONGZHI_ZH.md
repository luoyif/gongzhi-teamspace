# 为什么是共知？——与 QM、Ekko Studio 的真实差异

> 共知 Gongzhi：以 **任务证据与组织知识流转** 为核心的多人 × AI 员工工作空间。不是“多一个聊天入口”，也不是把几个 Agent 工具机械相加。
>
> 对照日期：2026-10-25。共知公开基础版 v0.16.0。
> 固定外部版本：QM `095a4bcc719058162a041258e246a58b1329f19e`、Ekko `a2a5e876cec566a52e1e1873c96524a8dbf9a9e2`。这是版本化功能分析，不是声称外部产品永远缺少这些能力。

## 简短结论

[QM](https://github.com/yc-software/qm) 非常擅长“每个人、每个空间都有独立记忆/文件/权限/计算机”：组织级多 Scope、安全边界、持久运行、后台任务以及 Slack/Web 跨入口。我们应学习其**来源敏感度、强隔离、独立部署目录、Skill 审核、可恢复执行**。

[Ekko Studio](https://github.com/EKKOLearnAI/ekko-studio) 擅长成熟的多 Agent 群聊体验、多运行时、执行 Trace 和有审批的图形工作流。我们应学习其**明确 @ 调度、统一 Run、上下文摘要及精简步骤视图**。请注意其 BSL 1.1 许可与商业复用限制；共知没有复制 Ekko 的受限代码。

**共知当前的取舍**：每一条团队讨论归属于明确的公司、项目、任务。Agent 可以参与但不会默认代表团队决策；一个模型结果、一个工具回执、一项人类验收、一次公司知识发布，是不同的事实与状态。我们的目标是让团队能从“说了什么”一路查到“做了什么、谁确认、哪些知识可以复用”。

## 1. 三方差异（讲真实能力，不造不存在的空白）

| 维度 | QM（MIT） | Ekko Studio（BSL1.1） | Gongzhi 0.16（MIT 原创代码） |
|---|---|---|---|
| 组织入口 | 人/频道/Room 各有独立 Scope | Profile / Session / Group Room | **公司 → 项目 → 任务 → 讨论** |
| 团队协作 | Slack + Web，同一身份上下文 | 多真人/多 Agent 共同聊天 | 同任务多人实时，显式 @AI |
| 多 Agent | 持久子会话、Swarm 与执行队列 | 多运行时、明确交接、DAG | **两位 Agent 串行、真人审批，最多两跳** |
| 上下文/记忆 | 带来源与敏感度的版本化记忆、权限回查 | 群聊摘要+游标、Agent 记忆 | TaskSummary 来源哈希、最近消息、项目检索；人工采用的知识 |
| 项目流程 | Scoped 后台作业、crons、app发布 | 画布式 DAG/审批 | **2–8步任务内线性计划，逐步 Run、真人验收** |
| 资料与权限 | 每 Scope 沙箱、文件、密钥和共享策略 | 会话/Profile 与工具沙箱 | 项目文件夹、文件版本、明确发布的团队快照；权限检查 |
| 优势 | 完整度高的多 Scope 安全和持久计算 | 多 Agent 执行和 GUI 成熟度 | **任务结果的验收、可追踪来源、知识采用链** |
| 当前短板 | 官方承认仍是实验性且存在未覆盖边界；云端运维更重 | 商业复制需许可 | 暂无持久独立电脑/Slack/复杂DAG/自动并行 Swarm |
| 部署模式 | 自建云/Postgres/多 Scope 沙箱 | Web/桌面、多个 Runner | 轻量 WSL/Linux Web/SQLite 单实例 |

请不要将“我们有项目计划/记忆”解释为QM或Ekko没有。QM的记忆权限和审计事实上很强；共知的特色是**围绕任务以及知识采纳的用户流程与默认约束**，而不是声称研究上的独创算法。

## 2. 共知要优化的实际工作任务

### A. 研究与产品项目：从原始文件走到被确认的结论

产品负责人上传 PDF/Word 和标准资料，在同一个任务里与设计、研发同事讨论。研究员 Agent 生成候选报告并引用资料；工程师提供执行方案。管理员逐步核验 Run 和产物；一份经人工采用的项目知识可以**选择性**发布成公司公共快照，未发布的原始项目文件和对话不会因为共享 Agent 而被其他项目检索。知识撤回后对外检索消失，项目历史仍保持。

**不同点：**把协作对话、执行、采纳和发布视为一条可治理的业务链，不把 Agent 回复自动升格为公司事实。

### B. 受控分工：研究员 → 工程师 → 真人 QA

研究 Agent 已完成才可以申请接力给工程师；项目管理员审阅来源与目标后批准第二次独立运行。任务执行计划每一步都有实际 Run 与验收；重复批准不会自动产生新模型调用；失败后先对账，不能直接重复执行已确认的写操作。

**不同点：**在具体项目任务里落实多 Agent，而不是把多个 Agent 混入无归属房间后靠聊天约定保障业务一致性。

### C. 会议与知识治理：纠正旧决定而不污染后续项目

有人修改了上午的决策，下午同事继续追问旧话。任务有原始消息序号、可回读内容、作者信息和来源哈希，摘要发现旧原文变化时会失效。最新请求优先；只有人核实并正式发布的内容才可成为团队共享知识。

**不同点：**强化“可纠正、可审计和可撤回”的团队工作结果，不把长记忆等同于无限上下文。

## 3. 真实运行与测试证据

| 测试来源 | 已核对结果 | 不该推导出的结论 |
|---|---|---|
| QM 固定代码的记忆披露/跨 Scope/增量召回 | **31 项专项 PASS**，隔离 Node 环境 | 不代表其全产品/云沙箱/安全已全验收 |
| Ekko 固定代码与官方技术资料 | 阅读群聊、权限、压缩、工作流代码；没有独立运行其 E2E | 不能声称 Ekko 在某场景失败 |
| 共知0.16私有/运行环境 | **340项 Python、15套HTTP、35项JS、18项 Windows Chrome** 均通过 | 不代表所有真实第三方模型、生产并发/复杂DAG都验证 |
| 共知生产迁移 | 原业务记录保留、源码和文件校验、HTTPS与匿名ACL检查通过 | 不等于形式化不泄漏证明或大规模安全认证 |

相关仓库版本、命令、场景与脚本范围见 [公开测试矩阵](TEST_MATRIX_ZH.md)。仅展示真实运行结果，不用不同测试数作跨产品能力排名。

## 4. 下一阶段如何吸收他们的长处

- **Scope 强化（优先）**：参照 QM，为来源添加明确受众和敏感度、并在公开/共享/撤回每一次访问时重新核实权限；同时保留现有项目任务归属。
- **任务证据图（研发）**：让模型消息、Run、文件版本、人工核验和公司快照按真实对象 ID 显示，不让 AI 猜测“谁完成了什么”。该功能在独立开发分支测试，**尚未包含在 v0.16 正式公开版**。
- **Skill 生命周期（优先）**：学习 QM 的 Git pin/ref、管理员审查、冲突检测和版本来源；仍保持项目使用所需最小权限。
- **进一步 Agent 编排（中期）**：参考 Ekko 的 DAG 与 QM 的持久 worker，先做人工门控的条件节点/恢复，再考虑只读并行和独立沙箱。
- **部署与成本（中期）**：当前保持轻量 SQLite/WSL；需要高可用与后台沙箱时引入可替换 Postgres/Compute 接口，避免为少数场景让部署变重。

## 5. 可查的一级参考

QM 固定提交：
[架构README](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/README.md) ·
[记忆与受众来源隔离](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/memory-records.md) ·
[安全模型与已知限制](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/SECURITY.md) ·
[Skill Pack 审核](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/skill-registry.md) ·
[持久子 Agent](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/persistent-subagent-sessions.md)

Ekko 固定提交：
[架构](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/ARCHITECTURE.md) ·
[群聊交接](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/packages/server/src/modules/studio/services/group-chat/handoff-depth.ts) ·
[可执行工作流](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/packages/server/src/modules/studio/services/workflow/manager.ts) ·
[BSL许可证](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/LICENSE)

**比较与引用仅说明相应固定源码的功能；未将 QM、Ekko 源码或素材并入共知。**
