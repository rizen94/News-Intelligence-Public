# Release v8.0 — Full-History Data Awareness and Collect-then-Analyze Pipeline

**Version**: 8.0.0  
**Status**: **Stable** (release anchor)  
**Date**: March 2026

## Stable v8.0.0 anchor (operations)

This commit is the **stable v8** baseline for production/Widow. Beyond the scheduler and full-history work below, it includes:

- **Database resilience** — Pool-free DB reachability probe for automation; `AUTOMATION_PAUSE_WHEN_DB_DOWN`; local queue `.local/db_pending_writes` + `pending_db_flush` for `automation_run_history`; see `docs/NARRATIVE_BOOTSTRAP_AND_DB_OUTAGE.md`.
- **Storyline / event / entity** — Per-domain `story_entity_index` (migration **179**); proactive cluster → domain storyline promotion; verification scripts and `docs/STORYLINE_EVENT_ENTITY_CHAINS.md`.
- **Claims → facts** — Fixed entity resolution (invalid `display_name` / broken join); context- and canonical-aware resolver; `docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md`.
- **Entity enrichment** — Removed hard skip when backlog &gt; 1000 profiles (`ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD`).
- **Source credibility** — `orchestrator_governance.yaml` `source_credibility` wired: RSS `quality_score` + `articles.metadata`, contexts metadata, claim confidence scaling; `docs/SOURCE_CREDIBILITY.md`.
- **Migrations 168–179** — Ledger, timeline/entities, Wikipedia knowledge, analytics, science-tech RSS, `chronological_events`, `story_entity_index` per domain; runbooks in `docs/DB_PRODUCTION_MAINTENANCE_RUNBOOK.md`.
- **Verification** — `scripts/verify_pipeline_db_alignment.py`, `verify_intelligence_phases_productivity.py`, `verify_storyline_event_entity_chains.py`, `db_persistence_gates.py`.

## Summary

v8 restructures the automation scheduler into a **collect-then-analyze** two-phase cycle, adds **pipeline-ordered analysis** with time budgets and re-enqueue caps so synthesis and editorials are never starved, and expands all intelligence services to consider the **full historical dataset**. It bridges data silos (PDFs, topics, claims, dossiers) so storylines, synthesis, and fact verification use every available source.

---

## New and Changed

### Scheduler: Collect-then-analyze pipeline

- **Collection cycle** (every 2 hours): Single master task runs RSS fetch → content enrichment (drain all pending) → document collection → document processing (drain all pending) → drain **pending_collection_queue**. No analysis tasks run during this window.
- **Analysis window** (remaining ~1.5 h): Work runs in **4 pipeline steps** with time budgets:
  - **Step 1 (30 min):** Foundation — context_sync, entity_profile_sync, ml_processing, entity_extraction, metadata_enrichment
  - **Step 2 (20 min):** Extraction — claim_extraction, event_tracking, topic_clustering, quality_scoring, sentiment_analysis
  - **Step 3 (20 min):** Intelligence — entity_profile_build, entity_organizer, pattern_recognition, cross_domain_synthesis, storyline_discovery, proactive_detection, fact_verification, event_coherence_review, entity_enrichment, story_enhancement, investigation_report_refresh, etc.
  - **Step 4 (remaining time):** Output — storyline_processing, rag_enhancement, storyline_automation, story_continuation, event_extraction, event_deduplication, timeline_generation, editorial generation, dossier_compile, entity_position_tracker, storyline_synthesis, daily_briefing_synthesis, etc.
- **Re-enqueue cap:** Tasks in the old “continuous” set can re-enqueue at most **3 times per analysis window** so no single task monopolizes workers.
- **Pending collection queue:** RAG/synthesis can call `queue_collection_request(type, url, source)`; the next collection cycle drains the queue. Persisted to DB on shutdown.
- **Config:** `orchestrator_governance.yaml` can expose `analysis_pipeline.step_budgets_seconds` and `analysis_pipeline.max_requeue_per_window`; optional env `COLLECTION_CYCLE_INTERVAL_SECONDS`.

### Full-history and data-scope expansions

- **Storyline discovery:** 7-day window (168 h), limit 1500 articles; **deduplication** against existing storylines (entity + title similarity, threshold 0.65); **automation_enabled = true** on new storylines; **topic co-assignment** and **PDF section contexts** (with domain_key) as similarity signals.
- **Proactive detection:** Wired into scheduler (e.g. every 2 h); default 72 h window, 1000 articles.
- **Content synthesis:** Domain context default 7 days (168 h); caps increased (e.g. max_articles 100, max_entities 50, max_storylines 25, max_events 25); **historical summary tier** for older articles; **source diversity** — per-source cap (e.g. 5 articles per source) so summaries use multiple feeds.
- **Deep content synthesis:** Topic window 30 days (720 h), breaking news 72 h; higher article caps.
- **Cross-domain synthesis:** time_window_days 30, event limit 1000; processed documents included where applicable.
- **Pattern recognition:** Temporal patterns 90 days.
- **Entity profile builder:** More contexts (e.g. 75 fetched, 40 for LLM); iterative summarization for large sets.
- **Entity position tracker:** 50 articles per entity (extract), 25 per entity (batch).
- **Storyline automation:** Entity/search window 90 days; RAG date filter fixed (date_range_days → date_from/date_to).
- **Relationship extraction:** Context limit increased (e.g. limit * 5) for historical depth.
- **Narrative thread synthesis:** Domain context 168 h.

### Data silo bridges

- **Processed documents:** PDF section contexts get **domain_key** from document metadata (e.g. politics/finance/science-tech); storyline discovery and cross-domain synthesis include PDF-derived content.
- **Source diversity:** Synthesis article queries use a per-source cap so no single feed dominates.
- **Fact verification:** Scheduled task runs `verify_recent_claims` (e.g. limit 20); corroboration/contradiction flags written to extracted_claims and available to synthesis.
- **Topics → storylines:** Topic assignments used as a similarity signal in storyline discovery; dedup checks topic overlap.
- **Dossiers and cross-domain → synthesis:** Top entity dossier summaries and cross-domain correlations included in domain synthesis context (e.g. “Key actor profiles” in LLM prompt); cross-domain limit increased (e.g. 20).

### Automation manager dispatch updates

- storyline_discovery: hours=168  
- cross_domain_synthesis: time_window_days=30  
- daily_briefing_synthesis: hours=72  
- entity_position_tracker: max_articles_per_entity=25  
- entity_profile_build: limit=25  

---

## Implementation Order (from plan)

1. **S1–S4** — Scheduler: collection_cycle, pipeline-ordered analysis, re-enqueue cap, pending_collection_queue  
2. **A1–A2** — Storyline discovery: automation_enabled on new, dedup vs existing  
3. **A3–A4** — Wider discovery window, proactive_detection wired in  
4. **D1–D2** — PDF domain_key bridge, source diversity  
5. **B1–B3, B9** — Synthesis/cross-domain scope expansions  
6. **B4–B8** — Entity/pattern/relationship depth  
7. **D3–D5** — Fact verification schedule, topic–storyline bridge, dossier/cross-domain feedback  
8. **C1** — Dispatch parameter updates  

---

## Files to Touch (summary)

- **automation_manager.py:** collection_cycle, ANALYSIS_PIPELINE_STEPS, STEP_TIME_BUDGETS, _run_analysis_pipeline(), _requeue_counts, MAX_REQUEUE_PER_WINDOW, pending_collection_queue, queue_collection_request(), remove standalone collection schedules, add proactive_detection and fact_verification schedules and executors, PHASE_ESTIMATED_DURATION_SECONDS (collection_cycle, proactive_detection, fact_verification), dispatch param updates  
- **ai_storyline_discovery.py:** automation_enabled in save_storyline_suggestion(), dedup vs existing storylines, fetch_recent_articles() hours/limit, topic and PDF context signals  
- **content_synthesis_service.py:** domain context hours/caps, historical summary tier, per-source cap, dossier/cross-domain in context and render_synthesis_for_llm()  
- **deep_content_synthesis.py:** topic/breaking hours and caps  
- **cross_domain_service.py:** time_window_days, event limit, processed documents  
- **pattern_recognition_service.py:** temporal 90 days  
- **entity_profile_builder_service.py:** context caps, iterative summarization  
- **entity_position_tracker_service.py:** article caps  
- **storyline_automation_service.py:** date_range_days 90, RAG date_from/date_to fix  
- **relationship_extraction_service.py:** context limit  
- **narrative_thread_service.py:** domain context 168 h  
- **document_processing_service.py:** domain_key assignment for PDF contexts  
- **proactive_detection_service.py:** hours/limit  
- **backlog_metrics.py:** any task list updates if needed  
- **orchestrator_governance.yaml:** optional analysis_pipeline and collection_cycle config  

---

## Config

- **orchestrator_governance.yaml** (optional):  
  - `analysis_pipeline.step_budgets_seconds: [1800, 1200, 1200, null]`  
  - `analysis_pipeline.max_requeue_per_window: 3`  
  - `collection_cycle.interval_seconds: 7200`  
- **Env (optional):** `COLLECTION_CYCLE_INTERVAL_SECONDS`  

---

## Implementation checklist (complete)

- [x] S1–S4 — Scheduler: collection_cycle, pipeline steps, re-enqueue cap, pending_collection_queue
- [x] A1–A4 — Storyline discovery: automation_enabled, dedup, 168h/1500, proactive_detection, topic + PDF signals
- [x] D1–D2 — PDF domain_key in contexts, source diversity (per-source cap in synthesis)
- [x] B1–B9 — Synthesis/cross-domain/entity/pattern scope (caps, 90d, 30d, 168h, iterative summarization, etc.)
- [x] D3–D5 — Fact_verification schedule, topic–storyline bridge, dossier/cross-domain in synthesis (key actor profiles, limit 20)
- [x] C1 — Dispatch params: time_window_days=30, hours=72, limit=25, max_articles_per_entity=25
- [x] Config — orchestrator_governance.yaml analysis_pipeline + collection_cycle; automation_manager loads them; env COLLECTION_CYCLE_INTERVAL_SECONDS
- [x] Backlog — entity_profile_build batch size 25 in backlog_metrics
- [x] Monitoring — Phase timeline grouped by v8 stages (Collection cycle, Foundation, Extraction, Intelligence, Output)

---

## Notes

- Pipeline step lists and duration estimates are specified in the plan (`.cursor/plans/full-history_data_awareness_*.plan.md`).  
- health_check remains outside the pipeline and runs on its interval regardless of step.  
- After v8, expect auto-created storylines and events to reflect a 7-day article window and PDF/topic signals; synthesis and briefings to use multiple sources and dossier/cross-domain context.
