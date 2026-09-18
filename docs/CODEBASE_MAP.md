# Codebase map (where things live)

**Audience:** Developers and reviewers cloning the repo. Use this with [CODE_REVIEW_AND_RUN_CAVEATS.md](CODE_REVIEW_AND_RUN_CAVEATS.md), [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md), and [AGENTS.md](../AGENTS.md).

---

## Start here (reading order)

1. **[README.md](../README.md)** — product summary, reviewer section, doc links.
2. **[AGENTS.md](../AGENTS.md)** — terminology (`storylines`, `domains`, `/api/...`), entry points.
3. **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** — routes, services, and data flow; stakeholder-style overview (archived): [_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md](_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md).
4. **[DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md)** — intelligence cascade (article → contexts → claims → storylines → editorial).
5. **[SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)** — API routes and web areas (long but authoritative).
6. **[PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md)** — automation phases and dependencies (follow-along with code).

---

## Repository layout

| Path | Role |
|------|------|
| [`api/main.py`](../api/main.py) | FastAPI app: lifespan, middleware, mounts all domain routers. |
| [`api/domains/`](../api/domains/) | **Domain-driven** packages: each has `routes/` (HTTP) and often `services/`. |
| [`api/services/`](../api/services/) | Cross-cutting services: **AutomationManager**, collectors, orchestration helpers. |
| [`api/shared/`](../api/shared/) | DB pool, LLM helpers, pipeline runners, intake backlog SQL, fast NER, context chunking. |
| [`api/config/`](../api/config/) | Settings, paths, orchestrator YAML, domain onboarding YAML. |
| [`api/database/migrations/`](../api/database/migrations/) | Active SQL migrations; older files under `archive/historical/`. |
| [`web/src/`](../web/src/) | React SPA: `App.tsx`, `layout/`, `pages/`, `services/api/`. |
| [`scripts/`](../scripts/) | Shell/Python ops; index in [SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md). |
| [`configs/`](../configs/) | `env.example` and deployment-related samples. |

---

## High-interest backend files

| Topic | File(s) | Notes |
|-------|---------|--------|
| HTTP entry | `api/main.py` | Router include order; `lifespan` starts background automation. |
| Database | `api/shared/database/connection.py` | **Only** supported way to connect (pools + `get_db_config`). |
| Background pipeline | `api/services/automation_manager.py` | v8 **collection_cycle** + scheduled phases; large file — use [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) first. |
| RSS / ingestion | `api/collectors/`, `api/services/rss/` | Feed fetch, article writes per domain schema. |
| Context bridge | `api/services/context_processor_service.py` | Domain articles → `intelligence.contexts`. |
| **Unified intake** | `api/services/unified_intake_extraction_service.py`, `api/shared/unified_intake_extraction_runner.py`, `api/shared/unified_intake_backlog.py` | Batched LLM intake (default prod path); legacy-aware backlog + backfill. |
| Fast NER / chunking | `api/shared/fast_ner_lane.py`, `api/shared/context_chunking.py` | spaCy + GLiNER pre-pass; semantic multi-chunk contexts. |
| Dual-lane GPU routing | `api/shared/bulk_catchup_llm_routing.py`, `api/shared/automation_llm_routing.py` | PopOS GPU + Widow CPU extraction lanes (`AUTOMATION_DUAL_LANE=true`). |
| Storylines API | `api/domains/storyline_management/routes/` | Aggregated in `routes/__init__.py` (pattern for other domains). |
| Intelligence API | `api/domains/intelligence_hub/routes/`, `context_centric` | Cross-domain entities, events, synthesis. |
| Finance | `api/domains/finance/` | Orchestrator-backed market/evidence flows + SQLite/Chroma under `data/finance/`. |
| Monitoring | `api/domains/system_monitoring/routes/` | Health, metrics, orchestrator visibility. |

---

## High-interest frontend files

| Topic | File(s) | Notes |
|-------|---------|--------|
| Routes | `web/src/App.tsx` | `BrowserRouter`; `/:domain/*` shell. |
| Layout | `web/src/layout/MainLayout.tsx` | Domain switcher, sidebar, outlet. |
| API base URL | `web/src/services/apiConnectionManager.ts` | Injects domain for scoped calls. |
| Domain keys | `web/src/utils/domainHelper.ts` | Fallback / typing; runtime list from **`registry_domains`** at SPA startup. |
| API modules | `web/src/services/api/*.ts` | One module per resource area (articles, storylines, monitoring, …). |

---

## Domain packages (`api/domains/*`)

Each domain typically mirrors this idea:

- `routes/` — FastAPI routers (mounted under `/api/...` — see each router’s `prefix`).
- `services/` — business logic used by routes or automation.

Shared cross-domain schema lives in PostgreSQL **`intelligence`**; per-domain content in **`legal`**, **`medicine`**, **`artificial_intelligence`**, **`politics`**, **`finance`** (see `public.domains`). **`science_tech` retired** (migration 212).

---

## Config and governance

| File | Purpose |
|------|---------|
| `api/config/orchestrator_governance.yaml` | Collection interval, analysis pipeline budgets, feature flags consumed by automation. |
| `api/config/sources.yaml` | External source hints (finance, etc.). |
| `api/config/domains/*.yaml` | YAML onboarding for additional silos — full parity with built-ins once provisioned (see [DOMAIN_EXTENSION_TEMPLATE.md](DOMAIN_EXTENSION_TEMPLATE.md)). |
| `api/scripts/provision_domain.py` | New silo: preflight, SQL, optional **`seed_feed_urls`** → `{schema}.rss_feeds`. |
| `api/scripts/seed_domain_rss_from_yaml.py` | Backfill **`rss_feeds`** from YAML **`seed_feed_urls`**. |
| `api/scripts/init_domain_yaml_from_template.py` | Create **`{domain_key}.yaml`** from **`_template.example.yaml`**. |
| `api/scripts/backfill_unified_intake_pass_from_legacy.py` | Marker-only unified pass backfill for legacy-complete articles (no LLM). |
| `api/scripts/diagnose_unified_intake_backlog_detail.py` | Actionable vs inventory unified backlog breakdown. |
| `scripts/run_remaining_catchup_popos.sh` | Off-hours GPU catch-up on PopOS (unified burn-down + profile/story phases). |

---

## Tests and scripts

- **`tests/`** (repo root) — **CI pytest** target.
- **`scripts/`** — Operational scripts; **`api/scripts/`** — migrations, registers, verifiers.

See [DOCS_INDEX.md](DOCS_INDEX.md) for the full documentation set.
