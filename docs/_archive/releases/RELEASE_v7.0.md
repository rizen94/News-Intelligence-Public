# Release v7.0 — Full-Text, Documents, Auto-Synthesis

**Version**: 7.0.0  
**Status**: **Completed**  
**Date**: March 2026

## Summary

v7 adds full-text article enrichment, automated document collection from government and academic sources, scheduled storyline and briefing synthesis, **automatic storyline discovery**, **entity dossiers**, and **batch-size-aware backlog logic** so the pipeline runs hands-off and surfaces reporter-quality intelligence.

---

## New and Changed

### Full-text article enrichment
- **Content enrichment phase** (every 10 min): Fetches full article body via **trafilatura** for articles with short or missing content.
- After enrichment: resets `entities`, re-queues topic extraction, and updates the linked **intelligence.contexts** row so downstream uses full text.
- **context_processor_service**: New `update_context_content_for_article()` to refresh context content after enrichment.

### Document pipeline
- **Document collector** (every 6 h): Discovers PDFs from CRS, GAO, CBO (RSS), and arXiv (API). Config: `document_sources.automated_sources` in `orchestrator_governance.yaml`.
- **Document processing** (every 30 min): Processes pending PDFs (download, pdfplumber, sections, entities, key findings). Processed **document sections** are written to **intelligence.contexts** (`source_type='pdf_section'`, `domain_key='documents'`) so they join claim extraction and synthesis.
- **No dependency on document_collection**: Manually added documents (via web “Add document”) are processed on the next cycle without waiting for the 6‑hour collector.
- **Process now**: Web “Processed documents” page has a **Process now** button that calls `POST /api/processed_documents/batch_process` to run processing immediately.

### Auto synthesis and intelligence
- **Storyline synthesis** (every 60 min): Runs deep content synthesis for storylines with 3+ articles and no synthesis yet (up to 2 per domain per run).
- **Daily briefing synthesis** (every 4 h): Runs breaking-news synthesis per domain for the briefing page.
- **Content synthesis service**: Includes processed documents, entity positions, and cross-domain correlations in storyline and domain context for LLM prompts.
- **Editorial documents**, **narrative threads**, **dossier narratives**, and **pattern reports** all consume this enriched context.

### Automatic storyline discovery
- **storyline_discovery** (Phase 6, every 4 h): **AIStorylineDiscovery** runs per domain (politics, finance, science-tech) over the last 48 hours of articles. Clusters by semantic + entity + temporal similarity, generates titles/descriptions via LLM, and **creates new storylines** (up to 10 per domain) with status `active` (breaking) or `suggested`. Background intelligence can now create and track storylines without manual input.

### Entity dossiers and Top Entities
- **Entity Dossier page** (`/:domain/investigate/entities/:entityId/dossier`): Biographic intelligence view — narrative summary, positions/stances, article timeline, relationships, patterns. Uses `GET /api/synthesis/entity/{id}` and optional **Build dossier** / **Recompile**.
- **Top Entities** tab on Entities list: Ranked by mention count (3+), filter by type; each row links to the entity dossier.
- **Entity Detail** page: **View Full Dossier** button links to the dossier view.
- **contextCentric API**: `getEntitySynthesis`, `getEntityDossier`, `compileEntityDossier`, `getEntityPositions`, `batchProcessDocuments`.

### Backlog logic (orchestrator)
- **Backlog** is redefined as “more work than one batch can handle,” not “any pending item.”
- **backlog_metrics**: `get_all_backlog_counts()` returns **pending − batch_size** per task (0 = keeping up). `get_all_pending_counts()` returns raw pending (used for SKIP_WHEN_EMPTY so tasks with 1+ item still run).
- **BATCH_SIZE_PER_TASK** defines per-task batch sizes (e.g. content_enrichment 60, context_sync 100, document_processing 10). Interval shortening and priority boosting apply only when true backlog > 0 (or > BACKLOG_HIGH_THRESHOLD).

### Extraction and LLM
- **Entity extraction**: Prefers articles with `LENGTH(content) >= 500` (or older than 2 h); content limits raised to 12k/10k chars.
- **Topic extraction**: Content limit raised from 2k to 5k chars (topic_clustering_service, llm_topic_extractor, advanced_topic_extractor).
- **Global LLM semaphore** in `llm_service`: Async Ollama callers share a concurrency cap (3).

### Phase ordering
- **content_enrichment** is a dependency for **context_sync**, **entity_extraction**, and **topic_clustering** so extraction runs after enrichment when possible.
- **document_processing** has no dependency on document_collection so manual documents process immediately.

---

## Files Added

- `api/services/article_content_enrichment_service.py` — trafilatura enrichment + re-extraction triggers.
- `api/services/document_collector_service.py` — CRS, GAO, CBO, arXiv collectors.
- `web/src/pages/Investigate/EntityDossierPage.tsx` — entity dossier (biographic) view.
- `web/src/pages/Investigate/ProcessedDocumentDetailPage.tsx` — processed document detail (if added in v7).

---

## Config

- `api/config/orchestrator_governance.yaml`: `document_sources.automated_sources: [crs, gao, cbo, arxiv]`.

---

## Dependencies

- **trafilatura** (≥1.6.0) for full-text extraction from article URLs.

---

## When to expect events and storylines

**From a cold start** (orchestrator and RSS running):

| What | When |
|------|------|
| **Tracked events** (event_tracking) | **~30–45 min** — After first RSS run, content_enrichment (5 min), then context_sync (15 min), then event_tracking (15 min). |
| **v5 events** (chronological_events) + **story continuation** | **~30–60 min** — Chain: content_enrichment → entity_extraction (5 min) → event_extraction (5 min) → event_deduplication (10 min) → story_continuation (10 min). Events appear in Briefings/Investigate once this chain has run; story_continuation links them to *existing* storylines. |
| **Auto-created storylines** | **Up to 4 hours** — `storyline_discovery` runs every **4 hours** and creates new storylines from the last 48 hours of articles (clustering + LLM titles). So the first batch of auto storylines appears at the first 4‑hour boundary after start. |
| **Manual storylines** | **Immediate** — Create from Story Management or Convert topic → storyline; storyline_automation then adds articles every 5 min. |

So: **events** (and event–storyline linking) typically within about **an hour**; **auto storylines** at the next **4‑hour** discovery run. If RSS or enrichment is delayed (e.g. backlog), events and storylines will shift accordingly.

---

## Notes

- Storyline synthesis expects `synthesized_content` (and optionally `synthesized_at`) on `storylines`; add columns via migration if missing.
- Document processing creates one context per PDF section; `domain_key='documents'` for all.
- Status endpoint (`/api/orchestrator/status` or equivalent) now exposes both `pending_counts` and `backlog_counts`.
