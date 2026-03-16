# Web UI vs Backend Feature Coverage

Assessment of whether the current web interface exposes the features we built (v6 quality-first). **Short answer:** The layout (Dashboard, Discover, Storylines, Briefings, Report, Investigate, Monitor, Analyze) **does** expose v6 intelligence: tracked events, entity resolution (canonical entities tab), processed documents, narrative threads, briefings, report, storylines, and monitor. **Gaps:** Articles/topics/RSS/watchlist and full pipeline/health are not in nav; content synthesis and fact verification are API-only (no dedicated UI).

**Related:** [PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md](PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md), [WEB_PRODUCT_DISPLAY_PLAN.md](WEB_PRODUCT_DISPLAY_PLAN.md).

---

## 1. Current UI (What’s Routed and in Nav)

| Route | Page | What it shows |
|-------|------|----------------|
| `/:domain/dashboard` | Dashboard | Context-centric: latest contexts, tracked events, context-centric status, orchestrator last collection. Links to context detail, event detail. |
| `/:domain/discover` | DiscoverPage | Contexts + entity profiles (tabs), context sync button. Links to context detail, entity detail. |
| `/:domain/discover/contexts/:id` | ContextDetailPage | Single context. |
| `/:domain/investigate` | InvestigatePage | Tracked events list. Buttons: Entities, Search. |
| `/:domain/investigate/events/:id` | EventDetailPage | Single tracked event. |
| `/:domain/investigate/entities` | EntitiesListPage | Entity profiles list. |
| `/:domain/investigate/entities/:id` | EntityDetailPage | Single entity profile. |
| `/:domain/investigate/search` | SearchPage | Search (contexts/entities). |
| `/:domain/monitor` | **MonitorPage** | Orchestrator last collection times + quality metrics (context/entity coverage). **No** pipeline trigger, **no** RSS update, **no** health/pipeline status. |
| `/:domain/analyze` | AnalyzePage | For finance: redirects to `/analysis`. For others: placeholder “planned for future”. |
| `/:domain/analysis` | FinancialAnalysis | Finance analysis submit (query → task). |
| `/:domain/analysis/:taskId` | FinancialAnalysisResult | Finance task result. Not in sidebar; reachable via Analyze (finance) or direct URL. |
| `/:domain/commodity/:commodity` | CommodityDashboard | Commodity (gold, etc.). Nav: “Commodity” (finance only). |

**Sidebar (AppNav):** Dashboard, Discover, Storylines, Briefings, Today's Report, Investigate, Monitor, Analyze, Commodity (finance only).

**v6 routes also in App.tsx:** `storylines`, `storylines/:id`, `briefings`, `report`, `investigate/documents`, `investigate/narrative-threads`. EntitiesListPage has **Canonical entities** tab (resolve, merge, aliases, cross-domain link). MonitorPage includes pipeline status and realtime monitoring.

---

## 2. Backend Features That Are Well Exposed

| Feature | Where in UI |
|---------|-------------|
| Context-centric status, contexts, entity profiles, tracked events | Dashboard, Discover, Investigate + detail pages |
| Context sync (backfill) | Discover (button) |
| Orchestrator collection status | Dashboard (card), Monitor (last collection times) |
| Quality metrics (context/entity coverage) | Monitor |
| Finance analysis (submit → poll → result) | Analyze (finance) → analysis, analysis/:taskId |
| Commodity dashboard | Commodity nav (finance) |
| Domain switcher | MainLayout (top right) |

---

## 3. Backend Features Not (or Barely) Exposed

### 3.1 No route / no nav

| Backend feature | API / capability | Current UI |
|-----------------|------------------|------------|
| **Articles** (list, detail, filtered, dedup) | `/api/{domain}/articles`, storylines, dedup | No route. Old routes were `articles`, `articles/:id`, `articles/duplicates`, `articles/filtered`. |
| **Storylines** (list, discovery, consolidation, detail, synthesis, timeline) | `/api/{domain}/storylines`, discovery, consolidation, timeline | No route. Pages exist: Storylines, StorylineDiscovery, ConsolidationPanel, StoryDetail, SynthesizedView, StoryTimeline. |
| **Topics** (list, topic articles) | `/api/{domain}/content_analysis/topics`, topic articles | No route. Pages: Topics, TopicArticles. |
| **RSS Feeds** (list, CRUD, duplicate manager) | `/api/{domain}/rss_feeds`, collect_now, duplicates | No route. Pages: RSSFeeds, RSSDuplicateManager. |
| **Watchlist** (watchlist + alerts) | `/api/{domain}/storylines/watchlist`, watchlist alerts | No route. Page: Watchlist. |
| **Briefings** | Intelligence/briefings API | No route. Page: Briefings. |
| **Intelligence RAG** (domain RAG query) | RAG/synthesis APIs | No route. Page: DomainRAG. |
| **Events** (as hub list) | Tracked events (we have in Investigate) | Events hub page exists but not routed. |
| **ML Processing** (queue, status) | LLM/topic queue, ML status | No route. Page: MLProcessing. |
| **Story control dashboard** | Storyline automation, controls | No route. Page: StoryControlDashboard. |
| **Full system monitoring** | Health, pipeline status/trigger, RSS trigger, orchestrator, DB stats, alerts | **Monitoring.tsx** has pipeline trigger, RSS update, health, traces, etc. It is **not** mounted in App.tsx. Only **MonitorPage** is at `monitor` (collection + quality). |
| **Finance: Evidence Explorer** | Evidence preview, ledger | No route. Page: EvidenceExplorer. |
| **Finance: Source Health** | Source health API | No route. Page: SourceHealth. |
| **Finance: Refresh Schedule** | Schedule API | No route. Page: RefreshSchedule. |
| **Finance: Fact Check** | Fact-check / verification | No route. Page: FactCheckViewer. |
| **Finance: Market Research / Corporate / Market Patterns** | Market research, corporate, patterns APIs | No route. Pages: MarketResearch, CorporateAnnouncements, MarketPatterns. |
| **Finance: Task Trace** | Task trace viewer | No route. Page: TaskTraceViewer (trace/:taskId). |
| **Context-centric status (dedicated)** | Run enhancement, entity enrichment, pattern matching, cleanup | Dashboard shows status; no dedicated “Context-centric” admin page with run buttons. |
| **Settings** | User/settings | No route. Page: Settings. |

### 3.2 In nav but minimal

| Item | Gap |
|------|-----|
| **Monitor** | No pipeline trigger, no “Update RSS”, no health/pipeline status. Full **Monitoring.tsx** exists but is not used. |
| **Analyze** (non-finance) | Placeholder only; no trend/network/report UI. |

---

## 4. Recommendations: Highlight All Built Features

### 4.1 Quick wins (one route or nav change)

1. **Use full Monitoring page at `/monitor`**  
   In `App.tsx`, render the existing **Monitoring** component (from `pages/Monitoring/Monitoring.tsx`) for `path="monitor"` instead of **MonitorPage**. That restores pipeline trigger, RSS update, health, pipeline status, and orchestrator in one step.

2. **Add “System” or “Monitoring” to nav**  
   If you prefer to keep the light MonitorPage as “Monitor”, add a second item (e.g. “System” or “Pipeline”) that routes to the full Monitoring page so both “collection/quality” and “pipeline/health/actions” are available.

### 4.2 Add routes and nav for content and intelligence

3. **Articles**  
   Add routes: `articles`, `articles/:id`, `articles/duplicates`, `articles/filtered` and point to existing Articles, ArticleDetail, ArticleDeduplicationManager, FilteredArticles. Add a “Content” or “Articles” section in the sidebar (or under Discover as “Articles”).

4. **Storylines**  
   Add routes: `storylines`, `storylines/discover`, `storylines/consolidation`, `storylines/:id`, `storylines/:id/synthesis`, `storylines/:id/timeline` and use existing Storylines, StorylineDiscovery, ConsolidationPanel, StoryDetail, SynthesizedView, StoryTimeline. Add “Storylines” to the nav.

5. **Topics**  
   Add routes: `topics`, `topics/:topicName` (TopicArticles). Add “Topics” to the nav or under Discover.

6. **RSS Feeds**  
   Add routes: `rss-feeds`, `rss-feeds/duplicates`. Add “RSS Feeds” (or “Feeds”) to the nav, e.g. under Monitor or as its own item.

7. **Watchlist**  
   Add route: `watchlist` and use existing Watchlist page. Link from Dashboard or add “Watchlist” to the nav.

8. **Briefings / RAG**  
   Add routes for Briefings and DomainRAG (e.g. `briefings`, `rag`) or group under “Intelligence” with sub-routes. Link from Dashboard or Analyze.

9. **ML Processing**  
   Add route: `ml-processing` for MLProcessing page. Optional nav item or link from Monitor.

10. **Story control**  
    Add route: `story-management` for StoryControlDashboard. Optional or under Storylines.

### 4.3 Finance sub-pages

11. **Finance-specific routes** (under finance domain)  
    Add: `evidence`, `sources`, `schedule`, `fact-check`, `market-research`, `corporate-announcements`, `market-patterns`, `trace/:taskId`. Use existing EvidenceExplorer, SourceHealth, RefreshSchedule, FactCheckViewer, MarketResearch, CorporateAnnouncements, MarketPatterns, TaskTraceViewer. Add a “Finance” submenu or a second row of links on the finance Analyze/Commodity pages.

### 4.4 Context-centric and settings

12. **Context-centric admin**  
    Optional dedicated page (or section on Monitor) with buttons for: run enhancement cycle, run entity enrichment, run pattern matching, run story state triggers, cleanup. These APIs exist; the Dashboard shows status but not run actions.

13. **Settings**  
    Add route `settings` and link from header or nav if user/settings are in scope.

---

## 5. Summary Table

| Area | Backend | Current UI | Suggested change |
|------|---------|------------|-------------------|
| Context-centric (contexts, entities, events, status) | ✅ | ✅ Dashboard, Discover, Investigate | — |
| Orchestrator (collection status) | ✅ | ✅ Dashboard, Monitor | — |
| Pipeline trigger, RSS trigger, health | ✅ | ❌ (full Monitoring.tsx not routed) | Use Monitoring at `monitor` or add “System” route |
| Articles, storylines, topics, RSS feeds | ✅ | ❌ No routes | Add routes + nav (Content / Storylines / Topics / Feeds) |
| Watchlist, briefings, RAG | ✅ | ❌ No routes | Add routes + nav or links from Dashboard |
| ML Processing, Story control | ✅ | ❌ No routes | Add routes (optional nav) |
| Finance analysis, commodity | ✅ | ✅ Analyze, Commodity | — |
| Finance evidence, sources, schedule, fact-check, market/corporate/patterns, trace | ✅ | ❌ No routes | Add finance sub-routes + links |
| Context-centric run actions | ✅ | Status only | Optional admin page or Monitor section |
| Settings | ✅ | ❌ No route | Add route if needed |

Implementing **§4.1** (full Monitoring at `monitor` or a “System” route) plus **§4.2** (articles, storylines, topics, RSS, watchlist, briefings/RAG) would make the UI align with what’s built and give a single place to operate and see all major features.
