# Feature registry (v10.1)

Backend features are registered in [`api/config/features.yaml`](../api/config/features.yaml) with lifecycle tags. Runtime gates use [`api/config/feature_registry.py`](../api/config/feature_registry.py).

## Lifecycle states

| State | Scheduler | Meaning |
|-------|-----------|---------|
| `under_developed` | Off | WIP — registered before merge |
| `staged` | Shadow/dry-run only | Ready for verification |
| `incorporated` | On (production) | Sole active path |
| `deprecated` | Off (env override for rollback) | Superseded by `replaced_by` |
| `archived` | Off permanently | Code in `api/_archived/` |

## Rollover checklist (replace only when necessary)

1. Register successor as `under_developed` with `replaces: [old_key]`
2. Implement; verify in shadow/staged mode
3. Cutover: successor → `incorporated`; predecessor → `deprecated`
4. Next release: move code to `api/_archived/`; predecessor → `archived` + `archive_path`
5. Update CHANGELOG and `UPGRADE_10.1.md`
6. Remove predecessor from `schedulers.yaml` / `SKIP_WHEN_EMPTY`

## Search

```bash
PYTHONPATH=api python api/scripts/list_features.py --lifecycle under_developed
PYTHONPATH=api python api/scripts/list_features.py --enabled false --json
PYTHONPATH=api python api/scripts/list_features.py --counts
python scripts/verify_feature_registry.py
```

API: `GET /api/system_monitoring/features?lifecycle=staged`

## Emergency override

```bash
FEATURE_OVERRIDE_unified_intake_extraction=false
```

Optional DB overrides: `intelligence.feature_registry_overrides` (migration 249).

## Policy

New backend capabilities must register as `under_developed` before merge to `release/*`. Use `is_feature_enabled("feature_key")` — do not add scattered `is_*_enabled()` helpers.
