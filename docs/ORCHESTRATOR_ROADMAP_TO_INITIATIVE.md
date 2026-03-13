# Roadmap: From Current Orchestration to Initiative-Taking News App

> **Goal:** The orchestrators run in a single loop and control every aspect of research, journalism, and reporting. The news app **takes initiative** to build and grow stories it considers important, with **guidance and input from the user** shaping what “important” means and where to focus.
>
> **References:** [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md) §2.6, [PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md](PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md) §9. Historical: _archive/ORCHESTRATOR_DEVELOPMENT_PLAN.md.

---

## 1. Target state (one sentence)

**One coordination loop** decides, each cycle, **what to do next** (collect, process, analyze, or develop a storyline); the system **proposes and pursues** stories it deems important (using quality, impact, velocity, cross-domain signals, and user interest); **user guidance** (watchlist, preferences, review queue, overrides) steers which stories get attention and how aggressive automation is.

---

## 2. Current state (recap)

| Under orchestrator control | Independent |
|----------------------------|-------------|
| **FinanceOrchestrator** — All finance-domain work. | **AutomationManager** — Own loop; runs RSS, article, ML, topics, storylines, RAG, cleanup on a fixed schedule. |
| **OrchestratorCoordinator** — Only *when* to run RSS and gold refresh. | **Cron**, **StorylineConsolidationService**, **TopicExtractionQueueWorker**, **MLProcessingService**, pipeline/API triggers. |

So today the system has **no single owner** for “what to work on.” AutomationManager runs **phases** on a **schedule**; it does not choose **which storylines to develop** or **which analyses to run** based on importance or user interest.

---

## 3. Gaps to close

1. **Single control loop** — One loop (the coordinator) should be the only place that decides “do X next.” All pipeline work (collection, processing, storyline automation, consolidation, etc.) is **triggered by** that loop, not by separate timers or cron.
2. **“What to work on”** — The loop must choose **what** to do, not only **when** (e.g. “run topic_clustering” vs “run topic_clustering for finance and politics, then develop storylines A and B”).
3. **Importance / initiative** — The app needs a notion of **story importance** and **editorial priority** so it can propose and pursue stories: e.g. watchlist items, high velocity, cross-domain impact, coverage gaps, user-defined focus areas.
4. **User guidance as input** — Watchlist, storyline automation settings, review-queue approvals/rejections, and manual overrides must feed into the coordinator’s decisions so “initiative” stays within user-defined guardrails.

---

## 4. Phased roadmap

### Phase A: Single control loop (orchestrators gate all work)

**Objective:** The **OrchestratorCoordinator** is the only component that triggers pipeline work. AutomationManager, cron, and API no longer start work on their own; they run only when the coordinator (or a governor it calls) says “run this now.”

| Step | Action |
|------|--------|
| A.1 | **Expose AutomationManager phases as callables** — Coordinator (or ProcessingGovernor) can invoke “run rss_processing,” “run article_processing,” “run storyline_processing,” etc., with optional domain/filter. |
| A.2 | **Coordinator asks ProcessingGovernor each cycle** — In addition to CollectionGovernor (“fetch RSS or gold?”), coordinator asks ProcessingGovernor “what processing should run next?” (e.g. “storyline_processing,” “topic_clustering for politics”). Execute at most one collection + one processing action per cycle (or a small batch if design allows). |
| A.3 | **Stop AutomationManager’s own scheduler** — AutomationManager no longer runs its 10s poll loop; it only executes when the coordinator (via ProcessingGovernor) requests a phase. Optionally keep a “fallback timer” that runs phases on a very slow schedule if coordinator is down (graceful degradation). |
| A.4 | **Route cron and API through coordinator** — Cron jobs (e.g. RSS, log archive) either (1) call coordinator “force_collect_now” / “run_phase” so the same loop owns the work, or (2) are deprecated in favor of coordinator-driven collection. Pipeline trigger and `collect_now` APIs become “request that coordinator run this soon” (e.g. enqueue a high-priority request) rather than running work directly. |
| A.5 | **StorylineConsolidationService and topic workers** — Either started by the coordinator (e.g. “run consolidation” as a phase) or triggered on a schedule that the coordinator sets (so the loop still “owns” when they run). |

**Outcome:** One loop decides *when* every type of work runs. No more independent AutomationManager or cron triggers.

---

### Phase B: ProcessingGovernor drives “what” (priority queue of phases)

**Objective:** ProcessingGovernor doesn’t just answer “what phase?”; it answers “what phase, for which domain or storyline, at what priority?” using a **priority queue** informed by resource and learning governors.

| Step | Action |
|------|--------|
| B.1 | **ProcessingGovernor returns a ranked list** — Each cycle it returns one or more “next best actions” (e.g. “run topic_clustering for politics,” “run storyline_automation for storyline_id=42,” “run consolidation for finance”) based on: last run times, dependencies, resource budget, and a simple priority (e.g. user request > watchlist > scheduled). |
| B.2 | **ResourceGovernor gates work** — Before executing, coordinator checks ResourceGovernor (LLM budget, API limits). If budget is low, skip low-priority processing and prefer user/watchlist-triggered work. |
| B.3 | **State records “last run” per phase/domain** — Orchestrator state (e.g. `last_processing_times`: phase → domain → timestamp) so ProcessingGovernor can recommend “topic_clustering politics hasn’t run in 20 min.” |

**Outcome:** The loop chooses *what* to process (which phase, which domain/storyline), not only “run the next phase in order.”

---

### Phase C: Importance and “what stories to grow”

**Objective:** The system has an explicit notion of **story/storyline importance** and uses it to decide which storylines to develop (e.g. run RAG, run story continuation, add articles via storyline automation). User inputs (watchlist, preferences) boost priority.

| Step | Action |
|------|--------|
| C.1 | **Importance score (per storyline / topic)** — Combine existing signals: watchlist (user said “follow this”), storyline automation settings (user said “this storyline matters”), quality/impact scores from articles, velocity (recent activity), coverage gaps, cross-domain links. Produce a scalar or tier (e.g. high / medium / low) per storyline or topic. |
| C.2 | **ProcessingGovernor uses importance** — When recommending “run storyline_automation” or “run story_continuation,” prefer storylines with higher importance; when recommending “run topic_clustering,” prefer domains with more high-importance storylines or recent breaking signals. |
| C.3 | **Feed watchlist and automation config into state** — Coordinator (or a small “EditorialGovernor”) reads watchlist and storyline automation_enabled / automation_mode / search_keywords so that “user guidance” is visible to the loop. |
| C.4 | **Review queue as feedback** — When user approves/rejects suggested articles (storyline_article_suggestions), log to decision_history or learned_patterns so LearningGovernor can adjust importance or relevance over time (optional, can be Phase D). |

**Outcome:** The app spends more effort on storylines and topics that are (a) marked important by the system and (b) aligned with user guidance (watchlist, automation config).

---

### Phase D: Initiative (app proposes and pursues stories)

**Objective:** The app **proactively proposes** “we should develop this storyline” or “we should run an analysis on this topic” and then does that work in the loop. User can guide by approving, rejecting, or narrowing focus.

| Step | Action |
|------|--------|
| D.1 | **“Proposed focus” queue** — A small layer (e.g. EditorialGovernor or Chief Editor role) produces a list of **proposed focus items**: e.g. “develop storyline X (importance 0.8, velocity high),” “run finance analysis for topic Y,” “investigate pattern Z.” These are not mandatory; they are suggestions the coordinator can schedule. |
| D.2 | **Coordinator consumes proposed focus** — Each cycle, in addition to “next collection” and “next processing,” coordinator considers “next proposed focus.” It schedules RAG, story continuation, storyline automation, or analysis for those items when resources allow. |
| D.3 | **User visibility and override** — UI shows “System focus: developing storylines A, B; next: analysis for C.” User can promote, demote, or remove items (e.g. “don’t focus on C”) so the loop respects guidance. Optional: “proposed focus” goes through a review step (e.g. “approve before we spend LLM on this”). |
| D.4 | **Learning from outcomes** — When the system develops a storyline and the user later engages (e.g. adds to watchlist, reads, approves suggestions), record that as positive feedback; when the user removes from focus or rejects, record as negative. LearningGovernor uses this to refine importance and proposal logic. |

**Outcome:** The news app takes **initiative** (proposes what to build and grow) and **adjusts** based on user guidance and outcomes.

---

### Phase E: User guidance as first-class input

**Objective:** All user guidance is explicit input to the orchestration loop: watchlist, focus areas, automation settings, review queue, and overrides. The loop treats them as constraints and high-priority signals.

| Step | Action |
|------|--------|
| E.1 | **Central “user guidance” state** — One place (e.g. in orchestrator state or a small service) aggregates: watchlist storyline IDs, user-defined “focus entities” or “focus topics,” automation mode per storyline, and recent overrides (“don’t run X,” “run Y now”). |
| E.2 | **Governors read user guidance** — CollectionGovernor, ProcessingGovernor, and any EditorialGovernor read this state so that watchlist and focus areas get higher priority; overrides can force or block actions. |
| E.3 | **Preferences and guardrails** — Optional: user settings like “max auto-approved articles per storyline per day,” “always put finance analysis above digest generation,” “never run RAG on storylines I haven’t watched.” These become rules the coordinator enforces. |
| E.4 | **Docs and API** — Document “how user guidance affects the loop” and expose a small API (e.g. “get current focus,” “set override”) so the UI and power users can see and steer behavior. |

**Outcome:** The app takes initiative **within** user-defined guardrails; “important” is a mix of system signals and user guidance.

---

## 5. How this fits existing pieces

| Existing piece | Role in roadmap |
|----------------|-----------------|
| **OrchestratorCoordinator** | Becomes the **single loop**; each cycle it asks CollectionGovernor, ProcessingGovernor, and (later) EditorialGovernor, then executes one or a few actions. |
| **ProcessingGovernor** | Grows from “status + trigger_finance_analysis” to **recommending the next processing action(s)** (phase + domain/storyline + priority) and later consuming importance + proposed focus. |
| **CollectionGovernor** | Unchanged in role; remains “when to fetch RSS / gold.” Optionally receives “user said run now” from overrides. |
| **AutomationManager** | Becomes an **executor**: exposes “run_phase(phase_name, domain=…)” and stops its own scheduler (Phase A). |
| **FinanceOrchestrator** | Stays the finance controller; coordinator (via ProcessingGovernor or CollectionGovernor) still calls `submit_task(refresh|analysis)`. |
| **Storyline automation** | Becomes a **phase** the coordinator can run (“run storyline_automation for storyline_id=X”); importance and user config determine which storylines get that run. |
| **Watchlist** | Feeds **user guidance** and **importance** (watchlist = high priority); coordinator prioritizes watchlist storylines for consolidation, continuation, and automation. |
| **Review queue (storyline_article_suggestions)** | User approvals/rejections become **feedback** for learning and importance (Phase C/D). |
| **v6 roles (Chief Editor, Reporter, etc.)** | Can be implemented **on top** of this loop: e.g. Reporter = collection + breaking-news detection; Journalist = pattern/investigation; Editor = quality + narrative; Chief Editor = proposed focus + resource allocation. Event bus (Redis) is optional; the same flow can be in-process first. |

---

## 6. Suggested order and dependencies

- **Phase A first** — Without a single loop, “initiative” has no single place to act. A.1–A.5 are the foundation.
- **Phase B next** — So the loop can choose *what* to process, not only when to collect.
- **Phase C and D** — Can overlap: C gives importance and user-guided priority; D adds “proposed focus” and proactive story development. Implement C.1–C.3, then D.1–D.2, then C.4 and D.3–D.4.
- **Phase E** — Can start early (E.1–E.2) once you have a loop, and deepen with E.3–E.4 as you add initiative and learning.

---

## 7. Risks and options

| Risk | Mitigation |
|------|------------|
| **AutomationManager is complex** | Expose a thin “run_phase” API and leave internal phase logic unchanged; coordinator doesn’t need to know dependencies, only “run this phase now.” |
| **Cron / external triggers** | Either fold them into “call coordinator API” or keep them as rare fallbacks with long intervals so the coordinator remains the primary driver. |
| **“Importance” is vague** | Start with a simple formula: watchlist=1.0, automation_enabled + high velocity=0.7, else quality/impact from articles. Refine with learning. |
| **User doesn’t want full automation** | Guardrails (Phase E): user sets “manual only” or “suggestions only” so the app proposes but doesn’t auto-approve; review queue stays the gate. |
| **Event-driven (v6) vs in-process** | This roadmap works **in-process** (coordinator calls governors and executors directly). You can later add Redis/event bus so roles run in separate workers; the same “single loop” logic can emit events instead of direct calls. |

---

## 8. Success criteria (target state)

- **One loop** — Only OrchestratorCoordinator (and its governors) decide what runs; no independent AutomationManager or cron pipeline triggers.
- **What to work on** — Each cycle the loop chooses *what* to do (which phase, which domain/storyline) from a priority queue informed by importance and user guidance.
- **Initiative** — The app proposes “focus on these storylines/topics” and spends resources developing them; proposals are visible and overridable by the user.
- **User guidance** — Watchlist, automation settings, focus areas, and overrides directly shape what the loop does; the app “takes initiative” within those guardrails.

---

*This roadmap is the single reference for moving from current orchestration to an initiative-taking news app with user guidance. For current controller layout see [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md). Historical implementation detail: _archive/ORCHESTRATOR_DEVELOPMENT_PLAN.md and _archive/v6-planning/ORCHESTRATOR_V6_IMPLEMENTATION_PLAN.md.*
