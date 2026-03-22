# News Intelligence System — System Overview

**Version 5.0.0** | FastAPI + React + TypeScript + PostgreSQL + Ollama LLM

This document maps the full system: API route structure, web interface structure, data flow, and key services. Use it as the single reference for "what exists and where."

**Related:** [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) (hosts, ops, scripts) · [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) (intelligence cascade) · stakeholder summary (archived): [_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md](_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md)

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Web Frontend (React 18 + TypeScript + Vite + MUI v5)              │
│  localhost:5173 → Nginx → localhost:8000                           │
├─────────────────────────────────────────────────────────────────────┤
│  API (FastAPI, Python) — api/main.py                            │
│  Domains: politics | finance | science-tech                        │
│  Routes: /api/{domain}/... and /api/...                            │
├──────────────┬──────────────┬───────────────┬───────────────────────┤
│  PostgreSQL  │  Ollama LLM  │  RSS Sources  │  External APIs       │
│  Widow host  │  Llama 3.1   │  via cron     │  EDGAR, FRED, Gold   │
│  port 5432   │  + Mistral   │  + on-demand  │  APIs                │
└──────────────┴──────────────┴───────────────┴───────────────────────┘
```

**Database:** PostgreSQL on Widow (<WIDOW_HOST_IP>:5432), DB `news_intel`. Domain data lives in schemas (`politics`, `finance`, `science_tech`); shared tables in `public` and `intelligence`.

---

## 2. Entry Points

| Role | Path |
|------|------|
| API server | `api/main.py` |
| Frontend app | `web/src/App.tsx` |
| API client layer | `web/src/services/api/` + `web/src/services/apiService.ts` |
| Database (single source) | `api/shared/database/connection.py` |
| LLM service | `api/shared/services/llm_service.py` |
| Automation (cron) | `scripts/rss_collection_with_health_check.sh`, `scripts/morning_data_pipeline.sh` |

---

## 3. API Route Structure

All routes are mounted from `api/main.py`. Each domain router defines its own prefix. The API pattern is `/api/{domain}/resource` for domain-scoped data and `/api/resource` for global endpoints.

### 3.1 News Aggregation

**Files:** `api/domains/news_aggregation/routes/news_aggregation.py`, `rss_duplicate_management.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/{domain}/rss_feeds` | List RSS feeds for domain |
| POST | `/api/{domain}/rss_feeds` | Create RSS feed (with duplicate prevention) |
| PUT | `/api/{domain}/rss_feeds/{feed_id}` | Update feed |
| DELETE | `/api/{domain}/rss_feeds/{feed_id}` | Delete feed |
| POST | `/api/{domain}/rss_feeds/collect_now` | Trigger immediate collection |
| POST | `/api/fetch_articles` | Fetch from all active feeds |
| GET | `/api/{domain}/articles` | List articles (filters: search, category, date, quality) |
| GET | `/api/{domain}/articles/{article_id}` | Single article |
| DELETE | `/api/{domain}/articles/{article_id}` | Delete article |
| DELETE | `/api/{domain}/articles` | Bulk delete |
| POST | `/api/articles/{article_id}/analyze_quality` | LLM quality analysis |
| GET | `/api/statistics` | Aggregation statistics |
| GET | `/api/rss_feeds/duplicates/detect` | Detect feed duplicates |
| GET | `/api/rss_feeds/duplicates/exact` | Exact URL duplicates |
| GET | `/api/rss_feeds/duplicates/similar` | Similar-domain feeds |
| POST | `/api/rss_feeds/duplicates/merge` | Merge duplicate feeds |
| POST | `/api/rss_feeds/duplicates/auto_merge` | Auto-merge all |
| GET | `/api/rss_feeds/duplicates/stats` | Duplicate stats |

### 3.2 Content Analysis

**Files:** `api/domains/content_analysis/routes/content_analysis.py`, `topic_management.py`, `topic_queue_management.py`, `article_deduplication.py`, `llm_activity_monitoring.py`, `deduplication_api.py`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/articles/{article_id}/analyze` | Full LLM analysis |
| POST | `/api/sentiment/analyze` | Sentiment analysis |
| POST | `/api/entities/extract` | Entity extraction |
| POST | `/api/summarize` | Summarization |
| GET | `/api/articles/{article_id}/analysis` | Get analysis results |
| POST | `/api/batch/process` | Start batch processing |
| GET | `/api/batch/status` | Batch status |
| GET | `/api/{domain}/content_analysis/topics` | Topic clusters for domain |
| POST | `/api/{domain}/content_analysis/topics/cluster` | AI topic clustering |
| GET | `/api/{domain}/content_analysis/topics/trending` | Trending topics |
| GET | `/api/{domain}/content_analysis/topics/big_picture` | Big picture analysis |
| GET | `/api/{domain}/content_analysis/topics/word_cloud` | Word cloud data |
| GET | `/api/{domain}/content_analysis/topics/merge_suggestions` | Merge suggestions |
| POST | `/api/{domain}/content_analysis/topics/merge_clusters` | Merge clusters |
| POST | `/api/{domain}/content_analysis/topics/{name}/convert_to_storyline` | Topic → storyline |
| GET | `/api/{domain}/content_analysis/topics/banned` | Banned topics |
| POST | `/api/{domain}/content_analysis/topics/banned` | Ban a topic |
| GET | `/api/{domain}/content_analysis/topics/queue/status` | Queue status |
| POST | `/api/{domain}/content_analysis/topics/queue/start` | Start queue worker |
| POST | `/api/{domain}/content_analysis/topics/queue/stop` | Stop queue worker |
| GET | `/api/articles/duplicates/detect` | Article duplicates |
| GET | `/api/articles/duplicates/content` | Content duplicates |
| POST | `/api/articles/duplicates/merge` | Merge duplicates |
| POST | `/api/articles/duplicates/auto_merge` | Auto-merge URL dupes |
| GET | `/api/articles/duplicates/stats` | Dedup stats |
| GET | `/api/content_analysis/llm/activity` | LLM activity log |
| GET | `/api/content_analysis/llm/status` | LLM status |
| GET | `/api/content_analysis/llm/dashboard` | LLM dashboard |

### 3.3 Storyline Management

**Files:** `api/domains/storyline_management/routes/storyline_management.py`, `storyline_automation.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/storylines` | List storylines |
| POST | `/api/{domain}/storylines` | Create storyline |
| GET | `/api/{domain}/storylines/{id}` | Get storyline |
| PUT | `/api/{domain}/storylines/{id}` | Update storyline |
| DELETE | `/api/{domain}/storylines/{id}` | Delete storyline |
| POST | `/api/{domain}/storylines/{id}/articles/{article_id}` | Add article to storyline |
| DELETE | `/api/{domain}/storylines/{id}/articles/{article_id}` | Remove article |
| GET | `/api/{domain}/storylines/{id}/available_articles` | Articles not yet linked |
| POST | `/api/{domain}/storylines/{id}/analyze` | LLM analysis |
| GET | `/api/{domain}/storylines/{id}/timeline` | Timeline view |
| GET | `/api/{domain}/storylines/{id}/narrative` | Narrative view |
| POST | `/api/{domain}/storylines/{id}/evolve` | Evolve storyline |
| POST | `/api/{domain}/storylines/{id}/assess_quality` | Quality assessment |
| GET | `/api/{domain}/storylines/{id}/report` | Storyline report |
| POST | `/api/{domain}/storylines/{id}/rag_analysis` | RAG analysis |
| GET | `/api/{domain}/storylines/{id}/correlations` | Correlations |
| GET | `/api/{domain}/storylines/{id}/predict` | Predictions |
| GET | `/api/{domain}/storylines/{id}/related` | Related storylines |
| POST | `/api/{domain}/storylines/discover` | Discover storylines |
| GET | `/api/{domain}/storylines/breaking_news` | Breaking news |
| GET | `/api/{domain}/storylines/emerging` | Emerging storylines |
| GET | `/api/{domain}/storylines/hierarchy` | Hierarchy view |
| GET | `/api/{domain}/storylines/mega` | Mega storylines |
| POST | `/api/{domain}/storylines/merge/{id1}/{id2}` | Manual merge |
| GET | `/api/{domain}/storylines/compare` | Compare storylines |
| GET | `/api/{domain}/storylines/evolution` | Evolution tracking |
| GET | `/api/storylines/consolidation/status` | Consolidation status |
| POST | `/api/{domain}/storylines/consolidation/run` | Run consolidation |
| GET | `/api/{domain}/storylines/{id}/automation/settings` | Automation settings |
| PUT | `/api/{domain}/storylines/{id}/automation/settings` | Update automation |
| POST | `/api/{domain}/storylines/{id}/automation/discover` | Discover articles for storyline |
| GET | `/api/{domain}/storylines/{id}/automation/suggestions` | Article suggestions |
| POST | `/api/{domain}/storylines/{id}/automation/suggestions/{sid}/approve` | Approve suggestion |
| POST | `/api/{domain}/storylines/{id}/automation/suggestions/{sid}/reject` | Reject suggestion |
| GET | `/api/watchlist` | Get watchlist |
| POST | `/api/watchlist/{storyline_id}` | Add to watchlist |
| DELETE | `/api/watchlist/{storyline_id}` | Remove from watchlist |
| GET | `/api/watchlist/alerts` | Watchlist alerts |
| POST | `/api/watchlist/alerts/{alert_id}/read` | Mark alert read |
| POST | `/api/watchlist/alerts/read-all` | Mark all read |
| GET | `/api/{domain}/events` | Get events |
| GET | `/api/monitoring/activity-feed` | Activity feed |
| GET | `/api/monitoring/dormant-alerts` | Dormant alerts |
| GET | `/api/monitoring/coverage-gaps` | Coverage gaps |
| GET | `/api/monitoring/cross-domain-connections` | Cross-domain connections |

### 3.4 Intelligence Hub

**Files:** `api/domains/intelligence_hub/routes/intelligence_hub.py`, `intelligence_analysis.py`, `rag_queries.py`, `content_synthesis.py`, `products.py`, `enrichment.py`, `quality.py`, `cross_domain.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/intelligence_hub/health` | Intelligence Hub health |
| GET | `/api/intelligence_hub/insights` | Intelligence insights |
| POST | `/api/intelligence_hub/insights/generate` | Generate insights |
| GET | `/api/intelligence_hub/trends` | Trend predictions |
| POST | `/api/intelligence_hub/trends/predict` | Predict trends |
| GET | `/api/intelligence_hub/analytics/summary` | Analytics summary |
| GET | `/api/{domain}/intelligence/rag/{storyline_id}` | RAG context for storyline |
| POST | `/api/{domain}/intelligence/rag/query` | RAG query |
| GET | `/api/{domain}/intelligence/quality/{storyline_id}` | Quality assessment |
| GET | `/api/{domain}/intelligence/anomalies` | Anomaly detection |
| GET | `/api/{domain}/intelligence/impact/{storyline_id}` | Impact assessment |
| GET | `/api/{domain}/intelligence/dashboard` | Intelligence dashboard |
| POST | `/api/{domain}/rag/query` | Domain RAG query |
| GET | `/api/{domain}/rag/quick` | Quick RAG query |
| POST | `/api/{domain}/rag/storyline/{id}/analyze` | RAG storyline analysis |
| GET | `/api/{domain}/rag/topic/{topic_name}` | Topic context |
| POST | `/api/{domain}/rag/knowledge/search` | Knowledge base search |
| GET | `/api/{domain}/rag/knowledge/entities` | Domain entities |
| GET | `/api/{domain}/rag/knowledge/terminology` | Terminology |
| GET | `/api/{domain}/rag/knowledge/sources` | Sources |
| POST | `/api/rag/cross-domain` | Cross-domain RAG |
| POST | `/api/{domain}/synthesis/storyline/{id}` | Synthesize storyline |
| GET | `/api/{domain}/synthesis/storyline/{id}/markdown` | Markdown synthesis |
| GET | `/api/{domain}/synthesis/storyline/{id}/cached` | Cached synthesis |
| POST | `/api/{domain}/synthesis/topic` | Synthesize topic |
| GET | `/api/{domain}/synthesis/breaking` | Breaking news synthesis |
| POST | `/api/{domain}/synthesis/storylines/bulk` | Bulk synthesis |
| POST | `/api/{domain}/synthesis/mega/{id}` | Mega storyline synthesis |

**Intelligence Products (briefings, digests, alerts):**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/products/generate_brief` | Generate daily brief on demand |
| POST | `/api/{domain}/intelligence/briefings/daily` | Domain daily briefing (with optional LLM lead) |
| GET | `/api/products/daily_brief` | Get daily brief |
| GET | `/api/products/weekly_digest` | Weekly digests |
| GET | `/api/products/alert_digest` | Alert digest |

**Quality & Enrichment:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/quality/claim_feedback` | Claim feedback |
| POST | `/api/quality/event_validation` | Event validation |
| GET | `/api/quality/extraction_metrics` | Extraction metrics |
| GET | `/api/quality/source_rankings` | Source rankings |
| POST | `/api/enrichment/enrich_entity` | Entity enrichment |
| POST | `/api/enrichment/verify_claim` | Claim verification |

**Cross-Domain Intelligence:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/intelligence/cross_domain_synthesis` | Cross-domain synthesis |
| GET | `/api/intelligence/cross_domain_correlations` | Cross-domain correlations |
| GET | `/api/intelligence/meta_storylines` | Meta storylines |
| GET | `/api/intelligence/unified_timeline` | Unified timeline |
| POST | `/api/intelligence/trend_analysis` | Trend analysis |
| GET | `/api/intelligence/predictions/{domain}` | Predictions |

### 3.5 Context-Centric Intelligence

**File:** `api/domains/intelligence_hub/routes/context_centric.py` (prefix `/api`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/context_centric/status` | Context-centric status |
| GET | `/api/context_centric/quality` | Quality metrics |
| POST | `/api/context_centric/sync_entity_profiles` | Sync entity profiles |
| POST | `/api/context_centric/sync_contexts` | Sync contexts |
| POST | `/api/context_centric/run_enhancement_cycle` | Run enhancement |
| POST | `/api/context_centric/run_pattern_matching` | Run pattern matching |
| POST | `/api/context_centric/run_entity_enrichment` | Run enrichment |
| POST | `/api/context_centric/discover_events` | Discover events |
| POST | `/api/context_centric/review_events` | Review events |
| POST | `/api/context_centric/cleanup` | Cleanup |
| GET | `/api/context_centric/search` | Context search |
| GET | `/api/entity_profiles` | List entity profiles |
| GET | `/api/entity_profiles/{id}` | Get entity profile |
| PATCH | `/api/entity_profiles/{id}` | Update profile |
| POST | `/api/entity_profiles/{id}/merge` | Merge profiles |
| GET | `/api/contexts` | List contexts |
| GET | `/api/contexts/{id}` | Get context |
| PATCH | `/api/contexts/{id}` | Update context |
| GET | `/api/tracked_events` | List tracked events |
| POST | `/api/tracked_events` | Create event |
| PUT | `/api/tracked_events/{id}` | Update event |
| GET | `/api/tracked_events/{id}` | Get event |
| POST | `/api/tracked_events/{id}/chronicles/update` | Update chronicles |
| GET | `/api/tracked_events/{id}/report` | Get event report |
| POST | `/api/tracked_events/{id}/report` | Generate report |
| GET | `/api/entity_dossiers` | List dossiers |
| POST | `/api/entity_dossiers/compile` | Compile dossier |
| GET | `/api/processed_documents` | List processed documents |
| POST | `/api/processed_documents` | Create document |
| POST | `/api/processed_documents/{id}/process` | Process document |
| GET | `/api/narrative_threads` | List narrative threads |
| POST | `/api/narrative_threads/build` | Build thread |
| POST | `/api/narrative_threads/synthesize` | Synthesize thread |
| GET | `/api/claims` | List claims |
| GET | `/api/pattern_discoveries` | Pattern discoveries |

### 3.6 Finance

**File:** `api/domains/finance/routes/finance.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/finance/tasks` | List analysis tasks |
| GET | `/api/{domain}/finance/tasks/{id}` | Task result |
| GET | `/api/{domain}/finance/tasks/{id}/status` | Task status |
| GET | `/api/{domain}/finance/tasks/{id}/ledger` | Task ledger |
| GET | `/api/{domain}/finance/trace/{id}` | Task trace |
| POST | `/api/{domain}/finance/analyze` | Trigger analysis task |
| POST | `/api/{domain}/finance/analyze/enhance` | Enhanced analysis |
| GET | `/api/{domain}/finance/evidence` | Evidence index |
| GET | `/api/{domain}/finance/evidence/preview` | Evidence preview |
| GET | `/api/{domain}/finance/verification` | Verification history |
| GET | `/api/{domain}/finance/schedule` | Schedule status |
| GET | `/api/{domain}/finance/sources/status` | Source health |
| GET | `/api/{domain}/finance/data-sources` | Data sources |
| GET | `/api/{domain}/finance/market-data` | Market data |
| GET | `/api/{domain}/finance/market-trends` | Market trends |
| GET | `/api/{domain}/finance/market-patterns` | Market patterns |
| GET | `/api/{domain}/finance/corporate-announcements` | Corporate announcements |
| GET | `/api/{domain}/finance/gold` | Gold amalgam |
| POST | `/api/{domain}/finance/gold/fetch` | Gold fetch |
| GET | `/api/{domain}/finance/gold/history` | Gold history |
| GET | `/api/{domain}/finance/gold/spot` | Gold spot price |
| GET | `/api/{domain}/finance/gold/authority` | Gold authority data |
| GET | `/api/{domain}/finance/gold/geo-events` | Gold geo events |
| GET | `/api/{domain}/finance/commodity/{commodity}/history` | Commodity history |
| GET | `/api/{domain}/finance/commodity/{commodity}/spot` | Commodity spot |
| GET | `/api/{domain}/finance/commodity/{commodity}/authority` | Commodity authority |
| POST | `/api/{domain}/finance/edgar/ingest` | EDGAR ingest |
| POST | `/api/{domain}/finance/fetch-fred` | FRED fetch |
| GET | `/api/{domain}/finance/research-topics` | Research topics |
| POST | `/api/{domain}/finance/research-topics` | Create research topic |
| POST | `/api/{domain}/finance/research-topics/{id}/refine` | Refine topic |

### 3.7 System Monitoring

**Files:** `api/domains/system_monitoring/routes/system_monitoring.py`, `route_supervisor.py`, `orchestrator.py`, `resource_dashboard.py`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system_monitoring/health` | System health |
| GET | `/api/system_monitoring/status` | System status |
| GET | `/api/system_monitoring/dashboard` | Dashboard |
| GET | `/api/system_monitoring/monitoring/overview` | Monitoring overview |
| GET | `/api/system_monitoring/fast_stats` | Fast stats |
| GET | `/api/system_monitoring/metrics` | Metrics |
| GET | `/api/system_monitoring/performance` | Performance metrics |
| GET | `/api/system_monitoring/automation/status` | Automation phase status |
| GET | `/api/system_monitoring/process_run_summary` | Process run summary (DB-backed) |
| GET | `/api/system_monitoring/pipeline_status` | Pipeline status |
| POST | `/api/system_monitoring/pipeline/trigger` | Trigger pipeline |
| POST | `/api/system_monitoring/monitoring/trigger_phase` | Trigger specific phase |
| GET | `/api/system_monitoring/sources_collected` | Sources collected |
| GET | `/api/system_monitoring/alerts` | System alerts |
| POST | `/api/system_monitoring/alerts/create` | Create alert |
| PUT | `/api/system_monitoring/alerts/{id}/resolve` | Resolve alert |
| GET | `/api/system_monitoring/anomalies` | Anomalies |
| POST | `/api/system_monitoring/investigate_anomaly` | Investigate anomaly |
| POST | `/api/system_monitoring/logs` | Ingest client log |
| POST | `/api/system_monitoring/logs/batch` | Batch log ingest |
| GET | `/api/system_monitoring/logs/stats` | Log statistics |
| GET | `/api/system_monitoring/logs/realtime` | Realtime logs |
| GET | `/api/system_monitoring/database/stats` | Database stats |
| GET | `/api/system_monitoring/devices` | Monitoring devices |
| GET | `/api/system_monitoring/health/feeds` | Feed health |
| GET | `/api/system_monitoring/route_supervisor/health` | Route supervisor health |
| GET | `/api/system_monitoring/route_supervisor/report` | Route supervisor report |
| GET | `/api/system_monitoring/route_supervisor/issues` | Route issues |
| POST | `/api/system_monitoring/route_supervisor/check_now` | Force route check |
| GET | `/api/orchestrator/status` | Orchestrator status |
| GET | `/api/orchestrator/metrics` | Orchestrator metrics |
| GET | `/api/orchestrator/decision_log` | Decision log |
| GET | `/api/orchestrator/dashboard` | Orchestrator dashboard |
| POST | `/api/orchestrator/manual_override` | Manual override |

### 3.8 User Management

**File:** `api/domains/user_management/routes/user_management.py` (prefix `/api/user_management`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user_management/users` | List users |
| GET | `/api/user_management/users/{id}` | Get user |
| POST | `/api/user_management/users` | Create user |
| PUT | `/api/user_management/users/{id}` | Update user |
| DELETE | `/api/user_management/users/{id}` | Delete user |
| GET | `/api/user_management/preferences/{id}` | Get preferences |
| PUT | `/api/user_management/preferences/{id}` | Update preferences |

### 3.9 v3 Compatibility Layer

**File:** `api/compatibility/v3_compatibility.py` — Legacy routes at `/api/articles/`, `/api/storylines/`, `/api/rss-feeds/`, `/api/topics/`, `/api/dashboard/stats`, `/api/intelligence/topic-clusters`.

---

## 4. Web Interface Structure

### 4.1 Route Map

All routes are under `/:domain/` where domain is `politics`, `finance`, or `science-tech`. Default redirect: `/` → `/politics/dashboard`.

| Path | Component | Description |
|------|-----------|-------------|
| `/:domain/dashboard` | `Dashboard` | Intelligence dashboard: What's New, Active Investigations, System Intelligence |
| `/:domain/discover` | `DiscoverPage` | Latest contexts, entity browser, event timeline |
| `/:domain/discover/contexts/:id` | `ContextDetailPage` | Context detail |
| `/:domain/storylines` | `Storylines` | Storyline list |
| `/:domain/storylines/:id` | `StorylineDetail` | Storyline detail, timeline, articles |
| `/:domain/briefings` | `Briefings` | Daily briefings with AI summary generation |
| `/:domain/report` | `ReportPage` | Today's Report — editorial display (lead, secondary, digest) |
| `/:domain/investigate` | `InvestigatePage` | Tracked events, entity profiles, context search |
| `/:domain/investigate/events/:id` | `EventDetailPage` | Event detail with chronicles |
| `/:domain/investigate/entities` | `EntitiesListPage` | Entity list |
| `/:domain/investigate/entities/:id` | `EntityDetailPage` | Entity detail |
| `/:domain/investigate/search` | `SearchPage` | Context-centric search |
| `/:domain/investigate/documents` | `ProcessedDocumentsPage` | Processed documents |
| `/:domain/investigate/narrative-threads` | `NarrativeThreadsPage` | Narrative threads |
| `/:domain/monitor` | `MonitorPage` | System monitoring, automation, pipeline |
| `/:domain/analyze` | `AnalyzePage` | Analysis |
| `/:domain/analysis` | `FinancialAnalysis` | Financial analysis form |
| `/:domain/analysis/:taskId` | `FinancialAnalysisResult` | Financial analysis result |
| `/:domain/commodity/:commodity` | `CommodityDashboard` | Commodity dashboard (gold, silver, platinum) |

### 4.2 Navigation (Sidebar)

Located in `web/src/layout/AppNav.tsx` — persistent sidebar (220px desktop, drawer on mobile).

| Label | Path | Icon | Visibility |
|-------|------|------|------------|
| Dashboard | `dashboard` | DashboardIcon | All domains |
| Discover | `discover` | ExploreIcon | All domains |
| Storylines | `storylines` | AutoStoriesIcon | All domains |
| Briefings | `briefings` | MenuBookIcon | All domains |
| Today's Report | `report` | NewspaperIcon | All domains |
| Investigate | `investigate` | SearchIcon | All domains |
| Monitor | `monitor` | MonitorHeartIcon | All domains |
| Analyze | `analyze` | AnalyticsIcon | All domains |
| Commodity | `commodity/gold` | ShowChartIcon | **Finance only** |

Domain selector in the header switches between politics, finance, science-tech.

### 4.3 Page Components

**Active (routed in `App.tsx`):**

| Component | File |
|-----------|------|
| Dashboard | `web/src/pages/Dashboard/Dashboard.tsx` |
| DiscoverPage | `web/src/pages/Discover/DiscoverPage.tsx` |
| ContextDetailPage | `web/src/pages/Discover/ContextDetailPage.tsx` |
| Storylines | `web/src/pages/Storylines/Storylines.tsx` |
| StorylineDetail | `web/src/pages/Storylines/StorylineDetail.jsx` |
| Briefings | `web/src/pages/Briefings/Briefings.tsx` |
| ReportPage | `web/src/pages/Report/ReportPage.tsx` |
| InvestigatePage | `web/src/pages/Investigate/InvestigatePage.tsx` |
| EventDetailPage | `web/src/pages/Investigate/EventDetailPage.tsx` |
| EntityDetailPage | `web/src/pages/Investigate/EntityDetailPage.tsx` |
| EntitiesListPage | `web/src/pages/Investigate/EntitiesListPage.tsx` |
| SearchPage | `web/src/pages/Investigate/SearchPage.tsx` |
| ProcessedDocumentsPage | `web/src/pages/Investigate/ProcessedDocumentsPage.tsx` |
| NarrativeThreadsPage | `web/src/pages/Investigate/NarrativeThreadsPage.tsx` |
| MonitorPage | `web/src/pages/Monitor/MonitorPage.tsx` |
| AnalyzePage | `web/src/pages/Analyze/AnalyzePage.tsx` |
| FinancialAnalysis | `web/src/pages/Finance/FinancialAnalysis.tsx` |
| FinancialAnalysisResult | `web/src/pages/Finance/FinancialAnalysisResult.tsx` |
| CommodityDashboard | `web/src/pages/Finance/CommodityDashboard.tsx` |

**Available but not currently routed:**

| Component | File | Notes |
|-----------|------|-------|
| Articles | `web/src/pages/Articles/Articles.tsx` | Article list view |
| ArticleDetail | `web/src/pages/Articles/ArticleDetail.jsx` | Article detail |
| RSSFeeds | `web/src/pages/RSSFeeds/RSSFeeds.tsx` | RSS feed management |
| Topics | `web/src/pages/Topics/Topics.tsx` | Topic management |
| Watchlist | `web/src/pages/Watchlist/Watchlist.tsx` | Watchlist view |
| Monitoring | `web/src/pages/Monitoring/Monitoring.tsx` | Older monitoring view |
| Settings | `web/src/pages/Settings/Settings.tsx` | Settings page |
| MLProcessing | `web/src/pages/MLProcessing/MLProcessing.tsx` | ML processing view |
| StorylineDiscovery | `web/src/pages/Storylines/StorylineDiscovery.jsx` | Discovery view |
| SynthesizedView | `web/src/pages/Storylines/SynthesizedView.jsx` | Synthesis view |

### 4.4 API Service Modules

Located in `web/src/services/api/`. Each module maps to a set of API endpoints.

| Module | Connects to |
|--------|------------|
| `articles.ts` | `/api/{domain}/articles`, article analysis |
| `storylines.ts` | `/api/{domain}/storylines`, automation, consolidation, synthesis |
| `contextCentric.ts` | `/api/context_centric/*`, `/api/entity_profiles`, `/api/tracked_events`, `/api/contexts`, `/api/claims`, `/api/processed_documents`, `/api/narrative_threads` |
| `monitoring.ts` | `/api/system_monitoring/*`, `/api/orchestrator/*`, `/api/{domain}/finance/*` (market data), `/api/articles/duplicates/*` |
| `watchlist.ts` | `/api/watchlist`, `/api/monitoring/activity-feed`, dormant-alerts, coverage-gaps |
| `rss.ts` | `/api/{domain}/rss_feeds` |
| `topics.ts` | `/api/{domain}/content_analysis/topics`, `/api/topics/*` |
| `financeAnalysis.ts` | `/api/{domain}/finance/analyze`, tasks, evidence, research-topics |
| `intelligence.ts` | `/api/{domain}/intelligence/*`, RAG, synthesis, briefings |
| `client.ts` | Axios instance via `apiConnectionManager` |

**`apiService.ts`** provides a unified wrapper (`articlesApi`, `watchlistApi`, `storylinesApi`, `topicsApi`, `rssApi`, `monitoringApi`, `intelligenceApi`, `financeAnalysisApi`) for backward compatibility.

### 4.5 Domain-Specific Components

**`web/src/domains/Finance/`:** `MarketResearch.tsx`, `CorporateAnnouncements.tsx`, `MarketPatterns.tsx` — exist but not routed in current `App.tsx` (were used in an archived layout).

### 4.6 Contexts and Providers

| Context | File | Purpose |
|---------|------|---------|
| DomainContext | `web/src/contexts/DomainContext.tsx` | Current domain state, `setDomain`, `availableDomains`. Persists in `localStorage`. |

**Provider hierarchy:** `ErrorBoundary` → `ThemeProvider` (MUI) → `CssBaseline` → `DomainProvider` → `Router` → `Routes`.

---

## 5. Database Schema Layout

| Schema | Contains |
|--------|---------|
| `public` | `domains`, `domain_metadata`, `rss_feeds` (legacy), `watchlist`, `automation_run_history`, `emerging_storylines` |
| `politics` | `articles`, `storylines`, `storyline_articles`, `topic_clusters`, `article_topic_clusters`, `rss_feeds`, `events` |
| `finance` | Same structure as politics |
| `science_tech` | Same structure as politics |
| `intelligence` | `tracked_events`, `entity_profiles`, `contexts`, `claims`, `versioned_facts`, `entity_dossiers`, `processed_documents`, `narrative_threads`, `document_intelligence`, `pattern_discoveries` |

### 5.1 Critical Data Preservation Points

Content must be preserved and enriched at every step of the pipeline. If content is lost at any stage, all downstream intelligence degrades. See `docs/DATA_FLOW_ARCHITECTURE.md` for the full cascade.

| Stage | Source | Must Preserve | Output Location | If Lost |
|-------|--------|--------------|----------------|---------|
| Ingestion | RSS feed | Full article text | `{domain}.articles.content` | All downstream intelligence empty |
| ML Processing | `articles.content` | Summary, key points, sentiment | `articles.ml_data` (JSONB) | Topic cloud empty, no intelligence |
| Entity Extraction | `articles.content` | People, orgs, locations | `article_entities`, `articles.entities` | Weak entity profiles |
| Context Creation | `articles.content` | Canonical content unit | `intelligence.contexts.content` | No claims, events, or profiles extracted |
| Claim Extraction | `contexts.content` | Subject-predicate-object facts | `intelligence.extracted_claims` | No fact verification |
| Event Tracking | Grouped contexts | Developments, analysis | `tracked_events` + `event_chronicles` | No event briefings |
| Entity Profiles | Contexts by entity | Sections, relationships | `entity_profiles.sections` | No entity dossiers |
| Storylines | Articles + entities | Editorial narrative | `storylines.editorial_document` (JSONB) | Metrics-only briefings |
| Editorial Output | Editorial documents | Narrative briefing | API response `content` field | Falls back to counts |

**Key JSONB intelligence fields** (the primary products of the system):

| Table | Field | Purpose | Status |
|-------|-------|---------|--------|
| `{domain}.storylines` | `editorial_document` | Storyline narrative (lede, developments, analysis, outlook) | Schema exists (migration 158); not yet populated by pipeline |
| `intelligence.tracked_events` | `editorial_briefing` / `editorial_briefing_json` | Event briefing (headline, chronology, impact) | Schema exists (migration 158); not yet populated by pipeline |
| `intelligence.entity_profiles` | `sections` / `relationships_summary` | Entity dossier | Schema exists (migration 143); populated by entity_profile_builder |
| `{domain}.articles` | `ml_data` | ML outputs (summary, key_points, sentiment) | Populated by ML pipeline |

See `docs/_archive/retired_root_docs_2026_03/CORE_ARCHITECTURE_PRINCIPLES.md` for architectural guardrails and `docs/_archive/retired_root_docs_2026_03/DATABASE_DESIGN_PHILOSOPHY.md` for the intended JSONB structures (archived).

---

## 6. Key Services (Backend)

| Service | File | Purpose |
|---------|------|---------|
| LLM Service | `api/shared/services/llm_service.py` | Ollama interface (Llama 3.1 8B primary, Mistral 7B secondary) |
| Automation Manager | `api/services/automation_manager.py` | Scheduled pipeline phases (RSS collection, ML processing, storyline evolution, quality assessment) |
| Daily Briefing | `api/modules/ml/daily_briefing_service.py` | Generates daily briefing sections from DB (key developments, metrics, storyline analysis) |
| Storyline Tracker | `api/modules/ml/storyline_tracker.py` | Topic cloud, breaking topics, daily summary |
| ML Pipeline | `api/modules/ml/ml_pipeline.py` | Article ML processing pipeline |
| Event Tracking | `api/services/event_tracking_service.py` | Event extraction and lifecycle management |
| Entity Profile Builder | `api/services/entity_profile_builder_service.py` | Entity profile construction from articles |
| Route Supervisor | `api/shared/services/route_supervisor.py` | API route health monitoring |
| RSS Collector | `api/collectors/rss_collector.py` | RSS feed fetching and article ingestion |
| Circuit Breaker | `api/services/circuit_breaker_service.py` | Ollama/external service circuit breaker |

---

## 7. Data Flow

```
RSS Sources / External APIs
       │
       ▼
  RSS Collector (cron or on-demand)
       │
       ▼
  {domain}.articles  ──────────────────────────────────────┐
       │                                                    │
       ▼                                                    ▼
  ML Pipeline (quality, entities, topics)          Storyline Automation
       │                                            (discover, link, evolve)
       ▼                                                    │
  {domain}.topic_clusters                                   ▼
  intelligence.entity_profiles                     {domain}.storylines
  intelligence.contexts                            {domain}.storyline_articles
       │                                                    │
       ▼                                                    ▼
  Event Tracking / Pattern Recognition           Briefings / Synthesis / Reports
       │                                                    │
       ▼                                                    ▼
  intelligence.tracked_events                      API → Frontend
  intelligence.claims
```

---

## 8. File Layout Summary

```
api/
├── main.py                    # FastAPI app, router mounting
├── domains/
│   ├── news_aggregation/routes/  # RSS feeds, articles
│   ├── content_analysis/routes/  # Topics, LLM analysis, deduplication
│   ├── storyline_management/routes/  # Storylines, watchlist, events
│   ├── intelligence_hub/routes/  # Intelligence, RAG, synthesis, briefings, context-centric
│   ├── finance/routes/           # Finance analysis, commodities
│   ├── user_management/routes/   # User CRUD, preferences
│   └── system_monitoring/routes/ # Health, automation, pipeline, orchestrator
├── services/                     # Business logic services
├── modules/ml/                   # ML pipeline, briefing, RAG, summarization
├── shared/
│   ├── database/connection.py    # DB connection (single source of truth)
│   └── services/llm_service.py   # LLM interface
├── collectors/                   # RSS collector
├── compatibility/                # v3 compat layer
├── orchestration/                # Newsroom orchestrator (background)
├── config/                       # Configuration files
└── database/migrations/          # SQL migrations

web/src/
├── App.tsx                       # Route definitions, providers
├── layout/AppNav.tsx             # Sidebar navigation
├── pages/                        # Page components (see 4.3)
├── components/                   # Shared components
├── services/
│   ├── api/                      # API modules (see 4.4)
│   ├── apiService.ts             # Unified API wrapper
│   └── apiConnectionManager.ts   # Connection management
├── contexts/DomainContext.tsx     # Domain state
├── domains/Finance/              # Finance-specific components
├── types/index.ts                # TypeScript types
└── utils/                        # Helpers (domain, debug, feature test)
```
