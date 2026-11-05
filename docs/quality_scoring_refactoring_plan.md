# Quality Scoring Pipeline Refactoring Plan

> **Status:** In Progress — Phase A (DB Migration) in execution
> **Created:** 2026-11-03
> **Related Issues:** `quality_score` hybrid formula collision, credibility multiplier distortion, scattered thresholds

---

## Problem Statement

The `articles.quality_score` column contains a hybrid of two different scoring formulas:

| Source | Formula | Applied When |
|--------|---------|-------------|
| **RSS Collector** (rss_collector.py) | `(content_length + title_length + source_reliability)` × `source_credibility.multiplier` (0.72–1.0) | Ingestion time, every article |
| **Deep Analysis** (content_quality_service.py) | Weighted composite of fact_density, clickbait_score, etc. | Post-enrichment processing |

Both write to the same `quality_score` column without version/provenance tracking. Consumers (home_feed, article_signal_gate, quality_assessment_service) read the value but cannot distinguish which formula produced it.

### Specific Issues

1. **No provenance**: A consumer reading `quality_score = 0.72` doesn't know if that's an un-multiplied RSS heuristic or a deep analysis score.
2. **Credibility distortion**: Source credibility multipliers (tier_3 default: 0.85) are applied to the DB column, making high-content articles from low-credibility sources score worse than medium-content articles from trusted sources.
3. **Threshold misalignment**: Scattered cutoffs (home_feed.py: 0.6, orchestrator_governance.py: 0.5/0.3, quality_assessment_service.py: 0.4) don't align with tier boundaries (tier_1≥0.8, tier_2≥0.6, tier_3≥0.4).

---

## Recommendations & Decision Matrix

### Rec 1: Version `quality_score` — eliminate formula collision
- **Approach:** Add `quality_version` column (`rss_heuristic` / `deep_analysis`). Deep analysis always writes complete replacement. RSS writes only initial heuristic.
- **Files affected:** 5 core + ~30 consumers
- **Migration needed?** Yes
- **Risk:** High

### Rec 2: Remove credibility multiplier from core score
- **Approach:** Stop applying `apply_credibility_to_quality_score()` at ingestion. Credibility stays in `metadata->source_credibility` JSON for presentation-layer only.
- **Files affected:** rss_collector.py, source_credibility_service.py, orchestrator_governance.py
- **Risk:** Medium (all scores rise 12-28%)

### Rec 3: Align thresholds with quality tiers
- **Approach:** Replace raw-score cutoffs with tier-based filtering everywhere.
- **Files affected:** home_feed.py, quality_assessment_service.py, article_signal_gate.py, orchestrator_governance.py
- **Risk:** Low (config-only)

### Rec 4: Add confidence/version metadata (paired with Rec 1)
- **Approach:** `quality_version` column + optionally `quality_confidence`.
- **Risk:** Low (additive column, safe backfill)

---

## Dependency Graph (Execution Order)

```
Phase A (Foundations — must be first):
  #4 + part of #1: Add quality_version column & backfill
      └── enables every other recommendation below it

Phase B (Core fix — depends on A):
  #1: Refactor quality_score to never write two formulas
      ├── RSS writes ONLY initial heuristic score
      └── Deep analysis ALWAYS fully replaces with version='deep_analysis'
      └── Depends on Phase A column being available

Phase C (Score isolation — depends on B):
  #2: Remove credibility multiplier from core quality score
      ├── RSS collector stops applying multiplier to quality_score
      └── Credibility becomes separate presentation-layer concept

Phase D (Threshold alignment — can be parallel with C):
  #3: Replace all raw-score thresholds with tier-based filtering
      ├── home_feed.py → filter by quality_tier
      ├── orchestrator_governance.py → use tier constants
      └── article_signal_gate.py → align to tier boundaries
```

**Critical path:** A → B → C → D. Do NOT do #3 in isolation — thresholds tuned against credibility-distorted scores will be meaningless once multipliers are removed.


---

## Implementation Plan: Step-by-Step

### Phase A1: DB Migration — `quality_version` column (Recs 4 + part of 1)

**Migration file:** `api/database/migrations/253_quality_score_provenance.sql`
*(Created separately)*

### Phase B1: RSS Collector Changes (Rec 1)
- **File:** `api/collectors/rss_collector.py`
- Remove `_apply_rss_source_credibility()` from main insertion path
- Keep `calculate_article_quality_score()` as-is (pure content formula)
- Write `quality_version = 'rss_heuristic'` alongside quality_score

### Phase B2: Deep Analysis Changes (Rec 1)
- **Files:** `api/services/content_quality_service.py`, `api/services/quality_assessment_service.py`
- Add `quality_version = 'deep_analysis'` to return dict from `analyze_content_quality()`
- In `update_article_quality_in_db()`, add `SET quality_version = 'deep_analysis'`
- Ensure deep analysis writes quality_score as complete replacement

### Phase C1: Governance Config (Rec 2)
- **File:** `api/config/orchestrator_governance.py`
- Set `"apply_to_quality_score": false` in source_credibility section

### Phase D1: Home Feed Thresholds (Rec 3)
- **File:** `api/domains/reader/services/home_feed.py`
```python
# BEFORE: QUALITY_SCORE_CUTOFF = 0.6
# AFTER:  QUALITY_TIER_GATE = 2 + quality_tier check alongside score
```

### Phase D2: Signal Gate Thresholds (Rec 3)
- **File:** `api/shared/article_signal_gate.py`
- Change from `min_importance_for_processing=0.3` to tier-based equivalent

---

## Effort Summary

| Phase | What | Files | Lines Est. | Days | Risk |
|-------|------|-------|-----------|------|------|
| A1 | Migration: quality_version column + backfill | 1 SQL | ~30 | 0.5 | Low |
| B1 | RSS collector: remove multiplier, add version | rss_collector.py | ~60 | 1 | Medium |
| B2 | Deep analysis: write version tag | content_quality_service.py, quality_assessment_service.py | ~15 | 0.5 | L-M |
| C1 | Governance config: apply_to_quality_score=false | orchestrator_governance.py | 1 | <0.5 | Low |
| D1 | Home feed: tier-aligned filtering | home_feed.py, quality_assessment_service.py | ~20 | 0.5 | Low |
| D2 | Signal gate thresholds | article_signal_gate.py | ~10 | 0.5 | Low |
| **Total** | | **~9 files** | **~136 lines** | **~4 days** | |

## Testing Strategy

1. Post-migration: `SELECT quality_version, count(*) FROM articles GROUP BY quality_version`
2. Before/after score comparison: sample 50 articles with known credibility tiers
3. Threshold regression: run home feed on test dataset, compare top-10 before vs after
4. Gate audit: verify pipeline_article_selection gates pass same articles as before
## Migration Execution Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2026-11-03 | A1 | ✅ Complete | Column `quality_version` added, CHECK constraint + default set |
| 2026-11-03 | B1 | ⏳ Pending | RSS collector: remove multiplier, write `version='rss_heuristic'` |
| 2026-11-03 | B2 | ⏳ Pending | Deep analysis: write `version='deep_analysis'`, ensure full replace |
| 2026-11-03 | C1 | ⏳ Pending | Governance config: `apply_to_quality_score=false` |
| 2026-11-03 | D1 | ⏳ Pending | Home feed: tier-aligned filtering |
| 2026-11-03 | D2 | ⏳ Pending | Signal gate thresholds |
