# Pipeline State Machine — Canonical Reference

**Last updated**: 2026-10-28  
**Author**: News Intelligence platform team  
**Single source of truth**: `api/shared/pipeline_state_constants.py`

---

## Overview

This document defines the canonical state machine for the News Intelligence pipeline. All modules must use constants from `shared.pipeline_state_constants` — no magic strings.

## State Diagrams

### Article Enrichment Lifecycle

```
┌──────────┐   ingest     ┌───────────────┐
│ pending  │─────────────►│ enriched      │── pipeline phases ──► (terminal)
│          │              │               │
└──────────┘              └───────┬───────┘
       │                          │
       │ RSS short body           │ fetch/content fails
       ▼                          ▼
┌──────────────┐         ┌──────────┐     ┌──────────────────┐
│ content_short│         │ failed   │────►│ inaccessible    │
│              │         │          │     │                  │
└──────────────┘         └──────────┘     └──────────────────┘
```

| State | DB Value | Meaning | Terminal? |
|-------|----------|---------|-----------|
| `pending` | `"pending"` | Article ingested, awaiting content fetch | No |
| `enriched` | `"enriched"` | Content fetched and body available | Yes |
| `failed` | `"failed"` | Fetch/extraction failed | Yes |
| `inaccessible` | `"inaccessible"` | URL returned 4xx/5xx or timed out | Yes |
| (empty) | `""` | RSS provided minimal body, no separate file | No |

**Key**: Only `enriched`, `failed`, `inaccessible` are terminal. Articles in `pending` or with empty content can be retried.

### Queue Phase Lifecycle

```
     ┌─────────┐
     │ pending ├─────────────────────►  failed (aborted)
     └────┬────┘
          │ picked up
          ▼
     ┌──────────────┐
     │ processing   ├─────────►  completed (success)
     │              ├─────────►  failed (error)
     └──────────────┘
```

All phases follow this pattern: `pending` → `processing` → `completed` / `failed`.

### ML Processing Lifecycle

```
     ┌─────────┐   enriched    ┌──────────┐
     │ pending ├──────────────►│ running  │─────►  completed (all models done)
     └─────────┘              └────┬─────┘         failed (partial/error)
                                  │ error/retry
```

## Valid Transitions

| From | To | Condition |
|------|-----|-----------|
| `pending` | `enriched` / `failed` / `inaccessible` | Content fetch completes |
| `content_short` | `enriched` / `failed` / `inaccessible` | Inline body processed or retry |
| `queued` (legacy) | `pending` | Migration alias only |
| `dead` (legacy) | `failed` | Migration alias only |
| `done` (legacy) | `completed` | Migration alias only |
| `resolved` (legacy) | `completed` | Migration alias only |

**No other transitions are valid.** A state should never jump directly to a non-adjacent state.

## Pipeline Phases

The following phases use the queue state machine:

| Phase | Group | Description | Batch Size (default) |
|-------|-------|-------------|---------------------|
| `content_enrichment` | ingestion | Fetch & extract article content | 60 |
| `context_sync` | ingestion | Build intelligence.contexts | 100 |
| `entity_extraction` | ml_processing | Extract entities via ML | 60 |
| `metadata_enrichment` | ml_processing | Enrich metadata via ML | 15 |
| `sentiment_analysis` | ml_processing | Sentiment classification | 300 |
| `claim_extraction` | ml_processing | Extract claims | 50 |
| `event_extraction` | ml_processing | Extract events | — |
| `event_tracking` | ml_processing | Track recurring events | 300 |
| `quality_scoring` | ml_processing | Quality scoring | 150 |
| `ml_processing` | ml_processing | ML inference orchestration | 150 |
| `topic_clustering` | storyline | Cluster articles by topic | — |
| `timeline_generation` | storyline | Generate event timelines | — |
| `entity_profile_sync` | storyline | Sync entity profiles | — |
| `document_processing` | ingestion | Process uploaded documents | 10 |
| `content_refinement_queue` | storyline | Refine content summaries | 4 |

## Backlog Detection

Backlog is detected when pending count exceeds the batch size per phase for a sustained period. Thresholds are defined in `api/services/backlog_metrics.py`:

```python
BATCH_SIZE_PER_TASK = {
    "content_enrichment": 60,
    "context_sync":       100,
    "ml_processing":      150,
    # ... see backlog_metrics.py for full list
}
```

When `pending_count > BATCH_SIZE_PER_TASK[phase]`, the phase is in **backlog mode** and runs at shorter intervals.

## Migration from Legacy Terms

Legacy values are mapped via `LEGACY_TO_CANONICAL`:

| Legacy | Canonical | Source |
|--------|-----------|--------|
| `queued` | `pending` | Old queue system |
| `dead` | `failed` | Old worker messages |
| `done` | `completed` | Old completion signal |
| `resolved` | `completed` | Old storyline states |

**Migration plan**: In the next DB migration, update all existing legacy values to canonical. After that, legacy columns can be dropped.

## Implementation Notes

### Writing State Changes

```python
from shared.pipeline_state_constants import ARTICLE_ENRICHED, QUEUE_COMPLETED

# Article enrichment
article.enrichment_status = ARTICLE_ENRICHED

# Queue phase
task.status = QUEUE_COMPLETED  # Use canonical names always
```

### Validating Transitions

```python
from shared.pipeline_state_constants import VALID_QUEUE_TRANSITIONS

VALID_TRANSITIONS = VALID_QUEUE_TRANSITIONS.get(current)
if new in VALID_TRANSITIONS:
    update_status(task, new)
else:
    raise InvalidTransition(f"{current} → {new}")
```

### Checking Terminal State

```python
from shared.pipeline_state_constants import ARTICLE_TERMINAL_STATES

if article.enrichment_status in ARTICLE_TERMINAL_STATES:
    skip_from_backlog(article)  # Don't re-process
```

---

*This document is the canonical reference. When in doubt, check `api/shared/pipeline_state_constants.py` first.*