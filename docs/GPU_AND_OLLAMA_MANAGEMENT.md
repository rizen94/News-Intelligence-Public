# GPU and Ollama Management

How the system tracks GPU usage and temperature, and how it throttles Ollama work when the GPU gets hot.

---

## 1. What we do today

### Tracking (read-only)
- **Health endpoint:** `GET /api/system_monitoring/health` returns `gpu_temperature_c`, `gpu_utilization_percent`, `gpu_vram_percent`, `gpu_memory_used_mb`, `gpu_memory_total_mb` (from `nvidia-smi` or GPUtil).
- **Shared helper:** `api/shared/gpu_metrics.py` — `get_gpu_metrics()` and `should_throttle_ollama(max_temp_c=82)`.

### Throttling
- **AutomationManager:** Before any Ollama task runs, we check `should_throttle_ollama()`. If GPU temp ≥ 82 °C:
  - Log a warning and sleep 60 seconds.
  - Re-check; if still ≥ 82 °C, the task is re-queued (not run this cycle) so the GPU can cool.
- **Concurrency cap:** At most **3** concurrent Ollama tasks in the automation manager (semaphore). All LLM-using phases (topic clustering, ML processing, entity extraction, claim extraction, event tracking, entity profile build, editorial document/briefing generation, etc.) go through this semaphore so we don’t pile 10+ Ollama requests at once.

### What we don’t do
- **No dynamic fan or power cap** — we don’t change GPU hardware settings.
- **No per-request temp check** — only at task start; a long run can still keep the GPU hot until the next task checks again.

---

## 2. If the GPU is still heating up

- **Lower the throttle temp:** In `api/shared/gpu_metrics.py`, set `GPU_TEMP_THROTTLE_C = 78` (or lower) so we pause earlier.
- **Reduce concurrency:** In `api/services/automation_manager.py`, set `MAX_CONCURRENT_OLLAMA_TASKS = 2` (or 1) to reduce parallel load.
- **Ollama side:** Use a smaller model or `num_gpu` / context limits in Ollama config to reduce VRAM and heat.
- **Hardware:** Improve case cooling or GPU fan curve (e.g. via `nvidia-settings` or BIOS).

---

## 3. What was breaking (from logs)

### Primary: Topic clustering → DB error → cascade
- **Error:** `column "relevance_score" of relation "article_topic_assignments" does not exist`
- **Cause:** In some domain schemas, `article_topic_assignments` was created without the `relevance_score` column (e.g. older migration or different migration order).
- **Effect:** Topic clustering fails on the first article that gets an assignment. The DB transaction aborts, so every subsequent use of that connection fails with **"current transaction is aborted, commands ignored until end of transaction block"**. That cascades to RSS processing (every feed), so many feeds report the same error.
- **Fix:** Run migration **162**: it adds `relevance_score` to `article_topic_assignments` in each domain schema if missing.
  ```bash
  cd "/path/to/News Intelligence"
  .venv/bin/python -c "
  import os, sys
  sys.path.insert(0, 'api')
  os.chdir('api')
  from shared.database.connection import get_db_connection
  conn = get_db_connection()
  if conn:
      with open('database/migrations/162_article_topic_assignments_relevance_score.sql') as f:
          conn.cursor().execute(f.read())
      conn.commit()
      conn.close()
      print('Migration 162 applied.')
  "
  ```
  Or run the SQL file directly with `psql` against your DB.

### Secondary
- **"can't compare offset-naive and offset-aware datetimes"** — One feed (e.g. Swiss National Bank) has dates without timezone; the collector should use timezone-aware comparison or normalize dates.
- **Entity JSON parse failed** — LLM sometimes returns invalid JSON for entity extraction; the code has fallbacks but may log warnings.

---

## 4. Summary

| Item | Status |
|------|--------|
| GPU temp/usage tracking | Yes — health endpoint and `shared/gpu_metrics.py` |
| GPU temp throttling | Yes — pause/re-queue Ollama tasks when temp ≥ 82 °C |
| Ollama concurrency cap | Yes — 3 concurrent tasks, all LLM phases use semaphore |
| Topic clustering / RSS cascade | Fixed by migration 162 (add `relevance_score` where missing) |

After applying migration 162 and restarting the API, topic clustering should stop failing and the RSS “transaction aborted” cascade should stop. GPU throttling will help avoid sustained high temps when the pipeline is busy.
