# Archived SQL migrations

## `historical/`

Contains **numbered `NNN_*.sql` files** moved out of the active migrations root after **176** (`public.applied_migrations`). Kept for audit and ordered replay on empty DBs — **not** for re-applying on existing prod.

**Path resolution:** `shared.migration_sql_paths.resolve_migration_sql_file` searches active dir first, then `archive/historical/`.

See **`../README.md`** in the migrations root for the ledger and how to add new SQL.
