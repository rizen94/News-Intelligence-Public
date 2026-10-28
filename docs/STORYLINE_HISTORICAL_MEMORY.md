# Storyline historical memory

Product intent for how memory feeds clearer narratives over time: [`KNOWLEDGE_LOOP.md`](KNOWLEDGE_LOOP.md).

## Philosophy

Separate **memory** (query on demand) from **signals** (small hot queues).

| Role | Stores | Used for |
|------|--------|----------|
| Memory | `intelligence.versioned_facts`, `{schema}.story_entity_index`, `public.chronological_events`, storyline articles | Synthesis, ~70B finisher, timeline narratives, story state snapshots |
| Hot queue | `intelligence.fact_change_log`, `intelligence.story_update_queue` | Trigger story-state refresh; drain via `story_enhancement` |

Never use `fact_change_log` row count as “how much history we have.” Bulk marking old log rows `processed = TRUE` only shrinks the **queue**; promoted facts remain in `versioned_facts`.

**`story_enhancement` mode:** Automation and catchup share `story_enhancement_facts_only()` / `story_enhancement_run_limits()` in `api/shared/pipeline_resource_policy.py`. When `STORY_ENHANCEMENT_FACTS_ONLY=true` (or GPU night work is not allowed), the phase drains the hot queues only (no Wikipedia enrich / profile build). When false, it also runs enrich/build on this phase. Enrich/build remain available as dedicated phases (`entity_enrichment`, `entity_profile_build`). Batch knobs: `STORY_ENHANCEMENT_FACT_BATCH`, `STORY_ENHANCEMENT_QUEUE_BATCH`, `STORY_ENHANCEMENT_ENRICH_LIMIT`, `STORY_ENHANCEMENT_BUILD_LIMIT`.

## Entry points

- **Build bundle:** `build_storyline_historical_context(domain_key, storyline_id)` in `api/services/storyline_historical_context_service.py`
- **LLM render:** `render_historical_context_for_llm(ctx)` — cap via `STORYLINE_HISTORICAL_CONTEXT_MAX_CHARS` (default 6000)
- **Chronological spine:** `build_storyline_spine()` in `api/services/timeline_builder_service.py` (domain-scoped `EXISTS` join on `{schema}.storylines`)
- **Operators:** `api/scripts/verify_storyline_historical_context.py`, `api/scripts/backfill_story_entity_index.py`
- **Migration indexes:** `api/database/migrations/218_storyline_historical_indexes.sql`

## Consumers

- `content_synthesis_service.synthesize_storyline_context` → `historical_context` / `historical_context_rendered`
- `storyline_narrative_finisher_service` finisher prompt
- `narrative_synthesis_service` + `content_refinement_queue` timeline jobs
- `story_state_service.update_story_state` → `intelligence.storyline_states.metadata` snapshot counts
- RAG analysis prepends historical block when the new service returns data

## Env (optional)

- `STORYLINE_HISTORICAL_MAX_FACTS`, `STORYLINE_HISTORICAL_MAX_ARTICLES`, `STORYLINE_HISTORICAL_CONTEXT_MAX_CHARS`
- `STORYLINE_HISTORICAL_IN_TIMELINE_SUMMARY=1` — fold facts into `timeline_generation` summary text
- `LEGACY_TIMELINE_EVENTS_WRITES=0` (default) — disable RAG writes to `{schema}.timeline_events`
- `STORY_STATE_FACT_CHANGE_REFINEMENT=1` (default) — enqueue `narrative_finisher` when a story-state snapshot has facts **and** the materiality gate says `run` (empty canonical or material evidence delta). Set `0` to disable enqueue entirely.
- `STORYLINE_ENQUEUE_FINISHER_ON_NEW_ARTICLE=1` (default) — after successful membership attach (`membership_store.admit` and API add-article), call `maybe_enqueue_narrative_finisher_on_membership`: initial finish if canonical empty; material delta → refresh enqueue; narrow → `narrow_debt_pending` only; unchanged → no-op.
- `NARRATIVE_FINISHER_MATERIALITY_GATE=1` (default) — skip/defer ~70B refresh when evidence fingerprint is unchanged (`skip`) or only a narrow delta (`defer`: +1 article or chronology-only). Full rewrite on material deltas. See `api/services/storyline_narrative_materiality.py`.
- `NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA=2` — article-count increase that counts as material (below this → narrow/defer).
- `NARRATIVE_FINISHER_FORCE=1` or job metadata `force=true` — bypass the gate for a full rewrite.
- `NARRATIVE_NARROW_DEBT_DRAIN=1` (default) — nightly GPU refinement drain force-enqueues finishers for storylines with `narrative_finisher_meta.narrow_debt_pending` (set when a refresh is deferred as narrow).
- `NARRATIVE_NARROW_DEBT_MIN_AGE_HOURS=6` — minimum age of the debt flag before nightly force enqueue.
- `NARRATIVE_NARROW_DEBT_PER_DOMAIN=4` — max forced finishers enqueued per domain per nightly drain pass.

**Refresh continuity:** the ~70B finisher prompt always includes the prior `canonical_narrative` as a first-class block (even when analysis bones exist) so material rewrites improve the last desk prose rather than ignoring it.

**Finisher model:** Prefer `OLLAMA_NARRATIVE_FINISHER_MODEL` (current: `qwen3.6:latest` on PopOS). Settings default matches that tag — do not leave an absent legacy tag (e.g. `qwen2.5:32b-instruct`) in env or defaults; that caused mass 404 failures historically.
