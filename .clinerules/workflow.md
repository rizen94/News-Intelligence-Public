# Workflow — Fix First, Explain Always

## Order of Operations (MUST FOLLOW)

1. **Triage first.** Before touching code, understand the symptom and root cause.
2. **Fix before feature.** If a bug is visible, fix it before building on top.
3. **Search before write.** Use `grep_repomix_output` to find callers/imports of anything you modify.
4. **Pack if needed.** For unfamiliar code, use `pack_codebase` then grep the packed output.

## Explaining Changes (MUST)

- State *what* you're doing and *why* in a single sentence before making changes.
- If fixing a bug: mention the symptom and your diagnosis.
- If refactoring: explain the pattern being replaced and what replaces it.
- Keep explanations concise — 1–2 sentences max.

## After Making Changes (MUST)

- Check if tests exist for the changed module — run them.
- For API changes: verify the route still wires correctly (check `__init__.py`).
- Commit messages follow: `type(scope): brief description` (e.g., `fix(db): close pool connection on timeout`)

## Code Quality (MUST)

- Never introduce a second copy of existing logic — extend or reuse first.
- Follow snake_case for Python, PascalCase for React components.
- Database connections: always use context manager or try/finally. Never hold across I/O.
- Single source of truth per concern — no config shims that diverge from the canonical one.

## Schema Changes & Migrations (MUST)

Database schema and code must stay in lockstep. The ledger (`public.applied_migrations`) is the single source of truth for what has been applied.

### Procedure when adding a migration

1. **Create** the SQL file: `api/database/migrations/NNN_name.sql`
2. **Commit the SQL first** (before any code that depends on it)
3. **Run the ledger report** to verify no gaps exist:
   ```bash
   PYTHONPATH=api python3 api/scripts/migration_ledger_report.py --active-only
   ```
4. **Apply the migration** using the hot-path script (one command):
   ```bash
   ./api/scripts/migrate_apply_and_register.sh NNN_name widow
   ```
5. **Write code against the new schema** and commit.

### When editing existing migrations

- Never modify an already-applied migration — always create a **new numbered migration**.
- If you must roll back: document in the ledger notes, don't silently rewrite history.

### Pre-commit gate

The `.git/hooks/pre-commit.d/01_migrations` hook blocks commits when new SQL files exist with missing ledger entries. Resolve the block by applying + registering before retrying.


## Unsafe Operations (BLOCKED without explicit approval)

The following are blocked without explicit human approval:
- Deleting files outside `archive/` or `docs/archive/`
- Modifying `api/shared/database/connection.py` (the single pool)
- Changing `.clinerules/` workflow rules themselves
- Any change that touches production deployment (systemd services, Docker compose)

## Investigation Policy (PERMISSIVE)

You have full freedom to:
- Read any file, trace any dependency chain
- Run commands, check logs, inspect DB state
- Propose multiple approaches and pick the simplest one
- Make temporary local edits for debugging (and tell me before discarding)