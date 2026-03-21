# RAG v8 and Article Discovery

This document describes the v8 RAG alignment (domain-aware retrieval and storage) and the two discovery processes: **recent incoming → existing** and **existing → enrichment** (full history).

## RAG v8 alignment

### Domain-aware retrieval

- **Retrieval** (`api/services/rag/retrieval.py`): `retrieve_relevant_articles(..., domain=..., filters=...)`
  - When `domain` is set (e.g. `politics`, `finance`, `science-tech`), search runs against that domain’s schema: `{schema}.articles` (e.g. `politics.articles`).
  - When `filters.get("full_history")` is `True` (or no `date_from`/`date_to`), **no date filter** is applied; the search uses the entire article history in that schema.
  - `exclude_article_ids` in `filters` excludes those IDs from results (e.g. articles already linked to the storyline).

### Domain-aware RAG context storage

- **Base RAG** (`api/services/rag/base.py`):
  - `enhance_storyline_context(..., domain=...)` and `_save_rag_context(..., domain=...)` write to **`intelligence.storyline_rag_context`** keyed by `(domain_key, storyline_id)`.
  - `get_rag_context(storyline_id, domain=...)` reads from that table when `domain` is set.
  - Legacy behaviour: when `domain` is `None`, the service still uses the legacy `storyline_rag_context` table (public schema) for backward compatibility.

### Migration

- **169_storyline_rag_context_by_domain.sql** creates `intelligence.storyline_rag_context` with `(domain_key, storyline_id)` and unique constraint. Apply with:
  - `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_169.py`

### Automation

- **RAG enhancement** (`api/services/automation_manager.py` → `_execute_rag_enhancement`): Runs per domain (`politics`, `finance`, `science_tech`), loads active storylines and their articles from the domain schema, and calls `enhance_storyline_context(..., domain=domain)`. Stored context is keyed by `(domain_key, storyline_id)` in `intelligence.storyline_rag_context`.

---

## Two discovery processes

Discovery can suggest related articles/contexts from:

1. **Recent incoming data** — match new articles to existing storylines and dossiers.
2. **Full history** — enrich existing storylines and dossiers with previously collected data and past events.

### Process A: Recent incoming → existing (storyline automation)

- **Purpose:** Use **recent** incoming data and compare it to existing storylines (and dossiers) to suggest new material.
- **Implementation:**
  - Task: **`storyline_automation`** (interval e.g. 5 minutes).
  - `StorylineAutomationService.discover_articles_for_storyline(..., enrichment_mode=False)` (default).
  - RAG retrieval uses a **date range** (e.g. `date_range_days`, default 90). No `full_history` flag.
  - Domain is passed through so search is against the correct `{schema}.articles`.
- **Behaviour:** For each automation-enabled storyline, discovery suggests articles from the configured recent window that relate to the storyline; results can be added to the storyline or reviewed.

### Process B: Existing → enrichment (full-history)

- **Purpose:** Take **existing** storylines (and in future dossiers) and enrich them with **previously collected data and past events** from the entire database.
- **Implementation:**
  - Task: **`storyline_enrichment`** (interval e.g. 12 hours).
  - `StorylineAutomationService.discover_articles_for_storyline(..., enrichment_mode=True)`.
  - When `enrichment_mode=True`, settings get `full_history=True`; RAG retrieval is called **without** a date filter, so the search runs over the **full** article history in that domain’s schema.
  - Same domain-aware retrieval: `{schema}.articles` for the storyline’s domain.
- **Behaviour:** For each automation-enabled storyline (with at least one article), discovery suggests related articles from **all time**; these can be linked to the storyline to enrich it with past context and events.

### Summary

| Process | Task | Mode | Time scope | Use case |
|--------|------|------|------------|----------|
| A | `storyline_automation` | `enrichment_mode=False` | Recent (e.g. 90 days) | Match new articles to existing storylines |
| B | `storyline_enrichment` | `enrichment_mode=True` | Full history | Enrich storylines with past articles/contexts |

### Running full-history enrichment manually

- **Single storyline:** Trigger a `storyline_enrichment` task with metadata `storyline_id` and `domain` (e.g. via governor or API that enqueues the task).
- **Batch (all domains):** The scheduler runs `storyline_enrichment` without metadata; the executor runs enrichment for up to 3 automation-enabled storylines per domain (with at least one article), each with `force_refresh=True` and `enrichment_mode=True`.

### Per-storyline override

- Storyline-level **automation_settings** can include `"full_history": true`. When that storyline is processed by **storyline_automation** (Process A), RAG discovery for that storyline will still use full-history search because `full_history` is merged from settings into the filters passed to retrieval.

---

## References

- RAG retrieval: `api/services/rag/retrieval.py`
- RAG base (enhance/save/get): `api/services/rag/base.py`
- Storyline automation and discovery: `api/services/storyline_automation_service.py` (`_rag_discover_articles`, `discover_articles_for_storyline`)
- Automation manager: `api/services/automation_manager.py` (`_execute_storyline_automation`, `_execute_storyline_enrichment`, `_execute_rag_enhancement`)
- Migration: `api/database/migrations/169_storyline_rag_context_by_domain.sql`
