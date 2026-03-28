# AutomationManager — scheduling and execution semantics

Single reference for how **work is scheduled**, how **`schedules[*].last_run`** behaves, and how **CPU vs GPU lanes** relate to **Ollama**. Implementation: `api/services/automation_manager.py`.

---

## Entry paths (all end in `_execute_task` except noted)

| Path | Behavior |
|------|----------|
| **Scheduler tick** | Builds runnable sequential phases and **parallel-group** members; each runnable phase is enqueued via `_create_and_queue_task` → `task_queue` → a **phase worker** dequeues and runs `_execute_task`. Parallel groups use the **same queue** (scheduler no longer blocks on `gather`). |
| **`request_phase` / governor** | Pushes to `_requested_task_queue`; phase workers **prefer** this queue over the scheduled `PriorityQueue`. Does **not** go through `_should_run_task` (execute-time gates still apply). |
| **`run_nightly_sequential_phase`** | `await _execute_task(...)` from the nightly unified drain coroutine (not the worker pool); metadata `nightly_sequential_drain` bypasses several deferrals and per-phase caps as documented in code. |

---

## `schedules[phase_name]["last_run"]` — two moments, one field

The same field is updated in different situations:

1. **After a successful scheduled enqueue** (`_create_and_queue_task` → `_enqueue_scheduled_task` returns true): `last_run` is set to **enqueue time**. Workload-driven cooldown uses this so the scheduler does not enqueue the same phase every tick.
2. **When a run finishes** (success or failure in `_execute_task`): `last_run` is set to **`completed_at` / `finished_at`**.

**Dependency settling** (`_are_dependencies_satisfied`) compares dependents against **`dep_schedule["last_run"]`**. After an enqueue, that timestamp reflects **enqueue**, not “dependency output visible in DB,” until completion overwrites it. In normal operation completion updates dominate; when debugging “dependent never ran,” remember **enqueue vs completion** on the dependency.

**Bootstrap**: `last_run is None` is treated specially so first-ever runs can queue together with dependencies (see comments in `_are_dependencies_satisfied`).

---

## Resource lanes vs Ollama

- **`OLLAMA_AUTOMATION_PHASES`** (module frozenset): phases that pass through the **Ollama yield-to-API**, **GPU temperature throttle**, and **`ollama_semaphore`** gate at the start of `_execute_task`.
- **`GPU_LANE_PHASES`**: **equals `OLLAMA_AUTOMATION_PHASES`**. Used for `_phase_default_lane`, `_phase_resource_class` (**gpu_heavy** vs **cpu_light**), and Monitor **`resource_router.phase_lane_defaults`**.

Phases that are **DB-heavy** and also call the LLM stack (e.g. some extraction phases) may appear in **`DB_HEAVY_PHASES`** as well; **`_phase_resource_class`** checks **GPU lane first**, then DB-heavy, then CPU-light—so a phase in both sets is classified **gpu_heavy** for router/cooldown purposes.

Phases **not** in `OLLAMA_AUTOMATION_PHASES` (e.g. `collection_cycle`, `context_sync`, `claims_to_facts`, `health_check`) do **not** take the semaphore/yield path at the top of `_execute_task` unless they are added to the frozenset.

**To add or remove an Ollama-gated phase:** update **`OLLAMA_AUTOMATION_PHASES`** only; **`GPU_LANE_PHASES`** follows automatically.

---

## Parallel groups (`parallel_group` in schedules)

Members of a parallel group are **not** run inline on the scheduler with `asyncio.gather`. They are **enqueued like sequential phases** when the group is eligible (`_should_run_parallel_group`) and each member passes `_should_run_task`. Actual overlap is determined by **worker count**, **per-phase concurrent caps**, and **queue ordering**—not by a dedicated “parallel burst” on the scheduler coroutine.

---

## Worker model and status fields

- **`_phase_worker_tasks`**: asyncio tasks running `_worker` (dequeue loop). Count is driven by **`max_concurrent_tasks`** and **`_sync_phase_worker_tasks`** after startup, scale up/down, or dynamic resource allocation.
- **`_background_automation_tasks`**: scheduler, standalone DB health loop, health monitor, metrics collector, entity organizer downtime loop.
- **`get_status()`**:
  - **`active_workers`**: phase workers **still running** (not done).
  - **`phase_workers_configured`**: `len(_phase_worker_tasks)` (target matches `max_concurrent_tasks` after sync).
  - **`max_concurrent_tasks`**: configured cap.
  - **`automation_background_tasks_active`**: non-done background tasks.

---

## Throughput vs wasted work (defaults are tuned together)

| Mechanism | Role |
|-----------|------|
| **`AUTOMATION_MAX_SCHEDULED_DEPTH_PER_PHASE`** (default 1) | Stops the scheduler from stacking many **scheduled** copies of the same phase while earlier copies are still queued. **Defer/retry** paths use `bypass_schedule_depth_cap` so work is not dropped; under sustained yield-to-API / GPU defer, scheduled depth can still grow—watch queue if the UI is busy 24/7. |
| **`AUTOMATION_PER_PHASE_CONCURRENT_CAP`** (default 2) + phase list | Limits how many workers may **run** the same capped phase at once (scheduler gate + **reserved slot** before `ollama_semaphore.acquire()` so the cap cannot be exceeded while tasks wait on the semaphore). **`0`** disables. |
| **`WORKLOAD_MIN_COOLDOWN`** (~10s) × resource-router multipliers | Spreads ticks; large pending + **`WORKLOAD_BALANCER_ENABLED`** shortens cooldown for listed backfill phases. |
| **`MAX_CONCURRENT_OLLAMA_TASKS`** | Global ceiling on phases that passed the Ollama gate—complements per-phase caps. |
| **Requested queue** | **`request_phase`** does not use scheduled depth caps; execute-time caps and the semaphore still apply. |
| **`AUTOMATION_QUEUE_SOFT_CAP`** (default 0) | Optional emergency brake on total scheduled depth; prefer tuning the knobs above first. |

**`last_run` on failed enqueue:** If scheduled enqueue is skipped (e.g. depth cap), `last_run` is **not** advanced, so the next tick can retry—no permanent stall.

---

## Related env and docs

- Caps and cooldowns: `configs/env.example`, module docstring at top of `automation_manager.py`.
- Pipeline order of phases: `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md`.
- Nightly window: `api/services/nightly_ingest_window_service.py`, `AGENTS.md` (nightly section).
