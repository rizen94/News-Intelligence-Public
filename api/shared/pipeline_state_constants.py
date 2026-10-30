"""Canonical pipeline state definitions for News Intelligence.

All pipeline phases, article enrichment states, and queue statuses
use these constants — never magic strings. This module is the single
source of truth for state machine transitions.

## Design Decisions

1. **Existing DB values are preserved** — The database already writes
   ``'enriched'``, ``'failed'``, ``'inaccessible'`` to enrichment_status.
   We map canonical names to these strings rather than renaming them,
   which would require a migration and risk breaking running workers.

2. **Four-value queue baseline** — All queue/pipeline-phase logic uses
   pending / processing / completed / failed. Legacy values ('queued',
   'dead', 'done') are kept as read-only aliases for scanning old data.

3. **Terminal state classification** — ``is_terminal()`` lets callers
   distinguish "awaiting further work" from "definitely done (for now)."

4. **Backlog thresholds** are NOT here — they live in backlog_metrics.py
   and config.settings where they are tunable per phase. Constants define
   only states and valid transitions.

## Usage Example

    from shared.pipeline_state_constants import ARTICLE_ENRICHED, QUEUE_PENDING

    article.enrichment_status = ARTICLE_ENRICHED
    if status in ARTICLE_TERMINAL_STATES:
        mark_as_done(article)

See docs/PIPELINE_STATE_MACHINE.md for the full state diagram.
"""

from __future__ import annotations

import enum
from typing import FrozenSet


ARTICLE_PENDING      = "pending"
ARTICLE_ENRICHED     = "enriched"
ARTICLE_FAILED       = "failed"
ARTICLE_INACCESSIBLE = "inaccessible"
ARTICLE_CONTENT_SHORT = ""


class ArticleState(enum.StrEnum):
    PENDING = ARTICLE_PENDING
    ENRICHED  = ARTICLE_ENRICHED
    FAILED    = ARTICLE_FAILED
    INACCESSIBLE = ARTICLE_INACCESSIBLE
    CONTENT_SHORT = ARTICLE_CONTENT_SHORT

ARTICLE_ALL_STATES: FrozenSet[str] = frozenset({
    ARTICLE_PENDING, ARTICLE_ENRICHED, ARTICLE_FAILED,
    ARTICLE_INACCESSIBLE, ARTICLE_CONTENT_SHORT,
})

ARTICLE_TERMINAL_STATES: FrozenSet[str] = frozenset({
    ARTICLE_ENRICHED, ARTICLE_FAILED, ARTICLE_INACCESSIBLE,
})

ARTICLE_NON_TERMINAL_STATES: FrozenSet[str] = frozenset({
    ARTICLE_PENDING, ARTICLE_CONTENT_SHORT,
})

ARTICLE_ML_ELIGIBLE: FrozenSet[str] = frozenset({ARTICLE_ENRICHED})


QUEUE_PENDING   = "pending"
QUEUE_PROCESSING = "processing"
QUEUE_COMPLETED  = "completed"
QUEUE_FAILED     = "failed"


class QueueState(enum.StrEnum):
    PENDING    = QUEUE_PENDING
    PROCESSING = QUEUE_PROCESSING
    COMPLETED  = QUEUE_COMPLETED
    FAILED     = QUEUE_FAILED

QUEUE_ALL_STATES: FrozenSet[str] = frozenset({
    QUEUE_PENDING, QUEUE_PROCESSING, QUEUE_COMPLETED, QUEUE_FAILED,
})

QUEUE_TERMINAL_STATES: FrozenSet[str] = frozenset({QUEUE_COMPLETED, QUEUE_FAILED})
QUEUE_NON_TERMINAL_STATES: FrozenSet[str] = frozenset({QUEUE_PENDING, QUEUE_PROCESSING})


ML_PENDING  = "pending"
ML_RUNNING  = "processing"
ML_COMPLETED = "completed"
ML_FAILED   = "failed"


class MLState(enum.StrEnum):
    PENDING   = ML_PENDING
    RUNNING   = ML_RUNNING
    COMPLETED = ML_COMPLETED
    FAILED    = ML_FAILED

ML_ALL_STATES: FrozenSet[str] = frozenset({ML_PENDING, ML_RUNNING, ML_COMPLETED, ML_FAILED})
ML_TERMINAL_STATES: FrozenSet[str] = frozenset({ML_COMPLETED, ML_FAILED})


LEGACY_QUEUED   = "queued"
LEGACY_DEAD     = "dead"
LEGACY_DONE     = "done"
LEGACY_RESOLVED = "resolved"

LEGACY_TO_CANONICAL: dict[str, str | None] = {
    LEGACY_QUEUED:   QUEUE_PENDING,
    LEGACY_DEAD:     QUEUE_FAILED,
    LEGACY_DONE:     QUEUE_COMPLETED,
    LEGACY_RESOLVED: QUEUE_COMPLETED,
}


VALID_ENRICHMENT_TRANSITIONS: dict[str, FrozenSet[str]] = {
    ARTICLE_PENDING:      frozenset({ARTICLE_ENRICHED, ARTICLE_FAILED, ARTICLE_INACCESSIBLE}),
    ARTICLE_CONTENT_SHORT: frozenset({ARTICLE_ENRICHED, ARTICLE_FAILED, ARTICLE_INACCESSIBLE}),
}

VALID_QUEUE_TRANSITIONS: dict[str, FrozenSet[str]] = {
    QUEUE_PENDING:  frozenset({QUEUE_PROCESSING, QUEUE_FAILED}),
    QUEUE_PROCESSING: frozenset({QUEUE_COMPLETED, QUEUE_FAILED}),
}

VALID_ML_TRANSITIONS: dict[str, FrozenSet[str]] = {
    ML_PENDING: frozenset({ML_RUNNING}),
    ML_RUNNING: frozenset({ML_COMPLETED, ML_FAILED}),
}


PIPELINE_PHASES: list[str] = [
    "content_enrichment", "context_sync", "entity_extraction",
    "metadata_enrichment", "storyline_discovery", "event_extraction",
    "sentiment_analysis", "claim_extraction", "event_tracking",
    "quality_scoring", "ml_processing", "topic_clustering",
    "timeline_generation", "entity_profile_sync", "document_processing",
    "content_refinement_queue", "nightly_enrichment_context",
]

PHASE_GROUP: dict[str, str] = {
    "content_enrichment":       "ingestion",
    "context_sync":             "ingestion",
    "entity_extraction":        "ml_processing",
    "metadata_enrichment":      "ml_processing",
    "sentiment_analysis":       "ml_processing",
    "claim_extraction":         "ml_processing",
    "event_extraction":         "ml_processing",
    "event_tracking":           "ml_processing",
    "quality_scoring":          "ml_processing",
    "topic_clustering":         "storyline",
    "timeline_generation":      "storyline",
    "entity_profile_sync":      "storyline",
    "document_processing":      "ingestion",
    "content_refinement_queue": "storyline",
    "nightly_enrichment_context": "nightly",
}