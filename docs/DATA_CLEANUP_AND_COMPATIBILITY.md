# Data Cleanup and Compatibility

After major schema updates (v4 domain silos, v5 events, context-centric, v6 quality-first, etc.), you may have old records that either work fine with the new system or need pruning. This doc summarizes **what the system handles gracefully**, **what to check**, and **when cleanup is reasonable**.

---

## v6: Do you need to clear anything?

**No.** You do **not** need to clear or truncate existing database content to “make room” for v6 or to avoid conflicts.

- **v6 is additive:** New columns use `ADD COLUMN IF NOT EXISTS … DEFAULT …`, so existing rows get defaults (e.g. `editorial_document = '{}'`, `document_status = 'draft'`). New intelligence tables (`intelligence.contexts`, `tracked_events`, `entity_dossiers`, `processed_documents`, etc.) start empty and are filled by the pipeline.
- **Existing articles and storylines** are used as-is; the pipeline will backfill `ml_data`, entity extraction, and (over time) `editorial_document` and event chronicles.
- **entity_canonical** (per-domain) already exists; v6 adds alias population and resolution. Rows with NULL or empty `aliases` are fine and get populated by the entity organizer.
- **Optional hygiene only:** Run the diagnostic below and, if you want, clean orphan join rows, prune very old pipeline/log data, and optionally reclaim space from legacy `public.*` tables. That is for health and space, not a v6 requirement.

## Run the diagnostic (read-only)

From the project root:

```bash
.venv/bin/python api/scripts/diagnose_db_legacy_data.py
```

The script reports:

- **Column presence** for `politics.articles` (so you can see if you have `feed_id` vs `rss_feed_id`, `category`, `source_name`, `entities`, `topics`, etc.).
- **NULL counts** for important columns (`entities`, `topics`, `created_at`) per domain.
- **Orphan rows** in join tables (e.g. `storyline_articles` pointing to deleted articles or storylines).
- **Pipeline / log table sizes** and how many rows are older than 90 days (pruning candidates).
- **Public schema leftovers** (e.g. rows still in `public.articles` after migration 125).

No data is modified.

---

## What the system handles gracefully

- **Missing or NULL JSONB:** Most code uses `.get('entities', [])`, `.get('topics', [])` or equivalent. RAG retrieval explicitly handles `entities`/`topics` as null, list, or JSON string. So **NULL or missing `entities`/`topics`** in articles generally do not break the app; they are treated as empty.
- **New columns added with DEFAULT:** Migrations that use `ADD COLUMN ... DEFAULT ...` backfill existing rows. Old rows get the default and do not need pruning for those columns.
- **Pipeline traces:** The pipeline status API uses whatever columns exist (`success`, `error_stage`, etc.). Old traces may have different shapes but are still counted; the system does not assume new fields on old rows.
- **Orchestrator state:** Decision log and status live in SQLite/separate storage; PostgreSQL legacy data does not directly affect them.

---

## Where problems can appear

1. **Column name drift**
   - **Articles:** Some code paths expect `feed_id` and `category` (e.g. `api/domains/news_aggregation/services/article_service.py`). The v4 base schema uses `rss_feed_id` and does not define `category`. If your domain tables were created from an older schema, you may have `feed_id`; if from v4 only, you might have `rss_feed_id` and no `category`. The diagnostic lists columns so you can align code or add compatibility columns/views.
   - **Intelligence/RAG:** Some services query `source_name` and `extracted_entities` on articles. The v4 schema has `source_domain` and `entities` (JSONB). If those columns are missing, those code paths can fail. Again, the diagnostic shows what is present.

2. **Orphan join rows**
   - `storyline_articles` rows whose `article_id` or `storyline_id` no longer exist can cause JOINs to drop rows or, if FKs are strict, cause constraint errors. The diagnostic counts such orphans; **cleaning is reasonable** (delete orphan join rows).

3. **Very old pipeline / log data**
   - Old `pipeline_traces`, `pipeline_checkpoints`, `pipeline_error_log` are not required for current behavior. Pruning records older than 90 days (or another retention window) is **reasonable** and reduces table bloat.

4. **Public schema after migration 125**
   - Migration 125 moved data into domain schemas. If `public.articles` / `public.storylines` / `public.rss_feeds` still have rows, they are legacy. The app uses domain schemas; **leaving them is harmless** unless you need to free space, in which case pruning or dropping after a backup is reasonable.

---

## Recommended actions

| Finding | Action |
|--------|--------|
| Orphan `storyline_articles` (or similar) | **Delete** orphan rows so JOINs and FKs stay consistent. Prefer a small script that deletes only rows where the referenced id does not exist. |
| Many NULL `entities`/`topics` | **No action required** for compatibility; the app treats them as empty. Optionally backfill later with an extraction job. |
| `feed_id` vs `rss_feed_id` / missing `category` | **Align** either by adding compatibility columns/views or by updating the article service to use the columns that exist (see diagnostic output). |
| `source_name` / `extracted_entities` missing | **Align** intelligence/RAG code to use `source_domain` and `entities`, or add columns/views if you need the old names. |
| Large pipeline/log tables with many old rows | **Prune** (e.g. delete `pipeline_traces` older than 90 days and related checkpoints/logs if applicable). Run during low traffic; consider a retention policy. |
| Rows left in `public.*` after 125 | **Optional** backup then drop or truncate if you want to reclaim space; not required for correctness. |

---

## Optional cleanup script (prune + normalize)

If you want to add a **safe cleanup script** that:

- Deletes orphan `storyline_articles` (and optionally other join tables),
- Normalizes NULL `entities`/`topics` to `'[]'`/`'{}'` where desired,
- Prunes `pipeline_traces` (and related tables) older than N days,

it can be added under `api/scripts/` and run manually or on a schedule. The diagnostic script is intentionally **read-only** so you can run it anytime without risk; any destructive cleanup should be a separate, opt-in script with clear comments and (if possible) a dry-run mode.

---

## Summary

- **Record cleaning is reasonable** for: orphan join rows, very old pipeline/log data, and (optionally) public schema leftovers.
- **The system already handles** missing/NULL JSONB and old pipeline trace shapes in most places.
- **Run the diagnostic first** to see your actual columns, nulls, and orphans; then fix schema/code drift and run targeted cleanup if you want.
