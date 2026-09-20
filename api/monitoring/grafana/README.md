# NI Grafana dashboards (Homelab apply)

Committed JSON for Homelab Grafana (PopOS), scraped from Widow:

`GET /api/system_monitoring/prometheus` → `ni_*` metrics.

| File | UID | Purpose |
|------|-----|---------|
| `ni-ops-dashboard.json` | `ni-ops` | Queue depths, backlog, DB size, SLA, automation runs, content, RSS summary |
| `rss-ingestion-dashboard.json` | `ni-rss-ingestion` | RSS feeds + article create rate + collection-phase runs (`ni_*` only) |

## Apply on PopOS (Homelab)

Cloud agents typically cannot reach PopOS Grafana. On the Homelab host:

1. Confirm Prometheus scrapes Widow NI API (job often `news-intelligence-api` / `widow-ni-api`):
   - Target URL: `https://news-intelligence-ag.duckdns.org/api/system_monitoring/prometheus` (or LAN equivalent)
   - Optional header: `X-NI-Scrape-Token: $NI_PROMETHEUS_SCRAPE_TOKEN` if set on the API
2. Import dashboards:
   - Grafana → Dashboards → Import → upload each JSON (or copy from this directory after `git pull` on Widow / sync to PopOS)
   - Select the Homelab Prometheus datasource when prompted (`${datasource}` placeholder)
3. Point Monitor deep link at the NI Ops dashboard, e.g.:
   - `VITE_NEWS_INTEL_GRAFANA_URL=https://<homelab-grafana>/d/ni-ops/news-intelligence-ops`
   - Or browser `localStorage.setItem('news_intel_grafana_url', '…')`

## Env (Widow API)

| Variable | Default | Meaning |
|----------|---------|---------|
| `NI_PROMETHEUS_METRICS_ENABLED` | `true` | Serve `/prometheus` |
| `NI_PROMETHEUS_METRICS_CACHE_SECONDS` | `60` | Cache TTL (min 30) |
| `NI_PROMETHEUS_SCRAPE_TOKEN` | empty | Optional bearer via `X-NI-Scrape-Token` |

GPU / host charts need node_exporter or DCGM on Widow — not exported by this endpoint.
