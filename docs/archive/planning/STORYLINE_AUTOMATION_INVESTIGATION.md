# Storyline Automation Investigation

**Purpose:** Clarify how storyline automation assembles data into narratives and what was fixed for v8.

## Components

| Component | Role | When it runs |
|-----------|------|----------------|
| **Storyline automation** (`storyline_automation` phase) | Finds and links articles to storylines (RAG + entity search). Can store suggestions or auto-add (by `automation_mode`). | Scheduler; per-domain, up to 5 automation-enabled storylines per run. |
| **Storyline processing** (`storyline_processing` phase) | Generates **narratives**: analysis summary and seeds `editorial_document` (lede, analysis, developments). | Scheduler; was public-only, **now runs per domain** (fix below). |
| **Editorial document generation** (`editorial_document_generation`) | Full editorial documents from content synthesis. | Scheduler. |
| **RAG enhancement** (`rag_enhancement` phase) | Enriches storylines with Wikipedia/GDELT context; writes to `storyline_rag_context`. | Scheduler; still uses legacy “all storylines” (public) for listing. |

## What was wrong

1. **Storyline processing was public-only**  
   It used `get_storyline_service().get_all_storylines()` from `api/services/storyline_service.py`, which queries **unqualified** `storylines` (i.e. `public.storylines`). With domain silos (`politics`, `finance`, `science_tech`), real storylines live in those schemas; `public.storylines` is empty or legacy. So **no domain storyline ever got a generated summary or seeded editorial_document** from the scheduler.

2. **RAG enhancement**  
   Same pattern: it uses `get_all_storylines()` (public only). So RAG enhancement never ran for domain storylines. Fixing this properly would require the RAG service to be domain-aware (schema-qualified `storyline_rag_context` or domain in the key). Left for follow-up.

3. **Automation-enabled count**  
   The batch path of storyline automation only runs discovery for storylines with `automation_enabled = true`, up to 5 per domain. If no storyline has automation enabled, the phase runs but adds no articles. **Enable automation on storylines** (UI or set `automation_enabled = true` when creating/discovering) so they receive new articles over time.

## What was fixed

- **`_execute_storyline_processing`** in `api/services/automation_manager.py` now:
  - Loops over **domains** `politics`, `finance`, `science_tech`.
  - For each domain, loads **active storylines that have articles** from `{schema}.storylines`.
  - Uses **domain-aware** `domains.storyline_management.services.storyline_service.StorylineService(domain=...)` to generate the summary (writes `analysis_summary` in that schema).
  - Seeds **editorial_document** in the **same schema** when missing, using the returned summary and a schema-qualified `UPDATE {schema}.storylines`.

So narrative assembly (summary + editorial_document seed) now runs for **politics, finance, and science_tech** storylines, not only public.

## How to verify

1. **Counts and automation**  
   Run:
   ```bash
   PYTHONPATH=api .venv/bin/python scripts/investigate_storyline_automation.py
   ```
   Check per-schema: total storylines, `automation_enabled`, with `editorial_document`, with `analysis_summary`, with articles.

2. **After a run of storyline_processing**  
   In each domain schema, storylines that have articles but no (or short) summary should get `analysis_summary` and, if they had no editorial_document, a seeded `editorial_document` (lede, analysis, `generated_at`).

## Enabling automation on storylines

- **New storylines from discovery**  
  Plan A1: when saving discovered storylines, set `automation_enabled = true` (see `api/services/ai_storyline_discovery.py`).
- **Existing storylines**  
  Enable in the UI (storyline automation settings) or via SQL, e.g.:
  ```sql
  UPDATE politics.storylines SET automation_enabled = true, automation_mode = 'suggest_only' WHERE id = <id>;
  ```

## Reference

- Automation schedule: `api/services/automation_manager.py` (`storyline_automation`, `storyline_processing`).
- Domain storyline service: `api/domains/storyline_management/services/storyline_service.py` (`generate_storyline_summary`).
- Article discovery: `api/services/storyline_automation_service.py` (`discover_articles_for_storyline`).
- Investigation script: `scripts/investigate_storyline_automation.py`.
