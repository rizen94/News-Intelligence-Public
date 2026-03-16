# Storylines in v6 — Usefulness, Gaps, and Integration

**Purpose:** Answer whether storylines are still useful in v6, why they can feel disconnected or stagnant, and how they fit the journalism/editorial standards.  
**Audience:** Product/editorial decisions.  
**Last updated:** 2026-03-15.

---

## 1. Are storylines still useful in v6? (Yes — they’re part of the plan)

Storylines are **not legacy artifacts**. They are explicitly part of the v6 and editorial strategy:

| Source | Role of storylines |
|--------|---------------------|
| **V6_QUALITY_FIRST_UPGRADE_PLAN** | “Reuse storylines + chronological_events”; event chronicles “link to storylines”; entity dossiers “aggregate article/storyline mentions”; narrative construction “builds on storylines”. |
| **CONTEXT_CENTRIC_UPGRADE_PLAN** | Contexts and entity profiles feed synthesis; storylines remain the **narrative unit** for timeline, briefing, and report. |
| **NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY** | “Lead” = top storylines with briefing; report assembles “storylines list, timeline narrative”; “one narrative per lead story” uses storyline narrative/briefing. |
| **PROJECT_SCOPE_AND_DEVELOPMENT_STATUS** | “Storyline management” is a core domain; pipeline is “article → … → storylines” and “editorial_document” lives on storylines. |

So in v6, storylines are the **main narrative container** for the editorial product: lead selection, report, briefings, and narrative threads all assume storylines exist and are improved over time.

---

## 2. Why they feel disconnected (article/context → storyline)

**Backend:** The path exists. You can:

- Create a storyline (with or without initial articles).
- Add an article to a storyline via `POST /api/{domain}/storylines/{id}/articles/{article_id}`.
- Create a storyline from an article (frontend creates storyline then adds the article).

**Frontend:** The only **cohesive** entry point is:

- **Articles page** → open article in **ArticleReader** → “Add to Storyline” (choose existing or “create new storyline”).

What’s missing or weak:

- **Report / Briefings:** No “Add this to a storyline” or “Start storyline from this” on the report or briefing cards (storylines appear as leads but you can’t turn a highlighted article/event into a storyline in one place).
- **Investigate (events, entities):** No direct “Create storyline from this event” or “Add event’s articles to storyline” in the UI.
- **Discovery:** “Storyline Discovery” finds clusters; creating a storyline from a **single article** is possible via ArticleReader but not obvious from the main nav or from context-centric pages.

So the feeling of “no cohesive way to take an article or context and turn it into a storyline” is mostly **UX/navigation**: the flow exists from Articles + ArticleReader, but it’s not surfaced from Report, Briefings, or Investigate.

---

## 3. Why they feel stagnant (not getting more details over time)

**Backend capability:** Storylines *can* be updated over time:

- **Storyline processing** (AutomationManager): Generates/refreshes `master_summary`, `timeline_summary`, and can trigger editorial document generation.
- **Storyline automation** (StorylineAutomationService): **RAG-based article discovery** for a storyline — finds new articles and can auto-add or put them in a review queue.
- **RAG enhancement:** Can run per storyline to enrich context.
- **Timeline generation:** Builds timeline from storyline articles.

**Why they still feel stagnant:**

1. **Automation is off by default**  
   `automation_enabled` is `false` in the schema (migration 120). So unless someone enables automation per storyline, **no new articles are discovered or added** by the system.

2. **Automation must be configured**  
   Even when enabled, discovery uses `search_keywords`, `search_entities`, `automation_frequency_hours`, and score thresholds. Empty or weak settings → few or no new articles.

3. **Processing is best-effort**  
   Storyline processing and timeline generation run on schedules and only fill in missing/short summaries. If automation never adds articles, the same set of articles is summarized repeatedly — so “more details over time” only appears when **new articles** are added (manual or automated).

4. **No obvious “live” signal in the UI**  
   Users don’t see “this storyline has automation on and last ran at X” or “N new articles suggested” unless they open automation/settings or the suggestion queue.

So: storylines are **capable** of evolving, but they stay static if automation is never enabled or is misconfigured, and the UI doesn’t make that evolution visible.

---

## 4. Artifacts vs journalism standards

- **Not artifacts.** They’re part of the **journalism/editorial standards** we set: DOMAIN_3 (Storyline Management) describes narrative coherence, temporal intelligence, RAG-enhanced analysis, and proactive story detection. NEWSPAPER_EDITORIAL and V6 treat storylines as the unit for “one narrative per lead” and “gets better over time” (watchlist, prioritization, synthesis).
- **Gap:** The **integration** is incomplete: storylines are in the pipeline and in the report/briefing *concept*, but (a) the **article/context → storyline** path is under-exposed outside Articles, and (b) **automation and “evolving over time”** are off by default and not clearly communicated in the UI, so they feel like static artifacts.

---

## 5. Recommendations (short)

1. **Keep storylines** as the main narrative container for v6 and the editorial product.
2. **Surface “article/context → storyline”** in more places: e.g. “Add to storyline” / “Start storyline” from Report and Briefings (and optionally from event/entity cards in Investigate).
3. **Make evolution visible and default-friendly:**  
   - Consider defaulting **automation_enabled** to `true` for new storylines (or a “suggestions only” mode) so discovery runs unless the user turns it off.  
   - In the UI, show per-storyline: automation status, last run, “N articles suggested” or “N new articles added,” and a clear link to automation settings.
4. **Tie storylines to events/context:** Use existing links (event_chronicles → storylines, narrative_threads from storylines) so that in Investigate and Report, “tracked event” or “entity” can open or create a storyline and feel part of one product.

These changes would make storylines clearly **incorporated** into the new journalism standards and reduce the sense that they’re disconnected or stagnant.
