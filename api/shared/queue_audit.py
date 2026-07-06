"""
Independent SQL cross-checks for Monitor phase ``pending_records`` (Total queue).

Not additive totals — each phase is verified against its automation/backlog_metrics definition.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_queue_audit(pending: dict[str, int]) -> dict[str, Any]:
    """Return per-phase verification payloads for Monitor queue audit."""
    phases: dict[str, Any] = {}

    try:
        from shared.unified_intake_backlog import get_unified_intake_backlog_stats

        stats = get_unified_intake_backlog_stats()
        actionable = int(stats.get("actionable_unified_intake") or 0)
        monitor = int(pending.get("unified_intake_extraction") or 0)
        phases["unified_intake_extraction"] = {
            "monitor_pending": monitor,
            "actionable_unified_intake": actionable,
            "total_missing_unified_pass": int(stats.get("total_missing_unified_pass") or 0),
            "legacy_backfill_eligible": int(stats.get("legacy_backfill_eligible") or 0),
            "matches_automation_sql": monitor == actionable,
            "note": (
                "Total queue = actionable_unified_intake (articles still needing unified LLM; "
                "legacy-complete rows excluded when legacy-aware backlog is on)."
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
        phases["claim_extraction"] = {
            "monitor_pending": monitor,
            "automation_sql_recount": automation,
            "actionable_no_claims_broad": broad,
            "total_no_claims_inventory": int(cb.get("total_no_claims") or 0),
            "matches_automation_sql": monitor == automation,
            "note": (
                "Total queue = automation pool (min text + pass-null + fusion gap-fill filter). "
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
        phases["entity_profile_build"] = {
            "monitor_pending": monitor,
            "automation_sql_recount": automation,
            "matches_automation_sql": monitor == automation,
            "note": "Total queue = profiles needing build with at least one context_entity_mention.",
        }
    except Exception as e:
        logger.debug("queue_audit entity_profile_build: %s", e)
        phases["entity_profile_build"] = {"error": str(e)[:200]}

    return {"phases": phases}
