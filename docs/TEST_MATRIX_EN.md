# Reproducible comparison tests: Gongzhi vs QM vs Ekko

[Why Gongzhi?](WHY_GONGZHI_EN.md) · [中文版](TEST_MATRIX_ZH.md)

**Reviewed 2026-10-25**, pinned sources: QM `095a4bcc`, Ekko `a2a5e876`, Gongzhi `0.16.0 / cb0aa32`. This is a **test-scope and product-design matrix**, not a leaderboard based on unrelated test counts.

## What actually ran

| System | Scope and environment | Result | Not established |
|---|---|---|---|
| QM | Windows Node 25.9, npm 11.12, isolated `npm ci --ignore-scripts`. Four selected files: disclosure, cross-scope memory, recall delta, ACL store | **31 PASS** | Entire application, cloud sandbox, Slack integration or security certification |
| Ekko | Pinned source/architecture review (group chat, context compaction, DAG service) | **SOURCE_REVIEWED** | **RUNTIME_NOT_RUN** — no runtime pass/fail claim |
| Gongzhi v0.16.0 | Windows WSL2/SQLite/real Chrome, deterministic mock models and restored data | **340 Python unit, 15 HTTP suites, 35 JS, 18 Chrome checks PASS** | Every real LLM provider, large-scale concurrency or conditional DAG |
| Experimental task evidence graph | Isolated Windows Python 3.12 with HTTP dependency shims only; real SQLite/ACL/revision behavior | **8 focused unit tests PASS** | **Native WSL API/browser NOT_RUN**; therefore **not shipped in v0.16** |

Test counts measure different things and **cannot be interpreted as product or security rankings**.

## Matched use cases and capability evidence

| Scenario | Gongzhi verified status | QM nearest implemented feature | Ekko nearest implemented feature |
|---|---|---|---|
| Two humans share one task history | Verified task ID, speaker and no implicit model billing | Scoped person/room chat on Slack/Web | Multi-human Group Room |
| New request vs old context | Verified latest-request priority and source-linked retrieval | Versioned memory + incrementally refreshed recall | Group summary snapshot and message tail |
| Agent A delegates to B | Verified explicit human approval, separate Run, dedup, max 2 hops | Persistent subagents/Swarm | Group @/handoff depth |
| Research → implementation → human review | Verified 2–8 sequential steps with human gates | Durable background tasks/approvals | Executable visual DAG |
| Project artifact → company knowledge | Verified human adoption and explicit publication/withdrawal | Scope/sensitivity versioned memory and governed Skills | Profile/Room memory and Journey |
| Revoked project/member access | Verified denial on private task context and file access | QM's passing cross-scope/disclosure tests | Group access controller |
| AI says “done” vs human accepts | Run status and acceptance remain separate | Audited effects / authority gates | Workflow+Trace |
| Durable personal computer/background cron | **Not implemented** | QM strength | Some runtime/desktop capabilities |
| Conditional parallel workflow | **Not implemented** (sequential only) | Swarm/background orchestration | Ekko DAG |
| Task-local evidence provenance graph | **Experimental**, Windows 8/8 unit only, not released | Source-scoped memory records | Journey/room summary |

## Reproduce the shipped Gongzhi task tests

With the documented isolated Octop/Python installation complete:

```bash
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m1_task_memory.py' -v
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m2_agent_handoff.py' -v
PYTHONPATH=app .venv/bin/python -m unittest discover -s app/tests -p 'test_m3_workflow.py' -v
```

These unit tests use temporary SQLite, not customer data or real LLM keys. The full private 15-suite HTTP harness needs additional isolated runtime fixtures not supplied with this public source release.

QM's scoped test command in its pinned checkout:

```bash
npm ci --ignore-scripts --no-audit --no-fund
node --experimental-test-module-mocks --test \
 test/memory-disclosure.test.ts \
 test/cross-scope-memory.test.ts \
 test/memory-recall-delta.test.ts \
 test/acl-store.test.ts
```

## Future fair evaluation contract

Use matched synthetic documents, equal authorization and tool availability, equivalent task goals and model budgets. Measure **successful deliverable completion, correct source citations, unauthorized reads, duplicate side effects, human review correctness, actual token and money spent, p50/p95 latency, and recovery after network interruption**. Keep unrun results `NOT_RUN`, and never claim that unit tests prove formal privacy guarantees.

Primary source links: [QM tests](https://github.com/yc-software/qm/tree/095a4bcc719058162a041258e246a58b1329f19e/test) · [QM memory record provenance](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/memory-records.md) · [Ekko architecture](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/ARCHITECTURE.md).
