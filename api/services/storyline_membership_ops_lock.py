"""
Membership ops lock — freeze silent auto-attach while narrative finish / core prune run.

Stored on ``{schema}.storylines.quality_metrics`` as:
  membership_frozen_until: ISO timestamptz
  membership_freeze_reason: short tag (narrative_finisher | core_prune | …)

Attach / discovery paths must call ``is_membership_frozen`` (or ``storyline_membership_frozen``)
and skip silent auto-add (prefer suggest-only / skip) while active.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_FREEZE_UNTIL_KEY = "membership_frozen_until"
_FREEZE_REASON_KEY = "membership_freeze_reason"
_DEFAULT_TTL_HOURS = 2.0


def _parse_metrics(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _parse_until(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_membership_frozen(
    quality_metrics: Any,
    *,
    now: datetime | None = None,
) -> tuple[bool, str | None]:
    """
    Return (frozen, reason) from quality_metrics payload.

    Stale / missing until → not frozen.
    """
    metrics = _parse_metrics(quality_metrics)
    until = _parse_until(metrics.get(_FREEZE_UNTIL_KEY))
    if until is None:
        return False, None
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    if clock >= until:
        return False, None
    reason = metrics.get(_FREEZE_REASON_KEY)
    return True, str(reason) if reason else "membership_ops"


def membership_freeze_patch(
    reason: str,
    *,
    ttl_hours: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """JSONB merge patch to set the freeze."""
    from config.runtime import env_float

    hours = float(
        ttl_hours
        if ttl_hours is not None
        else env_float("STORYLINE_MEMBERSHIP_FREEZE_TTL_HOURS", _DEFAULT_TTL_HOURS)
    )
    hours = max(0.25, min(12.0, hours))
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    until = clock + timedelta(hours=hours)
    return {
        _FREEZE_UNTIL_KEY: until.isoformat(),
        _FREEZE_REASON_KEY: (reason or "membership_ops")[:80],
    }


def membership_unfreeze_patch() -> dict[str, Any]:
    """JSONB merge patch to clear the freeze (nulls clear via || in callers that use jsonb_strip_nulls)."""
    return {
        _FREEZE_UNTIL_KEY: None,
        _FREEZE_REASON_KEY: None,
    }


def set_membership_freeze(
    schema: str,
    storyline_id: int,
    reason: str,
    *,
    ttl_hours: float | None = None,
    conn=None,
) -> bool:
    """Persist freeze on storyline quality_metrics. Returns True on success."""
    patch = membership_freeze_patch(reason, ttl_hours=ttl_hours)
    return _merge_quality_metrics(schema, storyline_id, patch, conn=conn, clear_nulls=False)


def clear_membership_freeze(
    schema: str,
    storyline_id: int,
    *,
    conn=None,
) -> bool:
    """Clear freeze keys from quality_metrics."""
    return _merge_quality_metrics(
        schema,
        storyline_id,
        membership_unfreeze_patch(),
        conn=conn,
        clear_nulls=True,
    )


def _merge_quality_metrics(
    schema: str,
    storyline_id: int,
    patch: dict[str, Any],
    *,
    conn=None,
    clear_nulls: bool,
) -> bool:
    own_conn = conn is None
    db = conn or get_db_connection()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            if clear_nulls:
                # Strip freeze keys explicitly (jsonb || null does not remove keys)
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET quality_metrics = COALESCE(quality_metrics, '{{}}'::jsonb)
                          - '{_FREEZE_UNTIL_KEY}' - '{_FREEZE_REASON_KEY}',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (storyline_id,),
                )
            else:
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET quality_metrics = COALESCE(quality_metrics, '{{}}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(patch), storyline_id),
                )
        if own_conn:
            db.commit()
        return True
    except Exception as e:
        logger.warning(
            "membership freeze merge failed schema=%s storyline=%s: %s",
            schema,
            storyline_id,
            e,
        )
        if own_conn:
            try:
                db.rollback()
            except Exception:
                pass
        return False
    finally:
        if own_conn and db:
            try:
                db.close()
            except Exception:
                pass


def storyline_membership_frozen(
    schema: str,
    storyline_id: int,
    *,
    conn=None,
) -> tuple[bool, str | None]:
    """Load quality_metrics and evaluate freeze."""
    own_conn = conn is None
    db = conn or get_db_connection()
    if not db:
        return False, None
    try:
        with db.cursor() as cur:
            cur.execute(
                f"""
                SELECT quality_metrics FROM {schema}.storylines WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                return False, None
            return is_membership_frozen(row[0])
    except Exception as e:
        logger.debug("storyline_membership_frozen read failed: %s", e)
        return False, None
    finally:
        if own_conn and db:
            try:
                db.close()
            except Exception:
                pass


def refinement_job_holds_membership(
    domain_key: str,
    storyline_id: int,
    *,
    conn=None,
) -> bool:
    """
    True when content_refinement_queue has narrative_finisher (or related)
    in processing for this storyline — belt-and-suspenders with quality_metrics freeze.
    """
    own_conn = conn is None
    db = conn or get_db_connection()
    if not db:
        return False
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM intelligence.content_refinement_queue
                WHERE domain_key = %s
                  AND storyline_id = %s
                  AND status = 'processing'
                  AND job_type IN (
                    'narrative_finisher',
                    'comprehensive_rag',
                    'headline_refiner'
                  )
                LIMIT 1
                """,
                (domain_key, storyline_id),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.debug("refinement_job_holds_membership: %s", e)
        return False
    finally:
        if own_conn and db:
            try:
                db.close()
            except Exception:
                pass


@contextmanager
def membership_ops_freeze(
    schema: str,
    storyline_id: int,
    reason: str,
    *,
    ttl_hours: float | None = None,
) -> Iterator[None]:
    """Context manager: set freeze on enter, clear on exit (best-effort)."""
    set_membership_freeze(
        schema, storyline_id, reason, ttl_hours=ttl_hours
    )
    try:
        yield
    finally:
        clear_membership_freeze(schema, storyline_id)
