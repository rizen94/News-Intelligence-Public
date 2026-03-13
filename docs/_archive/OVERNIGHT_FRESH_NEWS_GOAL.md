# Goal: Overnight Continuous Collection → Fresh News in the Morning

**Target:** Leave the system running overnight; orchestrators manage data pipelines; recurring cron supplements; orchestrators can run **additional collection** and **RAG analysis** based on **identified entities per storyline** to get more context.

**Last updated:** 2026-03-06

---

## 1. How close we are today

### What already works (leave running overnight)

| Capability | Status | Notes |
|------------|--------|--------|
| **Continuous RSS collection** | ✅ | AutomationManager runs `rss_processing` every 1h; OrchestratorCoordinator can run RSS every 5–120 min; optional cron 6 AM/6 PM; Widow worker every 10 min if enabled. |
| **Article → ML → topics → storylines** | ✅ | AutomationManager: article_processing (20m), ml_processing (20m), topic_clustering (20m), storyline_processing (30m). |
| **RAG enhancement for storylines** | ✅ | AutomationManager `rag_enhancement` every 30m: for each storyline (no RAG in last 1h), calls `enhance_storyline_context()` which **extracts entities from articles** and fetches Wikipedia + GDELT context. So RAG is already **entity-aware**; it’s just on a **fixed schedule**, not orchestrator-decided. |
| **Storyline consolidation** | ✅ | StorylineConsolidationService runs every 30 min from API lifespan. |
| **Cron as supplement** | ✅ | Optional: `setup_rss_cron_with_health_check.sh` (6 AM/6 PM), `setup_morning_data_pipeline.sh` (e.g. 4–6 AM). |
| **Finance (gold, EDGAR, analysis)** | ✅ | FinanceOrchestrator scheduler + queue; coordinator can trigger gold refresh. |

**Verdict:** If you **start the API and leave it running**, you already get overnight collection and processing. By morning you should have new articles, topics, storylines, and RAG-enhanced context. The main gaps are **authority** (orchestrators don’t yet “own” when things run) and **entity-driven initiative** (orchestrators don’t yet decide “get more data / RAG for this storyline’s entities”).

---

## 2. Gaps to close

### Gap A: Orchestrators don’t have full authority

- **Today:** AutomationManager has its **own** scheduler (10s poll); OrchestratorCoordinator only decides **when** to run RSS and gold. Cron and API triggers run work **independently**.
- **Goal:** Orchestrators manage pipelines; cron only **supplements** (e.g. “wake up” or “ensure run at 6 AM”) by asking the orchestrator to run, not by running collection directly.
- **Already documented:** [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) Phase A (single control loop): coordinator becomes the only thing that triggers pipeline work; AutomationManager becomes an executor; cron/API “request that coordinator run this.”

### Gap B: No orchestrator-driven “additional collection” for storyline entities

- **Today:** StorylineAutomationService can **discover** articles for a storyline using entities (`discover_articles_for_storyline` → entity-based search, RAG discovery). That’s used when **you** run storyline automation (e.g. from UI or API). Nothing in the **orchestrator loop** says “for storylines with these entities, run an extra collection or search and ingest.”
- **Goal:** Orchestrator has authority to run **additional** collection (e.g. entity-based search, or trigger ingestion for entities tied to a storyline) so storylines get deeper context overnight.
- **Needed:**  
  - A **recommendation** from a governor: “run entity-driven collection for storyline_id=42” (or “for entities [X,Y]”).  
  - An **action** the coordinator can execute: e.g. call `StorylineAutomationService.discover_articles_for_storyline()` and then **ingest** or **suggest** those articles into the storyline (or run a dedicated “entity-based fetch” that writes to the DB).  
  - Optional: a separate “entity-based collection” phase that pulls from external search or APIs for storyline entities and ingests results.

### Gap C: No orchestrator-driven “trigger RAG for this storyline” by priority

- **Today:** RAG enhancement runs on a **schedule** (every 30m for all storylines that haven’t been enhanced in 1h). The orchestrator does **not** decide “this storyline has new entities or high importance → run RAG now.”
- **Goal:** Orchestrators can trigger RAG analysis to get more context **based on** identified entities for each storyline (and ideally importance/watchlist).
- **Needed:**  
  - ProcessingGovernor (or EditorialGovernor) recommends “run RAG for storyline_id=42” (e.g. because of new entities, high importance, or watchlist).  
  - Coordinator executes that by calling existing `rag_service.enhance_storyline_context(...)` or ProgressiveEnhancementService.  
  - Optionally: **prioritize** which storylines get RAG first (importance, new entities, user watchlist), instead of “all storylines older than 1h.”

### Gap D: Overnight reliability and visibility

- **Today:** If the API crashes or the machine sleeps, overnight run stops. No single “overnight run” health or summary.
- **Goal:** Recurring cron supplements and you can trust “it ran overnight.”
- **Needed (small):**  
  - Optional: a **cron job** that runs once early morning (e.g. 5 AM) and calls `POST /api/system_monitoring/pipeline/trigger` (or a “request coordinator run” endpoint) so that even if the coordinator was idle, you get one full pipeline run before you wake.  
  - Optional: a **simple “overnight summary”** endpoint or log: last RSS run, last RAG run, article counts, so you can confirm “fresh news” is ready.

---

## 3. What needs to be built (prioritized)

### Tier 1: Minimal “overnight fresh news” (you’re almost there)

1. **Confirm and document “leave API running”**  
   - Ensure `start_system.sh` is the only thing needed on Primary; document that Widow worker is optional but gives extra RSS.  
   - Add a short “Overnight run” section to QUICK_START or ARCHITECTURE: start API, optional cron 6 AM/6 PM, optional 5 AM pipeline trigger.

2. **Optional: morning pipeline trigger via cron**  
   - Cron at e.g. 5 AM that calls `POST /api/system_monitoring/pipeline/trigger` so one full pipeline (RSS → topic clustering → AI analysis) runs before you read.  
   - Complements AutomationManager so you’re not solely dependent on its 1h/20m intervals for “fresh by 6 AM.”

3. **Optional: overnight summary**  
   - `GET /api/system_monitoring/overnight_summary` or similar: last collection time, last RAG run, article counts in last 12h. Lets you verify “fresh news” without digging logs.

**Outcome:** You can leave it running overnight and get fresh news in the morning with minimal new code; cron supplements and optional visibility.

---

### Tier 2: Orchestrators have authority (single loop)

4. **Phase A of ORCHESTRATOR_ROADMAP**  
   - AutomationManager phases become **callables** the coordinator (or ProcessingGovernor) can invoke.  
   - Coordinator asks ProcessingGovernor each cycle “what processing should run next?” and executes at most one (or a small batch).  
   - AutomationManager’s **own scheduler is disabled**; it only runs when the coordinator requests a phase.  
   - Cron and `pipeline/trigger` API **request** the coordinator to run (e.g. “enqueue high-priority run”) instead of running collection directly.

**Outcome:** One loop decides when every type of work runs; orchestrators “own” the pipelines; cron only supplements by asking the loop.

---

### Tier 3: Entity-driven additional collection and RAG

5. **ProcessingGovernor recommends “storyline automation” / “entity collection”**  
   - Extend ProcessingGovernor (or add EditorialGovernor) to recommend actions like:  
     - “run storyline automation for storyline_id=42” (discover + suggest/ingest articles for that storyline’s entities),  
     - or “run entity-based collection for entities [X,Y].”  
   - Use simple priority: e.g. storylines with automation_enabled, or with new entities, or on watchlist.

6. **Coordinator executes entity-driven collection**  
   - When the governor recommends “run storyline automation for storyline_id=42,” coordinator calls `StorylineAutomationService.discover_articles_for_storyline(42)` and then either:  
     - applies suggestions (e.g. auto-add to storyline if config allows), or  
     - writes discovered articles into the DB as new articles / storyline_articles.  
   - Optional: dedicated “entity-based fetch” that takes entity list, calls search or external APIs, and ingests.

7. **ProcessingGovernor recommends “run RAG for storyline X”**  
   - Governor recommends “run RAG for storyline_id=42” based on: new entities, not enhanced in N hours, importance/watchlist.  
   - Coordinator calls existing `rag_service.enhance_storyline_context(...)` (or ProgressiveEnhancementService) for that storyline only.  
   - RAG remains entity-based (existing code already extracts entities and fetches Wikipedia/GDELT); the **trigger** becomes orchestrator-driven and priority-based.

8. **Importance / watchlist feed into recommendations**  
   - Storyline importance (or watchlist) boosts priority for “run storyline automation” and “run RAG for this storyline.”  
   - Per ORCHESTRATOR_ROADMAP Phase C/D: importance score, proposed focus, user guidance.

**Outcome:** Orchestrators have authority to run additional collection and RAG based on identified entities per storyline; cron still supplements for regular updates.

---

## 4. One-paragraph summary

**Today:** Leaving the API running overnight already gives you continuous RSS, article processing, ML, topic clustering, storyline processing, and RAG enhancement on a schedule. Cron can add 6 AM/6 PM RSS and an optional 5 AM pipeline trigger. **Gaps:** (1) Orchestrators don’t yet have full authority—AutomationManager and cron run independently; (2) no orchestrator-driven “additional collection” or “run RAG for this storyline” based on entities. **To get to your goal:** Implement Tier 1 for minimal overnight confidence; Tier 2 (Phase A single loop) so orchestrators manage pipelines and cron only supplements; Tier 3 so the coordinator can run entity-based collection and priority-based RAG per storyline, with importance/watchlist feeding in.

---

## 5. References

- [DATA_INGESTION_PIPELINE_ASSESSMENT.md](DATA_INGESTION_PIPELINE_ASSESSMENT.md) — What controls collection and what’s orphaned.
- [ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md](ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md) — Phases A–E for single loop, “what to work on,” importance, initiative.
- [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md) — Current orchestrators and overlap.
