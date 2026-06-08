# Storyline historical memory

## Philosophy

Separate **memory** (query on demand) from **signals** (small hot queues).

| Role | Stores | Used for |
|------|--------|----------|
| Memory | `intelligence.versioned_facts`, `{schema}.story_entity_index`, `public.chronological_events`, storyline articles | Synthesis, ~70B finisher, timeline narratives, story state snapshots |
| Hot queue | `intelligence.fact_change_log`, `intelligence.story_update_queue` | Trigger story-state refresh; drain via `story_enhancement` |

Never use `fact_change_log` row count as “how much history we have.” Bulk marking old log rows `processed = TRUE` only shrinks the **queue**; promoted facts remain in `versioned_facts`.

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
- `STORY_STATE_FACT_CHANGE_REFINEMENT=0` — enqueue `narrative_finisher` when snapshot has facts
