"""Deterministic co-occurrence detection with mandatory base rates."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from nri_core.evidence import ni_reader


@dataclass
class DetectionCandidate:
    pattern_type: str
    entities: list[str]
    observed_count: int
    expected_count: float
    base_rate: float
    window: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_type": self.pattern_type,
            "entities": self.entities,
            "observed_count": self.observed_count,
            "expected_count": self.expected_count,
            "base_rate": self.base_rate,
            "window": self.window,
        }


DEFAULT_BASE_RATES = {
    "cooccurrence": 0.02,
    "velocity_spike": 0.01,
    "timing_anomaly": 0.005,
}


def detect_cooccurrence(
    entity_ftm_ids: list[str],
    since_context_id: int = 0,
    window: str = "30d",
    base_rate: float | None = None,
) -> list[DetectionCandidate]:
    """Detect entity pair co-occurrence in shared contexts."""
    base_rate = base_rate if base_rate is not None else DEFAULT_BASE_RATES["cooccurrence"]
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    total_contexts = 0

    mentions = ni_reader.fetch_new_mentions(since_id=since_context_id, limit=5000)
    by_context: dict[int, set[str]] = defaultdict(set)

    with ni_reader.news_intel_connection() as conn:
        import psycopg2.extras
        from nri_core.config import get_config

        cfg = get_config()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT context_id, ftm_id
                FROM {cfg.nri_schema}.resolved_mentions
                WHERE ftm_id IS NOT NULL AND status = 'auto_linked'
                """
            )
            for row in cur.fetchall():
                by_context[int(row["context_id"])].add(row["ftm_id"])

    entity_set = set(entity_ftm_ids)
    for ctx_id, ftm_ids in by_context.items():
        present = entity_set & ftm_ids
        if len(present) < 2:
            continue
        total_contexts += 1
        sorted_ids = sorted(present)
        for i, a in enumerate(sorted_ids):
            for b in sorted_ids[i + 1 :]:
                pair_counts[(a, b)] += 1

    expected = max(total_contexts * base_rate, 0.1)
    candidates: list[DetectionCandidate] = []
    for (a, b), observed in pair_counts.items():
        if observed < 2:
            continue
        candidates.append(
            DetectionCandidate(
                pattern_type="cooccurrence",
                entities=[a, b],
                observed_count=observed,
                expected_count=expected,
                base_rate=base_rate,
                window=window,
            )
        )
    return candidates


def detect_velocity_spike(
    entity_ftm_id: str,
    recent_count: int,
    baseline_count: int,
    window: str = "7d",
    base_rate: float | None = None,
) -> DetectionCandidate | None:
    base_rate = base_rate if base_rate is not None else DEFAULT_BASE_RATES["velocity_spike"]
    if baseline_count <= 0:
        baseline_count = 1
    expected = baseline_count * base_rate
    if recent_count <= expected:
        return None
    return DetectionCandidate(
        pattern_type="velocity_spike",
        entities=[entity_ftm_id],
        observed_count=recent_count,
        expected_count=expected,
        base_rate=base_rate,
        window=window,
    )


def reject_missing_base_rate(candidate: dict[str, Any]) -> bool:
    return candidate.get("base_rate") is not None and candidate.get("expected_count") is not None
