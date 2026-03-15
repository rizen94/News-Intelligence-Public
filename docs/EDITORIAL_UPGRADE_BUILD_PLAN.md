# Editorial Upgrade Build Plan

**Purpose:** Single executable build plan for the editorial product upgrade: Today's Report, editorial intelligence layer, persistent documents, and display strategy. Phases are ordered so early work delivers value and unblocks later work.

**Related:** [NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md](NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md), [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md), [PERSISTENT_EDITORIAL_DOCUMENTS.md](PERSISTENT_EDITORIAL_DOCUMENTS.md), [EDITORIAL_DISPLAY_STRATEGY.md](EDITORIAL_DISPLAY_STRATEGY.md).

**Conventions:** snake_case (files, functions, DB, API paths). New API under `/api`; domain in path or query where needed.

---

## Overview

| Phase | Name | Goal | Depends on |
|-------|------|------|------------|
| **1** | Report surface | Ship Today's Report (API + page + nav) using existing APIs only | — |
| **2** | Report smarter + docs schema | Better lead selection, briefings/finance wiring; add persistent document schema | Phase 1 |
| **3** | Editorial intelligence foundation | Schema + engagement APIs + recommended_leads; report can use engagement | Phase 1 |
| **4** | Editorial intelligence full | Newsworthiness, narrative arc, automation phases, governor | Phase 2, 3 |
| **5** | Persistent documents + display | Living documents (refine API, services); display strategy (hierarchy, time-based); P3 layer (perspectives, context, impact) | Phase 2, 4 |

---

## Phase 1 — Report surface (ship the reader)

**Goal:** One page and one API that assemble existing data into a readable “Today’s Report.” No new pipelines or schema.

### 1.1 Backend: report API

- [ ] Add route: `GET /api/{domain}/report` or `GET /api/products/todays_report?domain={domain}`.
- [ ] Response shape (minimal):
  - `report_id` (uuid or generation timestamp)
  - `generated_at`, `domain`
  - `lead_storylines`: array of `{ storyline_id, title, briefing, link }` (2–3 items)
  - `active_investigations`: array of `{ id, title, status, link }` (contexts or tracked_events)
  - `recent_events`: array of `{ id, title, date, storyline_id?, link }`
  - `finance_summary`: optional, for domain=finance only
  - `daily_brief`: optional, from existing products API
- [ ] Implementation: orchestration only. Call:
  - Storylines list (limit 3–5 by updated_at), then for top 2–3 fetch timeline + narrative briefing (existing narrative/timeline APIs).
  - Context-centric: get contexts or tracked_events (existing APIs).
  - Events list or story continuation output (existing).
  - Finance: one summary from existing finance routes if domain=finance.
  - Products: `GET /api/products/daily_brief` or generate_brief if available.
- [ ] No new DB tables; no new LLM calls in hot path (briefing can be cached or pre-generated).

### 1.2 Frontend: Report page

- [ ] New page component: e.g. `web/src/pages/Report/Report.tsx` (or TodayReport).
- [ ] Route: `/:domain/report` (or `/report` with domain from context).
- [ ] Single scrollable layout with sections: Lead (dominant + secondary), Investigations, New developments, Finance (if finance), Daily brief.
- [ ] Each block: headline/title, short text (briefing or status), link to detail (storyline, context, event, analysis).
- [ ] Apply display strategy basics: one dominant lead (larger type/weight), up to 2 secondary leads, rest digest-style. See [EDITORIAL_DISPLAY_STRATEGY.md](EDITORIAL_DISPLAY_STRATEGY.md).
- [ ] Reuse MUI + existing cards/typography; loading and error states.

### 1.3 Navigation

- [ ] Add “Report” or “Today’s Report” to main nav (e.g. `AppNav.tsx`). Place for high visibility (e.g. after Dashboard or first).

### Phase 1 exit criteria

- User can open `/:domain/report` and see lead storylines, investigations, events, optional finance and daily brief, with links to detail pages.

---

## Phase 2 — Report smarter + persistent docs schema

**Goal:** Smarter lead selection and wiring to briefings/finance; add DB schema for persistent editorial documents (used in Phase 5).

### 2.1 Lead selection

- [ ] In report API: select lead storylines by `updated_at` DESC, then optionally boost watchlist (if user/watchlist context available) or quality/importance.
- [ ] Cap at 2–3 leads; fetch narrative/briefing only for those to keep latency low.
- [ ] Document logic in code or config (e.g. “lead_selection: recency_first | watchlist_boost”).

### 2.2 Briefings and finance

- [ ] Briefings page: add path to load daily brief from `GET /api/products/daily_brief` (or generate_brief); show same block as on Report when available.
- [ ] Report finance block: for domain=finance, add one card (e.g. latest research topic or commodity snapshot); link to Financial Analysis or Commodity dashboard. Reuse existing finance APIs.

### 2.3 Persistent documents schema

- [ ] Run migration `api/database/migrations/158_persistent_editorial_documents.sql`.
- [ ] Verify: per-domain `storylines` have `editorial_document`, `document_version`, `document_status`, `last_refinement`, `refinement_triggers`; `intelligence.investigation_dossiers` and `document_refinements` exist; `intelligence.tracked_events` has briefing columns.
- [ ] No application code required yet; schema is ready for Phase 5.

### Phase 2 exit criteria

- Report leads are chosen by recency (+ optional watchlist); Briefings can show products API brief; finance domain has a finance card on Report; migration 158 applied.

---

## Phase 3 — Editorial intelligence foundation

**Goal:** Schema and APIs for editorial layer; report can call recommended_leads (with fallback) and send engagement; no heavy new services yet.

### 3.1 Editorial + engagement schema

- [ ] Add migration (or extend existing) for: `intelligence.editorial_scores`, `intelligence.story_arcs`, `intelligence.reader_engagement`, `intelligence.story_perspectives`, `intelligence.story_outcomes` as in [EDITORIAL_INTELLIGENCE_LAYER.md](EDITORIAL_INTELLIGENCE_LAYER.md) §3.
- [ ] Indexes and comments in place.

### 3.2 Engagement APIs

- [ ] `POST /api/engagement/track_interaction`: body `report_id`, `section`, `item_type`, `item_id`, `interaction_type` (view|click|share|save), optional `duration_seconds`, `depth_percent`, `user_segment`. Persist to `reader_engagement`.
- [ ] `GET /api/engagement/reader_insights`: query `since`, `domain`; return aggregates (e.g. clicks per section/item, completion). Read from `reader_engagement`.
- [ ] Optional: `POST /api/engagement/improve_selection`: stub or simple logic that uses reader_insights to adjust weights for next report build.

### 3.3 Recommended leads API

- [ ] `GET /api/editorial/recommended_leads`: query `domain`, `limit`, optional `time_slot`. Returns list of storyline ids (and optional scores).
- [ ] V1: implement with **fallback** only: same as current report logic (recency + optional watchlist). No newsworthiness scoring yet. Response shape compatible with report API (e.g. `{ storylines: [{ id, title, ... }] }`).
- [ ] Report API: optionally call `recommended_leads` instead of inline lead selection; if 404 or empty, fall back to current logic.

### 3.4 Report frontend: engagement

- [ ] On Report page: when user views section or clicks a story/event, call `POST /api/engagement/track_interaction` with report_id (from response), section name, item_id, item_type, interaction_type (view/click).
- [ ] Pass report_id from report API response to client.

### Phase 3 exit criteria

- Editorial + engagement tables exist; engagement and recommended_leads endpoints work; report uses recommended_leads with fallback and sends engagement events.

---

## Phase 4 — Editorial intelligence full

**Goal:** Newsworthiness scoring, narrative arc, automation phases, and governor integration so the report and pipeline get smarter.

### 4.1 Newsworthiness and recommended_leads

- [ ] Implement **EditorialIntelligenceService** (or equivalent): score storylines by exclusivity, impact, timeliness, surprise using existing signals (quality_score, article_count, event recency, etc.). Write to `editorial_scores`.
- [ ] `POST /api/editorial/score_newsworthiness`: body `domain`, optional `storyline_ids`; compute and store scores.
- [ ] Update `GET /api/editorial/recommended_leads` to use `editorial_scores` when present; otherwise keep fallback.

### 4.2 Narrative arc

- [ ] Implement **NarrativeArcAnalyzer**: infer phase (breaking|developing|mature|resolved) from timeline/event density/chronology; optional predicted_next. Write to `story_arcs`.
- [ ] `GET /api/narrative/story_arc/{domain}/{storyline_id}`: return current_phase, phase_confidence, predicted_next.
- [ ] `POST /api/narrative/predict_next_phase`: body `domain`, `storyline_ids`; recompute and store.

### 4.3 Automation phases

- [ ] Add to automation manager (or equivalent): **editorial_intelligence** (e.g. every 5–15 min): call score_newsworthiness and narrative arc update for active storylines.
- [ ] Add **reader_feedback_processing** (e.g. every 15 min): aggregate reader_engagement; optionally update weights for recommended_leads.

### 4.4 Governor integration

- [ ] In ProcessingGovernor (or equivalent): when recommending next processing, optionally factor in editorial_scores (prefer high newsworthiness), reader_insights (prefer high-engagement storylines), and story_arc phase (e.g. prefer developing/breaking over resolved). No change to governor’s public API; internal candidate scoring only.

### Phase 4 exit criteria

- recommended_leads uses newsworthiness when scores exist; narrative arc available per storyline; editorial and feedback phases run on schedule; governor considers editorial and engagement in prioritization.

---

## Phase 5 — Persistent documents + display polish

**Goal:** Living editorial documents (create + refine), documents API, and application of display strategy (time-based, trust signals). Optional P3 editorial features (perspectives, context, impact).

### 5.1 Persistent documents: creation and refinement

- [ ] **DocumentRefinementService** (or equivalent): load/create storyline editorial_document (from `storylines.editorial_document`); on trigger (new_event, entity_update, time_passage, user_feedback), determine sections to update; build refinement prompt; call LLM for those sections only; merge into document; bump version; write to `document_refinements`.
- [ ] First-time creation: generate full document (reuse existing synthesis/narrative services) and map into sectioned structure; save to `editorial_document`.
- [ ] `GET /api/documents/storyline/{domain}/{id}`: return document + metadata (version, status, last_refined, completeness).
- [ ] `POST /api/documents/refine`: body `document_type`, `domain`, `document_id`, `trigger`, `trigger_data`, optional `sections`; call DocumentRefinementService; return updated doc or job id.
- [ ] `GET /api/documents/history/{document_type}/{domain?}/{id}`: return versions and refinement_log from `document_refinements`.

### 5.2 Report uses persistent documents

- [ ] For lead storylines, report API or frontend: when available, use **lede** (and optionally **outlook**) from `storylines.editorial_document` instead of calling narrative generation on each request. Fallback to existing briefing if no document.

### 5.3 Display strategy application

- [ ] **Time-based layout:** Report or API accepts optional `time_slot` (morning|afternoon|evening|weekend); layout or section order/emphasis varies (e.g. morning = overnight prominent). Implement via `GET /api/editorial/optimal_layout` stub or client-side rules.
- [ ] **Trust signals:** On Report and storyline cards: show source attribution (multi-source, freshness), “Why this is the lead” when available, correction/update flag. Use fields from editorial layer and persistent docs.
- [ ] **Progressive disclosure:** Glance (headline + phase + one fact) → Scan (bullets, perspectives) → Read (full doc) → Dive (investigate/sources). Ensure Report and storyline detail support expand-in-place or clear navigation to Read/Dive.

### 5.4 Optional: perspectives, context, impact (P3)

- [ ] **Perspectives:** Extend multi_perspective to persist to `story_perspectives`; add `POST /api/perspectives/extract_viewpoints`, `GET /api/perspectives/tension_analysis/{domain}/{storyline_id}`. Report enriches lead_stories with perspectives when available.
- [ ] **Context:** EditorialContextEngine: `POST /api/editorial/generate_context`, `GET /api/editorial/historical_parallels`; report shows context sidebar when available.
- [ ] **Impact:** ImpactAnalyzer + `story_outcomes`; `POST /api/impact/track_outcome`, `GET /api/impact/story_influence`; report shows “This led to…” when available.

### Phase 5 exit criteria

- Storyline (and optionally investigation/event) documents can be created and refined via API; report can surface lede/outlook from stored docs; display strategy applied (time-based, trust, progressive disclosure); optional P3 features wired if scoped.

---

## Dependency summary

```
Phase 1 (Report surface)     →  Phase 2 (Smarter + schema)
        ↓                              ↓
Phase 3 (Editorial foundation)  →  Phase 4 (Editorial full)
        ↓                              ↓
        └────────── Phase 5 (Documents + display) ──────────┘
```

## Reference: doc → build plan

| Strategy doc | Build plan phases |
|--------------|-------------------|
| NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY | Phases 1–2 (report, smarter), 4 (editorial layer), 5 (display) |
| EDITORIAL_INTELLIGENCE_LAYER | Phases 3–4 (schema, engagement, newsworthiness, arc, automation, governor), 5 (P3) |
| PERSISTENT_EDITORIAL_DOCUMENTS | Phase 2 (schema), Phase 5 (services, API, report integration) |
| EDITORIAL_DISPLAY_STRATEGY | Phase 1 (hierarchy), Phase 5 (time-based, trust, progressive disclosure) |

---

## Getting started

1. **Start with Phase 1.** Implement report API and Report page in parallel if helpful; add nav when page exists.
2. **Track progress:** Check off items in this doc or copy into a task tracker; update exit criteria when each phase is done.
3. **Adjust order:** If briefings/finance are higher priority, do 2.1–2.2 before 2.3; if engagement is critical early, do Phase 3.1–3.2 right after Phase 1.
4. **Tests:** Add API tests for new routes (report, engagement, recommended_leads, documents); optional E2E for Report page.
