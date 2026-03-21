# SQL migrations (active)

## Layout

| Location | Purpose |
|----------|---------|
| **`api/database/migrations/*.sql`** | **Active** migrations only — what new environments or incremental upgrades run from the repo tip. |
| **`archive/historical/*.sql`** | **Archived** pre–ledger SQL (numbers **&lt; 176** and one-offs). Still on disk for forensics and greenfield replays; runners resolve these via `shared.migration_sql_paths.resolve_migration_sql_file`. |

## Permanent record (176+)

After **migration 176**, record every successful apply in **`public.applied_migrations`**:

```bash
PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 182 --notes "run_migration_182.py" \
  --file api/database/migrations/182_add_domain_foreign_keys_skip_missing_topic_learning.sql

PYTHONPATH=api uv run python api/scripts/run_migration_185.py
PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 185 --notes "run_migration_185.py" \
  --file api/database/migrations/185_storylines_master_summary.sql
```

Compare the database to files on disk:

```bash
PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py
PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py --active-only   # only active dir vs ledger
```

Schema checks (objects, not ledger rows): `api/scripts/verify_migrations_160_167.py` (see script docstring for current range).

## Adding a new migration

1. Add **`NNN_description.sql`** in **this directory** (next number after the highest active file).
2. Add or extend **`api/scripts/run_migration_NNN.py`** using `resolve_migration_sql_file("NNN_....sql")`.
3. Apply on target DB, then **`register_applied_migration.py`** with the same id / file path.

Do **not** put new migrations under `archive/historical/` unless you are explicitly retiring and moving an unused file.

## See also

- `archive/README.md` — archive policy and greenfield notes
- `api/shared/migration_sql_paths.py` — path resolution for runners
