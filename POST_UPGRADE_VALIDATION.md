# Post-Upgrade Validation Report (v4 -> canonical)

Date: 2025-10-30

## Overview
- Database: legacy tables dropped; `_v4` tables renamed to canonical (e.g., `articles`, `rss_feeds`).
- API: Routes updated to match schema; removed legacy column/table references.
- Frontend: All pages now call `/api/v4/...` via `apiService`/`api` with correct response mappings.

## Backend Endpoints (key)
- News Aggregation:
  - GET `/api/v4/news-aggregation/rss-feeds` (200)
  - GET `/api/v4/news-aggregation/articles/recent` (200)
- Storyline Management:
  - GET `/api/v4/storyline-management/storylines` (200)
  - POST `/api/v4/storyline-management/storylines` (200)
  - POST `/api/v4/storyline-management/storylines/{id}/add-article` (200)
- Content Analysis:
  - GET `/api/v4/content-analysis/articles` (200)
  - GET `/api/v4/content-analysis/topics/word-cloud` (200)
  - GET `/api/v4/content-analysis/topics/big-picture` (200)
  - GET `/api/v4/content-analysis/topics/trending` (200)
  - GET `/api/v4/content-analysis/topics/{topic_name}/summary` (200)
- System Monitoring:
  - GET `/api/v4/system-monitoring/health` (200)
  - GET `/api/v4/system-monitoring/metrics` (200)
  - GET `/api/v4/system-monitoring/status` (200)

## Schema Notes (canonical)
- `topic_clusters(topic_name)` used; removed references to `cluster_name`, `cluster_type`, `is_active`.
- `article_topics(article_id, topic_id, relevance_score)` used; removed `topic_cluster_id`.
- `pipeline_traces` uses `start_time/end_time`; monitoring queries updated from `created_at`.
- `intelligence_insights` includes `insight_title`, `insight_description`, `insight_data`, `confidence_score`, `relevance_score`, `expires_at`.

## Frontend Wiring
- `apiService.ts`: base URL `http://localhost:8000`; all methods use `/api/v4/...`.
- Pages updated:
  - `Dashboard/UnifiedDashboard.js`: v4 endpoints, normalized shapes, recent activity fixed.
  - `Storylines/Storylines.tsx`, `Storylines/StorylineDashboard.js`, `components/StorylineCreationDialog.js`, `components/ArticleReader.js`, `Storylines/SimpleStorylineReport.js`.
  - `RSSFeeds/RSSFeeds.tsx`: maps `feed_name/feed_url/last_fetched_at` to UI.
  - `Intelligence/IntelligenceHub.js`: uses v4 topic endpoints and normalized data.
  - `Monitoring/ResourceDashboard.js`, `Debug/DebugAPI.js`, `AdvancedMonitoring/AdvancedMonitoring.js` reference v4.

## Evidence (live checks)
- API responses (200): storylines, rss_feeds, recent articles, metrics, topics word-cloud/big-picture/trending.
- UI snapshots saved (HTML):
  - `logs/ui_snapshots_index.html`
  - `logs/ui_snapshots_rss.html`
  - `logs/ui_snapshots_intelligence.html`
  - `logs/ui_snapshots_storylines.html`
  - `logs/ui_snapshots_monitoring.html`
  - `logs/ui_snapshots_dashboard.html`

## Remaining Items
- None blocking. Optional: Enhance category derivation for topics (no `cluster_type`).

## Conclusion
System upgraded and fully wired end-to-end. API and UI verified against canonical schema; no temporary stubs remain.
