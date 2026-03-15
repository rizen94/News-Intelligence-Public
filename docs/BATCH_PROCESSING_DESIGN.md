# Batch Processing Design — Production Timings

Realistic batch sizes, intervals, and backpressure for context sync, claim extraction, event tracking, story enhancement, and entity enrichment. **Principle: small batches frequently beat large batches rarely** — prevents backlogs and keeps the system responsive.

---

## 1. Context Sync

**Schedule:** Every **15 minutes** (incremental).

| Setting | Value | Rationale |
|--------|--------|-----------|
| Batch size | 100 | ~5–10s per batch; embedding/DB work stays bounded |
| Timeout per batch | 30s | Avoid runaway runs |
| Full sync (10k contexts) | ~15–20 min | When backfilling |

**Reality:** 100 contexts ≈ 500–1000 facts to sync; embedding ~50ms per fact; DB ~200ms per context batch.

---

## 2. Claim Extraction

**Schedule:** Every **30 minutes**.

| Setting | Value | Rationale |
|--------|--------|-----------|
| Max contexts per run | 50 | LLM rate limits (e.g. 100 req/min) |
| Parallel requests | 5 | LLM concurrency cap |
| Confidence threshold | 0.7 | Configurable |
| Retry failed | After 60s | Back off on errors |

**Reality:** 2–5s per context; 50 contexts ≈ 20–50s total; cost-controlled by limiting run size.

---

## 3. Event Tracking

**Schedule:** Every **1 hour**.

| Setting | Value | Rationale |
|--------|--------|-----------|
| Time window | 6h | Focused; overlapping runs catch delayed correlations |
| Context limit | 1000 | Max contexts to scan per run |
| Early termination | Optional | Stop when enough events found |

**Reality:** ~10ms per context; 1000 contexts ≈ 10–15s scan + ~5s correlation ≈ 15–20s per batch.

---

## Routine Processing Schedule (Automation Manager)

| Phase | Interval | Batch / constraint | Typical duration |
|-------|----------|--------------------|------------------|
| **Context sync** | 15 min | 100 contexts/domain | 30–60s |
| **Claim extraction** | 30 min | 50 contexts | 1–2 min |
| **Event tracking** | 1 hour | 1000 contexts | ~30s |
| **Story state triggers** | 5 min | 100 fact changes, 20 queue | ~2s per 100 changes |
| **Story enhancement** | 5 min | 10 stories, 60s budget | ≤60s |
| **Entity enrichment** | 30 min | 20 entities/run | ~10s per entity |

---

## Queue Limits and Backpressure

### Entity Enrichment Queue

- Process **max 20 entities per run** (LLM limits).
- Timeout per entity: **10s** (implement in enrichment call if needed).
- **Skip run if queue depth > 1000** (system overloaded).
- Priority: new > updated > historical (order by `updated_at ASC NULLS FIRST`).

### Story Enhancement

- **Max 10 stories per run** (queue_batch=10).
- Each story: ~5–10s update.
- Run every 5 minutes; **total time budget ~60s** per run.

### Change Detection (fact_change_log / story_update_queue)

- Process in **100-change batches** (~2s per batch).
- If behind **>10k changes**: alert and consider “skip to recent” or critical-only mode.

---

## Backpressure Handling

### When system gets behind

1. **Incremental sync > 1 hour behind**
   - Switch to “critical only” (e.g. high-confidence facts).
   - Optionally skip embedding updates temporarily.

2. **LLM queue > 30 minutes**
   - Pause non-critical extraction.
   - Focus on key entities only.
   - Use cached results more aggressively.

3. **Event correlation > 12 hours behind**
   - Reduce correlation window to 1 hour.
   - Process only major event types.
   - Catch up in off-peak.

### Cost controls

- **LLM calls:** e.g. max $50/day budget (configure and monitor).
- **Embedding generation:** e.g. max 100k/day.
- **Database writes:** batch to max ~1000/s where applicable.
- Throttle before hitting limits.

---

## Code References

- Context sync: `context_processor_service.sync_domain_articles_to_contexts(limit=100)`
- Claim extraction: `claim_extraction_service.run_claim_extraction_batch(limit=50)`
- Event tracking: `event_tracking_service.run_event_tracking_batch(limit=100)`
- Story state: `story_state_trigger_service.process_fact_change_log(batch_size=100)`, `process_story_update_queue(batch_size=20)`
- Enhancement cycle: `enhancement_orchestrator_service.run_enhancement_cycle(fact_batch=100, queue_batch=10, …)`
- Entity enrichment: `entity_enrichment_service.run_enrichment_batch(limit=20)` + `ENTITY_ENRICHMENT_QUEUE_LIMIT = 1000`

Schedules and estimated durations: `api/services/automation_manager.py` (`schedules`, `PHASE_ESTIMATED_DURATION_SECONDS`).

---

## Orchestrators and API alignment

- **AutomationManager** — Uses the batch sizes and intervals above in `_execute_context_sync`, `_execute_claim_extraction`, `_execute_event_tracking`, `_execute_story_state_triggers`, `_execute_story_enhancement`, `_execute_entity_enrichment`; schedules use the intervals in this doc.
- **ProcessingGovernor** — Reads `api/config/orchestrator_governance.yaml` `processing.phases` (context_sync 900s, claim_extraction 1800s, event_tracking 3600s, etc.) to recommend the next phase to the OrchestratorCoordinator; intervals match the production schedule.
- **Context-centric API** (`api/domains/intelligence_hub/routes/context_centric.py`) — `sync_contexts` default limit 100; `run_story_state_triggers` defaults fact_batch=100, queue_batch=20; `run_enhancement_cycle` defaults fact_batch=100, queue_batch=10; `run_entity_enrichment` default limit=20. Manual API runs use the same production defaults.
