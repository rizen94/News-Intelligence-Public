# LLM Activity Monitoring Guide

## Overview

Real-time visibility into LLM usage and current processing status. Know exactly when LLM is being used and what's currently being processed.

## Quick Status Check

**Endpoint:** `GET /api/content_analysis/llm/status`

**Response:**
```json
{
  "success": true,
  "llm_available": true,
  "active_tasks": 2,
  "last_activity": "2024-01-01T12:00:00",
  "current_tasks": [
    {
      "type": "topic_extraction",
      "article_id": 123,
      "domain": "politics",
      "duration_seconds": 3.45
    }
  ]
}
```

## Full Activity View

**Endpoint:** `GET /api/content_analysis/llm/activity?include_history=true&history_limit=20`

**Shows:**
- LLM availability status
- Currently active tasks (with full details)
- Task statistics (total, completed, failed, success rate)
- Recent task history (optional)

**Response Fields:**
- `llm_status.available` - Is LLM currently available?
- `llm_status.last_check` - When was availability last checked?
- `llm_status.last_activity` - When was last LLM task?
- `current_processing.active_tasks` - Number of tasks running now
- `current_processing.tasks` - List of active tasks with:
  - `task_id` - Unique task identifier
  - `task_type` - Type of task (topic_extraction, queue_topic_extraction, etc.)
  - `article_id` - Article being processed
  - `domain` - Domain schema
  - `started_at` - When task started
  - `duration_seconds` - How long it's been running
  - `metadata` - Additional info (title, queue_id, etc.)

## Comprehensive Dashboard

**Endpoint:** `GET /api/content_analysis/llm/dashboard`

**Shows Everything:**
- LLM status and availability
- All active tasks across all domains
- Queue status per domain (pending/processing/completed/failed)
- Overall statistics
- System health indicators

## Domain-Specific View

**Endpoint:** `GET /api/{domain}/content_analysis/llm/activity`

**Shows:** LLM activity filtered to specific domain (politics, finance, science-tech)

## Understanding the Data

### LLM Available Status
- `true` - LLM service is responding and ready
- `false` - LLM service unavailable (articles will be queued)

### Active Tasks
Tasks currently being processed by LLM:
- `topic_extraction` - Direct topic extraction from articles
- `queue_topic_extraction` - Processing queued articles

### Task Duration
Shows how long each task has been running. Typical durations:
- Topic extraction: 200-500ms per article
- Queue processing: 1-2 seconds per article (includes database operations)

### Queue Status
Per-domain queue statistics:
- `pending` - Articles waiting for LLM
- `processing` - Articles currently being processed
- `completed` - Successfully processed
- `failed` - Failed after max retries

## Real-Time Updates

The tracker updates in real-time:
- Tasks are tracked when they **start**
- Duration is calculated **live** (updates on each request)
- Tasks are marked **complete** when finished
- History keeps last **100 tasks**

## Example Use Cases

### 1. Check if LLM is being used right now
```bash
curl http://localhost:8000/api/content_analysis/llm/status
```
Look for `active_tasks > 0` and `llm_available: true`

### 2. See what articles are currently processing
```bash
curl http://localhost:8000/api/content_analysis/llm/activity
```
Check `current_processing.tasks` array

### 3. Monitor queue backlog
```bash
curl http://localhost:8000/api/content_analysis/llm/dashboard
```
Check `queue_status.{domain}.pending` - shows articles waiting

### 4. Check domain-specific activity
```bash
curl http://localhost:8000/api/politics/content_analysis/llm/activity
```
See only politics domain tasks

## Integration Points

The tracker automatically tracks:
- ✅ Topic extraction tasks (when LLM is used)
- ✅ Queue processing tasks (when queue worker processes articles)
- ✅ LLM availability checks (updates when tested)

## Troubleshooting

**No active tasks but LLM available?**
- System is idle, no articles being processed
- Check queue status for pending articles

**LLM unavailable?**
- Articles are being queued automatically
- Check queue status to see pending count
- Queue worker will process when LLM available

**Tasks stuck in "processing"?**
- Check task duration - if very long (>60s), may be stuck
- Check LLM service health
- Review error logs

