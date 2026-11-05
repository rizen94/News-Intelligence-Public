# Work Management System — Design Specification

**Created**: 2026-10-30  
**Status**: Design draft  
**Author**: Cline (AI agent)  
**Sources**: TROUBLESHOOTING.md, BACKLOG_STATUS_ANALYSIS.md, PIPELINE_STATE_MACHINE.md, pending-items-triage.md, HOUSEKEEPING_BACKLOG.md, MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md

---

## Executive Summary

The News Intelligence pipeline currently suffers from **no unified work management**: backlog items accumulate untracked across multiple systems (Prometheus metrics, MonitorsPage live SQL, file-based TODO docs), stale data masks the true state of the system (996K+ dead suggestions, 432 backlog iterations on a 36-day ETA), and monitoring displays divergent views because three parallel data pipelines serve pending counts through different transport mechanisms with incompatible label schemas.

This design proposes a **Work Management System** that consolidates all work tracking into a single database-backed source of truth, unifies monitoring metrics, eliminates dead item accumulation, and provides both programmatic and visual visibility into work status by domain, priority, and age.

---

## Problem Statement (from documented evidence)

### P1: Massive Pending Item Accumulation (996K+ items)
- `STORYLINE_AUTOMATION_AUTO_ATTACH=0` killswitch blocks auto-commit path
- All items routed to `_store_suggestions()` -> inserted with `status='pending'`
- **No worker, cron, or endpoint** processes pending suggestions ever
- 996K+ items in `storyline_article_suggestions.pending`; ~615K expired past TTL
- No cleanup mechanism exists

### P2: Enrichment Backlog Starvation (90K+ pending)
- Theoretical rate: 700/hr; actual rate: ~114/hr due to statement timeouts
- `AUTOMATION_QUEUE_SOFT_CAP=100` prevents most phases from enqueueing when cap reached
- Net throughput drops below RSS inflow -> backlog grows despite active processing
- 432 backlog iterations beyond baseline threshold; **NOT in steady state**

### P3: Monitoring Data Divergence (Grafana vs MonitorPage)
- MonitorPage queries live SQL (no cache, max_stale_s=0)
- Grafana scrapes Prometheus metrics with TTL=30s + stale cache up to 600s (10 min)
- `ni_pipeline_backlog_total` missing `phase` and `status` labels -> Grafana queries return nothing
- `ni_pending_<phase>_total` uses metric-name-based labels instead of a unified `phase` label
- No "total pending" aggregate metric exists

### P4: Housekeeping Debt (untracked, unprioritized)
- Two archive layers (`_archive/` + `archive/`) with nested sub-directories
- Empty `docs/generated/` directory serving no purpose
- Orphaned `=NN.N` version marker files on production
- No ADRs or CHANGELOG exist
- Dev/prod path drift (PopOS vs Widow) without verification

### P5: Legacy Schema References (orphaned tables)
- Code references non-existent `items` and `pipeline_state` tables
- Legacy state terms (`queued`, `dead`, `done`, `resolved`) still in migration plan but no migration executed
- `topic_clustering` migration failure causes Monitor page to show "down"

---

## Design Goals

| Goal | How It's Measured |
|------|------------------|
| **Single source of truth** | All backlog counts from one query, served to both MonitorPage and Grafana |
| **No dead items** | All pending items have an expiry + a cleanup cron; TTL enforcement < 1 hour stale |
| **Accurate throughput** | Reported enrichment rate matches actual articles enriched per hour (from logs, not theoretical) |
| **Unified metrics schema** | One metric name with `phase` and `status` labels instead of per-phase metric names |
| **Tracked housekeeping** | All cleanup tasks in a single prioritized backlog with status tracking |
| **No stale monitoring** | Grafana staleness TTL <= 30s; no prefer_stale for monitoring dashboards |

---

## Architecture Overview

```
+-----------------------------------------------------------------+
|                    WORK MANAGEMENT SYSTEM                       |
|                                                                 |
|  +--------------+   +--------------+   +----------------+      |
|  | Work Items   |   | Pipeline     |   | Monitoring     |      |
|  | Table        |   | State Table  |   | Dashboard      |      |
|  | (new table)  |   | (existing    |   | (Monitor +     |      |
|  |              |   |  articles)   |   | Grafana)       |      |
|  +------+-------+   +------+-------+   +-------+--------+      |
|         |                  |                   |               |
|         v                  v                   v               |
|  +----------------------------------------------------------+  |
|  |           WORK MANAGER SERVICE (new)                     |  |
|  |                                                          |  |
|  |  * work_item_lifecycle()     // manage priorities        |  |
|  |  * backlog_unification()     // single query             |  |
|  |  * ttl_enforcement()         // cleanup dead items       |  |
|  |  * state_compliance_check()  // validate transitions     |  |
|  |  * metrics_normalization()   // unified schema           |  |
|  +---------------------------+------------------------------+  |
|                               |                                |
|              +----------------+-----------------+             |
|              v                                   v             |
|  +------------------+        +-----------------------------+  |
|  | API Endpoint      |        | Prometheus Exporter        |  |
|  | GET /api/work/    |        | /api/system_monitoring     |  |
|  | backlog            |        | prometheus (updated)       |  |
|  | status             |        |                            |  |
|  +------------------+        +-----------------------------+  |
+-----------------------------------------------------------------+
```

### Key Design Principle

**One query, multiple consumers.** The backlog count query (`SELECT domain_key, pipeline_phase, COUNT(*) FROM articles WHERE status='pending' GROUP BY domain_key, pipeline_phase`) runs once per scrape and feeds both the REST API endpoint (for MonitorPage) and the Prometheus metrics export (for Grafana). No separate caching layers with different staleness settings.

---

## Component 1: Work Items Table (New)

### Purpose
Replace file-based TODO/housekeeping docs with a persistent, queryable, prioritized work tracking table.

### Schema

```sql
CREATE TABLE IF NOT EXISTS work_items (
    id          SERIAL PRIMARY KEY,
    priority    VARCHAR(10) NOT NULL CHECK (priority IN ('P0','P1','P2','P3')),
    category    VARCHAR(50) NOT NULL,  -- 'pipeline_bug', 'monitoring_fix', 'housekeeping', 'tech_debt', 'feature'
    title       VARCHAR(255) NOT NULL,
    description TEXT,                    -- detailed steps, references, affected files
    status      VARCHAR(20) NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','in_progress','blocked','done','abandoned')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    source_file VARCHAR(500),             -- where this was discovered/recorded
    related_tables JSONB,                 -- ['articles', 'rss_feeds', 'storyline_article_suggestions']
    effort_est  VARCHAR(10),              -- 's', 'm', 'l', 'xl'
    tags        TEXT[] DEFAULT '{}'.       -- for ad-hoc filtering
    
    UNIQUE(priority, category, title)     -- prevent duplicate entries
);

CREATE INDEX idx_work_items_status ON work_items(status);
CREATE INDEX idx_work_items_priority ON work_items(priority DESC, created_at ASC);
```

### Initial Population (from documented findings)

```sql
INSERT INTO work_items (priority, category, title, description, status, source_file, effort_est, tags) VALUES
-- P0 items
('P0', 'pipeline_bug', 'Clean 996K stale storyline suggestions', 
 'storyline_article_suggestions has no cleanup mechanism. Add TTL cron + optional purge endpoint.', 
 'open', 'docs/pending-items-triage.md', 's', ARRAY['urgent','storage']),

('P0', 'monitoring_fix', 'Fix metric label schema for Grafana queries',
 'ni_pipeline_backlog_total missing phase/status labels. ni_pending_* uses per-phase metric names instead of unified phase label.',
 'open', 'docs/MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md', 's', ARRAY['grafana','metrics']),

('P0', 'pipeline_bug', 'Restore MonitorPage health',
 'Topic clustering migration failure causes missing column errors. Re-run migrations or add try/except for missing columns.',
 'open', 'docs/TROUBLESHOOTING.md', 'm', ARRAY['monitor','database']),

-- P1 items
('P1', 'tech_debt', 'Implement TTL cleanup cron for all pending tables',
 'Create a single cron that purges expired items from storyline_article_suggestions and any other pending-suspended table.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 's', ARRAY['housekeeping']),

('P1', 'monitoring_fix', 'Add unified total_pending metric',
 'ni_pipeline_backlog_total{status="pending"} = sum of all domain backlog counts. Enables easy Grafana queries without panel math.',
 'open', 'docs/MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md', 's', ARRAY['grafana']),

('P1', 'tech_debt', 'Consolidate archive layers (_archive/ + archive/)',
 'Move all _archive/ contents into archive/ with date-ordered naming; delete empty _archive/ directory.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 's', ARRAY['housekeeping']),

('P1', 'tech_debt', 'Clean up docs/generated/ and orphaned =NN.N files',
 'Delete empty docs/generated/. Identify and remove stale version markers on Widow.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 's', ARRAY['housekeeping']),

-- P2 items
('P2', 'tech_debt', 'Create ADR.md with initial architecture decisions',
 'Document bare-metal migration, AutomationManager design, per-domain schema silo pattern, Caddy+nginx HTTPS.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 'm', ARRAY['documentation']),

('P2', 'tech_debt', 'Create CHANGELOG.md with semver-compatible format',
 'Add Unreleased section at top; date-stamped entries by category (Added, Changed, Fixed, Removed).',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 's', ARRAY['documentation']),

('P2', 'pipeline_bug', 'Fix TimelineBuilderService domain-scoping',
 'TimelineBuilderService queries chronological_events without schema prefix. Pass domain/schema into service.',
 'open', 'docs/TROUBLESHOOTING.md', 'm', ARRAY['timeline','domain']),

('P2', 'pipeline_bug', 'Migrate legacy state values to canonical',
 'Update articles.enrichment_status: queued->pending, dead->failed, done/resolved->completed.',
 'open', 'docs/PIPELINE_STATE_MACHINE.md', 'l', ARRAY['migration','state_machine']),

-- P3 items
('P3', 'tech_debt', 'Implement dev/prod path drift verification',
 'Add CI check or script that diffs PopOS dev workspace against Widow prod state.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 'm', ARRAY['devops','verification']),

('P3', 'housekeeping', 'Move Assembly Integrity / Quality Reader docs to correct location',
 'Review doc placement conventions; move misplaced docs.',
 'open', 'docs/HOUSEKEEPING_BACKLOG.md', 's', ARRAY['documentation']);
```

---

## Component 2: Unified Backlog Query Service (New)

### Purpose
Eliminate the three-parallel-pipeline problem. One query, one cache layer, two consumers.

### Design (api/services/work_backlog.py — new file)

```python
from functools import lru_cache
import psycopg2
import time

_BACKLOG_CACHE = {}
_MAX_STALE_S = 30.0  # Tight for monitoring; Grafana can override


def get_unified_backlog(db_conn=None) -> dict:
    """Single source of truth for backlog counts.
    
    Returns: {
        "by_domain": {"politics": 157, "finance": 280},
        "by_phase": {"content_enrichment": 45, "context_sync": 120},
        "by_domain_phase": {"politics": {"content_enrichment": 30}},
        "total_pending": 437,
        "stale_age_s": float or None,
    }
    
    Caches results for up to 30 seconds.
    """
    global _BACKLOG_CACHE
    
    if _BACKLOG_CACHE:
        age = time.time() - _BACKLOG_CACHE["_timestamp"]
        if age <= _MAX_STALE_S:
            return {**_BACKLOG_CACHE, "stale_age_s": age}
    
    sql = """
    SELECT domain_key, pipeline_phase, COUNT(*)::int
    FROM articles
    WHERE status = 'pending'
      AND domain_key IN ('politics', 'finance')
    GROUP BY domain_key, pipeline_phase
    ORDER BY domain_key, pipeline_phase
    """
    
    with db_conn or get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
    
    by_domain = {}
    by_phase = {}
    by_domain_phase = {}
    
    for domain, phase, count in rows:
        by_domain[domain] = by_domain.get(domain, 0) + count
        by_phase[phase] = by_phase.get(phase, 0) + count
        if domain not in by_domain_phase:
            by_domain_phase[domain] = {}
        by_domain_phase[domain][phase] = count
    
    result = {
        "by_domain": by_domain,
        "by_phase": by_phase,
        "by_domain_phase": by_domain_phase,
        "total_pending": sum(by_domain.values()),
        "stale_age_s": 0.0,
        "_timestamp": time.time(),
    }
    
    _BACKLOG_CACHE = result
    return result
```

### API Endpoint Updates — MonitorPage (live SQL always)

```python
# api/domains/system_monitoring/routes/system_monitoring.py

def monitoring_dashboard_endpoint():
    from api.services.work_backlog import get_unified_backlog
    
    backlog = get_unified_backlog()  # NO prefer_stale, no long TTL
    return {
        "backlog": backlog["by_domain"],
        "total_pending": backlog["total_pending"],
        "processing_progress": get_processing_pulse(),
        "automation_health": ni_automation_health_status(),
    }
```

### Prometheus Exporter (unified labels)

```python
# api/services/ni_prometheus_metrics_service.py — update prometheus_metrics_endpoint()

def prometheus_metrics_endpoint():
    backlog = get_unified_backlog(max_stale_s=30.0)  # Tight staleness
    
    output_lines = []
    
    for domain, total in backlog["by_domain"].items():
        output_lines.append(
            f'ni_pipeline_backlog_total{{domain="{domain}", phase="all", status="pending"}} {total}'
        )
    
    for phase, count in backlog["by_phase"].items():
        for domain in sorted(backlog["by_domain"].keys()):
            dp = backlog["by_domain_phase"].get(domain, {}).get(phase, 0)
            output_lines.append(
                f'ni_pipeline_backlog_total{{domain="{domain}", phase="{phase}", status="pending"}} {dp}'
            )
    
    # Total pending aggregate
    output_lines.append(
        f'ni_pipeline_backlog_total{{domain="all", phase="all", status="pending"}} {backlog["total_pending"]}'
    )
    
    return "\n".join(output_lines) + "\n"
```

### Grafana Dashboard Updates

```promql
# BACKLOG BY DOMAIN (fixed — has phase and status labels now)
ni_pipeline_backlog_total{status="pending"} by (domain)

# TOTAL PENDING (new aggregate)
ni_pipeline_backlog_total{domain="all", status="pending"}

# PER-PHASE THROUGHPUT (still works for per-phase queries)
ni_pending_content_enrichment_total{status="pending"}
```

---

## Component 3: TTL Enforcement Cron (New)

### Purpose
Eliminate dead item accumulation across all pending-suspended tables.

### Implementation (scripts/ttl_cleanup.sh — new file)

```bash
#!/bin/bash
# Purges expired items from all pending-suspended tables
# Run via cron every hour

set -euo pipefail

psql -h "$DB_HOST" -p "$DB_PORT" -U newsapp -d "$DB_NAME" <<'SQL'
-- 1. Storyline suggestions (996K stale items)
DELETE FROM storyline_article_suggestions 
WHERE expires_at < NOW() - INTERVAL '24 hours';

-- 2. Any other pending-suspended tables that have TTL columns
-- Add here as new tables with pending states are discovered

SELECT pg_advisory_unlock(1) AS released;
SQL

echo "[$(date -Iseconds)] TTL cleanup completed" >> /var/log/news-intelligence/ttl_cleanup.log
```

### Cron Entry

```cron
# Purge expired pending items every hour
0 * * * * /home/pete/Documents/projects/News Intelligence/scripts/ttl_cleanup.sh 2>&1 | logger -t ttl_cleanup
```

---

## Component 4: State Compliance Checker (New)

### Purpose
Enforce valid state transitions. Catch invalid jumps before they corrupt data.

### Implementation (api/services/state_compliance.py — new file)

```python
from shared.pipeline_state_constants import VALID_QUEUE_TRANSITIONS, ARTICLE_TERMINAL_STATES

def validate_transition(entity_type: str, current_state: str, new_state: str) -> bool:
    """Validate a state transition against the pipeline state machine."""
    if entity_type == "article":
        if new_state in ARTICLE_TERMINAL_STATES:
            return True
        
        allowed = VALID_QUEUE_TRANSITIONS.get(current_state, [])
        valid = new_state in allowed
        
        if not valid:
            import logging
            logging.warning(
                f"INVALID transition: {entity_type} state {current_state} -> {new_state}"
            )
        
        return valid
    
    elif entity_type == "pipeline_task":
        allowed = VALID_QUEUE_TRANSITIONS.get(current_state, [])
        return new_state in allowed
    
    return False


def enforce_transition(entity_type: str, entity_id: int, current_state: str, new_state: str):
    """Validate and apply transition. Raises ValueError if invalid."""
    if not validate_transition(entity_type, current_state, new_state):
        raise ValueError(f"Invalid state transition: {entity_type} {current_state} -> {new_state}")
    
    with get_db_conn() as conn:
        cur = conn.cursor()
        if entity_type == "article":
            cur.execute(
                "UPDATE articles SET enrichment_status = %s WHERE id = %s",
                (new_state, entity_id)
            )
        elif entity_type == "pipeline_task":
            cur.execute(
                "UPDATE pipeline_state SET status = %s WHERE id = %s",
                (new_state, entity_id)
            )
        conn.commit()
        cur.close()
```

---

## Component 5: Work Items API Endpoints (New)

### Purpose
Query and manage work items from MonitorPage and external tooling.

### Endpoints (api/domains/work_management/routes/work_items.py — new file)

```python
from fastapi import APIRouter, Query
from typing import Optional
import psycopg2

router = APIRouter(prefix="/api/work", tags=["work"])


@router.get("/backlog")
def get_backlog_summary(
    priority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Returns prioritized work items filtered by optional criteria."""
    
    conditions = []
    params = []
    
    if priority:
        conditions.append("priority = %s")
        params.append(priority)
    if status:
        conditions.append("status = %s")
        params.append(status)
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    sql = f"""
    SELECT id, priority, category, title, description, status, 
           created_at, completed_at, effort_est, tags
    FROM work_items {where}
    ORDER BY priority ASC, created_at ASC
    """
    
    return {"items": rows, "count": len(rows)}


@router.get("/status")
def get_system_status():
    """Aggregated system health: backlog counts + work items by status."""
    from api.services.work_backlog import get_unified_backlog
    from shared.pipeline_state_constants import VALID_QUEUE_TRANSITIONS
    
    backlog = get_unified_backlog()
    
    sql = "SELECT priority, status, COUNT(*) FROM work_items GROUP BY priority, status ORDER BY priority, status"
    
    return {
        "backlog": backlog,
        "work_items_summary": work_summary_rows,
        "state_machine": {
            "article_terminal_states": list(ARTICLE_TERMINAL_STATES),
            "valid_transitions_count": len(VALID_QUEUE_TRANSITIONS),
        },
    }
```

---

## Implementation Plan (Prioritized)

### Phase 1: Emergency Cleanup (Day 1, P0)

| Task | File(s) | Impact |
|------|---------|--------|
| Enable AUTO_ATTACH (`STORYLINE_AUTOMATION_AUTO_ATTACH=1`) | `.env` line ~64 | Stops new dead item accumulation |
| Add TTL cleanup cron | `scripts/ttl_cleanup.sh` + crontab | Begins reclaiming 996K stale items |
| Delete empty `docs/generated/` | file system | Low risk, high signal-to-noise ratio |

### Phase 2: Monitoring Fix (Day 1-2, P0)

| Task | File(s) | Impact |
|------|---------|--------|
| Add phase/status labels to Prometheus metrics | `ni_prometheus_metrics_service.py` | Grafana queries return correct values |
| Add total_pending metric | same file | Easy Grafana panel for "total pending" |
| Reduce Grafana staleness TTL from 600s to 30s | caller of prometheus endpoint | Real-time monitoring, not stale |
| Update Grafana dashboard JSON panels | `grafana/dashboards/ni_pipeline_health.json` | Mirrors MonitorPage sections |

### Phase 3: Core Infrastructure (Day 2-4, P1-P2)

| Task | File(s) | Impact |
|------|---------|--------|
| Create work_items table + seed data | new DB migration | Unified work tracking replaces TODO docs |
| Create unified backlog query service | `api/services/work_backlog.py` | One query for all consumers |
| Add Work Items API endpoints | `routes/work_items.py` | Queryable work management REST API |
| Implement state compliance checker | `api/services/state_compliance.py` | Prevents invalid state transitions |

### Phase 4: Legacy Cleanup (Day 3-5, P2-P3)

| Task | File(s) | Impact |
|------|---------|--------|
| Migrate legacy state values to canonical | DB migration | Eliminates dead references in code |
| Consolidate archive layers | `_archive/` -> `archive/` | Reduces complexity |
| Create ADR.md and CHANGELOG.md | `docs/ADR.md`, `docs/CHANGELOG.md` | Architecture documentation |
| Update stale TROUBLESHOOTING.md cross-references | remaining docs in `docs/` | Eliminates Docker Compose references |

---

## Monitoring Metrics After Fix

### Before (broken):

```
# Grafana query: ni_pipeline_backlog_total{status="pending"} 
# Returns: NOTHING (no status label exists)

# Grafana query: ni_pipeline_backlog_total{phase="content_enrichment"}
# Returns: NOTHING (no phase label exists on ni_pipeline_backlog_total)

# MonitorPage shows: politics=157, finance=280 (live SQL)
# Grafana shows: 0 or stale data from >600s ago
```

### After (fixed):

```
# Grafana query: ni_pipeline_backlog_total{status="pending"} 
# Returns: politics=157, finance=280 (has phase and status labels!)

# Grafana query: ni_pipeline_backlog_total{domain="all", status="pending"}
# Returns: 437 (total pending aggregate)

# Grafana query: ni_pending_content_enrichment_total{status="pending"}
# Returns: politics=30, finance=15 (still works for per-phase)

# MonitorPage shows: same live SQL -> now matches Grafana
```

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| TTL cron deletes items still being processed | Only delete where `expires_at < NOW() - 24h`; give 24-hour grace period |
| Unified backlog query is slow for large datasets | Add partial index: `CREATE INDEX idx_articles_pending ON articles(status, domain_key) WHERE status='pending'` |
| State compliance checker adds latency to writes | Optional opt-in for new code; legacy code unaffected |
| Grafana dashboard JSON update breaks existing panels | Test panels on staging Grafana instance before prod deployment |

---

## Verification Queries (Post-Implementation)

```sql
-- 1. Verify no dead items remain in storyline_suggestions
SELECT status, COUNT(*) 
FROM storyline_article_suggestions 
GROUP BY status;
-- Expected: pending ~0 after TTL cron runs for 24h+

-- 2. Verify work_items populated correctly
SELECT priority, category, title, status FROM work_items ORDER BY priority, created_at;
-- Expected: all items from seed data visible

-- 3. Verify unified backlog query performance
EXPLAIN ANALYZE 
SELECT domain_key, pipeline_phase, COUNT(*)::int
FROM articles WHERE status = 'pending' GROUP BY domain_key, pipeline_phase;
-- Expected: < 50ms with partial index on (status, domain_key)

-- 4. Verify Grafana metric labels
curl -s http://localhost:8001/api/system_monitoring/prometheus | 
  grep ni_pipeline_backlog_total | head -20;
-- Expected: has "phase=" and "status=" labels present

-- 5. Verify state compliance catches invalid transitions
-- (Application-level test in unit tests, not SQL)
```

---

## Open Questions / Decisions Needed

1. **Should we enable AUTO_ATTACH or build a manual approve endpoint first?** 
   - Option A: Enable AUTO_ATTACH immediately (stops new dead items; fast win)
   - Option B: Build `/api/work/approve` endpoint for manual batch approval
   - Recommendation: Do both -- enable AUTO_ATTACH now, build approve endpoint in Phase 3

2. **What is the correct TTL grace period for cleanup cron?**
   - Current TTL in code: 7 days (expires_at = NOW() + 7d)
   - Proposal: purge at 24h past expiry (= 8 days total from creation)
   - Rationale: Allows time for pending items to be processed before deletion

3. **Should we keep `ni_pending_<phase>_total` per-phase metrics or migrate entirely to single metric with phase label?**
   - Option A: Keep both (backwards compatible, zero Grafana panel change)
   - Option B: Deprecate per-phase names after 2 weeks, redirect all queries
   - Recommendation: Option A -- backwards compatibility saves dashboard migration effort

---

## Appendix A: Affected Files Summary

| Action | File(s) |
|--------|---------|
| New file | `api/services/work_backlog.py` |
| New file | `api/services/state_compliance.py` |
| New file | `api/domains/work_management/routes/work_items.py` |
| New file | `scripts/ttl_cleanup.sh` |
| Modify | `.env` line 64: `STORYLINE_AUTOMATION_AUTO_ATTACH=0 -> 1` |
| Modify | `api/services/ni_prometheus_metrics_service.py` |
| Modify | `api/domains/system_monitoring/routes/system_monitoring.py` |
| Modify | `grafana/dashboards/ni_pipeline_health.json` (add/update panels) |
| Modify | DB: new migration for `work_items` table |

## Appendix B: Prior Evidence Mapping

| Finding In This Design | Source Document | Evidence |
|------------------------|-----------------|----------|
| 996K+ dead suggestions | pending-items-triage.md | Line 51: `storyline_article_suggestions.pending ~996K+ items` |
| No TTL cleanup cron exists | pending-items-triage.md | Line 57: no `DELETE FROM storyline_article_suggestions` anywhere |
| 432 backlog iterations, 36-day ETA | BACKLOG_STATUS_ANALYSIS.md | "Overall ETA: 862.1 hours" line 9; "NOT ACHIEVED" line 10 |
| 700/hr theoretical vs ~114/hr actual | TROUBLESHOOTING.md | Lines 360-383: content enrichment analysis |
| AUTOMATION_QUEUE_SOFT_CAP=100 | TROUBLESHOOTING.md | Line 207: queue depth behavior description |
| Metric naming mismatch | MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md | Issue #1 (lines 143-154), Fix 1 (lines 253-262) |
| Grafana stale cache 600s | MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md | Line 98: `max_stale_s=600.0` |
| No total pending metric | MONITOR_BACKLOG_DISCREPANCY_ANALYSIS.md | Issue #5 (lines 248-296) |
| Archive layer redundancy | HOUSEKEEPING_BACKLOG.md | P1 line 24: "Two separate archive layers" |
| Missing ADRs and CHANGELOG | HOUSEKEEPING_BACKLOG.md | P2 lines 56, 64 |
| Topic clustering migration failure | TROUBLESHOOTING.md | Lines 237+: web page slow due to missing column |
| TimelineBuilderService domain-scoping gap | TROUBLESHOOTING.md | Lines 213-218: known gaps table |
| Legacy state values not migrated | PIPELINE_STATE_MACHINE.md | Lines 119-127: migration plan documented but not executed |

---

*This design spec consolidates findings from six separate documentation sources into a unified work management system. Implementation should follow the phased prioritization above -- emergency fixes first, then core infrastructure, then legacy cleanup.*
