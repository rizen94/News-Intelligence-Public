# Briefing Strategy and Processes — For Review

This document summarizes **what** the daily briefing is meant to do, **how** it is generated, **where** it can fall short, and **options** to improve it. Use it for design review (e.g. Claude or a human) and to decide next steps.

---

## 1. Intent and Strategy

- **Product goal:** A short, scannable “AI summary of today’s developments” per domain (politics, finance, science-tech) that answers “what happened?” and “why should I care?” without requiring deep reading.
- **Design reference:** `docs/EDITORIAL_DISPLAY_STRATEGY.md` — hierarchy of attention (dominant lead → secondary → digest), progressive disclosure (glance → scan → read → dive), time-of-day framing (morning / midday / evening / weekend), and trust signals (sources, freshness).
- **Current scope:** The **generated briefing** is the “Read” layer: one narrative block produced when the user clicks “Generate an AI summary of today’s developments” on the Briefings page. The **page layout** (lead card, secondary cards, digest, time-of-day line) is separate and uses live articles/storylines/events; the **generated content** is the text returned from the briefing API.

---

## 2. End-to-End Flow

```
User (Briefings UI, per domain)
  → clicks "Generate briefing"
  → POST /api/{domain}/intelligence/briefings/daily  (e.g. /api/politics/...)
  → products.post_domain_daily_briefing(domain, date?)
  → DailyBriefingService.generate_daily_briefing(briefing_date, domain=domain, days_window=3)
  → Sections built from DB (domain schema, last 3 days)
  → _brief_to_content(brief)  → single string "content"
  → Response: { success, data: { content, article_count, sections, statistics } }
  → UI displays data.content in "Full briefing synthesis" and article_count in chips
```

- **Domain:** Path parameter (e.g. `politics`). The service resolves `schema_name` from the `domains` table and queries **that schema’s** `articles` table (e.g. `politics.articles`). If domain is missing or schema not found, the brief can fall back to unqualified `articles` (often empty).
- **Time window:** Last **3 days** of data (`BRIEFING_DAYS_WINDOW = 3`). All section queries use `created_at >= start_date` (and optionally `updated_at`). No dependency on API restart.

---

## 3. Data and Sections (Backend)

The briefing is a structured object with **sections**; the HTTP response also sends a **narrative string** `content` built from those sections.

### 3.1 Section sources

| Section | Source | What it uses | Possible failure / thin output |
|--------|--------|----------------|--------------------------------|
| **system_overview** | `DailyBriefingService._generate_system_overview` | `{schema}.articles`: count where `created_at >= start_date`, count where `updated_at >= start_date`, total rows, distinct sources in window | No rows in that schema in last 3 days → 0 new, 0 updated. Wrong or missing schema → 0. |
| **content_analysis** | `_generate_content_analysis` | Same table: category distribution, top sources, total articles in window (by category) | Same as above; also “0 categories” if no articles. |
| **storyline_analysis** | `StorylineTracker.generate_topic_cloud(days=3, schema=schema)` | Same table, but **filters**: `ml_data IS NOT NULL` and `quality_score >= 0.3`. Produces `topic_cloud`, `breaking_topics`, `daily_summary`, `article_count`. | No ML-processed articles or all low quality → 0 articles in topic cloud, generic “No significant articles…” and template daily_summary. |
| **deduplication_report** | `AdvancedDeduplicationService.get_deduplication_stats()` | Global dedup stats (not per-domain). | Can return error or empty if service/DB not configured. |
| **quality_metrics** | `_generate_quality_metrics` | Same articles table: quality distribution (high/medium/low), category-level avg quality (categories with ≥3 articles). | No articles → empty distribution, overall_quality_score 0.0. |
| **key_developments** | `_extract_key_developments(start_date, articles_table, schema)` | **Editorial layer:** top 10 headlines by quality; top 8 storylines with `editorial_document` ledes when populated; event briefings from `intelligence.tracked_events` where `editorial_briefing` is present. Returns `top_headlines`, `top_storylines`, `editorial_ledes`, `event_briefings`, `has_content`. Only when domain/schema set. | Schema missing or no rows → has_content false; no editorial_document → no ledes (falls back to titles). |
| **recommendations** | `_generate_recommendations(briefing)` | Derived from other sections: e.g. “low volume” if today_new_articles < 10, “no breaking” if breaking_topics empty, quality suggestions. | All recommendations conditional on having data; with zeros, only a few generic lines may appear. |

### 3.2 Storyline “daily summary” (the only prose today)

- **Location:** `api/modules/ml/storyline_tracker.py` → `_generate_daily_summary(articles, breaking_topics)`.
- **Logic:** Pure template, **no LLM**:
  - “Daily News Summary: {N} articles processed with average quality score of {X}. Top category: {Y}. {N} breaking stories identified / No breaking stories identified. Review topic cloud for detailed analysis…”
- So the only “narrative” in the pipeline is this fixed sentence. It does not summarize headlines, themes, or developments.

### 3.3 Turning sections into the UI string "content"

- **Location:** `api/domains/intelligence_hub/routes/products.py` -> `_brief_to_content(brief)`.
- **Logic:** **Editorial-first ordering.** If `key_developments` has content:
  1. **Editorial ledes** from storylines with populated `editorial_document` -> "Top stories: {lede1} {lede2}"
  2. **Headlines** (fallback when no editorial ledes exist) -> "Key developments: {title1} {title2}"
  3. **Storyline titles** -> "Leading storylines: {title}; {title}"
  4. **Event briefings** from tracked events with `editorial_briefing` -> "Events: {headline}: {excerpt}"
  5. Then supporting metrics: system overview, content analysis, storyline daily_summary, quality, recommendations.
- **Optional LLM lead:** When `use_llm_lead: true` (default) and key_developments has content, `post_domain_daily_briefing` calls `llm_service.generate_briefing_lead(context, domain)` and prepends "Lead: ..." to content. The LLM context now includes editorial ledes, headlines, storyline titles, and event briefings. If the LLM fails, content is returned without the lead.

---

## 4. Why the Briefing Can Still Feel Thin

1. **LLM lead is optional; editorial documents may be empty**  
   The briefing now has an optional LLM-generated lead paragraph and can draw from `editorial_document` ledes, but both depend on upstream pipeline phases (`editorial_document_generation`, `editorial_briefing_generation`) having run. Until those populate the JSONB fields, the briefing falls back to headline titles and counts.

2. **Strict filters for storyline/topic cloud**  
   Topic cloud and daily_summary only see articles with `ml_data IS NOT NULL` and `quality_score >= 0.3`. If ML processing is behind or quality scores are low, the storyline section is empty or “No significant articles…”.

3. **Domain and schema**  
   If the request domain does not match a schema, or the schema’s `articles` table is empty for the last 3 days, every section returns zeros or empty lists.

4. **Breaking topics are narrow**  
   “Breaking” = articles with `published_at` in the **last 6 hours** and `quality_score >= 0.5`. So only very recent, higher-quality items count; otherwise “No breaking stories identified.”

5. **Recommendations are reactive**  
   They react to counts (e.g. “low volume”, “no breaking”). With little data, they add little value.

---

## 5. Files and Entry Points (Quick Reference)

| Role | Path |
|------|------|
| Editorial strategy (design) | `docs/EDITORIAL_DISPLAY_STRATEGY.md` |
| Briefings UI (Generate button, display) | `web/src/pages/Briefings/Briefings.tsx` |
| Frontend API call | `web/src/services/api/intelligence.ts` → `generateDailyBriefing(date?, domain)` → POST ` /api/{domain}/intelligence/briefings/daily` |
| API route (domain-scoped) | `api/domains/intelligence_hub/routes/products.py` → `post_domain_daily_briefing(domain, date)` |
| Section → narrative string | Same file → `_brief_to_content(brief)` |
| Briefing engine | `api/modules/ml/daily_briefing_service.py` → `DailyBriefingService.generate_daily_briefing(..., domain=..., days_window=3)` |
| Topic cloud + daily_summary | `api/modules/ml/storyline_tracker.py` → `generate_topic_cloud(days, schema)`, `_generate_daily_summary(...)` |
| Deduplication | `api/modules/deduplication/advanced_deduplication_service.py` (via `get_deduplication_service`) |

---

## 6. Options for Richer Briefings (For Review)

- **A. Add an LLM narrative pass**  
  After building `brief["sections"]`, call the project’s LLM service with a prompt that takes:
  - system_overview, content_analysis, storyline_analysis (topic_cloud, breaking_topics, daily_summary), and optionally top headlines or storyline titles from the same domain.
  - Ask for 2–4 short paragraphs: “what happened,” “what matters,” “what to watch,” in the style of EDITORIAL_DISPLAY_STRATEGY (glance/scan).  
  Store result in `brief["sections"]["narrative"]` or similar and make `_brief_to_content` use that as the main `content` (with fallback to current count-based + template summary if LLM fails).

- **B. Enrich daily_summary with real headlines/themes**  
  Keep `_generate_daily_summary` but feed it top titles and categories (and optionally breaking_topics) and build a slightly richer template, or use a small LLM call only for this paragraph so “Summary: …” in the UI is more informative.

- **C. Relax or broaden filters**  
  Consider including articles without `ml_data` (or with a fallback) for topic cloud when ML-processed volume is low; or broaden “breaking” to a 24h window so the “breaking” line and recommendations are less empty.

- **D. Expose more structure in the UI**  
  Return and render `sections` (e.g. breaking_topics, top_topics, top_sources) as structured blocks or bullets instead of hiding them inside a single string, so the brief feels denser even before adding LLM.

- **E. Align with Today’s Report**  
  The “Today’s Report” view already uses articles, storylines, and tracked events for hierarchy and time-of-day. The **generated briefing** could be one block inside that view (e.g. “Full briefing synthesis” pulled from this same API) so strategy and processes stay aligned (see `docs/EDITORIAL_DISPLAY_STRATEGY.md` “Where This Applies”).

---

## 7. Checklist for Review

- [ ] Confirm intent: is the main gap “no LLM narrative” or “too few articles / wrong schema / filters too strict”?
- [ ] Confirm data: for the domain you care about, does `{schema}.articles` have rows in the last 3 days? Do many have `ml_data` and `quality_score >= 0.3`?
- [ ] Choose direction: A (LLM pass), B (richer template/LLM for daily_summary), C (relax filters), D (structured UI), E (integrate with Report), or a combination.
- [ ] If adding LLM: which service and prompt shape (see `api/shared/services/llm_service.py`, existing patterns in content_analysis or intelligence_hub)?

This document is the single place to understand briefing strategy and processes for review and iteration.
