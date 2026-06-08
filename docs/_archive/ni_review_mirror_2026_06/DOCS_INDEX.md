# Documentation index

Use this index for **current** documentation: architecture, how the API and database fit together, setup, security, and operations. **Proposals, plans, strategy docs, release-style summaries, and long-form feature write-ups** that used to sit beside these files are in [`_archive/retired_root_docs_2026_03/`](_archive/retired_root_docs_2026_03/README.md).

---

## Reviewers (navigation and pipelines)

| Doc | Purpose |
|-----|---------|
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | Directory map — API / web / scripts layout and reading order. |
| [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md) | What runs when — automation phases; points to `automation_manager.py`. |
| [CODE_REVIEW_AND_RUN_CAVEATS.md](CODE_REVIEW_AND_RUN_CAVEATS.md) | Run requirements and why casual local deploy is not recommended. |

---

## System and data flow

| Doc | Purpose |
|-----|---------|
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | System map — routes, UI, services, file layout. |
| [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) | Hosts, DB, Widow, scripts, pipeline visibility. |
| [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) | Intelligence cascade — ingestion through storylines and editorial. |
| [DATABASE.md](DATABASE.md) | **Canonical DB reference** — schemas, who reads/writes what. |
| [API_REFERENCE.md](API_REFERENCE.md) | **API reference** — endpoint areas and methods. |

---

## API, web, and implementation rules

| Doc | Purpose |
|-----|---------|
| [DOMAIN_EXTENSION_TEMPLATE.md](DOMAIN_EXTENSION_TEMPLATE.md) | Adding an optional domain — YAML, registry, validation (`api/config/domains/README.md`). |
| [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md) | PDF ingestion — collectors, download, extraction (see code: `document_download_service.py`). |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | Web → API — base URL, proxy, checklist. |
| [DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md) | DB connection single source of truth. |
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | Naming, patterns, project layout. |
| [IMPLEMENTATION_CONSTRAINTS.md](IMPLEMENTATION_CONSTRAINTS.md) | Hard rules and verification checklists. |
| [API_TESTING_GUIDE.md](API_TESTING_GUIDE.md) | API testing. |
| [FRONTEND_DEBUGGING_GUIDE.md](FRONTEND_DEBUGGING_GUIDE.md) | Frontend debugging. |

---

## Setup, security, and deployment

| Doc | Purpose |
|-----|---------|
| [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) | Install, `.env`, DB, migrations, Ollama, GPU. |
| [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) | Exposure, secrets, SSH, untrusted input. |
| [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) | Public HTTPS read-only demo (`NEWS_INTEL_DEMO_*`, etc.). |
| [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) | Widow DB-adjacent cron (RSS, flush, sync). |
| [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md) | Widow public stack notes. |
| [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) | SSH keys for monitoring hosts. |
| [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) | NAS rollback and storage. |
| [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) | DDNS on Widow. |

---

## Database operations

| Doc | Purpose |
|-----|---------|
| [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md) | Prod/staging maintenance, migrations ledger. |
| Deep assessment & cleanup bundles | Archived: [_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md](_archive/retired_root_docs_2026_03/DB_FULL_ASSESSMENT.md), [_archive/retired_root_docs_2026_03/DB_CLEANUP_BUNDLES.md](_archive/retired_root_docs_2026_03/DB_CLEANUP_BUNDLES.md) |

---

## Troubleshooting and feature guides (current)

| Doc | Purpose |
|-----|---------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues. |
| [EVENTS_ZERO_AND_HOW_TO_POPULATE.md](EVENTS_ZERO_AND_HOW_TO_POPULATE.md) | `tracked_events` empty — how to populate. |
| [MONITOR_BLOCKAGES_AND_GPU.md](MONITOR_BLOCKAGES_AND_GPU.md) | Monitor / GPU blockages. |
| [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md) | Storyline automation. |

---

## Generated reports (do not edit by hand)

| Location | Purpose |
|----------|---------|
| [generated/README.md](generated/README.md) | How to regenerate pipeline alignment, storyline/event chains, intelligence-phase productivity reports. |

---

## Repo maintenance

| Doc | Purpose |
|-----|---------|
| [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) | Git, Cursor, commit practice. |
| [GITIGNORE.md](GITIGNORE.md) | `.gitignore` rationale. |
| [OBFUSCATION.md](OBFUSCATION.md) | Public-repo placeholders and scrub tooling. |
| [archive/CLEANUP_2026_03.md](archive/CLEANUP_2026_03.md) | Housekeeping log (trees moved to `docs/archive/`). |

---

## Archived documentation (policy)

| Location | Purpose |
|----------|---------|
| [_archive/retired_root_docs_2026_03/](_archive/retired_root_docs_2026_03/README.md) | **Retired `docs/*.md` root files** — plans, summaries, strategy, long-form feature docs (March 2026). |
| [_archive/](_archive/) | Older release notes, deprecated guides, v4/v6 copies, consolidated legacy pages. |
| [archive/planning_incubator/](archive/planning_incubator/README.md) | Proposals not shipped. |

---

## Quick links

- **Root README:** [../README.md](../README.md)
- **AGENTS.md:** [../AGENTS.md](../AGENTS.md) (terminology, entry points)
- **Quick start:** [../QUICK_START.md](../QUICK_START.md) (if present)
