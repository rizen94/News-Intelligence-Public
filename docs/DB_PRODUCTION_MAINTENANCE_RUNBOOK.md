# Production database maintenance runbook

Use this for **staging first**, then **production**, when executing assessment cleanup bundles.

## Preconditions

- Change ticket approved; owner on-call.
- [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md) baseline section updated for this environment.
- Backup completed and verified (`scripts/db_backup.sh` or org standard).

## Steps

1. Run read-only checks: `verify_migrations_160_167.py`, `db_full_inventory.py`, `db_persistence_gates.py`, `diagnose_db_legacy_data.py`.
2. Apply **bundle A** only from [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md); re-run verification scripts.
3. If **bundle C** is in scope: complete **pre-delete checklist** per object in [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md); second-person sign-off.
4. **Bundle B** archive before any C action.
5. Post-change: smoke test web critical paths (dashboard, articles, monitor); re-run gates.
6. Optional maintenance window: `PYTHONPATH=api uv run python scripts/db_maintenance_analyze.py --vacuum` (longer; coordinate with DBA).

## Staging vs production

- Use distinct `DB_HOST` / credentials in `.env` or deployment secrets.
- Record each migration in `public.applied_migrations` via `api/scripts/register_applied_migration.py` after successful apply.

## Rollback

- Restore from backup taken in step 0; document LSN or dump path in the ticket.
