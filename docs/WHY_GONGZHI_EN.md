# Why Gongzhi? Comparing QM, Ekko Studio, and Gongzhi

> Gongzhi is a **task-centered, evidence-aware team knowledge workflow**, not just another chatroom with several agents attached.
>
> Date: 2026-10-25. Comparisons are to pinned source revisions: QM `095a4bcc719058162a041258e246a58b1329f19e`, Ekko `a2a5e876cec566a52e1e1873c96524a8dbf9a9e2`; Gongzhi's publicly reproducible base here is v0.16.0.

## What we learned from the other two

**[QM](https://github.com/yc-software/qm)** offers a serious scope-centered approach: each person and shared room has separate memory, permissions, keychain view, files, background jobs and durable computers. Its implementation includes record-level source/sensitivity labels, audience checks, delegated sessions, sandbox recovery, pinned skill packs and operator-owned deployments. **We should learn from it rather than claim Gongzhi invented these controls.**

**[Ekko Studio](https://github.com/EKKOLearnAI/ekko-studio)** offers multi-agent group chat, multiple runtime adapters, a well-developed UI, context snapshot compaction and executable visual workflows. We can adopt the interaction principles and interfaces through independent implementation. Its **BSL 1.1 license** is not equivalent to MIT, so its source and components are not imported into Gongzhi.

**Gongzhi's product thesis** is different: every collaboration thread has an explicit **team → project → task** owner. A chat message, an agent's answer, a real tool receipt, a human's acceptance, a project knowledge item, and an explicitly published company snapshot are **different states**. The main user journey is from problem to auditable deliverable and then reviewed, reusable knowledge.

## Honest capability comparison

| Dimension | QM (MIT) | Ekko Studio (BSL 1.1) | Gongzhi 0.16 (MIT original code) |
|---|---|---|---|
| Primary boundary | Person and room Scope | Profile, Session and Group Room | Team → Project → **Task** |
| Collaboration | Slack + Web, internal team rooms | Humans + multiple Agents in rooms | Real-time multi-human task chat and explicit @AI |
| Agent operation | Multiple harnesses, persistent subagents and swarms | Multiple runtimes, handoffs, DAG | **Two sequential agents, owner approval, max two hops** |
| Memory/audience | Provenance/sensitivity labelled revision records, fresh grants | Profile/room memory, snapshot+cursor compaction | Task snapshot with source hash; reviewed project knowledge; explicit company publication |
| Planning | Durable background tasks, crons, sandbox workers | DAG workflow and approvals | **2–8-step task-local sequential plan with human review** |
| Security | Rich scope and credential boundaries, documented gaps | Room/member ACL and agent execution controls | Project ACL + explicit @/tool approval + controlled knowledge promotion |
| Self-hosting | Own cloud, Postgres and scope computers | Web/Desktop with multiple agent CLIs | Lightweight Windows WSL2/Linux Web and single-instance SQLite |
| Advantage | Scope governance & long-running compute | Agent orchestration & mature UX | **Task accountability and review-to-knowledge lifecycle** |
| Current limits | Operator complexity, acknowledged experimental security gaps | Source reuse for commercial products requires review/license | No persistent private computers, Slack, automatic agent swarm or general DAG |

This is a product-workflow distinction, **not a claim that QM or Ekko cannot technically create a similar flow**. They already have substantial provenance, role policy and skill governance mechanisms.

## Three concrete jobs Gongzhi is designed to finish

**1. From product research to adopted company knowledge.** Several people discuss a research task with source PDFs/Word files. The research AI creates a source-backed proposal, an engineering agent creates a design after explicit approval, a reviewer checks the actual run and artifact, and an administrator may publish one reviewed project result to the team. Other projects should retrieve the **published snapshot**, never the unpublished task chat merely because they use the same agent.

**2. Cross-agent work without repeated side effects.** Research → engineer → human QA happens inside one task, with a separate bounded Run for each agent and explicit approval between steps. A duplicate click, disconnection or model failure must not silently run an already-confirmed business operation again.

**3. Audit and correct a team decision.** When an earlier statement is revised, the original message ID, speaker and source hash remain available. The task summary is marked stale if earlier messages change. An accepted artifact is distinct from a company publication, and revoking a published snapshot removes it from authorized downstream retrieval without rewriting the original project history.

## Tests and evidence — no unfair numerical comparisons

| Source | Actually checked | Not established |
|---|---|---|
| QM pinned source | **31 tests passed** for cross-scope disclosure and incremental memory recall, isolated Node environment | Not a whole QM deployment, cloud-sandbox or security certification |
| Ekko pinned source | Architectural and implementation review; earlier source scan | No independent full runtime/E2E pass claimed |
| Gongzhi 0.16 | **340 Python unit tests, 15 API/Octop suites, 35 JS tests, 18 Chrome checks**, plus existing-data migration/HTTP verification | Not universal model correctness, production-scale concurrency or arbitrary DAG |
| New knowledge-flow evidence graph | Experimental local branch; requires full WSL/integration/browser gate | **Not shipped in v0.16** until that gate passes |

Read the [precise test matrix](TEST_MATRIX_EN.md), including the individual invariant checks and what each test does *not* demonstrate. Test counts are not a ranking of the three products.

## Next improvements

1. **Adopt QM's best scope ideas:** add explicit provenance/audience metadata and fail-closed sharing reviews, without relaxing Gongzhi's project ACL or task binding.
2. **Make task knowledge auditable:** a compact task-local provenance graph built from actual message, Run, document revision, human review and company publication IDs; never use an LLM to invent the edges.
3. **Govern skill imports:** pinned source revision, eligibility/collision checks, operator review before enabling an imported Skill.
4. **Evolve bounded orchestration:** task-local approval/conditional DAG nodes first, read-only multi-agent comparison second; preserve separate authority and idempotency.
5. **Keep deployment lightweight:** Postgres, distributed background ownership and durable sandbox adapters are future choices, not an immediate rewrite of working WSL/Linux deployment.

## Primary sources pinned to the versions reviewed

QM: [README](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/README.md) ·
[Security](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/SECURITY.md) ·
[Memory records](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/memory-records.md) ·
[Subagent sessions](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/persistent-subagent-sessions.md) ·
[Skill pack registry](https://github.com/yc-software/qm/blob/095a4bcc719058162a041258e246a58b1329f19e/docs/skill-registry.md).

Ekko: [Architecture](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/ARCHITECTURE.md) ·
[Handoff](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/packages/server/src/modules/studio/services/group-chat/handoff-depth.ts) ·
[Workflow](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/packages/server/src/modules/studio/services/workflow/manager.ts) ·
[License](https://github.com/EKKOLearnAI/ekko-studio/blob/a2a5e876cec566a52e1e1873c96524a8dbf9a9e2/LICENSE).

All comparisons refer to these exact commits and are subject to upstream changes.
