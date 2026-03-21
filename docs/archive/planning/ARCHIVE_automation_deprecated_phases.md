# Archived: Deprecated automation phases (removed from active codebase)

**Archived:** 2025. These phases were merged into other phases and removed from `api/services/automation_manager.py` and `api/config/orchestrator_governance.yaml`. Kept for historic reference only. Move to `docs/_archive/` if you keep archived docs there.

## Summary

| Phase | Merged into |
|-------|-------------|
| `article_processing` | `content_enrichment` |
| `relationship_extraction` | `entity_organizer` |
| `story_state_triggers` | `story_enhancement` |
| `basic_summary_generation` | `storyline_processing` |

## Removed from automation_manager.py

- **PHASE_ESTIMATED_DURATION_SECONDS:** `article_processing` (180), `basic_summary_generation` (120), `story_state_triggers` (120), `relationship_extraction` (90).
- **schedules:** Four schedule entries (relationship_extraction, article_processing, basic_summary_generation, story_state_triggers), all with `enabled: False`.
- **_execute_task:** Four `elif task.name == '...'` branches calling the removed _execute_* methods.
- **_activity_message:** Branches for relationship_extraction, story_state_triggers, article_processing (basic_summary had no explicit branch).
- **_execute_* methods:** _execute_story_state_triggers, _execute_relationship_extraction, _execute_article_processing, _execute_basic_summary_generation (no-op stubs).

## Removed from orchestrator_governance.yaml

- **processing.phases:** `article_processing: { interval_seconds: 300, scope: null }`.

## Unchanged (intentionally)

- API route `POST /context_centric/run_story_state_triggers` — runs the story state trigger *service*, not the automation phase.
- DB table name `article_processing_log` in monitoring queries.
- `relationship_extraction_service` and `entity_organizer_service` (entity_organizer still uses relationship extraction).
