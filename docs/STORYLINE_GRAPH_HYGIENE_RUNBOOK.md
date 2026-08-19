# Storyline / graph hygiene operator notes (2026-07-20)

Follow-up after mega prune (`Ongoing: WHAT`).

## Results (2026-07-20)

| Step | Result |
|------|--------|
| Pairwise merge gate | Shipped: `assess_storyline_pair_merge_coherence` in consolidation + `merge_storylines_by_ids` |
| Kitchen-sink audit | legal **3651** flagged (`title_amid_join`); membership dry-run scored 953, queued ~1002 actions |
| Cross-domain mega-bags | **0** rows with `cardinality(event_ids) > 12` (already clean) |
| Graph link drift | **25941** eligible stale/weak active links (dry-run count only; no mass quarantine this pass) |
| Chronicle hygiene | dry-run 20 events OK |
| Mega prune `--apply` | archived/renamed junk megas across domains; second pass removed `Ongoing: Keywords/Entities` junk renames |
| Membership pilot | `STORYLINE_MEMBERSHIP_REVIEW_ENABLED=true` + `DRY_RUN=true` on Widow |

## Scripts

| Script | Purpose |
|--------|---------|
| `api/scripts/audit_kitchen_sink_storylines.py` | Flag large incoherent storylines; `--apply` runs membership dry-run |
| `api/scripts/run_storyline_core_prune.py` | **Core dissimilar prune** (Pillar B) for one storyline; dry-run default |
| `api/scripts/purge_cross_domain_mega_bags.py` | Delete `cross_domain_correlations` with `cardinality(event_ids) > 12` |
| `api/scripts/run_graph_link_drift_dry_run.py` | Count/rescore stale weak graph links |
| `api/scripts/hygiene_event_chronicles.py` | Chronicle off-topic cleanup |
| `api/scripts/prune_bad_mega_storylines.py` | Placeholder/leak/generic mega archive |
| `api/scripts/repair_duplicate_mega_storylines.py` | Dup megas + finance bad-title renames |

## Core dissimilar prune (pre-synthesis gate)

Wired in `content_refinement_queue_service._ensure_core_prune_before_synthesis`
when `STORYLINE_CORE_PRUNE_ENABLED=true` (default) and outlier count ≥
`STORYLINE_CORE_PRUNE_OUTLIER_GATE` (default 5) on megas
(`STORYLINE_CORE_PRUNE_MEGA_ARTICLES`, default 50).

Kitchen-sink **Global Update** / meta mega bodies and **LIVE UPDATES** /
**Ongoing:** titles are excluded from core tokens so the storyline **title**
remains the anchor (e.g. politics **3570** Nepal → core `{nepal}`).

Pre-synthesis gate lives in
`content_refinement_queue_service._ensure_core_prune_before_synthesis`
(defaults on via `STORYLINE_CORE_PRUNE_*` in `configs/env.example`).

```bash
# Dry-run (safe) — from repo root with prod DB env loaded
PYTHONPATH=api python3 api/scripts/run_storyline_core_prune.py \
  --domain politics --storyline-id 3570

# Limited apply (default max 40 unlinks/pass; raise for one-shot catch-up)
PYTHONPATH=api python3 api/scripts/run_storyline_core_prune.py \
  --domain politics --storyline-id 3570 --apply --max-unlinks 200
```

Do **not** mass-apply on Iran LIVE UPDATES (~8k) without an explicit plan
(dry-run may show thousands of unlinks; keep capped passes only).
Membership review still picks megas via `STORYLINE_MEMBERSHIP_MIN_ARTICLE_COUNT`
(default 50).

**Deploy note:** ship `storyline_core_prune_service.py` + the CLI to Widow
`/opt/news-intelligence` before relying on the pre-synth gate; restart API
only when ready for automation to pick it up.

## Membership pilot (no global hard-unlink)

Keep `STORYLINE_MEMBERSHIP_REVIEW_DRY_RUN=true`. Review queued rows in
`intelligence.storyline_membership_actions` / UI Membership tab before approving.

```bash
PYTHONPATH=api python3 -c "
from services.storyline_membership_review_service import review_storyline_membership
print(review_storyline_membership('legal', 3651, dry_run=True))
"
```

## Prevention shipped

- Pairwise merge coherence gate (`assess_storyline_pair_merge_coherence`)
- Kitchen-sink heuristic (`assess_kitchen_sink_risk` / `title_amid_join`)
- Mega gates + legal discovery thresholds from prior repair
- Core dissimilar prune + title-anchored signature for Global Update bags
