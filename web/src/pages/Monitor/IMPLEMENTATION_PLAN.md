---
title: "Grafana-Monitor Dashboard Discrepancy - Implementation Plan"
date: 2026-10-24
status: pending_review
author: Cline
tags: [implementation, monitoring, grafana, backlog]
related: docs/MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md
---

# Implementation Plan: Grafana-Monitor Dashboard Discrepancy Resolution

## Priority: High (fix #1) — Standardize Label Schema

### Scope: `api/services/ni_prometheus_metrics_service.py`

**Current state:** Metrics use metric-name labels (`ni_pending_article_extract_total`) instead of unified labels.

**Required change in `prometheus_metrics_endpoint()`:**
```python
# BEFORE (current):
for domain, phases in pending.items():
    for phase, count in phases.items():
        collector.add(metric_labels={'domain': domain}, value=count, metric_name=f"pending_{phase}_total")

# AFTER (fixed):
for domain, phases in pending.items():
    for phase, count in phases.items():
        collector.add(
            metric_labels={'domain': domain, 'phase': phase, 'status': 'pending'},
            value=count,
            metric_name='pipeline_backlog_total'  # unified metric name
        )

# Also add total pending:
total = sum(sum(p.values()) for p in pending.values())
collector.add(
    metric_labels={'status': 'pending'},
    value=total,
    metric_name='pipeline_backlog_total'
)
```

### Priority #2 — Tighten Staleness TTL

**Scope: `api/services/ni_prometheus_metrics_service.py`**

In `prometheus_metrics_endpoint()`, change:
```python
# BEFORE:
backlog = get_all_backlog_counts(prefer_stale=True, max_stale_s=600.0)
pending = get_all_pending_counts(prefer_stale=True, max_stale_s=max_stale_s or 180.0)

# AFTER:
backlog = get_all_backlog_counts(prefer_stale=True, max_stale_s=30.0)
pending = get_all_pending_counts(prefer_stale=True, max_stale_s=30.0)
```

### Priority #3 — Add Grafana Panels (manual in Grafana UI)

1. **Backlog by Domain** panel:
   - Query: `sum(ni_pipeline_backlog_total) by (domain)`
   - Display: Bar chart, legend as value
2. **Phase Throughput Over Time**:
   - Query: `rate(ni_pipeline_throughput_total[1h])` filtered by domain/phase
3. **Active Runners Gauge**:
   - Query: `ni_automation_active_runners`

### Priority #4 — Verify Grafana Data Source Configuration

Check that the "NI Pipeline Health" dashboard uses Prometheus (not direct Postgres) as its primary datasource for metric queries. If it uses Postgres directly, verify the SQL query matches `get_backlog_counts_v2()`.

## Testing Plan

1. Run `curl http://localhost:8001/api/system_monitoring/prometheus | grep pipeline_backlog` to verify new labels
2. Update Grafana dashboard with corrected queries
3. Compare MonitorPage output vs Grafana panels at same time window
4. Verify staleness < 30s by checking `_backlog_cache_time` in logs

## Rollback Plan

If Prometheus metric changes break existing dashboards:
1. Revert `ni_prometheus_metrics_service.py` changes
2. Keep both old and new metrics during transition (temporary dual-metric)
