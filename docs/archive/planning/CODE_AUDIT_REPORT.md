# Code Audit Report: Architectural Constraint Violations

**Date:** 2026-03-06  
**Scope:** Full codebase audit against core architectural principles  
**Files Audited:** 15 primary files + dependency analysis  
**Violations Found:** 34 (10 Critical, 12 High, 12 Medium)  
**Status:** FULLY REMEDIATED — All 34 violations (10 Critical, 12 High, 12 Medium) fixed 2026-03-06

---

## Architectural Principles Under Test

1. **Content is King** — Article body text, quotes, and facts must be preserved and used, not just title/metadata/counts.
2. **Intelligence Accumulates** — Each pipeline step enriches data, building on prior phases.
3. **Narratives Over Metrics** — User-facing outputs are editorial narratives, not statistics dashboards.
4. **Editorial Documents are Primary** — `storylines.editorial_document` and `tracked_events.editorial_briefing` JSONB fields are the core product.

---

## Component Scorecard

| Component | Rating | Summary |
|-----------|--------|---------|
| RSS Ingestion | :warning: PARTIAL | Captures `summary`/`description` but ignores `content:encoded` (full body). Summary column always NULL on insert. |
| ML Pipeline | :white_check_mark: COMPLIANT | Best-behaved file. Reads content, sends to LLM, stores enriched `ml_data`. Minor: `get_processing_status` returns counts. |
| Storyline Management | :x: VIOLATING | `editorial_document` not selected in list endpoint, not populated by RAG analysis. Articles shown without content. Suggestions have no semantic relevance. |
| Event Tracking | :x: VIOLATING | Creates events with NULL `editorial_briefing`. Chronicles have empty `analysis` and `predictions`. Content truncated to 200 chars for LLM. |
| Briefing Generation | :x: VIOLATING | Entire briefing built from `COUNT(*)` and `AVG()`. No article content accessed. ML enrichments ignored. Weekly summary is summed counts. |
| Intelligence APIs | :x: VIOLATING | Dashboard is three `COUNT(*)` queries. High-impact storylines return `title + count`. Big picture analysis is pure metrics. |
| Entity Profile Builder | :white_check_mark: COMPLIANT | Reads content, passes to LLM, populates structured JSONB. Minor: 500-char truncation per context. |
| Editorial Document Service | :warning: PARTIAL | Exists and populates `editorial_document`, but queries only `title + summary` (not `content`), ignores all accumulated intelligence. |
| Automation Manager | :warning: PARTIAL | Phase dependencies properly sequenced, but phases don't consume enrichments from prior phases — each starts from scratch. |

---

## Database Field Usage

| Field | Status | Detail |
|-------|--------|--------|
| `storylines.editorial_document` | SOMETIMES POPULATED | Written by `editorial_document_service.py` but from impoverished context (title+summary only). Not selected in list endpoints. Not populated by RAG analysis. |
| `tracked_events.editorial_briefing` | EMPTY | `event_tracking_service.py` creates events without populating this field. `editorial_document_service.generate_event_editorial()` exists but has same content limitations. |
| `entity_profiles.profile_data` | POPULATED | `entity_profile_builder_service.py` properly reads content and writes structured profiles. Best implementation in the system. |
| `articles.content` | PRESERVED BUT RARELY RE-ACCESSED | Stored at ingestion (RSS summary/description, not full body). Read by `ml_pipeline.py` for enrichment. Ignored by briefings, storyline tracker, event tracking, and most API endpoints. |
| `articles.ml_data` | POPULATED BUT NEVER DOWNSTREAM | ML pipeline writes summaries, key points, sentiment, arguments. No downstream service ever reads `ml_data`. |
| `articles.summary` | ALWAYS NULL AT INGESTION | RSS collector inserts `summary=NULL`. ML pipeline may populate it later, but many articles remain NULL. |

---

## CRITICAL Violations (10)

### C1. Daily Briefing Service — Entire file generates stats, not narratives

**FILE:** `api/modules/ml/daily_briefing_service.py`  
**FUNCTIONS:** `_generate_system_overview`, `_generate_content_analysis`, `_generate_quality_metrics`, `_generate_weekly_summary`  
**TYPE:** METADATA ONLY  

The daily briefing — the system's primary intelligence product — is composed entirely of `COUNT(*)`, `AVG()`, and template strings. Zero article content is ever read. Zero LLM calls for narrative generation.

Output examples:
- "System overview: 147 new articles, 12 updated"
- "Content: 5 categories, 42 articles analyzed"
- "Quality: 0.68 avg score"
- "Weekly: 734 total articles, 23 breaking, 104.9 avg/day"

**Impact:** Users receive a statistics dashboard labeled as an "intelligence briefing."

---

### C2. Storyline Tracker — Content fetched from DB but never read

**FILE:** `api/modules/ml/storyline_tracker.py`  
**FUNCTION:** `_analyze_topics` (line ~219)  
**TYPE:** CONTENT LOSS  

SQL fetches `content` (column index 2) from articles, transferring full text over the wire. Every function that processes results ignores index 2 and does naive word counting on `title + summary` instead.

```python
words = (title + " " + summary).lower().split()  # content (index 2) never accessed
```

**Impact:** Topic analysis is word-frequency counting on titles. ML-generated `ml_data` (key points, arguments) also fetched but ignored.

---

### C3. Storyline Tracker — Daily summary is a stats template

**FILE:** `api/modules/ml/storyline_tracker.py`  
**FUNCTION:** `_generate_daily_summary` (line ~291)  
**TYPE:** METADATA ONLY  

```python
summary = f"Daily News Summary: {total_articles} articles processed with average quality score of {avg_quality:.2f}. "
summary += f"Top category: {top_category}. "
```

**Impact:** The only "narrative" in the pipeline is this template sentence. No LLM. No synthesis.

---

### C4. Storyline Tracker — Comprehensive dossier uses titles + quality scores

**FILE:** `api/modules/ml/storyline_tracker.py`  
**FUNCTION:** `_generate_comprehensive_dossier` (line ~330)  
**TYPE:** CONTENT LOSS  

The "comprehensive dossier" timeline lists: title, source, quality score. Content (available in the query) is ignored. Executive summary is just the best article's summary field.

**Impact:** Story dossiers are metadata chronologies, not intelligence products.

---

### C5. Event Tracking — Events created with NULL editorial_briefing

**FILE:** `api/services/event_tracking_service.py`  
**FUNCTION:** `discover_events_from_contexts` (line ~201)  
**TYPE:** EMPTY EDITORIAL  

```python
INSERT INTO intelligence.tracked_events
(event_type, event_name, start_date, geographic_scope,
 key_participant_entity_ids, milestones, domain_keys)
VALUES (%s, %s, %s, %s, '[]', '[]', %s)
```

`editorial_briefing` and `editorial_briefing_json` are never set. No code path in this service populates them.

**Impact:** Core event editorial product is always empty.

---

### C6. Event Tracking — Chronicles have empty analysis, never build on prior

**FILE:** `api/services/event_tracking_service.py`  
**FUNCTION:** `_update_existing_event_chronicles` (line ~309)  
**TYPE:** INTELLIGENCE LOST  

```python
INSERT INTO intelligence.event_chronicles
(event_id, update_date, developments, analysis, predictions, momentum_score)
VALUES (%s, CURRENT_DATE, %s, '{}', '[]', %s)
```

`analysis` is `'{}'` (empty), `predictions` is `'[]'` (empty). Previous chronicle analysis is never read or extended.

**Impact:** Event chronicles never accumulate intelligence. Each update starts from scratch.

---

### C7. Editorial Document Service — Queries only title+summary, ignores content and intelligence

**FILE:** `api/services/editorial_document_service.py`  
**FUNCTION:** `generate_storyline_editorial` (line ~96)  
**TYPE:** CONTENT LOSS + INTELLIGENCE LOST  

```python
SELECT a.id, a.title, a.summary, a.sentiment_label, a.source_domain, a.published_at
FROM {schema}.storyline_articles sa
JOIN {schema}.articles a ON a.id = sa.article_id
```

The editorial document generator — the core architectural product — never reads `a.content`, `a.entities`, `a.ml_data`, entity profiles, claims, events, or any intelligence-layer data. Summaries are truncated to 200 chars. The LLM builds editorial output from impoverished context.

**Impact:** The system's most important output is generated from the least data.

---

### C8. Intelligence Dashboard — Three COUNT(*) queries

**FILE:** `api/domains/intelligence_hub/routes/intelligence_analysis.py`  
**FUNCTION:** `get_intelligence_dashboard` (line ~469)  
**TYPE:** BYPASSING EDITORIAL + METADATA ONLY  

```python
SELECT
    (SELECT COUNT(*) FROM {schema}.storylines WHERE status = 'active') as active_storylines,
    (SELECT COUNT(*) FROM {schema}.articles WHERE created_at > NOW() - INTERVAL '24 hours') as recent_articles,
    (SELECT COUNT(DISTINCT source_name) FROM {schema}.articles WHERE ...) as active_sources
```

**Impact:** The "Intelligence Dashboard" — flagship intelligence hub feature — shows three numbers and a health status.

---

### C9. High-Impact Storylines — Title + count, no editorial content

**FILE:** `api/domains/intelligence_hub/routes/intelligence_analysis.py`  
**FUNCTION:** `get_high_impact_storylines` (line ~388)  
**TYPE:** BYPASSING EDITORIAL  

```python
SELECT id, title, article_count
FROM {schema}.storylines
WHERE status = 'active' AND article_count >= 2
```

Does not select `editorial_document`, `description`, or `analysis_summary`. Output: "Trade War Escalation — 8 articles — impact: 0.87."

**Impact:** Most important storylines presented without any editorial content.

---

### C10. Automation Manager — Phases run in order but don't enrich each other

**FILE:** `api/services/automation_manager.py`  
**TYPE:** INTELLIGENCE LOST (systemic)  

The phase dependency chain is properly sequenced at the scheduling level, but the actual data flow is broken. Each `_execute_*` method fetches its own data from scratch:

- `editorial_document_generation` depends on `storyline_processing` but doesn't use `master_summary`
- `digest_generation` depends on `editorial_document_generation` but never queries `editorial_document`
- `storyline_processing` depends on `ml_processing` but doesn't use ML/sentiment results
- `rag_enhancement` depends on `basic_summary_generation` but doesn't consume the basic summary

**Impact:** The intelligence cascade exists as a scheduling concept but not as a data flow. Each phase is a silo.

---

## HIGH Violations (12)

| # | File | Function | Type | Impact |
|---|------|----------|------|--------|
| H1 | `daily_briefing_service.py` | `_extract_key_developments` | CONTENT LOSS | Headlines section fetches only `title, source` — no content, summary, or ML data |
| H2 | `event_tracking_service.py` | `discover_events_from_contexts` | CONTENT LOSS | Article content truncated to 200 chars for LLM event clustering |
| H3 | `rss_collector.py` | article insert loop | CONTENT LOSS | Ignores `entry.content` (full body from `content:encoded`); only reads `summary`/`description`. Summary column always NULL. |
| H4 | `products.py` | `_build_llm_lead_prompt` | CONTENT LOSS | LLM editorial lead receives only headline titles — no article text, quotes, or facts |
| H5 | `products.py` | `get_daily_brief` | METADATA ONLY | Returns raw `sections` + `statistics` dicts without narrative transformation |
| H6 | `storyline_management.py` | `get_domain_storyline` | CONTENT LOSS | Article sub-query fetches `title, url, source, date, summary` — no `content` field |
| H7 | `storyline_management.py` | `get_domain_storyline_suggestions` | CONTENT LOSS | Suggestions are naive "most recent" with no semantic relevance and no content preview |
| H8 | `storyline_management.py` | `process_storyline_rag_analysis` | BYPASSING EDITORIAL | RAG analysis writes to `analysis_summary` (legacy), not `editorial_document` (core product) |
| H9 | `content_analysis.py` | `get_topic_summary` | CONTENT LOSS | LLM topic summary built from `title + summary` — not `content` |
| H10 | `automation_manager.py` | `_execute_entity_extraction` | CONTENT LOSS | Entity context (quotes, actions, relationships) discarded; only entity list stored |
| H11 | `automation_manager.py` | `_execute_storyline_processing` | INTELLIGENCE LOST | Generates `master_summary` from scratch, ignoring sentiment/entity/quality enrichments |
| H12 | `automation_manager.py` | `_execute_basic_summary_generation` | BYPASSING EDITORIAL | Populates `master_summary` without contributing to `editorial_document` |

---

## MEDIUM Violations (12)

| # | File | Function | Type | Impact |
|---|------|----------|------|--------|
| M1 | `ml_pipeline.py` | `get_processing_status` | METADATA ONLY | Processing status is pure row counts |
| M2 | `storyline_tracker.py` | `_summarize_evolution` | METADATA ONLY | "Evolution summary" is "15 articles over 7 days, 5 sources" |
| M3 | `entity_profile_builder_service.py` | `build_profile_sections` | CONTENT LOSS | Content truncated to 500 chars per context (could be 1000-1500) |
| M4 | `products.py` | `get_alert_digest` | METADATA ONLY | Alert digest is a JSON array + count, no editorial summary |
| M5 | `storyline_management.py` | `get_domain_storyline_timeline` | METADATA ONLY | Timeline has no editorial narrative connecting events |
| M6 | `storyline_management.py` | `get_domain_available_articles_for_storyline` | CONTENT LOSS | No content preview for article selection |
| M7 | `content_analysis.py` | `get_big_picture_analysis` | METADATA ONLY | "Big picture" is "42 articles, 8 topics, 5 sources" |
| M8 | `content_analysis.py` | `get_trending_topics` | METADATA ONLY | Trending topics have `description: None` (hardcoded) |
| M9 | `content_analysis.py` | `get_topics` | METADATA ONLY | Topic descriptions hardcoded NULL in SQL |
| M10 | `content_analysis.py` | `get_articles` / `get_topic_articles` | CONTENT LOSS | Content truncated to 500 chars |
| M11 | `content_analysis.py` | `get_article_analysis` | METADATA ONLY | Analysis returns scores/labels, no narrative explanation |
| M12 | `intelligence_analysis.py` | `batch_quality_assessment` | METADATA ONLY | Assessment stripped to `issues_count` (textual issues discarded) |

---

## Missing Implementation Report

| Component | Status | Notes |
|-----------|--------|-------|
| Article content intelligence extraction | :warning: Partial | `ml_pipeline.py` extracts to `ml_data`, but no downstream service reads it |
| Editorial document generation pipeline | :warning: Partial | `editorial_document_service.py` exists but uses impoverished context |
| Event chronicle building from articles | :x: Missing | Chronicles created with empty `analysis` and `predictions` |
| Entity profile narrative construction | :white_check_mark: Exists | `entity_profile_builder_service.py` is well-implemented |
| Content-based briefing generation | :x: Missing | Briefings are 100% statistics-based |
| Storyline narrative synthesis | :warning: Partial | `editorial_document` populated from title+summary; RAG analysis goes to wrong field |
| Content synthesis service | :x: Missing | No service aggregates intelligence from all phases into editorial context |
| RAG service | :x: Missing | No centralized RAG service |
| Newsroom orchestrator | :x: Missing | `api/orchestration/__init__.py` is a v0.1.0 stub |

---

## Systemic Patterns

### 1. The Content Black Hole

Article content flows: RSS feed -> `rss_collector` (captures excerpt, not full body) -> DB -> `ml_pipeline` (enriches with LLM, stores in `ml_data`) -> **never read again**. The daily briefing, storyline tracker, dossier generator, editorial document service, and event tracking all query the same articles table but look only at titles, counts, and scores.

### 2. The Editorial JSONB Ghost Fields

`storylines.editorial_document` and `tracked_events.editorial_briefing` are declared as the system's core products, but:
- `editorial_document` is populated from impoverished context (title + 200-char summary)
- `editorial_briefing` is never populated by the event tracking service
- RAG analysis (the richest analytical output) writes to `analysis_summary`, not `editorial_document`
- Neither field is selected in list endpoints
- The intelligence dashboard doesn't query either field

### 3. LLM Investment Wasted

`ml_pipeline.py` makes 4 LLM calls per article (summary, key points, sentiment, arguments) and stores results in `ml_data`. No downstream service ever reads `ml_data`. The storyline tracker does naive word counting on titles instead. The editorial document service queries title+summary, not ml_data. The cost is incurred but the intelligence never reaches users.

### 4. "Analysis" Means "COUNT(*)"

Every function with "analysis", "summary", "assessment", or "overview" in its name produces counts and averages: `get_big_picture_analysis`, `_generate_system_overview`, `_generate_content_analysis`, `get_intelligence_dashboard`, `_generate_weekly_summary`. The system generates the **shape** of intelligence (sections, dossiers, briefings) but fills them with statistics.

### 5. Parallel Silos Instead of Cascade

The automation manager sequences 30+ phases in a dependency graph. But each phase independently queries the database from scratch. Phase N's enrichments are stored in the database but Phase N+1 doesn't read them. The "intelligence cascade" (articles -> facts -> events -> storylines -> narratives -> briefings) exists as an architectural concept but not as a data flow.

---

## Priority Recommendations

### IMMEDIATE FIXES (Biggest impact, smallest changes)

1. **Fix `editorial_document_service.py` to query `content` + `ml_data`** — The editorial document generator should SELECT `a.content, a.ml_data, a.entities` and feed full article text + accumulated intelligence to the LLM. This single change transforms the core product from title-based to content-based.

2. **Fix `event_tracking_service.py` to populate `editorial_briefing`** — After creating events, generate an initial editorial briefing from the clustered articles' content. Currently events are created as metadata stubs.

3. **Fix `rss_collector.py` to capture `entry.content`** — Check for `entry.content[0].value` (feedparser's `content:encoded` mapping) before falling back to `summary`/`description`. Many major feeds provide full articles this way.

4. **Fix RAG analysis to write to `editorial_document`** — In `storyline_management.py`, `process_storyline_rag_analysis` should update `editorial_document` (the core product field), not just `analysis_summary` (a legacy field).

### HIGH PRIORITY (User-facing features)

5. **Add `editorial_document` excerpt to storyline list endpoint** — Select `editorial_document->'lede'` in `get_domain_storylines` so storyline cards show editorial content instead of just title+count.

6. **Fix `_build_llm_lead_prompt` to include article content** — The LLM lead prompt should include article summaries/content, not just headline titles.

7. **Fix `get_intelligence_dashboard` to surface editorial ledes** — Query recent storylines' `editorial_document` ledes instead of just counting rows.

8. **Fix `get_big_picture_analysis` and `get_trending_topics`** — Generate narrative descriptions for topics and the big picture view instead of returning NULL descriptions and pure counts.

### SYSTEMATIC CHANGES NEEDED

9. **Create a content synthesis service** — A centralized service that, given a storyline or event ID, aggregates all accumulated intelligence (articles, ml_data, entities, claims, events, chronicles, entity profiles) into a rich context object for LLM editorial generation.

10. **Wire the intelligence cascade** — Modify automation manager `_execute_*` methods to pass enriched data forward rather than each phase querying raw data from scratch.

11. **Eliminate dual summary tracks** — Consolidate `master_summary` and `editorial_document` into a single editorial product. RAG analysis, basic summary, and editorial generation should all contribute to `editorial_document`.

---

## Recommendation Summary

1. **Most critical fix:** `editorial_document_service.py` must query `content` + `ml_data` + `entities` instead of just `title` + `summary`. The core product is being built from the least data.

2. **Quick wins that immediately improve output:**
   - RSS collector: capture `content:encoded` for full article bodies
   - RAG analysis: write to `editorial_document` not `analysis_summary`
   - Event creation: populate `editorial_briefing` on insert
   - Storyline list: include `editorial_document->'lede'` in SELECT

3. **Systematic change needed:** Create a content synthesis layer that aggregates all intelligence phases into a unified context before editorial generation, replacing the current pattern where each service independently queries raw data.
