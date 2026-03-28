# Resource budgets and lean pipeline discipline

This document operationalizes **explicit limits**, **avoiding wasted work**, and **periodic review**—the same habits that made small-machine code reliable—applied to the News Intelligence stack (Python, asyncio, Postgres, Ollama).

---

## 1. Treat RAM and connections as explicit budgets

### Database (per process)

Each process that imports `shared.database.connection` holds **up to**:

| Pool | Env (typical) | Purpose |
|------|----------------|--------|
| Worker | `DB_POOL_WORKER_MIN` / `DB_POOL_WORKER_MAX` | Automation, batch, RSS, enrichment |
| UI | `DB_POOL_UI_MIN` / `DB_POOL_UI_MAX` | Page loads, monitoring |
| Health | `DB_POOL_HEALTH_MIN` / `DB_POOL_HEALTH_MAX` | `health_check` + `automation_run_history` for that phase |
| SQLAlchemy | `DB_POOL_SA_SIZE` / `DB_POOL_SA_OVERFLOW` | ORM paths |

**Footprint rule:** sum, over **every** running process (API workers, automation host, scripts, cron), each pool’s **max** connections. That total must stay under PostgreSQL `max_connections` and any **PgBouncer** server pool limit.

See `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md` and `docs/CODING_STYLE_GUIDE.md` (connection pools).

### Automation / LLM (per API host)

Relevant env vars (see `configs/env.example` and `api/services/automation_manager.py`):

- `AUTOMATION_MAX_CONCURRENT_TASKS` — asyncio phase workers (fixed at process start).
- `AUTOMATION_EXECUTOR_MAX_WORKERS` — `ThreadPoolExecutor` for sync CPU work.
- `MAX_CONCURRENT_OLLAMA_TASKS` — global semaphore for Ollama-backed phase execution.
- `OLLAMA_CPU_CONCURRENCY` / `OLLAMA_GPU_CONCURRENCY` — per-lane HTTP concurrency when dual-host routing is on (`api/shared/services/llm_service.py`).
- `AUTOMATION_QUEUE_SOFT_CAP` — `0` = off (recommended); set only as a safety valve.

**Rule:** raising one knob without headroom elsewhere (DB, GPU VRAM, Ollama queue) just moves the queue.

---

## 2. Prefer streaming and chunking for huge text

**Principles:**

- Pass **slices** into LLM prompts (already common in extractors); avoid keeping multiple full copies of the same article in memory.
- **Do not** hold a DB connection open across LLM or HTTP (see `AGENTS.md` database rules).
- When adding new phases, prefer **one read → process chunk → write → release** over loading entire corpora into Python lists.

**Existing patterns to mirror:** prompt truncation in claim/event extraction services; batch limits via env (`CLAIM_EXTRACTION_BATCH_LIMIT`, etc.).

---

## 3. Centralize “expensive once” work

**Expensive:** embeddings, parsed HTML, normalized body text, cross-phase entity resolution results.

**Discipline:**

- One **canonical** stored representation (e.g. in `articles` or `intelligence.contexts`) where possible.
- If a cache is in-memory, use a **bounded** structure or TTL; unbounded dicts are debt.
- **Cache keys** should include domain, content hash or version, and model id when applicable.

Before adding a second code path that recomputes the same embedding for the same row, extend the first path or read from stored artifacts.

---

## 4. Keep scheduling honest (bounded tick + cooldown + backpressure)

Scheduling is **not** “as fast as possible”; it is **controlled** so DB and Ollama stay stable.

| Mechanism | Role |
|-----------|------|
| `AUTOMATION_SCHEDULER_TICK_SECONDS` | How often the scheduler loop enqueues candidates. |
| `AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS` | Min time before the same phase can enqueue again when it has backlog. |
| `WORKLOAD_BALANCER_ENABLED` | Optional extra variable cooldown for some phases (default off in code). |
| Resource router multipliers | `AUTOMATION_ROUTER_COOLDOWN_MULT_*` — soften or tighten backoff when CPU/GPU/DB look hot. |
| `COLLECTION_THROTTLE_PENDING_THRESHOLD` | Slows RSS when downstream enrichment/context work is heavy. |
| `AUTOMATION_QUEUE_SOFT_CAP` | Optional pause on most scheduled enqueues when queue depth is high (`0` = disabled). |

**Unbounded enqueue** (infinite pending `Task` objects) is **debt**—use `0` soft cap only with monitoring, or a very high cap as a last-resort safety valve.

---

## 5. Periodic audits (hot loops today)

**Wall time:** completed runs in `public.automation_run_history`:

```bash
PYTHONPATH=api uv run python scripts/automation_run_analysis.py --hours 24
```

**Rows / backlog:** `GET /api/system_monitoring/backlog_status` and per-phase pending in automation status.

**Interpretation:** phases with **high average duration** or **few completions but huge backlog** are candidates for batching, parallelism inside the phase, or removing serial bottlenecks—not only raising global worker counts.

---

## Checklist for changes

- [ ] Updated pool or worker counts? Recompute **footprint × processes** vs Postgres/PgBouncer.
- [ ] New LLM path? Confirm **lane** (CPU vs GPU) and **semaphore** limits.
- [ ] New long-running loop? Confirm **no** DB connection held across LLM/HTTP.
- [ ] Duplicated expensive computation? **Merge** or **read from store** instead.

---

## See also

- `AGENTS.md` — Database connection rules
- `docs/CODING_STYLE_GUIDE.md` — **Core principle 5** (resource budgets), **Connection pool architecture**, **Resource discipline and lean pipeline**
- `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`
- `scripts/automation_run_analysis.py` — Phase duration and run counts
