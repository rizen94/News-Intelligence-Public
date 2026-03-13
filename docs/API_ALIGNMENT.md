# API–Frontend Alignment Reference (v5)

Quick reference so API routes and response fields stay aligned with the web app.

## Route prefixes (backend)

| Prefix | Domain / router |
|--------|------------------|
| `/api` | Content Analysis (articles list, analyze, topics, etc.) |
| `/api` | News Aggregation (`/{domain}/articles`, `/{domain}/rss_feeds`, etc.) |
| `/api/articles` | Article Deduplication (duplicates/stats, merge, etc.) |
| `/api/rss_feeds` | RSS duplicate management (duplicates/detect, merge, etc.) |
| `/api` | Storyline Management (storylines, watchlist, monitoring) |
| `/api/intelligence_hub` | Intelligence Hub (insights, health) — **underscore**, not hyphen |
| `/api` | Intelligence Hub synthesis (`/{domain}/synthesis/storyline/{id}`) |
| `/api/system_monitoring` | System monitoring, orchestrator health |

## Paths the frontend must use

- **Intelligence Hub insights:** `GET /api/intelligence_hub/insights` (not `intelligence-hub`).
- **Content-analysis article list (e.g. discovery):** `GET /api/articles` (not `content-analysis/articles`).
- **Domain articles:** `GET /api/{domain}/articles` (politics | finance | science-tech).
- **Article detail:** `GET /api/{domain}/articles/{id}`.
- **Article duplicates:** `GET /api/articles/duplicates/stats`, etc.
- **Watchlist:** `GET /api/watchlist`, `POST /api/watchlist/{storyline_id}`, etc.
- **Monitoring:** `GET /api/monitoring/activity-feed`, `dormant-alerts`, `coverage-gaps`, `cross-domain-connections`.
- **Synthesis:** `POST/GET /api/{domain}/synthesis/storyline/{storyline_id}`.

## Article response fields

APIs use DB column names; the frontend should tolerate both where legacy code remains:

| DB / API name | Frontend-friendly alias | Usage |
|---------------|-------------------------|--------|
| `source_domain` | `source` | Single “source” label (API adds `source` when missing). |
| `published_at` | `published_date` | Display date (API adds `published_date` when missing). |
| `content` | — | Body; if empty, API may fill from `excerpt`. |
| `excerpt` | — | Short text; API uses for `summary`/body when content empty. |
| `summary` | — | API fills from excerpt when empty. |

**Backend:** News aggregation article detail and list responses add `source` and `published_date` when not present. Content analysis `GET /api/articles` includes both `source` and `published_date`.

**Frontend:** Prefer `source || source_domain` and `published_date || published_at` (and for body `content || excerpt || summary`) so both naming conventions work.

## RSS

- List: `GET /api/{domain}/rss_feeds`.
- Collect now: `POST /api/{domain}/rss_feeds/collect_now`.
- Create: `POST /api/{domain}/rss_feeds` (body: feed_name, feed_url, is_active, fetch_interval_seconds or update_interval in minutes). Writes to that domain’s schema (e.g. politics.rss_feeds).
- Update: `PUT /api/{domain}/rss_feeds/{feed_id}`.
- Delete: `DELETE /api/{domain}/rss_feeds/{feed_id}`.
- Legacy: `POST /api/rss_feeds` still accepted with `domain` in body (defaults to politics).

## Response shapes

- **Article list (news aggregation):** `{ success, data: { articles, domain, count, total, limit, offset } }`.
- **Article detail:** `{ success, data: <article>, domain? }`.
- **Article list (content analysis):** `{ success, data: { articles, total, page, limit }, message, timestamp }`.
- **Watchlist:** `{ success, data: <array> }`.

**Frontend types:** `web/src/types/index.ts` exports `ArticleLike` (source/source_domain, published_date/published_at, content/excerpt/summary) and helpers `articleSource()`, `articlePublishedAt()`, `articleBody()` so components can treat API responses consistently.

When in doubt, check `api/domains/*/routes/*.py` and `web/src/services/api/*.ts`.
