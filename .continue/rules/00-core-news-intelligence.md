---
name: News Intelligence — core context
description: Project intent, terminology, entry points, and where to read full agent guidance
alwaysApply: true
---

# News Intelligence — core context

You are working in the **News Intelligence** monorepo: FastAPI backend (`api/`), React + TypeScript frontend (`web/`), Postgres per-domain schemas, background automation.

## Authoritative docs (read when unsure)

- **`AGENTS.md`** (repo root) — full agent guidance: terminology, flows, DB rules, file layout, doc alignment policy.
- **`docs/CODEBASE_MAP.md`** — human navigation.
- **`docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md`** — pipeline order.
- **`docs/CODING_STYLE_GUIDE.md`** — Python + TS naming and patterns.
- **`docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md`** — ingest / phase contracts.
- **`docs/CODE_REVIEW_AND_RUN_CAVEATS.md`** — ops caveats.

Prefer **built-in Agent tools** (`read_file`, `grep_search`, `glob_search`, `view_repo_map`) to explore before large edits. Do not invent `/api/v4/` or legacy path prefixes.

## Terminology (use consistently)

| Use | Avoid |
|-----|--------|
| **storylines** | stories, threads |
| **domains** | sections, buckets |
| Domain keys **politics**, **finance**, **science-tech** | ALL CAPS domain names |
| **`rss_feeds`** | rssFeeds |
| **`/api/{domain}/...`** and **`/api/...`** global | `/api/v4/` |

## Entry points (quick)

- API: `api/main.py`
- Frontend shell: `web/src/App.tsx`, `web/src/layout/MainLayout.tsx`
- DB: `api/shared/database/connection.py` (single source; `config.database` is a shim)
- Automation: `api/services/automation_manager.py`

## API URLs

- All routes under **`/api`**, **no version prefix**.
- Domain routes: **`/api/{domain}/...`** (`politics`, `finance`, `science-tech`, plus optional silos from registry).
- Global: **`/api/system_monitoring/...`**, **`/api/orchestrator/...`**, **`/api/watchlist`**, etc.
- Route segments: **`snake_case`**.

## Database (must follow)

- Use **`get_db_connection_context()`** or **`try` / `finally`** with `conn.close()` — never close only inside `try`.
- Do **not** hold DB connections across LLM calls, HTTP, or sleeps.
- Do **not** mix worker / UI / health pools or open raw `psycopg2.connect()` for app work.

## Change discipline

- Only change what the task requires; match existing style and imports.
- When you change **routes, response shapes, or core behaviour**, update **`AGENTS.md`** and the relevant **`docs/*`** in the same change (see `AGENTS.md` “Keeping Documentation Aligned”).
