# Assembly integrity loop (instrument-first)

Aligned with [`api/services/ASSEMBLY_MODEL.md`](../api/services/ASSEMBLY_MODEL.md). Measure → one gate → deploy Widow → remasure. Packages-as-binder / membership merges / FTM stay parked.

## Ops

- Baseline / remasure: `PYTHONPATH=api .venv/bin/python api/scripts/assembly_integrity_baseline.py --out docs/ASSEMBLY_INTEGRITY_An.md`
- Deploy: `scripts/deploy_to_widow.sh` + `scripts/ensure_widow_api_runtime.sh` (targeted rsync if kit permission noise)
- Reconcile drain: maintenance `EPISODE_ASSEMBLY_RECONCILE_BAG` or `api/scripts/reconcile_eel_bag_asymmetric.py`
- A4 backfill (optional): `api/scripts/assembly_integrity_a4_handoff.py`

## Gates (2026-10-04)

| Gate | Change | Remeasure | Pass |
|------|--------|-----------|------|
| A1 | `reconcile_derived_bag_from_eel` + maintenance; reader `also_in` prefers EEL | [`ASSEMBLY_INTEGRITY_A1.md`](ASSEMBLY_INTEGRITY_A1.md) | **PASS** — `drift_total` 20321 → **0** (≤50% of PRE) |
| A2 | Stale-slate `vault_morning_prime` nudge (+72h freshness floor) | [`ASSEMBLY_INTEGRITY_A2.md`](ASSEMBLY_INTEGRITY_A2.md) | **PASS** — max_age ~119h → **~0.03h** after wake; deferred share stable |
| A3 | `admit()` rejects `is_false_enriched_body` → `not_yieldable` | [`ASSEMBLY_INTEGRITY_A3.md`](ASSEMBLY_INTEGRITY_A3.md) | **PASS** — probe admit → `False, not_yieldable`; 14d EEL proxy residual historical (14/87) |
| A4 | Evidence-brief `upsert_vault_note` + article-member clipping ensure; `get_package` exposes `vault_path`/`package_id` | [`ASSEMBLY_INTEGRITY_A4.md`](ASSEMBLY_INTEGRITY_A4.md) | **PASS** — vault brief share 0 → 0.072 (89); clipping coverage 0 → 54 members |

PRE snapshot: [`ASSEMBLY_INTEGRITY_BASELINE_PRE.md`](ASSEMBLY_INTEGRITY_BASELINE_PRE.md), `data/assembly_integrity_baseline_pre.json`.
POST snapshot: `data/assembly_integrity_post.json`.

## Residual follow-ups (2026-10-04 evening)

| Item | Action | Status |
|------|--------|--------|
| A2 slate age | 72h hard freshness floor + EEL novelty; triggered `vault_morning_prime` | **PASS** — max_age **119h → ~0.03h** ([`ASSEMBLY_INTEGRITY_A2.md`](ASSEMBLY_INTEGRITY_A2.md)) |
| A3 / F9 residual | F9 baseline now uses `is_false_enriched_body` (not cookie ILIKE); Q3c **F9=0.000** | done |
| A4 clipping thin | `assembly_integrity_a4_handoff.py --clip-limit 200` | clipping_share **0.023 → 0.226** (519/2297) |
| Hand F4 | [`HAND_F4_SCORING_SHEET.md`](HAND_F4_SCORING_SHEET.md) n=20 sheet | awaiting human scores (proxy still ~2.5) |
| Deploy hygiene | `deploy_to_widow.sh` excludes `news-intelligence-kit/` + `infrastructure/cron.d/` | done |

## Out of scope (still parked)

- Packages as binder / membership merges
- Domain-as-routing / global FTM
- On-read briefing LLM
- Attach score floor retunes
