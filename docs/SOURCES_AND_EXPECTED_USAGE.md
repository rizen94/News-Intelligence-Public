# Sources and expected usage

Master inventory of **where data comes from** and **what in the system consumes it**. For collection cadence and orchestration detail, see [DATA_SOURCES_AND_COLLECTION.md](./DATA_SOURCES_AND_COLLECTION.md). For finance commodity specifics, see [COMMODITY_DATA_SOURCES.md](./COMMODITY_DATA_SOURCES.md).

---

## Quick reference — source → usage

| Source / category | Primary config or location | Expected usage in the system |
|-------------------|----------------------------|--------------------------------|
| **RSS (per domain)** | DB: `politics.rss_feeds`, `finance.rss_feeds`, `science_tech.rss_feeds` (`is_active = true`) | Ingest headlines/articles via `collect_rss_feeds()`; OrchestratorCoordinator (`source_id: rss`) + AutomationManager `rss_processing`; feeds **topics**, **storylines**, **contexts**, **events**, enrichment. Science-tech feed expansion: migration **173** + [SCIENCE_TECH_DOMAIN_STRATEGY.md](./SCIENCE_TECH_DOMAIN_STRATEGY.md) |
| **Gold (prices)** | `orchestrator_governance.yaml` → `collection.sources` (`topic: gold`) | FinanceOrchestrator refresh; **gold_amalgamator** (FRED IQ12260, metals.dev, freegoldapi); commodity APIs/dashboards |
| **Silver / Platinum (prices)** | Same YAML (`topic: silver` / `platinum`) | **commodity_fetcher** + registry; finance dashboards |
| **Oil / Gas (prices)** | `commodity_registry.yaml` + env `FRED_OIL_SERIES_ID`, `FRED_GAS_SERIES_ID` | FRED-only spot/history when env set; filtered **news** via finance RSS + contexts |
| **EDGAR (SEC)** | YAML (`topic: edgar`); `api/config/sources.yaml`; env `EDGAR_USER_AGENT` | 10-K / filing ingest, finance evidence, vector store; rate-limited SEC API |
| **FRED (macro series)** | `api/config/sources.yaml`; env `FRED_API_KEY` | Gold index series, oil/gas, rates/CPI/M2/etc.; gold amalgamator; optional `POST /{domain}/finance/fetch-fred` |
| **Metals.dev** | `sources.yaml`; env `METALS_DEV_API_KEY` | Gold/silver/platinum price windows in amalgamator/commodity paths |
| **Freegoldapi** | `domains/finance/gold_sources/freegoldapi.py` (no key) | Fallback USD/oz spot in **gold_amalgamator** |
| **Document feeds (CRS, GAO, CBO, arXiv)** | `orchestrator_governance.yaml` → `document_sources.automated_sources`; `document_collector_service.py` | PDF discovery → `intelligence.processed_documents` → document processing pipeline |
| **Wikipedia (REST)** | `services/rag/base.py` — `https://en.wikipedia.org/api/rest_v1` | RAG **storyline context** enrichment, summaries; optional smart cache |
| **GDELT (public API)** | `services/rag/base.py` — `https://api.gdeltproject.org/api/v2` | RAG context, **chronological_events** (extraction_method `gdelt`); circuit breaker `gdelt` |
| **Ollama** | env `OLLAMA_URL` (default `http://localhost:11434`); `shared/services/llm_service.py` | Summaries, entities, sentiment, topic extraction, storyline analysis, entity JSON, relational expansion, many automation phases |
| **Sentence Transformers** | `sentence_transformers` model `all-MiniLM-L6-v2` (`services/rag/retrieval.py`) | RAG **semantic/hybrid** retrieval embeddings (local) |
| **Article URL fetch (enrichment)** | `article_content_enrichment_service.py` — trafilatura, optional Wayback / archive.today / Playwright | Full-text **enrichment** for short RSS bodies; 403/401 expected on some publishers |
| **Monitoring / health** | `api/config/monitoring_devices.yaml` | SSH/HTTP checks for Widow/NAS/Pi; health_feeds poll API routes |
| **Legacy embedded RSS list** | `api/modules/data_collection/rss_feed_service.py` | **Not canonical** — production ingestion uses **domain `rss_feeds` tables**; keep in mind if scripts still import this module |

---

## 1. Orchestrated collection (`collection.sources`)

**File:** `api/config/orchestrator_governance.yaml` → `collection`.

| `source_id` | Handler | Topic / notes | Expected usage |
|-------------|---------|---------------|----------------|
| `rss` | `rss` | — | Pull all active domain RSS feeds; primary news ingest. |
| `gold` | `finance` | `gold` | Refresh gold evidence/spot; uses amalgamator (FRED + metals.dev + freegoldapi). Intervals: `min_fetch_interval_seconds` / `off_hours_interval_seconds`. |
| `silver` | `finance` | `silver` | Commodity spot/history for silver. |
| `platinum` | `finance` | `platinum` | Commodity spot/history for platinum. |
| `edgar` | `finance` | `edgar` | SEC filing pipeline. |

**Runner:** `OrchestratorCoordinator` (see `main_v4` lifespan) rotates sources using `CollectionGovernor` and the YAML intervals.

**Commodity news (headlines)** is intentionally **not** these handlers — it comes from **finance-domain RSS** (e.g. Kitco, Mining.com, Reuters, MarketWatch, Bloomberg, Yahoo — see migration `148_add_finance_rss_feeds.sql`).

---

## 2. Domain RSS feeds (database)

- **Tables:** `{politics|finance|science_tech}.rss_feeds` (schema name `science_tech` in DB).
- **Consumers:** `collect_rss_feeds()` (orchestrator + automation), domain article APIs, downstream ML/context/event pipelines.
- **Seeded / documented feeds:**
  - **Migration 128** — SEC, Fed, Treasury, FDIC (finance); White House, State, DOJ, DOD, CRS, GAO, CBO (politics); NASA, NIST, DOE, NIH (science-tech).
  - **Migration 148** — Additional finance/market RSS (Kitco, Mining.com, Reuters, MarketWatch, Bloomberg, Yahoo).
- **Human-readable list:** [OFFICIAL_GOVERNMENT_FEEDS.md](./OFFICIAL_GOVERNMENT_FEEDS.md).
- **Management:** API routes under news aggregation / RSS management (see [RSS_FEED_MANAGEMENT_SYSTEM.md](./RSS_FEED_MANAGEMENT_SYSTEM.md)); `is_active` gates collection.

---

## 3. Document acquisition (`document_sources`)

**File:** `api/config/orchestrator_governance.yaml` → `document_sources`.

| Key | Purpose |
|-----|---------|
| `automated_sources` | Subset of `crs`, `gao`, `cbo`, `arxiv` run by `document_collector_service.collect_documents_batch` |
| `ingest_urls` | Optional manual URLs or `{url, title, source_type}` for one-off ingest |

**Fetch endpoints (in code):**

| Source | Feed / API | Domain tagging | Output |
|--------|------------|----------------|--------|
| CRS | `https://crsreports.congress.gov/rss/reports` | politics | `intelligence.processed_documents` |
| GAO | `https://www.gao.gov/rss/reports.xml` | unscoped (`None`) | Same |
| CBO | `https://www.cbo.gov/publications/all/rss.xml` | unscoped | Same |
| arXiv | `export.arxiv.org` API (cs.AI, cs.CL) | science-tech | PDF URLs → same table |

---

## 4. Finance API registry

**File:** `api/config/sources.yaml`

| Key | Type | Credentials | Expected usage |
|-----|------|-------------|----------------|
| `fred` | API | `FRED_API_KEY` | Economic series; referenced by finance data source orchestrator and gold/commodity paths |
| `metals_dev` | API | `METALS_DEV_API_KEY` | Precious metals quotes |
| `edgar` | API | `EDGAR_USER_AGENT` (required by SEC) | Filings ingest |

**Related:** `api/config/commodity_registry.yaml` — keywords, FRED series ids per commodity, `metals_dev` flags for UI/API filtering.

---

## 5. RAG and knowledge enrichment

| Source | When used | Output |
|--------|-----------|--------|
| **Wikipedia REST** | `BaseRAGService.enhance_storyline_context` | Summaries/articles text in `rag_context["wikipedia"]` |
| **GDELT** | Same | Events/mentions; may write **chronological** rows |
| **DB entities** | `_get_entities_from_db` | Canonical names, aliases, Wikipedia page ids from `article_entities` / `entity_canonical` |
| **Hybrid retrieval** | `RAGRetrievalModule` | Keyword + **MiniLM** embeddings over domain articles |

---

## 6. LLM and local models

| Component | Role |
|-----------|------|
| **Ollama** (`llama3.1:8b`, `mistral:7b` per `llm_service`) | Async HTTP to `/api/generate`; global semaphore; circuit breaker `ollama` |
| **Legacy sync ML** | Some services use `modules/ml/summarization_service` (sync `requests` to Ollama) — prefer `shared.services.llm_service` for new code |

Embeddings for RAG retrieval are **local** (SentenceTransformers), not Ollama, unless you change that module.

---

## 7. External HTTP used for operations (non-news)

| Target | Usage |
|--------|--------|
| **Internet Archive (Wayback)** | Optional article body recovery (`ENABLE_WAYBACK_ENRICHMENT`) |
| **archive.today** | Optional fallback (`ENABLE_ARCHIVETODAY_ENRICHMENT`) |
| **Playwright** | Optional browser fetch (`ENABLE_BROWSER_ENRICHMENT`) |
| **Remote monitoring hosts** | SSH (`df`, `ps`) per `monitoring_devices.yaml` |

---

## 8. Candidate free / open sources (not integrated)

Curated list of reliable **no-subscription** APIs and feeds (PubMed, bioRxiv, BLS, USGS, World Bank, civic APIs, etc.): **[FREE_OPEN_DATA_SOURCES.md](./FREE_OPEN_DATA_SOURCES.md)**. Use it when planning new collectors; prefer **RSS** via `rss_feeds` where possible.

---

## 9. Related documentation

| Doc | Focus |
|-----|--------|
| [FREE_OPEN_DATA_SOURCES.md](./FREE_OPEN_DATA_SOURCES.md) | Curated free/open APIs and feeds; integration hints |
| [DATA_SOURCES_AND_COLLECTION.md](./DATA_SOURCES_AND_COLLECTION.md) | Orchestrator + automation triggers, rotation |
| [COMMODITY_DATA_SOURCES.md](./COMMODITY_DATA_SOURCES.md) | Registry, oil/gas, news filtering |
| [OFFICIAL_GOVERNMENT_FEEDS.md](./OFFICIAL_GOVERNMENT_FEEDS.md) | Government RSS URLs and rationale |
| [FINANCE_REFERENCE_SOURCES.md](./FINANCE_REFERENCE_SOURCES.md) | Finance reference material |
| [RAG_V8_AND_DISCOVERY.md](./RAG_V8_AND_DISCOVERY.md) | RAG and discovery behavior |
| [OLLAMA_SETUP.md](./OLLAMA_SETUP.md) | Local LLM setup |

---

*Last aligned with repo layout: domain `rss_feeds`, `api/config/orchestrator_governance.yaml`, `api/config/sources.yaml`, `document_collector_service`, `services/rag/base.py`. If you add a new external source, update this file and the relevant config section in the same change.*
