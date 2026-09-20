"""Promotion validation for hypothesis vault writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PromotionResult:
    ok: bool
    reason: str = ""


def validate_promotion(hypothesis_meta: dict[str, Any]) -> PromotionResult:
    """Facts may promote only after a hypothesis survived falsification."""
    meta = hypothesis_meta or {}
    if meta.get("status") == "promoted" and not meta.get("ran_survived"):
        return PromotionResult(ok=False, reason="promoted without ran_survived")
    return PromotionResult(ok=True)
