# UI and pipeline audit guide

How the web UI surfaces **provenance**, **pagination**, and **human grouping judgments** so you can validate reliability while the backend collects data.

## Pipeline layers for weekly audits

Use a consistent top-down pass so everyone reviews the same artifacts in the same order:

1. **Ingest** — source freshness and collection health (`rss_feeds`, monitor).
2. **Corpus** — article/document capture quality (`articles`, processed documents).
3. **Interpretation** — extracted entities/topics/claims and quality metadata.
4. **Story and time** — storyline linking and timeline event integrity.
5. **Cross-cutting** — contexts/entity dossiers/tracked events consistency.
6. **Outputs** — briefings/synthesis cite the same underlying records.

## Discover pagination

- **Contexts** and **entity profiles** on **Discover** use `limit` / `offset` with a **total** count from the API (`GET /api/contexts`, `GET /api/entity_profiles`).
- Use pagination controls to audit large corpora without loading everything at once.

## Provenance panels

Shared **Provenance & pipeline** cards appear on:

- **Article** detail — IDs, domain, source, dates, quality score, ML status, original URL, optional feed metadata.
- **Context** detail — context id, domain, source type, linked article link, metadata URLs/feeds.
- **Storyline** detail — storyline id, status, article count, timestamps, ML status, link to timeline.
- **Story timeline** — event counts, source diversity, time span, build time; each timeline event can show **extraction method** (e.g. `ml`, `gdelt`) when expanded.

Timeline events are loaded from `public.chronological_events` (non-canonical rows only); see `TimelineBuilderService`.

## Storyline audit and empty timelines

- **API:** `GET /api/{domain}/storylines/{id}/audit` — article count vs `chronological_events`, timeline empty flag, automation/doc touch metadata.
- **UI:** Storyline detail → **Storyline audit** card links to the timeline. An **empty** timeline is an informational state (not a hard error); narrative features that need events stay disabled until data exists.
- **Events list:** Domain **Extracted Events** table shows **extraction method**, **dedup role / canonical id**, and a **source article** link when the API provides them (`list_domain_events`).

## Cross-entity matrix (context ↔ article ↔ topic/storyline)

- **UI:** Context detail → card listing **topics** and **storylines** that reference the **same linked article** as the context (IDs for manual checks).
- **API:** `GET /api/contexts/{id}` includes optional `related: { topics, storylines }`.

## Synthesis provenance and versions

- **UI:** Storyline detail synthesis dialog — collapsible **sources used** (article ids / source list), **document version** chip, **generated** time (`created_at` / cached `synthesized_at`).

## Weekly audit checklist (in-app)

- **Route:** `/{domain}/audit-checklist` — short checklist with links to **Discover**, **Articles**, **Monitor**, and this guide.

## Two-week reliability run (recommended cadence)

- **Week 1:** Focus on ingest/corpus/storyline coverage. Track empty timelines, source freshness, and article-to-storyline link rates.
- **Week 2:** Focus on cross-entity and synthesis trust. Verify context-topic-storyline agreement and inspect synthesis source IDs/version timestamps.
- Record discrepancies with IDs (article, context, storyline, event) so they are reproducible in follow-up fixes.

## Context grouping feedback (migration 174)

Analysts can record whether a **context** belongs with a **topic**, **storyline**, **pattern**, or **other** grouping:

- **UI:** Context detail → **Grouping audit** card.
- **API:** `POST /api/contexts/{id}/grouping_feedback`, `GET /api/contexts/{id}/grouping_feedback`.
- **DB:** `intelligence.context_grouping_feedback`.

Apply migration once:

```bash
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_174.py
```

Judgments (`belongs`, `does_not_belong`, `unsure`) are stored for audits and future tuning; they do not automatically retrain models yet.

## Related docs

- [SOURCES_AND_EXPECTED_USAGE.md](./SOURCES_AND_EXPECTED_USAGE.md) — what feeds the pipeline.
- [DATA_FLOW_ARCHITECTURE.md](./DATA_FLOW_ARCHITECTURE.md) — cascade from articles to intelligence.
- [WEB_PRODUCT_DISPLAY_PLAN.md](archive/planning_incubator/WEB_PRODUCT_DISPLAY_PLAN.md) — dashboard / navigation intent (incorporation candidate).
