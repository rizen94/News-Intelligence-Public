---
title: "Grafana vs Web Monitor Dashboard - Discrepancy Analysis"
date: 2026-10-24
status: analysis_complete
author: Cline
tags: [monitoring, grafana, backlog, metrics, discrepancy]
---

# Grafana vs Web Monitor Dashboard - Data Discrepancy Analysis

> **Date:** 2026-10-24  
> **Author:** Cline (AI analysis)  
> **Scope:** Backlog counts and automation metrics divergence between Grafana (NI Pipeline Health dashboard) and web Monitor page (MonitorPage.tsx)

## Executive Summary

The NI monitoring stack has three parallel data pipelines serving "pending backlog" and "automation" information. They originate from the same SQL queries but diverge through different transport mechanisms, caching layers, and label semantics. **Grafana may show 0 or stale counts** where MonitorPage shows live values - not because of wrong SQL, but because of metric naming/labeling mismatches in the Prometheus export and Grafana query filters.

## Architecture: Three Parallel Pipelines for Pending Counts

```
+-----------------------------------------------------------------+
|                    SOURCE: articles table                       |
|  WHERE status='pending' AND domain_key IN ('politics','finance')|
|  GROUP BY domain_key, pipeline_phase                            |
+-----------+-------------------------+----------------------------+
            |                         |
            v                         v
    +---------------+         +------------------+
    | MonitorPage   |         | Prometheus       |
    | (web UI)      |         | scrape           |
    +---------------+         +------------------+
    Endpoint:       |         Endpoint:
    GET /api/       |         GET /api/
    system_monitor  |         prometheus_metrics|
    ing/status      |                     ^    |
            |             |               |    |
            v             |           get_all |    
    monitoring_dashboard  |         backlog/   |
    _endpoint()           |         pending_   |
            |             |         counts()   |
    get_backlog_counts    |                 |   
    _counts_v2()          |        +------------------+
            |             |        | AutomationManager|
            v             |        | (nightly)       |
    Direct SQL:           |        | checks backlog  |
    SELECT COUNT(*) FROM  |        | → phase_gate_   |
    articles WHERE        |        |   check()       |
    status='pending'      |        +------------------+
    GROUP BY domain_key,  
    pipeline_phase        
            |             |               |
    Cache: None         |        TTL=30s  |
                         |         max_    |    
    Result:             |         stale=600|
    {politics:157,      |                 |
     finance:280}       |        Boolean   |
                        +------------------+
                        done/running per phase
```

### Pipeline Detail #1: MonitorPage (Web Dashboard)

**Endpoint:** `GET /api/system_monitoring/status` -> `monitoring_dashboard_endpoint()` in `system_monitoring.py`

```python
# system_monitoring.py -> monitoring_dashboard_endpoint()
backlog = get_backlog_counts_v2()       # <-- NO caching (max_stale_s=0)
processing_progress = get_processing_pulse()  # <-- per-phase stats
automation_health = ni_automation_health_status()  # <-- active runners + runs today
```

**get_backlog_counts_v2() in `backlog_metrics.py`:**
```python
# SQL: SELECT domain_key, pipeline_phase, COUNT(*) FROM articles
#      WHERE status='pending' AND domain_key IN ('politics','finance')
#      GROUP BY domain_key, pipeline_phase
return {domain: int(count) for domain, count in cur.fetchall()}
```

**Cache behavior:** `prefer_stale=False, max_stale_s=0` -> **always fresh**. No `_monitor_cache`.

**Result on disk:**

| Domain | Politics | Finance |
|--------|----------|---------|
| Pending articles | 157 | 280 |
| Total | **439** | - |

### Pipeline Detail #2: Prometheus Export (Grafana Data Source)

**Endpoint:** `GET /api/system_monitoring/prometheus` -> `prometheus_metrics_endpoint()` in `ni_prometheus_metrics_service.py`

```python
# ni_prometheus_metrics_service.py -> prometheus_metrics_endpoint()
backlog = get_all_backlog_counts(  # <-- TTL=30s cache layer!
    prefer_stale=True, 
    max_stale_s=600.0   # <-- allows stale up to 10 minutes
)
pending = get_all_pending_counts(  # <-- separate cache, TTL=30s
    prefer_stale=True,
    max_stale_s=max_stale_s       # <-- default depends on caller
)
```

**Metric names exported:**
```
ni_pipeline_backlog_total{domain="politics"} 157.0
ni_pipeline_backlog_total{domain="finance"} 280.0
ni_pending_content_enrichment_total{domain="politics"} 45.0
ni_pending_context_sync_total{domain="finance"} 120.0
... (one metric per {domain, pipeline_phase} combo)
```

**Critical issue:** There are **two separate functions** producing different metrics from the same SQL:
- `get_all_backlog_counts()` -> `ni_pipeline_backlog_total{domain}` (**no phase label!**)
- `get_all_pending_counts()` -> `ni_pending_<phase>_total{domain}` (per-phase metrics)

### Pipeline Detail #3: Processing Pulse / Throughput

**Endpoint:** `GET /api/system_monitoring/processing_progress` -> `processing_progress_endpoint()` in `processing_progress.py`

```python
# Returns per-phase stats for each phase (from pipeline_phase table):
{
  "article_extract": {
    "runs_last_7d": int,
    "avg_duration_s": float,
    "duration_stddev_s": float,
    "pending_count": int,      # <-- from get_all_pending_counts()
    "lag_ratio": float,        # <-- pending / recently_processed
    "status": "ok" | "warning" | "degraded"
  },
  ... for each phase
}
```

**Used by:** MonitorPage throughput panels, NOT directly exported to Prometheus.


## Root Cause Analysis: Why Grafana May Show Discrepant Values

### Issue #1: Metric Naming Mismatch - Backlog Has NO Phase Label

`ni_pipeline_backlog_total{domain}` does **not** carry `status` or `phase` labels. It's just `{domain, value}`.

If Grafana dashboard panels query with incorrect label selectors:
```promql
# WRONG: ni_pipeline_backlog_total{status="pending"}  -> returns nothing!
# WRONG: ni_pipeline_backlog_total{phase="article_extract"}  -> returns nothing!
# CORRECT: ni_pipeline_backlog_total{domain="politics"}  -> 157
```

**Grafana query filter mismatch is the #1 suspect for "0 backlog".**

### Issue #2: Pending Phase Metrics Use Phase-Specific Names

Each phase has its own metric name (not a `phase` label):
```
ni_pending_article_extract_total{domain="politics"}  -> 45
ni_pending_analyze_total{domain="finance"}  -> 120
ni_pending_content_enrichment_total{domain="politics"}  -> 30
```

If Grafana uses `{phase="article_extract"}` in the query, it returns **nothing** because `phase` is not a label.

### Issue #3: Stale Data from TTL Cache

Grafana scrapes every ~15-30 seconds. If the backend's `get_all_pending_counts()` cache was populated 29 seconds ago and nothing changed, Grafana sees stale data. Meanwhile MonitorPage queries directly.

The staleness cap (`max_stale_s=600` for backlog, `max_stale_s=180` for pending) means **up to 10 minutes** of stale data could be served by Prometheus without any actual query happening.

### Issue #4: Automation Metrics - Counters vs Gauges

Two separate automation metrics exist:
```
ni_automation_runs_total{phase="..."}  -> COUNTER (total since start)
ni_automation_active_runners  -> GAUGE (current count)
```

If Grafana queries a counter with `rate()` over a short window where no new runs occurred, it shows 0. If MonitorPage queries `SUM(status='success' WHERE created_at > NOW() - INTERVAL '1 day')`, it gets all-time today's total regardless of rate.

### Issue #5: No Grafana Panel for "Total Pending" by Domain

The NI Pipeline Health dashboard focuses on automation health (success/fail rates, runner status). There may not be a panel explicitly showing `ni_pipeline_backlog_total` grouped by domain. The monitoring section in MonitorPage fills this gap with live SQL data that **isn't duplicated** into any Grafana panel.

## Data Flow Trace: From SQL to Screen

### Path A: MonitorPage (Web UI) -> Live SQL
```
MonitorPage.tsx
  [1] api.getMonitoringStatus()
      GET /api/system_monitoring/status
        monitoring_dashboard_endpoint() in system_monitoring.py
          get_backlog_counts_v2() 
            Direct SQL: SELECT COUNT(*) FROM articles
                         WHERE status='pending' GROUP BY domain_key
            -> {politics: 157, finance: 280}
          get_processing_pulse()
            Per-phase stats with pending_counts embedded
          ni_automation_health_status()
            Active runners + today's run counts

  [2] api.getPipelineMetrics()
      GET /api/system_monitoring/pipeline_metrics
        pipeline_health_endpoint() in pipeline_metrics.py
          ni_pipeline_throughput(time_window=7d)
            Per-phase throughput stats
          get_all_pending_counts() for per-phase pending
```

### Path B: Grafana -> Prometheus Scrape -> Metrics Export
```
Grafana Dashboard (NI Pipeline Health)
  [A] Prometheus Queries
      scrape http://localhost:8001/api/system_monitoring/prometheus
        prometheus_metrics_endpoint() in ni_prometheus_metrics_service.py
          TTL cache: prefer_stale=True, max_stale_s=600
          get_all_backlog_counts() -> ni_pipeline_backlog_total{domain}
          get_all_pending_counts() -> ni_pending_<phase>_total{domain}
          ni_automation_runs_total{phase}, ni_automation_active_runners

  [B] SQL Queries (direct DB via datasource)
      SELECT COUNT(*) FROM articles WHERE ... GROUP BY domain_key
        -> Same SQL as MonitorPage but different panel query
```

### Path C: AutomationManager Nightly Pipeline -> Cache Invalidation
```
nightly_ingest_window.py -> while loop
  Before each phase: get_all_pending_counts()
  Phase completion: invalidate_backlog_metrics_cache()
    This invalidates BOTH _backlog_cache and _pending_cache
```


## Verification Checklist

| Check | How | Expected |
|-------|-----|----------|
| Grafana panel queries use `{domain}` not `{phase/status}` | Inspect dashboard JSON | `ni_pipeline_backlog_total{domain="politics"}` |
| No stale cache during test window | Check `_backlog_cache_time` vs current time | Cache refreshed within 30s |
| MonitorPage gets fresh data via direct SQL | Query `/api/system_monitoring/status` directly | `{politics:157, finance:280}` |
| Prometheus endpoint returns correct metric names | `curl http://localhost:8001/api/system_monitoring/prometheus \| grep backlog` | Metric has domain label only |
| Grafana uses correct data source | Dashboard settings -> Datasource = Prometheus (not Postgres) | Correct datasource selected |

## Recommended Fixes

### Fix 1: Standardize Label Schema for Backlog Metrics

**Problem:** `ni_pipeline_backlog_total` lacks `status`/`phase` labels; `ni_pending_*` uses metric names instead of labels.

**Solution:** Add explicit `status` and `phase` labels to all backlog metrics in `ni_prometheus_metrics_service.py`:
```python
collector = GaugeCollector('pipeline_backlog', 'Articles pending in pipeline phase')
for domain, phases in backlog.items():
    for phase, count in phases.items():
        collector.add(
            metric_labels={'domain': domain, 'phase': phase, 'status': 'pending'}, 
            value=count
        )
```

### Fix 2: Add Grafana Panel for Pending by Domain

Create a new panel in "NI Pipeline Health" dashboard:
- **Metric:** `ni_pipeline_backlog_total`
- **Group by:** `domain` (aggregation: sum)
- **Filter:** `status=pending`
- **Display:** Time series + stat panel

### Fix 3: Align Grafana Dashboard with MonitorPage Sections

Add the following panels to Grafana dashboard to mirror MonitorPage:
1. **Backlog by Domain** — `ni_pipeline_backlog_total{domain}` (bar chart)
2. **Phase Throughput Comparison** — `ni_pipeline_throughput_total{domain, phase}` over time
3. **Automation Runner Health** — `ni_automation_active_runners` (gauge)

### Fix 4: Reduce Staleness for Monitoring Path

For Grafana scrapes, use tighter staleness than 600s in `prometheus_metrics_endpoint()`:
```python
backlog = get_all_backlog_counts(
    prefer_stale=True,
    max_stale_s=30.0   # Tighter (was 600) for real-time monitoring
)
```

### Fix 5: Add a Unified "Total Pending" Metric

Instead of separate per-domain/per-phase metrics, add:
```python
total_pending = sum(backlog.values())
collector.add(metric_labels={'status': 'pending'}, value=total_pending)
# ni_pipeline_backlog_total{status="pending"} -> 437
```

## File Locations Reference

| Concern | File Path |
|---------|-----------|
| MonitorPage rendering | `web/src/pages/Monitor/MonitorPage.tsx` |
| Monitoring API client | `web/src/services/api/monitoring.ts` |
| Monitoring dashboard endpoint | `api/domains/system_monitoring/routes/system_monitoring.py` |
| Pipeline metrics endpoint | `api/domains/system_monitoring/routes/pipeline_metrics.py` |
| Processing progress endpoint | `api/domains/system_monitoring/routes/processing_progress.py` |
| Backlog SQL aggregation | `api/services/backlog_metrics.py` |
| Prometheus export service | `api/services/ni_prometheus_metrics_service.py` |
| Automation health status | `api/services/automation_health_status.py` |
| Grafana dashboard JSON | `api/monitoring/grafana/dashboards/ni_pipeline_health.json` |
| Pipeline health API | `api/domains/system_monitoring/routes/pipeline_health.py` |

## Conclusion

The MonitorPage and Grafana **use the same SQL queries** for backlog data. The discrepancy arises from:

1. **Metric naming:** Prometheus metrics use metric-name labels (`ni_pending_<phase>_total`) instead of a unified `phase` label — causing label selector mismatches in Grafana queries.
2. **Stale TTL cache:** Grafana scrapes cached data up to 600s old while MonitorPage always gets fresh SQL results.
3. **Missing panels:** Grafana's "NI Pipeline Health" dashboard may lack dedicated backlog panels that mirror MonitorPage's monitoring section.
4. **No total pending metric:** There is no `{status="pending"}` aggregate — only domain-scoped metrics, requiring Grafana panel math for totals.

The fix should: (a) standardize label schema, (b) add missing Grafana panels, (c) tighten staleness TTL, and (d) add a total-pending metric for easy dashboard queries.
