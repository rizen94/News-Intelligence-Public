# Design Alignment with Project Plan and Intent

**Purpose:** High-level check that what is built matches stated project intent, architecture, and roadmap.  
**Audience:** Product/tech lead, onboarding, design review.  
**Last updated:** 2026-03-07.

---

## 1. Stated Intent (from AGENTS.md, README, scope docs)

| Intent | Source |
|--------|--------|
| **Core mission** | Automated collection → intelligent processing → storyline evolution → intelligence delivery |
| **Product** | AI-powered news aggregation and analysis; investigative journalism support |
| **Key flows** | (1) Article: RSS → processing → storyline linking → event extraction. (2) Storyline: create → add articles → analyze → timeline → watchlist. (3) Events: extract → deduplicate → story continuation → alerts |
| **Domain structure** | politics, finance, science-tech; per-domain articles, storylines, topics, rss_feeds, events; global watchlist, system_monitoring |
| **Architecture principles** | Single source of truth; reuse before create; consolidate don’t proliferate; snake_case (Python), PascalCase (React); flat `/api/` (no version in path) |

---

## 2. Alignment Summary

| Area | Aligned? | Notes |
|------|----------|--------|
| **Core mission** | ✅ Yes | Collection (RSS, finance sources), processing (article, ML, topics, entities), storyline evolution (CRUD, discovery, consolidation, timeline, watchlist), intelligence delivery (hub, RAG, synthesis, briefings, events) are all implemented and wired. |
| **Key flows** | ✅ Yes | RSS→articles→processing→topic/entity extraction; storylines with articles, timeline, watchlist; event extraction, tracked_events, event_chronicles, discovery from contexts. |
| **Domain structure** | ✅ Yes | Three domains with shared schema; per-domain tables; global watchlist and system_monitoring; DB and API follow this. |
| **Architecture principles** | ✅ Yes | Single DB module (`shared.database.connection`), single config patterns, domain routers under `/api/`, snake_case/PascalCase and flat `/api/` in use. |
| **Context-centric plan** | ✅ Largely | Phase 1–3 done: contexts, article_to_context, entity_profiles, entity_profile_sync/build, extracted_claims, pattern_discoveries, event_tracking (tracked_events, event_chronicles). Dual-mode (existing + context-centric) as planned. |
| **Orchestration “current state”** | ✅ As documented | CONTROLLER_ARCHITECTURE and PROJECT_SCOPE describe “orchestrators not fully in control.” Reality matches: OrchestratorCoordinator decides *when* to run RSS and finance refresh; AutomationManager, cron, topic workers, MLProcessingService run independently. |
| **Orchestration “target state”** | ⚠️ Not yet | ORCHESTRATOR_ROADMAP target is one loop deciding *what* to do next, with importance/watchlist driving “what stories to grow.” That single control loop and importance-driven ProcessingGovernor are not implemented. |
| **Finance** | ✅ Yes | FinanceOrchestrator owns all finance work (gold, FRED, EDGAR, analysis, schedule); evidence collector uses finance.articles; chain DB→API→web is connected. |
| **Docs and UX** | ⚠️ Minor gaps | README health URL updated to `/api/system_monitoring/health`. Optional: “News used” (rss_snippets) on finance result page; evidence preview button; some legacy “/api/v4/” references in older docs. |

---

## 3. What Matches the Plan

- **End-to-end chains** (PROJECT_SCOPE §5): Finance analysis, RSS→articles→evidence, orchestrator coordinator loop, storylines/content are implemented and connected DB → API → web.
- **Orchestrator coordinator**: Assess → plan (CollectionGovernor) → execute (RSS or finance refresh) → learn (record, decision log) → sleep; status and decision_log APIs; manual_override. Matches the described “Phase 1” behavior.
- **AutomationManager**: Phases (rss_processing, article_processing, ml_processing, topic_clustering, entity_extraction, event_tracking, context_sync, etc.) on defined intervals with dependencies. Matches CONTROLLER_ARCHITECTURE “Data Processing Controller” description.
- **Context-centric**: Contexts, article_to_context, entity_profiles, old_entity_to_new, claim extraction, pattern recognition, event tracking with run_event_tracking_batch and chronicles. Aligns with CONTEXT_CENTRIC_UPGRADE_PLAN Phases 1–3.
- **V6 / Newsroom**: Treated as optional and feature-flagged; chief_editor/archivist stubs. Plan does not require them for core flows.

---

## 4. Gaps vs Plan (by design or deferred)

| Gap | Plan reference | Status |
|-----|----------------|--------|
| **Single control loop** | ORCHESTRATOR_ROADMAP Phase A | Coordinator does not gate AutomationManager, cron, or API triggers. Multiple independent triggers (coordinator, AutomationManager, cron, collect_now) remain. |
| **“What to work on” / importance** | ORCHESTRATOR_ROADMAP Phase B–C | No importance score per storyline/topic driving ProcessingGovernor. Watchlist and automation config are not yet inputs to a single “what next” decision. |
| **ProcessingGovernor in the loop** | CONTROLLER_ARCHITECTURE §3.2, ORCHESTRATOR_ROADMAP | ProcessingGovernor exists but coordinator does not ask it “what processing to run next”; AutomationManager runs phases on its own schedule. |
| **Evidence preview / “News used” UI** | PROJECT_SCOPE §6, suggested next steps | Backend has evidence preview and rss_snippets; frontend does not yet show “News used” or a preview button. Documented as optional. |
| **User preemption, EDGAR checkpointing, etc.** | PROJECT_SCOPE §7 | Explicitly deferred. |

---

## 5. Conclusion

- **Intent and core design are aligned:** The system implements the stated mission (collection → processing → storyline evolution → intelligence delivery), domain structure, key flows, and context-centric foundation. Architecture principles (single source of truth, naming, flat API) are followed.
- **Documented “current state” of orchestration matches reality:** Orchestrators control finance and collection *timing*; the rest of the pipeline (AutomationManager, cron, workers) is intentionally described as independent in CONTROLLER_ARCHITECTURE and PROJECT_SCOPE.
- **Roadmap “target state” is not yet implemented:** A single loop that decides *what* to do next and uses importance/user guidance (ORCHESTRATOR_ROADMAP Phases A–C) is the stated direction but is not in place. That is a planned evolution, not a design violation.
- **Small doc/UX cleanups:** README health URL corrected; optional improvements (News used, evidence preview, remaining /api/v4/ references) are noted in scope/cleanup docs.

Overall, **what is built is aligned with the project plan and intents** as they are currently documented; the main open item is the *future* orchestration evolution (single loop, importance, ProcessingGovernor in the loop), which the roadmap already describes.
