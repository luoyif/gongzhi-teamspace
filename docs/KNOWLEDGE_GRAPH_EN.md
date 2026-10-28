# Gongzhi Knowledge Flow Graph — evidence, review and controlled sharing

[English README](../README.en.md) · [中文版](KNOWLEDGE_GRAPH_ZH.md) · [Product comparison](WHY_GONGZHI_EN.md)

> The graph answers **where a team conclusion came from, what was actually executed, who reviewed it, and whether it was deliberately shared**. It does not invent a causal/semantic relationship because two passages sound alike.

## Two complementary views

**Task evidence graph:** Inside an existing project's task discussion, expand **Knowledge Flow & Evidence** in the right sidebar. Click **Open full relationship graph** to inspect task messages, original uploads, Agent Runs, tool-event receipts, human review, project documents and explicit publication snapshots. Nodes expose IDs, revisions, SHA-256 fingerprints, approval status and authorization scope. Real files and Run Trace remain behind their original backend access checks.

**Organization knowledge graph:** Open the company's **Knowledge & Memory** page and select the graph. Company members can see knowledge intentionally published into the company library. A user who is **not a member of the originating project** cannot see that project's raw document ID, original task, or private source contents. A new grant makes eligible sources visible; revoking it hides them on the next request. Published snapshot contents remain deliberately shared even if their original source is private.

Nothing is automatically uploaded to an external graph database, and viewing the graph does **not** call an LLM or start any agent work.

## Actual browser captures (isolated synthetic project)

**Task graph and clickable evidence inspector**

![Task evidence map](images/v017/01-task-knowledge-map.webp)

**Company graph with authorized source relationships**

![Company provenance map](images/v017/02-company-knowledge-map.webp)

**Company member without access to the original project**

![Published snapshot visible while source project remains restricted](images/v017/03-company-restricted-source.webp)

**Mobile task graph**

![Scrollable provenance map on mobile](images/v017/04-mobile-knowledge-map.webp)

These images are real Gongzhi browser captures made with two synthetic accounts and an isolated WSL service. They are neither QM/Ekko screenshots nor production customer data.

## Evidence semantics — what a relation means

| Graph element | Authoritative underlying state | What it does **not** mean |
|---|---|---|
| Message | Stored message ID, author, sequence, task ID, content hash | Every statement is verified |
| Agent Run | Persisted run, status and related tool-event metadata | A model's claim of success was independently validated |
| Original upload | Upload receipt, filename, origin and linked document | File bytes are publicly readable |
| Human review | Recorded approver, status, review note hash | A mathematically proven outcome |
| Project knowledge | Adopted **and** ready project document | Automatically accessible to all teams |
| Published snapshot | Separate explicit company knowledge row, revision and publication state | Membership to the source project or unrestricted raw-file access |

The graph is derived deterministically from stored IDs and verified join relationships. It never fabricates edges from natural-language similarity. It deliberately avoids returning raw chat bodies, hidden reasoning, full tool responses, provider prompts, or credentials.

## Permission and performance guarantees within the current design

- Task reads require fresh project membership and a readable task. Company reads require company membership, and private source expansion independently checks source project membership. Shared Agent configuration grants no access by itself.
- The company view excludes private task/document IDs and titles for members lacking the source project's grant; only deliberately published snapshot metadata can remain.
- There is **no automatic sensitivity classifier** in this release. Nodes are marked *unclassified* where appropriate. This is not a privacy proof; QM's provenance and sensitivity governance remains more developed.
- Bounded read queries (e.g., up to 90 recent messages, 24 Runs, 30 task documents and 100 company publications) explicitly mark partial results and preserve references for source read-back.
- The graph loads when a member expands its panel, and SVG rendering happens locally inside the browser. Mobile horizontal scrolling is constrained to the visualization rather than the whole application.

## What kind of knowledge graph is this?

This is an **auditable provenance/knowledge-flow graph**, not an automatically mined conceptual/semantic entity graph. It links operational facts: source file → message → model action/tool event → reviewed artifact → deliberate company publication. A later semantic layer could add tentative concept relations, but only when human-verified relationships and inferred suggestions are visually and contractually separated.

Gongzhi's product distinction from **[QM](https://github.com/yc-software/qm)** and **[Ekko Studio](https://github.com/EKKOLearnAI/ekko-studio)** is its *default task-to-reviewed-knowledge journey*. It is not a claim those projects lack scope controls, memory provenance, DAG workflows or multi-agent messaging. In fact, QM has stronger classified-scope memory and durable sandbox capabilities today; Ekko offers more general visual workflow orchestration.

Read the honest [three-way comparison](WHY_GONGZHI_EN.md) and its [reproducible testing matrix](TEST_MATRIX_EN.md).

## Limitations and future work

The current release does not implement a semantic ontology, automatic fact truth verification, full company-wide provenance search across every private source, mature sensitivity classification, autonomous swarms, persistent per-user cloud computers, or a general parallel/conditional DAG engine. Those remain independently gated projects.

Each source row is re-authorized before projection. Real-world model accuracy, shared credentials, arbitrary user-generated code and deployment-specific security still require their own reviews. The new graph does not make an untrusted Agent or a model prompt into an authorization authority.
