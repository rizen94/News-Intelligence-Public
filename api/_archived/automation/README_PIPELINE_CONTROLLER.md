# Retired scheduling loops (v10.1 pipeline controller cutover)

**Date:** 2026-07

The following scheduling entry points were replaced by `api/services/pipeline_controller.py`:

| Retired loop | Former module |
|--------------|---------------|
| AutomationManager `_scheduler` 5s tick | `automation_manager.py` (no longer started) |
| `spine_conductor_loop` | `spine_pipeline_conductor.py` |
| `assembly_conductor_loop` | `assembly_conductor_service.py` |
| OrchestratorCoordinator RSS/processing scheduling | `orchestrator_coordinator.py` (skipped when controller active) |

Drain helpers remain in active modules for scripts and rollback.
