# Content Quality Assessment — Before Phase 1 & 2

**Purpose:** Summarize how we measure content quality today and what we can (and can’t) say about whether we’re generating quality material before deeper v6 quality-first work.

---

## 1. What We Measure Today

### Ingested content (RSS articles)

| Signal | Where | How |
|--------|--------|-----|
| **Article quality score (0–1)** | `api/collectors/rss_collector.py` | `calculate_article_quality_score()`: content length, title length, source reputation (Reuters, AP, BBC, etc.), and “quality indicators” (attribution, data, experts, studies). Stored per article. |
| **Gate at ingest** | Same | Articles with score **&lt; 0.3** are **excluded** and not stored. |
| **Impact score** | Same | `calculate_article_impact_score()`: newsworthiness/impact; used with quality in filtering. |
| **Filtering** | Same + system_monitoring | Clickbait, excluded content, advertisement checks; `GET /api/system_monitoring/articles/analyze` reports how many *existing* articles would be filtered and why (low_quality, low_impact, clickbait, etc.) with sample scores. |

So **input quality** is: (1) scored at ingest, (2) gated (reject &lt; 0.3), and (3) analyzable after the fact via the analyze endpoint.

### Downstream use of quality_score

- **Storyline automation:** `min_quality_score` (default 0.5); articles ordered by quality when building storylines.
- **RAG / briefings:** Articles with `quality_score >= 0.3` used in retrieval; daily briefing and storyline tracker use average quality in context.
- **Topic intelligence:** Topic quality score from confidence, article count, recency.
- **Storyline quality:** Per-storyline `quality_score` (e.g. average of article quality); `QualityAssessmentService` combines article quality, summary presence, etc.

### Generated material (LLM / synthesis)

| Output | Quality signal | Where |
|--------|----------------|-------|
| **Finance orchestrator** | **EVAL_PASSED** / **EVAL_FAILED** | Refresh: “did we get data from any source?” Analysis: “did we complete within budget/iterations?” Logged in finance.log; not a “readability” quality. |
| **Deep content synthesis** | `synthesis_quality_score` | Computed and stored (e.g. completeness, coherence); used in expert/deep synthesis. |
| **Expert / multi-perspective** | `synthesis_quality_score`, `analysis_quality_score` | Calculated from analyses; stored. |
| **LLM calls** | Latency, success/fail | 8 LLM events in last 12h (llama3.1:8b); no explicit “output quality” score in logs. |

So **generated material** has: (1) task-level pass/fail for finance, (2) synthesis/analysis scores in some services, (3) no single human-facing “synthesis quality report” or A/B feedback loop.

---

## 2. What We Can Say Today

- **Ingested articles:** We *do* score and gate them; we can run “analyze existing articles” to see how many would be filtered and their quality/impact distribution. We don’t have a single “last 7 days quality distribution” dashboard.
- **Storylines:** We have per-storyline and per-article quality in the DB; intelligence hub analytics expose **avg article quality** and **avg storyline quality** per domain (where those columns exist).
- **Finance:** Recent 12h: gold_refresh **EVAL_PASSED**; one **EVAL_FAILED** (all_sources_failed); EDGAR ingest ran but vector store add failed (chromadb). So “did we get data?” is trackable; “was the analysis text good?” is not measured.
- **RSS health:** In the same window there were **~8k feed_pull errors** (e.g. “current transaction is aborted”); many feeds reported 0 fetched / 0 saved. That affects *volume* and freshness more than the quality *formula*, but it means we may be processing a smaller subset of feeds than intended.

**Bottom line:** We have the *building blocks* (scores, gates, some aggregates) but **no single “content quality report”** that answers “are we generating quality material?” across ingest, storylines, and synthesis in one place.

---

## 3. Gaps Before Phase 1 & 2

1. **No unified quality snapshot**  
   No one dashboard or report that shows, for a time window: article quality distribution, storyline quality, finance eval pass rate, and (where available) synthesis scores.

2. **Generated output quality is under-measured**  
   We don’t score or log “quality of the LLM-generated summary/synthesis” in a way that’s queryable (e.g. “last 10 briefings: avg score”). Human feedback exists only for topic assignments (`record_feedback`), not for summaries or finance analysis text.

3. **Pipeline observability**  
   Last 12h: no recent pipeline trace in `pipeline_trace.log` (last entry 2026-03-03). So we can’t easily correlate “this run processed N articles with avg quality X” from that log.

4. **RSS transaction errors**  
   Large number of “transaction is aborted” errors suggest DB/connection issues during feed pull; that can reduce how much content we even get to score.

---

## 4. Recommendations Before Phase 1 & 2

1. **Run the existing “analyze articles” endpoint** (e.g. `GET /api/system_monitoring/articles/analyze`) to see current *passing vs filtered* and sample low-quality articles. That gives a baseline for *ingested* content.
2. **Check intelligence hub analytics** (where exposed) for **avg_article_quality** and **avg_storyline_quality** per domain to see if numbers are in a reasonable band (e.g. &gt; 0.5).
3. **Add a minimal “quality snapshot” API or report** (e.g. last 7 days): by domain, (a) article count and avg quality_score, (b) storyline count and avg quality_score, (c) finance eval pass/fail counts. That gives one place to answer “are we generating quality material?” before investing in Phase 1 & 2.
4. **Stabilize RSS/DB** so feed_pull errors drop and pipeline traces (or equivalent) run again; then re-check volume and quality together.

---

## 5. References

- **Quality scoring:** `api/collectors/rss_collector.py` (`calculate_article_quality_score`, `calculate_article_impact_score`), `api/modules/ml/quality_scorer.py`, `api/services/early_quality_service.py`, `api/services/metadata_enrichment_service.py` (quality_score).
- **Filtering / analyze:** `api/domains/system_monitoring/routes/system_monitoring.py` (`GET /articles/analyze`).
- **Aggregates:** `api/services/article_service.py` (avg_quality_score), `api/domains/intelligence_hub/routes/intelligence_hub.py` (avg_article_quality, avg_storyline_quality), `api/domains/news_aggregation/routes/news_aggregation.py` (average_quality_score).
- **v6 quality-first:** `docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md`, `docs/V6_QUALITY_FIRST_TODO.md`.
- **Recent activity:** `docs/LOG_SUMMARY_12H.md`.
