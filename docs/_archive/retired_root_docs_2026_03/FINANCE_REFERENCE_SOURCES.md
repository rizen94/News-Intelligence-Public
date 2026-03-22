# Finance Reference Sources — What We Have and What’s Publicly Available

Reference data and events to supplement price data: news, reporting, and public disclosures. This doc lists what the system already uses and what public sources you can add for topic-based or query-based requests.

---

## What We Already Have

### 1. **RSS / news (finance domain)**

- **Where:** Articles from `finance.rss_feeds` — collected by `collect_rss_feeds()` and stored in `finance.articles`.
- **How it’s used:** Evidence collector pulls recent finance-domain articles (last 168 hours by default) for analysis prompts; no topic/query filter — it’s “recent N articles” for the domain.
- **What’s in the DB:** Migration 128 adds SEC Press Releases, Federal Reserve Press Releases, Treasury Direct, FDIC. You can add more feeds to `finance.rss_feeds` (Bloomberg, Reuters, MarketWatch, etc.) via API or migration; they’re all public RSS URLs.

**Limitation:** No “request by topic” — we don’t currently filter RSS by keyword (e.g. “platinum”) or call external search APIs. Improving this means either (a) filtering existing finance articles by query/topic before passing to the LLM, or (b) adding topic-aware sources below.

### 2. **SEC EDGAR (public disclosures)**

- **Where:** `api/domains/finance/data_sources/edgar.py` — SEC EDGAR API (no API key; User-Agent required).
- **What we do:** Fetch 10-K (and 40-F) filings for a fixed list of **mining companies** (Barrick, Newmont, Freeport-McMoRan, Agnico Eagle, Wheaton Precious Metals). Full-text sections are extracted, embedded, and stored in the finance vector store for RAG.
- **Rate limit:** 10 requests/second (SEC requirement).
- **Public:** Yes — [SEC EDGAR](https://www.sec.gov/edgar), [SEC Company Search](https://www.sec.gov/cgi-bin/browse-edgar).

**Ways to extend:** Add more CIKs (companies) for commodities (e.g. platinum refiners, other miners), or add 8-K / press-release feeds for event-heavy disclosures.

### 3. **FRED (Federal Reserve Economic Data)**

- **Where:** `api/domains/finance/data_sources/fred.py` — FRED API (API key required, free).
- **What we do:** Fetch series observations (e.g. gold index IQ12260, platinum IP7110, silver IP7106) for history and spot. Used for commodity evidence and charts.
- **Public:** Yes — [FRED](https://fred.stlouisfed.org/), [API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html).

### 4. **Metals / commodities (price data)**

- **Where:** FRED (primary), metals.dev (fallback), manual store (backfill). Silver/platinum/gold flows in `commodity_fetcher`, `commodity_store`, `fred_commodity`.
- **Public:** FRED is public (with key). Metals.dev is a separate provider (quota).

### 5. **Finance vector store (RAG)**

- **Where:** ChromaDB + embeddings of EDGAR-derived text (and any other ingested finance docs).
- **How it’s used:** For analysis tasks we run semantic search on the query and inject top chunks into the prompt. So “topic” is implicit via the user’s query.

---

## Public Sources You Can Add (topic / query oriented)

These are all publicly usable (free or with free tier / registration) and can support “requests for topics” or “requests for events” alongside price data.

### News / reporting (topic or keyword)

| Source | What it provides | Topic/query? | Notes |
|--------|------------------|-------------|--------|
| **SEC RSS / EDGAR full-text** | Filings, press releases, announcements | By company (CIK) or form type | Already have RSS; can add [SEC full-text search](https://www.sec.gov/cgi-bin/sbrt-search) or more RSS feeds (e.g. by SIC) for topic coverage. |
| **Federal Reserve** | FOMC statements, press releases, speeches | By topic (e.g. “monetary policy”) | We have Fed RSS; could filter by keyword or add [Fed calendar/speeches](https://www.federalreserve.gov/newsevents.htm) (RSS/HTML). |
| **NewsAPI.org** | Headlines and articles from many outlets | **Yes — `q` (query) and `language`** | Free tier: 100 req/day. [NewsAPI](https://newsapi.org/docs). Good for “platinum” or “precious metals” topic requests. |
| **GNews** | News search API | **Yes — query and topic** | Free tier available. [GNews API](https://gnews.io/docs/v4). |
| **Event Registry** | News + events, semantic search | **Yes — concept/query and date** | Free tier. [Event Registry](https://eventregistry.org/documentation). Good for “events” plus news. |
| **RSS with filtering** | Our existing RSS articles | **Yes — in our app** | We already store articles; add a **keyword/topic filter** (e.g. “platinum”, “supply”, “PGM”) when building evidence so we only pass relevant snippets. No new API — just filter `finance.articles` by query before sending to the LLM. |

### Disclosures / regulatory (by topic or entity)

| Source | What it provides | Topic/query? | Notes |
|--------|------------------|-------------|--------|
| **SEC EDGAR** | 10-K, 10-Q, 8-K, filings | By company (CIK) or form | Already integrated for mining 10-Ks. Extend to more companies or 8-K for events. |
| **SEC Full-Text Search** | Search filings by text | **Yes — full-text search** | [SEC EDGAR full-text](https://www.sec.gov/edgar/searchedgar/companysearch.html) — can be automated with care (rate limits, no official “search API” but structured URLs). |
| **FDIC / OCC / Fed** | Bank and regulatory releases | By institution or topic | We have FDIC RSS; could add OCC, state regulators, or filter by keyword. |
| **Treasury (Treasury Direct, OFAC)** | Auctions, sanctions, announcements | By topic (e.g. “sanctions”, “bond”) | We have Treasury Direct RSS; OFAC lists and Treasury press releases are public. |

### Events / calendars (dates and themes)

| Source | What it provides | Topic/query? | Notes |
|--------|------------------|-------------|--------|
| **FRED release calendar** | Release dates for series | By series or category | [FRED releases](https://fred.stlouisfed.org/releases) — can map “platinum” or “commodity” to release events. |
| **Fed calendar** | FOMC, speeches, releases | By type | Public calendars; can scrape or use RSS. |
| **LBMA / industry** | Precious metals fixes, reports | By metal | Some public reports and calendars; may require scraping or manual RSS. |

---

## News orchestrator (implemented)

The **news orchestrator** (`api/domains/finance/news_orchestrator.py`) builds a **topic-aware shortlist** for analysis:

- **Input:** query, topic (e.g. platinum), hours lookback, max_items.
- **Sources:** Finance-domain articles (from RSS collection) and intelligence.contexts (finance domain).
- **Scoring:** Topic keywords (e.g. platinum → platinum, pgm, precious metal, catalyst) plus query terms; each item scored by matches in title and snippet.
- **Output:** Sorted shortlist of top N items (title, snippet, url, source, published_at).

The **evidence collector** uses this shortlist when `use_news_orchestrator=True` and a query or topic is set (the default for finance analysis). So analysis gets both price evidence and a **relevant** set of news/contexts instead of “last N” only.

## Practical next steps (no new API keys)

1. **Topic-aware RSS evidence** — Done via the news orchestrator above.

2. **More finance RSS feeds**  
   Migration **148_add_finance_rss_feeds.sql** adds Kitco (markets, commodities, mining), Mining.com, Reuters Business, MarketWatch, Bloomberg Markets, Yahoo Finance to `finance.rss_feeds`. Run the migration (or apply the INSERTs) so routine RSS collection pulls more commodity/market news; the news orchestrator then ranks these by topic for analysis.

3. **EDGAR expansion**  
   Add more CIKs (e.g. platinum-related companies, refiners) or 8-K ingestion so disclosures and event-heavy filings supplement price data.

---

## Adding a “topic request” API (e.g. NewsAPI)

If you add an external news API that accepts a query/topic:

- Add a small **topic-news** module (e.g. `api/domains/finance/data_sources/news_api.py`) that, given `topic` (e.g. `"platinum"`) and optional date range, calls the API and returns normalized snippets (title, url, date, snippet).
- In the **evidence collector** (or orchestrator’s analysis step), when `topic` is platinum/silver/commodity, call this module and merge results into `rss_snippets` (or a dedicated `topic_news_snippets`) so the LLM sees both price evidence and topic-focused news.
- Keep rate limits and API keys in config (e.g. `NEWS_API_KEY` in settings); use the same evidence bundle shape so the rest of the pipeline stays unchanged.

---

## Summary

| Type | Already have | Public and topic/query-capable to add |
|------|----------------|----------------------------------------|
| **News** | RSS (finance domain, gov feeds) | NewsAPI, GNews, Event Registry; or filter existing RSS by topic |
| **Disclosures** | SEC EDGAR (mining 10-Ks) | More CIKs, 8-K, SEC full-text search |
| **Macro / data** | FRED, Fed/Treasury/FDIC RSS | FRED release calendar, more FRED series |
| **Events** | — | Fed calendar, FRED releases, LBMA-style (if public) |

So: we already have **news (RSS)** and **public disclosures (EDGAR)** plus **price data (FRED, metals)**. The biggest leverage with no new keys is **topic filtering of existing RSS** and **more RSS feeds + more EDGAR companies**. For explicit “request by topic” from an external API, NewsAPI, GNews, or Event Registry are good public options to plug into the same evidence path.
