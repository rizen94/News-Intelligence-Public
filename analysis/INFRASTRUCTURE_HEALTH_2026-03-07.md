# Infrastructure Health Report — 2026-03-07 12:20 EST

## Server resources

| Resource | Value | Status |
|----------|-------|--------|
| CPU | 20 cores, load avg 13.5 | OK (62% sys — elevated but not critical) |
| Memory | 30 GB used / 62 GB total (49%) | OK |
| Swap | 0 B used / 20 GB | OK |
| Disk | 676 GB / 907 GB (79%) | Watch — approaching 80% |
| Uptime | 42 minutes (recent reboot) | |

## Process inventory

| Process | PID | Memory | Status |
|---------|-----|--------|--------|
| API (uvicorn) | 189505 | 1.5 GB | Running, port 8000 |
| Ollama | 7065 | — | Running, port 11434 (system service, enabled at boot) |
| Frontend (Vite) | — | — | Running, port 3000 (systemd user service) |

## Network connectivity

| Service | Target | Status | Latency |
|---------|--------|--------|---------|
| PostgreSQL | 192.168.93.101:5432 | Connected | 0.5ms avg |
| Ollama | localhost:11434 | Connected | <1ms |
| Redis | localhost:6379 | **Not installed** | N/A |

## Database

| Metric | Value |
|--------|-------|
| DB size | 80 MB |
| Active connections | 1 |
| Idle connections | 3 |
| Total connections | 4 of 60 max |
| Longest idle connection | 1774s (~30 min) |
| Connection acquire time | 13ms |

### Largest tables

| Table | Size | Rows |
|-------|------|------|
| politics.articles | 20 MB | 8,270 |
| politics.topic_keywords | 7.4 MB | 30,024 |
| politics.article_entities | 4.6 MB | 9,169 |
| politics.topic_clusters | 3.5 MB | 12,954 |
| public.articles | 2.6 MB | 1,312 |
| science_tech.articles | 2.0 MB | 970 |
| finance.articles | — | 200 |

### Schema table counts

| Schema | Tables |
|--------|--------|
| public | 87 |
| finance | 21 |
| science_tech | 18 |
| politics | 18 |
| intelligence | 16 |
| orchestration | 8 |

### Index health (politics.articles)

Before migration 147: 35 indexes (25 with zero scans ever).
After migration 147: **10 indexes** — all actively used.

New index added: `finance.article_topic_clusters(article_id)` — was doing 531 sequential scans.

## Mar 2 outage root cause analysis

**Timeline:**
- Mar 1 15:00: Error rate spikes to 30%, rises to 100% by 16:00
- Mar 1 20:38-20:40: Two git commits deployed (`v4.1.0 Widow migration`, `consolidate docs`)
- Mar 2 02:00-16:00: Sustained 100% error rate, 76 requests/hour from frontend polling
- Mar 2 17:00: User activity resumes, request volume spikes to 2,334/hour
- Mar 3 01:00: System recovers, error rate drops to <1%

**Error breakdown (9,574 errors total on Mar 2):**
- 500 Internal Server Error: 5,392 (56%) — system_monitoring/status, logs, dashboard
- 400 Bad Request: 2,118 (22%) — domain routes returning 400 (URL routing issue with /api/v4/ prefix)
- 503 Service Unavailable: 1,283 (13%) — watchlist/alerts
- 404 Not Found: 781 (8%) — duplicates/stats endpoint missing

**Root cause:** The `v4.1.0 Widow migration` commit at 20:38 on Mar 1 likely changed backend route handling while the frontend was still using `/api/v4/` prefixed URLs. The 400 errors on domain routes (`/api/v4/politics/articles`) confirm a URL mismatch. The 500 errors on system_monitoring suggest the database was also slow or temporarily unreachable during the migration. Recovery at Mar 3 01:00 likely coincided with a manual restart or cache refresh.

**Prevention:** The request timeout middleware (added today) would have returned fast 504s instead of letting requests hang for 20-942 seconds.

## Ollama models available

| Model | Size | Purpose |
|-------|------|---------|
| nomic-embed-text:latest | 274 MB | Embeddings |
| llama3.1:405b | 243 GB | Large analysis (likely not loaded in VRAM) |
| (other models) | — | Check `ollama list` for full inventory |
