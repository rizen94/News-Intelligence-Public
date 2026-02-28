# Cursor Prompt — Finance Orchestrator Build

Paste this into Cursor as the guiding document for the orchestrator implementation.

**Implementation status:** All 6 phases complete. Orchestrator at `api/domains/finance/orchestrator.py`. Routes: gold/fetch, edgar/ingest, fetch-fred, analyze, schedule, tasks/{id}.

---

## Context for Cursor

You are building a `FinanceOrchestrator` class for a multi-domain research API. The finance domain already has working infrastructure. Your job is to build the central controller that ties all existing components together into an iterative, quality-controlled workflow.

### What Already Exists (Do Not Rebuild)

**Data sources — all returning DataResult or raw data, all tested:**
- FRED adapter at `api/domains/finance/data_sources/fred.py` — custom HTTP client, fetches economic series, caches in market_data_store
- Gold sources at `api/domains/finance/gold_sources/` — FreeGoldAPI (USD/oz) and FRED IQ12260 (index), preference logic in gold_amalgamator.py
- EDGAR at `api/domains/finance/data_sources/edgar.py` — index fetcher, filing downloader with caching, section extractor for Items 1/7/8, ingestion function for 5 mining companies (GOLD, NEM, FCX, AEM, WPM), rate limited at 10 req/sec

**Storage — all with schema versioning:**
- `api/domains/finance/data/api_cache.py` — general HTTP response cache
- `api/domains/finance/data/market_data_store.py` — time series storage, returns DataResult
- `api/domains/finance/data/vector_store.py` — ChromaDB wrapper, model-aware collection routing (bge_large vs nomic_embed suffix)
- `api/domains/finance/data/evidence_ledger.py` — provenance log, records every source fetch with status, error_type, timestamps

**Processing:**
- `api/domains/finance/embedding.py` — EvidenceChunk dataclass, ingest_evidence_chunks(), embed_with_ollama_fallback() returning (vec, model_name)
- `api/domains/finance/stats.py` — price_change_pct, validate_range, latest_value
- `api/domains/finance/llm.py` — thin wrapper around shared LLMService

**Infrastructure:**
- `api/config/paths.py` — centralized path resolution
- `api/config/sources.yaml` — source registry with scope annotations
- `api/shared/data_result.py` — DataResult generic type with success, data, error, error_type
- `api/domains/finance/data_sources/__init__.py` — dynamic source loader, get_source(), get_all_sources(), list_source_ids()

**Routes:**
- `api/domains/finance/routes/finance.py` — GET/POST gold endpoints, POST edgar/ingest endpoint, domain validation

**Known issue:** FRED adapter and gold sources still return raw lists on failure instead of DataResult in some paths. The orchestrator should handle both gracefully until the retrofit is complete.

**Known issue:** Agnico Eagle CIK 0000001832 returns 404 from EDGAR. The orchestrator should handle missing/invalid CIKs without failing the entire batch.

---

## Architecture — What to Build

### Single Orchestrator Class

File: `api/domains/finance/orchestrator.py`

One class called `FinanceOrchestrator`. It holds references to every infrastructure component. It is the only thing that decides task ordering, iteration, and quality acceptance. Routes become thin — they validate input, submit a task to the orchestrator, and return whatever it delivers.

The orchestrator is initialized once at startup in `main_v4.py` and passed all component references. It is async throughout.

### Three Queue Types

**CPU worker pool** — for data fetching, embedding, statistical computation, evidence retrieval, chunking, fact-checking. These run in parallel across available cores. Use asyncio with a configurable concurrency limit. Independent tasks (FRED fetch and EDGAR fetch) run simultaneously. Dependent tasks (embedding waits for download) are sequenced by the orchestrator's dependency tracker.

**GPU queue** — for LLM inference only. Strictly serialized, one prompt at a time. Everything that needs the LLM submits to this queue and waits. The orchestrator front-loads all data gathering and evidence assembly on CPU queues so the prompt is fully built before it hits the GPU queue. No mid-generation data requests.

**Priority rules** — user-facing requests are high priority in all queues. Scheduled background tasks are low priority. Orchestrator-generated revision tasks (fact-check failed, need re-synthesis) are medium priority. User requests preempt background tasks. Within the GPU queue, fact-check revision passes on user output take priority over first-draft generation for background tasks.

### Iterative Evaluation Loop

The orchestrator does not run a linear pipeline. It runs a loop: plan, execute, evaluate, decide. If evaluation fails, it revises the plan and loops. Each task has an iteration budget (default 3). If the budget is exhausted, the orchestrator returns the best result it has with a reduced confidence score and a note about what's missing.

The loop phases are:
1. **Plan** — determine which workers to call, in what order, with what parameters
2. **Execute** — dispatch to CPU and GPU queues, collect results into task context
3. **Evaluate** — check results against quality criteria for this task type
4. **Decide** — accept (deliver result), revise (modify plan, loop back to execute), or fail (budget exhausted, deliver best effort with warnings)

### Fact-Checking Philosophy

The system verifies concrete data only. It does not evaluate causal reasoning or predictions.

**Verified:** prices, dates, percentages, company names, filing references, series identifiers, time ranges. If the LLM says "gold hit $2,672 on September 30, 2024" both the price and the date must exist in the evidence that was provided to it.

**Not verified:** causal claims, qualitative assessments, predictions. "Rising geopolitical tensions likely contributed to the price increase" is interpretive and left alone.

**Mechanic:** Before the LLM sees anything, the orchestrator builds an evidence index — a flat list of every verifiable fact with a reference ID, source, date, and value. The prompt includes these references. After generation, a verification pass extracts concrete claims from the output and checks each one against the index. Claims that match are verified. Claims that contradict the evidence are fabricated and trigger revision. Claims not in the evidence but not contradicting it are marked unsupported (acceptable for interpretive statements, flagged for concrete numbers).

---

## Data Structures to Define

All of these go in `api/domains/finance/orchestrator_types.py` or a similar module. They are dataclasses, not ORM models.

### Task
- task_id: auto-generated unique identifier
- task_type: enum — refresh, ingest, analysis, report, scheduled_refresh
- priority: enum — high (user-facing), medium (orchestrator revision), low (scheduled)
- parameters: dict — topic, query, source filters, date range, anything task-specific
- iteration_budget: int — max passes through the evaluation loop, default 3
- current_iteration: int — starts at 0
- context: TaskContext — mutable accumulator for everything gathered during execution
- status: enum — queued, planning, executing, evaluating, revising, complete, failed
- created_at, updated_at: timestamps

### TaskContext
- fetched_data: dict mapping source name to DataResult
- evidence_index: list of EvidenceIndexEntry
- evidence_chunks: list of EvidenceChunk
- stats_results: dict of computation name to result
- llm_prompt: str or None
- llm_response: str or None
- verification_result: VerificationResult or None
- revision_notes: list of str — what the orchestrator decided to fix on each iteration

### EvidenceIndexEntry
- ref_id: str — e.g. "REF-001"
- source: str — e.g. "fred", "freegoldapi", "edgar_10k"
- identifier: str — series ID, filing accession number, etc.
- date: date or datetime
- value: str or float — the concrete fact
- unit: str — "USD/oz", "index", "percent", etc.
- context: str — brief description of what this entry represents

### VerificationResult
- total_claims: int
- verified: int
- unsupported: int — not in evidence but not contradicting
- fabricated: int — contradicts evidence
- details: list of ClaimCheck (each with the claim text, the ref_id it should match, and the verdict)

### TaskResult
- task_id: str
- status: enum — success, partial, failed
- output: str or structured data — the final deliverable
- confidence: float — 0.0 to 1.0, reduced for unverified claims or exhausted iteration budget
- iterations_used: int
- provenance: list of EvidenceIndexEntry — what backed this result
- verification_summary: VerificationResult
- warnings: list of str — anything the orchestrator wants the consumer to know
- duration_ms: int

### QualityCriteria
- min_sources: int — minimum number of distinct sources that must contribute data
- min_evidence_chunks: int — minimum chunks retrieved for analysis tasks
- require_stat_validation: bool — whether statistical assertions must be verified against data
- max_unsupported_claims: int — how many concrete claims can lack evidence backing
- max_fabricated_claims: int — should be 0 for acceptance, any fabrication triggers revision

---

## Phase-by-Phase Build Checklist

### Phase 1 — Data structures and skeleton ✅

**Goal:** Orchestrator class exists, initializes with all components, accepts tasks, but doesn't execute them yet.

Checklist:
- [x] Define all data structures in orchestrator_types.py (Task, TaskContext, EvidenceIndexEntry, VerificationResult, TaskResult, QualityCriteria)
- [x] Define task type and priority enums
- [x] Define status enum for task lifecycle
- [x] Create orchestrator.py with FinanceOrchestrator class
- [x] Constructor accepts all component references (source loader, market_data_store, vector_store, evidence_ledger, embedding module, stats module, llm wrapper)
- [x] submit_task() method that creates a Task, assigns priority, adds to internal queue, returns task_id
- [x] get_task_status() method that returns current state of a task
- [x] get_task_result() method that returns TaskResult if complete
- [x] Initialize orchestrator in main_v4.py lifespan, passing all component references
- [x] Unit test: orchestrator initializes, accepts a task, returns queued status

### Phase 2 — CPU worker pool and data refresh ✅

**Goal:** The orchestrator can execute a refresh task — fetch from multiple sources in parallel, store results, record in ledger.

Checklist:
- [x] Build async worker pool with configurable concurrency limit (ThreadPoolExecutor + run_in_executor)
- [x] Implement plan_refresh() — consults topic parameter to determine which sources (gold, edgar, fred)
- [x] Implement execute_refresh() — dispatches fetch calls via executor in parallel, collects results into task context
- [x] Handle partial failures — if one source fails, continue with others (gold amalgamator records in ledger)
- [x] Handle the Agnico Eagle CIK 404 case — EDGAR ingest_edgar_10ks already skips failed companies
- [x] After all fetches complete, store via gold_amalgamator (calls market_data_store) / edgar (embeds to vector store)
- [x] Record every fetch in evidence_ledger — gold_amalgamator and edgar do this; orchestrator records task-level failures
- [x] Implement evaluate_refresh() — check sources succeeded vs min_sources
- [x] If evaluation fails, accept partial (status=complete)
- [x] Build RefreshSummary and return as TaskResult
- [x] Refactor gold routes: POST gold/fetch submits refresh task, awaits run_task
- [x] Refactor edgar route: POST edgar/ingest submits ingest task, awaits run_task
- [x] Preserve gold_amalgamator.py — orchestrator calls it internally
- [x] Tests: refresh with mocked fetch_all (plan_refresh, run_task with mock)

### Phase 3 — Evidence index and ingestion pipeline ✅

**Goal:** After a refresh, the orchestrator builds an evidence index from fetched data and ingests evidence chunks into the vector store.

Checklist:
- [x] Implement build_evidence_index() — extracts verifiable facts from refresh_results, assigns REF-ids
- [x] For FRED data: each observation becomes an index entry (date, value, series ID)
- [x] For gold sources: each price point becomes an index entry (date, USD/oz value, source name), max 100 per source
- [x] For EDGAR: summary entry (chunks count); filing metadata per company deferred
- [x] plan_ingest/execute_ingest — EDGAR uses existing ingest_edgar_10ks (chunking/embedding in embedding module)
- [x] Single embedding model — ingest_evidence_chunks uses embedding module's model
- [x] Evidence index stored in task.context.evidence_index and TaskResult.provenance
- [ ] evaluate_ingest — verify chunks retrievable (deferred; ingest success checked via count)
- [x] Refresh chains into build_evidence_index after evaluate_refresh
- [x] Standalone ingest (TaskType.ingest) builds evidence index from ingest_results
- [x] Test: evidence index built from real gold refresh, provenance in TaskResult

### Phase 4 — GPU queue and LLM synthesis ✅

**Goal:** The orchestrator can execute an analysis task — retrieve evidence, build a prompt with the evidence index, call the LLM, return the response.

Checklist:
- [x] GPU serialization — asyncio.Lock ensures one LLM call at a time
- [x] plan_analysis() — determines query, topic, n_chunks
- [ ] Stale data check — refresh triggered; currently always runs gold refresh for analysis
- [x] retrieve_evidence() — embed query, vector_store.query for semantic chunks
- [x] compute_stats() — latest_value, price_change_pct from evidence index
- [x] build_prompt() — evidence index (REF-ids), stats, chunks, query; system prompt instructs citation
- [x] Prompt includes evidence index with REF-ids, citation instructions
- [x] LLM called via finance.llm.generate, response in task context
- [x] POST /{domain}/finance/analyze — query, topic params, returns response
- [x] Test: analysis task with real gold data, provenance in result

### Phase 5 — Verification loop ✅

**Goal:** After LLM generates output, the orchestrator fact-checks concrete claims against the evidence index and revises if needed.

Checklist:
- [x] extract_claims + verify_claims in _extract_and_verify_claims — REF-ids, dollar amounts, dates via regex
- [x] CPU-only extraction (no LLM)
- [x] Match logic: REF-id must exist in index; dollar/date matched against evidence
- [x] VerificationResult with verified/unsupported/fabricated counts and ClaimCheck details
- [x] evaluate_analysis() — check against max_fabricated_claims (0), max_unsupported_claims (5)
- [x] Revision loop: if fail → _build_revision_prompt → next iteration; budget enforced
- [x] revise_analysis via _build_revision_prompt — original response + failed claims + evidence
- [x] Confidence: 1.0 - 0.02*unsupported - 0.1*fabricated - 0.1*iterations
- [x] TaskResult includes verification_summary, confidence; analyze route returns verification

### Phase 6 — Scheduling ✅

**Goal:** The orchestrator generates and executes tasks on a timed basis without external cron.

Checklist:
- [x] Scheduler in orchestrator — asyncio task, 60s poll, config from finance_schedule.yaml
- [x] finance_schedule.yaml: gold_refresh daily, edgar_ingest weekly
- [x] Scheduled tasks use TaskPriority.low
- [ ] User preemption — queue ordering (deferred; both use same run_task)
- [ ] Catch-up on startup — first run executes all due tasks
- [x] GET /{domain}/finance/schedule — next run, last run per task
- [ ] Checkpointing for EDGAR — deferred

### Post-Phase Polish ✅

- [x] Topic "all" includes gold + edgar in plan_refresh
- [x] FRED fetch route migrated to orchestrator (POST fetch-fred → refresh topic=fred)
- [x] GET /{domain}/finance/tasks/{task_id} — poll task status and result
- [x] POST analyze ?wait=false — return task_id for async polling

---

## Integration Points — How Existing Code Connects

**Gold amalgamator** — the orchestrator imports its preference logic and uses it during gold refresh planning. The amalgamator module stays as a file but routes stop calling it directly. The orchestrator calls it internally when the task topic is gold.

**Dynamic source loader** — the orchestrator calls get_source() and list_source_ids() during planning to determine what's available. When a new source is added to sources.yaml and registered, the orchestrator automatically includes it in relevant refresh plans.

**Evidence ledger** — the orchestrator writes to it on every worker dispatch, not just successful ones. Failed fetches, skipped sources, revision passes — all recorded. The ledger becomes the complete audit trail for every task.

**Existing routes** — refactor incrementally. Start by adding the new analyze endpoint alongside existing endpoints. Then migrate gold routes to use the orchestrator. Then migrate edgar route. Don't break existing endpoints during the transition — they should continue working through the orchestrator with identical external behavior.

---

## Rules for Cursor

- Do not rewrite existing modules. Import and use them as they are.
- If an existing module's interface doesn't quite fit, add a thin adapter method in the orchestrator rather than changing the module.
- The FRED adapter and gold sources may return raw lists instead of DataResult in some failure paths. Wrap their calls in try/except and produce DataResult in the orchestrator if the source doesn't.
- All orchestrator methods are async.
- Use asyncio.gather() for parallel CPU tasks. Use a simple asyncio.Queue for the GPU queue.
- Log every decision the orchestrator makes — task accepted, plan created, worker dispatched, evaluation result, revision triggered, task completed. Use the finance logger.
- Every TaskResult must include full provenance — which sources were consulted, which succeeded, which failed, how many iterations, what the confidence is.
- Tests go in tests/unit/test_finance_orchestrator.py. Mock all external dependencies. Test the orchestrator's decision logic, not the components it calls.
