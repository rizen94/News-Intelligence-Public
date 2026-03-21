# Plan: Fix Remaining Dossier and Story Journey Gaps

**Purpose:** Address the two remaining gaps that limit dossier richness and event chronicle matching: (1) entity position extraction not in the pipeline, and (2) `key_participant_entity_ids` never auto-populated on tracked events.

**Related:** [DOSSIER_PIPELINE_ORDERING_PLAN.md](DOSSIER_PIPELINE_ORDERING_PLAN.md), [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md).

---

## Gap 1: Entity Position Tracker Not Automated

**Problem:** `entity_position_tracker_service` exists and works (LLM extracts stances/positions from articles), but it is only callable via API. No scheduled task runs it. So `intelligence.entity_positions` stays empty and dossiers show `positions: []`.

**Goal:** Run position extraction on a schedule so dossiers include stance/vote/policy data.

### 1.1 Add automation task

| Step | Action |
|------|--------|
| 1 | Add `"entity_position_tracker": 300` to `PHASE_ESTIMATED_DURATION_SECONDS` in `api/services/automation_manager.py` (LLM-bound, ~30–60s per entity). |
| 2 | Add schedule entry `entity_position_tracker`: interval 7200 (2 hours), phase 2, `depends_on: ['entity_profile_sync']`, enabled True. |
| 3 | Add `entity_position_tracker` to `_OLLAMA_TASKS` so it shares the Ollama semaphore (max 3 concurrent). |
| 4 | In the task dispatch block, add `elif task.name == 'entity_position_tracker': await self._execute_entity_position_tracker(task)`. |
| 5 | Implement `_execute_entity_position_tracker`: call `run_position_tracker_batch(domain_key=None, min_mentions=5, max_entities=8, max_articles_per_entity=10)` from `entity_position_tracker_service`. Use `run_in_executor` because `run_position_tracker_batch` is synchronous and calls LLM. |
| 6 | Add task description in `_get_task_description` for `entity_position_tracker`. |

### 1.2 Service contract

- `run_position_tracker_batch(domain_key=None, min_mentions=5, max_entities=10, max_articles_per_entity=10)` is already implemented and returns `Dict[domain, result]`.
- No API or config change required; optional later: add `entity_position_tracker: true` to `context_centric.yaml` and check in executor if you want a kill switch.

### 1.3 Files to touch

- `api/services/automation_manager.py` only.

---

## Gap 2: key_participant_entity_ids Never Auto-Populated

**Problem:** When events are created in `discover_events_from_contexts`, we set `key_participant_entity_ids` to `'[]'`. Nothing ever fills it. The improved chronicle matching (contexts that mention participant entities) never activates.

**Goal:** After creating a new event, derive participant entity profile IDs from the contexts linked to that event and UPDATE the row.

### 2.1 Data flow

1. When we create an event we have `valid_ids` = list of context IDs linked to this event.
2. For each context_id: `article_to_context` gives `(article_id, domain_key)`.
3. For each (domain_key, article_id): that domain’s `article_entities` gives `canonical_entity_id`s.
4. For each (domain_key, canonical_entity_id): `entity_profiles` gives `id` (entity_profile_id).
5. Collect unique entity_profile_ids (cap at 20), then `UPDATE intelligence.tracked_events SET key_participant_entity_ids = %s WHERE id = %s`.

### 2.2 Implementation options

**Option A (recommended): Populate at event creation**

- In `event_tracking_service.discover_events_from_contexts`, immediately after the `INSERT INTO event_chronicles` for a new event, call a helper `_set_key_participants_from_contexts(cur, event_id, valid_ids)` that:
  - For each context_id in valid_ids: SELECT article_id, domain_key FROM article_to_context WHERE context_id = %s.
  - For each (article_id, domain_key): SELECT canonical_entity_id FROM {schema}.article_entities WHERE article_id = %s (schema from domain_key).
  - For each (domain_key, canonical_entity_id): SELECT id FROM entity_profiles WHERE domain_key = %s AND canonical_entity_id = %s.
  - Collect unique profile IDs, take first 20, then UPDATE tracked_events SET key_participant_entity_ids = %s WHERE id = %s.
- All in the same DB connection/transaction as the event insert.

**Option B: Backfill existing events**

- Add a function `_backfill_key_participants_for_event(event_id)` that gets context_ids from that event’s chronicles, then runs the same resolution logic as in Option A, then UPDATE.
- Call it from a new automation task (e.g. `event_participant_backfill`) or once from a script. Lower priority than Option A.

### 2.3 Implementation steps (Option A)

| Step | Action |
|------|--------|
| 1 | In `api/services/event_tracking_service.py`, add a helper `_resolve_context_ids_to_entity_profile_ids(conn, context_ids: List[int]) -> List[int]` that returns up to 20 unique entity_profile IDs (logic above). Use one cursor; domain_key from article_to_context maps to schema via DOMAIN_SCHEMA or existing _schema(). |
| 2 | In the same file, in `discover_events_from_contexts`, after each event’s chronicle INSERT and before appending to `created_events`, call `profile_ids = _resolve_context_ids_to_entity_profile_ids(conn, valid_ids)`; if non-empty, `cur.execute("UPDATE intelligence.tracked_events SET key_participant_entity_ids = %s WHERE id = %s", (json.dumps(profile_ids), event_id))`. |
| 3 | Handle domain_key format: article_to_context uses `domain_key` (e.g. `politics`); entity_profiles uses same; article_entities live in schema `politics` / `finance` / `science_tech`. So when reading article_to_context we get domain_key; when querying article_entities we need schema = domain_key.replace('-','_') for science-tech. |
| 4 | Optional: add a comment in `_update_existing_event_chronicles` that the existing entity-based branch (OR c.id IN (SELECT context_id FROM context_entity_mentions WHERE entity_profile_id = ANY(%s))) will now be used once new events get key_participant_entity_ids set. |

### 2.4 Edge cases

- **Context not in article_to_context:** Skip that context_id (should not happen for contexts we just grouped).
- **Article has no article_entities:** Skip; no profile IDs from that article.
- **Canonical entity has no entity_profile yet:** entity_profile_sync may not have run for that entity; skip that canonical_entity_id (no INSERT into entity_profiles in this flow).
- **Empty profile_ids:** Leave key_participant_entity_ids as `'[]'` (no UPDATE needed).

### 2.5 Files to touch

- `api/services/event_tracking_service.py` only.

---

## Optional: Backfill key_participant_entity_ids for Existing Events (Option B)

If you want existing events to gain participant IDs without waiting for new context linking:

- Add `_backfill_key_participants_for_event(conn, event_id)` that:
  - SELECT developments FROM event_chronicles WHERE event_id = %s; collect all context_ids from developments.
  - Call _resolve_context_ids_to_entity_profile_ids(conn, context_ids).
  - UPDATE tracked_events SET key_participant_entity_ids = %s WHERE id = %s.
- Add a one-off script or an automation task that selects events where key_participant_entity_ids = '[]' and runs the backfill (e.g. limit 50 per run). Lower priority than Option A.

---

## Summary Checklist

| # | Item | Status |
|---|------|--------|
| 1 | Add entity_position_tracker to automation (schedule, executor, _OLLAMA_TASKS, description) | Done |
| 2 | Add _resolve_context_ids_to_entity_profile_ids in event_tracking_service | Done |
| 3 | Call it after each new event insert and UPDATE key_participant_entity_ids | Done |
| 4 | (Optional) Backfill task or script for existing events | Done (runs in event_tracking batch, 30/run) |

---

## Result After Implementation

- **Dossiers:** Will include `positions` (from entity_positions) as the position tracker runs every 2 hours on top entities by mention count.
- **Event chronicles:** New events will have `key_participant_entity_ids` set from the contexts that were grouped into the event; `_update_existing_event_chronicles` will then match new contexts that mention those entities via `context_entity_mentions`, improving iterative buildup.
