# News Intelligence System — Web Interface Summary for Claude

**Purpose:** Shareable reference for AI assistants (Claude) working with the React/HTML frontend.  
**Last Updated:** 2025-02-27  
**Project Version:** 4.0

---

## 1. Overview

**News Intelligence System** is an AI-powered news aggregation and analysis platform. The web interface is a **React 18 + TypeScript + Vite** SPA that provides:

- Multi-domain news analysis (politics, finance, science-tech)
- Article collection, processing, and storyline tracking
- RSS feed management
- Intelligence hub with AI insights, briefings, RAG, and watchlist
- System monitoring and ML pipeline control

**Default entry:** `/` redirects to `/politics/dashboard`.

---

## 2. Tech Stack

| Category | Technology |
|----------|------------|
| Framework | React 18 |
| Language | TypeScript (migration ongoing; some `.jsx` remain) |
| Build | Vite 7 |
| Routing | react-router-dom v6 |
| UI Library | Material-UI (MUI) v5 |
| Charts | Recharts, MUI X Charts, D3 |
| HTTP | Axios |
| State | Zustand (limited), React Context |
| API | REST via `/api/v4/{domain}/{resource}` |

**Key dependencies:**
- `@mui/material`, `@mui/icons-material`, `@mui/x-data-grid`, `@mui/x-charts`
- `react-markdown` + `remark-gfm` for markdown
- `date-fns` for dates

---

## 3. Entry Points & HTML

| File | Purpose |
|------|---------|
| `web/index.html` | Root HTML: loads `#root`, script `/src/index.tsx` |
| `web/src/index.tsx` | Renders `<App />` in `React.StrictMode` |
| `web/src/App.tsx` | Root component: theme, domain provider, router, layout |

**index.html** (main shell):
- Single-page app shell
- `<div id="root"></div>`
- Script: `type="module" src="/src/index.tsx"`
- Meta: viewport, theme-color, PWA manifest

**Archived HTML:**  
`api/_archived/index.html` — legacy bundled SPA (140K+ chars); not used in active build.

---

## 4. Architecture: Domain-Based Routing

Routes follow `/:domain/*`. Domains: **politics**, **finance**, **science-tech**.

### Routing Layout

```
App.tsx
├── ThemeProvider (MUI light theme)
├── DomainProvider (context)
└── Router
    ├── Header
    ├── Navigation (sidebar)
    ├── main
    │   ├── / → redirect to /politics/dashboard
    │   ├── /monitoring
    │   ├── /settings
    │   ├── /test-storyline-management
    │   ├── Legacy redirects (e.g. /dashboard → /politics/dashboard)
    │   └── /:domain/* → DomainLayout (nested routes)
    └── Footer
```

### DomainLayout (`web/src/components/shared/DomainLayout/DomainLayout.tsx`)

- Validates `domain` URL param and syncs with `DomainContext`
- Wraps routes in `DomainRouteGuard`
- Renders nested `Routes` under `/:domain/*`

### DomainContext (`web/src/contexts/DomainContext.tsx`)

- Provides `domain`, `setDomain`, `availableDomains`, `domainName`
- Persists domain to `localStorage`
- Dispatches `domainChanged` custom event

### useDomainRoute Hook (`web/src/hooks/useDomainRoute.ts`)

- Returns `domain`, `getDomainPath(path)`, `isInDomain(domainKey)`
- Used for domain-aware links and active-state logic

---

## 5. Routes (Domain Layout)

All under `/:domain/` except where noted.

| Path | Page Component | Purpose |
|------|----------------|---------|
| `dashboard` | Dashboard | Domain overview, stats, recent activity |
| `articles` | Articles | Article list, filters, management |
| `articles/:id` | ArticleDetail | Article viewer, reader |
| `articles/duplicates` | ArticleDeduplicationManager | Duplicate detection/merge |
| `articles/filtered` | FilteredArticles | Filtered article views |
| `storylines` | Storylines | Storyline list |
| `storylines/discover` | StorylineDiscovery | RAG-based discovery |
| `storylines/consolidation` | ConsolidationPanel | Storyline consolidation UI |
| `storylines/:id` | StorylineDetail | Single storyline |
| `storylines/:id/synthesis` | SynthesizedView | AI synthesis view |
| `storylines/:id/timeline` | StoryTimeline | Timeline view |
| `topics` | Topics | Topic list |
| `topics/:topicName` | TopicArticles | Articles per topic |
| `rss-feeds` | RSSFeeds | RSS feed management |
| `rss-feeds/duplicates` | RSSDuplicateManager | RSS duplicate handling |
| `intelligence` | IntelligenceHub | Main intelligence hub |
| `intelligence/analysis` | IntelligenceAnalysis | AI analysis views |
| `intelligence/rag` | DomainRAG | Domain RAG interface |
| `intelligence/tracking` | StorylineTracking | Storyline tracking |
| `intelligence/briefings` | Briefings | Briefings |
| `intelligence/events` | Events | Events |
| `intelligence/watchlist` | Watchlist | Watchlist |
| `ml-processing` | MLProcessing | ML pipeline control |
| `story-management` | StoryControlDashboard | Story control panel |

**Finance-only routes (within finance domain):**

| Path | Page | Purpose |
|------|------|---------|
| `market-research` | MarketResearch | Market research |
| `corporate-announcements` | CorporateAnnouncements | Corporate news |
| `market-patterns` | MarketPatterns | Market patterns |

**Domain-agnostic (no domain prefix):**

| Path | Page |
|------|------|
| `/monitoring` | Monitoring |
| `/settings` | Settings |
| `/test-storyline-management` | StorylineManagementTest |

---

## 6. Pages Inventory

**Location:** `web/src/pages/`

| Page | File | Notes |
|------|------|-------|
| Dashboard | Dashboard/Dashboard.tsx | Domain stats, cards, recent activity |
| Articles | Articles/Articles.tsx | Main list |
| ArticleDetail | Articles/ArticleDetail.jsx | Reader |
| ArticleDeduplicationManager | Articles/ArticleDeduplicationManager.jsx | Dedup UI |
| FilteredArticles | FilteredArticles/FilteredArticles.tsx | Filtered views |
| Storylines | Storylines/Storylines.tsx | List |
| StorylineDetail | Storylines/StorylineDetail.jsx | Detail/synthesis |
| StorylineDiscovery | Storylines/StorylineDiscovery.jsx | Discovery |
| SynthesizedView | Storylines/SynthesizedView.jsx | Synthesis |
| ConsolidationPanel | Storylines/ConsolidationPanel.jsx (in components) | Consolidation |
| StoryTimeline | StoryTimeline/StoryTimeline.tsx | Timeline |
| Topics | Topics/Topics.tsx | Topic list |
| TopicArticles | Topics/TopicArticles.jsx | Per-topic articles |
| TopicManagement | Topics/TopicManagement.jsx | Topic management |
| RSSFeeds | RSSFeeds/RSSFeeds.tsx | Feed management |
| RSSDuplicateManager | RSSFeeds/RSSDuplicateManager.jsx | RSS duplicates |
| IntelligenceHub | Intelligence/IntelligenceHub.jsx | Hub |
| IntelligenceAnalysis | Intelligence/IntelligenceAnalysis.jsx | Analysis |
| DomainRAG | Intelligence/DomainRAG.jsx | RAG |
| StorylineTracking | StorylineTracking/StorylineTracking.tsx | Tracking |
| Briefings | Briefings/Briefings.tsx | Briefings |
| Events | Events/Events.tsx | Events |
| Watchlist | Watchlist/Watchlist.tsx | Watchlist |
| MLProcessing | MLProcessing/MLProcessing.tsx | ML pipeline |
| StoryControlDashboard | StoryManagement/StoryControlDashboard.tsx | Story control |
| Monitoring | Monitoring/Monitoring.tsx | System monitoring |
| Settings | Settings/Settings.tsx | Settings |

**Finance domain pages:** `web/src/domains/Finance/`  
- MarketResearch/MarketResearch.tsx  
- CorporateAnnouncements/CorporateAnnouncements.tsx  
- MarketPatterns/MarketPatterns.tsx  

---

## 7. Components Inventory

**Location:** `web/src/components/`

### Layout & Structure

| Component | File | Purpose |
|-----------|------|---------|
| DomainLayout | shared/DomainLayout/DomainLayout.tsx | Wraps domain routes |
| DomainRouteGuard | shared/DomainRouteGuard/DomainRouteGuard.tsx | Route guard |
| DomainBreadcrumb | shared/DomainBreadcrumb/DomainBreadcrumb.tsx | Breadcrumbs |
| DomainIndicator | shared/DomainIndicator/DomainIndicator.tsx | Domain label |
| LegacyRedirect | shared/LegacyRedirect/LegacyRedirect.tsx | Legacy route redirects |
| Header | Header/Header.tsx | Top bar, domain chip, API status |
| Footer | Footer/Footer.tsx | Footer |
| Navigation | Navigation/Navigation.tsx | Sidebar nav |
| DomainSelector | DomainSelector/DomainSelector.tsx | Domain switcher |

### Shared UI

| Component | File | Purpose |
|-----------|------|---------|
| EmptyState | shared/EmptyState.tsx | Empty-state placeholder |
| LoadingState | shared/LoadingState.tsx | Loading placeholder |
| ErrorBoundary | ErrorBoundary/ErrorBoundary.tsx | Error boundary |
| APIConnectionStatus | APIConnectionStatus/APIConnectionStatus.tsx | API status display |

### Feature Components

| Component | File | Purpose |
|-----------|------|---------|
| ArticleReader | ArticleReader.jsx | Article display |
| ArticleTopics | ArticleTopics/ArticleTopics.jsx | Topics for article |
| StorylineCreationDialog | StorylineCreationDialog.jsx | Create storyline |
| StorylineConfirmationDialog | StorylineConfirmationDialog.jsx | Confirm storyline actions |
| StorylineManagementDialog | StorylineManagementDialog.jsx | Manage storyline |
| StorylineAutomationDialog | StorylineAutomationDialog.jsx | Automation config |
| ArticleSuggestionsDialog | ArticleSuggestionsDialog.jsx | Article suggestions |
| RealtimeMonitor | Monitoring/RealtimeMonitor.tsx | Realtime monitoring |
| SystemAnalytics | Analytics/SystemAnalytics.tsx | System analytics |
| NotificationSystem | Notifications/NotificationSystem.jsx | Notifications |
| StorylineManagementTest | StorylineManagementTest.jsx | Dev/test UI |

---

## 8. API Service Layer

**Location:** `web/src/services/`

### API Modules (`web/src/services/api/`)

| Module | File | Domain-scoped | Purpose |
|--------|------|---------------|---------|
| articlesApi | articles.ts | Yes | Articles CRUD, search |
| storylinesApi | storylines.ts | Yes | Storylines, timeline |
| topicsApi | topics.ts | Yes | Topics |
| rssApi | rss.ts | Yes | RSS feeds |
| intelligenceApi | intelligence.ts | Yes | Intelligence endpoints |
| watchlistApi | watchlist.ts | No | Watchlist, alerts |
| monitoringApi | monitoring.ts | No | System monitoring |

### API Client (`web/src/services/api/client.ts`)

- `getApi()` — returns Axios instance with domain-aware base URL
- `getCurrentDomain()` — current domain from helper
- Base URL pattern: `/api/v4/{domain}/...` (domain from `getCurrentDomain()`)

### Other Services

| Service | File | Purpose |
|---------|------|---------|
| apiService | apiService.ts | Legacy/combined API layer |
| apiConnectionManager | apiConnectionManager.ts | Connection health, retries |
| frontendHealthService | frontendHealthService.ts | Frontend health reporting |
| loggingService | loggingService.ts | Centralized logging |
| errorHandler | errorHandler.ts | Error handling |

### API Config (`web/src/config/apiConfig.ts`)

- Base URL: `VITE_API_URL` or `localStorage` `news_intelligence_api_url`, fallback `''` (proxy)
- Timeout: `VITE_API_TIMEOUT` or 30000
- Health: `/api/v4/system_monitoring/health`

---

## 9. Styling

**Approach:** MUI theme + component-specific CSS.

### Theme (App.tsx)

- `createTheme` with `mode: 'light'`
- Palette: primary `#1976d2`, secondary `#9c27b0`, error/warning/info/success

### CSS Files

| File | Scope |
|------|-------|
| src/index.css | Global |
| src/App.css | App container |
| components/Navigation/Navigation.css | Sidebar |
| components/Header/Header.css | Header |
| components/Footer/Footer.css | Footer |
| components/DomainSelector/DomainSelector.css | Domain selector |
| pages/Dashboard/Dashboard.css | Dashboard |
| pages/Articles/Articles.css | Articles |
| pages/Storylines/Storylines.css | Storylines |
| pages/RSSFeeds/RSSFeeds.css | RSS Feeds |
| pages/Settings/Settings.css | Settings |
| pages/Monitoring/Monitoring.css | Monitoring |
| pages/Intelligence/Intelligence.css | Intelligence |
| pages/StorylineTracking/StorylineTracking.css | Storyline tracking |

---

## 10. Types (TypeScript)

**Location:** `web/src/types/`

- `index.ts` — Main exports (Article, Storyline, RSSFeed, APIResponse, etc.)
- `api.ts` — API types
- `components.ts` — Component prop types
- `utils.ts` — Utility types

**Notable types:** `Article`, `Storyline`, `TimelineEvent`, `RSSFeed`, `DashboardData`, `IntelligenceInsight`, `APIResponse<T>`, `PaginatedResponse<T>`, `SearchParams`, `SearchResult`.

---

## 11. Hooks

| Hook | File | Purpose |
|------|------|---------|
| useDomain | contexts/DomainContext | Domain context (via context) |
| useDomainRoute | hooks/useDomainRoute.ts | Domain path helpers |
| useDomainNavigation | hooks/useDomainNavigation.ts | Domain-aware navigation |
| useNotification | hooks/useNotification.tsx | Notification handling |

---

## 12. Utils

| File | Purpose |
|------|---------|
| logger.ts | Central logging (use instead of console) |
| domainHelper.ts | Domain validation, `AVAILABLE_DOMAINS`, `getCurrentDomain` |
| errorHandler.ts | Error handling |
| debugHelper.ts | Dev debug init |
| featureTestHelper.ts | Feature test init |
| articleUtils.js | Article helpers |

---

## 13. Build & Development

**Vite config:** `web/vite.config.mts`

- Port: 3000
- Proxy: `/api` → `http://localhost:8000`
- Path aliases: `@`, `@components`, `@pages`, `@services`, `@utils`, `@types`
- Build: `dist/`, sourcemaps, manual chunks (vendor, mui)

**Scripts:**
- `npm run dev` / `npm start` — Vite dev server
- `npm run build` — `tsc && vite build`
- `npm run lint`, `npm run format`, `npm run style:check` — Lint/format

---

## 14. Frontend Conventions (from FRONTEND_STYLE_GUIDE.md)

- **Logging:** Use `Logger` (from `utils/logger.ts`), not `console.log`
- **Components:** Prefer arrow functions
- **Imports:** React → third-party → local
- **New code:** Prefer TypeScript (`.tsx`/`.ts`)
- **Naming:** PascalCase for components; align with project terminology (storylines, domains, etc.)

---

## 15. Terminology (Use Consistently)

| Concept | Use | Avoid |
|---------|-----|-------|
| Evolving clusters | **storylines** | stories, threads |
| Per-domain silos | **domains** | sections, buckets |
| Domain keys | **politics**, **finance**, **science-tech** | Politics, FINANCE |
| Feed storage | **rss_feeds** | rssFeeds |
| API version | **v4** or **api/v4** | v1, v2, v3 |

---

## 16. File Count Summary

- **Pages:** ~30 (including domain-specific)
- **Components:** ~25+
- **Services:** 7 API modules + support services
- **CSS files:** 14
- **Type definitions:** 4 type files

---

## 17. Related Documentation

- `News Intelligence/AGENTS.md` — Agent guidance
- `News Intelligence/docs/CODING_STYLE_GUIDE.md` — Coding standards
- `News Intelligence/docs/ARCHITECTURAL_STANDARDS.md` — Architecture
- `News Intelligence/web/FRONTEND_STYLE_GUIDE.md` — Frontend style
- `News Intelligence/.cursor/rules/news-intelligence-project.mdc` — Project context
- `News Intelligence/.cursor/rules/reuse-before-create.mdc` — Reuse rules

---

*This document is intended as a portable reference for AI assistants working with the News Intelligence web interface. Update as the codebase evolves.*
