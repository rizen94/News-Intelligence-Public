"""
Finance domain — statistical engine for price analysis and validation.
"""

import logging

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


def price_change_pct(values: list[tuple[str, float]]) -> float | None:
    """
    Percent change from first to last observation.
    values: list of (date_str, value). Returns None if < 2 points.
    """
    if not values or len(values) < 2:
        return None
    first = values[0][1]
    last = values[-1][1]
    if first == 0:
        return None
    return 100.0 * (last - first) / first


def validate_range(
    value: float, min_val: float | None = None, max_val: float | None = None
) -> tuple[bool, str]:
    """
    Check value is within expected range.
    Returns (valid: bool, reason: str).
    """
    if min_val is not None and value < min_val:
        return False, f"value {value} below minimum {min_val}"
    if max_val is not None and value > max_val:
        return False, f"value {value} above maximum {max_val}"
    return True, "ok"


def latest_value(observations: list[dict]) -> float | None:
    """Extract latest value from observations (expect {'date': str, 'value': float})."""
    if not observations:
        return None
    sorted_obs = sorted(observations, key=lambda o: o.get("date", ""), reverse=True)
    for o in sorted_obs:
        v = o.get("value")
        if v is not None and v != "" and v != ".":
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None
