# API Routes Overlap Report

## Executive Summary
Analysis of 54 route files across 9 domains revealed significant duplication and overlap in API endpoints. Key findings include:
- **6+ duplicate health check endpoints**
- **2 identical deduplication endpoint sets** (`/duplicates/*`)
- **Storyline CRUD split across 3 files**
- **Article endpoints duplicated across 3 domains**
- **Automation endpoints split across 3 files**
- **Inconsistent naming and parameter patterns**

---

## Detailed Overlap Analysis

### 1. Health Check Endpoints (6+ Duplicates)
Each domain implements its own `/health` endpoint with similar functionality:

| File | Endpoint | Description | Lines |
|------|----------|-------------|-------|
| `api/domains/news_aggregation/routes/news_aggregation.py:38` | `GET /api/health` | Domain health + DB + LLM check | 38-72 |
| `api/domains/content_analysis/routes/topic_management.py:82` | `GET /api/health` | Domain health | 82-? |
| `api/domains/content_analysis/routes/content_analysis.py:40` | `GET /api/health` | Domain health | 40-? |
| `api/domains/storyline_management/routes/storyline_management.py:36` | `GET /api/health` | Domain health | 36-? |
| `api/domains/system_monitoring/routes/system_monitoring.py:196` | `GET /api/health` | System-wide health | 196-? |
| `api/domains/system_monitoring/routes/route_supervisor.py:21` | `GET /api/route_supervisor/health` | Route health | 21-? |
| `api/domains/intelligence_hub/routes/intelligence_hub.py:25` | `GET /api/health` | Intelligence hub health | 25-? |

**Impact**: 6+ redundant implementations, inconsistent health check coverage
**Resolution**: Create centralized health check service with domain-specific probes

---

### 2. Identical Deduplication Endpoints (Exact Duplicates)
Two files implement the exact same `/duplicates/*` endpoints:

#### File 1: `api/domains/news_aggregation/routes/rss_duplicate_management.py` (lines 49-271)
- `GET /duplicates/detect` (line 49)
- `GET /duplicates/exact` (line 76)
- `GET /duplicates/similar` (line 103)
- `POST /duplicates/merge` (line 130)
- `POST /duplicates/auto_merge` (line 203)
- `POST /duplicates/prevent` (line 242)
- `GET /duplicates/stats` (line 271)

#### File 2: `api/domains/content_analysis/routes/article_deduplication.py` (lines 38-347)
- `GET /duplicates/detect` (line 38)
- `GET /duplicates/url` (line 65) - *Note: slightly different name*
- `GET /duplicates/content` (line 92)
- `GET /duplicates/similar` (line 119)
- `POST /duplicates/merge` (line 146)
- `POST /duplicates/auto_merge` (line 202)
- `POST /duplicates/prevent` (line 241)
- `GET /duplicates/stats` (line 271)
- `POST /duplicates/analyze_similarity` (line 347) - *Additional endpoint*

**Impact**: Complete duplication of core deduplication functionality
**Note**: Despite similar endpoints, implementations differ slightly (URL vs content focus)
**Resolution**: Consolidate into single deduplication service with clear separation of concerns

---

### 3. Storyline CRUD Split Across 3 Files

#### File 1: `api/domains/storyline_management/routes/storyline_crud.py` (lines 53-688)
Basic CRUD:
- `GET /{domain}/storylines` (list) - line 53
- `POST /{domain}/storylines` (create) - line 196
- `GET /{domain}/storylines/{storyline_id}` (detail) - line 262
- `PUT /{domain}/storylines/{storyline_id}` (update) - line 501
- `DELETE /{domain}/storylines/{storyline_id}` (delete) - line 688
- `GET /{domain}/storylines/{id}/related_cross_domain` - line 605

#### File 2: `api/domains/storyline_management/routes/storyline_management.py` (lines 36-1349)
**Duplicates the CRUD operations**:
- `GET /{domain}/storylines` (line 93)
- `POST /{domain}/storylines` (line 186)
- `PUT /{domain}/storylines/{storyline_id}` (line 221)
- `DELETE /{domain}/storylines/{storyline_id}` (line 288)
- `GET /{domain}/storylines/{storyline_id}` (line 595)
- Plus additional endpoints for articles: 
  - `DELETE /{domain}/storylines/{id}/articles/{article_id}` (line 346)
  - `POST /{domain}/storylines/{id}/articles/{article_id}` (line 424)
  - `GET /{domain}/storylines/{id}/available_articles` (line 517)

#### File 3: `api/domains/storyline_management/routes/storyline_articles.py` (lines 34-229)
Further duplication:
- `POST /{domain}/storylines/{storyline_id}/articles/{article_id}` (line 34)
- `DELETE /{domain}/storylines/{storyline_id}/articles/{article_id}` (line 151)
- `GET /{domain}/storylines/{storyline_id}/available_articles` (line 229)

**Impact**: Triple implementation of core storyline entity operations
**Resolution**: Single storyline CRUD router with modular sub-routers for articles, timeline, etc.

---

### 4. Article Endpoints Duplicated Across 3 Domains

#### News Aggregation Domain
- `GET /{domain}/articles` - list articles (line 426)
- `GET /{domain}/articles/{article_id}` - get single article (line 522)
- `POST /articles/{article_id}/analyze_quality` - background quality analysis (line 723)

#### Content Analysis Domain
- `GET /articles` - list articles (line 175) - *Note: no domain prefix!*
- `GET /articles/{article_id}` - get single article (line 2471)
- `POST /articles/{article_id}/analyze` - immediate analysis (line 201)

#### Storyline Management Domain (via article linking)
- `GET /{domain}/storylines/{storyline_id}/articles` - get articles in storyline (line 432 in topic_management.py)
- `POST /{domain}/storylines/{storyline_id}/articles/{article_id}` - add article to storyline (multiple locations)

**Impact**: Inconsistent article access patterns, domain confusion
**Resolution**: Single article service with domain-scoped routing via middleware

---

### 5. Automation Endpoints Split Across 3 Files

#### File 1: `api/domains/storyline_management/routes/storyline_automation.py` (lines 100-509)
- `GET /{domain}/storylines/review-queue/count` (line 100)
- `GET /{domain}/storylines/review-queue` (line 127)
- `GET /{domain}/storylines/{storyline_id}/automation/settings` (line 196)
- `PUT /{domain}/storylines/{storyline_id}/automation/settings` (line 265)
- `POST /{domain}/storylines/{storyline_id}/automation/discover` (line 342)
- `GET /{domain}/storylines/{storyline_id}/automation/suggestions` (line 369)
- `POST /{domain}/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/approve` (line 427)
- `POST /{domain}/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/reject` (line 509)

#### File 2: `api/domains/storyline_management/routes/storyline_automation_bulk.py` (lines 84-197)
- `POST /{domain}/storylines/review-queue/bulk-approve` (line 84)
- `POST /{domain}/storylines/review-queue/bulk-reject` (line 148)
- `POST /{domain}/storylines/automation/discover` (line 197) - *Duplicate!*

#### File 3: `api/domains/storyline_management/routes/storyline_management.py` (partial)
Contains automation-like endpoints:
- `POST /{domain}/storylines/{storyline_id}/evolve` (line 1044)
- `POST /{domain}/storylines/{storyline_id}/analyze` (line 780)
- `POST /{domain}/storylines/detect` (line 1297)

**Impact**: Fragmented automation workflow, duplicate discover endpoints
**Resolution**: Unified automation service with clear pipeline stages

---

### 6. Entity/Resolution Endpoints in Wrong Domain

Entity resolution operations belong in services but are exposed via intelligence hub:

#### `api/domains/intelligence_hub/routes/context_centric.py`
- `POST /entities/resolve` (line 2534)
- `POST /entities/populate_aliases` (line 2553)
- `GET /entities/merge_candidates` (line 2570)
- `POST /entities/merge` (line 2584)
- `POST /entities/auto_merge` (line 2602)
- `POST /entities/cross_domain_link` (line 2621)
- `POST /entities/run_resolution_batch` (line 2634)
- `GET /entities/canonical` (line 2650)

**Impact**: Business logic leaked into API layer, tight coupling
**Resolution**: Move to dedicated entity service with clean service-layer API

---

### 7. Legacy Endpoints Still Active

#### `api/domains/news_aggregation/routes/news_aggregation.py`
- `GET /articles/recent` (line 697) - Comment: "Legacy endpoint - redirects to politics domain."
- `POST /rss_feeds` (line 342) - Comment: "Create RSS feed (legacy). Prefer POST /{domain}/rss_feeds."
- `POST /fetch_articles` (line 395) - Global RSS collection trigger

**Impact**: Technical debt, confusing API surface
**Response**: Should return 410 Gone or 301 Moved Permanently with deprecation headers

---

### 8. Cross-Domain Endpoint Ambiguity

#### Intelligence Hub vs Content Analysis
- `POST /{domain}/content_analysis/topics/{cluster_name}/convert_to_storyline` (content_analysis:1198) - Creates storyline from topic cluster
- Multiple storyline creation endpoints in storyline_management
- Entity resolution endpoints in intelligence_hub that should be service calls

**Impact**: Unclear domain responsibilities, circular dependencies possible

---

## Summary of Overlap Issues

| Issue Type | Count | Examples | Severity |
|------------|-------|----------|----------|
| Exact Duplicates | 2+ | Health checks, deduplication endpoints | High |
| Functional Duplicates | 5+ | Storyline CRUD, article endpoints, automation | High |
| Boundary Violations | 3+ | Entity resolution in API, cross-domain leaks | Medium |
| Legacy Endpoints | 3 | `/articles/recent`, `/rss_feeds` (global), `/fetch_articles` | Low-Medium |
| Naming Inconsistencies | Numerous | `{domain}` vs `{domain_key}`, `{id}` vs various | Low |

## Recommended Consolidation Order

1. **P0**: Health checks (simple, high impact)
2. **P0**: Deduplication endpoints (exact duplicates)
3. **P0**: Storyline CRUD (triple implementation)
4. **P1**: Article endpoints (cross-domain confusion)
5. **P1**: Automation endpoints (fragmented workflow)
6. **P2**: Entity resolution (move to service layer)
7. **P2**: Legacy endpoint deprecation
8. **P3**: Naming/pattern standardization

## Estimated Effort
- **P0 items**: 1-2 days each (straightforward consolidation)
- **P1 items**: 3-5 days each (require interface design)
- **P2 items**: 2-3 days each (refactoring with tests)
- **P3 items**: 1-2 days each (largely mechanical)

Total estimated effort: 2-3 weeks for significant duplication reduction.