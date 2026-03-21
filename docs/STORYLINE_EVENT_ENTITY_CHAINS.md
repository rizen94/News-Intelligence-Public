# Storylines from events & entities

This document describes how **storylines**, **extracted events** (`public.chronological_events`), and **entities** connect, and how to verify the chain.

## How the pieces fit

| Layer | Role |
|-------|------|
| **Storyline discovery / automation** | Creates or grows domain `storylines` and `storyline_articles` from article clusters and matching (`AIStorylineDiscovery`, `StorylineAutomationService`). |
| **`article_entities` + `entity_canonical`** | Per-article entities; merged into **`story_entity_index`** when articles are attached to a storyline (feeds matching). |
| **Event extraction** | Writes rows to **`public.chronological_events`** with `source_article_id` (per-domain article id). Initial `storyline_id` is often empty. |
| **Story continuation** (`story_continuation` phase) | For unlinked events, finds candidate **domain** `storylines` using **`story_entity_index`** (requires **≥2** overlapping entity names with the event), filters by event type, then LLM verification. On success, sets `chronological_events.storyline_id` to the numeric storyline id and refreshes the entity index for that storyline. |

So: **“Chains” of events on a storyline** appear when continuation links multiple events to the same `storylines.id`, and **entity overlap** is what makes matching possible.

## Prerequisites on the database

1. **`{politics,finance,science_tech}.story_entity_index`** must exist (migration **179** creates them if missing; legacy **135** was search-path dependent).
2. Enough **storylines** with **`story_entity_index`** (or merged **`article_entities`**) so continuation can find **≥2** shared entity names with a new event.
3. Automation phase **`story_continuation`** running after **`event_extraction`** (see `automation_manager` phase order / `depends_on`).

## Verify (read-only)

```bash
PYTHONPATH=api uv run python scripts/verify_storyline_event_entity_chains.py
PYTHONPATH=api uv run python scripts/verify_storyline_event_entity_chains.py --write-report docs/STORYLINE_EVENT_ENTITY_CHAINS_REPORT.md
```

The report includes:

- Row counts: domain `storylines`, `storyline_articles`, `story_entity_index`
- Events per domain (via join to domain `articles`) and how many have non-empty `storyline_id`
- Orphan check: numeric `storyline_id` with no matching domain `storylines` row
- Storylines with **≥2** linked chronological events (event chains)
- Storylines that have both `storyline_articles` and `article_entities` on those articles

## Apply migration 179 (if `story_entity_index` is missing)

```bash
PYTHONPATH=api uv run python api/scripts/run_migration_179.py
```

Then re-run the verification script and ensure **`storyline_discovery`** / **`storyline_automation`** populate storylines so continuation has candidates.

## Related code

- `api/services/story_continuation_service.py` — matching and `story_entity_index` updates
- `api/services/storyline_automation_service.py` — merges `article_entities` into `story_entity_index`
- `api/services/ai_storyline_discovery.py` — cluster → new storylines
- `api/services/automation_manager.py` — `_execute_story_continuation_v5`, `_execute_storyline_discovery`
