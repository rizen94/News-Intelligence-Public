"""Promotion gate — facts only after ran_survived."""

from __future__ import annotations

from nri_core.vault.validator.firewall import validate_promotion


def check_promotion(hypothesis_meta: dict) -> bool:
    result = validate_promotion(hypothesis_meta)
    return result.ok
