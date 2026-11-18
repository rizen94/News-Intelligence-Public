---
name: ni-migrations
description: >-
  Add or apply News Intelligence SQL migrations — NNN files, ledger,
  register_applied_migration, migrate_apply_and_register.sh. Use for schema,
  new tables/columns, migration ledger drift, or DB_PRODUCTION_MAINTENANCE.
---

# NI SQL migrations

SoT: `api/database/migrations/README.md` · runbook: `docs/DB_PRODUCTION_MAINTENANCE_RUNBOOK.md`

## New migration

1. Add **`api/database/migrations/NNN_description.sql`** — next number after highest **active** file **and** after `public.applied_migrations` (never reuse an id already in the ledger; e.g. **263** is `graph_pattern_refusal_and_link_status`).
2. Add or extend **`api/scripts/run_migration_NNN.py`** using `resolve_migration_sql_file(...)` from `shared.migration_sql_paths`.
3. **Never rewrite** an already-applied migration — add a new `NNN`.
4. Domain silo post-SQL (RSS YAML, `domains.is_active`): see README § “YAML-onboarded silo” and `run_migration_180.py` pattern.

## Ledger (before/after apply)

```bash
PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py --active-only
```

Compare active dir vs `public.applied_migrations`.

## Apply + register (typical)

```bash
./api/scripts/migrate_apply_and_register.sh <migration_id>   # widow default
# or explicit: ... <id> widow | dev popos — see script header
```

Manual path (when script doesn’t fit):

```bash
PYTHONPATH=api uv run python api/scripts/run_migration_NNN.py
PYTHONPATH=api uv run python api/scripts/register_applied_migration.py NNN --notes "..." --file api/database/migrations/NNN_....sql
```

Prod/Widow apply only when user authorizes — then skill **`ni-ship-widow`** if deploy bundles the change.

## Blocked without explicit approval

- Edit **`api/shared/database/connection.py`** — skill **`ni-db-code`**.
- Delete outside `archive/` (see `.clinerules/workflow.md`).

## Live DB checks

Skill **`ni-postgres`** — schema/objects on Widow via `postgres-mcp`, not homelab `:15432`.
