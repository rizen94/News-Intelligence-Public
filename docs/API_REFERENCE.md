# News Intelligence System — API Reference

**Purpose:** All API areas, endpoint patterns, and integrations.  
**Base URL:** `http://localhost:8000` (or configured API host)  
**Interactive docs:** `GET /docs` (Swagger), `GET /redoc` (ReDoc)  
**Version:** 8.0 | **Last updated:** March 2026

---

## 1. Overview

- **Path convention:** Flat `/api` prefix (no version in path). Domain-scoped routes use `{domain}` where `domain` is `politics`, `finance`, or `science-tech`.
- **Response shape:** Endpoints typically return JSON with `success`, `data`, and optional `message`. Standard error responses use HTTP status codes and a consistent error payload.
- **Integrations:** The React frontend calls these APIs via `web/src/services/api/` and `apiService.ts`; base URL and proxy are configured in env and Vite.

---

## 2. Health and root

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root: app name, version, domains, docs links. |
| GET | `/api/system_monitoring/health` | System health (DB, Redis, components). |
| GET | `/api/health` | Legacy health (news_aggregation, route_supervisor). |

---

## 3. Domain-scoped content

### 3.1 News aggregation (`/api`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/rss_feeds` | List RSS feeds for domain. |
| POST | `/api/{domain}/rss_feeds` | Create feed. |
| PUT | `/api/{domain}/rss_feeds/{feed_id}` | Update feed. |
| DELETE | `/api/{domain}/rss_feeds/{feed_id}` | Delete feed. |
| POST | `/api/{domain}/rss_feeds/collect_now` | Trigger collection now. |
| GET | `/api/{domain}/articles` | List articles (paginated, filters). |
| GET | `/api/{domain}/articles/{article_id}` | Get article by ID. |
| DELETE | `/api/{domain}/articles/{article_id}` | Delete article. |
| POST | `/api/fetch_articles` | Fetch articles (body: URLs/sources). |
| GET | `/api/articles/recent` | Recent articles (all domains). |
| GET | `/api/statistics` | Article statistics. |

### 3.2 Content analysis (`/api`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/content_analysis/topics` | Topic clusters. |
| GET | `/api/{domain}/content_analysis/topics/trending` | Trending topics. |
| GET | `/api/{domain}/content_analysis/topics/big_picture` | Big-picture topics. |
| POST | `/api/{domain}/content_analysis/topics/cluster` | Run clustering. |
| GET | `/api/{domain}/content_analysis/topics/cluster/status` | Cluster job status. |
| POST | `/api/{domain}/content_analysis/topics/merge_clusters` | Merge clusters. |
| GET | `/api/{domain}/content_analysis/topics/{cluster_name}/articles` | Articles in cluster. |
| GET | `/api/{domain}/content_analysis/topics/{cluster_name}/summary` | Cluster summary. |
| POST | `/api/{domain}/content_analysis/topics/{cluster_name}/convert_to_storyline` | Convert cluster to storyline. |
| GET | `/api/{domain}/content_analysis/topics/banned` | Banned topics. |
| POST | `/api/{domain}/content_analysis/topics/banned` | Add banned topic. |
| DELETE | `/api/{domain}/content_analysis/topics/banned/{topic_name}` | Remove banned topic. |
| GET | `/api/articles/{article_id}` | Article (content_analysis). |
| POST | `/api/articles/{article_id}/analyze` | Trigger analysis. |
| GET | `/api/{domain}/content_analysis/topics/queue/status` | Topic queue status. |
| POST | `/api/{domain}/content_analysis/topics/queue/start` | Start queue. |
| POST | `/api/{domain}/content_analysis/topics/queue/process` | Process queue. |
| GET | `/api/content_analysis/llm/activity` | LLM activity. |
| GET | `/api/{domain}/content_analysis/llm/activity` | LLM activity per domain. |

### 3.3 Article deduplication (`/api/articles`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/articles/duplicates/detect` | Detect duplicates. |
| GET | `/api/articles/duplicates/url` | Duplicates by URL. |
| POST | `/api/articles/duplicates/merge` | Merge duplicates. |
| POST | `/api/articles/duplicates/auto_merge` | Auto-merge. |
| GET | `/api/articles/duplicates/stats` | Duplicate stats. |

### 3.4 Storylines (`/api`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/storylines` | List storylines. |
| GET | `/api/{domain}/storylines/emerging` | Emerging storylines. |
| POST | `/api/{domain}/storylines` | Create storyline. |
| GET | `/api/{domain}/storylines/{storyline_id}` | Get storyline. |
| PUT | `/api/{domain}/storylines/{storyline_id}` | Update storyline. |
| DELETE | `/api/{domain}/storylines/{storyline_id}` | Delete storyline. |
| POST | `/api/{domain}/storylines/{storyline_id}/add_article` | Add article. |
| GET | `/api/{domain}/storylines/{storyline_id}/timeline` | Timeline. |
| GET | `/api/{domain}/storylines/{storyline_id}/narrative` | Narrative. |
| POST | `/api/{domain}/storylines/{storyline_id}/analyze` | Analyze. |
| POST | `/api/{domain}/storylines/{storyline_id}/rag_analysis` | RAG analysis. |
| POST | `/api/{domain}/storylines/detect` | Detect storylines. |
| GET | `/api/storylines/consolidation/status` | Consolidation status (global). |
| POST | `/api/storylines/consolidation/run` | Run consolidation (all domains). |
| POST | `/api/{domain}/storylines/consolidation/run` | Run consolidation for one domain. |
| POST | `/api/{domain}/storylines/merge/{primary_id}/{secondary_id}` | Merge two storylines. |
| GET | `/api/{domain}/storylines/{storyline_id}/automation/settings` | Automation settings. |
| PUT | `/api/{domain}/storylines/{storyline_id}/automation/settings` | Update automation. |
| GET | `/api/{domain}/events` | Events (timeline). |

### 3.5 Topic management (DB `topics` / assignments — domain-scoped)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/topics` | List managed topics. |
| GET | `/api/{domain}/topics/needing_review` | Topics below accuracy threshold. |
| GET | `/api/{domain}/topics/{topic_id}` | Get one topic. |
| POST | `/api/{domain}/topics` | Create topic. |
| PUT | `/api/{domain}/topics/{topic_id}` | Update topic. |
| POST | `/api/{domain}/topics/merge` | Merge topics (body: `topic_ids`, optional `domain` override). |
| GET | `/api/{domain}/topics/{topic_id}/articles` | Articles linked to topic. |
| POST | `/api/{domain}/articles/{article_id}/process_topics` | LLM topic extraction for one article. |
| POST | `/api/{domain}/articles/batch_process_topics` | Batch process (body: article id list). |
| POST | `/api/{domain}/assignments/{assignment_id}/feedback` | Assignment feedback. |
| GET | `/api/topics/categories/stats` | Aggregate category stats (all silos). |

---

## 4. Intelligence and context-centric

All under `/api` unless noted.

### 4.1 Report and briefings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/report` | Domain report. |
| POST | `/api/products/generate_brief` | Generate brief. |
| POST | `/api/{domain}/intelligence/briefings/daily` | Daily briefing. |
| GET | `/api/products/daily_brief` | Get daily brief. |
| GET | `/api/products/weekly_digest` | Weekly digest. |
| GET | `/api/products/alert_digest` | Alert digest. |
| GET | `/api/{domain}/intelligence/briefing_feed` | Briefing feed. |
| POST | `/api/{domain}/intelligence/feedback` | Briefing feedback. |

### 4.2 Synthesis

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/{domain}/synthesis/storyline/{storyline_id}` | Storyline synthesis. |
| GET | `/api/{domain}/synthesis/storyline/{storyline_id}/markdown` | Markdown. |
| POST | `/api/{domain}/synthesis/topic` | Topic synthesis. |
| GET | `/api/{domain}/synthesis/breaking` | Breaking synthesis. |
| POST | `/api/{domain}/synthesis/storylines/bulk` | Bulk storyline synthesis. |
| GET | `/api/synthesis/domain` | Domain synthesis (context_centric). |
| GET | `/api/synthesis/storyline/{storyline_id}` | Storyline synthesis (context_centric). |
| GET | `/api/synthesis/event/{event_id}` | Event synthesis. |
| GET | `/api/synthesis/entity/{entity_id}` | Entity synthesis. |

### 4.3 Context-centric (entities, events, contexts, verification)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/context_centric/sync_entity_profiles` | Sync entity profiles. |
| POST | `/api/context_centric/sync_contexts` | Sync contexts. |
| POST | `/api/context_centric/run_enhancement_cycle` | Run enhancement cycle. |
| GET | `/api/context_centric/status` | Pipeline status. |
| GET | `/api/entity_profiles` | List entity profiles. |
| GET | `/api/entity_profiles/{profile_id}` | Get profile. |
| PATCH | `/api/entity_profiles/{profile_id}` | Update profile. |
| GET | `/api/contexts` | List contexts. |
| GET | `/api/contexts/{context_id}` | Get context. |
| GET | `/api/tracked_events` | List tracked events. |
| POST | `/api/tracked_events` | Create event. |
| PUT | `/api/tracked_events/{event_id}` | Update event. |
| GET | `/api/tracked_events/{event_id}/report` | Event report. |
| POST | `/api/tracked_events/{event_id}/chronicles/update` | Update chronicles. |
| GET | `/api/entity_dossiers` | List dossiers. |
| POST | `/api/entity_dossiers/compile` | Compile dossier. |
| GET | `/api/entity_positions` | Entity positions. |
| POST | `/api/entity_positions/extract` | Extract positions. |
| GET | `/api/processed_documents` | List processed documents. |
| GET | `/api/processed_documents/{document_id}` | Get document. |
| POST | `/api/processed_documents` | Create/ingest document. |
| POST | `/api/processed_documents/{document_id}/process` | Process document. |
| GET | `/api/pattern_discoveries` | Pattern discoveries. |
| GET | `/api/narrative_threads` | Narrative threads. |
| POST | `/api/narrative_threads/build` | Build threads. |
| GET | `/api/claims` | List claims. |
| POST | `/api/entities/resolve` | Resolve entity. |
| GET | `/api/entities/canonical` | List canonical entities. |
| GET | `/api/entities/merge_candidates` | Merge candidates. |
| POST | `/api/entities/merge` | Merge entities. |
| POST | `/api/entities/auto_merge` | Auto-merge. |
| POST | `/api/entities/cross_domain_link` | Cross-domain link. |
| POST | `/api/verification/claim/{claim_id}` | Verify claim. |
| POST | `/api/verification/corroborate` | Corroborate. |
| GET | `/api/verification/contradictions` | Contradictions. |
| POST | `/api/verification/batch` | Batch verification. |
| GET | `/api/verification/source_reliability` | Source reliability. |
| POST | `/api/context_centric/cleanup` | Run intelligence cleanup. |

### 4.4 RAG and intelligence hub

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/{domain}/rag/query` | RAG query. |
| GET | `/api/{domain}/rag/quick` | Quick RAG. |
| POST | `/api/{domain}/rag/storyline/{storyline_id}/analyze` | Storyline RAG. |
| GET | `/api/{domain}/rag/entity/{entity_name}` | Entity RAG. |
| POST | `/api/rag/cross-domain` | Cross-domain RAG. |
| GET | `/api/intelligence_hub/health` | Hub health. |
| GET | `/api/intelligence_hub/insights` | Insights. |
| POST | `/api/intelligence_hub/insights/generate` | Generate insights. |
| GET | `/api/intelligence_hub/trends` | Trends. |
| GET | `/api/{domain}/intelligence/dashboard` | Intelligence dashboard. |
| GET | `/api/{domain}/intelligence/quality/{storyline_id}` | Quality. |
| GET | `/api/{domain}/intelligence/anomalies` | Anomalies. |

### 4.5 Cross-domain (`/api/intelligence`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/intelligence/cross_domain_synthesis` | Cross-domain synthesis. |
| GET | `/api/intelligence/cross_domain_correlations` | Correlations. |
| GET | `/api/intelligence/meta_storylines` | Meta storylines. |
| GET | `/api/intelligence/unified_timeline` | Unified timeline. |
| POST | `/api/intelligence/extract_relationships` | Extract relationships. |
| GET | `/api/intelligence/predictions/{domain}` | Predictions. |
| GET | `/api/intelligence/network_graph/{domain}/{entity_id}` | Network graph. |

### 4.6 Quality and enrichment

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/quality/claim_feedback` | Claim feedback. |
| POST | `/api/quality/event_validation` | Event validation. |
| GET | `/api/quality/extraction_metrics` | Extraction metrics. |
| GET | `/api/quality/source_rankings` | Source rankings. |
| POST | `/api/enrich_entity` | Enrich entity. |
| POST | `/api/verify_claim` | Verify claim. |

---

## 5. Finance (`/api`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/{domain}/finance/tasks` | List tasks. |
| GET | `/api/{domain}/finance/tasks/{task_id}` | Task status/result. |
| GET | `/api/{domain}/finance/evidence` | Evidence index. |
| GET | `/api/{domain}/finance/evidence/preview` | Evidence preview. |
| GET | `/api/{domain}/finance/verification` | Verification history. |
| GET | `/api/{domain}/finance/trace/{task_id}` | Task trace. |
| GET | `/api/{domain}/finance/schedule` | Schedule status. |
| GET | `/api/{domain}/finance/sources/status` | Source health. |
| GET | `/api/{domain}/finance/market-data` | Market data. |
| GET | `/api/{domain}/finance/gold` | Gold amalgam. |
| POST | `/api/{domain}/finance/gold/fetch` | Fetch gold. |
| GET | `/api/{domain}/finance/gold/spot` | Gold spot. |
| GET | `/api/{domain}/finance/commodity/{commodity}/history` | Commodity history. |
| GET | `/api/{domain}/finance/commodity/{commodity}/spot` | Commodity spot. |
| POST | `/api/{domain}/finance/edgar/ingest` | EDGAR ingest. |
| POST | `/api/{domain}/finance/analyze` | Submit analysis. |
| GET | `/api/{domain}/finance/research-topics` | Research topics. |
| POST | `/api/{domain}/finance/research-topics` | Create research topic. |
| GET | `/api/{domain}/finance/market-trends` | Market trends. |
| GET | `/api/{domain}/finance/market-patterns` | Market patterns. |
| GET | `/api/{domain}/finance/corporate-announcements` | Corporate announcements. |

---

## 6. System monitoring and orchestrator

### 6.1 System monitoring (`/api/system_monitoring`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system_monitoring/health` | Health check. |
| GET | `/api/system_monitoring/orchestrator` | Orchestrator status. |
| GET | `/api/system_monitoring/monitoring/overview` | Monitoring overview. |
| GET | `/api/system_monitoring/automation/status` | Automation status. |
| GET | `/api/system_monitoring/pipeline_status` | Pipeline status. |
| POST | `/api/system_monitoring/pipeline/trigger` | Trigger pipeline. |
| GET | `/api/system_monitoring/metrics` | Metrics. |
| GET | `/api/system_monitoring/alerts` | Alerts. |
| POST | `/api/system_monitoring/alerts/create` | Create alert. |
| GET | `/api/system_monitoring/dashboard` | Dashboard. |
| GET | `/api/system_monitoring/performance` | Performance. |
| GET | `/api/system_monitoring/fast_stats` | Fast stats. |
| GET | `/api/system_monitoring/sources_collected` | Sources collected. |
| POST | `/api/system_monitoring/monitoring/trigger_phase` | Trigger phase. |
| GET | `/api/system_monitoring/logs/realtime` | Realtime logs. |

### 6.2 Orchestrator (`/api/orchestrator`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/orchestrator/status` | Status. |
| GET | `/api/orchestrator/metrics` | Metrics. |
| GET | `/api/orchestrator/decision_log` | Decision log. |
| GET | `/api/orchestrator/dashboard` | Dashboard. |
| POST | `/api/orchestrator/manual_override` | Manual override. |

### 6.3 Route supervisor (`/api/system_monitoring/route_supervisor`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system_monitoring/route_supervisor/health` | Health. |
| GET | `/api/system_monitoring/route_supervisor/report` | Report. |
| GET | `/api/system_monitoring/route_supervisor/issues` | Issues. |
| POST | `/api/system_monitoring/route_supervisor/check_now` | Check now. |

---

## 7. User management (`/api/user_management`)

| Method | Path | Description |
|--------|------|-------------|
| (varies) | `/api/user_management/*` | User management endpoints. See `/docs`. |

---

## 8. Integrations

- **Frontend:** React app in `web/` uses `fetch`/axios to the API base URL. Domain is selected in the UI; API modules in `web/src/services/api/` build paths like `/api/${domain}/articles`. See [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md).
- **Proxying:** In development, Vite can proxy `/api` to the backend (e.g. port 8000).
- **Auth:** Currently no global auth layer; optional per-route or future gateway.
- **OpenAPI:** Full OpenAPI spec available at `/openapi.json`; interactive docs at `/docs` and `/redoc`.

---

## 9. Related docs

- [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) — Frontend–API connection and troubleshooting.
- [API_DESIGN_PRINCIPLES.md](_archive/retired_root_docs_2026_03/API_DESIGN_PRINCIPLES.md) — Response standards and narrative-first design (archived).
- [DOCS_INDEX.md](DOCS_INDEX.md) — Full documentation index.
