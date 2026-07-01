# Frontend migration note — June 2026 overhaul

**Date:** 2026-06-09  
**Scope:** Sidebar IA rewrite, NRI investigation UX, longitudinal arc pages, orphan cleanup.

---

## Deleted files

| Removed | Reason | Functionality moved to |
|---------|--------|----------------------|
| `web/src/pages/Monitoring/Monitoring.tsx` | Superseded | `web/src/pages/Monitor/MonitorPage.tsx` |
| `web/src/pages/StorylineTracking/StorylineTracking.tsx` (+ `.css`) | Unrouted orphan | `web/src/pages/Storylines/Storylines.tsx`, storyline detail routes |
| `web/src/pages/StoryManagement/StoryControlDashboard.tsx` | Unrouted orphan | Storylines + review queue + discovery |
| `web/src/pages/FilteredArticles/FilteredArticles.tsx` | Unrouted orphan | `web/src/pages/Articles/Articles.tsx` |
| `web/src/pages/Settings/Settings.tsx` | Stub, no API | — (no user settings UI yet) |
| `web/src/pages/Analyze/AnalyzePage.tsx` | Removed from nav/product | Finance analysis at `/{domain}/analysis`; investigate hub for intelligence |

**Kept (finance orphans, still unrouted):** `EvidenceExplorer`, `FactCheckViewer`, `SourceHealth`, `RefreshSchedule`, `GoldCommodity`, etc.

---

## New pages

| Route | File |
|-------|------|
| `/{domain}/investigate/spine-browser` | `web/src/pages/Investigate/SpineBrowserPage.tsx` |
| `/{domain}/arcs` | `web/src/pages/Arcs/ArcCatalogPage.tsx` |
| `/{domain}/arcs/:arcId/spine` | `web/src/pages/Arcs/ArcSpinePage.tsx` |
| `/{domain}/arcs/:arcId/heatmap` | `web/src/pages/Arcs/ArcHeatmapPage.tsx` |
| `/{domain}/arcs/reports` | `web/src/pages/Arcs/ArcWeeklyBriefsPage.tsx` |
| `/{domain}/operations/nri-ops` | `web/src/pages/Operations/NriOpsPage.tsx` |
| `/{domain}/operations/llm-activity` | `web/src/pages/MLProcessing/MLProcessing.tsx` (routed) |

---

## Upgraded pages

| Page | Changes |
|------|---------|
| `EntityResolutionPage` | v2 tabs (auto_linked / parked / provisional / non_entity_topic), park-rate StatCards, context/entity links, parked approve with FtM ID (hidden in demo) |
| `HypothesesPage` | Loop run timeline, shadow/main badge, ACH frontmatter in drawer |
| `EntityDetailPage` / `EntityDossierPage` | Full FtM bridge panel (`FtmBridgePanel`) from `/api/nri/entity_bridge/{id}` |
| `InvestigatePage` | All NRI nav buttons (entities, search, documents, narrative threads, entity resolution, spine browser, hypotheses) |
| `AppNav.tsx` | Full IA: Overview, Corpus, Stories, Signals, Investigate, Arcs, Outputs, Finance, Operations |

---

## API client additions

`web/src/services/api/contextCentric.ts`:

- NRI: `getNriSpineEntities`, `matchNriSpine`, `getNriResolutionStats`, `getNriLoopRuns`, `getNriFtMCacheStats`
- Arcs: `listArcs`, `getArcSpine`, `getArcHeatmap`, `getArcAnalogues`, `getLatestArcReport`

---

## Routes preserved but hidden from nav

- `/{domain}/discover` — context discovery (nav removed; route kept)
- `/{domain}/watchlist` — demo-guarded

---

## Deploy

Run `web/scripts/deploy-web-dist.sh` on Widow to build and rsync to:

- `/opt/news-intelligence/web/dist`
- `/var/www/news-intelligence/web/dist` (nginx public root)

See `docs/FRONTEND_UPGRADE_DEVELOPMENT_PLAN.md` §6.
