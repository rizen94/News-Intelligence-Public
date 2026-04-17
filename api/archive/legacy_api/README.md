# Archived: legacy global API router

**Status:** Retired from the running app (2026-04). This folder is **reference only**.

**File:** `legacy_global_api.py` — former `FastAPI` `APIRouter` (`legacy_global_router`) that mounted **flat** paths under `/api/...` without a `{domain}` segment (e.g. `/api/storylines/`, `/api/rss-feeds/`, `/api/topics/`, `/api/dashboard/stats`, `/api/intelligence/topic-clusters`).

**Why removed:** Domain-scoped routes under `api/domains/*/routes` are the supported surface; the legacy router duplicated behavior, confused versioning labels ("v3"), and overlapped routes registered earlier in `main.py`.

**If something breaks in production:**

1. Identify which **exact path** the client calls (e.g. `GET /api/storylines/`).
2. Prefer **migrating the client** to the equivalent `/api/{domain}/...` route (see `storyline_management`, `content_analysis`, `news_aggregation` routers).
3. **Temporary restore:** copy `legacy_global_api.py` back to `api/compatibility/legacy_global_api.py`, add an empty `api/compatibility/__init__.py`, then in `main.py`:
   ```python
   from compatibility.legacy_global_api import legacy_global_router
   app.include_router(legacy_global_router)
   ```
   Fix any import paths if the file was edited while archived.

**Do not** re-enable long-term without a migration plan; restore is for incident triage only.
