"""
Adaptive signal admission threshold governor (v10.1).

Reads intake metrics and adjusts intelligence.pipeline_admission_config.full_min_quality
within orchestrator_governance target_full_llm_ratio band.
"""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_float

logger = logging.getLogger(__name__)

_FLOOR = 0.35
_CEILING = 0.60
_STEP = 0.02


def _governance_band() -> tuple[float, float]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        gov = get_orchestrator_governance_config()
        sf = gov.get("signal_first") or {}
        lo = float(sf.get("target_full_llm_ratio_min", 0.15))
        hi = float(sf.get("target_full_llm_ratio_max", 0.35))
        return max(0.05, lo), max(lo, hi)
    except Exception:
        return 0.15, 0.35


def get_persisted_full_min_quality() -> float | None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT full_min_quality
                    FROM intelligence.pipeline_admission_config
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
        if row and row[0] is not None:
            return max(0.0, min(1.0, float(row[0])))
    except Exception as exc:
        logger.debug("get_persisted_full_min_quality: %s", exc)
    return None


def _intake_net_growth_metrics() -> dict[str, Any]:
    """Reuse intake_processing_ratio domain loop for 7d net growth estimate."""
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_schema_names_active

    created_7d = 0
    enriched_7d = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for schema in get_schema_names_active():
                try:
                    cur.execute(
                        f"""
                        SELECT
                            COUNT(*) FILTER (
                                WHERE created_at >= NOW() - INTERVAL '7 days'
                            )::bigint,
                            COUNT(*) FILTER (
                                WHERE enrichment_status = 'enriched'
                                  AND updated_at >= NOW() - INTERVAL '7 days'
                            )::bigint
                        FROM {schema}.articles
                        """
                    )
                    row = cur.fetchone()
                    if row:
                        created_7d += int(row[0] or 0)
                        enriched_7d += int(row[1] or 0)
                except Exception:
                    continue
    net = created_7d - enriched_7d
    return {
        "created_7d": created_7d,
        "enriched_7d": enriched_7d,
        "net_growth_7d": net,
        "net_growth_per_day": net / 7.0 if created_7d else 0.0,
    }


def adjust_admission_threshold(*, dry_run: bool = False) -> dict[str, Any]:
    """
    If net_growth > 0 for sustained window, raise threshold; if shrinking, lower.
    Updates intelligence.pipeline_admission_config.
    """
    metrics = _intake_net_growth_metrics()
    net = float(metrics["net_growth_7d"])
    current = get_persisted_full_min_quality()
    if current is None:
        current = env_float("ARTICLE_SIGNAL_FULL_MIN_QUALITY", 0.45)

    growing = net > 0
    shrinking = net < 0
    new_threshold = current
    action = "hold"

    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT consecutive_growth_days, consecutive_shrink_days
                    FROM intelligence.pipeline_admission_config
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
                growth_days = int(row[0] or 0) if row else 0
                shrink_days = int(row[1] or 0) if row else 0

                if growing:
                    growth_days += 1
                    shrink_days = 0
                elif shrinking:
                    shrink_days += 1
                    growth_days = 0
                else:
                    growth_days = 0
                    shrink_days = 0

                if growth_days >= 3 and current < _CEILING:
                    new_threshold = min(_CEILING, round(current + _STEP, 3))
                    action = "tighten"
                    growth_days = 0
                elif shrink_days >= 3 and current > _FLOOR:
                    new_threshold = max(_FLOOR, round(current - _STEP, 3))
                    action = "loosen"
                    shrink_days = 0

                ratio_lo, ratio_hi = _governance_band()
                result = {
                    "action": action,
                    "previous_threshold": current,
                    "new_threshold": new_threshold,
                    "net_growth_7d": net,
                    "target_ratio_band": [ratio_lo, ratio_hi],
                    "dry_run": dry_run,
                }

                if not dry_run:
                    cur.execute(
                        """
                        UPDATE intelligence.pipeline_admission_config
                        SET full_min_quality = %s,
                            target_ratio_min = %s,
                            target_ratio_max = %s,
                            net_growth_7d = %s,
                            consecutive_growth_days = %s,
                            consecutive_shrink_days = %s,
                            last_adjusted_at = CASE WHEN %s != %s THEN NOW() ELSE last_adjusted_at END,
                            updated_at = NOW()
                        WHERE id = 1
                        """,
                        (
                            new_threshold,
                            ratio_lo,
                            ratio_hi,
                            net,
                            growth_days,
                            shrink_days,
                            new_threshold,
                            current,
                        ),
                    )
                    conn.commit()
                return result
    except Exception as exc:
        logger.warning("adjust_admission_threshold failed: %s", exc)
        return {"action": "error", "error": str(exc), **metrics}

    return {"action": action, **metrics}
