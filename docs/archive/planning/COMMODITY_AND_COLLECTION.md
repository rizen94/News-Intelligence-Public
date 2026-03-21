# Commodity and Collection Behaviour

## Gold, silver, platinum: price vs news

- **Price collection** (orchestrator sources `gold`, `silver`, `platinum`) fetches **spot prices** from finance APIs (e.g. FRED, FreeGoldAPI). This is **not** news; it’s numeric data for charts and analysis.
- **Commodity news** (Kitco, Mining.com, Reuters Commodities, etc.) is collected via **RSS** in the **finance** domain. Those feeds are in `finance.rss_feeds` and are run by the same RSS collection phase as politics/science-tech. That’s what adds “what is happening at large” and narrative context.

So: the system already separates **price** (throttled commodity sources) from **news** (RSS). Commodity price collection is now run less often, especially off-hours; commodity news continues to flow from RSS at the normal collection cadence.

## Throttling commodity price collection

- In **orchestrator_governance** (YAML and defaults), gold, silver, and platinum have:
  - `min_fetch_interval_seconds: 3600` (1 hour) when **market hours** (US ~9:30–16:00 Eastern).
  - `off_hours_interval_seconds: 14400` (4 hours) when markets are closed (weekends and outside that window).
- The **collection governor** uses these per-source intervals and a simple US market-hours check (UTC 13:30–21:00, weekdays) so price collection runs less often during off-hours.

## What decides “commodity-specific” vs “general market” on the timeline

The **commodity tracker timeline** (and choropleth) shows **tracked events** from the finance domain. To avoid “lots of activity only somewhat related to the specific commodity,” relevance is decided as follows.

### Topic keywords (single source of truth)

- **Defined in:** `api/domains/finance/news_orchestrator.py` → `TOPIC_KEYWORDS`.
- **Per commodity:**
  - **gold:** `gold`, `bullion`, `precious metal`, `yellow metal`, `ounce`, `oz`
  - **silver:** `silver`, `precious metal`, `industrial metal`, `ounce`, `oz`
  - **platinum:** `platinum`, `pgm`, `palladium`, `precious metal`, `catalyst`, `automotive`
- **“all” (broad):** includes `market`, `mining`, `commodity` — used for analysis when the user doesn’t pick a single metal; tends to pull in general market news.

- **Gold vs Goldman Sachs:** The term `gold` is matched as a **whole word** only (`WORD_BOUNDARY_TERMS` in `news_orchestrator.py`), so "Goldman Sachs" is not treated as gold-the-metal.

**Entity extraction and learning:** The pipeline also extracts entities (people, organizations, subjects, recurring_events) into `entity_canonical` per domain. There, "Goldman Sachs" would be stored as `organization` and "gold" (when the LLM treats it as a theme/commodity) as `subject`, so they become **distinct entities** over time. Commodity relevance is currently driven by keyword/topic matching above; in future, timeline/shortlist could use entity_canonical (e.g. "only events/articles that mention the gold subject entity" or "exclude organization Goldman Sachs when showing gold") for an entity-aware filter.

### Timeline / geo-events

- **Endpoint:** `GET /api/{domain}/finance/commodity/geo-events?commodity=gold|silver|platinum` (and `GET .../finance/gold/geo-events` for the gold-only page).
- **Behaviour:** Events are fetched from `intelligence.tracked_events` where `domain_keys` contains the finance domain. If **commodity** is set (or the gold-specific route is used), only events whose **event_name** or **geographic_scope** contain at least one of that commodity’s topic keywords are returned. So “Fed rate decision” (no gold/silver/platinum keyword) is excluded from the gold timeline; “Central bank gold buying” is included.
- **Helper:** `news_orchestrator.is_relevant_to_commodity(text, commodity)` returns True when the text matches at least one keyword for that commodity.

### Analysis shortlist (evidence for LLM)

- **Used by:** evidence collector and analysis flows that call `news_orchestrator.get_shortlist(query, topic=...)`.
- **Behaviour:** Finance articles and intelligence contexts are **scored** by how many topic keywords (and query words) appear in title and snippet. Results are sorted by score and the top `max_items` are returned. There is **no minimum score** today, so a single loose match (e.g. “market”) can still appear when topic is `all`. For a single commodity (e.g. `topic=gold`), only gold keywords are used, so the shortlist is more commodity-specific.

### Tuning

- To make the **timeline** stricter or looser for a commodity, add or remove terms in `TOPIC_KEYWORDS` in `news_orchestrator.py` for that commodity.
- To reduce general market noise in **analysis**, use a specific topic (gold/silver/platinum) rather than “all,” or add a minimum score threshold in `get_shortlist` (e.g. only return items with score ≥ 2).

---

## National and regulatory sources

The **National & regulatory** panel on the commodity dashboard shows tracked events with `event_type` in `regulatory`, `policy`, or `government_bond` (optionally filtered by commodity keywords). Those events are produced by the event-tracking pipeline when it processes finance articles and intelligence contexts. Coverage is **international**: we watch major trading countries, major producers and importers, and countries with significant mining or refining, so gold, silver, and platinum are covered globally.

### International scope: priority countries and regions

Gold, silver, and platinum are globally traded. The system is intended to watch:

- **Major producers (mining):** Australia, Canada, China, Russia, South Africa, Peru, Mexico, Indonesia, USA, Ghana, Kazakhstan (gold); China, Mexico, Peru, Australia, Russia (silver); South Africa, Russia, Zimbabwe, USA (platinum/PGM).
- **Major importers / demand:** India, China, Turkey, USA, UAE, Saudi Arabia, and other large consumer or reserve-building markets.
- **Trading and regulatory hubs:** USA (CFTC, Fed, Treasury), UK (LBMA, Bank of England), Switzerland (SNB), EU (ECB), Canada, Australia, Japan, Singapore.

There is no country filter in the API: events from any `geographic_scope` (e.g. "China", "India", "South Africa") appear in the timeline and regulatory panel when they match commodity keywords and event types. Adding RSS feeds from central banks, mints, and regulators in these jurisdictions increases international coverage.

### RSS feeds that supply regulatory / government content (finance domain)

**US (migration 128):**

- **SEC** — EDGAR browse Atom feed (and `api/scripts/add_official_feeds.py`). Company filings and SEC announcements.
- **Federal Reserve** — `https://www.federalreserve.gov/feeds/press_all.xml`. Press releases and policy.
- **Treasury Direct** — `https://www.treasurydirect.gov/rss/announcements.xml`. Treasury offerings and announcements.
- **FDIC** — `https://www.fdic.gov/news/news/press/feed.xml`. Bank regulatory news.

**International (migration 159):**

- **ECB** — `https://www.ecb.europa.eu/rss/press.html`. Eurozone press releases, speeches, policy.
- **Bank of England** — `https://www.bankofengland.co.uk/rss/news`. UK monetary policy and regulatory news (LBMA hub).
- **Bank of Canada** — News and press-release feeds. Canada is a major gold producer and financial centre.
- **Swiss National Bank** — `https://www.snb.ch/public/en/rss/pressrel`. Switzerland is a major gold trading and storage hub.

These are in `finance.rss_feeds` (migrations `128_add_official_government_feeds.sql`, `159_international_commodity_feeds.sql`). The same RSS collection phase collects all finance feeds; articles are then processed (context_sync → event_tracking). The LLM assigns `event_type` and `geographic_scope`; events appear in the **National & regulatory** panel and in geo-events when they have the right type and (for the map) geographic_scope.

**Not yet in feeds (candidates for future addition):**

- **CFTC** — Script lists CFTC but URL is HTML; add when an RSS/Atom URL is available.
- **Reserve Bank of Australia** — RBA media releases (major gold producer); add feed when URL is confirmed.
- **Reserve Bank of India** — Major gold importer; add if RSS available.
- **Commodity bodies** — LBMA, World Gold Council, and regional mints (e.g. US Mint, Perth Mint) when RSS URLs are available.

### Why the panel can still look empty

1. **Event extraction** — Events only appear after the event-tracking pipeline runs on finance contexts and assigns `event_type` regulatory/policy/government_bond. If few articles mention regulators or policy, few such events are created.
2. **Commodity filter** — When a commodity is selected, the regulatory-events endpoint filters to events whose name/scope match that commodity's topic keywords. General "Fed rate decision" items (no gold/silver/platinum keyword) are excluded from the gold/silver/platinum views.
3. **New deployments** — Migrations 128, 148, and 159 must be applied so finance has US and international regulatory feeds plus commodity business feeds; RSS must have run at least once so articles exist for event extraction.

### API

- **Regulatory events (for National & regulatory panel):** `GET /api/{domain}/finance/commodity/regulatory-events?commodity=gold|silver|platinum&limit=20`  
  Returns events with `event_type` in (`regulatory`, `policy`, `government_bond`), optionally filtered by commodity keywords.

---

## Config reference

- `api/config/orchestrator_governance.yaml` — `collection.sources` entries for gold, silver, platinum with `min_fetch_interval_seconds` and `off_hours_interval_seconds`.
- `api/services/collection_governor.py` — `_base_interval_seconds`, `_is_us_market_hours`, `COMMODITY_PRICE_SOURCE_IDS`.
- `api/domains/finance/news_orchestrator.py` — `TOPIC_KEYWORDS` (and `is_relevant_to_commodity`) for timeline and shortlist relevance.
