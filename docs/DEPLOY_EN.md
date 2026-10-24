# Gongzhi: Complete Deployment Guide for Windows WSL2 and Ubuntu Linux

[English README](../README.en.md) · [中文版部署](DEPLOY_ZH.md) · [Configuration](CONFIGURATION.md)

This document covers a **fresh self-hosted installation of the public source release**. It deliberately does not assume access to the original author's servers, accounts, API keys, SSH configuration, or company data.

## 1. Requirements

| Area | Recommended |
|---|---|
| Host | Ubuntu 22.04/24.04 Linux, or Windows 11 with WSL2 Ubuntu |
| Runtime | Python **3.12**, installed into an isolated venv by uv |
| Hardware | Recommended ≥4 GB RAM and ≥5 GB free disk; stored documents need additional space |
| Networking | Internet access for pinned Octop source and Python dependencies |
| Storage | Single-instance SQLite; original files on the local Linux filesystem |
| Browser | Current Chrome/Edge/Safari; microphone recording requires HTTPS or localhost |
| Public access | Your own HTTPS-terminating reverse proxy and appropriate firewall rules |

## 2. Prepare Windows WSL2 (skip on native Linux)

Open an **elevated PowerShell** and run:

~~~powershell
wsl --install -d Ubuntu
wsl --list --verbose
~~~

Complete the Ubuntu first-run user setup, and ensure the distro runs in WSL2 mode. All remaining commands belong in the **Ubuntu shell**, not PowerShell.

Keep the application inside the Linux filesystem, for example <code>~/develop/gongzhi-teamspace</code>, rather than in <code>/mnt/c</code> or another Windows mounted folder. This is particularly important for SQLite and frequent file access.

## 3. Install prerequisites

In Ubuntu:

~~~bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env" 2>/dev/null || true
uv --version
~~~

See [official uv installation docs](https://docs.astral.sh/uv/getting-started/installation/). Existing installations of uv can be reused.

## 4. Clone the public repository

~~~bash
mkdir -p ~/develop
cd ~/develop
git clone https://github.com/luoyif/gongzhi-teamspace.git
cd gongzhi-teamspace
~~~

Before deploying, review LICENSE, SECURITY.md, and app/THIRD_PARTY_NOTICES.md.

## 5. Install the application

~~~bash
bash app/deployment/install.sh
~~~

The installer prepares a project-local Python 3.12 environment, downloads the **pinned Octop source archive**, checks SHA-256 against the reviewed release, applies the scoped integration hook to an isolated source copy, installs constrained Python dependencies, and checks imports.

Do not bypass archive/hash checks if upstream content has changed. Review and consciously update the pinned source instead. No global Python environment changes should be necessary.

## 6. Start and verify the service

~~~bash
.venv/bin/python app/deployment/service.py start
.venv/bin/python app/deployment/service.py status
curl --fail --silent http://127.0.0.1:47821/api/health
~~~

Expected health response includes a JSON object with <code>ok: true</code> and <code>product: "teamspace"</code>.

Open **http://127.0.0.1:47821**. Create your initial administrator account and workspace, then invite team members.

![Team dashboard](images/01-dashboard.webp)

## 7. Configure models, employees, skills and MCP

An installed web app does **not** mean that an external model is automatically configured.

From **Integrations → Model providers**, enter your chosen provider's endpoint, model ID and server-side API key. Run a small test request before using the model in real work. Configure AI employees with their responsibilities, model, system prompts, skills, MCP connections, platform tools and execution permissions.

To invite an agent into a conversation, mention it explicitly with @. Ordinary human-to-human task messages do not consume model tokens.

### Optional speech transcription

Speech uses <code>FunAudioLLM/SenseVoiceSmall</code> with your own SiliconFlow key, never committed to Git:

~~~bash
mkdir -p data/credentials
chmod 700 data/credentials
# Write your key yourself to data/credentials/siliconflow-asr.key
chmod 600 data/credentials/siliconflow-asr.key
~~~

The browser records and converts microphone audio to mono PCM WAV, the authenticated backend performs transcription, and returned text appears in the draft. **It never automatically sends or triggers the AI.** Read [configuration details](CONFIGURATION.md).

## 8. Optional remote access via HTTPS

**Do not publish the development port or database to the public internet.** The app listens on loopback by default. Use a separate reverse proxy with trusted HTTPS certificates and restricted access.

An illustrative Nginx proxy block, which must be adapted to your own certificate and hostname:

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

This is **not** a complete hardened Nginx configuration. Add certificate renewal, login throttling, firewall rules, SSE connection handling, restricted reverse-tunnel access when necessary, and appropriate user policies.

## 9. Maintenance, backup and recovery

~~~bash
.venv/bin/python app/deployment/service.py status
.venv/bin/python app/deployment/service.py stop
.venv/bin/python app/deployment/service.py start

# Private archive includes SQLite, original documents and credentials
.venv/bin/python app/deployment/backup.py
~~~

Keep archives private. Test a restore **into a new empty directory** before altering any live runtime:

~~~bash
.venv/bin/python app/deployment/restore_check.py \
  backups/<YOUR_BACKUP>.tar.gz /tmp/gongzhi-restore-check
~~~

Never extract a backup over a running instance. Before changing runtime code, stop new agent tasks, inspect currently executing runs, back up data, and retain the last-known-good source version.

## 10. Troubleshooting

| Symptom | What to check |
|---|---|
| Browser cannot open the site | Confirm service status, health endpoint and port 47821 availability |
| Public site disconnects when Windows sleeps | WSL availability depends on host state; configure explicit host keepalive or deploy on always-on Linux |
| Microphone is unavailable | HTTPS or localhost required, plus browser microphone permission |
| ASR returns unavailable | Server-side key file location, permissions, vendor quota and network access |
| Agent doesn't respond | Did you explicitly @Agent? Is its model configured and enabled? |
| File search has no hits | Has the file been parsed? Scanned PDFs may have no text layer |
| Imported Skill cannot run | Review, enable and attach the Skill with appropriate tool permissions |
| Different people see different files | Verify project ACL; company-wide agent identity does not grant cross-project data access |
| App slows down | Inspect long model jobs, file parsing, SQLite contention and local disk availability |

## 11. Operational boundaries

This code is a **self-hostable base**, not a formally audited, high-scale multi-tenant SaaS. The current system is single-instance, uses bounded agent runs and does not implement autonomous parallel multi-agent orchestration. Third-party models, Skills and MCP connections must be used within your own security policies and service terms.

[Features](FEATURES_EN.md) · [中文版部署](DEPLOY_ZH.md) · [Return to README](../README.en.md)
