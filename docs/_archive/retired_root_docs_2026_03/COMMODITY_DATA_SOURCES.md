# Commodity data sources and ingestion

Commodity tracking (dashboard, news, price) is driven by the **commodity registry** and shared finance ingestion.

## Registry

- **Config:** `api/config/commodity_registry.yaml`
- **Ids:** gold, silver, platinum, oil, gas (and any added via YAML)
- **Per commodity:** topic_keywords, financial_signals, non_financial_exclude, unit, metals_dev, fred_series_id
- **FRED:** Series ID from registry `fred_series_id` or env `FRED_{COMMODITY_ID}_SERIES_ID`. Oil defaults to **DCOILWTICO** (WTI); gas defaults to **DHHNGSP** (Henry Hub). Override env when you want Brent or another series.

## Price data

- **Metals (gold, silver, platinum):** FRED (from registry/env) and optionally metals.dev; gold also uses the gold amalgamator.
- **Oil / gas:** **FRED only** (metals.dev does not cover these). Defaults are set in `commodity_registry.yaml`; require `FRED_API_KEY`. Optional env `FRED_OIL_SERIES_ID` / `FRED_GAS_SERIES_ID` overrides the registry series.

### Manual / scheduled collection

- **API:** `POST /api/{domain}/finance/commodity/{commodity}/fetch?days=365` (e.g. domain `finance`, commodity `oil`) — pulls the window and **persists** (FRED `store`, or gold amalgamator). Use after changing series ids or to backfill oil/gas.
- **UI:** Finance commodity dashboard — **Fetch FRED prices** (oil/gas) or **Refresh price store** (metals).
- **Orchestrator:** `orchestrator_governance.yaml` → `collection.sources` includes `oil` and `gas` (same finance refresh handler as silver/platinum) so the coordinator can refresh FRED on its interval.

## News and supply-chain

- **Source:** Finance-domain **RSS articles** and **intelligence contexts** (see finance pipeline and orchestrator governance).
- **Relevance:** News orchestrator and supply-chain endpoint filter by registry topic_keywords, financial_signals, and non_financial_exclude so only financial-commodity content is returned. This applies to all registry commodities, including oil and gas.
- **Ingestion:** No change required for oil/gas; existing finance RSS and context pipelines already ingest content. Energy/commodity-focused feeds (e.g. from finance or general business) will surface oil/gas headlines; the commodity news API and dashboard then filter by the registry rules. To improve oil/gas coverage, add or tag energy-focused feeds in the finance domain (e.g. in `rss_feeds` or collection config).

## Event and geo data

- **Tracked events:** `intelligence.tracked_events` with `domain_keys` containing `finance`. Geo and regulatory endpoints filter by commodity using the same registry relevance (topic + word-boundary). Oil/gas events will appear when event discovery produces events whose name/scope match the oil/gas topic keywords.
