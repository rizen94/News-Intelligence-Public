# Repository cleanup — 2026-03

Consolidated archival pass: move **unused or non-canonical** trees out of day-to-day paths.

| Former location | Now |
|-----------------|-----|
| `analysis/` | `docs/archive/root_analysis_snapshots/analysis/` |
| `development/` | `docs/archive/development_ai_session_tooling/development/` |
| `monitoring/` (repo root) | `docs/archive/observability_stack_unused/monitoring/` |
| `docs/WEB_PRODUCT_DISPLAY_PLAN.md` etc. | `docs/archive/planning_incubator/` |
| `web/src/_archived_interface/` | `web/_archived_duplicates/_archived_interface/` |
| `api/tests/` | `api/_archived/legacy_pytest_tree_2026_03/` |
| `web/NEXT_STEPS.md` | `docs/archive/frontend_stale_notes/` |

**Still active:** `infrastructure/` (referenced by `WIDOW_DB_ADJACENT_CRON.md`), `api/orchestration/` (loaded from `main.py`), `docs/_archive/` (historical docs policy).

## Scripts (2026-03)

| Was | Now |
|-----|-----|
| One-off / diagnostic / Pi / old migration shells / `maintenance/` / `production/` under `scripts/` | `scripts/archive/retired_scripts_2026_03/` (see README there) |
