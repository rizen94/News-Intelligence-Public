# Web Product Display Plan: Intelligence Dashboard

**Audience:** Individual investigative analyst (primary); trusted colleagues (future).  
**Goal:** One place to see what’s happening, system health, contexts that need attention, and tools to investigate entities and stories.

---

## Audience & Goals

### Primary User Profile

```yaml
user_type: Individual Investigative Analyst (You)
needs:
  immediate:
    - What's happening now?
    - Is my system healthy?
    - What contexts need attention?

  investigation:
    - Deep dive into entities
    - Track developing stories
    - Connect hidden relationships

  operational:
    - Monitor collection health
    - Adjust tracking priorities
    - Export/share findings
```

### Secondary Users (Future)

```yaml
trusted_colleagues:
  - Share specific investigations
  - Collaborative context building
  - Controlled access to findings
```

---

## Landing Dashboard Design

### Hero Status Bar

```yaml
layout: Full width, always visible
components:

  system_health:
    position: Top left
    display: "●" with color (green/yellow/red)
    shows:
      - Orchestrator status
      - Active collections: "23 sources active"
      - Pipeline health: "2.3k articles/hour"

  quick_stats:
    position: Center
    display: Key metrics row
    shows:
      - Total contexts: 14,523
      - Active entities: 3,421
      - Today's events: 234
      - Priority alerts: 7

  time_context:
    position: Top right
    display: "Last update: 2 min ago"
    shows:
      - Collection freshness
      - Time filter toggle
```

### Main Dashboard Grid (3 columns)

```yaml
left_column: "What's New"
  components:
    latest_contexts:
      - Shows 10 most recent contexts
      - Mini cards with: headline, entities, confidence
      - Click → Context detail page

    trending_entities:
      - Top 5 entities by mention velocity
      - Sparkline showing 24h trend
      - Click → Entity profile

middle_column: "Active Investigations"
  components:
    tracked_events:
      - Your manually flagged events
      - Status: developing/stale/resolved
      - Quick notes field

    watched_entities:
      - Priority entities you're monitoring
      - Recent activity indicator
      - Relationship warnings

right_column: "System Intelligence"
  components:
    collection_status:
      - Source by source health
      - Articles collected today
      - Error/warning indicators

    pipeline_metrics:
      - Context extraction rate
      - Confidence distribution
      - Processing backlog
```

---

## Navigation Architecture

### Primary Navigation Bar

```yaml
structure:
  logo: "NewsIntel" (click → dashboard)

  main_sections:
    discover:
      label: "Discover"
      icon: compass
      subsections:
        - Latest Contexts
        - Entity Browser
        - Event Timeline
        - Relationship Map

    investigate:
      label: "Investigate"
      icon: magnifying-glass
      subsections:
        - Tracked Events
        - Entity Profiles
        - Context Search
        - Pattern Analysis

    monitor:
      label: "Monitor"
      icon: radar
      subsections:
        - Collection Watch
        - Source Health
        - Alert Config
        - Quality Metrics

    analyze:
      label: "Analyze"
      icon: chart
      subsections:
        - Trend Analysis
        - Network Graphs
        - Timeline Builder
        - Report Generator
```

### Context-Centric Page Templates

#### Entity Profile Page

```yaml
url_pattern: /entity/{entity_id}  # or /:domain/intelligence/entity-profiles/:id (current)
layout:

  header:
    - Entity name (with aliases)
    - Entity type & confidence
    - Quick stats (first seen, mention count)
    - Action buttons: Track/Untrack, Export, Share

  main_content:
    tab_1_timeline:
      - Chronological context appearances
      - Filterable by source, confidence
      - Expandable context cards

    tab_2_relationships:
      - Network graph of connected entities
      - Relationship strength indicators
      - Co-occurrence patterns

    tab_3_analysis:
      - Sentiment over time
      - Topic associations
      - Geographic presence
      - Source distribution
```

#### Context Detail Page

```yaml
url_pattern: /context/{context_id}  # to be added
layout:

  header:
    - Extracted claim/event
    - Confidence score & indicators
    - Timestamp & sources

  evidence_section:
    - Original quotes with highlighting
    - Supporting articles
    - Conflicting information

  entity_section:
    - All entities involved
    - Their roles in context
    - Historical patterns

  investigation_tools:
    - Add to tracked event
    - Flag for review
    - Export evidence package
```

---

## Key User Flows

### Flow 1: Morning Briefing

```yaml
user_need: "What happened overnight?"

steps:
  1_dashboard:
    - Check system health indicator
    - Scan "What's New" column
    - Note any priority alerts

  2_deep_dive:
    - Click interesting context
    - Review entity relationships
    - Check source reliability

  3_action:
    - Flag important contexts
    - Add entities to watch list
    - Export briefing summary
```

### Flow 2: Entity Investigation

```yaml
user_need: "Tell me everything about [entity]"

steps:
  1_search:
    - Global search → entity name
    - Or: Entity Browser → filter by type

  2_profile:
    - View entity profile
    - Check relationship network
    - Review timeline

  3_expand:
    - Click related entities
    - Find hidden connections
    - Build investigation graph
```

### Flow 3: System Monitoring

```yaml
user_need: "Is my collection working properly?"

steps:
  1_monitor:
    - Navigate → Monitor → Collection Watch
    - Check source statuses
    - Review error logs

  2_diagnose:
    - Identify failing sources
    - Check processing backlogs
    - View confidence distributions

  3_adjust:
    - Disable problematic sources
    - Adjust collection priorities
    - Clear backlogs
```

---

## Implementation Priorities

### Phase 1: Core Dashboard (Week 1)

```yaml
build:
  - Basic dashboard with 3-column layout
  - System health indicator
  - Latest contexts list
  - Simple navigation structure

technical:
  - React + Vite (existing)
  - Material-UI layout and components
  - contextCentricApi + orchestrator/health APIs
  - New route: / or /:domain/dashboard as landing
```

### Phase 2: Entity & Context Views (Week 2)

```yaml
build:
  - Entity profile pages (enhance existing)
  - Context detail page (new)
  - Basic search (Intelligence Search exists)
  - Relationship graphs (simple)

technical:
  - Dynamic routing (existing pattern)
  - Graph viz (e.g. Recharts or D3)
  - GET /api/contexts/:id if not present
  - Pagination (existing on list endpoints)
```

### Phase 3: Investigation Tools (Week 3)

```yaml
build:
  - Event tracking (Tracked Events exist)
  - Entity watch lists (priority/importance in profiles)
  - Export functionality
  - Basic filtering

technical:
  - State / preferences (localStorage or API)
  - Export to PDF/JSON
  - PATCH entity_profiles (importance), existing
  - Advanced search (context_centric/search exists)
```

### Phase 4: Monitoring & Analytics (Week 4)

```yaml
build:
  - Collection watch dashboard (CollectionWatch exists)
  - Source health metrics
  - Trend analysis
  - Alert system

technical:
  - Polling or SSE for real-time
  - Charts (MUI + Recharts)
  - Orchestrator + context_centric/quality APIs
  - system_alerts or notification UI
```

---

## Design Principles

### Visual Hierarchy

```yaml
colors:
  primary: Navy blue (trust, intelligence)
  accent: Bright blue (CTAs, alerts)
  success: Green (health, confidence)
  warning: Amber (attention needed)
  danger: Red (errors, conflicts)

typography:
  headings: Inter or SF Pro (clean, modern)
  body: System fonts (fast loading)
  monospace: JetBrains Mono (data display)

spacing:
  compact: Dashboard views (more data)
  comfortable: Investigation pages (focus)
  responsive: Mobile-friendly layouts
```

Align with existing MUI theme in `web/src/App.tsx` (primary #1976d2, success, warning, error) and extend with custom palette if needed.

### Information Density

```yaml
dashboard:
  - High density, scannable
  - Progressive disclosure
  - Hover for details

investigation:
  - Focused, single-task
  - Clear CTAs
  - Contextual help

mobile:
  - Stack columns vertically
  - Touch-friendly targets
  - Swipe gestures
```

---

## Live routes (v8) and product map

**Stack:** React 18, Vite, Material-UI v5, TypeScript (see [AGENTS.md](../AGENTS.md), [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md)). Use MUI components and existing theme.

All active web routes are domain-scoped (`/:domain/...`) in `web/src/App.tsx`.

| Product layer | Live route(s) | Primary UI file(s) | Primary API module(s) |
|--------------|----------------|--------------------|------------------------|
| Overview | `/:domain/dashboard` | `web/src/pages/Dashboard/Dashboard.tsx` | `web/src/services/apiService.ts`, `web/src/services/api/monitoring.ts` |
| Corpus | `/:domain/articles`, `/:domain/articles/:id`, `/:domain/rss_feeds`, `/:domain/investigate/documents` | `Articles.tsx`, `ArticleDetail.jsx`, `RSSFeeds.tsx`, `ProcessedDocumentsPage.tsx` | `apiService.ts`, `web/src/services/api/rss.ts` |
| Stories | `/:domain/storylines`, `/:domain/storylines/:id`, `/:domain/storylines/:id/timeline`, `/:domain/storylines/discovery`, `/:domain/storylines/synthesized` | `Storylines.tsx`, `StorylineDetail.tsx`, `StoryTimeline.tsx`, `StorylineDiscovery.jsx`, `SynthesizedView.jsx` | `web/src/services/api/storylines.ts` |
| Signals | `/:domain/topics`, `/:domain/events` | `Topics.tsx`, `Events.tsx` | `apiService.ts`, `web/src/services/api/topics.ts` |
| Cross-cutting intelligence | `/:domain/discover`, `/:domain/discover/contexts/:id`, `/:domain/investigate/*` | `DiscoverPage.tsx`, `ContextDetailPage.tsx`, `InvestigatePage.tsx`, entity/event/document pages | `web/src/services/api/contextCentric.ts`, `apiService.ts` |
| Outputs | `/:domain/briefings`, `/:domain/report`, `/:domain/watchlist` | `Briefings.tsx`, `ReportPage.tsx`, `Watchlist.tsx` | `apiService.ts`, `web/src/services/api/watchlist.ts` |
| Operations | `/:domain/monitor`, `/:domain/audit-checklist`, `/:domain/analyze` | `MonitorPage.tsx`, `AuditChecklistPage.tsx`, `AnalyzePage.tsx` | `apiService.ts`, `web/src/services/api/monitoring.ts` |
| Finance-specific | `/:domain/commodity/:commodity`, `/:domain/analysis`, `/:domain/analysis/:taskId` | `CommodityDashboard.tsx`, `FinancialAnalysis.tsx`, `FinancialAnalysisResult.tsx` | `web/src/services/api/finance.ts`, `apiService.ts` |

## Historical routes note

References to `/intelligence/...` paths in older docs and archived UI folders are historical and not the live router. Keep those references only for migration context; implement against `/:domain/...` routes and flat `/api/...` endpoints.

## Current alignment gaps

- Navigation is now route-complete but still benefits from pipeline-layer grouping in `AppNav.tsx`.
- A shared "raw/technical" disclosure pattern should be standardized across high-audit pages.
- High-traffic JSX pages should be migrated to TSX (`ArticleDetail`, `StorylineDiscovery`, `SynthesizedView`) to reduce drift and improve type safety.

This plan remains the roadmap for keeping UI language, navigation, and audit workflows aligned to the real data pipeline.
