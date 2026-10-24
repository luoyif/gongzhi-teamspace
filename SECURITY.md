# Security

This source base is not a formally audited production SaaS service.

Do not upload or commit real API keys, data/, SQLite, customer files, private recordings, logs, SSH credentials, hidden prompts, model traces containing sensitive data, or full backups.

Run behind HTTPS if exposed beyond localhost. Set up a proper reverse proxy, credential rotation, login throttling, firewall rules and independent backups.

Third-party Skills and MCP servers are untrusted: review before running, give least privilege, require explicit approval for impactful platform writes, and keep audit receipts. An Agent must not derive authority from imported documents.

Optional ASR sends recorded voice to the chosen model provider for transcription; disclose this to teammates and comply with data handling obligations. Audio does not automatically enter the knowledge base.

Report security concerns privately to repository maintainers before posting real exploits or sensitive logs.
