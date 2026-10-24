# 共知：Windows WSL2 / Linux 完整部署指南

[返回中文首页](../README.md) · [English deployment guide](DEPLOY_EN.md) · [模型与语音配置](CONFIGURATION.md)

> 本文针对 GitHub **公开基础版**，在你自己的计算机上从零安装。这里不会使用作者现有的云服务器、数据库、账号、API Key 或私有运行目录。

## 1. 部署形态与推荐配置

共知由一个受限的 FastAPI Web 服务、固定版本 Octop Harness、SQLite 数据库以及浏览器前端组成。初始服务只绑定本机的 <code>127.0.0.1:47821</code>。

| 项目 | 推荐或最低要求 |
|---|---|
| 操作系统 | Ubuntu 22.04/24.04，或 Windows 11 + WSL2 Ubuntu |
| Python | **3.12**，安装脚本通过 uv 安装项目独立环境 |
| Node.js | 运行网站不需要；仅开发/执行 JavaScript 测试时使用 |
| 内存与磁盘 | 建议至少 4 GB 内存和 5 GB 可用磁盘（大量文件需更多空间） |
| 网络 | 首次安装需要访问 GitHub 固定归档、Python 包源；模型/MCP/ASR 使用时另需访问对应提供商 |
| 存储 | SQLite + 本地附件，**单实例**运行 |
| 对外访问 | HTTPS 反向代理；麦克风需要 HTTPS 或 localhost 安全上下文 |

## 2. Windows 安装 WSL2

在管理员 PowerShell 中执行：

~~~powershell
wsl --install -d Ubuntu
wsl --list --verbose
~~~

按照提示重启并完成 Ubuntu 初始用户名/密码创建。确认 Ubuntu 的版本是 WSL2。若已经安装 Ubuntu，无需重复安装。

**接下来的命令都在 Ubuntu 终端执行，不是在 PowerShell 中执行。** 把源码、运行环境、数据库放在 Linux 的 <code>~/develop</code> 下，而不是 Windows 的 C/E 盘挂载目录，这对 SQLite 和文件访问稳定性很重要。

## 3. 安装 uv 与系统基础工具

在 Ubuntu 或 Linux 中：

~~~bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env" 2>/dev/null || true
uv --version
~~~

uv 的官方安装说明：https://docs.astral.sh/uv/getting-started/installation/ 。如果已经在 PATH 中安装过 uv，可以跳过安装步骤。

## 4. 获取共知源码

~~~bash
mkdir -p ~/develop
cd ~/develop
git clone https://github.com/luoyif/gongzhi-teamspace.git
cd gongzhi-teamspace
~~~

首次安装请先查看仓库的 LICENSE、SECURITY.md 和 app/THIRD_PARTY_NOTICES.md。

## 5. 安装独立运行环境

~~~bash
bash app/deployment/install.sh
~~~

脚本会：

1. 创建项目自己的 Python 3.12 虚拟环境和缓存目录；
2. 下载固定 Octop 源码版本（不是随意使用最新版本）；
3. 检查压缩包 SHA-256 和关键代码的已审阅哈希；
4. 只对项目隔离的 Octop 副本安装共知入口；
5. 安装受约束的 Python 依赖，检查 Python 和应用模块能否导入。

完成后，确认目录中存在 <code>.venv/bin/python</code>、<code>runtime/Octop</code>。没有必要向全局 Python 环境安装依赖。

**如果固定归档哈希不匹配，脚本会拒绝继续。不要为了安装成功删除校验。** 应先确认下载来源或审查版本变更。

## 6. 首次启动

~~~bash
.venv/bin/python app/deployment/service.py start
.venv/bin/python app/deployment/service.py status
curl --fail --silent http://127.0.0.1:47821/api/health
~~~

健康接口预计返回含 <code>"ok":true</code>、<code>"product":"teamspace"</code> 的 JSON。

在部署机器的浏览器打开：

**http://127.0.0.1:47821**

首次创建**管理员账号及密码**，然后创建团队和项目。共知本身不要求验证码服务。

可以依次查看：

- 左侧工作台：团队项目、待验收、任务和日历；
- 项目：创建任务并设置负责人、状态及截止日期；
- AI 员工：团队级配置可复用的专家、模型和工具；
- 技能与连接：Skills、平台插件、MCP、模型厂商；
- 任务讨论：真人发消息不会自动召唤 AI，输入 @ 才会邀请；
- 资料与知识：上传原件、预览、检索、审核后沉淀。

![共知工作台，演示数据](images/01-dashboard.webp)

## 7. 模型、Skills、MCP 和语音输入

安装完毕**不代表外部模型已自动接通**。

在「技能与连接 → 模型厂商」中输入兼容接口的 Base URL、模型 ID、API Key，使用界面测试后再配置 AI 员工。模型必须遵守供应方的服务条款与配额。

AI 员工配置分为身份/提示词、模型、Skills、数据连接 MCP、平台插件和高级运行预算。一个员工配置属于团队，多项目按权限使用它，**不能因为模型跨项目共享而泄漏文件**。

语音识别是可选功能，使用 <code>FunAudioLLM/SenseVoiceSmall</code>，需要你自己的 SiliconFlow 密钥：

~~~bash
mkdir -p data/credentials
chmod 700 data/credentials
# 自己在 data/credentials/siliconflow-asr.key 写入密钥（别放进 Git）
chmod 600 data/credentials/siliconflow-asr.key
~~~

更详细的配置和识别限制参见 [CONFIGURATION.md](CONFIGURATION.md)。语音识别成功只把文字插入输入框，不自动发送聊天消息。

## 8. 公网访问：推荐 HTTPS + 反向代理

**不要直接让 FastAPI/SQLite 暴露给公网。** 基础程序保持监听 <code>127.0.0.1:47821</code>。若使用自己的 Linux 公网服务器、反向 SSH 隧道或零信任网络，代理也应仅回源到受保护的本地端口。

以下为 Nginx 代理的**示例思路**，请替换自己的域名、证书和可访问的内网目标。它不是一份可原样覆盖现有 Nginx 的完整配置：

~~~nginx
server {
    listen 443 ssl;
    server_name workspace.example.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    client_max_body_size 25m;
    location / {
        proxy_pass http://127.0.0.1:47821;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_read_timeout 900s;
    }
}
~~~

代理必须考虑登录限流、HTTPS 证书自动续期、上传上限、SSE 长连接，以及账号访问控制。如果内网服务器没有公网 IP，可以使用只允许回环端口的受限 SSH 反向隧道；不要开放数据库端口、调试 API 或私有凭证文件。

## 9. 日常维护与备份

~~~bash
# 查看是否就绪
.venv/bin/python app/deployment/service.py status

# 停止/恢复当前项目，不会关闭整个 WSL
.venv/bin/python app/deployment/service.py stop
.venv/bin/python app/deployment/service.py start

# 私有完整备份
.venv/bin/python app/deployment/backup.py
~~~

备份包含业务数据库、上传原件和服务器密钥等敏感内容，必须使用私有存储并定期验证。仓库不会上传运行数据。

在升级前，应先停止新 Agent 任务、检查在运行的操作、备份并保存已验证的源码版本。测试恢复时使用新的空目录：

~~~bash
.venv/bin/python app/deployment/restore_check.py \
  backups/<YOUR_BACKUP>.tar.gz \
  /tmp/gongzhi-restore-check
~~~

不要把备份直接解包覆盖当前运行的 <code>data</code>。

## 10. 常见问题

| 现象 | 检查方式 |
|---|---|
| 网站无法打开 | 先运行 service.py status 和本机 health；检查 47821 端口冲突 |
| WSL 休眠后外网断开 | WSL 随 Windows 开机、登录和睡眠状态变化；需自建受控保活或 Linux 常驻服务 |
| 语音按钮不能录音 | 必须使用 HTTPS 或 localhost；检查浏览器麦克风权限 |
| 语音识别返回 503 | 核实私有密钥文件存在、权限为 600、提供商额度正常 |
| AI 不回复 | 是否在任务中明确选择了 @Agent；模型连接是否可用 |
| 文件检索不到 | 原件是否已成功解析；扫描 PDF 未必带文字层 |
| Skill 无法执行 | 是否已审核、启用、挂载到员工且明确授权工具 |
| 两人看到的资料不同 | 检查当前项目成员和文件访问权限；不能跨项目越权 |
| 导入 Skill 遭拒 | 核对 ZIP 结构、SKILL.md、来源版本和安全检查 |
| 单人机器变慢 | 检查上传、SQLite 写操作与长任务日志；当前仅提供单实例部署 |

## 11. 安全边界和上线检查

部署互联网前，请自行检查：强密码、最小授权、HTTPS/证书续期、日志不泄露敏感信息、备份可恢复、模型/ASR 额度、外部 MCP 工具权限、服务器磁盘、系统更新、团队数据使用规则。

这份文档说明**当前代码的配置与安装入口**，不构成大型高并发、容灾或正式安全认证。发现缺陷欢迎在 GitHub Issue 描述可复现步骤，但**不要公开访问令牌、数据库或用户资料**。

[功能介绍](FEATURES_ZH.md) · [English deployment guide](DEPLOY_EN.md) · [返回首页](../README.md)
