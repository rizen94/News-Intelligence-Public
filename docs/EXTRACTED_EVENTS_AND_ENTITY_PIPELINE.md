# Extracted events vs entities — pipeline trace

There are **two different “events” concepts** in the product:

| Concept | Storage | UI / API |
|--------|---------|----------|
| **Extracted (timeline) events** | `public.chronological_events` | Domain **Extracted Events** page, `GET /api/{domain}/events`, story timelines |
| **Tracked (investigation) events** | `intelligence.tracked_events` | Investigate flows, dashboard count in some views — see [EVENTS_ZERO_AND_HOW_TO_POPULATE.md](./EVENTS_ZERO_AND_HOW_TO_POPULATE.md) |

This note traces **chronological / extracted** events and how they relate to **entity extraction**.

---

## When are extracted events created?

Automation phase **`event_extraction`** (`_execute_event_extraction_v5` in `api/services/automation_manager.py`):

1. Runs in **analysis step 3** of the v8 pipeline (after `collection_cycle` opens the analysis window), together with deduplication and timeline/editorial phases.
2. For each domain schema (`politics`, `finance`, `science_tech`), selects up to **30** articles per run that satisfy **all** of:
   - `timeline_processed = false` (column must exist on `{schema}.articles` — apply migration **177** if missing: `api/scripts/run_migration_177.py`)
   - `content` present and **length > 100**
   - `processing_status = 'completed'` **or** `enrichment_status IN ('completed', 'enriched')`
3. Calls **`EventExtractionService`** (LLM) and **`save_events`** → inserts into **`public.chronological_events`**.
4. Marks the article `timeline_processed = true` (and stores `timeline_events_generated` — column must exist on domain `articles`; migration **178**: `api/scripts/run_migration_178.py`).

So if **no articles pass those gates**, or **`event_extraction` never runs**, or the **LLM fails**, the Extracted Events page can stay at **0** even though RSS collection is healthy.

**Entity extraction** (`entity_extraction` phase, step 0) fills **`{schema}.article_entities`**. It is **not** a hard prerequisite for `event_extraction` in code, but if articles never reach `processing_status` / enrichment completed, **both** entity and event phases may see no useful work. If the **`article_entities`** table is missing in a domain schema, run migration **177** (idempotent) or **138** to create it.

**Poll script note:** `poll_extracted_events_and_pipeline.py` uses `information_schema.tables` to detect **`article_entities`** (not column names); upgrade the script if you pull an older copy that incorrectly checked columns.

---

## Poll the database (recommended)

From the repo root:

```bash
PYTHONPATH=api uv run python scripts/poll_extracted_events_and_pipeline.py
```

The script prints:

- Total and per-domain counts in `chronological_events`
- Approximate **eligible article backlog** for event extraction (same rules as automation)
- **`article_entities`** footprint per domain (entity generation signal)
- Recent **`automation_run_history`** rows for `event_extraction`, `entity_extraction`, `content_enrichment`, `collection_cycle`, etc. (requires migration **161**)

Use that output to see whether the gap is **no runs**, **no eligible articles**, **already processed** (`timeline_processed`), or **DB/LLM errors**.

---

## Manual run (validate LLM → DB commits)

1. Apply migrations **177** and **178** if verify script reports gaps:
   `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py`
2. Run extraction for one eligible article and print before/after row counts:
   ```bash
   PYTHONPATH=api uv run python scripts/run_event_pipeline_manual.py --domain politics --limit 1
   ```
   Use `--dry-run` to call the LLM only (no inserts). Requires **Ollama** (same as the API).
3. Or enqueue the automation phases (API must be up):
   ```bash
   curl -s -X POST "http://localhost:8000/api/system_monitoring/monitoring/trigger_phase" \
     -H "Content-Type: application/json" -d '{"phase":"event_extraction"}'
   curl -s -X POST "http://localhost:8000/api/system_monitoring/monitoring/trigger_phase" \
     -H "Content-Type: application/json" -d '{"phase":"event_deduplication"}'
   ```

**Why deduplication shows `checked=0`:** `event_deduplication` only scans existing rows in `public.chronological_events` with `canonical_event_id IS NULL`. Until extraction inserts at least one row, dedup legitimately does nothing.

## Manual checks

- **API / Monitor:** `event_extraction` and `entity_extraction` completion in the last 24h.
- **Logs:** errors containing `Event extraction failed`, `Event extraction skipped`, or LLM timeouts during `event_extraction`.
- **Ollama / LLM:** event extraction uses the shared LLM service; if the model is down, runs may complete with zero inserts or errors.

---

## Related docs

- [EVENTS_ZERO_AND_HOW_TO_POPULATE.md](./EVENTS_ZERO_AND_HOW_TO_POPULATE.md) — **tracked** events (`intelligence.tracked_events`)
- [AUTOMATION_AND_LAST_24H_ACTIVITY.md](./AUTOMATION_AND_LAST_24H_ACTIVITY.md) — what ran recently
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — DB connection and services
