# Release: Dossier Pipeline Fixes and Wire-Ins

**Date:** March 2026  
**Scope:** Automation and pipeline fixes from [DOSSIER_REMAINING_GAPS_PLAN.md](DOSSIER_REMAINING_GAPS_PLAN.md) plus wiring of previously unwired features.

---

## Summary

- **Entity position tracker** — Now runs on a schedule (every 2 hours); config kill switch added.
- **Event participant IDs** — New events get `key_participant_entity_ids` at creation; existing events are backfilled each event_tracking run (30/run).
- **Metadata enrichment** — New automation task runs every 15 minutes for domain articles (language, categories, sentiment, quality).
- **Context-centric config** — `entity_position_tracker` added to `context_centric.yaml` and `context_centric_config.DEFAULT_TASKS` with executor check.

---

## Changes

### Automation (`api/services/automation_manager.py`)

- **entity_position_tracker** — Schedule 7200s, phase 2, `depends_on: ['entity_profile_sync']`; executor calls `run_position_tracker_batch` via `run_in_executor`; respects `is_context_centric_task_enabled("entity_position_tracker")`.
- **metadata_enrichment** — New task: interval 900s, phase 2, `depends_on: ['article_processing']`; executor calls `run_metadata_enrichment_batch_for_domains(limit_per_domain=5)`.

### Event tracking (`api/services/event_tracking_service.py`)

- **`_resolve_context_ids_to_entity_profile_ids(conn, context_ids)`** — Resolves context IDs to entity_profile IDs via article_to_context → article_entities → entity_profiles (cap 20).
- **At event creation** — After inserting each new event and chronicle, resolver runs and `tracked_events.key_participant_entity_ids` is updated.
- **`_backfill_key_participants_for_event(conn, event_id)`** — Fills participant IDs from chronicle developments.
- **`backfill_key_participants_for_tracked_events(limit=30)`** — Selects events with empty participant IDs and backfills; called from `run_event_tracking_batch` after chronicle updates.

### Metadata enrichment (`api/services/metadata_enrichment_service.py`)

- **`enrich_article_for_schema(article_id, schema, title, content)`** — Domain-aware enrichment: language, categories, sentiment, quality; updates `{schema}.articles` (quality_score, sentiment_score, categories, metadata.enrichment_done).
- **`run_metadata_enrichment_batch_for_domains(limit_per_domain=5)`** — Selects articles without `metadata->>'enrichment_done'` per domain and enriches them.

### Config

- **`api/config/context_centric_config.py`** — `DEFAULT_TASKS["entity_position_tracker"] = True`.
- **`api/config/context_centric.yaml`** — `entity_position_tracker: true` under tasks.

---

## Restart

After pulling or applying these changes:

```bash
./stop_system.sh
./start_system.sh
```

This restarts the API, frontend, and background automation so the new tasks and backfill run.

---

## Related docs

- [DOSSIER_REMAINING_GAPS_PLAN.md](DOSSIER_REMAINING_GAPS_PLAN.md) — Plan and checklist (all items Done).
- [DOSSIER_PIPELINE_ORDERING_PLAN.md](DOSSIER_PIPELINE_ORDERING_PLAN.md) — Pipeline ordering and dossier compile.
- [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md) — How assembly uses contexts and quality.
