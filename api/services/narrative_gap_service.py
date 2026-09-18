"""
Narrative gap detection (Phase 5).

For typed arcs with an inferred stage, if the next expected stage is missing
beyond N days, enqueue a rag_evidence_pull_queue ticket to seek evidence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool, env_int

logger = logging.getLogger(__name__)


def narrative_gap_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("narrative_gap_detection", default=False):
            return True
    except Exception:
        pass
    return env_bool("NARRATIVE_GAP_DETECTION_ENABLED", False)


def gap_days_threshold() -> int:
    return max(1, env_int("NARRATIVE_GAP_DAYS", 14))


def detect_gap_for_storyline(
    domain_key: str,
    storyline_id: int,
    *,
    gap_days: int | None = None,
) -> dict[str, Any] | None:
    """
    Return a gap dict when the next arc stage is overdue, else None.

    Pure detection — does not enqueue.
    """
    from services.arc_stage_service import infer_arc_stage

    info = infer_arc_stage(domain_key, storyline_id, persist=False)
    stages = info.get("stages") or []
    stage = info.get("stage")
    idx = int(info.get("stage_index") if info.get("stage_index") is not None else -1)
    if not stages or not stage or idx < 0 or idx >= len(stages) - 1:
        return None

    next_stage = stages[idx + 1]
    threshold = gap_days if gap_days is not None else gap_days_threshold()

    # Age since last matched event (or storyline material update)
    last_event_at = _last_event_ts(domain_key, storyline_id)
    if last_event_at is None:
        return None
    age_days = (datetime.now(timezone.utc) - last_event_at).total_seconds() / 86400.0
    if age_days < threshold:
        return None

    return {
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "pattern": info.get("pattern"),
        "current_stage": stage,
        "missing_stage": next_stage,
        "age_days": round(age_days, 1),
        "gap_days": threshold,
    }


def _last_event_ts(domain_key: str, storyline_id: int) -> datetime | None:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT MAX(COALESCE(actual_event_date, created_at))
                    FROM public.chronological_events
                    WHERE storyline_id = %s
                    """,
                    (storyline_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    ts = row[0]
                    if getattr(ts, "tzinfo", None) is None:
                        return ts.replace(tzinfo=timezone.utc)
                    return ts
                cur.execute(
                    f"""
                    SELECT COALESCE(material_updated_at, updated_at, created_at)
                    FROM {schema}.storylines WHERE id = %s
                    """,
                    (storyline_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    ts = row[0]
                    if getattr(ts, "tzinfo", None) is None:
                        return ts.replace(tzinfo=timezone.utc)
                    return ts
    except Exception as e:
        logger.debug("_last_event_ts: %s", e)
    return None


def enqueue_gap_ticket(gap: dict[str, Any], *, auto_queue: bool = False) -> dict[str, Any]:
    """Enqueue stimulus RAG ticket for a detected narrative gap."""
    from services.rag_evidence_pull_service import enqueue_evidence_pull

    domain_key = gap["domain_key"]
    storyline_id = int(gap["storyline_id"])
    reason = (
        f"narrative_gap:pattern={gap.get('pattern')}"
        f":have={gap.get('current_stage')}:need={gap.get('missing_stage')}"
        f":age_days={gap.get('age_days')}"
    )
    source_type = "court_pdf" if domain_key == "legal" else "url_fetch"
    if domain_key in ("medicine",):
        source_type = "who_cdc"
    return enqueue_evidence_pull(
        domain_key=domain_key,
        storyline_id=storyline_id,
        interest_score=0.55,
        selection_reason=reason[:2000],
        auto_queue=auto_queue,
        source_type=source_type,
    )


def scan_narrative_gaps(
    *,
    domain_keys: list[str] | None = None,
    limit_per_domain: int = 40,
    gap_days: int | None = None,
    enqueue: bool = True,
    auto_queue: bool = False,
) -> dict[str, Any]:
    """Scan active storylines for typed-arc gaps; optionally enqueue tickets."""
    if not narrative_gap_enabled() and enqueue:
        # Allow dry detection even when flag off
        pass
    if not narrative_gap_enabled():
        return {"enabled": False, "gaps": 0, "enqueued": 0}

    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from shared.database.connection import get_db_connection_context

    domains = domain_keys or list(get_pipeline_active_domain_keys())
    stats: dict[str, Any] = {
        "enabled": True,
        "gaps": 0,
        "enqueued": 0,
        "skipped": 0,
        "by_domain": {},
    }
    threshold = gap_days if gap_days is not None else gap_days_threshold()

    for dk in domains:
        schema = resolve_domain_schema(dk)
        found: list[dict[str, Any]] = []
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.storylines
                        WHERE COALESCE(status, 'active') NOT IN ('archived', 'merged', 'deleted')
                          AND COALESCE(material_updated_at, updated_at, created_at)
                              < NOW() - (%s * INTERVAL '1 day')
                        ORDER BY COALESCE(material_updated_at, updated_at) DESC NULLS LAST
                        LIMIT %s
                        """,
                        (threshold, limit_per_domain),
                    )
                    ids = [int(r[0]) for r in (cur.fetchall() or [])]
        except Exception as e:
            logger.warning("scan_narrative_gaps list %s: %s", dk, e)
            continue

        for sid in ids:
            gap = detect_gap_for_storyline(dk, sid, gap_days=threshold)
            if not gap:
                stats["skipped"] += 1
                continue
            stats["gaps"] += 1
            found.append(gap)
            if enqueue:
                res = enqueue_gap_ticket(gap, auto_queue=auto_queue)
                if res.get("ok") and not res.get("duplicate"):
                    stats["enqueued"] += 1
        stats["by_domain"][dk] = {"gaps": len(found), "storylines_scanned": len(ids)}
    return stats
