# 共知 Gongzhi — 多人与 AI 协作的共享知识工作空间

## v0.16.1：知识来源图谱与备份修复

新增任务和团队知识来源图谱，展示有记录的来源、执行、人工审核及发布关系；来源项目权限仍会逐次检查。修复 SQLite 备份时临时日志文件可能导致恢复校验失败的问题。图谱不推断事实或自动发布知识，复杂 DAG 和自动并行多 Agent 仍未实现。详见[知识流转图谱](docs/KNOWLEDGE_GRAPH_ZH.md)和[版本记录](docs/RELEASE_0_16_1.md)。

<p align="center"><strong>让人与人、人与 AI 的每次协作，都留下可追溯、可继承、可复用的知识。</strong></p>

<p align="center">
  <a href="README.en.md">English</a> ·
  <a href="docs/WHY_GONGZHI_ZH.md">为什么选择共知 / Key Differences</a> ·
  <a href="docs/TEST_MATRIX_ZH.md">测试对比</a> ·
  <a href="docs/DEPLOY_ZH.md">部署指南</a> ·
  <a href="docs/FEATURES_ZH.md">功能介绍</a> ·
  <a href="docs/SCREENSHOTS.md">产品截图</a> ·
  <a href="docs/KNOWLEDGE_FLOW.md">知识流转原则</a> ·
  <a href="SECURITY.md">安全边界</a>
</p>

<p align="center"><img src="docs/images/v016/01-task-execution-desktop.webp" alt="共知团队工作台：项目、任务、日历和知识概览" width="1020"></p>
<p align="center"><sub>真实运行界面截图 · 使用隔离的演示账号和示例数据，不包含正式用户资料</sub></p>

## 新版 v0.16：任务不止能讨论，还能可靠交接与验收

**已上线的基础能力：**任务长期摘要（历史来源和消息游标）、真人批准的双 Agent 串行交接（最多两跳）、2–8 步顺序任务流程（每步人工启动与核验）、折叠 Trace 和一致的 Web/手机界面。

[查看 8 张新版实机截图](docs/SCREENSHOTS_V016.md) · [与 QM、Ekko Studio 的真实差异](docs/WHY_GONGZHI_ZH.md)

## 为什么需要共知？

聊天工具、项目看板、文件库、AI 聊天、Agent 和 MCP 各自都很强，但实际协作中，它们经常是一个个孤岛：讨论发生在聊天里，任务又要手工搬到看板；换个 Agent 就得重新解释资料；一个人或 Agent 的成果，无法自然成为可验证、可复用的组织知识。

**共知的出发点是知识流转，而不是再造一个聊天框。** 让团队、项目、任务、讨论、资料、执行记录与经过核验的记忆连起来。

> **团队 → 项目 → 任务 → 人与 AI 讨论 → 可核验产物 → 知识沉淀与复用。**

## 看看它长什么样

### 多人讨论 × @AI 员工

在同一任务里，人可以实时讨论；只有明确 <code>@AI 员工</code>，才会启动模型。Agent 读取当前任务上下文和有权访问的项目资料；执行过程折叠在对应回复中。

| 多人实时任务讨论 | 选择 AI 员工或文件 |
|:---:|:---:|
| [![任务内多人讨论](docs/images/07-task-discussion.webp)](docs/images/07-task-discussion.webp) | [![Agent 和文件引用](docs/images/08-mention-agents.webp)](docs/images/08-mention-agents.webp) |

### 专业 AI 员工 × 团队统一配置

员工在团队层管理，不用每建一个项目就复制一套：提示词、模型、Skills、MCP 和受限平台插件均可组合使用。

| AI 员工 | Skill、MCP 与模型连接 |
|:---:|:---:|
| [![AI 员工配置](docs/images/05-ai-employees.webp)](docs/images/05-ai-employees.webp) | [![技能和连接](docs/images/06-skills-connectors.webp)](docs/images/06-skills-connectors.webp) |

### 任务、知识与日程互相连通

项目文件支持目录、检索、预览和来源版本。纪要和产物经过人工审核后才成为团队知识；任务期限和跨项目安排汇总在工作台。

| 知识与记忆 | 团队日历 |
|:---:|:---:|
| [![知识与记忆](docs/images/04-knowledge-memory.webp)](docs/images/04-knowledge-memory.webp) | [![团队日历](docs/images/03-team-calendar.webp)](docs/images/03-team-calendar.webp) |

[**查看全部 9 张真实产品截图 →**](docs/SCREENSHOTS.md)

## Key Difference：共知为什么不是 QM + Ekko 的简单拼接？

QM 在 Scope 权限、持久沙箱和后台执行上值得我们学习；Ekko 在多 Agent 交互与 DAG 上更成熟。共知坚持的默认结构是 **公司 → 项目 → 任务 → 讨论 → 可核验结果 → 人工采用/公司发布知识**。

这里一条模型消息、一次真实 Run、一次人工验收、一个已采用的项目知识和一份公司公开快照，**不是同一个“完成”状态**。这让产品调研、研究—研发—审核的任务成果能够回到团队知识，而不要求每个新项目重新复制历史。

这不是声称别人做不到或没有记忆。QM 也实现了来源/敏感度标记的版本化记忆。请看[逐项诚实比较](docs/WHY_GONGZHI_ZH.md)和[包含三方证据强度的测试矩阵](docs/TEST_MATRIX_ZH.md)。

## 核心功能

| 能力 | 当前已实现 |
|---|---|
| **多人协作** | 团队/成员邀请、项目、任务、真人实时聊天、在线与输入状态 |
| **AI 员工** | 显式 @Agent / @文件、团队级配置、多员工人工批准的有限串行交接、Skills/MCP/插件 |
| **文件和知识** | 多层文件夹、Markdown/Word/Excel/PDF 等常见格式预览、FTS5/BM25 检索、出处追溯 |
| **AI 执行过程** | 流式、审批、执行权限设置、停止/继续、折叠 Trace、工具回执 |
| **知识沉淀** | 讨论整理 → 待核对候选 → 人工采用 → 项目记忆 → 明确发布的公司知识 |
| **日程和规划** | 项目计划、任务看板、负责人和期限、工作台日历；2–8 步人工门控的顺序计划 |
| **语音输入** | 可选 SenseVoiceSmall，将语音转写进草稿，**不自动发送** |
| **自托管** | Windows WSL2 / Ubuntu Linux、浏览器访问、SQLite、可自行配置 HTTPS |

技术栈：Python 3.12 / FastAPI / SQLite FTS5、[TencentCloud/Octop](https://github.com/TencentCloud/Octop) Harness、原生 HTML/CSS/JavaScript。了解 [技术架构](docs/ARCHITECTURE.md)。

## 立即部署

建议使用 **Windows 11 + WSL2 Ubuntu，或 Ubuntu 22.04/24.04 Linux**，运行在 Linux 文件系统中（不要放在 /mnt/c）。

### Windows 首次安装 WSL2

在管理员 PowerShell 中运行：

~~~powershell
wsl --install -d Ubuntu
~~~

初始化 Ubuntu 后，在 **Ubuntu 终端**运行以下命令。Linux 用户直接从下一步开始：

~~~bash
# 先安装 uv，参考 https://docs.astral.sh/uv/getting-started/installation/
git clone https://github.com/luoyif/gongzhi-teamspace.git
cd gongzhi-teamspace

bash app/deployment/install.sh
.venv/bin/python app/deployment/service.py start
.venv/bin/python app/deployment/service.py status
~~~

打开 **http://127.0.0.1:47821**，创建第一个管理员、团队和项目。

安装脚本会联网获取**固定版本 Octop** 和 Python 依赖，并校验固定源码摘要。不要把已审阅的固定版本随意替换成最新版。

**图文和故障排查：** [完整中文部署说明](docs/DEPLOY_ZH.md) · [模型 / Skill / MCP / ASR 配置](docs/CONFIGURATION.md)。

### 选择模型与 Agent

部署后到「技能与连接 → 模型厂商」填写自己的 API 地址、Model ID、密钥；到「AI 员工」配置专家及允许工具。团队普通聊天不需要 AI。**本仓库不带真实密钥，也不包含现网数据。**

## 知识如何流转？

~~~text
上传原始文件 → 版本/权限/检索索引
      ↓
任务里的真人讨论 + @AI员工 + @项目文件
      ↓
模型输出、真实工具回执、候选纪要/成果
      ↓
人工核对 / 采用 / 验收
      ↓
项目知识和记忆（可导出 Markdown）
      ↓
明确发布的公司共享知识 → 其他任务按权限复用
                          → 审核形成 Skill 草稿
~~~

原件不被摘要覆盖，模型建议不冒充核验结果，跨项目资料不会因共享 Agent 身份而泄漏。[知识流转原则](docs/KNOWLEDGE_FLOW.md)。

## 当前边界和发展路线

**这是可自部署的基础版，不是已通过独立安全审计的大规模 SaaS。**

- **一次 Run 一位 Agent**；任务中可以人工批准最多两跳的串行接力；**多 Agent 自主并行、复杂条件 DAG 尚未实现**。
- SQLite、在线状态与任务执行按**单实例**设计，不承诺集群高可用。
- 无任意宿主 shell、无限运行时间或不受约束的云电脑。
- 外部模型、语音识别及 MCP 会使用部署者自己的额度；重要写入仍需权限和审计。

下一步方向：多 Agent 任务协商、可验证知识图谱、跨工具上下文迁移、离线优先、可视化工作流和完善的安全评估。

## 开源与参与

原创代码以 [MIT](LICENSE) 许可证发布；Octop 和其他组件按各自许可使用，参见 [第三方通知](app/THIRD_PARTY_NOTICES.md)。欢迎通过 Issue / PR 贡献和讨论。

[English README](README.en.md) · [贡献指南](CONTRIBUTING.md) · [安全说明](SECURITY.md)

---

<p align="center"><sub>Gongzhi · Knowledge should outlive a conversation.</sub></p>
