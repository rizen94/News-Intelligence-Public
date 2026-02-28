# Architecture Shrink — Verified Metrics & Savings Estimates

**Generated:** Spot-check of current state and best-guess savings vs. realistic minimums.

---

## 1. Verified Current State (as of check)

### Disk Size

| Location | Size | Notes |
|----------|------|-------|
| **archive/** | 27 GB | v3 backups, pre-consolidation copies |
| **web/** | 879 MB | ~878 MB is node_modules (excluded from context) |
| **web/src** | 1.5 MB | Actual frontend source |
| **api/** | 6.5 MB | Backend source |
| **scripts/** | 1.4 MB | |
| **docs/** | 2.3 MB | |
| **configs/** | 12 KB | |
| **Project total** | ~34 GB | Dominated by archive |

### File Counts

| Category | Count | Notes |
|----------|-------|-------|
| archive/ | 508,387 | Inflates indexing, find, grep |
| api/ | 377 | Includes all Python |
| web/ (excl. node_modules) | 118 | TS/TSX/JS/JSX in src |
| scripts/ | 151 | |
| docs/ (total) | 249 | 94 active .md, 155 in docs/archive |
| api route files | 30 | In domains/*/routes/ |
| Migrations | 51 | SQL files |

### Line Counts (source)

| Category | Lines |
|----------|-------|
| API Python (all) | ~84,145 |
| Web src (TS/TSX/JS/JSX) | ~32,923 |
| **Route files total** | 13,677 |
| storyline routes (11 files) | 4,385 |
| apiService.ts | 1,911 |
| main_v4.py | 510 |

### Structure

| Item | Count |
|------|-------|
| apiService methods | ~124 |
| Frontend pages | 26 |
| main_v4 router imports | 18 |

---

## 2. Context / Memory Estimates

### Token convention

- **~4 tokens per line** for typical code
- **1,000 lines ≈ 4,000 tokens**
- Agent context budgets: often 100k–200k tokens

### Typical “storyline backend” task

| Loaded | Lines | Tokens (≈) |
|--------|-------|-------------|
| main_v4.py | 510 | 2,040 |
| 11 storyline route files | 4,385 | 17,540 |
| 1–2 service files | 600 | 2,400 |
| **Total** | **~5,500** | **~22,000** |

### Typical “add API call in frontend” task

| Loaded | Lines | Tokens (≈) |
|--------|-------|-------------|
| apiService.ts (full) | 1,911 | 7,644 |
| 1 page component | 400 | 1,600 |
| DomainLayout or routing | 200 | 800 |
| **Total** | **~2,500** | **~10,000** |

### Where the pain is

1. **apiService.ts** — 1,911 lines loaded for almost any API change, even if only one method is relevant.
2. **11 storyline route files** — Agent often needs to open several to understand patterns.
3. **508k files** — Slower indexing and search even if archive is ignored.
4. **249 docs** — Extra noise when searching for how things work.

---

## 3. Realistic Minimums (given project complexity)

Feature set: 3 domains × (articles, storylines, topics, RSS, events, watchlist, briefings, intelligence).

| Resource | Current | Realistic min | Reason |
|----------|---------|---------------|--------|
| Route files | 30 | 8–10 | One per domain/feature area |
| Route lines | 13,677 | ~12,000 | Small reduction from dedup, not major cuts |
| apiService | 1 file, 1,911 lines | 8 files, ~2,000 total | Same surface, split by domain |
| Frontend pages | 26 | 22–26 | Already close to minimum |
| Scripts | 151 | 25–40 | Keep core ops; archive/remove one-offs |
| Active docs | 94 | 12–20 | One-per-area + README, QUICK_START |
| Migrations | 51 | 51 | Keep as-is (tooling) |
| Archive in-tree | 27 GB, 508k | 0 | Move externally |

You can’t shrink below ~12k route lines without cutting features. The main levers are **file count** and **context targeting**, not large deletions of behavior.

---

## 4. Savings Estimates by Phase

### Phase 1: Move archive out of project

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Disk in project | 34 GB | ~7 GB | **~27 GB (79%)** |
| Files in tree | 508k+ | ~500 | **~99.9%** |
| Index/search speed | Slow | Fast | High (search no longer over 508k files) |
| Context | ~0* | 0 | None |

\*Archive typically in .cursorignore; main win is indexing and repo operations.

### Phase 2: API route consolidation (11→2 storyline, 6→1 content, 4→1 intelligence)

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Route files | 30 | ~10 | **20 files** |
| Route lines | 13,677 | ~13,200 | ~500 (dedup) |
| Files opened per “route” task | 5–11 | 1–2 | **~80% fewer** |
| Approx. context per route task | ~22k tokens | ~18k tokens | **~20%** (less switching, cleaner scope) |

### Phase 3: apiService split by domain

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| apiService structure | 1 file, 1,911 lines | 8 files, ~200–280 each | Same total lines |
| Context for “add articles API call” | 1,911 lines | ~280 lines | **~85%** |
| Context for “add storyline API call” | 1,911 lines | ~250 lines | **~87%** |
| Files to load per narrow task | 1 big file | 1 small file | Clearer boundaries |

### Phase 4: Scripts

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Script files | 151 | 30–40 | **~110 files** |
| Disk | 1.4 MB | ~0.3 MB | Small |

### Phase 5: Docs

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Active docs | 94 | 15–20 | **~75 files** |
| Archived docs in-tree | 155 | 0 (move out) | 155 files |

---

## 5. Summary Table

| Metric | Current | Post all phases | Savings |
|--------|---------|-----------------|---------|
| **Disk** | 34 GB | ~7 GB | **~27 GB** |
| **Files (excl. node_modules)** | 508k+ | ~600 | **~99.9%** |
| **Route files** | 30 | ~10 | **~67%** |
| **apiService context (typical task)** | 1,911 lines | ~250–300 lines | **~85%** |
| **Scripts** | 151 | ~35 | **~77%** |
| **Docs** | 249 | ~20 | **~92%** |

---

## 6. Context Reduction (best guess)

| Task type | Current tokens (≈) | Post-shrink (≈) | Reduction |
|-----------|-------------------|-----------------|-----------|
| Backend route change | 22,000 | 16,000 | ~27% |
| Frontend API integration | 10,000 | 2,500 | ~75% |
| “Where does X happen?” search | High (many files) | Lower (fewer files) | Qualitative |
| Full project overview | 117k lines | Same | No change (we’re not removing features) |

Frontend API tasks benefit most; backend route work gets a moderate improvement; overall context for a full overview stays similar because feature set is unchanged.

---

## 7. What we’re not saving

- **Total lines of behavior** — Roughly unchanged; consolidation and dedup only.
- **Migrations** — 51 kept; squashing is optional and tooling-specific.
- **Core services** — Event extraction, dedup, watchlist, etc. stay; they’re core logic.
- **Frontend pages** — 26 is already close to the minimum for the current feature set.

---

## 8. Confidence

| Phase | Confidence | Notes |
|-------|------------|-------|
| Phase 1 (archive) | High | Simple move; numbers are accurate |
| Phase 2 (routes) | Medium | Merge is mechanical; need solid tests |
| Phase 3 (apiService) | High | Split is well understood |
| Phase 4 (scripts) | Medium | Depends on which scripts are truly unused |
| Phase 5 (docs) | High | Archive old docs; keep essential ones |

Token/context numbers are approximate (~4 tokens/line); actual tokenization varies by model.
