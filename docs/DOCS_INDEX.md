# Documentation Index

Use this index to find the right document. **Project-facing** docs (overview, database, API) are listed first; **planning and development history** are in a separate archive.

---

## Reviewers (navigation and pipelines)

| Doc | Purpose |
|-----|---------|
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | **Directory map** — API/web/scripts layout, high-interest files, reading order. |
| [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md) | **v8 automation** — collection cycle vs analysis phases; mermaid + pointers to `automation_manager.py`. |
| [CODE_REVIEW_AND_RUN_CAVEATS.md](CODE_REVIEW_AND_RUN_CAVEATS.md) | **Run requirements** and **why casual local deploy is not recommended** (DB, Ollama, compose drift, lab defaults). |

---

## Project documentation (what it is and how it works)

| Doc | Purpose |
|-----|---------|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | **How the project works** — end-to-end flow, pipeline, concepts, **capabilities snapshot**, **scope/status** (replaces separate brief/scope docs) |
| [DATABASE.md](DATABASE.md) | **Database reference** — schema layout (domain + intelligence), data I/O, who writes/reads what |
| [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md) | **Full DB assessment** — four-surface matrix, persistence gates, baseline snapshots, expert checklist |
| [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md) | **Cleanup bundles A/B/C** — non-destructive vs archive vs destructive (pre-delete checklist) |
| [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md) | **Prod/staging DB maintenance** — ordered steps, rollback, applied_migrations ledger |
| [PIPELINE_DB_ALIGNMENT_REPORT.md](PIPELINE_DB_ALIGNMENT_REPORT.md) | **Generated** — refresh via `scripts/verify_pipeline_db_alignment.py --write-report …` (see [generated/README.md](generated/README.md)) |
| [STORYLINE_EVENT_ENTITY_CHAINS.md](STORYLINE_EVENT_ENTITY_CHAINS.md) | **Storylines ↔ events ↔ entities** — how continuation matches events to storylines; report file is generated (see [generated/README.md](generated/README.md)) |
| [INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md](INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md) | **Generated** — refresh via `scripts/verify_intelligence_phases_productivity.py` (see [generated/README.md](generated/README.md)) |
| [CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md](CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md) | **Claims → facts** — how `promote_claims_to_versioned_facts` resolves subjects to `entity_profiles`; prior bug (`display_name` / bad join) and verification scripts |
| [SOURCE_CREDIBILITY.md](SOURCE_CREDIBILITY.md) | **Source credibility tiers** — `orchestrator_governance.yaml` `source_credibility`; RSS quality scaling, `articles`/`contexts` metadata, claim confidence |
| [NARRATIVE_BOOTSTRAP_AND_DB_OUTAGE.md](NARRATIVE_BOOTSTRAP_AND_DB_OUTAGE.md) | **Proactive cluster → domain storyline** promotion + **DB outage** pause + `pending_db_flush` / `.local/db_pending_writes` |
| [API_REFERENCE.md](API_REFERENCE.md) | **API reference** — every endpoint area, method + path, integrations |
| [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) | **Architecture and ops** — three-machine setup, DB config, Widow, scripts, pipeline and automations, troubleshooting |
| [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) | **Security** — mixed LAN/internet exposure, env toggles, secrets, SSH, untrusted input (RSS/HTML/LLM) |
| [DOMAIN_EXTENSION_TEMPLATE.md](DOMAIN_EXTENSION_TEMPLATE.md) | **Adding an optional domain** — onboarding YAML, registry, validation one-liner, links to `api/config/domains/README.md` and `provision_domain.py` |
| [LEGAL_DOMAIN_DEPLOYMENT.md](LEGAL_DOMAIN_DEPLOYMENT.md) | **Legal domain (first expansion)** — provision/rollback, ledger, RSS seeds, synthesis config, UI cutover |
| [STORYLINE_70B_NARRATIVE_FINISHER.md](STORYLINE_70B_NARRATIVE_FINISHER.md) | **~70B narrative finisher** — final editorial pass on storylines; consumes 8B/Mistral outputs; durable narrative + config (`NARRATIVE_FINISHER_MODEL`) |

---

## Releases

| Doc | Purpose |
|-----|---------|
| [RELEASE_v8.0.md](RELEASE_v8.0.md) | **Current** — collect-then-analyze, full-history awareness, pipeline-ordered analysis |
| [_archive/releases/](_archive/releases/) | Older release notes (v7, v5, dossier wire-in) — historic only |

---

## Architecture and design

| Doc | Purpose |
|-----|---------|
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | **System map** — API routes, web UI, data flow, key services, file layout |
| [CORE_ARCHITECTURE_PRINCIPLES.md](CORE_ARCHITECTURE_PRINCIPLES.md) | **Four principles** — Content is King, Intelligence Accumulates, Narratives Over Metrics, Editorial Documents are Primary |
| [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) | **Intelligence cascade** — ingestion → ML → entities → contexts → claims/events → storylines → editorial |
| [IMPLEMENTATION_CONSTRAINTS.md](IMPLEMENTATION_CONSTRAINTS.md) | **Hard rules** — code patterns, verification checklists |
| [API_DESIGN_PRINCIPLES.md](API_DESIGN_PRINCIPLES.md) | **API standards** — narrative-first endpoints, editorial fields |
| [DATABASE_DESIGN_PHILOSOPHY.md](DATABASE_DESIGN_PHILOSOPHY.md) | **Schema philosophy** — editorial_document / editorial_briefing / sections JSONB |
| [ORCHESTRATION_REQUIREMENTS.md](ORCHESTRATION_REQUIREMENTS.md) | **Pipeline requirements** — phase checks, health queries |
| [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md) | **Story assembly** — contexts/entities → Report, Briefing, synthesis; caps vs minimums |
| [BRIEFING_STRATEGY_AND_PROCESSES.md](BRIEFING_STRATEGY_AND_PROCESSES.md) | **Briefing generation** — daily/weekly, editorial-first, LLM lead |

---

## Reference

| Doc | Purpose |
|-----|---------|
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | **Coding standards** — naming, patterns, project layout |
| [DATABASE_SCHEMA_DOCUMENTATION.md](DATABASE_SCHEMA_DOCUMENTATION.md) | Legacy schema reference (v3-era); see [DATABASE.md](DATABASE.md) for current. |
| [API_ALIGNMENT.md](API_ALIGNMENT.md) | API–frontend routes and article fields alignment |
| [UI_PIPELINE_AUDIT_GUIDE.md](UI_PIPELINE_AUDIT_GUIDE.md) | **Audit UI** — pipeline layer checklist, storyline/timeline reliability, cross-entity checks, synthesis provenance |
| [CONTENT_QUALITY_STANDARDS.md](CONTENT_QUALITY_STANDARDS.md) | **Content quality** — 4-tier quality, content_quality_service, briefing prioritization |
| [BRIEFING_FILTERS_AND_FEEDBACK.md](BRIEFING_FILTERS_AND_FEEDBACK.md) | **Briefing filters and feedback** — not interested, usefulness, low-priority entities/keywords |
| [AUTOMATION_AND_LAST_24H_ACTIVITY.md](AUTOMATION_AND_LAST_24H_ACTIVITY.md) | **What ran / what was collected** — last-24h report, automation sources |
| [CONTENT_COLLECTION_AND_INSIGHT_EXPECTATIONS.md](CONTENT_COLLECTION_AND_INSIGHT_EXPECTATIONS.md) | **What to expect** — collection/processing cadence, backlogs |
| [ARTICLE_ENTITY_SCHEMA_DESIGN.md](ARTICLE_ENTITY_SCHEMA_DESIGN.md) | Article entity and entity_canonical design |
| [ENTITY_KNOWLEDGE_AND_SOURCES.md](ENTITY_KNOWLEDGE_AND_SOURCES.md) | **Entity–knowledge connector** — high-level resolution, when to add vector DB or other sources |
| [DATA_SOURCES_AND_COLLECTION.md](DATA_SOURCES_AND_COLLECTION.md) | Data sources and collection |
| [SOURCES_AND_EXPECTED_USAGE.md](SOURCES_AND_EXPECTED_USAGE.md) | **Master source list** — all sources and expected system usage (RSS, finance APIs, RAG, LLM, documents) |
| [FREE_OPEN_DATA_SOURCES.md](FREE_OPEN_DATA_SOURCES.md) | **Curated free/open sources** — academic, macro, civic, environmental; candidate integrations |
| [RSS_FEED_MANAGEMENT_SYSTEM.md](RSS_FEED_MANAGEMENT_SYSTEM.md) | RSS feed management |
| [FINANCE_PIPELINE.md](FINANCE_PIPELINE.md) | Finance domain pipeline |
| [FINANCE_REFERENCE_SOURCES.md](FINANCE_REFERENCE_SOURCES.md) | Finance reference sources |
| [SCIENCE_TECH_DOMAIN_STRATEGY.md](SCIENCE_TECH_DOMAIN_STRATEGY.md) | **Science-tech domain** — RSS expansion, cross-field linking, capability-aware prompts |
| [RAG_V8_AND_DISCOVERY.md](RAG_V8_AND_DISCOVERY.md) | RAG and discovery (v8) |
| [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md) | Vector schema (pgvector/ChromaDB) |
| [CHRONOLOGICAL_TIMING.md](CHRONOLOGICAL_TIMING.md) | Chronological ordering, time-based queries, timezones |
| [LOGGING_SYSTEM_SUMMARY.md](LOGGING_SYSTEM_SUMMARY.md) | Logging |
| [STORAGE_ESTIMATES_AND_OPTIMIZATION.md](STORAGE_ESTIMATES_AND_OPTIMIZATION.md) | Storage planning and optimization |

---

## Setup and configuration

| Doc | Purpose |
|-----|---------|
| [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) | **Setup and runtime** — install, `.env`, DB, migrations pointers, Ollama, GPU/throttle (canonical) |
| [DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md) | **DB connection** — single source of truth, consistency |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | **Web→API** — base URL, proxy, connection checklist |
| [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) | NAS rollback and storage |
| [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) | SSH keys for monitoring (Widow, NAS, Pi) |

Superseded full copies of the old setup/Ollama/GPU pages: [_archive/consolidated/](_archive/consolidated/) (`SETUP_AND_DEPLOYMENT.md`, `VENV_AND_GPU_SETUP.md`, `OLLAMA_SETUP.md`, `GPU_AND_OLLAMA_MANAGEMENT.md`).

---

## Operations and troubleshooting

| Doc | Purpose |
|-----|---------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **Troubleshooting** — common issues and solutions |
| [EVENTS_ZERO_AND_HOW_TO_POPULATE.md](EVENTS_ZERO_AND_HOW_TO_POPULATE.md) | Tracked events zero (`intelligence.tracked_events`) and how to populate |
| [EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md](EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md) | **Extracted timeline events** (`chronological_events`), automation gates, entity vs event phases, DB poll script |
| [MONITOR_BLOCKAGES_AND_GPU.md](MONITOR_BLOCKAGES_AND_GPU.md) | Monitor blockages and GPU |
| [FRONTEND_DEBUGGING_GUIDE.md](FRONTEND_DEBUGGING_GUIDE.md) | Frontend debugging |
| [LLM_ACTIVITY_MONITORING.md](LLM_ACTIVITY_MONITORING.md) | LLM activity monitoring |
| [OFFICIAL_GOVERNMENT_FEEDS.md](OFFICIAL_GOVERNMENT_FEEDS.md) | Official government feeds |
| [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md) | Storyline automation |

---

## Repo and maintenance

| Doc | Purpose |
|-----|---------|
| [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) | Git and Cursor — what's ignored, commit practice |

---

## Archived

| Location | Purpose |
|----------|---------|
| [archive/planning/](archive/planning/) | **Planning and development history** — roadmaps, build plans, TODOs, assessments, domain planning docs. Kept for historic record-keeping. |
| [_archive/](_archive/) | **Obsolete and legacy docs** — older versions, deprecated guides, previous consolidations. |

---

## Quick links

- **Root README:** [../README.md](../README.md)
- **AGENTS.md (terminology, entry points):** [../AGENTS.md](../AGENTS.md)
- **Quick start:** [../QUICK_START.md](../QUICK_START.md) (if present)
