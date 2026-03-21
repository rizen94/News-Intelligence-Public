# Quality-First Implementation Plan

**Purpose:** Activate existing quality gates so selection logic prioritizes **quality over recency** and optionally enforces hard quality thresholds. This doc maps the strategy from [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md) to concrete code and rollout order.

**Related:** [CONTENT_QUALITY_STANDARDS.md](CONTENT_QUALITY_STANDARDS.md), [STORY_ASSEMBLY_AND_DATA_QUALITY.md](STORY_ASSEMBLY_AND_DATA_QUALITY.md), migration `164_content_quality_tiers.sql`.

---

## 1. Problem Summary

- **Caps protect quantity, not quality.** "Latest 30 articles" or "top 20 entities by mention count" can be low-quality.
- **Briefings "prefer" quality_tier 1–2** but don't require it; we fall back to any quality.
- **Report lead** is "first event, else first storyline, else first article" by list order — no quality check.
- **Domain synthesis** and **article list** order by recency only; no quality_tier or quality_score in selection.

---

## 2. Levers Already in the Codebase

| Lever | Where | Current state |
|-------|--------|----------------|
| `quality_tier` (1=best, 4=worst) | `{domain}.articles` | Populated by ML pipeline; default 3 |
| `quality_score` (0–1) | `{domain}.articles` | Populated by ML pipeline |
| `clickbait_probability`, `fact_density` | `{domain}.articles` | Optional; migration 164 |
| Briefing headlines | `daily_briefing_service._extract_key_developments` | ORDER BY quality_tier ASC, quality_score DESC — **no WHERE** |
| Article list | `article_service.get_articles` | ORDER BY published_at DESC only |
| Domain synthesis articles | `content_synthesis_service.synthesize_domain_context` | ORDER BY published_at DESC only |
| Storyline editorial articles | `editorial_document_service.generate_storyline_editorial` | ORDER BY published_at DESC only |
| Report page | `getArticles(12)` + `getStorylines()` + `getTrackedEvents(8)` | No quality filter; lead = first in list |

---

## 3. Implementation Order

### Phase 1: Quality-first selection (backward-compatible)

- **content_synthesis_service**  
  - Add optional `max_quality_tier: Optional[int] = None`.  
  - When set (e.g. 2): `WHERE quality_tier <= max_quality_tier` and `ORDER BY COALESCE(quality_tier, 4) ASC, COALESCE(quality_score, 0) DESC, published_at DESC`.  
  - When None: keep current behavior (recency only).

- **article_service**  
  - Add optional filters: `max_quality_tier`, `quality_first` (bool).  
  - When `max_quality_tier` set: add `AND quality_tier <= max_quality_tier`.  
  - When `quality_first` true: `ORDER BY COALESCE(quality_tier, 4) ASC, COALESCE(quality_score, 0) DESC, published_at DESC NULLS LAST`.  
  - Default: no change (recency as today).

- **news_aggregation route**  
  - Add query params: `quality_first`, `max_quality_tier`; pass into `filters`.

- **daily_briefing_service**  
  - Add optional `require_quality_tier_1_2: bool = False`.  
  - When True: headlines query `WHERE ... AND COALESCE(quality_tier, 4) <= 2` (fewer items OK).  
  - Default False to preserve current behavior.

- **editorial_document_service**  
  - For storyline articles query: change to quality-first order: `ORDER BY COALESCE(a.quality_tier, 4) ASC, COALESCE(a.quality_score, 0) DESC, a.published_at DESC NULLS LAST`.  
  - No new param; always use best 12 articles for editorial.

### Phase 2: Enforce quality at ingestion (later)

- Auto-reject or flag `quality_tier = 4` from context creation (optional).  
- Skip or deprioritize entity extraction for clickbait (e.g. `clickbait_probability > 0.7`).  
- Flag sources with >50% low-quality for monitoring.

### Phase 3: Assembly logic (later)

- Briefings: prefer showing fewer items when strict quality is on (already done if we add `require_quality_tier_1_2`).  
- Report: optional rule "lead must have editorial_document or editorial_briefing" (frontend or backend).  
- Storylines: auto-remove articles that drop below threshold (existing quality gates in discovery).

### Phase 4: Historical cleanup (optional)

- Archive contexts from quality_tier 4 articles; merge duplicate entities; recalc mention counts excluding low-quality.

---

## 4. Code Map (Phase 1)

| File | Change |
|------|--------|
| `api/services/content_synthesis_service.py` | `synthesize_domain_context(..., max_quality_tier=None)`. Article query: optional WHERE quality_tier <= max_quality_tier; ORDER BY quality_tier, quality_score, published_at when max_quality_tier set. |
| `api/domains/news_aggregation/services/article_service.py` | `get_articles(..., filters: max_quality_tier, quality_first)`. WHERE and ORDER BY as above. |
| `api/domains/news_aggregation/routes/news_aggregation.py` | Query params `quality_first`, `max_quality_tier` → filters. |
| `api/modules/ml/daily_briefing_service.py` | `_extract_key_developments(..., require_quality_tier_1_2=False)`. Headlines: add AND COALESCE(quality_tier, 4) <= 2 when True. |
| `api/services/editorial_document_service.py` | Storyline articles: ORDER BY COALESCE(a.quality_tier, 4) ASC, COALESCE(a.quality_score, 0) DESC, a.published_at DESC. |

---

## 5. How to Flip the Switch

- **Report page (Today's Report):**  
  Call `getArticles({ limit: 12, quality_first: true, max_quality_tier: 2 })` so the article list (and thus potential article lead) is quality-bounded. Events and storylines are already ordered by backend; optional future rule: prefer lead that has editorial_document/editorial_briefing.

- **Briefings:**  
  Set `require_quality_tier_1_2=True` where key_developments is called (e.g. config or env `BRIEFING_REQUIRE_QUALITY_TIER_1_2=true`).

- **Domain synthesis:**  
  Call `synthesize_domain_context(..., max_quality_tier=2)` from products that want quality-first context (e.g. LLM briefing lead, future editorial endpoints).

- **Article list API:**  
  Any client can pass `quality_first=true` and/or `max_quality_tier=2`; no frontend change required for other pages until you want them quality-first.

---

## 6. Defaults and Backward Compatibility

- All new parameters are **optional** and default to current behavior (recency-only, no hard quality filter).  
- Enabling quality-first is opt-in per call or via config so existing consumers are unchanged.

---

## 7. Quick Wins Checklist

- [x] Content synthesis: optional `max_quality_tier` + quality-first ORDER when set.  
- [x] Article service: filters `max_quality_tier`, `quality_first`; quality-first ORDER when requested.  
- [x] Articles route: query params `quality_first`, `max_quality_tier`.  
- [x] Briefing: optional `require_quality_tier_1_2` for headlines.  
- [x] Editorial document: storyline articles ordered by quality then recency.  
- [x] Report page: pass `quality_first: true`, `max_quality_tier: 2` in `getArticles` (ReportPage.tsx).  
- [ ] Config/env for briefing and synthesis defaults (e.g. `SYNTHESIS_MAX_QUALITY_TIER` when calling synthesis from products).

---

## 8. Review (post-implementation)

- **Article service count:** Count query now applies the same `max_quality_tier` filter as the main query so `total` is correct when filtering by quality.
- **Domain synthesis API:** `GET /api/synthesis/domain` accepts optional `max_quality_tier` (1–4) and passes it to `synthesize_domain_context`.
- **Storyline synthesis:** `synthesize_storyline_context` now orders storyline articles quality-first (same as editorial_document_service) so synthesis and editorial use the same article ordering.
