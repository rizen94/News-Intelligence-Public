# NI Grafana dashboards (Homelab apply)

Committed JSON for Homelab Grafana (PopOS), scraped from Widow:

`GET /api/system_monitoring/prometheus` → `ni_*` metrics.

| File | UID | Purpose |
|------|-----|---------|
| `ni-ops-dashboard.json` | `ni-ops` | Queue depths, backlog, DB size, SLA, automation runs, content, RSS summary |
| `rss-ingestion-dashboard.json` | `ni-rss-ingestion` | RSS feeds + article create rate + collection-phase runs (`ni_*` only) |
| `alerts-embeddings-host.yaml` | — | Prometheus rules: Dockside embeddings down / paused / no progress |

## Dockside embeddings (`ni_embeddings_*`)

When `OLLAMA_EMBEDDINGS_HOST` points at Dockside (via Widow tunnel `:11435`):

| Metric | Meaning |
|--------|---------|
| `ni_embeddings_host_configured` | 1 if dedicated embed host is set |
| `ni_embeddings_host_up` | 1 if last probe/embed succeeded |
| `ni_embeddings_host_paused` | 1 when `embeddings_worker` yields (do not burn cycles) |
| `ni_embeddings_host_consecutive_failures` | Fail streak before / during pause |
| `ni_embeddings_embed_success_total` / `_fail_total` | Process-lifetime embed outcomes |
| `ni_embeddings_probe_ok_total` / `_fail_total` | Health probe outcomes |
| `ni_embeddings_worker_yield_total` | Batches skipped due to pause |
| `ni_embeddings_host_probe_latency_ms` | Last probe RTT |
| `ni_embedding_chunks_ingested{window=…}` | DB rows by `15m` / `1h` / `all` |

**Alerts:** copy `alerts-embeddings-host.yaml` into Homelab Prometheus `rule_files` (or recreate as Grafana-managed alerts). `NIEmbeddingsHostDown` / `NIEmbeddingsHostPaused` fire when Dockside drops; the worker pauses automatically so AutomationManager does not spam the tunnel.

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
