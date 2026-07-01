"""
Spine throughput / efficiency metrics for Monitor and rollout validation.

Tracks LLM passes per article, fan-out vs LLM time ratio, and spine latency samples.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_MAX_SAMPLES = 500
_lock = Lock()

_fusion_batches: deque[dict[str, float]] = deque(maxlen=_MAX_SAMPLES)
_spine_latency_hours: deque[float] = deque(maxlen=_MAX_SAMPLES)
_over_sla_count = 0
_SLA_HOURS = 4.0


@dataclass
class SpineThroughputSnapshot:
    fusion_batch_count: int = 0
    avg_llm_seconds_per_article: float = 0.0
    avg_fan_out_seconds_per_article: float = 0.0
    avg_passes_per_article: float = 0.0
    fan_out_ratio: float = 0.0
    avg_articles_per_gpu_call: float = 0.0
    spine_p95_latency_hours: float | None = None
    spine_over_sla_count: int = 0
    spine_sla_hours: float = _SLA_HOURS


_snapshot = SpineThroughputSnapshot()


def record_fusion_batch_metrics(
    *,
    article_count: int,
    llm_seconds: float,
    fan_out_seconds: float,
) -> None:
    n = max(1, int(article_count))
    with _lock:
        _fusion_batches.append(
            {
                "articles": float(n),
                "llm_seconds": float(llm_seconds),
                "fan_out_seconds": float(fan_out_seconds),
                "passes_per_article": 1.0 / float(n),
            }
        )
        _recompute_snapshot_locked()


def record_spine_latency_hours(hours: float) -> None:
    global _over_sla_count
    h = max(0.0, float(hours))
    with _lock:
        _spine_latency_hours.append(h)
        if h > _SLA_HOURS:
            _over_sla_count += 1
        _recompute_snapshot_locked()


def _recompute_snapshot_locked() -> None:
    global _snapshot
    snap = SpineThroughputSnapshot(spine_over_sla_count=_over_sla_count)

    if _fusion_batches:
        total_articles = sum(b["articles"] for b in _fusion_batches)
        total_llm = sum(b["llm_seconds"] for b in _fusion_batches)
        total_fan = sum(b["fan_out_seconds"] for b in _fusion_batches)
        if total_articles > 0:
            snap.fusion_batch_count = len(_fusion_batches)
            snap.avg_llm_seconds_per_article = total_llm / total_articles
            snap.avg_fan_out_seconds_per_article = total_fan / total_articles
            snap.avg_passes_per_article = len(_fusion_batches) / total_articles
            snap.avg_articles_per_gpu_call = total_articles / len(_fusion_batches)
            denom = total_llm + total_fan
            snap.fan_out_ratio = (total_fan / denom) if denom > 0 else 0.0

    if _spine_latency_hours:
        ordered = sorted(_spine_latency_hours)
        idx = min(len(ordered) - 1, int(0.95 * len(ordered)))
        snap.spine_p95_latency_hours = round(ordered[idx], 3)

    _snapshot = snap


def get_spine_throughput_snapshot() -> dict[str, Any]:
    with _lock:
        s = _snapshot
        return {
            "fusion_batch_count": s.fusion_batch_count,
            "avg_llm_seconds_per_article": round(s.avg_llm_seconds_per_article, 3),
            "avg_fan_out_seconds_per_article": round(s.avg_fan_out_seconds_per_article, 3),
            "avg_passes_per_article": round(s.avg_passes_per_article, 4),
            "fan_out_ratio": round(s.fan_out_ratio, 3),
            "avg_articles_per_gpu_call": round(s.avg_articles_per_gpu_call, 2),
            "spine_p95_latency_hours": s.spine_p95_latency_hours,
            "spine_over_sla_count": s.spine_over_sla_count,
            "spine_sla_hours": s.spine_sla_hours,
        }


def sample_spine_latencies_from_db(*, limit: int = 200) -> int:
    """
    Populate latency samples from articles with cleared unified intake pass.
    Returns number of samples recorded.
    """
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import pipeline_url_schema_pairs
        from shared.pipeline_pass_marker import sql_article_pass_cleared

        recorded = 0
        per_schema = max(10, limit // 5)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for _dk, schema in pipeline_url_schema_pairs():
                    cur.execute(
                        f"""
                        SELECT EXTRACT(EPOCH FROM (
                            COALESCE(
                                (a.metadata #>> '{{pipeline,unified_intake_extraction,last_pass_at}}')::timestamptz,
                                a.updated_at
                            ) - a.created_at
                        )) / 3600.0 AS spine_hours
                        FROM {schema}.articles a
                        WHERE ({sql_article_pass_cleared("unified_intake_extraction", "a")})
                          AND a.created_at > NOW() - INTERVAL '7 days'
                        ORDER BY a.created_at DESC
                        LIMIT %s
                        """,
                        (per_schema,),
                    )
                    for (hours,) in cur.fetchall():
                        if hours is not None:
                            record_spine_latency_hours(float(hours))
                            recorded += 1
        return recorded
    except Exception as e:
        logger.debug("sample_spine_latencies_from_db: %s", e)
        return 0
