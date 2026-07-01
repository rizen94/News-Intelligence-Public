# NI + NRI Unification Baseline

> Generated June 2026 — pre-cutover snapshot for the `unification/big-bang` feature branch.

## Corpus scale (Widow dev workspace)

| Corpus | Files | Notes |
|--------|-------|-------|
| `api/` Python | 626 | incl. 73 in `api/nri_core/` |
| `web/src` TypeScript | 131 | Investigation product surface |
| `docs/` Markdown | 186 | target ≤40 active post-consolidation |
| Top LOC bucket | `api/services` ~75k | `automation_manager.py` god-object |

Run `python3 scripts/complexity_inventory.py` to refresh counts.

## Locked naming

| Layer | Name |
|-------|------|
| Internal Python package | `api/nri_core/` |
| UI product label | **Investigation** |
| Public API prefix | `/api/investigation/*` |
| Legacy shim | `/api/nri/*` (same handlers) |
| Post-migration tables | `intelligence.investigation_*` |

## Config kernel (SSOT)

| Module | Role |
|--------|------|
| `api/config/runtime.py` | Only module that reads `os.environ` for app code |
| `api/config/database_targets.py` | `news_intel_dsn()`, `spine_dsn()`, `maintenance_connect_kwargs()` |
| `api/config/investigation_tables.py` | Qualified table names (`T_RESOLVED_MENTIONS`, etc.) |
| `api/config/schedulers.yaml` | Scheduler manifest (5+ owners) |
| `web/src/config/apiRoutes.ts` | API path constants for TS |

Enforcement: `python3 scripts/verify_single_source_of_truth.py`

## Scheduler map (pre-unification)

| Owner | Unit / file | Status after cutover |
|-------|-------------|----------------------|
| AutomationManager | embedded 5s loop | **Primary** — includes `mention_resolution` phase |
| OrchestratorCoordinator | 60s | Active — collection cadence |
| newsplatform-secondary | systemd service | Active — RSS ingest |
| widow-db-adjacent | cron `infrastructure/widow-db-adjacent.cron` | Active — `context_sync` authoritative on Widow |
| nri-mention-resolver.timer | systemd | **Disabled** — replaced by `mention_resolution` |
| nri-loop.timer | systemd | **Disabled** — default off |
| nri-api.service | systemd :8010 | **Disabled** — in-process routes |

`context_sync` split-brain: cron owns sync on Widow prod when listed in `AUTOMATION_DISABLED_SCHEDULES`.

## Repomix packs

| Config | Output | Baseline (frozen) |
|--------|--------|-------------------|
| `repomix-widow.config.json` | `repomix-output.md` (full NI) | `repomix-output-2026-06-15.baseline.md` |
| `repomix-nri.config.json` | `repomix-nri-output.md` (nri_core + kernel) | `repomix-nri-output-2026-06-16.baseline.md` |

**Last regenerated:** 2026-06-24 on `unification/big-bang` — NI 1,215 files / ~910k tokens; NRI 87 files / ~18k tokens. See [generated/REPOMIX_COMPARISON_2026-06-24.md](generated/REPOMIX_COMPARISON_2026-06-24.md).

Regenerate:

```bash
repomix -c repomix-widow.config.json -o repomix-output-2026-06-24.md
repomix -c repomix-nri.config.json -o repomix-nri-output-2026-06-24.md
python3 scripts/compare_repomix_snapshots.py \
  --old repomix-output-2026-06-15.baseline.md \
  --new repomix-output-2026-06-24.md --label NI
```

Ignore additions in `repomix-widow.config.json`: `news-intelligence-kit/**`, `.cursor/**` (unreadable paths).

## Schema migration

`api/database/migrations/237_investigation_schema_merge.sql` — `nri.*` → `intelligence.investigation_*` with compatibility views.

Toggle post-migration: `USE_INVESTIGATION_PREFIXED_TABLES=true`

`identity_spine` remains a **separate database** on `:5432`.

## Prune targets (Phase 1)

- `api/collectors/enhanced_rss_collector.py` → archived (superseded by `rss_collector`)
- Unrouted finance pages → `web/_archived_duplicates/pages/Finance/`
- `web/_archived_duplicates/` — excluded from builds (tsconfig, repomix)

## Verification commands

```bash
# Import smoke
cd api && PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health; print(get_investigation_health())"

# SSOT lint
PYTHONPATH=api python3 scripts/verify_single_source_of_truth.py

# Post-cutover (on Widow)
scripts/verify_unification_cutover.sh
```

See [UNIFICATION_CUTOVER.md](UNIFICATION_CUTOVER.md) for maintenance-window steps.
