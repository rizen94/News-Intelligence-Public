"""NARRATIVE_SOURCE_STAGE_PATCH v1 — assembly allow-list and stage tags."""

from __future__ import annotations

import logging
import os
from typing import Any

from api.config.runtime import env_bool, env_str

logger = logging.getLogger(__name__)

PATCH_ENV = "NARRATIVE_SOURCE_STAGE_PATCH"
FEATURE_KEY = "narrative_source_stage_patch"


def narrative_source_stage_patch_enabled() -> bool:
    if env_str(PATCH_ENV, "").strip().lower() in ("1", "true", "v1", "yes", "on"):
        return True
    try:
        from api.config.feature_registry import is_feature_enabled

        return bool(is_feature_enabled(FEATURE_KEY, default=False))
    except Exception:
        return False


def assembly_operator_override() -> bool:
    """Allow discovery save + proactive promote when operator explicitly overrides."""
    return env_bool("STORYLINE_ASSEMBLY_OPERATOR_OVERRIDE", False)


def assembly_default_kwargs() -> dict[str, Any]:
    """Keyword overrides for run_storyline_assembly_for_domain when patch v1 is on."""
    if not narrative_source_stage_patch_enabled():
        return {}
    override = assembly_operator_override()
    return {
        "run_proactive": True,
        "run_discovery": override,
        "run_automation": True,
        "discovery_save_to_db": override,
        "run_eel_reconcile": True,
        "assembly_stage": "S4",
        # Dual-write is env-only (STORYLINE_ARTICLES_DUAL_WRITE); not enabled by patch.
    }


def assembly_step_log(domain_key: str, step: str, *, stage: str = "S4") -> None:
    if narrative_source_stage_patch_enabled():
        logger.info(
            "assembly_stage=%s step=%s domain=%s patch=v1",
            stage,
            step,
            domain_key,
        )