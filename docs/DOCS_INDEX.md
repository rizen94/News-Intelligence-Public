# Documentation Index

## Start here

| Doc | Purpose |
|-----|---------|
| [PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md](PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md) | **High-level scope** — what’s built, DB→API→web, gaps, E2E chains |
| [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) | **Architecture, ops, troubleshooting** — primary reference |
| [RELEASE_v5.0_STABLE.md](RELEASE_v5.0_STABLE.md) | v5.0 stable release notes |
| [../QUICK_START.md](../QUICK_START.md) | Start/stop/status |

## Architecture & Guardrails

| Doc | Purpose |
|-----|---------|
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | **Full system map** — API routes, web interface, data flow, key services, file layout |
| [CORE_ARCHITECTURE_PRINCIPLES.md](CORE_ARCHITECTURE_PRINCIPLES.md) | **4 principles** — Content is King, Intelligence Accumulates, Narratives Over Metrics, Editorial Documents are Primary |
| [IMPLEMENTATION_CONSTRAINTS.md](IMPLEMENTATION_CONSTRAINTS.md) | **Hard rules** — correct vs incorrect code patterns, verification checklists |
| [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) | **Intelligence cascade** — ingestion → ML → entities → contexts → claims/events → storylines → editorial output; content loss warnings |
| [API_DESIGN_PRINCIPLES.md](API_DESIGN_PRINCIPLES.md) | **API response standards** — narrative-first endpoints, editorial fields, example responses |
| [DATABASE_DESIGN_PHILOSOPHY.md](DATABASE_DESIGN_PHILOSOPHY.md) | **Schema philosophy** — editorial_document / editorial_briefing / sections JSONB structures, design rules |
| [ORCHESTRATION_REQUIREMENTS.md](ORCHESTRATION_REQUIREMENTS.md) | **Pipeline requirements** — phase-by-phase content checks, health queries, missing phases |
| [DEVELOPMENT_GUARDRAILS.md](DEVELOPMENT_GUARDRAILS.md) | **Pre-implementation checklists** — what to check before writing, anti-patterns, code review checklist |
| [CODE_AUDIT_REPORT.md](CODE_AUDIT_REPORT.md) | **Audit results** — 34 violations found and remediated; scorecard, systemic patterns, priority fixes |
| [BRIEFING_STRATEGY_AND_PROCESSES.md](BRIEFING_STRATEGY_AND_PROCESSES.md) | **Briefing generation** — how daily/weekly briefings are built, editorial-first ordering, LLM lead generation |

## Reference

| Doc | Purpose |
|-----|---------|
| [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md) | Coding standards |
| [CLEANUP_PLAN.md](CLEANUP_PLAN.md) | Post-development cleanup (merge, rename, placeholders; includes remaining doc tasks) |
| [PROJECT_CAPABILITIES_BRIEF.md](PROJECT_CAPABILITIES_BRIEF.md) | Capabilities overview |
| [API_REFERENCE.md](API_REFERENCE.md) | API reference |
| [API_ALIGNMENT.md](API_ALIGNMENT.md) | API–frontend routes and article fields alignment |
| [DATABASE_SCHEMA_DOCUMENTATION.md](DATABASE_SCHEMA_DOCUMENTATION.md) | Schema |
| [AUTOMATION_AND_LAST_24H_ACTIVITY.md](AUTOMATION_AND_LAST_24H_ACTIVITY.md) | **What ran / what was collected** — last-24h report script, automation sources, gaps to connect |
| [CRON_LOGS_AND_REPORT_FOR_CLAUDE.md](CRON_LOGS_AND_REPORT_FOR_CLAUDE.md) | **Cron, logs, report + doc list for Claude** — what to pass (in order), paste areas, prompt |
| [CLAUDE_ASSESSMENT_SYSTEM_AND_GAPS.md](CLAUDE_ASSESSMENT_SYSTEM_AND_GAPS.md) | **Claude assessment** — what’s working, gaps, recommendations, P0–P4 action items |

## Setup & configuration

| Doc | Purpose |
|-----|---------|
| [SETUP_AND_DEPLOYMENT.md](SETUP_AND_DEPLOYMENT.md) | Setup guide |
| [DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md) | **DB connection** — single source of truth, why DB fails after migration, consistency fixes |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | **Web→API connections** — base URL, proxy, why data doesn’t load, connection status, checklist |
| [VENV_AND_GPU_SETUP.md](VENV_AND_GPU_SETUP.md) | Venv, GPU |
| [OLLAMA_SETUP.md](OLLAMA_SETUP.md) | Ollama |
| [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) | NAS rollback, storage |
| [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) | SSH keys for monitoring remote devices (Widow, NAS, Pi) |

## Planning & architecture

| Doc | Purpose |
|-----|---------|
| [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md) | Controller design |
| [DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md](DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md) | **Full roadmap** — orchestrators, governors, collection/processing/routing, API stack, data flow, config, startup order |
| [DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md](DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md) | **Pipeline enhancements** — feedback loops, cross-domain synthesis, source quality, real-time, relationships, predictive, enrichment, dedupe, intelligence products, anomaly detection; proposed routes, schema, integration, priority |
| [EDITORIAL_UPGRADE_BUILD_PLAN.md](EDITORIAL_UPGRADE_BUILD_PLAN.md) | **Editorial upgrade build plan** — phased implementation: Phase 1 Report surface, 2 Smarter + docs schema, 3 Editorial foundation, 4 Editorial full, 5 Persistent documents + display; checklists and dependencies |
| [NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md](NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md) | **Today's Report** — pull pipelines into one reader-facing product; phases A–D; link to editorial layer |
| [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md) | **Editorial intelligence** — newsworthiness, narrative arc, reader engagement, perspectives, context, impact, time-based layout; APIs, schema, automation phases, governor integration |
| [PERSISTENT_EDITORIAL_DOCUMENTS.md](PERSISTENT_EDITORIAL_DOCUMENTS.md) | **Living documents** — write once, refine forever; storyline/investigation/event canonical docs, section-level refinement, triggers, schema, API, refinement log |
| [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) | **Production batch timings** — context sync, claim extraction, event tracking, story enhancement, entity enrichment; queue limits, backpressure, cost controls |
| [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) | Path to orchestrator-controlled, initiative-taking app with user guidance |
| [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) | **Context-centric model** — contexts, entity mapping, living profiles, claims, patterns; aligns with coding style and v6 entity work |
| [CONTEXTS_BY_DOMAIN.md](CONTEXTS_BY_DOMAIN.md) | **Contexts by domain** — why politics vs finance use the same pipeline; no finance contexts = no finance feeds/articles; how to add feeds and sync |
| [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | v6 quality-first upgrades (entity dossiers, event tracking, documents, narrative) — adapted to coding style |
| [V6_QUALITY_FIRST_TODO.md](V6_QUALITY_FIRST_TODO.md) | Prioritized to-do list for v6 quality-first work |

## Domains & features

| Doc | Purpose |
|-----|---------|
| [WEB_PRODUCT_DISPLAY_PLAN.md](WEB_PRODUCT_DISPLAY_PLAN.md) | **Intelligence dashboard** — audience, landing dashboard (hero + 3 columns), nav (Discover/Investigate/Monitor/Analyze), entity/context templates, user flows, implementation phases; aligned with React/Vite/MUI and existing Intelligence pages |
| [EDITORIAL_DISPLAY_STRATEGY.md](EDITORIAL_DISPLAY_STRATEGY.md) | **Report & intelligence UI** — hierarchy of attention, progressive disclosure (Glance/Scan/Read/Dive), visual grammar by type, time-based layout, mobile-first, trust signals, ambient awareness |
| [WEB_UI_FEATURE_COVERAGE.md](WEB_UI_FEATURE_COVERAGE.md) | **UI vs backend coverage** — what’s routed and in nav vs not; full Monitoring page not used; articles, storylines, topics, RSS, watchlist, finance sub-pages missing; recommendations to expose all features |
| [DOMAIN_1_NEWS_AGGREGATION.md](DOMAIN_1_NEWS_AGGREGATION.md) through [DOMAIN_6_SYSTEM_MONITORING.md](DOMAIN_6_SYSTEM_MONITORING.md) | Domain reference |
| [RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md](RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md) | **RAG system** — current implementation, rationale, and improvements (story details, continual pull, historical context) |
| [RAG_ENHANCEMENT_ROADMAP.md](RAG_ENHANCEMENT_ROADMAP.md) | **RAG roadmap** — iterative story enhancement, entity profiles, watch patterns, phased implementation (8 weeks) |
| [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md) | **Vector schema** — versioned facts, entity relationships, story states; pgvector/ChromaDB, temporal queries, 768d |
| [STORAGE_ESTIMATES_AND_OPTIMIZATION.md](STORAGE_ESTIMATES_AND_OPTIMIZATION.md) | **Storage planning** — growth estimates for versioned facts/entities/vectors; optimization (compression, dedup, tiering, retention); runnable analysis query |
| [OPTIMIZATION_STRATEGIES_ASSESSMENT.md](OPTIMIZATION_STRATEGIES_ASSESSMENT.md) | **What’s implemented vs gaps** — retention/cleanup/caps today; recommended limits to stay under ~1 TB; new intelligence retention (fact_log, queue, pattern_matches, storyline_states) |
| [STORY_STATE_UPDATE_TRIGGERS.md](STORY_STATE_UPDATE_TRIGGERS.md) | **Story state triggers** — fact_change_log, story_update_queue, trigger on versioned_facts; process log → enqueue → refresh |
| [FINANCE_PIPELINE.md](FINANCE_PIPELINE.md), [FINANCE_TODO.md](FINANCE_TODO.md) | Finance domain |
| [LOGGING_SYSTEM_SUMMARY.md](LOGGING_SYSTEM_SUMMARY.md) | Logging |
| [FRONTEND_DEBUGGING_GUIDE.md](FRONTEND_DEBUGGING_GUIDE.md) | Frontend debug |

## Repo and context hygiene

| Doc | Purpose |
|-----|---------|
| [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) | **Git and Cursor** — what’s ignored, commit in small chunks, optional disk cleanup |

## Archived

