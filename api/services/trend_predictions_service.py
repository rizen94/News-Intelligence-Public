"""
Trend and predictions API backend (P3). Thin layer over context/event data; extend with Learning Governor later.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def get_trend_analysis(
    domain: Optional[str] = None,
    time_window_days: int = 14,
    indicators: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Return trends (volume over time, direction) and optional leading_indicators.
    Uses intelligence.contexts and domain articles when available.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "trends": [], "leading_indicators": [], "error": "Database unavailable"}
    try:
        trends: List[Dict[str, Any]] = []
        leading_indicators: List[Dict[str, Any]] = []

        domain_clause = "AND domain_key = %s" if domain else ""
        args = [time_window_days]
        if domain:
            args.append(domain)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                FROM intelligence.contexts
                WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' * %s
                """ + domain_clause + """
                GROUP BY DATE(created_at)
                ORDER BY d
                """,
                tuple(args),
            )
            rows = cur.fetchall()
        conn.close()

        if rows:
            counts = [r[1] for r in rows]
            days = [str(r[0]) for r in rows]
            avg = sum(counts) / len(counts) if counts else 0
            recent = counts[-1] if counts else 0
            older = counts[0] if len(counts) > 1 else recent
            direction = "increasing" if recent > older else "decreasing" if recent < older else "stable"
            trends.append({
                "metric": "context_volume",
                "direction": direction,
                "daily_counts": [{"date": d, "count": c} for d, c in zip(days, counts)],
                "average_per_day": round(avg, 1),
                "window_days": time_window_days,
            })
            if direction != "stable" and abs(recent - older) / max(older, 1) > 0.2:
                leading_indicators.append({
                    "indicator": "context_volume_trend",
                    "signal": direction,
                    "confidence": 0.7,
                    "description": f"Context volume is {direction} over the last {time_window_days} days",
                })
        return {"success": True, "trends": trends, "leading_indicators": leading_indicators}
    except Exception as e:
        logger.warning("get_trend_analysis: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "trends": [], "leading_indicators": [], "error": str(e)}


def get_predictions(
    domain: str,
    entity_id: Optional[int] = None,
    horizon_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Return predictions for domain (and optionally entity) from learned patterns and decision history.
    When no patterns exist yet, returns a single fallback prediction so callers always get a useful response.
    """
    horizon = horizon_days or 7
    predictions: List[Dict[str, Any]] = []
    based_on: List[str] = ["decision_history", "learned_patterns"]
    confidence = 0.0
    try:
        from services.orchestrator_state import get_learned_patterns
        patterns = get_learned_patterns("source_patterns", limit=1)
        pattern = patterns[0] if patterns else None
        if pattern and pattern.get("pattern_data"):
            success_rate = pattern["pattern_data"].get("success_rate")
            if success_rate is not None:
                confidence = float(success_rate)
                predictions.append({
                    "type": "collection_quality",
                    "horizon_days": horizon,
                    "summary": "Collection success rate from recent patterns",
                    "confidence": round(confidence, 2),
                })
    except Exception as e:
        logger.debug("get_predictions learned_pattern: %s", e)
    if not predictions:
        predictions.append({
            "type": "collection_quality",
            "horizon_days": horizon,
            "summary": "No predictions yet; collection patterns will appear after more orchestrator runs.",
            "confidence": 0.0,
        })
    return {
        "success": True,
        "predictions": predictions,
        "confidence": round(confidence, 2),
        "based_on": based_on,
        "domain": domain,
    }
