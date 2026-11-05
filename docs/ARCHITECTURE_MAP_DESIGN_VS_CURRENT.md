# Architecture Map: Design Intent vs Current Pathing

**Purpose:** Compare the designed architecture (what it should be) against current pathing (what it actually is). This serves as a debugging reference when implementing repairs.

---

## 1. End-to-End Data Flow

### Design Intent (from PIPELINE_AND_AUTOMATION.md, PIPELINE_OPERATIONS_WIDOW.md)

```
TIER 0 — INGEST (Widow)
├── RSS feeds: newsplatform-secondary.service → collect_rss_feeds → {domain}.articles
│   Schedule: every 10 min; quiet window weekday daytime
├── Widow cron */15: context_sync*, entity_profile_sync*, pending_db_flush
├── AutomationManager.collection_cycle → enrichment + docs + queue drain
└── AutomationManager.content_enrichment → Trafilatura full-text (every 5min)

TIER 1 — FOUNDATION (AutomationManager on Widow API)
├── context_sync: articles → intelligence.contexts
├── entity_profile_sync: canonical entity maps
├── metadata_enrichment, ml_processing, entity_extraction
├── entity_profile_build, embeddings_worker

TIER 2 — EXTRACTION & EVENTS
├── claim_extraction → claims_to_facts → extracted_claims_dedupe
├── event_tracking → event_coherence_review → investigation_report_refresh
├── event_extraction → event_deduplication → story_continuation
└── legislative_references, cross_domain_synthesis, pattern_recognition

TIER 3 — STORYLINES & INTELLIGENCE PRODUCTS
├── storyline_discovery → storyline_processing → storyline_automation
├── storyline_enrichment → content_refinement_queue → narrative finisher (5090)
├── storyline_synthesis, story_enhancement, timeline_generation
└── editorial_*, daily_briefing_synthesis, digest_generation, watchlist_alerts

TIER 4 — MAINTENANCE & NIGHTLY
└── nightly_enrichment_context (02:00–07:00 EST unified drain)
    cache_cleanup, data_cleanup, health_check, longitudinal_matview_refresh
```

### Current Reality (from automation_manager.py schedules)

| Scheduled Task | Interval | Phase | Depends On | Notes |
|---------------|----------|-------|------------|-------|
| **collection_cycle** | config/env-based | 0 | — | Main RSS intake cycle. Contains enrichment + docs + queue drain as sub-steps |
| **nightly_enrichment_context** | 60s (but window-limited) | 0 | — | 02:00–07:00 EST; unified drain of RSS→enrichment→context_sync |
| **document_processing** | 10 min | 0 | — | PDF fetch + extract sections/entities |
| **research_paper_profiling** | 10 min | 1 | — | Scientific papers (no enrichment dep to avoid settling) |
| **claim_evidence_appraisal** | 15 min | 1 | — | Lit → claims → knowledge_profiles / ledger |
| **content_enrichment** | 5min when idle; faster when pending>0 | 0 | — | Trafilatura full-text for RSS-short articles |

**Key divergence from design:**
- `context_sync`, `entity_profile_sync`, `pending_db_flush` run via **Widow cron** (`run_widow_db_adjacent.py`) and are **disabled in AutomationManager** to avoid duplicates. Design docs show them as tier 1 phases; current path has them off-host.
- No explicit phase execution for Tiers 2–3 as standalone schedules — they're invoked via `request_phase()` (user/governor-triggered) or inside `collection_cycle`. The scheduled tasks map differently: `claim_evidence_appraisal` covers some Tier 2 work, `research_paper_profiling` covers papers, but other extraction TIER tasks are not independently scheduled.

## 2. Database Architecture

### Design Intent

| Aspect | Value |
|--------|-------|
| Host | Widow `192.168.93.101`, port `5432` |
| Database | `news_intel` |
| User | `newsapp` |
| Schema layout | Per-domain: `{politics,finance,science_tech,*silo}` + global `public`,`intelligence`,`pipeline` |
| Tables | See DATABASE.md — 250+ migrations (latest: 253) |
| Connection pools | 4 pools: UI (12s wait), Worker (30s), Health (2s), SA (SQLAlchemy) |

### Current Reality

- **Migrations**: 253 total. Latest are `253_quality_score_provenance.sql` and `252_ml_processing_retry_count.sql`
- **Domains live**: politics, finance, artificial-intelligence, legal, medicine, neurodiversity, environment-climate
- **Per-domain provisioned silos** from YAML specs in `api/config/domains/` (8 configs) + JSON domain specs in `api/config/domains/specs/`
- **Pools**: All four defined in `connection.py`; widow writes to `{domain}.articles` exclusively (no message queue)
- **DB pool pressure gating** is enabled: defers new schedules when worker pool utilization ≥ threshold

## 3. API Routing

### Design Intent

| Product Root | Prefix | Code Location |
|-------------|--------|--------------|
| News (default) | `/`, `/news`, `/current`, `/research` | `web/src/v2/` |
| Finance | `/finance/…` | `web/src/finance/` |
| Admin | `/admin/…` | `web/src/v2/pages/admin/` |

| API Area | Routes |
|----------|--------|
| Domain routes | `/api/{domain}/...` — RSS, storylines, content analysis |
| Reader (broadsheet) | `/api/reader/home?domain=`, `/api/reader/storylines/{id}?domain=` |
| Orchestrator | `/api/orchestrator/status`, `/api/orchestrator/metrics` |
| System monitoring | `/api/system_monitoring/pipeline_status`, etc. |

### Current Reality (from domain routes `__init__.py` files)

| Domain/Module | Router Prefix | Tags |
|--------------|---------------|------|
| Content Analysis | `""` (mounted under `/api`) | "Content Analysis" |
| Intelligence Hub | `""` (mounted under `/api`) | "Intelligence Hub" |
| News Aggregation | `""` (mounted under `/api`) | "News Aggregation" |
| Reader | `/api/reader` | "Reader" |
| Storyline Management | `/api` | "Storyline Management" |
| System Monitoring | `""` (mounted under `/api`) | "System Monitoring" |

**Key divergence:** Most domain routes mount under `prefix="/api"` (not scoped per-domain). The `{domain}` path parameter is used within route functions but the router prefix is flat. No explicit domain-scoped router mounting — domain context flows through function parameters and config, not URL structure.

## 4. Automation / Scheduling Architecture

### Design Intent (orchestrator_governance.yaml)

```yaml
orchestrator:
  loop_interval_seconds: 60
  cycle_phases: [assessment, prioritization, deep_processing, quality_review, synthesis]
  
quality_thresholds:
  min_quality_score: 0.5
  min_importance_for_processing: 0.55

signal_first:
  article_signal_enabled: true
  article_signal_full_min_quality: 0.55
```

### Current Reality (AutomationManager in `api/services/automation_manager.py`)

**7 scheduled tasks** (not 5 as the orchestrator config suggests):
- The orchestrator cycle_phases are defined but phase execution is handled by AutomationManager which maps task names to `_execute_*` methods.

**Active backpressure mechanisms:**
1. `AUTOMATION_QUEUE_SOFT_CAP` — combined queue depth cap
2. `AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE` — per-phase stack prevention
3. `AUTOMATION_DB_POOL_PRESSURE_GATE_ENABLED` — defers when DB pool pressure ≥ 0.82
4. `AUTOMATION_PER_PHASE_CONCURRENT_CAP` — max concurrent workers per phase (default 2)
5. `AUTOMATION_NIGHTLY_ENRICHMENT_MAX_QUEUED` — nightly task cap (default 1)


## 5. Domain Configuration & Silos

### Design Intent

| Domain Key | YAML Spec | JSON Schema | Postgres Schema |
|-----------|-----------|------------|-----------------|
| politics | `politics.yaml` | `politics.domain.json` | `politics` |
| finance | `finance.yaml` | `finance.domain.json` | `finance` |
| artificial-intelligence | `artificial-intelligence.yaml` | `artificial-intelligence.domain.json` | provisioned |
| legal | `legal.yaml` | `legal.domain.json` | provisioned |
| medicine | `medicine.yaml` | `medicine.domain.json` | provisioned |
| neurodiversity | `neurodiversity.yaml` | `neurodiversity.domain.json` | provisioned |
| environment-climate | — | `environment-climate.domain.json` | provisioned |

### Current Reality

- Domain configs in `api/config/domains/*.yaml` (7 files + template)
- JSON domain specs in `api/config/domains/specs/` (9 files including template/schema)
- Migration 219 handled politics/finance schema rename from `*_2` to canonical names
- Migration 227 dropped politics_2/finance_2 stubs
- **Gap**: No environment-climate YAML config — only JSON spec exists

## 6. Frontend Architecture

### Design Intent

Three product roots with switcher in `web/src/shell/ProductRootSwitcher.tsx`:
- News (default): broadsheet UI, domain filter via `?domain=`
- Finance: trackers/markets/reporting
- Admin: Monitor/Work/SQL/Audit/Grafana

### Current Reality (`web/src/` directory)

```
broad-sheet/         ← News default product root
├── pages/           ← Home, News, Research, OneOffs, Situations, Current, StorylineReader, EntityDossier, Hub, admin
├── components/      ← 37+ component directories
├── hooks/layouts/services/styles/

shell/               ← ProductRootSwitcher
components/          ← shared components (EntityCard, Thread, Charts, etc.)
hooks/

finance/             ← EXISTS (separate product root)
admin/               ← under broad-sheet/pages/admin/
```

## 7. Knowledge Graph Integration

### Current State

- Palace wing `projects` / room `news_intelligence` stores NI memories as cross-reference
- AAAK dialect used for compressed entity codes
- Tunnels connect related domains (e.g., API design ↔ database schema)
- MemPalace tools accessible via MCP server (`mempalace`)
- Knowledge graph stores facts about NI entities, relationships, lifecycle events

---

## Summary of Key Divergences

| Area | Design Intent | Current Pathing | Impact |
|------|--------------|----------------|--------|
| **Tier 1 sync** | Phase inside AutomationManager | External cron (`run_widow_db_adjacent.py`) | Sync logic decoupled; harder to monitor together |
| **Domain-scoped routes** | `/api/{domain}/...` as distinct router | Flat `/api/` with domain param in functions | Domain boundary enforcement weaker at routing layer |
| **Phase execution** | 5 orchestrator cycle phases → AutomationManager | 7 independent scheduled tasks + request_phase() calls | Scheduling more fragmented than 5-phase cycle design |
| **Finance product root** | Separate `/finance/` codebase | Filter on broadsheet UI only | Finance users get same UI with domain filter |
| **Environment-climate domain** | JSON spec exists, no YAML config | No YAML — provisioned silo may be incomplete | Gap in domain lifecycle for environment-climate |
| **Pipeline tiers 2-3** | Explicit phases per tier | Mostly via request_phase() or collection_cycle sub-steps | Harder to trace execution chain for Tier 2 work |
| **Backpressure** | Not explicitly designed in early docs | Heavy backpressure system (DB pool pressure, queue caps, phase concurrency) | Over-engineered but effective for resource control |

