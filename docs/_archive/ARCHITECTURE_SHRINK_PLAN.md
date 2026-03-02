# News Intelligence — Architecture Shrink Plan

**Goal:** Reduce project footprint so it fits comfortably in AI/LLM context for coding. Prioritize fewer files, simpler structure, and multipurpose components over scattered, single-purpose modules.

---

## Current State Snapshot

| Category | Count | Notes |
|----------|-------|-------|
| **Archive** | 27GB, ~508k files | v3 backups, pre-consolidation copies — **primary bloat** |
| **Active Python** | ~207 files | API, services, domains |
| **Active Frontend** | ~76 files | TS/TSX/JS/JSX in web/src |
| **API routers in main** | 18+ | Each mounted separately from domain route files |
| **Storyline routes** | 11 files | crud, articles, evolution, analysis, helpers, timeline, watchlist, automation, discovery, consolidation |
| **Content analysis routes** | 6 files | content_analysis, topic_*, article_deduplication, llm_activity |
| **Intelligence hub routes** | 4 files | hub, analysis, rag_queries, content_synthesis |
| **apiService.ts** | 1,911 lines | Monolithic — single file with 100+ methods |
| ** migrations** | 48 | Sequential SQL files |
| **scripts/** | 151 files | Many one-off or rarely used |

---

## Design Principles for Shrinkage

1. **One concept, one file** — Merge related route modules instead of one route per file.
2. **Co-locate by feature** — Keep routes, services, and types for a feature together when it simplifies context.
3. **Archive off-project** — Move large archives outside the repo or compress; use external backup/versioning.
4. **Single source of truth** — One config layer, one API client shape, one docs tree.
5. **Facades over fragmentation** — Fewer entry points (main.py, apiService) that delegate internally.

---

## Phase 1: Archive & Disk Size (Immediate Win)

**Impact:** ~27GB freed, ~500k files removed from tree.

### 1.1 Move archive out of the project

- **Action:** Move `archive/` outside the project (e.g. `~/news-intelligence-archives/` or a separate repo).
- **Rationale:** Archives are for recovery, not daily development. They inflate `find`, `grep`, and indexers.
- **Safety:** Keep a tarball or zip of `archive/` in a safe location before deleting from the project.
- **Optional:** Git LFS or external backup for specific snapshots you might need.

### 1.2 Compress or retire legacy backups

- Consolidate `v3_latest_working_*`, `PRE_CONSOLIDATION_BACKUP_*`, etc. into one or two reference tarballs.
- Remove redundant or duplicate backups from the active tree.
- Document what was archived and where.

---

## Phase 2: API Route Consolidation

**Impact:** Fewer route files and imports; simpler mental model and less context load.

### 2.1 Storyline management: 11 → 1–2 files

**Current:** `storyline_crud`, `storyline_articles`, `storyline_evolution`, `storyline_analysis`, `storyline_helpers`, `storyline_timeline`, `storyline_watchlist`, `storyline_automation`, `storyline_discovery`, `storyline_consolidation`, `storyline_management`.

**Proposed:**

- `storyline_routes.py` — All CRUD, articles, evolution, analysis, helpers, discovery, consolidation, automation. Use sections/comments to separate logical groups.
- `storyline_timeline_routes.py` — Timeline + watchlist (or fold into `storyline_routes.py` if small enough).

**Rationale:** All storyline endpoints share the same prefix and domain model. One file (~400–600 lines) is easier to reason about than 11 files.

### 2.2 Content analysis: 6 → 1 file

**Current:** content_analysis, topic_management, topic_queue_management, article_deduplication, llm_activity_monitoring.

**Proposed:** `content_analysis_routes.py` — All content analysis endpoints in one file, grouped by section.

### 2.3 Intelligence hub: 4 → 1 file

**Current:** intelligence_hub, intelligence_analysis, rag_queries, content_synthesis.

**Proposed:** `intelligence_routes.py` — Single consolidated router.

### 2.4 Reduce `main_v4.py` router imports

**Current:** 18+ `include_router` calls.

**Proposed:** Domain packages expose a single router each, e.g.:

```python
# domains/storyline_management/routes.py
router = APIRouter(...)
# Include all storyline sub-routers internally
```

`main_v4.py` then only imports:

- news_aggregation
- content_analysis
- storyline_management
- intelligence_hub
- finance
- user_management
- system_monitoring
- compatibility

---

## Phase 3: Frontend Consolidation

**Impact:** Fewer files, smaller `apiService`, clearer boundaries.

### 3.1 Split apiService by domain

**Current:** One 1,911-line file with 100+ methods.

**Proposed structure:**

```
services/
  api/
    index.ts          # Re-exports, getApi(), shared config
    articles.ts       # getArticles, getArticle, ...
    storylines.ts     # getStorylines, getStoryline, getStorylineTimeline, ...
    topics.ts
    rss.ts
    intelligence.ts   # RAG, synthesis, briefings
    monitoring.ts    # health, metrics, pipeline status
    watchlist.ts     # getWatchlist, addToWatchlist, ...
```

- Each file is ~100–250 lines.
- `index.ts` aggregates and exposes a single `apiService` with the same interface.
- Agents can load only the domain they are modifying.

### 3.2 Page consolidation

- **Storylines + StorylineDetail:** Consider a single `Storylines/` folder with `index.tsx` (list) and `Detail.tsx` (detail). Same for Articles.
- **Intelligence sub-pages:** Tracking, Briefings, Events, Watchlist — evaluate if some can share layout and reduce route/page fragmentation.

### 3.3 Shared components

- Audit `shared/` and `components/` for single-use or near-duplicate components.
- Merge or remove where a generic component can replace several specific ones.

---

## Phase 4: Scripts & Config Simplification

**Impact:** Fewer scattered scripts and configs.

### 4.1 Scripts

- **Inventory:** Categorize 151 scripts: daily use, one-off, deprecated.
- **Consolidate:** Merge small helper scripts into a small set of entry points (e.g. `scripts/run.sh`, `scripts/setup.sh`).
- **Archive:** Move one-off or deprecated scripts to `scripts/archive/` or remove if no longer needed.

### 4.2 Config

- Single config module: e.g. `config/settings.py` or `config/index.ts` that reads env and exposes a typed config.
- Collapse scattered `.env.example`, `configs/*.yml`, etc. into one documented template.

### 4.3 Migrations

- Keep migrations as individual files (tooling expects this).
- Option: Squash very old migrations (e.g. 001–020) into a single “baseline” migration if schema is stable and tooling supports it. Defer until tooling is checked.

---

## Phase 5: Documentation Consolidation

**Impact:** One docs tree, less noise for both humans and AI.

### 5.1 Structure

- `docs/` — Only active documentation.
- `docs/archive/` — Older or deprecated docs, or move out of repo.
- Single `README.md` at project root with links to key docs.

### 5.2 Essential docs to keep

- `CODING_STYLE_GUIDE.md`
- `QUICK_START.md` (or merge into README)
- `ARCHITECTURE.md` (new: high-level overview)
- API reference (generated from OpenAPI or a single hand-maintained doc)

### 5.3 Remove or archive

- Redundant setup/deployment guides.
- Historical “completion” or “fix” reports.
- Duplicate style guides or methodology docs.

---

## Phase 6: Agent/LLM Context Optimization

**Impact:** Better use of context windows when coding with AI.

### 6.1 Single “project map” file

Create `PROJECT_MAP.md` (or `.cursor/PROJECT_MAP.md`):

```markdown
# News Intelligence — Project Map

## Entry points
- API: api/main_v4.py
- Frontend: web/src/App.tsx
- API client: web/src/services/api/

## Domain structure
- politics, finance, science-tech share schemas
- Each domain: articles, storylines, topics, rss_feeds

## Key flows
- Article: RSS → processing → storyline linking → event extraction
- Storyline: create → add articles → analyze → timeline → watchlist

## File counts (target)
- API routes: ~8 consolidated files
- Services: ~15 core services
- Frontend pages: ~15
```

Update this as the project evolves.

### 6.2 Cursor rules

- One rule file that references the project map and coding guide.
- Avoid multiple overlapping rules that repeat the same concepts.

### 6.3 Modular context loading

- Use `.cursorignore` to exclude archive, node_modules, build artifacts.
- Consider `AGENTS.md` or similar with “load this for backend work” / “load this for frontend work” sections.

---

## Target State (Post-Shrink)

| Metric | Before | After (Target) |
|--------|--------|----------------|
| Archive in project | 27GB, 508k files | 0 (moved external) |
| API route files | ~30 | ~8 |
| main_v4 router imports | 18+ | ~8 |
| apiService | 1 file, 1911 lines | Split into ~8 domain files |
| Scripts (active) | 151 | ~20–30 |
| Docs (active) | Mixed | Single tree, ~10–15 essential |
| Total project size | ~34GB | ~7GB (api + web + config) |

---

## Implementation Order

1. **Phase 1** — Archive relocation (no code changes, huge impact).
2. **Phase 5** — Docs consolidation (low risk, reduces noise).
3. **Phase 4.1** — Scripts inventory and archive (low risk).
4. **Phase 3.1** — apiService split (medium risk, high payoff for frontend work).
5. **Phase 2** — API route consolidation (medium risk, test thoroughly).
6. **Phase 6** — Project map and rules (low risk).
7. **Phases 3.2, 4.2** — Page/config refinements as needed.

---

## Risk Mitigation

- **Backup:** Full backup before each phase.
- **Incremental:** One phase at a time; verify tests and manual checks before proceeding.
- **Reversibility:** Keep consolidations in separate commits so they can be reverted if necessary.
- **Compatibility:** Ensure v3_compatibility router and any external integrations still work after route consolidation.
