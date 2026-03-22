# Scripts Index

## Essential

| Script | Purpose |
|--------|---------|
| `../start_system.sh` | Start all services (manual) |
| `../start-news-intelligence.sh` | Same as above; symlink from `~/bin` to run from anywhere (see script header) |
| `../stop_system.sh` | Stop API and frontend |
| `../restart_system.sh` | Stop then start (e.g. after changing .env) |
| `../status_system.sh` | Check service status |
| `archive_logs_to_nas.sh` | Copy old log files to NAS and trim local (run on Widow; keep disk clean) |
| `export_cold_data_to_nas.sh` | Export old articles/contexts to NAS (optional prune); see docs/NAS_LEGACY_AND_STORAGE.md |
| `setup_autostart.sh` | Enable auto-start on boot (systemd user services) |
| `setup_nas_ssh_tunnel.sh` | SSH tunnel to NAS (rollback only) |
| `restart_api_with_db.sh` | Restart API |
| `db_backup.sh` | DB backup (run on Widow) |

## Widow / secondary

| Script | Purpose |
|--------|---------|
| `setup_widow_ssh.sh` | SSH config for Widow |
| `deploy_to_widow.sh` | Deploy code to Widow |
| `setup_widow_app.sh` | Setup on Widow (venv, systemd) |
| `run_secondary_worker.py` | RSS daemon (Widow) |
| `configure_widow_no_sleep.sh` | Keep server on full time (no suspend/hibernate/power-saver) — run on server |
| `run_widow_updates.sh` | apt update on Widow |
| `ddns_update_duckdns.sh` | DuckDNS DDNS **fallback** when router has no DDNS; cron on Widow; `configs/ddns.env` — [docs/DYNAMIC_DNS_WIDOW.md](../docs/DYNAMIC_DNS_WIDOW.md) (prefer router for entry + DDNS) |
| `widow_setup_public_nginx.sh` | **Widow:** install nginx — HTTP→HTTPS, ACME path, self-signed 443 until certbot; `PUBLIC_DEMO_HOSTNAME` / `PUBLIC_API_UPSTREAM` — [docs/DYNAMIC_DNS_WIDOW.md](../docs/DYNAMIC_DNS_WIDOW.md) §6 |
| `deploy_public_demo_to_widow.sh` | **`npm run build:bundle`** + rsync `web/dist` → Widow `/var/www/news-intelligence/web/dist` |
| `widow_disable_public_api.sh` | **Widow (sudo):** disable `news-intelligence-api-public` — API stays on main GPU host; nginx uses `PUBLIC_API_UPSTREAM` |
| `decommission_nas_postgresql.sh` | **One-time / rare:** NAS PostgreSQL decommission (see script header); rollback notes in [docs/NAS_LEGACY_AND_STORAGE.md](../docs/NAS_LEGACY_AND_STORAGE.md) |
| `../api/scripts/run_widow_db_adjacent.py` | **Widow cron:** RSS / context_sync / entity_profile_sync / pending_db_flush without API — [docs/WIDOW_DB_ADJACENT_CRON.md](../docs/WIDOW_DB_ADJACENT_CRON.md) |
| `run_backfill_on_widow.sh` | Run entity description backfill on Widow (DB local). `./scripts/run_backfill_on_widow.sh [--deploy] [--limit N]` — sources .env on remote so DB_HOST=127.0.0.1. |

## Wikipedia / entity descriptions

| Script | Purpose |
|--------|---------|
| `backfill_entity_descriptions.py` | Backfill `entity_canonical.description` from local `intelligence.wikipedia_knowledge` or, with `--api-fallback`, from the Wikipedia API. Run on Widow via `./scripts/run_backfill_on_widow.sh` or locally: `PYTHONPATH=api uv run python scripts/backfill_entity_descriptions.py --api-fallback [--limit N]`. |
| `load_wikipedia_dump.py` | Load abstract dump into `intelligence.wikipedia_knowledge`. Default URL may 404 (abstract dumps discontinued); use `--file /path/to/dump.xml.gz` if you have one. See script docstring for alternates (API fallback, Cirrus/full dumps). |
| `run_entity_consolidation.py` | **Entity consolidation:** merge duplicate canonicals (e.g. Donald Trump, Trump, King Trump → one entity with aliases). Populates aliases from mentions, then auto-merges by confidence. Run: `PYTHONPATH=api uv run python scripts/run_entity_consolidation.py [--domain politics] [--confidence 0.6] [--dry-run]`. Use `--decouple` to only split role-word merges (e.g. X executives / Y executives). |
| `run_consolidation_on_widow.sh` | Run entity consolidation on Widow (DB local). `./scripts/run_consolidation_on_widow.sh [--dry-run] [--confidence 0.6]`. Run before wiki backfill so consolidated entities get descriptions. |
| `run_decouple_role_merges.py` | **Entity decouple pipeline:** split bad merges (role-word and future steps). Runs automatically in data_cleanup when `entity_bad_merge_decouple` is True. Manual: `PYTHONPATH=api uv run python scripts/run_decouple_role_merges.py [--domain DOMAIN] [--dry-run] [--max-splits N]`. |
| `run_decouple_on_widow.sh` | Run decouple on Widow. `./scripts/run_decouple_on_widow.sh [--domain DOMAIN]`. |
| `run_consolidation_and_decouple_on_widow.sh` | Run consolidation then decouple on Widow in one SSH session. `./scripts/run_consolidation_and_decouple_on_widow.sh [--dry-run] [--confidence 0.6]`. |

## Migrations (API)

| Script | Purpose |
|--------|---------|
| `api/scripts/run_migrations_140_to_152.py` | Run migrations 140–154 (orchestration, intelligence, context-centric, watch patterns). From repo root: `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_140_to_152.py` |
| `api/scripts/run_migrations_155_to_160.py` | Run migrations 155–161 (quality feedback, cross-domain, anomaly, claim merges, editorial docs, commodity feeds, processed_documents, automation_run_history). From repo root: `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_155_to_160.py` |
| `api/scripts/run_migration_173.py` | Migration **173**: expand **science_tech** RSS (universities, journals, agencies). `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_173.py` |
| `api/scripts/run_migration_174.py` | Migration **174**: `intelligence.context_grouping_feedback` (human audit: context ↔ topic/storyline/pattern). `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_174.py` |
| `api/scripts/run_migration_176.py` | Migration **176**: `public.applied_migrations` ledger. `PYTHONPATH=api uv run python api/scripts/run_migration_176.py` |
| `api/scripts/run_migration_177.py` | Migration **177**: `{domain}.articles.timeline_processed` + ensure `article_entities` / `entity_canonical` per active domain. `PYTHONPATH=api uv run python api/scripts/run_migration_177.py` |
| `api/scripts/run_migration_178.py` | Migration **178**: `{domain}.articles.timeline_events_generated` (required for event_extraction UPDATE). `PYTHONPATH=api uv run python api/scripts/run_migration_178.py` |
| `api/scripts/register_applied_migration.py` | Record an applied migration in the ledger: `PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 176 --env dev --notes "..." [--file path.sql]` |
| `api/scripts/migration_ledger_report.py` | Compare `public.applied_migrations` to SQL on disk (active + archive): `PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py` (`--json`, `--active-only` for 176+ gaps only) |
| `api/scripts/refresh_ollama_models.py` | **`ollama pull`** for each model in `settings.ollama_pull_model_names()` (refresh weights for same tags). `PYTHONPATH=api uv run python api/scripts/refresh_ollama_models.py` — see `docs/SETUP_ENV_AND_RUNTIME.md`. |
| `api/scripts/reset_pdf_parser_failed_documents.py` | After installing **pdfplumber** + **pdfminer.six** (`uv pip install -r api/requirements.txt` or `.venv/bin/python -m pip install -r api/requirements.txt` — not system pip on PEP 668), clear `permanent_failure` on matching rows. Loads repo-root `.env` for `DB_*`. `PYTHONPATH=api uv run python api/scripts/reset_pdf_parser_failed_documents.py` (`--dry-run` to list only). |

## Utilities

| Script | Purpose |
|--------|---------|
| `full_system_status_check.py` | **Full status:** resource usage (CPU, RAM, disk, GPU) + data quality (articles, phases, storylines, contexts). Run: `uv run python scripts/full_system_status_check.py` |
| `automation_run_analysis.py` | **Automation run analysis:** last N hours from `automation_run_history` — run counts per phase, actual vs estimated duration, phases not run in 2h. Run: `PYTHONPATH=api uv run python scripts/automation_run_analysis.py --hours 3 --window-2h`. Use to tune schedule intervals and `PHASE_ESTIMATED_DURATION_SECONDS`. |
| `run_daily_analytics_rollup.py` | **Daily analytics rollup:** populates `automation_run_history_daily` + `log_archive_daily_rollup` for weekly/monthly analytics from summarized daily data. Run: `PYTHONPATH=api uv run python scripts/run_daily_analytics_rollup.py` (defaults to yesterday UTC). |
| `backlog_eta.py` | **Backlog ETA:** estimate time to clear article enrichment, document processing, and storyline synthesis backlogs. Run: `uv run python scripts/backlog_eta.py` |
| `check_data_collection_health.py` | Data quality: articles, selected automation phases (e.g. `collection_cycle`, `document_processing`), documents, storylines, contexts. Run: `uv run python scripts/check_data_collection_health.py` |
| `db_full_inventory.py` | **DB inventory:** row counts + empty tables per schema + critical table presence. `PYTHONPATH=api uv run python scripts/db_full_inventory.py` (`--json`) |
| `db_persistence_gates.py` | **Persistence gates:** critical tables + recent `automation_run_history`. `PYTHONPATH=api uv run python scripts/db_persistence_gates.py [--require-automation]` |
| `db_maintenance_analyze.py` | **Planner stats:** `ANALYZE` on hot tables; optional `--vacuum` in maintenance window. `PYTHONPATH=api uv run python scripts/db_maintenance_analyze.py` |
| `poll_extracted_events_and_pipeline.py` | **Extracted events + pipeline trace:** `chronological_events` counts per domain, article gates for `event_extraction`, `article_entities` footprint, `automation_run_history` (48h). Run: `PYTHONPATH=api uv run python scripts/poll_extracted_events_and_pipeline.py` — see [docs/_archive/retired_root_docs_2026_03/EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md](../docs/_archive/retired_root_docs_2026_03/EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md) |
| `run_event_pipeline_manual.py` | **Manual event extraction + dedup:** runs LLM extraction for N eligible articles, writes `public.chronological_events`, updates article flags; optional dedup. `PYTHONPATH=api uv run python scripts/run_event_pipeline_manual.py [--domain politics] [--limit 1] [--dry-run]` |
| `verify_pipeline_db_alignment.py` | **Pipeline ↔ DB audit:** required tables/columns vs collection, enrichment, entities, events, contexts, documents, automation; writes optional `docs/generated/PIPELINE_DB_ALIGNMENT_REPORT.md`. `PYTHONPATH=api uv run python scripts/verify_pipeline_db_alignment.py [--write-report docs/generated/PIPELINE_DB_ALIGNMENT_REPORT.md]` |
| `verify_storyline_event_entity_chains.py` | **Storylines ↔ events ↔ entities:** domain `storylines` / `story_entity_index`, events linked via `chronological_events.storyline_id`, multi-event chains, article–entity overlap. See [docs/_archive/retired_root_docs_2026_03/STORYLINE_EVENT_ENTITY_CHAINS.md](../docs/_archive/retired_root_docs_2026_03/STORYLINE_EVENT_ENTITY_CHAINS.md). `PYTHONPATH=api uv run python scripts/verify_storyline_event_entity_chains.py [--write-report docs/generated/STORYLINE_EVENT_ENTITY_CHAINS_REPORT.md]` |
| `verify_intelligence_phases_productivity.py` | **Intelligence phases productivity:** cross-domain synthesis, entity enrichment, claims_to_facts, pattern recognition, event coherence review, pattern matching. Checks automation_run_history + output tables. `PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py [--write-report docs/generated/INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md] [--hours 48]` |
| `diagnose_claims_to_facts.py` | **Quick diagnostic for claims_to_facts:** extracted_claims counts, unpromoted high-confidence claims, entity resolution match rate. `PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py` |
| `enable_all_storyline_automation.py` | **Bulk-enable storyline automation** on all domain `storylines` (`automation_enabled`, `automation_mode`, suggestions queue / `auto_approve`, optional `last_automation_run` reset). `PYTHONPATH=api uv run python scripts/enable_all_storyline_automation.py [--dry-run] [--mode review_queue\|suggest_only\|auto_approve]` |
| `verify_gpu.py` | GPU/ML verification |
| `verify_connections.py` | DB, Ollama, Redis check |
| `rss_collection_with_health_check.sh` | RSS + health check (used by cron) |
| `run_last_24h_report.sh` | Run last-24h activity report (uses .venv-report) |
| `setup_rss_cron_with_health_check.sh` | Install RSS cron (6/18) with quoted paths |
| `setup_morning_data_pipeline.sh` | Install morning pipeline cron (4/5/6 AM) with quoted paths |
| `setup_log_archive_cron.sh` | Install log-archive-to-NAS cron (6/18) with quoted paths |
| `setup_log_cleanup_cron.sh` | Install pipeline_trace.log cleanup (2 AM) with quoted path |
| `backup_database.sh` | DB backup |
| `doc_obfuscation.py` | **Public-repo docs:** expand/scrub LAN placeholders — [docs/OBFUSCATION.md](../docs/OBFUSCATION.md) |
| `commit_context_centric.sh` | **Interactive chunk commits** for large changes — [docs/REPO_MAINTENANCE.md](../docs/REPO_MAINTENANCE.md) |
| `last_24h_activity_report.py` | Activity report (usually via `run_last_24h_report.sh`) |

## Archived

`scripts/archive/` — legacy NAS scripts, one-time migrations, deprecated.

### `archive/retired_scripts_2026_03/` (one-off / not invoked by the API)

Diagnostics, Pi helpers, old migration shells, dev benchmarks, manual CSV import/export, duplicate cron installer, and superseded `maintenance/` + `production/` helpers. Catalog: [archive/retired_scripts_2026_03/README.md](archive/retired_scripts_2026_03/README.md).

**2026-03 housekeeping** (see [docs/archive/CLEANUP_2026_03.md](../docs/archive/CLEANUP_2026_03.md)):

| Was | Now |
|-----|-----|
| `development/scripts/*` | `docs/archive/development_ai_session_tooling/development/scripts/` |
| Root `monitoring/` | `docs/archive/observability_stack_unused/monitoring/` |
| Root `analysis/` | `docs/archive/root_analysis_snapshots/analysis/` |
| `docker-compose.yml` etc. | `docs/archive/docker_stack/` |

Service archives (handled via git history):
- `api/services/article_service.py` (legacy global-table SQL, unused)
- `api/services/dashboard_service.py` (legacy global-table SQL, unused)
- `api/services/progressive_enhancement_service.py` (legacy global-table SQL, unused)
- `api/services/storyline_service.py` (legacy global `storylines` SQL; use `domains/storyline_management/services/storyline_service.py`)
- `api/services/multi_perspective_storyline_service.py` (unused v3 multi-perspective layer)
- `api/collectors/rss_collector_tracking.py` (unused; no runtime imports)
- `api/modules/ml/ml_rag_service.py` (unused; `MLRAGService` had no consumers)
