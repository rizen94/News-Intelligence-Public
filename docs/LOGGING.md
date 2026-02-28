# Logging — Standardized Activity and Storage

## Overview

Logging is standardized across API requests, RSS pulls, orchestrator decisions, external API calls, LLM interactions, and task traces. All activity uses a unified schema and writes to consolidated files. See `docs/LOGGING_SYSTEM_SUMMARY.md` for the full architecture and implementation plan.

## Canonical Activity Storage

| File | Format | Purpose |
|------|--------|---------|
| `logs/activity.log` | Human-readable lines | All API requests, RSS pulls, orchestrator queue decisions |
| `logs/activity.jsonl` | JSON Lines | Same events, machine-parseable for analysis/scripts |

## Standard Schema

Every activity entry includes:

```json
{
  "timestamp": "2025-02-21T12:00:00.000Z",
  "component": "api|rss|orchestrator",
  "event_type": "request|feed_pull|queue_decision",
  "status": "success|error|queued|no_entries|..."
}
```

Plus event-specific fields (method, path, status_code, feed_name, activity, reason, etc.).

## What Gets Logged

### API Requests

- **When**: Every HTTP request (middleware)
- **Fields**: method, path, status_code, duration_ms
- **Component**: `api`

### RSS Pulls

- **When**: Every RSS feed fetch (news_aggregation, services/rss/fetching, collectors/rss_collector)
- **Fields**: feed_id, feed_name, articles_fetched, articles_saved, duration_ms, error (if any)
- **Status**: success | error | no_entries
- **Component**: `rss`

### Orchestrator Decisions

- **When**: Every task submitted to the finance orchestrator
- **Fields**: activity (e.g. "refresh", "analysis"), reason (short rationale), task_id, priority
- **Examples**:
  - "User requested analysis"
  - "Manual/API-triggered refresh (topic=gold)"
  - "Scheduled run: gold_refresh (interval met)"
  - "Orchestrator revision (retry after failed evaluation)"
- **Component**: `orchestrator`

## Usage in Code

```python
from shared.logging.activity_logger import (
    log_api_request,   # Called by middleware
    log_rss_pull,      # Called by RSS fetch paths
    log_orchestrator_decision,  # Called by orchestrator
    log_activity,      # Generic for other components
)
```

## Legacy Loggers

Component loggers (api.log, rss_processing.log, finance.log, etc.) still exist for backward compatibility. New instrumentation should prefer the activity logger. Component logs can be phased out over time.

## Querying

```bash
# All API errors
grep '"component":"api"' logs/activity.jsonl | grep '"status":"error"'

# All RSS pulls for a feed
grep '"feed_name":"Reuters"' logs/activity.jsonl

# Orchestrator decisions
grep '"event_type":"queue_decision"' logs/activity.jsonl

# Trace a task
grep 'fin-abc123' logs/activity.jsonl
```
