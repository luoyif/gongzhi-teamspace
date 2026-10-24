# 共知 · Gongzhi Teamspace

A self-hosted, task-centric workspace for people and AI employees, designed around knowledge flow.

中文：多人 × AI 员工 × 任务讨论 × 共享资料 × 可追溯的知识沉淀。

## Why Gongzhi / 为什么做共知

Modern collaboration is fragmented: humans discuss in chat, AI runs in another app, tasks move to a board, and files become isolated in yet another database. Every product boundary silently discards useful context.

Gongzhi takes a different foundation: one team's verified knowledge, decisions, artifacts, provenance and history should flow through people and AI tools without becoming separated islands. Work happens within a team, project, and task. A task owns a shared discussion. Agent activity and adopted knowledge remain traceable back to that task.

## Implemented today / 当前已实现

- Company/team -> project -> task -> shared multi-person conversation with presence and typing state.
- Explicit @AI employee / @document invocation; ordinary human chat does not trigger model billing.
- Company-level reusable agent, Skill, MCP, model, and platform-plugin configuration.
- Bounded Octop Harness execution: streaming, approvals, stop/continue, tool receipts, nested Trace.
- Project folders with upload, preview and FTS5/BM25 chunk search for controlled context use.
- Original sources -> draft summary -> human confirmation -> project memory -> explicit team publication.
- Dashboard calendar and project milestones, voice dictation into the draft only (no auto-send).
- Browser UI with no frontend CDN dependency; Windows WSL2 or Linux single-machine deployment.

## Current boundaries / 已知边界

One Agent per run; autonomous multi-agent negotiation and parallel orchestration are planned, not yet implemented. This is a base version, not a formally security-audited internet-scale multi-tenant service. SQLite and task presence state are single-instance; no multi-node HA claim. Importing untrusted Skills, external MCP, and third-party model access requires explicit authorization.

## Architecture

    Company / Team
      Shared AI employees (model, Skill, MCP, controlled tools)
      Projects
        Plan, calendar, file folders, indexed knowledge
        Tasks
          Team chat + explicit @AI / @file
          Model and tool execution, approvals, Trace
          Candidate summary -> human review -> knowledge memory
      Published team knowledge snapshots

Read docs/KNOWLEDGE_FLOW.md and docs/ARCHITECTURE.md.

## Quick deployment (Ubuntu or Windows WSL2)

1. Install Ubuntu (or Windows: wsl --install -d Ubuntu).
2. Install uv using the official guide: https://docs.astral.sh/uv/getting-started/installation/
3. Clone this repository into the Linux filesystem, not /mnt/c.
4. From the repository root:

    bash app/deployment/install.sh
    .venv/bin/python app/deployment/service.py start
    .venv/bin/python app/deployment/service.py status

Open http://127.0.0.1:47821 and create the initial administrator locally. For external access terminate HTTPS at a separately configured reverse proxy. Do not publish the local development port, database, or credential directory.

See docs/INSTALL_WSL.md for migration and backup. See docs/CONFIGURATION.md for agent and optional ASR setup.

## License and dependencies

MIT for this repository's original code. TencentCloud/Octop runtime is used with its own MIT license, pinned upstream commit and SHA checks; other packages follow their respective licenses. See app/THIRD_PARTY_NOTICES.md and licenses/Octop-MIT.txt. No private upstream dependencies, real API keys, customer content, SSH config, or operational logs are bundled.

## Contributing

Contributions are welcome around source-verified memory, collaboration protocols, portable deployment, scoped tools and future multi-agent workflows. Read CONTRIBUTING.md and SECURITY.md before opening issues.
