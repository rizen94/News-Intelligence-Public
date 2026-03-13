# Log Analysis Summary — 2026-03-07

Covers activity from **Feb 28 16:00** through **Mar 7 16:00 EST**.
Source logs: `logs/api_server.log`, `logs/activity.jsonl`, `logs/finance.log`, `logs/frontend.log`.

---

## 1. System uptime and sessions

| Session | Start | End | Duration | Notes |
|---------|-------|-----|----------|-------|
| 1 | Feb 28 ~16:00 | Mar 1 ~16:00 | ~24h | Stable. Error rate 0% except one 2% blip at 21:00. |
| 2 | Mar 1 16:00 | Mar 3 01:00 | ~33h | **Major outage.** 100% error rate for most of Mar 2. |
| 3 | Mar 3 01:00 | Mar 3 02:00 | ~1h | Brief recovery, then offline. |
| 4 | Mar 4 01:00 | Mar 4 04:00 | ~3h | Short session. Clean. |
| 5 | Mar 6 10:11 | Mar 6 10:30 | 19 min | Ollama went down; system shut down. |
| 6 | Mar 7 11:50 | ongoing | 5+ hours | **Current.** 14/14 routes healthy, 0 issues, <1% error rate. |

**Total observed uptime: ~66 hours across 8 days.** Significant gaps suggest the system was stopped or the machine was off.

---

## 2. The Mar 2 outage

From **Mar 1 15:00 to Mar 3 00:00**, error rates hit 73–100% every hour.

- **Symptom:** All API responses returned 400/404/500/503 with response times of 5–12 seconds (vs normal 114ms).
- **Root cause:** Most likely a database or network dependency failure — the request pattern (76 req/hr steady) shows the frontend polling on schedule but getting only errors back.
- **Recovery:** Error rate dropped to 0.6% by Mar 3 01:00.
- **Single worst request:** `GET /api/v4/politics/content_analysis/topics` — **942 seconds** (15+ minutes), returned 500. This was at Mar 3 00:00 during the tail of the outage.

---

## 3. Error and warning inventory

| Category | Count | Severity | Action needed |
|----------|-------|----------|---------------|
| Redis module missing (`No module named 'redis'`) | 12 | Low | Install `redis` pip package or remove Redis checks. Currently non-functional but non-blocking. |
| GPUtil missing | 12 | Low | Install `gputil` or suppress the warning. No GPU monitoring without it. |
| Ollama connection refused / timeout | 13 | **High** | Ollama (LLM) was unreachable after reboot. Entity extraction and topic extraction both fail silently. Start Ollama on boot or add it to autostart. |
| DB slow connections (1–4.3s) | ~30 | Medium | `science-tech` and `public` schemas consistently slow. May need connection pool tuning or index review. |
| DB health check timeout (>2s) | 2 | Medium | Occasional. Monitor. |
| EDGAR 404 for CIK 0000001832 | 3 | Low | Stale CIK in finance config. Remove or update. |
| `analysis_updated_at` column missing | 1 | Medium | Schema drift — `articles` table is missing this column. A migration is needed. |
| Frontend ECONNREFUSED | 61 | Info | All from periods when API was down. Expected behavior. |
| Route supervisor: 1 unhealthy route | 1 (once) | Low | Transient. Self-recovered next check. |

---

## 4. Entity extraction and topic extraction

| Metric | Value |
|--------|-------|
| Entity extractions attempted | 13 |
| Successful | 7 (54%) |
| Failed (Ollama down) | 6 (46%) |
| Articles processed for topics | 5 |
| Topics found | 0 out of 5 |

**Root cause:** Ollama was not running (connection refused on port 11434). Without the LLM, both entity extraction and topic clustering return empty results. This means new articles are ingested but never enriched.

**Fix:** Start Ollama before or alongside the API. Consider adding it to the systemd autostart.

---

## 5. RSS collection

Six collection runs are logged in the current `api_server.log`:

| Time | Articles added | Duplicates rejected | Total filtered |
|------|---------------|--------------------:|---------------:|
| Mar 6 10:13 | 0 | — | — |
| Mar 6 10:13 | 0 | — | — |
| Mar 6 10:18 | 4 | — | — |
| Mar 6 10:24 | 4 | — | — |
| Mar 6 10:29 | 3 | 426 | 750 |
| Mar 7 11:51 | 3 | — | — |

The last full breakdown (Mar 6 10:29):
- Clickbait filtered: 2
- Advertisements: 31
- Low quality (<0.4): 16
- Low impact (<0.4): 294
- Content exclusion (sports/entertainment): 407
- Duplicates: 426

**Observation:** Only 3–4 articles per run survive filtering. The low-impact filter (294 articles) is the biggest reducer. Worth reviewing whether the threshold is too aggressive.

---

## 6. API performance

### Normal operation (Mar 7 10:00+)

| Metric | Value |
|--------|-------|
| Avg response time | 127 ms |
| p95 response time | 91 ms |
| Max response time | ~13.2 s (one slow endpoint per hour) |
| Requests per hour | 690–714 |
| Error rate | 0.6% |

### Busiest endpoints (all-time)

| Rank | Endpoint | Requests |
|------|----------|----------|
| 1 | `/api/system_monitoring/status` | 2,647 |
| 2 | `/api/context_centric/status` | 1,825 |
| 3 | `/api/orchestrator/dashboard` | 1,821 |
| 4 | `/api/watchlist/alerts` | 1,495 |
| 5 | `/api/orchestrator/status` | 931 |

These are all polling endpoints hit by the frontend on timers. The top 5 account for ~8,700 of ~41,500 requests (21%).

### Slowest endpoints (single-request peaks)

| Duration | Endpoint | Status |
|----------|----------|--------|
| 942.5s | `/api/politics/content_analysis/topics` | 500 |
| 27.9s | `/api/system_monitoring/status` | 500 |
| 26.5s | `/api/context_centric/status` | 200 |
| 25.8s | `/api/articles/duplicates/stats` | 404 |
| 25.4s | `/api/tracked_events` | 200 |

The 942-second outlier was during the Mar 2 outage. The 25–27s responses suggest a connection timeout waiting for the database.

---

## 7. Finance orchestrator

All finance tasks completed successfully. Pattern: low-priority refresh cycles every ~1 minute, completing in 1–2 seconds.

| Metric | Value |
|--------|-------|
| Task types observed | `refresh`, `ingest` |
| Typical refresh duration | 1–2 seconds |
| Longest task | `ingest` at 23.3 seconds |
| Failures | 0 in observed window |

Known issues:
- `chromadb` not installed — vector store writes fail silently.
- EDGAR 404 for CIK 0000001832 (Agnico Eagle Mines, wrong CIK).

---

## 8. Route supervisor

| Session | Healthy routes | Issues per check |
|---------|---------------|------------------|
| Mar 6 | 13–14 / 14 | 5–7 (mostly slow DB) |
| Mar 7 | 14 / 14 | 0 |

Current session is fully clean.

---

## 9. Recommended improvements

### Critical (data quality impact)

1. **Start Ollama on boot.** Without it, entity extraction and topic clustering both fail. Add a systemd service or include it in the autostart script.
2. **Fix the `analysis_updated_at` migration.** The pipeline tried to update this column and failed, aborting the transaction for subsequent articles.

### High (reliability)

3. **Investigate the Mar 2 outage.** Was it a database failure, network issue, or machine shutdown? Add monitoring/alerting for DB connectivity.
4. **Review the 13-second recurring max latency.** One endpoint per hour is consistently slow (~13s). Identify which endpoint and optimize or add a timeout.

### Medium (operational)

5. **Install the `redis` Python package** or remove Redis health checks to eliminate 12+ warnings per session.
6. **Review low-impact filter threshold.** 294 articles per collection run are filtered as "low impact" — is the 0.4 cutoff too aggressive?
7. **Fix EDGAR CIK for Agnico Eagle Mines** (CIK 0000001832 returns 404).
8. **Install `chromadb`** if finance vector search is intended to work, or suppress the warning.

### Low (cleanup)

9. **Install `gputil`** or suppress the GPU warning if no GPU monitoring is needed.
10. **Log rotation.** `activity.jsonl` is 14MB and growing. Set up rotation or archival.
