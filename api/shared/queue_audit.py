"""
Independent SQL cross-checks for Monitor phase ``pending_records`` (Total queue).

Not additive totals — each phase is verified against its automation/backlog_metrics definition.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.pipeline_queue_vocabulary import (
    ACTIONABLE_UNIFIED_INTAKE,
    INVENTORY_MISSING_PASS,
    LEGACY_BACKFILL_ELIGIBLE,
    QUEUE_DEPTH,
    SPINE_QUEUE_DEPTH,
)

logger = logging.getLogger(__name__)


def build_queue_audit(pending: dict[str, int]) -> dict[str, Any]:
    """Return per-phase verification payloads for Monitor queue audit."""
    phases: dict[str, Any] = {}

    try:
        from shared.pipeline_queue_counts import get_unified_intake_breakdown, verify_unified_intake_alignment

        breakdown = get_unified_intake_breakdown()
        alignment = verify_unified_intake_alignment(pending)
        actionable = int(breakdown["actionable_unified_intake"])
        monitor = int(pending.get("unified_intake_extraction") or 0)
        matches = bool(alignment["matches_actionable_sql"])
        phases["unified_intake_extraction"] = {
            QUEUE_DEPTH: monitor,
            "monitor_pending": monitor,
            ACTIONABLE_UNIFIED_INTAKE: actionable,
            INVENTORY_MISSING_PASS: int(breakdown["inventory_missing_pass"]),
            "total_missing_unified_pass": int(breakdown["inventory_missing_pass"]),
            LEGACY_BACKFILL_ELIGIBLE: int(breakdown["legacy_backfill_eligible"]),
            SPINE_QUEUE_DEPTH: int(breakdown["spine_queue_depth"]),
            "matches_actionable_sql": matches,
            "matches_automation_sql": matches,
            "note": (
                "queue_depth = actionable_unified_intake (articles still needing unified LLM; "
                "legacy-complete rows excluded when legacy-aware backlog is on). "
                "spine_queue_depth is operational only and may exceed queue_depth."
            ),
        }
    except Exception as e:
        logger.debug("queue_audit unified_intake: %s", e)
        phases["unified_intake_extraction"] = {"error": str(e)[:200]}

    try:
        from services.backlog_metrics import _count_claim_extraction_backlog
        from services.claim_extraction_service import get_context_claim_backlog_stats

        cb = get_context_claim_backlog_stats()
        monitor = int(pending.get("claim_extraction") or 0)
        broad = int(cb.get("actionable_no_claims") or 0)
        automation = int(_count_claim_extraction_backlog() or 0)
        matches = monitor == automation
        phases["claim_extraction"] = {
            QUEUE_DEPTH: monitor,
            "monitor_pending": monitor,
            "automation_sql_recount": automation,
            "actionable_no_claims_broad": broad,
            "total_no_claims_inventory": int(cb.get("total_no_claims") or 0),
            "matches_actionable_sql": matches,
            "matches_automation_sql": matches,
            "note": (
                "queue_depth = automation pool (min text + pass-null + fusion gap-fill filter). "
                f"Broader actionable inventory without gap-fill: {broad:,}; "
                f"all contexts with zero claim rows: {int(cb.get('total_no_claims') or 0):,}."
            ),
        }
    except Exception as e:
        logger.debug("queue_audit claim_extraction: %s", e)
        phases["claim_extraction"] = {"error": str(e)[:200]}

    try:
        from services.backlog_metrics import _count_entity_profile_build_backlog

        monitor = int(pending.get("entity_profile_build") or 0)
        automation = int(_count_entity_profile_build_backlog() or 0)
        matches = monitor == automation
        phases["entity_profile_build"] = {
            QUEUE_DEPTH: monitor,
            "monitor_pending": monitor,
            "automation_sql_recount": automation,
            "matches_actionable_sql": matches,
            "matches_automation_sql": matches,
            "note": "queue_depth = profiles needing build with at least one context_entity_mention.",
        }
    except Exception as e:
        logger.debug("queue_audit entity_profile_build: %s", e)
        phases["entity_profile_build"] = {"error": str(e)[:200]}

    return {"phases": phases}
