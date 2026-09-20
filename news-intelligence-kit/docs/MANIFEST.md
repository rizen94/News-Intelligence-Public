# News Intelligence Kit — file manifest

Greenfield package under `news-intelligence-kit/`. Full NI API is **vendored at export time** via `scripts/export_kit.sh` from the parent repo (not edited in place).

## Keep (Standard tier)

### API (`api/` after export)

| Area | Paths |
|------|-------|
| Entry | `main.py`, `main_kit.py` (kit overlay) |
| Config | `config/`, `config/runtime.py`, `config/settings.py`, `config/paths.py`, `config/domains/specs/_template.domain.json` |
| Shared | `shared/database/`, `shared/domain_registry.py`, `shared/domain_spec.py`, `shared/pipeline_pass_marker.py`, `shared/services/llm_service.py`, `shared/services/ollama_model_caller.py` |
| Collectors | `collectors/`, `services/rss/`, `services/collect_rss_feeds.py` |
| Automation | `services/automation_manager.py`, `services/backlog_metrics.py`, `services/pipeline_schedule_service.py`, `services/monitor_backlog_snapshot_service.py` |
| Domains | `domains/news_aggregation/`, `domains/content_analysis/` (core), `domains/storyline_management/`, `domains/intelligence_hub/` (no finance synthesis), `domains/system_monitoring/` |
| Provision | `scripts/provision_domain.py`, `scripts/init_domain_spec.py`, `shared/services/domain_rss_seed.py` |
| Kit-only | `kit_api/` (setup, vault, agent, kit_status) |

### Web (`web/` after export)

| Page | Path |
|------|------|
| Dashboard | `pages/Dashboard/` |
| Monitor | `pages/Monitor/MonitorPage.tsx` |
| Articles | `pages/Articles/` |
| Storylines | `pages/Storylines/` |
| RSS | `pages/RSSFeeds/` |
| Events | `pages/Events/` |
| Investigate entities/events | `pages/Investigate/EntitiesListPage.tsx`, `EntityDetailPage.tsx`, `EventDetailPage.tsx`, `SearchPage.tsx` |
| Shell | `layout/MainLayout.tsx`, `App.tsx` (trimmed routes) |

### Setup SPA (`setup/`)

| Component | Purpose |
|-----------|---------|
| `setup/src/` | 7-step wizard |
| Served at `/setup` via nginx |

## Exclude from kit export

- `api/domains/finance/` (Chroma, FRED, market DB)
- `api/domains/politics/routes/official.py` (Congress.gov)
- `api/nri_core/` (optional; kit uses simplified `investigation_loop_service`)
- `web/src/pages/Finance/`, `Arcs/`, `Hypotheses/`, `Briefings/`, `Audit/`, `SqlExplorer`
- Pre-seeded `config/domains/politics.yaml`, `finance.yaml`, etc. → `_examples/` only
- `_archive/`, `scripts/ni_review/`, `.continue/`, `.cursor/`
- Multi-host: `OLLAMA_POP_OS_HOST` defaults removed in `.env.template`

## Migrations (kit)

| File | Role |
|------|------|
| `migrations/001_baseline.sql` | public + intelligence + template_silo + helper functions |
| `migrations/002_kit_schema_version.sql` | `automation_state.kit_schema_version` |

Domain silos created at runtime via `kit_provision_domain()` — not numbered per-domain migrations.
