# Repo and context hygiene

Keep the repo and Cursor context manageable so Git and the AI use resources responsibly.

## Single main branch: master

**master** is the only active branch and holds the current working version. Older branches (production, production-rtx5090-optimized, ai-session-*) were removed; their tips are preserved as tags for reference: `archive/production`, `archive/production-rtx5090-optimized`, `archive/ai-session-20250925-175937`. To inspect an old state: `git show archive/production`, or `git checkout archive/production` (detached HEAD). Do not create long-lived alternate branches unless you have a clear reason; work on master and commit there.

## What’s ignored (and why)

- **`.gitignore`** — Git does not track: venvs (`.venv/`, `.venv.backup/`), `node_modules/`, logs, `data/`, **`/archive/`** (repo-root external archive only — **not** `api/database/migrations/archive/`), `.env`, `.db_password_widow`, `api/config/.secrets`, backups, `scripts/pi_reports/`, and the usual Python/IDE/OS cruft. See project root `.gitignore` for the full list. Periodically run `git grep -iE 'password|api_key|secret' -- ':!docs/_archive' ':!archive'` to spot accidental literals (triage; many hits will be docs or env var *names*).
- **`.cursorignore`** — Cursor skips the same heavy/generated dirs when building context, plus `docs/_archive/`, `uv.lock`, and a few very large single files (`tests/unit/test_finance_market_data_store.py`, `web/DEVELOPMENT_SETUP.md`, `api/_archived/`) to avoid overloading indexing. That keeps the context window focused and can reduce crashes.

## Commit in smaller, logical chunks

When you have many changed files (e.g. 50+), Git and Cursor both do better if you commit in batches instead of one giant commit.

**Suggested order for a “DB reliability + doc consolidation” session:**
1. **Docs and repo hygiene** — `.gitignore`, `README.md`, `docs/REPO_MAINTENANCE.md`, `docs/DOCS_INDEX.md`, `QUICK_START.md`, any other `docs/*.md` only.
2. **DB connection and scripts** — `api/shared/database/connection.py`, `api/config/database.py`, all `api/**` that use `get_db_connection`/pool, `start_system.sh`, `stop_system.sh`, `restart_system.sh`, `scripts/*.sh` (cron, report).
3. **Migrations and new API** — `api/database/migrations/*.sql`, `api/scripts/run_migration_*.py`, new services/routes.
4. **Frontend and config** — `web/src/**`, `configs/`, `pyproject.toml`, `docker-compose.yml`.

Example split (generic):

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

## Where to put retired material (archive layout)

| Location | Use for |
|----------|---------|
| **`archive/`** (repo root) | Planning packs, exports, non-markdown history, large attachments. Listed in [DOCS_INDEX.md](DOCS_INDEX.md) § Archived. Git may ignore per `.gitignore` — confirm before relying on Git history for these paths. |
| **`docs/_archive/`** | Superseded **Markdown** guides, old release notes (`_archive/releases/`), consolidated copies of merged docs (`_archive/consolidated/`). Still versioned unless excluded. |
| **`scripts/archive/`** | Retired **scripts** (one-off migrations, deprecated daemons). Do not delete without checking `SCRIPTS_INDEX.md`. |
| **`api/_archived/`**, **`web/_archived_duplicates/`** | Retired **code** only; follow “reuse before create” — restore from here before re-implementing. |
| **`docs/generated/`** | Pointer [generated/README.md](generated/README.md) — documents script-emitted reports; reports may still live as `docs/*_REPORT.md` at repo root for tooling compatibility. |

When you **merge** two docs, move the superseded file under `docs/_archive/consolidated/` with a one-line “Status: superseded by …” banner and update [DOCS_INDEX.md](DOCS_INDEX.md) (prefer updating the index over leaving stale top-level paths).

## Documentation inventory (quick)

- **Canonical index:** [DOCS_INDEX.md](DOCS_INDEX.md)
- **Orientation:** [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (includes capabilities + scope summaries; full matrices in `_archive/consolidated/`)
- **Setup:** [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md)
- **Security:** [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)
- **Generated reports:** [generated/README.md](generated/README.md)

## Merging branches and resolving conflicts

- **Branches:** Prefer **one mainline** (`master`) for day-to-day work; use tags for frozen snapshots (see § Single main branch above).
- **Before merge:** Commit (or stash) all local changes. Run `./status_system.sh` and a quick API health check so the tree you merge is known-good.
- **Conflict resolution:** If `git merge` reports conflicts:
  1. `git status` — lists conflicted files (e.g. `api/main_v4.py`, `start_system.sh`).
  2. Open each file; fix markers `<<<<<<<`, `=======`, `>>>>>>>` by keeping the correct version or combining both sides.
  3. `git add <file>` for each resolved file, then `git commit` to complete the merge.
- **Large change sets:** Commit in logical chunks (see “Commit in smaller, logical chunks” above) so merges produce smaller, reviewable conflict sets.

## Reference

- Full doc index: [DOCS_INDEX.md](DOCS_INDEX.md)
- Coding style: [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md)
