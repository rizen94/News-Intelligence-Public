# Repo and context hygiene

Keep the repo and Cursor context manageable so Git and the AI use resources responsibly.

## What’s ignored (and why)

- **`.gitignore`** — Git does not track: venvs (`.venv/`, `.venv.backup/`), `node_modules/`, logs, `data/`, `archive/`, secrets, backups, `scripts/pi_reports/`, and the usual Python/IDE/OS cruft. See project root `.gitignore` for the full list.
- **`.cursorignore`** — Cursor skips the same heavy/generated dirs when building context, plus `docs/_archive/`, `uv.lock`, and a few very large single files (`tests/unit/test_finance_market_data_store.py`, `web/DEVELOPMENT_SETUP.md`, `api/_archived/`) to avoid overloading indexing. That keeps the context window focused and can reduce crashes.

## Commit in smaller, logical chunks

When you have many changed files (e.g. 50+), Git and Cursor both do better if you commit in batches instead of one giant commit. Example split:

1. **Migrations and runners** — `api/database/migrations/*.sql`, `api/scripts/run_migration_*.py`
2. **Context pipeline** — `api/services/context_processor_service.py`, `api/collectors/rss_collector.py`, `api/services/automation_manager.py`
3. **Docs** — `docs/*.md`, `docs/_archive/*.md`
4. **Config and scripts** — `api/config/*`, `scripts/*`, `infrastructure/*`
5. **Web** — `web/src/**`, `web/package.json`, etc.
6. **API domains** — group by domain or feature

Smaller commits mean smaller diffs, faster operations, and easier history.

## If Cursor keeps crashing

- **Indexing load** — `.cursorignore` now excludes a few very large files (800KB+ test file, 345KB doc, archived API code). Restart Cursor after changing `.cursorignore` so it re-indexes with the new rules.
- **Working tree** — Commit or stash so you have fewer modified/untracked files; large `git status` can add load.
- **Context length** — Start a new chat for new topics so the current thread doesn’t grow too long; close unused file tabs.
- **Rules** — If you have many or very long `.cursor` rules or `AGENTS.md`, consider shortening them or splitting into smaller files.

## Testing before Phase 4 (context-centric)

- **Smoke test (no DB):** From project root run  
  `PYTHONPATH=api .venv/bin/python api/tests/test_context_centric_imports.py`  
  Verifies context-centric services and API routes load.
- **Full API tests (DB required):** `PYTHONPATH=api .venv/bin/python api/tests/test_api_routes.py` — needs PostgreSQL (e.g. Widow) and credentials.
- **Commit in chunks:** Use `bash scripts/commit_context_centric.sh` to commit context-centric and doc changes in logical order (migrations → services → config → API → test → docs → hygiene). Confirm each step at the prompt.

## Optional disk cleanup

- **`.venv.backup`** — If you no longer need it, remove it to free several GB: `rm -rf .venv.backup` (it’s ignored by Git and Cursor).
- **Old docs** — Keep superseded plans in `docs/_archive/`; they’re ignored by Cursor but still in Git for reference.

## Reference

- Full doc index: [DOCS_INDEX.md](DOCS_INDEX.md)
- Coding style: [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md)
