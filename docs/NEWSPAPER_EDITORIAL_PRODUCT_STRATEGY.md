# Newspaper-Style Editorial Product Strategy

**Purpose:** Pull entity extraction, new articles, investigations, events, financial analysis, narratives, and storylines into a **single reader-facing product** that informs users and gets better over time.

**Related:** [EDITORIAL_UPGRADE_BUILD_PLAN.md](EDITORIAL_UPGRADE_BUILD_PLAN.md) (phased implementation checklist), [EDITORIAL_DISPLAY_STRATEGY.md](EDITORIAL_DISPLAY_STRATEGY.md) (how to present: hierarchy, progressive disclosure, time-based layout, trust signals), [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md) (newsworthiness, narrative arc, engagement, perspectives, context, impact), [PERSISTENT_EDITORIAL_DOCUMENTS.md](PERSISTENT_EDITORIAL_DOCUMENTS.md) (living documents: write once, refine forever), [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md), [DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md](DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md), [WEB_UI_FEATURE_COVERAGE.md](WEB_UI_FEATURE_COVERAGE.md).

---

## 1. What we already have (the parts)

| Layer | What it does | Where it lives |
|-------|--------------|----------------|
| **Entity extraction** | People, orgs, places, products from articles | `article_entity_extraction_service`, `entity_canonical`, article_entities |
| **New articles** | RSS → processing → dedupe → domain articles | Collection, `article_service`, storylines linking |
| **Active investigations** | Contexts, tracked events, entity dossiers | `context_centric`, Investigate, event chronicles (planned) |
| **Possible events** | Extracted/deduped events, story continuation | `event_tracking_service`, storylines, chronological_events |
| **Financial analysis** | Research topics, evidence, gold/commodity, tasks | Finance domain, `evidence_collector`, orchestrator |
| **Narratives & storylines** | Timeline → briefing or long-form narrative | `NarrativeSynthesisService`, `DeepContentSynthesisService`, storyline timeline/narrative APIs |
| **Synthesis** | Wikipedia-style storyline articles, RAG context | `content_synthesis` routes, storyline synthesis, RAG |
| **Briefings** | Daily/weekly system + storyline briefs | `DailyBriefingService`, `products.generate_brief`, `get_daily_brief`, Briefings page |

So we have: **ingestion → entities/events → storylines → narratives/synthesis + briefings**. The gap is a **unified editorial product** and a **feedback loop** so the system improves with use.

---

## 2. The final product: one “newspaper” surface

**Goal:** One place a user opens to **read** the day’s (or week’s) intelligence — not to manage feeds or run pipelines, but to be informed.

### 2.1 “Today’s Report” (editorial front)

- **Single reader view** (e.g. route: `/:domain/report` or “Today’s Report” in nav).
- **Sections** (all sourced from existing APIs and services):
  1. **Lead** — Top 1–3 storylines (by recency + watchlist + importance), each with:
     - One-paragraph **briefing** (from `NarrativeSynthesisService.generate_briefing` per storyline).
     - Link to full storyline (detail → timeline → narrative/synthesis).
  2. **Active investigations** — 3–5 contexts or tracked events (from context-centric / Investigate), with one-line status and link to investigate.
  3. **New developments** — Recent events (possible events) with short headlines and link to event/storyline.
  4. **Finance** (finance domain only) — One block: latest research insight or commodity snapshot; link to analysis/commodity.
  5. **Briefing** — Optional “daily brief” block from `POST/GET /api/products/generate_brief` or `daily_brief` (system overview + storyline analysis + dedupe/quality).

All of this is **assembled**, not rebuilt: call existing APIs (storylines list, timeline narrative, products.generate_brief, contexts, tracked events, finance summary) and lay them out in one scrollable, readable page.

### 2.2 Editorial intelligence layer (elevates the report)

Between the data pipelines and the report, an **editorial intelligence layer** can make the report truly editorial rather than just assembled:

| Layer component | What it adds to the report |
|-----------------|----------------------------|
| **Newsworthiness scoring** | Lead selection by exclusivity, impact, timeliness, surprise → `GET /api/editorial/recommended_leads`. |
| **Narrative arc** | Per-story phase (breaking → developing → mature → resolved), predicted next → "why this story now" and follow-up prompts. |
| **Reader engagement** | Track clicks, time on page, depth → `reader_insights` and `improve_selection` so future leads match what readers actually use. |
| **Multi-perspective** | Story angles, tension, balanced viewpoints → perspectives and tension_analysis enrich lead cards. |
| **Editorial context** | Historical parallels, "Previously on…" → context sidebars for each lead. |
| **Story impact** | Outcomes (market move, policy change) linked to stories → credibility and influence in the report. |
| **Time-based editorial** | Morning vs afternoon vs evening emphasis → optimal_layout and time_based_selection. |

When this layer is implemented, the report API can return an **enhanced** payload: each lead story includes `newsworthiness_score`, `why_lead`, `narrative_arc`, `perspectives`, `context_sidebar`, `predicted_next`; sections can include `reader_guidance` and `editorial_notes`. Full API shape, schema, pipeline phases, and governor integration are in [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md).

### 2.3 What "worth reading" means here

- **One narrative per lead story** — Use existing storyline narrative/briefing; no new LLM surface.
- **Clear hierarchy** — Lead → investigations → events → domain-specific (e.g. finance) → full daily brief.
- **Links, not duplication** — Every block links to Storylines, Investigate, Events, Finance so the report is the front door, not the only door.
- **Domain-aware** — Same layout per domain; finance gets the finance block; politics/science-tech get their own storylines and events.

### 2.4 Gets better over time (feedback loop)

| Mechanism | How it improves the product |
|-----------|-----------------------------|
| **Watchlist** | User watches storylines/entities → prioritization and “Lead” section can prefer watchlist items (already in pipeline/governance ideas). |
| **Quality / feedback** | Claim validations, event corrections, source reliability (from DATA_PIPELINE_ENHANCEMENTS_ROADMAP) → better evidence and narrative inputs over time. |
| **Prioritization** | Processing Governor / orchestrator uses watchlist + active_events + importance (V6 plan T2.3) → deeper processing for what the user cares about → better storylines and narratives. |
| **Event chronicles** | Tracked events + event_chronicles (V6 T2.1) → “Active investigations” stays current and narrative-rich. |
| **Synthesis on demand** | When a storyline is opened, synthesis/narrative can be generated or refreshed → report links to ever-better deep dives. |
| **Reader engagement** | Track interactions (view, click, time, depth) → editorial layer’s `reader_insights` and `improve_selection` → lead selection and governor prioritization align with what users read. |
| **Editorial scores & arc** | Newsworthiness and narrative phase (editorial layer) → report leads and “why lead” get smarter; governor can prefer high-impact or developing stories. |

So the **report** stays a thin, readable front; the **backend** (prioritization, quality, chronicles, synthesis, and the **editorial intelligence layer**) makes what appears there more relevant and accurate over time.

---

## 3. How the pieces connect (flow)

```
RSS / finance sources
    → articles, entities, events (existing)
    → storylines, story continuation (existing)
    → contexts, tracked events, investigations (existing)

                    ↓
        [Prioritization: watchlist, importance, resources]
                    ↓
    Deep processing / narrative / synthesis (existing services)
                    ↓
        [Editorial intelligence layer: newsworthiness, arc, perspectives, context, engagement]
                    ↓
        [Editorial product: Today’s Report]
                    ↓
    One page: Lead storylines | Investigations | Events | Finance | Daily brief
                    ↓
    User reads, clicks through to Storylines / Investigate / Events / Finance
                    ↓
    Watchlist, feedback, corrections, engagement tracking (existing + editorial layer)
                    ↓
    Next cycle: prioritization uses feedback → better selection and quality
```

No new pipeline stage is required to **launch** the report; it’s an **assembly layer** on top of existing APIs. Improvements (governance, event chronicles, quality, cross-domain) make the same report better over time.

---

## 4. Concrete next steps (prioritized)

### Phase A — Ship the reader surface (minimal)

1. **Backend: “report” payload API**  
   - New route, e.g. `GET /api/{domain}/report` or `GET /api/products/todays_report?domain=`.  
   - Response: structured JSON with sections (lead_storylines, investigations, recent_events, finance_summary, daily_brief).  
   - Implementation: call existing services (storylines list, timeline + narrative per lead storyline, context_centric contexts/events, products.generate_brief or daily_brief, finance summary if domain is finance). No new LLM; only orchestration.

2. **Frontend: “Today’s Report” page**  
   - New page under `/:domain/report` (or “Report” in nav).  
   - Single scrollable layout: render each section from the API; each block links to the relevant detail (storyline, context, event, analysis).  
   - Apply **editorial display strategy**: dominant lead + up to 2 secondary leads (visual hierarchy), then digest-style supporting items; progressive disclosure (Glance → Scan → Read → Dive). See [EDITORIAL_DISPLAY_STRATEGY.md](EDITORIAL_DISPLAY_STRATEGY.md).  
   - Reuse existing components (cards, typography, links) for consistency.

3. **Navigation**  
   - Add “Report” or “Today’s Report” to the main nav so it’s the default “read” destination alongside Dashboard and Storylines.

### Phase B — Make the report smarter (no new pipelines)

4. **Lead selection**  
   - In the report API, choose “lead” storylines by: recent `updated_at`, then optionally watchlist (if user context available) or quality/importance.  
   - Limit to 2–3; fetch narrative/briefing only for those (to keep latency low).

5. **Wire Briefings page to products API**  
   - Briefings page currently assembles from articles + storylines; add option to pull “daily brief” from `GET /api/products/daily_brief` (or generate_brief) so the same brief appears in Report and in Briefings.

6. **Finance block**  
   - For finance domain, add one card: e.g. “Latest research” (one topic or result) or commodity snapshot; link to Financial Analysis or Commodity dashboard.

### Phase C — Improve over time (existing roadmaps)

7. **Prioritization and governance**  
   - Implement Processing Governor / orchestrator cycle (V6 T2.3) so prioritization uses watchlist + active_events; report’s “lead” and “investigations” naturally reflect what’s being deepened.

8. **Event chronicles**  
   - Add event_chronicles (V6 T2.1); feed “Active investigations” from chronicles so each item has a short status line or development summary.

9. **Quality and feedback**  
   - Add claim_validations, source_reliability (DATA_PIPELINE_ENHANCEMENTS_ROADMAP); use in narrative/synthesis and in “importance” so the report surfaces higher-quality stories first.

10. **Optional: cross-domain and digests**  
    - Cross-domain synthesis and weekly digest (same roadmap) can later power a “Weekly edition” or “Cross-domain” section without changing the core report layout.

### Phase D — Editorial intelligence layer (see EDITORIAL_INTELLIGENCE_LAYER.md)

11. **Schema and engagement**  
    - Add `intelligence.editorial_scores`, `story_arcs`, `reader_engagement`, `story_perspectives`, `story_outcomes`.  
    - Implement `POST /api/engagement/track_interaction` and `GET /api/engagement/reader_insights`; wire report frontend to send engagement, and run `reader_feedback_processing` phase.

12. **Newsworthiness and leads**  
    - Implement EditorialIntelligenceService and `POST /api/editorial/score_newsworthiness`; add `editorial_intelligence` automation phase.  
    - Implement `GET /api/editorial/recommended_leads`; report API uses it for lead selection (with fallback to recency + watchlist).

13. **Narrative arc and perspectives**  
    - Implement NarrativeArcAnalyzer and `story_arcs`; expose `GET /api/narrative/story_arc/{domain}/{storyline_id}`.  
    - Extend multi_perspective to persist to `story_perspectives`; add `extract_viewpoints` and `tension_analysis` APIs.  
    - Report API enriches lead_stories with `narrative_arc`, `perspectives`, `context_sidebar`, `predicted_next` when available.

14. **Governor and time-based**  
    - Processing Governor: factor in editorial_scores, reader_insights, and story_arc phase when recommending next processing.  
    - Optional: `GET /api/editorial/optimal_layout` and time_based_selection for morning/afternoon/evening/weekend emphasis.

---

## 5. Summary

- **Final product:** One newspaper-style **Today’s Report** page that assembles lead storylines (with briefings), active investigations, recent events, optional finance block, and daily brief — from existing APIs at minimum, and from the **editorial intelligence layer** when implemented (newsworthiness, narrative arc, perspectives, context, engagement, impact, time-based layout).
- **Informs the user:** Clear sections, one narrative per lead story, links to Storylines / Investigate / Events / Finance for depth; optional “why lead,” context sidebars, and reader guidance when the editorial layer is in place.
- **Gets better over time:** Watchlist and prioritization, event chronicles, quality/feedback, synthesis improvements—plus **reader engagement** and **editorial scores/arc** from the editorial layer—make the same report more relevant and accurate without changing its structure.

Starting with **Phase A** (report API + Report page + nav) delivers the “final product worth reading” quickly; Phases B and C align with existing roadmaps; **Phase D** (see [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md)) turns it into an intelligent editorial product that knows what’s newsworthy, balances perspectives, learns from readers, tracks impact, and adapts by time of day.
