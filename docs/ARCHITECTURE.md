# Architecture / 系统架构

Browser SPA (HTML/CSS/JS)
- Team/project/task collaboration, @Agent and @file, live SSE and typing.
- File preview, voice-to-draft, dashboard/calendar, collapsible Trace and human approvals.

Restricted FastAPI service (Octop integration)
- Native login, team/project ACL and explicit permission boundaries.
- Task messages, artifact provenance, scheduling, object versions and knowledge review.
- Octop Harness: bounded, single-Agent model and tool cycles with stream and audit.
- SQLite with FTS5/BM25, project Markdown export, original-file checksums.
- Optional external models, speech API and scoped MCP services.

Directory map:
- app/teamspace: authenticated API, workspace, agents, tools, knowledge, task SSE, ASR.
- app/web: native browser UI and local audio/calendar helpers.
- app/deployment: source-pinned installation, launch, backup and recovery check.
- app/tests: selected portable regression checks.
- docs: knowledge flow, installation, configuration and security.

This base version is not a distributed scheduler, vector graph database, unrestricted cloud desktop or multi-agent parallel orchestrator.
