# GPU Scheduling, Backpressure & Blockage Detection

> **Purpose:** Operator reference for how News Intelligence manages GPU resources, detects blockages, and reacts via the Ollama circuit breaker system. Complements [`MONITOR_REPORTING_AND_METRICS.md`](MONITOR_REPORTING_AND_METRICS.md) (defer/shed/overload terminology) and [`PIPELINE_OPERATIONS_WIDOW.md`](PIPELINE_OPERATIONS_WIDOW.md).

---

## GPU Architecture

### Host topology

| Role | Host | GPU | Lane |
|------|------|-----|------|
| **PopOS phase worker** | PopOS LAN `192.168.93.99` | RTX 5090 (70B narrative) | `ollama_pop_os` |
| **Widow primary** | Widow `192.168.93.101` | — | `ollama`, `ollama_cpu` |
| **Dockside embeddings** | Dockside LAN `192.168.93.95` | — | `ollama_embeddings` (separate breaker) |

Generate / extract / narrative finish go to PopOS (`OLLAMA_POP_OS_HOST`). Embeddings go to Dockside via tunnel (`http://127.0.0.1:11435`) or LAN. Do **not** enable `OLLAMA_NARRATIVE_FINISHER_FALLBACK_TO_PRIMARY` in production.

### Dual-lane routing

`OLLAMA_DUAL_HOST_ROUTING_ENABLED=true` splits generate traffic into two lanes:

| Lane | Env gate | Concurrency env | Destination |
|------|----------|-----------------|-------------|
| **GPU** | `OLLAMA_GPU_CONCURRENCY` (default 6) | `OLLAMA_GPU_HOST` | GPU-equipped host (PopOS / dedicated GPU box) |
| **CPU** | `OLLAMA_CPU_CONCURRENCY` (default 6) | `OLLAMA_CPU_HOST` | CPU-only Ollama instance |

**Default: dual-lane routing is OFF.** All traffic goes through the single `ollama` CB key. Enable dual-lane only when deliberately splitting lanes (e.g. during a GPU host migration).

### Concurrency budget

| Env var | Default | Scope |
|---------|---------|-------|
| `OLLAMA_CONCURRENCY` | 6 | Global cap (legacy, applies when dual-lane is off) |
| `MAX_CONCURRENT_OLLAMA_TASKS` | inherits from AM | Overrides OLLAMA_CONCURRENCY when set by AutomationManager |
| `OLLAMA_GPU_CONCURRENCY` | 6 | GPU lane semaphore (dual-lane only) |
| `OLLAMA_CPU_CONCURRENCY` | 6 | CPU lane semaphore (dual-lane only) |

**Warning:** Setting both `OLLAMA_GPU_CONCURRENCY` and `OLLAMA_CPU_CONCURRENCY` to high values simultaneously on the same RTX 5090 caused a hard crash in testing. Keep total concurrent across lanes within GPU memory budget (`CAPACITY_GPU_HOURS_PER_DAY`, default 14 h/day).

---

## Backpressure States (from Monitor / AutomationManager)

### The four states

| State | When it fires | What happens |
|-------|---------------|-------------|
| **defer** | Worker pool `pressure >= AUTOMATION_DB_WORKER_UTILIZATION_SKIP_THRESHOLD` (default 0.82) **or** `waiters > 0`. Cross-host: published to `public.db_pool_pressure_advisory`. | AutomationManager skips new enqueues; phase workers requeue work for later. Not a CB state -- it is DB pool pressure. |
| **shed** | Any key in `OLLAMA_CB_KEYS` (not `ollama_embeddings`) is OPEN. | Intake phases (`collection_cycle`, `storyline_discovery`, `proactive_detection`, `document_collection`) are hard-paused. Must-run cadence also defers. Explicit Monitor phase trigger may still proceed. |
| **overload** | Timeout / 502-504 from Ollama -- host is alive but slow. | Raise overloaded flag; do **not** trip the breaker. Trickle drain continues (shrink batch sizes). Host unreachable -> transitions to OPEN circuit. |
| **trickle** | Under backlog / CB pressure, shrink LLM drain batches so work keeps moving without skip-and-burn. | Gradual throttle rather than hard pause. Keeps partial throughput while reducing contention. |

### Capacity states (Monitor Pulse - Capacity chip)

| State | Condition | Action |
|-------|-----------|--------|
| **in budget** | Drain demand <= GPU hours/day budget | Normal operation |
| **warning** | Demand > 100% of budget, < 200% | Watch -- may become underwater |
| **underwater** | Intake demand exceeds budget OR backlog drain exceeds 2x budget | Consider raising `CAPACITY_GPU_HOURS_PER_DAY` or adding GPU capacity |

---

## Blockage Detection Flow

```
[Generate / Embed Request]
         |
         v
[llm_service.py CB hub]
    +----+-----+
    |Lane router|  (GPU/CPU when dual-lane ON)
    +----+-----+
         |
    [Per-key circuit breaker]
    +--+--+--+--+
    |  |  |  |
   ollama ollama_gpu ollama_cpu ollama_pop_os
    |  |     |        |         |
    v  v     v        v         v
  CLOSED CLOSED CLOSED CLOSED  CLOSED
   |       |      |        |        |
   +--FAILURE_COUNT >= failure_threshold (2)--|
                          |
                   [CIRCUIT OPENS]
                          |
            +-------------+-------------+
            v           v               v
        shed_intake  defer_scheduled  notify_monitor
            |           |               |
            v           v               v
       Pause RSS/Discovery   Requeue work    Pulse chip:
       Discovery/Proactive  for later run   "Ollama CB: ollama_gpu"
       /DocumentCollection                  (error chip in Monitor)
            |
            v
     After recovery_timeout (300s):
           probe -> HALF_OPEN
           success? -> CLOSED OK
           fail?  -> OPEN again (300s cycle repeats)
```

### Detection signals

1. **Monitor Status chip:** `Ollama CB: ollama_gpu` (error outline) with tooltip showing open/half-open keys. Green = closed.
2. **AutomationManager health check:** reads `ollama_shedding` from circuit breaker service -> exposed in `GET /api/system_monitoring/automation/status`.
3. **Pulse chip - Capacity warning** when GPU hours/day budget is exceeded.
4. **Grafana:** `ni_ollama_circuit_open_*` time series metrics (via `/api/system_monitoring/prometheus`).

---

## Recovery Playbook

### Quick (host recovered)

1. Confirm host is back: `curl -sS "$OLLAMA_HOST/api/tags"`
2. Reset CB: **Monitor -> Actions -> Reset Ollama CB** or `POST /api/system_monitoring/circuit_breakers/reset`
3. Watch Monitor pulse chip for green.

### Auto-recovery (no action needed)

Wait 300 seconds. If the host is healthy, the half-open probe succeeds and the breaker auto-closes (`success_threshold=1`). No operator intervention required.

### When reset fails / host unrecoverable

1. Check GPU memory / OOM logs on the GPU host (dmesg, nvidia-smi).
2. Verify network tunnel (PopOS -> Dockside for embeddings; Widow -> PopOS for narrative).
3. If PopOS GPU is down: temporarily set `OLLAMA_DUAL_HOST_ROUTING_ENABLED=false` so all traffic routes through single `ollama_pop_os` path (if configured).
4. Check Dockside Ollama health if embeddings breaker (`ollama_embeddings`) opens -- this does not shed intake but blocks storylines from getting enriched.

### After recovery

1. Monitor **Pulse chip** for capacity state -> ensure drain catches up.
2. Check `automation_run_history` for skipped runs during the outage window.
3. If backlog grew significantly: adjust `CAPACITY_GPU_HOURS_PER_DAY` or enable `BULK_DUAL_LANE_CATCHUP`.

---

## Configuration Summary

| Env Var | Default | Role |
|---------|---------|------|
| `OLLAMA_HOST` | localhost:11434 | Primary Ollama host (CB key: `ollama`) |
| `OLLAMA_POP_OS_HOST` | PopOS LAN:11434 | GPU lane / narrative finisher (CB key: `ollama_pop_os`) |
| `OLLAMA_GPU_HOST` | -- | Dual-lane GPU destination (CB key: `ollama_gpu`) |
| `OLLAMA_CPU_HOST` | -- | Dual-lane CPU destination (CB key: `ollama_cpu`) |
| `OLLAMA_EMBEDDINGS_HOST` | Dockside tunnel | Embeddings appliance (separate CB key) |
| `OLLAMA_CONCURRENCY` | 6 | Global concurrency cap (when dual-lane is off) |
| `OLLAMA_GPU_CONCURRENCY` | 6 | GPU lane semaphore |
| `OLLAMA_CPU_CONCURRENCY` | 6 | CPU lane semaphore |
| `OLLAMA_DUAL_HOST_ROUTING_ENABLED` | false | Split generate traffic into GPU/CPU lanes |
| `OLLAMA_CB_KEYS` | tuple of 4 keys | Keys that shed intake when OPEN |
| `OLLAMA_EMBEDDINGS_CB_KEYS` | (`ollama_embeddings`,) | Separate reset, no shedding |
| `failure_threshold` | 2 | Failures before circuit opens |
| `recovery_timeout` | 300s | Seconds before half-open probe |
| `success_threshold` | 1 | Good probes needed to close |

---

## Related Docs

- [`MONITOR_REPORTING_AND_METRICS.md`](MONITOR_REPORTING_AND_METRICS.md) -- defer/shed/overload terminology, Monitor vs Grafana split, Prometheus metrics
- [`PIPELINE_OPERATIONS_WIDOW.md`](PIPELINE_OPERATIONS_WIDOW.md) -- pipeline handoffs and automation scheduling
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) -- Ollama CB troubleshooting section
- [`AGENTS.md`](../AGENTS.md) -- key flows, architecture principles, database connection rules

