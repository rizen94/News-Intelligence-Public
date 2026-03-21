# Editorial Intelligence Layer

**Purpose:** Define the **editorial intelligence layer** between data pipelines and the final report product. This layer makes editorial decisions (newsworthiness, narrative arc, perspectives, context, impact) so the Today's Report becomes an intelligent editorial product, not just an assembly of parts.

**Related:** [NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md](NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md), [PERSISTENT_EDITORIAL_DOCUMENTS.md](PERSISTENT_EDITORIAL_DOCUMENTS.md) (write-once, refine-forever documents), [DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md](DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md), [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md).

**Conventions:** snake_case for tables, columns, API paths, config keys. Storylines are per-domain (`{schema}.storylines`); editorial tables use `domain_key` + `storyline_id` to reference them.

---

## 1. Missing connections (summary)

| Gap | What it enables |
|-----|------------------|
| **Newsworthiness scoring** | Automatic lead selection (exclusivity, impact, timeliness, surprise). |
| **Narrative arc tracking** | Know where each story is (breaking → developing → analysis → resolution); flag follow-up and deep-dive opportunities. |
| **Reader engagement loop** | Click-through, time on page, follow-up clicks → improve selection and prioritization over time. |
| **Multi-perspective synthesis** | Multiple angles on same story; tension/balance; contrarian viewpoints. |
| **Editorial context engine** | Historical parallels, "Previously on…", context sidebars for current events. |
| **Story impact tracking** | Market/policy reaction to stories; credibility and outcome tracking. |
| **Time-based editorial** | Morning vs afternoon vs evening layout and emphasis (overnight vs analysis vs preview). |
| **Persistent editorial documents** | Canonical storyline/investigation/event documents stored in DB; refined by section (not regenerated). See [PERSISTENT_EDITORIAL_DOCUMENTS.md](PERSISTENT_EDITORIAL_DOCUMENTS.md). |

---

## 2. API surface (editorial layer)

All paths under `/api`; path segments snake_case. Domain where needed: `domain_key` = `politics` | `finance` | `science-tech`.

### 2.1 Editorial intelligence (newsworthiness, angles, leads)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/editorial/score_newsworthiness` | Score storylines (or articles) by exclusivity, impact, timeliness, surprise. Body: `{ "domain": "...", "storyline_ids"?: [...], "article_ids"?: [...] }`. |
| GET | `/api/editorial/story_angles/{domain}/{storyline_id}` | Return detected angles/viewpoints for a storyline. |
| GET | `/api/editorial/recommended_leads` | Return recommended lead storylines for report. Query: `domain`, `limit`, `time_slot` (optional: morning \| afternoon \| evening \| weekend). |

### 2.2 Narrative arc

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/narrative/story_arc/{domain}/{storyline_id}` | Current phase (breaking \| developing \| mature \| resolved), confidence, predicted_next. |
| POST | `/api/narrative/predict_next_phase` | Recompute arc and next-phase prediction for given storyline(s). Body: `{ "domain", "storyline_ids" }`. |

### 2.3 Reader engagement (feedback loop)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/engagement/track_interaction` | Record view/click/time/scroll. Body: `report_id`, `section`, `item_id`, `item_type` (storyline \| event \| context), `interaction_type` (view \| click \| share \| save), `duration_seconds`, `depth_percent`, optional `user_segment`. |
| GET | `/api/engagement/reader_insights` | Aggregated insights for editorial: which sections/items get clicks, completion rates, interest by topic. Query: `since`, `domain`. |
| POST | `/api/engagement/improve_selection` | Trigger recompute of lead/priority weights using engagement (e.g. call before next report build). Body: optional `domain`. |

### 2.4 Multi-perspective

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/perspectives/extract_viewpoints` | Extract viewpoints for a storyline from its articles/sources. Body: `{ "domain", "storyline_id" }`. |
| GET | `/api/perspectives/tension_analysis/{domain}/{storyline_id}` | Conflicting claims, stance summary (supportive \| critical \| neutral), tension points. |

**Existing hook:** `multi_perspective_storyline_service` and expert/perspective analysis can be extended to persist to `story_perspectives` and serve these endpoints.

### 2.5 Editorial context (historical, “Previously on…”)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/editorial/generate_context` | Generate context block for a storyline/event (background, historical parallels). Body: `{ "domain", "storyline_id" or "event_id" }`. |
| GET | `/api/editorial/historical_parallels/{domain}/{storyline_id}` | Historical parallels and primer links. |

### 2.6 Story impact (outcomes, influence)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/impact/track_outcome` | Record outcome linked to story (e.g. market move, policy change). Body: `storyline_id`, `domain`, `outcome_type`, `description`, `source_url`, `observed_at`. |
| GET | `/api/impact/story_influence/{domain}/{storyline_id}` | Influence summary, credibility signals, observed outcomes. |

### 2.7 Time-based editorial (layout / selection)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/editorial/optimal_layout` | Suggested section emphasis by time_slot. Query: `domain`, `time_slot` (morning \| afternoon \| evening \| weekend). |
| POST | `/api/editorial/time_based_selection` | Get lead/investigation/event set optimized for time_slot. Body: `domain`, `time_slot`. |

---

## 3. Database schema (intelligence schema, snake_case)

Storylines live in domain schemas (`politics.storylines`, etc.). Editorial tables live in `intelligence` and reference by `domain_key` + `storyline_id`.

```sql
-- Editorial newsworthiness (per storyline, per domain)
CREATE TABLE IF NOT EXISTS intelligence.editorial_scores (
    id SERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    storyline_id INTEGER NOT NULL,
    newsworthiness FLOAT,
    exclusivity FLOAT,
    impact_potential FLOAT,
    surprise_factor FLOAT,
    timeliness FLOAT,
    scored_at TIMESTAMPTZ DEFAULT NOW(),
    factors JSONB DEFAULT '{}',
    UNIQUE (domain_key, storyline_id)
);
CREATE INDEX IF NOT EXISTS idx_editorial_scores_domain_scored ON intelligence.editorial_scores(domain_key, scored_at DESC);

-- Reader engagement (anonymous or segment-level)
CREATE TABLE IF NOT EXISTS intelligence.reader_engagement (
    id SERIAL PRIMARY KEY,
    report_id UUID,
    domain_key TEXT,
    section TEXT,
    item_type TEXT,  -- storyline, event, context, article
    item_id TEXT,
    interaction_type TEXT,  -- view, click, share, save
    duration_seconds INTEGER,
    depth_percent FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_segment TEXT
);
CREATE INDEX IF NOT EXISTS idx_reader_engagement_report ON intelligence.reader_engagement(report_id, section);
CREATE INDEX IF NOT EXISTS idx_reader_engagement_created ON intelligence.reader_engagement(domain_key, created_at DESC);

-- Narrative arc (lifecycle phase per storyline)
CREATE TABLE IF NOT EXISTS intelligence.story_arcs (
    id SERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    storyline_id INTEGER NOT NULL,
    current_phase TEXT NOT NULL,  -- breaking, developing, mature, resolved
    phase_confidence FLOAT,
    predicted_next TEXT,
    peak_interest_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    arc_metadata JSONB DEFAULT '{}',
    UNIQUE (domain_key, storyline_id)
);
CREATE INDEX IF NOT EXISTS idx_story_arcs_phase ON intelligence.story_arcs(domain_key, current_phase);

-- Multi-perspective (viewpoints per storyline/source)
CREATE TABLE IF NOT EXISTS intelligence.story_perspectives (
    id SERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    storyline_id INTEGER NOT NULL,
    source_id TEXT,  -- feed/source identifier
    source_name TEXT,
    perspective_summary TEXT,
    stance TEXT,  -- supportive, critical, neutral
    confidence FLOAT,
    key_claims JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_story_perspectives_storyline ON intelligence.story_perspectives(domain_key, storyline_id);

-- Story impact / outcomes (optional; link story to real-world outcome)
CREATE TABLE IF NOT EXISTS intelligence.story_outcomes (
    id SERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    storyline_id INTEGER NOT NULL,
    outcome_type TEXT,  -- market_move, policy_change, correction, follow_up
    description TEXT,
    source_url TEXT,
    observed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_story_outcomes_storyline ON intelligence.story_outcomes(domain_key, storyline_id);
```

---

## 4. Enhanced report API structure

The Today's Report payload can be extended to include editorial and narrative fields when the editorial layer is populated.

```python
# GET /api/products/todays_report  (or GET /api/{domain}/report)
# Response shape (extended when editorial layer is available)

{
    "report_id": "...",
    "generated_at": "...",
    "domain": "finance",

    "lead_stories": [
        {
            "storyline_id": 42,
            "headline": "...",
            "briefing": "...",
            "newsworthiness_score": 0.92,
            "why_lead": "Breaking development with market impact",
            "narrative_arc": "developing",
            "perspectives": [
                {"source": "Fed", "stance": "hawkish"},
                {"source": "Markets", "stance": "concerned"}
            ],
            "context_sidebar": "Previous rate decisions...",
            "predicted_next": "Market reaction expected at open"
        }
    ],

    "active_investigations": [
        {
            "investigation_id": "...",
            "title": "...",
            "status": "3 new developments today",
            "impact_tracking": "Policy review initiated",
            "next_milestone": "Committee hearing Tuesday"
        }
    ],

    "reader_guidance": {
        "reading_time": "5 minutes",
        "key_takeaways": ["...", "..."],
        "follow_tomorrow": ["Fed minutes release", "..."]
    },

    "editorial_notes": {
        "coverage_gaps": ["No European perspective on..."],
        "developing_stories": ["Watch for..."],
        "correction_notices": []
    }
}
```

When editorial tables are empty or services are not yet implemented, the report API should still return the basic structure (lead_stories from recency + watchlist, without newsworthiness_score, why_lead, narrative_arc, perspectives, context_sidebar, predicted_next). Frontend can show extended fields when present.

---

## 5. Pipeline integration points

### 5.1 Automation Manager — new phases

Add phases that run **before** report generation (or on a schedule) so the report has fresh editorial data. Align with existing `automation_manager.py` phase style and `PHASE_ESTIMATED_DURATION_SECONDS`.

| Phase | Interval (min) | Purpose |
|-------|----------------|--------|
| `editorial_intelligence` | 5–15 | Score newsworthiness, update story_arcs, extract perspectives (per domain or for active storylines). |
| `editorial_context` | 30 | Generate context blocks / historical parallels for lead storylines. |
| `reader_feedback_processing` | 15 | Aggregate reader_engagement; update weights for recommended_leads / improve_selection. |

Implementation: add to `schedules` (or equivalent) and implement `_execute_editorial_intelligence`, `_execute_editorial_context`, `_execute_reader_feedback_processing` that call the new editorial services (or stubs). Same pattern as `intelligence_products` in DATA_PIPELINE_ENHANCEMENTS_ROADMAP.

### 5.2 Pre-report generation

Before building the Today's Report payload, the report builder can:

1. Call `GET /api/editorial/recommended_leads?domain=...&time_slot=...` for lead storylines (or fall back to recency + watchlist if not implemented).
2. For each lead, optionally fetch `story_arc`, `perspectives`, `context_sidebar`, `predicted_next` from editorial/narrative/perspectives tables or APIs.
3. Call `GET /api/editorial/optimal_layout?domain=...&time_slot=...` to adjust section order/emphasis if implemented.

### 5.3 Processing Governor — new decision factors

Extend `ProcessingGovernor.recommend_next_processing()` (and any config it reads, e.g. `orchestrator_governance.yaml`) so that:

- **Editorial scores:** When choosing which storylines to deep-process (e.g. narrative, synthesis), prefer higher `newsworthiness` or `impact_potential` from `editorial_scores`.
- **Reader engagement:** Prefer storylines that have high click-through or completion in `reader_engagement` (reader_insights) so processing aligns with what users read.
- **Narrative arc:** Prefer “developing” or “breaking” over “resolved” when resources are limited (so the report stays current).

No change to the governor’s signature; add optional reads from editorial_scores, reader_engagement aggregates, and story_arcs when building the candidate list or sorting.

### 5.4 Post-report: engagement tracking

When the frontend serves the report:

1. Send a `report_id` (or generation timestamp) with the response so the client can include it in engagement calls.
2. Frontend calls `POST /api/engagement/track_interaction` on view (section in viewport), click (storyline/event/context link), and optionally on leave (duration, depth_percent).
3. Periodic job or `reader_feedback_processing` phase aggregates this data and updates weights used by `recommended_leads` and governor.

---

## 6. Service layer (conceptual)

| Service | Responsibility | Existing / new |
|---------|----------------|-----------------|
| **EditorialIntelligenceService** | newsworthiness scoring, story angles, recommended_leads | New; can use `quality_score`, `article_count`, event recency from existing DB. |
| **NarrativeArcAnalyzer** | phase detection (breaking/developing/mature/resolved), predict_next_phase | New; consumes timeline + event density + chronology; can extend proactive_detection or timeline_builder. |
| **ReaderEngagementTracker** | track_interaction, reader_insights, improve_selection | New; writes/reads `reader_engagement`; improve_selection updates weights or editorial_scores. |
| **PerspectiveBalancer** | extract_viewpoints, tension_analysis | Extend `multi_perspective_storyline_service`; persist to `story_perspectives`. |
| **EditorialContextEngine** | generate_context, historical_parallels | New; can use RAG, Wikipedia, existing context_centric and chronology. |
| **ImpactAnalyzer** | track_outcome, story_influence | New; writes `story_outcomes`; story_influence aggregates outcomes and optional credibility. |
| **EditorialAutomation** | optimal_layout, time_based_selection | New; rule-based or config-driven by time_slot (morning/afternoon/evening/weekend). |

---

## 7. Implementation priority

| Priority | Item | Rationale |
|----------|------|-----------|
| P1 | Schema migration for `editorial_scores`, `story_arcs`, `reader_engagement`, `story_perspectives` | Unblocks all editorial features. |
| P1 | `GET /api/editorial/recommended_leads` (with fallback to recency + watchlist) | Report can choose leads by newsworthiness once scores exist. |
| P1 | `POST /api/engagement/track_interaction` + `GET /api/engagement/reader_insights` | Enables feedback loop; improve_selection can follow. |
| P2 | EditorialIntelligenceService + `POST /api/editorial/score_newsworthiness` | Populate editorial_scores; run in editorial_intelligence phase. |
| P2 | NarrativeArcAnalyzer + story_arcs + `GET /api/narrative/story_arc/...` | Report and governor can use phase. |
| P2 | Automation phases: editorial_intelligence, reader_feedback_processing | Keeps scores and engagement current. |
| P3 | PerspectiveBalancer + story_perspectives + perspectives/tension APIs | Enriches lead_stories with angles; extends multi_perspective. |
| P3 | EditorialContextEngine + context/historical_parallels APIs | Context sidebars and “Previously on…”. |
| P3 | ImpactAnalyzer + story_outcomes + impact APIs | Outcome tracking and story_influence. |
| P3 | Time-based layout (optimal_layout, time_based_selection) | Same report structure, different emphasis by time of day. |

---

## 8. Critical missing elements (addressed)

| Missing element | Addressed by |
|-----------------|--------------|
| No newsworthiness scoring | `editorial_scores` table; EditorialIntelligenceService; `score_newsworthiness`, `recommended_leads`. |
| No narrative arc tracking | `story_arcs` table; NarrativeArcAnalyzer; `story_arc`, `predict_next_phase`. |
| No reader feedback loop | `reader_engagement` table; ReaderEngagementTracker; `track_interaction`, `reader_insights`, `improve_selection`; governor + report use. |
| No perspective balancing | `story_perspectives` table; PerspectiveBalancer; `extract_viewpoints`, `tension_analysis`; extend multi_perspective. |
| No context generation | EditorialContextEngine; `generate_context`, `historical_parallels`. |
| No impact tracking | `story_outcomes` table; ImpactAnalyzer; `track_outcome`, `story_influence`. |
| No time-based optimization | EditorialAutomation; `optimal_layout`, `time_based_selection`; report builder uses time_slot. |

This layer turns the report from an **assembly of parts** into an **intelligent editorial product** that can prioritize what’s newsworthy, balance perspectives, learn from readers, track impact, provide context, and adapt by time of day—while staying consistent with existing pipelines, governors, and the Today’s Report surface.
