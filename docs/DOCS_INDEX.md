# Documentation Index

## Start here

| Doc | Purpose |
|-----|---------|
| [PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md](PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md) | **High-level scope** — what’s built, DB→API→web, gaps, E2E chains |
| [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) | **Architecture, ops, troubleshooting** — primary reference |
| [RELEASE_v5.0_STABLE.md](RELEASE_v5.0_STABLE.md) | v5.0 stable release notes |
| [../QUICK_START.md](../QUICK_START.md) | Start/stop/status |

## Reference

| Doc | Purpose |
|-----|---------|
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | Coding standards |
| [CLEANUP_PLAN.md](CLEANUP_PLAN.md) | Post-development cleanup (merge, rename, placeholders; includes remaining doc tasks) |
| [PROJECT_CAPABILITIES_BRIEF.md](PROJECT_CAPABILITIES_BRIEF.md) | Capabilities overview |
| [API_REFERENCE.md](API_REFERENCE.md) | API reference |
| [API_ALIGNMENT.md](API_ALIGNMENT.md) | API–frontend routes and article fields alignment |
| [DATABASE_SCHEMA_DOCUMENTATION.md](DATABASE_SCHEMA_DOCUMENTATION.md) | Schema |

## Setup & configuration

| Doc | Purpose |
|-----|---------|
| [SETUP_AND_DEPLOYMENT.md](SETUP_AND_DEPLOYMENT.md) | Setup guide |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | **Web→API connections** — base URL, proxy, why data doesn’t load, connection status, checklist |
| [VENV_AND_GPU_SETUP.md](VENV_AND_GPU_SETUP.md) | Venv, GPU |
| [OLLAMA_SETUP.md](OLLAMA_SETUP.md) | Ollama |
| [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) | NAS rollback, storage |
| [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) | SSH keys for monitoring remote devices (Widow, NAS, Pi) |

## Migration & planning

| Doc | Purpose |
|-----|---------|
| [MIGRATION_TODO.md](MIGRATION_TODO.md) | Migration checklist |
| [MIGRATION_THREE_MACHINE.md](MIGRATION_THREE_MACHINE.md) | Full migration plan |
| [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md) | Controller design |
| [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) | Path to orchestrator-controlled, initiative-taking app with user guidance |
| [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) | **Context-centric model** — contexts, entity mapping, living profiles, claims, patterns; aligns with coding style and v6 entity work |
| [CONTEXT_CENTRIC_MIGRATION_READINESS.md](CONTEXT_CENTRIC_MIGRATION_READINESS.md) | **Pre-collection checklist** — confirm context-centric is primary; what’s incorporated vs dual-mode; verification steps |
| [CONTEXTS_BY_DOMAIN.md](CONTEXTS_BY_DOMAIN.md) | **Contexts by domain** — why politics vs finance use the same pipeline; no finance contexts = no finance feeds/articles; how to add feeds and sync |
| [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | v6 quality-first upgrades (entity dossiers, event tracking, documents, narrative) — adapted to coding style |
| [V6_QUALITY_FIRST_TODO.md](V6_QUALITY_FIRST_TODO.md) | Prioritized to-do list for v6 quality-first work |

## Domains & features

| Doc | Purpose |
|-----|---------|
| [WEB_PRODUCT_DISPLAY_PLAN.md](WEB_PRODUCT_DISPLAY_PLAN.md) | **Intelligence dashboard** — audience, landing dashboard (hero + 3 columns), nav (Discover/Investigate/Monitor/Analyze), entity/context templates, user flows, implementation phases; aligned with React/Vite/MUI and existing Intelligence pages |
| [DOMAIN_1_NEWS_AGGREGATION.md](DOMAIN_1_NEWS_AGGREGATION.md) through [DOMAIN_6_SYSTEM_MONITORING.md](DOMAIN_6_SYSTEM_MONITORING.md) | Domain reference |
| [FINANCE_PIPELINE.md](FINANCE_PIPELINE.md), [FINANCE_TODO.md](FINANCE_TODO.md) | Finance domain |
| [LOGGING_SYSTEM_SUMMARY.md](LOGGING_SYSTEM_SUMMARY.md) | Logging |
| [FRONTEND_DEBUGGING_GUIDE.md](FRONTEND_DEBUGGING_GUIDE.md) | Frontend debug |

## Repo and context hygiene

| Doc | Purpose |
|-----|---------|
| [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) | **Git and Cursor** — what’s ignored, commit in small chunks, optional disk cleanup |

## Archived

Historical and superseded docs live in `docs/_archive/` (and are excluded from Cursor context via `.cursorignore`). Use the index above for current docs.

- **Context-centric:** `_archive/CONTEXT_CENTRIC_TRANSITION_PLAN_ORIGINAL.md` — superseded by [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md).
- **v6 planning (pre-docs consolidation):** `_archive/v6-planning/` — superseded by [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) and [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md).
- **Other archived:** One-time or outdated: OVERNIGHT_FRESH_NEWS_GOAL, DATA_INGESTION_PIPELINE_ASSESSMENT, RELEASE_v4.1_WIDOW_MIGRATION, PHASE5_DEPLOYMENT, FINANCE_INFRASTRUCTURE_*, DEVELOPMENT_METHODOLOGY, ORCHESTRATOR_DEVELOPMENT_PLAN, ORCHESTRATOR_TODO, EVIDENCE_AND_CONTROLLER_STATE, ARCHITECTURAL_STANDARDS, GPU_SETUP, PROJECT_MAP, REBOOT_CHECKLIST, plus older v4/NAS/Claude docs. Full list: `ls docs/_archive/*.md docs/_archive/**/*.md`.
