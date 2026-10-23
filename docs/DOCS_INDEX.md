# Documentation index

Use this index for **current** documentation. See **[../PROJECT_STATUS.md](../PROJECT_STATUS.md)** for host authority (Widow is canonical; PopOS copy is cold storage).

**Proposals and retired docs:** [`_archive/retired_root_docs_2026_03/`](_archive/retired_root_docs_2026_03/README.md)

---

## Project status and boundaries

| Doc | Purpose |
|-----|---------|
| [../PROJECT_STATUS.md](../PROJECT_STATUS.md) | Migration complete; Widow paths; cold storage checklist |
| [../../PROJECT_BOUNDARIES.md](../../PROJECT_BOUNDARIES.md) | NI vs HomeLab AI Stack split |
| [SECRETS_AND_SETTINGS_INDEX.md](SECRETS_AND_SETTINGS_INDEX.md) | Env and secrets locations (paths only) |

---

## Reviewers (navigation and pipelines)

| Doc | Purpose |
|-----|---------|
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | Directory map — API / web / scripts layout. |
| [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) | Pipeline phases, automation, order of operations; Ollama CB defer/shed/overload. |
| [MONITOR_REPORTING_AND_METRICS.md](MONITOR_REPORTING_AND_METRICS.md) | Monitor vs Grafana; health/`ni_*`; **Ollama backpressure** + CB reset. |
| [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) | **Reboot / systemd runbook** — boot stack, verify, troubleshooting. |
| [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md) | **Widow operator checklist** — schedulers, full phase list, `.env`. |
| [CODE_REVIEW_AND_RUN_CAVEATS.md](CODE_REVIEW_AND_RUN_CAVEATS.md) | Run requirements and ops caveats. |

---

## System and data flow

| Doc | Purpose |
|-----|---------|
| [KNOWLEDGE_LOOP.md](KNOWLEDGE_LOOP.md) | **Product intent** — content improves over time; materiality gate, prior canonical, narrow debt, vault twin. |
| [RESEARCH_PAPER_PATHWAY.md](RESEARCH_PAPER_PATHWAY.md) | Research twin — papers → appraisal → subject ledger / knowledge_profiles → `/research` board. |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | System map — routes, UI, services. |
| [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) | Hosts, DB, Widow, scripts, pipeline visibility. |
| [PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md](PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md) | Ingestion through storylines and editorial. |
| [STORYLINE_HISTORICAL_MEMORY.md](STORYLINE_HISTORICAL_MEMORY.md) | Memory vs hot queues; narrative finisher env knobs. |
| [DATABASE.md](DATABASE.md) | **Canonical DB reference** — connection, schema, pools. |
| [API_REFERENCE.md](API_REFERENCE.md) | API endpoint areas and methods. |
| [WIDOW_SERVER_MIGRATION_2026_06.md](WIDOW_SERVER_MIGRATION_2026_06.md) | Migration record (completed June 2026). |
| [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md) | Public HTTPS: PopOS Caddy → Widow nginx. |
| [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) | Public demo env, TLS, read-only mode. |
| [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) | Router DDNS + port forward to PopOS Caddy. |
| [WIDOW_DEVELOPMENT_MOUNT.md](WIDOW_DEVELOPMENT_MOUNT.md) | Remote SSH / SSHFS access to Widow. |

---

## API, web, and implementation rules

| Doc | Purpose |
|-----|---------|
| [DOMAIN_EXTENSION_TEMPLATE.md](DOMAIN_EXTENSION_TEMPLATE.md) | Adding a YAML-onboarded silo. |
| [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md) | PDF ingestion pipeline. |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | Web → API base URL, proxy, checklist. |
| [PGBOUNCER_AND_CONNECTION_BUDGET.md](PGBOUNCER_AND_CONNECTION_BUDGET.md) | Connection pooling and PgBouncer. |
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | Naming, patterns, project layout. |
| [_archive/retired_root_docs_2026_03/IMPLEMENTATION_CONSTRAINTS.md](_archive/retired_root_docs_2026_03/IMPLEMENTATION_CONSTRAINTS.md) | Hard rules (archived copy). |
| [API_TESTING_GUIDE.md](API_TESTING_GUIDE.md) | API testing. |
| [FRONTEND_DEBUGGING_GUIDE.md](FRONTEND_DEBUGGING_GUIDE.md) | Frontend debugging. |

---

## Setup, security, and deployment

| Doc | Purpose |
|-----|---------|
| [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) | Install, `.env`, DB, migrations, Ollama, GPU. |
| [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) | Exposure, secrets, SSH. |
| [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) | Public HTTPS read-only demo. |
| [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) | Widow DB-adjacent cron. |
| [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md) | Widow public stack notes. |
| [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) | SSH keys for monitoring. |
| [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) | NAS rollback and storage. |
| [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) | DDNS on Widow. |

---

## Database operations

| Doc | Purpose |
|-----|---------|
| [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md) | Prod maintenance, migrations ledger. |
| [DATABASE_BACKUP.md](DATABASE_BACKUP.md) | Backup policy and scripts. |

---

## Troubleshooting and feature guides

| Doc | Purpose |
|-----|---------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues (incl. Ollama CB reset vs API restart). |
| [EVENTS_ZERO_AND_HOW_TO_POPULATE.md](EVENTS_ZERO_AND_HOW_TO_POPULATE.md) | Populate `tracked_events`. |
| [MONITOR_BLOCKAGES_AND_GPU.md](MONITOR_BLOCKAGES_AND_GPU.md) | Monitor / GPU blockages. |
| [MONITOR_REPORTING_AND_METRICS.md](MONITOR_REPORTING_AND_METRICS.md) | Live health, pulse, CB reset, defer/shed/overload terms. |
| [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md) | Storyline automation. |

---

## Obsidian vault mirror

| Location | Purpose |
|----------|---------|
| [vault/README.md](vault/README.md) | Sync to `/mnt/obsidian-vault` |
| [VAULT_NOTES_AND_PULL_CONTEXT.md](VAULT_NOTES_AND_PULL_CONTEXT.md) | Living vault notes, tag sync, context packs, Pull context (v2 default path) |
| [MEMPALACE_NI.md](MEMPALACE_NI.md) | MemPalace wing/rooms for NI; audit/hygiene (process memory vs app RAG) |

---

## Archived documentation

| Location | Purpose |
|----------|---------|
| [_archive/retired_root_docs_2026_03/](_archive/retired_root_docs_2026_03/README.md) | Retired root docs (March 2026). |
| [_archive/ni_review_mirror_2026_06/](_archive/ni_review_mirror_2026_06/README.md) | Retired `scripts/ni_review/docs/` mirror. |
| [_archive/](_archive/) | Older release notes, deprecated guides. |

---

## Quick links

- **Root README:** [../README.md](../README.md)
- **AGENTS.md:** [../AGENTS.md](../AGENTS.md)
- **QUICK_START.md:** [../QUICK_START.md](../QUICK_START.md)
