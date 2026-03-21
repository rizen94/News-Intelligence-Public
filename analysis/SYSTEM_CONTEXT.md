# System Context — News Intelligence

Reference document for log analysis. Describes the system architecture, route inventory, database schemas, and frontend polling behavior.

---

## Architecture overview

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│  React SPA  │────>│  Vite proxy :3000 │────>│  FastAPI :8000  │
│  (TypeScript)│     │  /api → :8000    │     │  uvicorn        │
└─────────────┘     └──────────────────┘     └───────┬────────┘
                                                      │
                              ┌────────────────────────┼─────────────┐
                              │                        │             │
                         ┌────▼────┐            ┌──────▼──┐   ┌─────▼─────┐
                         │ Postgres │            │ Ollama  │   │ External  │
                         │ :5432    │            │ :11434  │   │ APIs      │
                         │ (Widow)  │            │ (local) │   │ FRED/EDGAR│
                         └─────────┘            └─────────┘   └───────────┘
```

- **Database:** PostgreSQL on Widow (<WIDOW_HOST_IP>:5432), DB `news_intel`.
- **LLM:** Ollama on localhost:11434. Used for entity extraction, topic clustering, intelligence analysis.
- **External APIs:** FRED (economic data), EDGAR (SEC filings), FreeGoldAPI.

---

## API route inventory

### Domain-scoped routes (require `{domain}` in path)

| Prefix | Description | Source |
|--------|-------------|--------|
| `/api/{domain}/articles` | Article CRUD, listing, search | news_aggregation.py |
| `/api/{domain}/storylines` | Storyline CRUD, timeline, analysis | storyline_management.py |
| `/api/{domain}/content_analysis/topics` | Topic management | topic_management.py |
| `/api/{domain}/rss_feeds` | RSS feed management | news_aggregation.py |
| `/api/{domain}/finance/*` | Finance data, tasks, analysis | finance.py |

### Global routes (no domain prefix)

| Prefix | Description | Source |
|--------|-------------|--------|
| `/api/system_monitoring/status` | System health and status | system_monitoring.py |
| `/api/system_monitoring/health` | Health check endpoint | system_monitoring.py |
| `/api/system_monitoring/pipeline_status` | Pipeline status | system_monitoring.py |
| `/api/system_monitoring/metrics` | System metrics | system_monitoring.py |
| `/api/system_monitoring/dashboard` | Dashboard data | system_monitoring.py |
| `/api/system_monitoring/logs/*` | Log retrieval | system_monitoring.py |
| `/api/system_monitoring/route_supervisor/*` | Route health checks | route_supervisor.py |
| `/api/system_monitoring/resource_dashboard` | Resource usage | resource_dashboard.py |
| `/api/orchestrator/status` | Orchestrator status | orchestrator.py |
| `/api/orchestrator/dashboard` | Orchestrator dashboard | orchestrator.py |
| `/api/context_centric/status` | Context-centric pipeline status | context_centric.py |
| `/api/contexts` | Context queries | context_centric.py |
| `/api/entity_profiles` | Entity profiles | context_centric.py |
| `/api/tracked_events` | Event tracking | context_centric.py |
| `/api/claims` | Extracted claims | context_centric.py |
| `/api/intelligence_hub/*` | Intelligence analysis, RAG | intelligence_hub.py |
| `/api/watchlist/*` | Watchlist and alerts | storyline_management.py |
| `/api/user_management/*` | User preferences | user_management.py |
| `/api/rss_feeds/*` | RSS duplicate management | rss_duplicate_management.py |

---

## Database schemas

| Schema | Purpose | Key tables |
|--------|---------|------------|
| `public` | Shared tables, legacy | articles, storylines, rss_feeds, topics, watchlist, system_metrics |
| `politics` | Politics domain silo | articles, storylines, topics, rss_feeds, entity_canonical, article_entities |
| `finance` | Finance domain silo | articles, storylines, topics, market_patterns, corporate_announcements |
| `science_tech` | Science/tech domain silo | articles, storylines, topics, rss_feeds |
| `intelligence` | Context-centric analytics | contexts, entity_profiles, tracked_events, extracted_claims, pattern_discoveries, entity_dossiers |
| `orchestration` | Event-driven orchestration | events, task_queue, processing_state, source_plugins |

---

## Frontend polling behavior

These endpoints are polled automatically by the frontend on timers:

| Endpoint | Interval | Component |
|----------|----------|-----------|
| `/api/system_monitoring/health` | 30s | frontendHealthService, HeroStatusBar |
| `/api/system_monitoring/status` | 30s | Monitoring page |
| `/api/orchestrator/dashboard` | 30–60s | HeroStatusBar, Monitoring, MonitorPage |
| `/api/context_centric/status` | 60s | HeroStatusBar |
| `/api/watchlist/alerts` | 60s | Navigation |
| `/api/system_monitoring/pipeline_status` | 30s | Monitoring page |
| `/api/system_monitoring/metrics` | 30s | Monitoring page |
| `/api/system_monitoring/dashboard` | 30s | Monitoring page |
| API connectivity test | 30s | APIConnectionStatus |

**Estimated polling load with browser open on Monitoring page:** ~20 requests per 30-second cycle, or ~40 req/min. With the browser closed or on a non-polling page, the load drops to ~6 req/min from background health checks and navigation badge updates.

---

## Key services and dependencies

| Service | Dependency | Impact if missing |
|---------|-----------|-------------------|
| Entity extraction | Ollama (localhost:11434) | No entities extracted from new articles |
| Topic clustering | Ollama | No topics assigned to articles |
| Intelligence analysis | Ollama | RAG and synthesis unavailable |
| Finance vector store | chromadb | Vector writes fail silently |
| GPU monitoring | GPUtil | Warning logged, no GPU metrics |
| Distributed cache | redis | Warning logged, falls back to in-memory |
| Economic data | FRED API key | Skips FRED data fetch |

---

## Configuration files

| File | Purpose |
|------|---------|
| `api/config/settings.py` | Core settings (paths, models, DB, GPU/RAM limits, Ollama) |
| `api/config/database.py` | DB connection shim → shared.database.connection |
| `api/config/paths.py` | Project paths (root, data, reports, logs) |
| `api/config/logging_config.py` | Logging setup (handlers, levels, JSON output) |
| `api/config/context_centric.yaml` | Context-centric pipeline task flags |
| `api/config/orchestrator_governance.yaml` | Orchestrator loop and governor settings |
| `api/config/newsroom.yaml` | Newsroom orchestrator v6 role config |
| `api/config/monitoring_devices.yaml` | Device health monitoring targets |
| `api/config/finance_schedule.yaml` | Finance task schedule |
| `api/config/sources.yaml` | Finance data source config |
