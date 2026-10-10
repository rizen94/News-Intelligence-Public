"""
Storyline lifecycle state machine (Phase 6 C2).

States: emerging → active → dormant → resolved | merged | split
Transitions driven by event velocity and centroid/title drift signals.
Persisted on quality_metrics.storyline_lifecycle (and optional status mirror).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool, env_float, env_int

logger = logging.getLogger(__name__)

LIFECYCLE_STATES = frozenset(
    {"emerging", "active", "dormant", "resolved", "merged", "split"}
)

# Allowed transitions (from → to)
_TRANSITIONS: dict[str, frozenset[str]] = {
    "emerging": frozenset({"active", "dormant", "merged", "resolved"}),
    "active": frozenset({"dormant", "resolved", "merged", "split"}),
    "dormant": frozenset({"active", "resolved", "merged"}),
    "resolved": frozenset({"active"}),  # rare reopen
    "merged": frozenset(),
    "split": frozenset({"active", "emerging"}),
}


def lifecycle_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("storyline_lifecycle", default=False):
            return True
    except Exception:
        pass
    return env_bool("STORYLINE_LIFECYCLE_ENABLED", False)


def dormant_days() -> int:
    return max(3, env_int("STORYLINE_LIFECYCLE_DORMANT_DAYS", 21))


def emerging_max_events() -> int:
    return max(1, env_int("STORYLINE_LIFECYCLE_EMERGING_MAX_EVENTS", 3))


def active_min_events() -> int:
    return max(2, env_int("STORYLINE_LIFECYCLE_ACTIVE_MIN_EVENTS", 4))


def can_transition(current: str, target: str) -> bool:
    cur = (current or "emerging").lower()
    tgt = (target or "").lower()
    if tgt not in LIFECYCLE_STATES:
        return False
    if cur == tgt:
        return True
    return tgt in _TRANSITIONS.get(cur, frozenset())


def infer_lifecycle_transition(
    *,
    current: str | None,
    event_count: int,
    days_since_last_event: float | None,
    article_count: int = 0,
    drift_score: float | None = None,
    explicit_terminal: str | None = None,
) -> str:
    """
    Pure rule function: compute next lifecycle state from velocity/drift signals.
    """
    cur = (current or "emerging").lower()
    if explicit_terminal in ("merged", "split", "resolved"):
        if can_transition(cur, explicit_terminal):
            return explicit_terminal
    if cur in ("merged",):
        return cur

    dormant_n = float(dormant_days())
    days = days_since_last_event

    # Resolved: long dormant + low velocity
    if days is not None and days >= dormant_n * 2 and event_count >= 1:
        if can_transition(cur, "resolved"):
            return "resolved"

    # Dormant: quiet beyond threshold
    if days is not None and days >= dormant_n:
        if can_transition(cur, "dormant"):
            return "dormant"

    # Active: enough events / recent activity
    if event_count >= active_min_events() or (
        days is not None and days < dormant_n / 2 and event_count >= 2
    ):
        if can_transition(cur, "active"):
            return "active"

    # Emerging: few events / young
    if event_count <= emerging_max_events() and article_count < 8:
        if can_transition(cur, "emerging"):
            return "emerging"

    # Drift high while active → stay active (split is operator/explicit)
    if drift_score is not None and drift_score >= env_float(
        "STORYLINE_LIFECYCLE_SPLIT_DRIFT", 0.85
    ):
        if can_transition(cur, "split") and explicit_terminal == "split":
            return "split"

    return cur if cur in LIFECYCLE_STATES else "emerging"


def get_storyline_lifecycle(
    domain_key: str,
    storyline_id: int,
) -> dict[str, Any]:
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT quality_metrics, COALESCE(status, 'active'),
                           COALESCE(material_updated_at, updated_at, created_at)
                    FROM {schema}.storylines WHERE id = %s
                    """,
                    (storyline_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {"error": "not_found"}
                qm = row[0] if isinstance(row[0], dict) else {}
                if isinstance(row[0], str):
                    try:
                        qm = json.loads(row[0])
                    except Exception:
                        qm = {}
                cur.execute(
                    """
                    SELECT COUNT(*)::int,
                           MAX(COALESCE(actual_event_date, created_at))
                    FROM public.chronological_events
                    WHERE storyline_id = %s
                    """,
                    (storyline_id,),
                )
                ec, last_ts = cur.fetchone()
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                    """,
                    (storyline_id,),
                )
                ac = int(cur.fetchone()[0] or 0)

        days = None
        if last_ts:
            ts = last_ts
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.replace(tzinfo=timezone.utc)
            days = (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0

        current = (qm or {}).get("storyline_lifecycle") or "emerging"
        nxt = infer_lifecycle_transition(
            current=current,
            event_count=int(ec or 0),
            days_since_last_event=days,
            article_count=ac,
        )
        return {
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "lifecycle": current,
            "suggested": nxt,
            "event_count": int(ec or 0),
            "article_count": ac,
            "days_since_last_event": round(days, 1) if days is not None else None,
            "enabled": lifecycle_enabled(),
        }
    except Exception as e:
        logger.warning("get_storyline_lifecycle: %s", e)
        return {"error": str(e)[:200]}


def apply_lifecycle_transition(
    domain_key: str,
    storyline_id: int,
    *,
    target: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Compute (and optionally persist) lifecycle transition."""
    info = get_storyline_lifecycle(domain_key, storyline_id)
    if info.get("error"):
        return info
    nxt = (target or info.get("suggested") or info.get("lifecycle") or "emerging").lower()
    cur = (info.get("lifecycle") or "emerging").lower()
    if not can_transition(cur, nxt):
        return {**info, "ok": False, "error": f"illegal_transition:{cur}->{nxt}"}
    if persist and lifecycle_enabled() and nxt != cur:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(domain_key)
        patch = {
            "storyline_lifecycle": nxt,
            "storyline_lifecycle_at": datetime.now(timezone.utc).isoformat(),
            "storyline_lifecycle_from": cur,
        }
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur_db:
                    cur_db.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET quality_metrics = COALESCE(quality_metrics, '{{}}'::jsonb) || %s::jsonb,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(patch), storyline_id),
                    )
                conn.commit()
        except Exception as e:
            logger.warning("apply_lifecycle_transition persist: %s", e)
            return {**info, "ok": False, "error": str(e)[:200]}
    return {**info, "lifecycle": nxt, "ok": True, "transitioned": nxt != cur}
