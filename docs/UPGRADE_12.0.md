# Upgrade to News Intelligence 12.0

Operator runbook for the `release/12.0` MUST + THIN cutover.

**Lab:** PopOS `News Intelligence` (`release/12.0`)  
**Prod:** Widow `/opt/news-intelligence`  
**Do not cut over Widow until PopOS pytest + dry-runs pass and reassessment says go.**

## Scope lock

| Layer | In v12.0 |
|-------|----------|
| **MUST** | Episode attach sole path; bag absorb off; EEL reads; publish escape → `closed_thin`; EDGAR/FR/CourtListener; archive/phase hygiene |
| **THIN** | Deterministic StakesGate; act-verb CE top-K kernel; reactivation → `watchlist_alerts` |
| **LAST** | LLM stakes, expectation NLP, hop engine, Edition SPA, spotlight, ntfy — **only after reassessment** |

## Migrations

| # | File | Purpose |
|---|------|---------|
| 295 | `295_episode_container_assembly.sql` | EEL + anchor class (may already be applied) |
| 296 | `296_package_evidence_briefs.sql` | Evidence briefs |
| 297 | `297_editorial_packages_closed_thin.sql` | `closed_thin` status for thin escape |

```bash
cd /opt/news-intelligence   # or lab checkout
PYTHONPATH=api python api/scripts/run_migration.py 297
PYTHONPATH=api python api/scripts/register_applied_migration.py 297 \
  --file api/database/migrations/297_editorial_packages_closed_thin.sql \
  --notes "v12 closed_thin"
```

## Environment (v12 defaults)

```bash
EPISODE_CONTAINER_ASSEMBLY_ENABLED=true
STORYLINE_AUTOMATION_AUTO_ATTACH=0
STORYLINE_ARTICLES_DUAL_WRITE=0          # EEL is membership SSOT; no SA dual-write

### Membership write freeze (v12.1+)

After the membership SSOT refactor, **all admits** go through `api/shared/membership_store.admit()` → `intelligence.event_episode_links`. The `storyline_articles` bag table is **write-frozen** (kept for rollback/audit). Migration **298** adds a `BEFORE INSERT` trigger on domain `storyline_articles` tables; only `membership_store` sets session var `ni.membership_store_write=1` during dual-write or legacy mode.

See [adr/001-membership-ssot.md](adr/001-membership-ssot.md).
NEWS_STORY_AUTO_REPUBLISH=1             # refresh published stories when events continue
NEWS_STORY_AUTO_PUBLISH_ON_GATE_PASS=1  # compose that clears StakesGate publishes
EDITORIAL_ROOM_LOOP_ENABLED=false
ASSEMBLY_PIPELINE_MODE=ordered

# Collectors (enable after dry-run)
EDGAR_COLLECTOR_ENABLED=true            # needs EDGAR_USER_AGENT
FEDERAL_REGISTER_COLLECTOR_ENABLED=true
COURTLISTENER_COLLECTOR_ENABLED=true    # needs COURTLISTENER_API_TOKEN
```

Feature registry: `episode_container_assembly`, `edgar_collector`, `federal_register_collector`, `courtlistener_collector` enabled in `api/config/features.yaml`.

## Lab sequence (PopOS)

1. Baseline rsync from Widow `/opt/news-intelligence` → lab (done for this branch)
2. Branch `release/12.0`; apply migration 297 on lab DB
3. Dry-run collectors:  
   `PYTHONPATH=api python api/scripts/run_public_data_collectors.py --source edgar,federal_register,courtlistener --dry-run`
4. Pytest: gate / escape / stakes-det / kernel-topk
5. Triage parking lot:  
   `PYTHONPATH=api python api/scripts/triage_editorial_parking_lot.py --dry-run`
6. Write reassessment note under `docs/reviews/`
7. Only then: Widow cutover

## Widow cutover (after reassessment)

1. Tag archive on Widow: `v11-pre-12.0` (or dated) on `/opt` tree
2. Stop API: `sudo systemctl stop news-intelligence-api-public.service`
3. Rsync lab `release/12.0` → `/opt/news-intelligence` (exclude `.venv`, `.env`, data)
4. Run migration 297; register ledger
5. Confirm env flags above in Infisical-rendered / local `.env` (names only in chat)
6. Start API; smoke: episode attach, collector CE row, thin close path
7. Monitor Gatus / processing progress

## Success criteria (before Widow)

- Episode gate on; bag absorb off; dual-write off
- Max-rounds → `closed_thin` (not ready_for_editor parking)
- Nut graf + walkaway required; deterministic thin path
- Filings CE rows from enabled collectors
- Reactivation writes `watchlist_alerts`
- Pytest green for gate / escape / stakes-det / kernel-topk

## Rollback

1. Stop API; restore prior `/opt` tag
2. `EPISODE_CONTAINER_ASSEMBLY_ENABLED=false` only if forced (re-opens bag paths — avoid if possible)
3. Do **not** drop `closed_thin` rows without review — status is additive

## Craft reference

See [NI_LEAD_STORY_CRAFT.md](NI_LEAD_STORY_CRAFT.md). Hub denylist: `api/shared/hub_denylist.py`.
