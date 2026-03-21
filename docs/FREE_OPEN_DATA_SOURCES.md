# Free and open-access data sources (curated)

Reference list of **no-subscription** sources that are often suitable for research, news context, and monitoring. **Not wired into the codebase by default** — verify each provider’s terms, rate limits, and attribution rules before production use.

**Already in the system:** FRED, GDELT (RAG), arXiv (document collector), many government RSS feeds (migrations / `rss_feeds`), Treasury Direct RSS (migration 128). See [SOURCES_AND_EXPECTED_USAGE.md](./SOURCES_AND_EXPECTED_USAGE.md).

**Where new integrations would likely land:**

| Need | Domain / layer | Typical integration |
|------|----------------|---------------------|
| Academic PDFs / metadata | **science-tech** + `intelligence.processed_documents` | Extend `document_collector_service` or a sibling fetcher |
| Macro / labour / census | **finance** | New modules under `domains/finance/data_sources/`, keys in `api/config/sources.yaml` |
| Civic / Congress data | **politics** | API clients + optional RSS or stored `events` / contexts |
| Environment / hazards | **science-tech** or global monitoring | Scheduled fetch → articles-like rows or dedicated tables |
| International macro | **finance** | SDMX/CSV parsers, registry-driven series |

---

## Scientific and academic

### Open access repositories

| Source | Notes | API / docs |
|--------|--------|------------|
| **PubMed Central** | Full-text biomedical (PMC); NCBI E-utilities | Developer hub: `https://www.ncbi.nlm.nih.gov/pmc/tools/developers/` — respect **E-utilities rate limits** (typically ~3 req/s without API key; API key improves quota) |
| **arXiv** | Already used (`document_collector_service`) | Could add categories beyond cs.AI/cs.CL via `export.arxiv.org` query |
| **bioRxiv** | Biology preprints | `https://api.biorxiv.org/` |
| **PLOS ONE** | Open access journal | `https://api.plos.org/` |
| **DOAJ** | Directory of Open Access Journals | `https://doaj.org/api/v3/docs` |

### Government research (usually free)

| Source | Notes | API / access |
|--------|--------|----------------|
| **NASA NTRS** | Technical reports | OpenAPI: `https://ntrs.nasa.gov/api/openapi/` |
| **Europe PMC** | European life-science literature | REST, often no key |
| **NIH RePORTER** | Grants and projects | `https://api.reporter.nih.gov/` |

---

## Economic and financial (free tiers / public)

### Government (US)

| Source | Notes | API / access |
|--------|--------|----------------|
| **FRED** | Already in use | `FRED_API_KEY`; see `api/config/sources.yaml` |
| **BLS** | Employment, CPI, etc. | `https://api.bls.gov/publicAPI/v2/` (registration for higher volume) |
| **U.S. Census Bureau** | Economic indicators, surveys | `https://api.census.gov/` (key required for most datasets) |
| **Treasury Direct** | Auctions, debt | RSS/XML available (RSS already partially covered via migration 128 announcements feed) |

### International

| Source | Notes |
|--------|--------|
| **ECB SDW** | European statistics; SDMX |
| **Bank of Canada** | Often free with registration |
| **Reserve Bank of Australia** | Tables / downloads (CSV/Excel), parseable |

---

## News, civic, and analysis (free or registration)

### Nonprofit / public interest

| Source | Notes |
|--------|--------|
| **ProPublica** | Data store / APIs (e.g. Congress-related) — check current docs |
| **OpenSecrets** | Campaign finance — free API with registration |
| **GovTrack** | Congressional activity — free API |

### University news (RSS)

MIT News, Stanford News, Harvard Gazette, and similar often expose **RSS** — add URLs to **`science_tech.rss_feeds`** (or politics if policy-focused) like any other feed; no code change required.

---

## International and development

| Source | Notes |
|--------|--------|
| **UN Data** | Various datasets; confirm endpoint stability |
| **WHO GHO** | Health statistics; OData-style APIs |
| **FAO / FAOSTAT** | Food and agriculture |
| **World Bank Open Data** | Broad open data API |
| **OECD** | Many free datasets; API coverage varies by series |

---

## Environmental and specialized monitoring

| Source | Notes |
|--------|--------|
| **NOAA** | Climate / weather APIs — often token-based, free tier |
| **USGS Earthquakes** | GeoJSON feeds, no auth — good for **real-time monitoring** widgets or event ingestion |
| **OpenAQ** | Air quality — `https://api.openaq.org/v2/` (check v2 deprecation / migration notices) |

### Security / conflict (often free for research)

| Source | Notes |
|--------|--------|
| **GDELT** | Already used in RAG |
| **ACLED** | Often free for non-commercial; registration |
| **GTD** | Registration; academic use |

---

## Free with registration (no payment)

| Source | Typical use |
|--------|----------------|
| **OpenCorporates** | Company identifiers |
| **CrossRef** | DOI / citation metadata (polite use) |
| **CORE** | OA aggregator API |
| **Semantic Scholar** | Paper search / metadata |

---

## Prefer to avoid for “free” production news pipelines

- **X (Twitter) API** — heavily restricted / paid for real volume  
- Commercial terminals and proprietary research DBs — licensing  
- “Free” news APIs that are rate-limited to unusable levels for aggregation  

---

## Example config sketch (future — not loaded by app)

Illustrative YAML only; **do not** assume this file exists in `api/config` until implemented.

```yaml
# Illustrative: free sources (candidate design — not wired)
free_sources:
  pubmed_pmc:
    type: api
    base_url: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
    rate_limit_per_sec: 3
    api_key_env: NCBI_API_KEY   # optional; increases quota

  biorxiv:
    type: api
    base_url: https://api.biorxiv.org/
    # optional: restrict subject collections

  bls:
    type: api
    base_url: https://api.bls.gov/publicAPI/v2/
    registration_key_env: BLS_API_KEY

  treasury_auctions_rss:
    type: rss
    url: https://www.treasurydirect.gov/TA_WS/securities/auctioned/rss

  usgs_earthquakes:
    type: geojson_feed
    urls:
      significant_month: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson
      m4_5_day: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson
```

---

## Next steps (when you want implementation)

1. Pick **one** source (e.g. USGS GeoJSON for science-tech monitoring, or BLS for finance CPI series).  
2. Add a **data source module** under `api/domains/{domain}/data_sources/` or extend **`document_collector_service`** for PDF/metadata-only flows.  
3. Register credentials and rate limits in **`api/config/sources.yaml`** (or a dedicated YAML loaded by that module).  
4. Document the new source in **[SOURCES_AND_EXPECTED_USAGE.md](./SOURCES_AND_EXPECTED_USAGE.md)** in the same PR.

For **RSS-only** additions, prefer inserting rows into **`rss_feeds`** via migration or admin API — fastest path, no new Python.
