# Operator decisions (event-core)

Locked for the event-core assembly rebuild (2026-07-24).

| Question | Decision |
|----------|----------|
| Deliverable | Implementation roadmap with first slice (not docs-only) |
| Event identity home | Elevate **`intelligence.tracked_events`** as megathread; domain storylines are **facet projections** |
| Surface of record | **Membership is evidence** (I2). Keeper-as-dirt-filter forbidden. Summaries select among typed members; RAG is labeled background only |
| Multi-membership | One TE per event an article reports; facets allow multi-domain *angles* on that TE |
| Reprocessing | Forward-only + selective gold rare-anchor backfill; **no** full corpus re-UIE / storyline flush |
| Chemistry / graph | Non-arbitrating for evidence membership until Phase 4 reconcile |
| Rejected shortcut | Mint TE + graph `same_event` links while leaving `storyline_articles` absorb alone |

## Feature flag

`EVENT_CORE_MEMBERSHIP_ENABLED=true` (or `FEATURE_OVERRIDE_EVENT_CORE_MEMBERSHIP=true`) gates founding-before-absorb and TE typed membership writes.

Also: `EVENT_CORE_SPLIT_APPLY=true` to apply split hygiene; `EVENT_CORE_SPLIT_UNLINK=true` to unlink from bags when splitting.

## First-slice scope

**Quality type** (cyclosporiasis is an *example*, not the scoreboard): distinctive identity (rare name / instrument ID / bounded episode), multi-article co-reference, owns a megathread, domain-agnostic facets. Founding paths: seed examples + instrument IDs (NCT / docket / FDA / EPA) + morphological rare names (`*iasis`, uncommon `*virus`). Metrics score all anchored TEs on multi-article / cross-domain / anti-mega — not cyclosporiasis alone. Legacy bags remain readable but are not event SSOT.

## Ops scripts

```bash
# Quality-type scoreboard (safe)
PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py

# Probe founding-path kinds in recent articles
PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --probe-kinds

# Quality-type scan founding (not cyclosporiasis-only)
EVENT_CORE_MEMBERSHIP_ENABLED=1 PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --quality-scan --apply

# Illustrative example backfill (optional)
EVENT_CORE_MEMBERSHIP_ENABLED=1 PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --backfill --apply

# Split proposals (dry-run)
EVENT_CORE_MEMBERSHIP_ENABLED=1 PYTHONPATH=api python3 api/scripts/run_event_core_split_hygiene.py
```
