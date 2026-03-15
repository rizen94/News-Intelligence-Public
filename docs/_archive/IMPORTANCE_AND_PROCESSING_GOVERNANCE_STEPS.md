# Importance and Processing Governance — Implementation Steps

**Goal:** Build out ProcessingGovernor and importance so the coordinator can choose *what* to process (phase + domain/storyline) and prefer high-importance storylines. Aligns with [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) Phase B and C.

---

## 1. State and config

- **Orchestrator state** (existing `state_json`): Add `last_processing_times` and optional `user_guidance_snapshot`.
  - `last_processing_times`: `{"phase:domain": "ISO timestamp", "phase:storyline:42": "ISO timestamp"}` so we can tell "topic_clustering politics last ran at X".
  - No schema migration; state is a single JSON blob.
- **Config** (`orchestrator_governance.yaml`): Add `processing.phases` with phase → `interval_seconds` and optional `scope` (e.g. `domain`, `storyline`).
  - Phases: `topic_clustering`, `article_processing`, `entity_extraction`, `storyline_automation`, `story_continuation`, `context_sync`, `event_tracking` (subset to start).

---

## 2. User guidance loader

- **Purpose:** One place that aggregates watchlist storyline IDs and automation-enabled storylines (with last_automation_run, automation_mode, search_keywords) so governors can prioritize.
- **Implementation:** New helper or small module that:
  - Reads from PostgreSQL: `watchlist` (storyline_id), and `storylines` (automation_enabled, automation_mode, last_automation_run, search_keywords) per domain.
  - Returns e.g. `{"watchlist_storyline_ids": [1,2,3], "automation_storylines": [{"id": 4, "domain": "politics", "last_automation_run": "...", "automation_mode": "auto_approve"}]}`.
- **Caching:** Coordinator can call once per cycle and store in state as `user_guidance_snapshot` (optional) or ProcessingGovernor loads on each recommend.

---

## 3. Importance scoring (per storyline)

- **Purpose:** Scalar or tier (high / medium / low) per storyline so ProcessingGovernor can rank "run storyline_automation for storyline_id=42" before others.
- **Signals:**
  - On watchlist → high.
  - automation_enabled + automation_mode in (auto_approve, manual) → medium or high.
  - Velocity: recent articles or recent automation run → boost.
  - (Future: quality/impact of articles, cross-domain links.)
- **Implementation:** Function `compute_storyline_importance(storyline_id, domain, watchlist_ids, automation_info)` → float in [0, 1] or tier string. Used by ProcessingGovernor when building the ranked list for storyline-scoped phases.

---

## 4. ProcessingGovernor: recommend and record

- **recommend_next_processing(state, resource_ok)**:
  - Input: `state` (last_processing_times, user_guidance_snapshot or load fresh), `resource_ok` (ResourceGovernor.can_run("processing")).
  - Build candidates: for each phase in config, check `last_processing_times`; if due (never run or elapsed >= interval), add (phase, domain?, storyline_id?, priority).
  - For domain-scoped phases (e.g. topic_clustering): one candidate per domain that is due.
  - For storyline-scoped phases (storyline_automation, story_continuation): use importance to pick top N storylines that are due (e.g. last_automation_run + frequency).
  - Sort by priority: user_request > watchlist > high_importance > scheduled.
  - Return single "next best action": `{"phase": str, "domain": str|None, "storyline_id": int|None, "priority": str}` or None.
- **record_processing_result(phase, domain, storyline_id, success)**:
  - Update state `last_processing_times` with key like `phase` or `phase:domain` or `phase:storyline:{id}` and current timestamp.
  - Persist via orchestrator_state.save_controller_state.

---

## 5. AutomationManager: run_phase

- **run_phase(phase_name, domain=None, storyline_id=None)**:
  - Create a Task with name=phase_name, metadata={domain, storyline_id}, priority from caller.
  - Put task on existing task_queue. Workers already run _execute_* by task.name.
  - Phases that support scoping: pass metadata into handler; e.g. _execute_topic_clustering(task) checks task.metadata.get("domain") and runs only for that domain if set. _execute_storyline_automation(task) is new: calls storyline_automation_service.discover_articles_for_storyline(storyline_id) when storyline_id in metadata.
- **New phase "storyline_automation":** Distinct from "storyline_processing" (summary generation). Runs RAG discovery for one or all automation-enabled storylines; when storyline_id is in metadata, run only for that storyline.

---

## 6. Coordinator loop wiring

- In `_run_loop`, after handling collection (or in same cycle):
  - Call `processing_action = self._processing_governor.recommend_next_processing(state, self._resource_governor.can_run("processing"))`.
  - If `processing_action` and resource OK:
    - Call `automation.run_phase(processing_action["phase"], domain=..., storyline_id=...)` (need to get automation reference into coordinator).
    - Call `record_processing_result(...)` with the action and success=True after run (or False on exception).
  - Append decision_log for "process_phase" with outcome.
- Coordinator must have access to AutomationManager (e.g. app.state.automation or passed into OrchestratorCoordinator). Currently it is not passed; we need to add get_automation to the coordinator constructor and use it when executing processing actions.

---

## 7. Order of implementation (done)

| Step | What | Status |
|------|------|--------|
| 1 | Processing config (phase intervals) in yaml; state shape | ✅ `api/config/orchestrator_governance.yaml` + defaults in `orchestrator_governance.py` |
| 2 | User guidance loader (watchlist + automation storylines) | ✅ `api/services/user_guidance_service.py` |
| 3 | Importance scoring (per storyline) | ✅ Inline in `user_guidance_service.compute_storyline_importance` |
| 4 | ProcessingGovernor.recommend_next_processing + record_processing_result | ✅ `api/services/processing_governor.py` |
| 5 | AutomationManager.request_phase + storyline_automation phase; handlers accept metadata | ✅ `api/services/automation_manager.py` (_phase_request_queue, _execute_storyline_automation) |
| 6 | Coordinator: get_automation, get_db_connection, ask ProcessingGovernor, request_phase, record | ✅ `api/services/orchestrator_coordinator.py`, `api/main_v4.py` |

---

## 8. Out of scope for this pass

- Phase A (coordinator as single trigger; stop AutomationManager’s own scheduler) — we keep both: coordinator can *also* trigger phases while AutomationManager still runs its schedule. Unifying to one trigger is a later step.
- Review queue (C.4) as feedback into importance — deferred.
- EditorialGovernor / proposed focus queue (Phase D) — deferred.
