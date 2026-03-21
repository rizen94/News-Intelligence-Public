# Synthesis & Intelligence-Output Processes — Audit

**Purpose:** Verify that every process that turns processed data into readable intelligence is **domain-aware** and actually contributes. "Running successfully" is not enough if it reads from the wrong schema (e.g. empty `public`) or never writes.

---

## Summary table

| Process | Domain-aware? | Data source | Output | Status |
|--------|----------------|-------------|--------|--------|
| **storyline_processing** | ✅ Yes (fixed) | `{schema}.storylines` + articles | `analysis_summary`, `editorial_document` in same schema | **Fixed** — was public-only |
| **storyline_synthesis** | ✅ Yes | `{schema}.storylines`, `{schema}.storyline_articles` | `synthesized_content` in same schema | OK |
| **daily_briefing_synthesis** | ✅ Yes | Per-domain via `synthesize_breaking_news(domain)` | Deep content synthesis output | OK |
| **cross_domain_synthesis** | ✅ Yes | `intelligence.tracked_events` (global) | `intelligence.cross_domain_correlations` | OK |
| **editorial_document_generation** | ✅ Yes | `{schema}.storylines` via `generate_storyline_editorial(domain)` | `editorial_document` in same schema | OK |
| **editorial_briefing_generation** | ✅ Yes | `intelligence.tracked_events`, `intelligence.event_chronicles` | `editorial_briefing` on events | OK |
| **narrative_thread_build** | ✅ Yes | `{schema}.storylines` per domain, `build_threads_for_domain(domain)` | `intelligence.narrative_threads` | OK |
| **digest_generation** | ❌ **No** | **public.articles** (empty) via `generate_weekly_briefing()` with no domain | `weekly_digests` | **Broken** — sees no domain data |
| **RAG enhancement** | ❌ No | Legacy `get_all_storylines()` → public only | `storyline_rag_context` | **Broken** — not domain-scoped |

---

## Details

### 1. storyline_processing
- **Fix applied:** Now loops over `politics`, `finance`, `science_tech`, queries `{schema}.storylines` (with articles), uses domain `StorylineService(domain).generate_storyline_summary()`, seeds `editorial_document` in same schema.
- **Previously:** Used legacy `get_all_storylines()` (public only) → 0 storylines processed.

### 2. storyline_synthesis (DeepContentSynthesisService)
- **Data:** Per-domain loop in automation; queries `{schema}.storylines` and `{schema}.storyline_articles`; `synthesize_storyline_content(domain_key, storyline_id)`.
- **Output:** `_save_synthesis_to_db(schema, ...)` with `SET search_path TO {schema}`; updates `storylines.synthesized_content`, `synthesized_at`.
- **Verdict:** Domain-aware and contributing.

### 3. daily_briefing_synthesis
- **Data:** Loops domains, calls `synthesize_breaking_news(domain_key, hours=72)`.
- **Verdict:** Domain-aware and contributing.

### 4. cross_domain_synthesis
- **Data:** `intelligence.tracked_events` (global, not per-domain tables).
- **Output:** `intelligence.cross_domain_correlations`.
- **Verdict:** Correct; events are in intelligence layer.

### 5. editorial_document_generation
- **Data:** Loops domains, `generate_storyline_editorial(domain, limit=5)` which queries `{schema}.storylines` and uses `synthesize_storyline_context(domain, storyline_id)`.
- **Output:** Updates `{schema}.storylines.editorial_document`.
- **Verdict:** Domain-aware and contributing.

### 6. editorial_briefing_generation
- **Data:** `intelligence.tracked_events`, `intelligence.event_chronicles`.
- **Output:** `editorial_briefing` / `editorial_briefing_json` on same table.
- **Verdict:** Correct; events are global.

### 7. narrative_thread_build
- **Data:** Per-domain `build_threads_for_domain(domain)`; reads `{schema}.storylines`, `{schema}.storyline_articles`.
- **Output:** `intelligence.narrative_threads` (domain_key + storyline_id).
- **Verdict:** Domain-aware and contributing.

### 8. digest_generation (weekly digest)
- **Bug:** `generate_digest_if_needed()` → `_run_weekly_briefing_sync(week_start)` → `svc.generate_weekly_briefing(week_start_dt)`. `generate_weekly_briefing()` calls `generate_daily_briefing(current_date, include_deduplication=False)` **without** `domain`. So `articles_table = "articles"` (unqualified = **public.articles**). With domain silos, real articles are in `politics.articles`, `finance.articles`, `science_tech.articles`; public is empty or legacy. So the weekly digest is built from **no meaningful data**.
- **Fix:** Generate daily briefings **per domain** and **merge** them (sum article counts, combine storylines/headlines) so the weekly digest reflects all domains. See digest_automation_service and daily_briefing_service changes.

### 9. RAG enhancement
- **Bug:** Uses `get_storyline_service().get_all_storylines()` (public only). So it never enhances domain storylines. `_save_rag_context` writes to unqualified `storyline_rag_context` (public) with storyline_id only (no domain) → ID collision across domains.
- **Fix (deferred):** Make RAG enhancement run per-domain and pass domain into the RAG service so context is stored by (domain, storyline_id) or schema-qualified table.

---

## Verification

- Run `scripts/investigate_storyline_automation.py` for storyline/automation counts.
- After digest fix: generate a weekly digest and confirm `total_articles_analyzed` and `story_suggestions` are non-zero when domain tables have data.
- Check `weekly_digests` and one digest’s `story_suggestions` / `quality_metrics` to ensure they reflect politics/finance/science_tech.
