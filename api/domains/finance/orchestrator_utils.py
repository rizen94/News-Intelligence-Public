"""
Orchestrator utilities — DataResult normalization and evidence ledger helpers.
Bulletproof normalization between inconsistent source returns and orchestrator logic.
"""

import logging
from typing import Any

from shared.data_result import DataResult

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


def normalize_to_data_result(raw: Any, source_id: str = "") -> DataResult:
    """
    Normalize any source return to DataResult. Handles:
    - DataResult: passthrough
    - list: wrap as success with data
    - dict: wrap as success with data
    - None: failure
    - str (error message): failure
    - Exception: failure with message
    """
    if isinstance(raw, DataResult):
        return raw
    if raw is None:
        return DataResult.fail("Source returned None", "no_data")
    if isinstance(raw, list):
        return DataResult.ok(raw)
    if isinstance(raw, dict):
        return DataResult.ok(raw)
    if isinstance(raw, Exception):
        return DataResult.fail(str(raw), "network")
    if isinstance(raw, str):
        return DataResult.fail(raw, "unknown")
    # Fallback: wrap as success (e.g. int count)
    return DataResult.ok(raw)
