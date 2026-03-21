# Data Sources and Collection

How the system uses each data source and what runs routinely.

**Full source inventory:** [SOURCES_AND_EXPECTED_USAGE.md](./SOURCES_AND_EXPECTED_USAGE.md) (all sources and expected usages in one place).

## Sources in routine use

| Source | Used by | What runs | Feeds into |
|--------|--------|-----------|------------|
| **RSS** | OrchestratorCoordinator + AutomationManager | `collect_rss_feeds()` from `politics.rss_feeds`, `finance.rss_feeds`, `science_tech.rss_feeds` | Domain articles → context_sync → intelligence.contexts → event_tracking → investigation reports |
| **Gold** | OrchestratorCoordinator | FinanceOrchestrator refresh (topic=gold): gold_amalgamator (metals.dev, freegoldapi, FRED index) | Finance evidence, commodity dashboards, gold history/spot API |
| **Silver** | OrchestratorCoordinator | FinanceOrchestrator refresh (topic=silver): commodity_fetcher | Commodity dashboards |
| **Platinum** | OrchestratorCoordinator | FinanceOrchestrator refresh (topic=platinum): commodity_fetcher | Commodity dashboards |
| **EDGAR** | OrchestratorCoordinator | FinanceOrchestrator refresh (topic=edgar): 10-K ingest, vector store | Finance evidence, analysis |

## How collection is triggered

- **OrchestratorCoordinator** (started in `main_v4` lifespan): Every ~60s it asks CollectionGovernor for the next source to run (rss, gold, silver, platinum, edgar). Whichever source has waited longest since its last run (within min/max interval) gets run. So all five sources rotate.
- **AutomationManager** (background thread): Runs scheduled tasks including `rss_processing` (hourly), which calls `collect_rss_feeds()` so **the same domain RSS feeds** are used. Other tasks: context_sync, event_tracking, claim_extraction, investigation_report_refresh, etc.

## Configuration

- **Collection sources and order**: `api/config/orchestrator_governance.yaml` → `collection.sources`. Add or remove `source_id` / `handler` / `topic` to change what the coordinator runs.
- **RSS feeds**: Stored per domain in `politics.rss_feeds`, `finance.rss_feeds`, `science_tech.rss_feeds`. Migration 128 adds SEC/Fed/Treasury/FDIC for finance; migration 148 adds Kitco, Mining.com, Reuters, MarketWatch, Bloomberg, Yahoo Finance. Manage via API or migrations; active feeds (`is_active = true`) are used by `collect_rss_feeds()`.
- **News orchestrator**: For finance analysis, the evidence collector uses the news orchestrator (`domains.finance.news_orchestrator`) to build a topic-relevant shortlist from finance articles and intelligence.contexts, so the LLM gets ranked news/disclosures in addition to price data.
- **Finance topics**: Gold/silver/platinum/edgar are passed as `topic` to FinanceOrchestrator.refresh(). FRED is used inside gold (amalgamator) and can also be run as a standalone topic via the finance API.

## Optional / on-demand

- **FRED** (standalone series): Not in the default collection rotation. Trigger via `POST /{domain}/finance/fetch-fred` or submit a refresh task with `topic: fred`.
- **Legacy RSS table**: `services.rss` (BaseRSSService) uses a single `rss_feeds` table (e.g. public). The canonical feeds are in domain schemas; automation and coordinator both use `collect_rss_feeds()` and domain tables.
