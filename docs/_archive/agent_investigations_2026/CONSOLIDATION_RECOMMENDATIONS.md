# API Routes Consolidation Recommendations

## Executive Summary
Analysis of 54 route files across 9 domains revealed significant duplication, inconsistency, and domain boundary violations. Key findings include 6+ duplicate health endpoints, exact duplicate `/duplicates/*` routes in 2 files, storyline CRUD split across 3 files, and article endpoints duplicated across 3 domains.

---

## Priority Consolidation Recommendations

### P0 - Critical (Do First Sprint)

| # | Area | Action | Files Affected | Effort | Impact |
|---|------|--------|----------------|--------|--------|
| 1 | Health Checks | Centralize to single `/api/health` with domain query param | 6+ files | Low (1 day) | High - removes 5+ duplicates |
| 2 | Duplicate `/duplicates/*` | Merge `rss_duplicate_management.py` + `article_deduplication.py` | 2 files | Medium (3 days) | High - eliminates exact duplication |
| 3 | Storyline CRUD | Consolidate `storyline_crud.py` + `storyline_management.py` + `storyline_articles.py` | 3 files | Medium (3 days) | High - single source of truth |
| 4 | Legacy Endpoints | Deprecate `/api/articles/recent`, `/api/rss_feeds`, `/api/fetch_articles` | 1 file | Low (1 day) | Medium - cleanup |

### P1 - High (Next 2 Sprints)

| # | Area | Action | Files Affected | Effort | Impact |
|---|------|--------|----------------|--------|--------|
| 5 | Article Endpoints | Create shared article service/router, domain-scoped via middleware | 3 domains | Medium (5 days) | High - reduces 3x duplication |
| 6 | Topic/Clustering | Consolidate 4 topic files into 2: `topics.py` (CRUD) + `clustering.py` (ML) | 4 files | High (10 days) | Medium - clear separation |
| 7 | Automation | Merge 3 automation files into `automation.py` with sub-routers | 3 files | Medium (5 days) | Medium |
| 8 | Entity Resolution | Move from `context_centric.py` to dedicated `entity_resolution.py` router | 1 file | Low (2 days) | Medium - proper domain placement |

### P2 - Medium (Quarter)

| # | Area | Action | Files Affected | Effort | Impact |
|---|------|--------|----------------|--------|--------|
| 9 | Route Standardization | Enforce consistent path params, response format, domain prefix | All | Medium (10 days) | Medium - DX improvement |
| 10 | Cross-Domain Routes | Move to dedicated `cross_domain.py` with clear ownership | 2 files | Medium (5 days) | Low - architecture clarity |
| 11 | Monitoring Consolidation | Merge 8 monitoring files into logical groups | 8 files | High (15 days) | Medium |

### P3 - Long-term

| # | Area | Action | Effort | Impact |
|---|------|--------|--------|--------|
| 12 | API Versioning | Implement versioning strategy | High | High |
| 13 | OpenAPI Spec | Single-source OpenAPI generation | Medium | Medium |
| 14 | Automated Testing | Route consistency tests in CI | Medium | High |

---

## Detailed Findings

### Exact Duplicates
1. **Health Checks** (6+): Each domain implements `/health` with similar DB+LLM checks
2. **Deduplication Endpoints** (2 files, identical paths):
   - `news_aggregation/routes/rss_duplicate_management.py` (lines 49-271)
   - `content_analysis/routes/article_deduplication.py` (lines 38-347)
3. **Storyline CRUD** (3 files):
   - `storyline_crud.py` (lines 53-688)
   - `storyline_management.py` (lines 93-288) - **duplicate CRUD**
   - `storyline_articles.py` (overlaps article linking)

### Functional Duplicates
- Article retrieval: 3 domains (news_aggregation, content_analysis, storyline_management)
- Article analysis: 3 endpoints with different paths
- Topic management: 4 files with overlapping responsibilities

### Pattern Inconsistencies
- Path params: `{domain}`, `{domain_key}`, `{article_id}`, `{id}`, `{storyline_id}`
- Response formats: Some `{"success": true, "data": {...}}`, others raw models
- Domain prefix: `/api/{domain}/`, `/api/content_analysis/`, `/api/{domain}/finance/`

### Domain Boundary Violations
- Content Analysis routes in News Aggregation (deduplication)
- Storyline conversion in Content Analysis (`convert_to_storyline`)
- Entity resolution in Intelligence Hub (should be in services)
- Cross-domain synthesis in Intelligence Hub (should orchestrate)

---

## Implementation Order

1. **Week 1**: Health centralization + Legacy deprecation
2. **Week 2-3**: Deduplication merge + Storyline CRUD consolidation
3. **Week 4-5**: Article service extraction + Topic consolidation
4. **Week 6-8**: Automation merge + Entity resolution move
5. **Ongoing**: Route standardization + Monitoring consolidation

## Estimated Effort
- **P0 items**: 1-2 days each (straightforward consolidation)
- **P1 items**: 3-5 days each (require interface design)
- **P2 items**: 2-3 days each (refactoring with tests)
- **P3 items**: 1-2 days each (largely mechanical)

Total estimated effort: 2-3 weeks for significant duplication reduction.