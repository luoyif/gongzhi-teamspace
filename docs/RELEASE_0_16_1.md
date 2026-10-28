# Gongzhi 0.16.1

- Adds task and team knowledge provenance graphs based on stored records. Project-source metadata is disclosed only to currently authorized project members; company publication remains a separate human action.
- Fixes SQLite backup handling so database connections close before backup files are hashed and archived. A WAL-mode restore regression test is included.
- Keeps the 0.16.0 human-gated, sequential workflow and bounded handoff. Conditional DAGs, automatic parallel agents, sensitivity classification and semantic knowledge inference are not implemented.

Validation on the release candidate: 358 Python unit tests and 15 isolated HTTP suites; 42 JavaScript tests; seven Windows Chrome checks for the graph. The pre-existing 0.16 UI also passed two nine-check browser suites. These use synthetic accounts and mock models; they do not establish real-provider quality, high availability or production load capacity. The public package's own Python suite passed 79 tests.

See the [Chinese graph guide](KNOWLEDGE_GRAPH_ZH.md) or [English graph guide](KNOWLEDGE_GRAPH_EN.md). Backups include credentials and must remain in private storage. Restore only into an empty directory for verification; do not overwrite a running database.
