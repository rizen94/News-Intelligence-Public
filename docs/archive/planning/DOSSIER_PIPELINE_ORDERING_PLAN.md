# Dossier Pipeline Ordering and Integration Plan

**Purpose:** Fix pipeline dependency ordering so entity profiles and pattern recognition run after the data they need, and add the entity dossier compiler to the main automation pipeline so dossier-style summaries for people/entities are built at scale.

**Related:** [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md), [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md), [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md).

---

## 1. Problems Addressed

| Issue | Impact |
|-------|--------|
| **entity_profile_build** depended only on `context_sync` | Profile builder needs `entity_profiles` (from entity_profile_sync) and `context_entity_mentions` (populated during/after entity_profile_sync backfill). Without entity_profile_sync first, many profiles have zero contexts and are skipped. |
| **pattern_recognition** had no dependencies | Uses `context_entity_mentions`; should run after context_sync and entity_profile_sync so mentions exist. |
| **Entity dossier compiler** not in automation manager | Dossier compilation (people/org chronicles) only ran in OrchestratorCoordinator at 2/day with 24h interval. At that rate, 16k entities would take years to get dossiers. |
| **context_centric.yaml** missing two task flags | `investigation_report_refresh` and `event_coherence_review` were not listed; they relied on code defaults only. |

---

## 2. Dependency Order (Target)

```
Phase 1 (no deps):
  rss_processing, context_sync, entity_profile_sync

Phase 2 (after Phase 1):
  claim_extraction          depends_on: [context_sync]
  event_tracking            depends_on: [context_sync]
  entity_profile_build      depends_on: [context_sync, entity_profile_sync]   ← FIXED
  pattern_recognition       depends_on: [context_sync, entity_profile_sync]   ← FIXED
  entity_dossier_compile    depends_on: [entity_profile_sync]                 ← NEW
  investigation_report_refresh  depends_on: [event_tracking]
  cross_domain_synthesis    depends_on: [event_tracking]
  relationship_extraction  (none)
  entity_organizer          depends_on: [entity_profile_sync]
  ...
```

Entity dossier compiler only needs `entity_profile_sync` so that `entity_profiles` (and thus entity_dossiers candidates) exist. It reads from domain articles, storylines, entity_relationships, entity_positions, pattern_discoveries — all of which may be populated by other phases; the critical gate is that we have entity_profiles to know which (domain_key, entity_id) to compile.

---

## 3. Implementation Checklist

### 3.1 Automation manager: fix dependencies ✅

- [x] **entity_profile_build**  
  Changed `depends_on` from `['context_sync']` to `['context_sync', 'entity_profile_sync']`.

- [x] **pattern_recognition**  
  Changed `depends_on` from `[]` to `['context_sync', 'entity_profile_sync']`.

### 3.2 Automation manager: add entity_dossier_compile ✅

- [x] Added `entity_dossier_compile` to `PHASE_ESTIMATED_DURATION_SECONDS` (90 seconds).
- [x] Added schedule entry (interval 3600, phase 2, depends_on entity_profile_sync).
- [x] Added execution branch and `_execute_entity_dossier_compile` calling `_run_scheduled_dossier_compiles(20, None, 7)` via `run_in_executor`.
- [x] Added task description for `entity_dossier_compile`.

### 3.3 Context-centric config ✅

- [x] Added `entity_dossier_compile` to `DEFAULT_TASKS` in `context_centric_config.py`.
- [x] `_execute_entity_dossier_compile` checks `is_context_centric_task_enabled("entity_dossier_compile")`.
- [x] In `api/config/context_centric.yaml`, added `investigation_report_refresh`, `event_coherence_review`, and `entity_dossier_compile`.

### 3.4 Optional follow-ups ✅ (implemented)

- [x] **context_entity_mentions backfill limit:** Increased from 500 to 1000 per domain in `entity_profile_sync_service.backfill_context_entity_mentions_for_domain(domain_key, limit=1000)`.
- [x] **Event chronicle matching:** Improved `_update_existing_event_chronicles`: (1) multi-keyword match — significant words (length ≥ 4) from event name, up to 3, with OR across title/content; (2) when `key_participant_entity_ids` is non-empty, also match contexts that mention those entity profiles via `context_entity_mentions`.
- [x] **Orchestrator dossier compile:** Set `entity_tracking.enabled: false` in `orchestrator_governance.yaml` so dossier compilation runs only from the automation manager (hourly, 20/run); comment added to re-enable if desired.

---

## 4. Resulting Pipeline Behavior

- **Entity profile builder** runs only when both context_sync and entity_profile_sync have run, so profiles and context_entity_mentions are in place; more profiles get sections populated.
- **Pattern recognition** runs after the same prerequisites, so co-mention and behavioral patterns have data to work with.
- **Entity dossier compile** runs hourly in the automation manager, compiling up to 20 entity dossiers per run (entities missing a dossier or with stale dossier first). At 20/hour, ~480/day, so the 16k-entity backlog is drained in roughly a month instead of years.

The OrchestratorCoordinator can continue to run its own dossier_compile (2/cycle, 24h) as a secondary path, or you can disable entity_tracking.dossier_compile in orchestrator_governance.yaml to avoid duplicate work; the primary path is now the automation manager.

---

## 5. Files Touched

| File | Change |
|------|--------|
| `api/services/automation_manager.py` | Fix entity_profile_build and pattern_recognition depends_on; add entity_dossier_compile schedule, executor branch, _execute_entity_dossier_compile, duration constant, task description. |
| `api/config/context_centric_config.py` | Add entity_dossier_compile to DEFAULT_TASKS. |
| `api/config/context_centric.yaml` | Add investigation_report_refresh, event_coherence_review, entity_dossier_compile. |
| `docs/DOSSIER_PIPELINE_ORDERING_PLAN.md` | This plan. |
