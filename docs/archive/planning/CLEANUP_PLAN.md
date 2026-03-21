# Post-Development Cleanup Plan

> **Purpose:** Consolidate files where possible, align naming with coding standards, and address under-developed features and temporary values.  
> **Reference:** [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md) (snake_case files, PascalCase classes, flat `/api` routes).  
> **Last updated:** 2026-02-21.

---

## 1. File consolidation (merge candidates)

### 1.1 Domain routes — keep structure, no merge

- **Storyline management:** 11 route files under `api/domains/storyline_management/routes/` are already composed via `__init__.py` into one router. Structure is acceptable; merging all into one file would create a 3000+ line file. **Action:** None; optionally group related routes into fewer files later (e.g. `storyline_crud.py` + `storyline_articles.py` → `storyline_crud_and_articles.py`) only if desired.
- **Other domains:** Content analysis, news aggregation, intelligence hub each use multiple route files composed in `__init__.py`. Same pattern; no mandatory merge.

### 1.2 Config — already minimal

- `api/config/`: `database.py`, `paths.py`, `settings.py`, `logging_config.py`, `orchestrator_governance.py`, `import_standards.py`, `__init__.py`. Single responsibility per file. **Action:** None.

### 1.3 Docs — consolidate references

- **Remaining doc tasks:** Now in **Section 6** of this document (no separate file). **docs/README.md** and **DOCS_INDEX** point to CLEANUP_PLAN. (Superseded: `docs/REMAINING_DOCUMENTATION_TASKS.md`, which does not exist at that path (only in `_archive` under different names). **Action:** Create `docs/REMAINING_DOCUMENTATION_TASKS.md` with a short checklist (e.g. “Sync FINANCE_ORCHESTRATOR_BUILD checkboxes”, “Review CODING_STYLE_GUIDE API prefix vs actual”), or update README to remove the link and point to FINANCE_TODO / ORCHESTRATOR_TODO instead.
- **Duplicate “remaining” content:** Several docs have “Remaining” or “Phase 8” sections (MIGRATION_TODO, RELEASE_v4.1_WIDOW_MIGRATION, FINANCE_ORCHESTRATOR_BUILD). **Action:** Keep as-is; they are domain-specific. Optionally add one-line cross-links between them in a “Remaining work” subsection of DOCS_INDEX.

### 1.4 Summary (merge)

| Area              | Recommendation |
|-------------------|----------------|
| Domain routes     | No merge; structure is composed and maintainable. |
| Config            | No change. |
| Docs              | Remaining doc tasks in Section 6 of this doc; optional cross-links for "Phase 8" sections. |

---

## 2. Renaming scheme (align with coding standards)

Standards (from CODING_STYLE_GUIDE): **snake_case** (files, functions, variables, DB columns), **PascalCase** (classes), **UPPER_SNAKE_CASE** (constants), **flat `/api`** (no `/api` in path).

### 2.1 API router prefix (doc vs code)

- **Current code:** Routers use `prefix="/api"` or `prefix="/api/system_monitoring"`, etc. Paths are flat `/api/...`. **Correct.**
- **CODING_STYLE_GUIDE.md:** Section “Router Prefix Convention” still describes `/api` as the main prefix and warns against double prefix. **Action:** Update CODING_STYLE_GUIDE.md to state that the project uses **flat `/api`** (no version in path), and that sub-routers must not duplicate `/api` when included under a parent that already has `prefix="/api"`. Remove or rewrite `/api` examples so they match current usage.

### 2.2 Python

- **Files:** All under `api/` are already snake_case. **Action:** None.
- **Optional[X] → X | None:** FINANCE_INFRASTRUCTURE_HANDOFF mentions a project-wide sweep. Low priority; do per-file when touching code. **Action:** Document in CLEANUP_PLAN or a short “Style migration” note; no bulk rename in this pass.

### 2.3 Frontend (web/)

- **Components/pages:** PascalCase for component names and folder names (e.g. `FinancialAnalysis.tsx`, `MainLayout.tsx`) is correct for React. **Action:** None.
- **Files:** Mix of PascalCase (components/pages) and camelCase (e.g. `apiService.ts`). CODING_STYLE_GUIDE does not mandate frontend; common practice is PascalCase for components, camelCase for utilities. **Action:** None unless you adopt a strict frontend guide.

### 2.4 Database and API paths

- Tables/columns: snake_case. Route path segments: snake_case (e.g. `market-trends` is kebab-case; guide says snake_case — acceptable for URL readability). **Action:** Optional: document that URL path segments may use kebab-case for readability while internal symbols stay snake_case.

### 2.5 Rename checklist

| Item | Current | Target | Priority |
|------|---------|--------|----------|
| CODING_STYLE_GUIDE API prefix section | /api | Flat /api, no version | High |
| REMAINING_DOCUMENTATION_TASKS | N/A (merged into Section 6 of this doc) | — | Done |
| Optional[X] in Python | Many files | X \| None (incremental) | Low |

---

## 3. Under-developed features and temporary values

### 3.1 Placeholder / TODO endpoints (expand or document)

| Location | Item | Recommendation |
|----------|------|----------------|
| `api/domains/finance/routes/finance.py` | `GET market-trends` | Placeholder; TODO: implement from financial articles. Either: (1) Implement a minimal version (e.g. aggregate from finance.articles + gold/FRED), or (2) Return 501 Not Implemented and document in FINANCE_TODO. |
| `api/domains/finance/routes/finance.py` | `GET market-patterns` | Same as above. |
| `api/domains/finance/routes/finance.py` | `GET corporate-announcements` | Same as above. |

**Suggested action:** Add to FINANCE_TODO as “Placeholder endpoints (market-trends, market-patterns, corporate-announcements): implement or 501 + doc”. Prefer one of: implement thin version using existing finance evidence/articles, or 501 + clear doc.

### 3.2 TODOs that need a decision

| Location | TODO | Recommendation |
|----------|------|----------------|
| `api/services/rss/fetching.py` | “Implement local NLP classifier using HuggingFace” | Either implement (e.g. small classifier for feed category) or remove/comment and add a short “Future: local NLP” note in docstring. |
| `api/domains/storyline_management/routes/storyline_automation.py` | “Move to domain schemas if needed” | Evaluate: if schemas are shared, move to `domains/storyline_management/schemas/`; otherwise leave and remove TODO. |
| `api/modules/ml/local_monitoring.py` | `eviction_count=0  # TODO: Track evictions` | Add eviction tracking (increment on evict) or document “Eviction tracking not implemented” and keep 0. |

### 3.3 Stub / pass blocks (evaluate)

- **Orchestration roles:** `orchestration/roles/chief_editor.py`, `archivist.py` — `logger.debug(..., "stub")`. **Action:** Leave as stubs or add one-line “Stub: no-op for now” in docstring; ensure they don’t break callers.
- **Finance data sources:** `edgar.py`, `fred.py`, `freegoldapi.py` — some `except: pass`. **Action:** Prefer logging and/or re-raise where appropriate; replace bare `pass` with at least `logger.debug(...)` or comment.
- **Shared logging:** `trace_logger.py`, `decision_logger.py`, `llm_logger.py`, `activity_logger.py` — no-op `pass` in fallback paths. **Action:** Acceptable for “no-op backend”; ensure docstrings say “No-op when X not configured”.

### 3.4 Magic numbers and constants

- **automation_manager.py:** Many `estimated_duration` values (seconds). **Action:** Move to a single dict or config (e.g. `PHASE_ESTIMATED_DURATIONS`) in the same file or `config/` so they can be tuned in one place.
- **route_supervisor.py:** `max_response_time_ms = 5000`. **Action:** Consider config or constant at top of file; document.
- **Cache TTLs:** Multiple files use `3600` (1 hour), `1800` (30 min). **Action:** Optional: define shared constants in `config/settings.py` or `shared/constants.py` (e.g. `DEFAULT_CACHE_TTL_SECONDS = 3600`) and reuse.

### 3.5 Summary (features / temporaries)

| Priority | Action |
|----------|--------|
| High | Document or implement finance placeholder endpoints (market-trends, market-patterns, corporate-announcements). |
| Medium | Resolve RSS NLP classifier TODO (implement or document as future). Resolve local_monitoring eviction_count (track or document). |
| Low | Replace bare `except: pass` in finance data sources with logging; centralize automation_manager estimated_duration; optional shared cache TTL constants. |

---

## 4. Documentation fixes (concrete)

1. **docs/README.md:** Replace “Check `docs/REMAINING_DOCUMENTATION_TASKS.md` for pending tasks” with either (a) a link to a new `docs/REMAINING_DOCUMENTATION_TASKS.md` that lists 3–5 items (e.g. sync FINANCE_ORCHESTRATOR_BUILD, review API prefix in guide), or (b) “See FINANCE_TODO.md and ORCHESTRATOR_TODO.md for domain-specific remaining work.”
2. **docs/CODING_STYLE_GUIDE.md:** In “Router Prefix Convention”, switch all examples from `prefix="/api"` to `prefix="/api"` and state that the project does not use a version segment in the path. Keep the “no double prefix” rule.
3. **docs/FINANCE_TODO.md:** Already states API is flat; ensure no remaining “/api” in that file.
4. **docs/FINANCE_ORCHESTRATOR_BUILD.md:** Sync checkboxes with FINANCE_TODO (e.g. “Stale data check”, “Catch-up on startup” marked done in TODO should be [x] in BUILD).

---

## 5. Execution order (suggested)

1. **Phase A (doc-only):** Update CODING_STYLE_GUIDE API prefix; remaining doc tasks in Section 6; sync FINANCE_ORCHESTRATOR_BUILD checkboxes; docs/README references CLEANUP_PLAN.
2. **Phase B (placeholders):** Decide and document or implement finance market-trends / market-patterns / corporate-announcements (implement minimal or 501 + FINANCE_TODO).
3. **Phase C (TODOs):** Resolve RSS NLP TODO, local_monitoring eviction_count, storyline_automation “move to domain schemas” (evaluate and either do or remove TODO).
4. **Phase D (optional):** Centralize automation_manager durations; optional shared cache TTL constants; replace critical bare `pass` in finance data sources with logging.

---

## 6. Remaining documentation tasks

Short checklist of pending doc updates. For domain-specific work, see [FINANCE_TODO.md](./FINANCE_TODO.md); orchestrator tracking is in _archive/ORCHESTRATOR_TODO.md.

- [x] CODING_STYLE_GUIDE: API prefix updated to flat `/api` (no `/api`).
- [x] FINANCE_ORCHESTRATOR_BUILD: Checkboxes synced with FINANCE_TODO (stale data check, catch-up on startup).
- [ ] Review other "Remaining" / "Phase 8" sections across docs and add cross-links in DOCS_INDEX if useful.
- [x] Finance placeholder endpoints (market-trends, market-patterns, corporate-announcements) implemented minimally; FINANCE_TODO and CLEANUP_PLAN updated.

---

*This plan is the single reference for post-development cleanup. Execute in order; update this doc when items are completed.*
