# Shrink Implementation Audit

**Date:** 2026-02-21

## Summary

All six phases implemented. One regression found and fixed. No functionality lost.

---

## Verification

### Phase 1: Archive
- ✅ `archive/` moved to `../News-Intelligence-Archive/archive_20260221/`
- ✅ `archive/` in `.gitignore`
- ✅ No code depends on archive

### Phase 2: API Route Consolidation
- ✅ All 8 domain routers import and mount correctly
- ✅ Storyline discovery, consolidation, automation included in storyline `__init__`
- ✅ Prefix handling: child routers retain their paths; no double-prefix
- ✅ Compatibility router still included

### Phase 3: apiService Split
- ✅ `articlesApi` and `watchlistApi` exported and assigned to APIService
- ✅ All article methods (getArticles, getArticle, deleteArticle, deleteArticlesBulk, analyzeArticles, getArticleEvents) available
- ✅ All watchlist methods available
- ✅ TypeScript compiles (`tsc --noEmit`)

### Phase 4: Scripts
- ✅ SCRIPTS_INDEX.md created
- ✅ No scripts removed; archive structure preserved

### Phase 5: Docs
- ✅ docs/archive moved to News-Intelligence-Archive
- ✅ DOCS_INDEX.md created
- ✅ ARCHIVE_RELOCATION.md documents moves

### Phase 6: Context
- ✅ PROJECT_MAP.md created
- ⚠️ .cursorignore — write failed (permissions); create manually. Suggested contents: node_modules/, dist/, .venv/, archive/, __pycache__/

---

## Regression Fixed

**apiConnectionManager** was rewriting `/api/v4/watchlist` and `/api/v4/monitoring/*` to `/api/v4/{domain}/watchlist`, causing 404s. The watchlist and monitoring routes are domain-agnostic.

**Fix:** Added `watchlist` and `monitoring` to `globalRoutes` so the interceptor skips domain injection for these paths.

---

## Pre-Existing (Not Introduced by Shrink)

1. **config.database vs shared.database.connection** — Timeline and watchlist routes use `config.database.get_db_connection()`; main app uses `shared.database.connection`. Both work; consolidation would be a separate refactor.

2. **Vite build-html error** — `npm run build` fails with JSX parse error (Vite 7 build-html plugin parses TSX as HTML). `npm run dev` works. Workaround: pin Vite to 5.x and ensure `"type": "module"` in package.json, or wait for upstream fix. TypeScript passes.

---

## Safe Improvements Not Yet Done

| Improvement | Risk | Effort |
|-------------|------|--------|
| Split more apiService domains (storylines, topics, rss, monitoring) | Done (2026-02-21) | — |
| Unify config.database and shared.database.connection | Done (2026-02-21) | — |
| Fix Vite production build | Low | Low–Medium |
| Add .cursorignore manually | None | Trivial |

---

## Functionality Checklist

| Feature | Status |
|---------|--------|
| Articles CRUD | ✅ |
| Article events (v5) | ✅ |
| Watchlist CRUD | ✅ |
| Watchlist alerts, activity feed, dormant, gaps | ✅ |
| Storylines CRUD, timeline, narrative | ✅ |
| RSS feeds | ✅ |
| Topics | ✅ |
| Intelligence/RAG | ✅ |
| Monitoring, health, pipeline | ✅ |
| Finance (market trends, etc.) | ✅ |
| Domain routing (politics, finance, science-tech) | ✅ |
