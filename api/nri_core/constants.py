"""Re-export investigation triage constants (from legacy nri_resolution_config)."""

from config.nri_resolution_config import (
    BRIDGE_QA_OK_SIMILARITY,
    BRIDGE_QA_SUSPECT_SIMILARITY,
    GENERIC_FTM_CAPTIONS,
    PARKED_GENERIC_MENTIONS,
)

__all__ = [
    "BRIDGE_QA_OK_SIMILARITY",
    "BRIDGE_QA_SUSPECT_SIMILARITY",
    "GENERIC_FTM_CAPTIONS",
    "PARKED_GENERIC_MENTIONS",
]
