"""
Processing Governor — finance analysis trigger and orchestrator run-history helpers.

Processing enqueue is owned by PipelineController (v10.1+). This module retains:
  - ``trigger_finance_analysis`` for OrchestratorCoordinator finance areas-of-interest
  - ``record_processing_result`` to persist last_processing_times in orchestrator state
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)


def _processing_state_key(
    phase: str, domain: str | None = None, storyline_id: int | None = None
) -> str:
    """Key for last_processing_times: phase, phase:domain, or phase:storyline:id."""
    if storyline_id is not None:
        return f"{phase}:storyline:{storyline_id}"
    if domain:
        return f"{phase}:{domain}"
    return phase


class ProcessingGovernor:
    """Finance analysis delegation + orchestrator processing timestamps."""

    def __init__(
        self,
        *,
        get_automation: Callable[[], Any] | None = None,
        get_finance_orchestrator: Callable[[], Any] | None = None,
    ):
        self._get_automation = get_automation
        self._get_finance_orchestrator = get_finance_orchestrator

    def trigger_finance_analysis(
        self,
        query: str,
        topic: str = "gold",
        *,
        priority: str = "medium",
    ) -> dict[str, Any] | None:
        """
        Submit a finance analysis task. Returns task_id and status or None on failure.
        priority: high (user/watchlist), medium, low.
        """
        try:
            if not self._get_finance_orchestrator:
                return None
            orch = self._get_finance_orchestrator()
            if not orch:
                return None
            from domains.finance.orchestrator_types import TaskPriority, TaskType

            priority_map = {
                "high": TaskPriority.high,
                "medium": TaskPriority.medium,
                "low": TaskPriority.low,
            }
            p = priority_map.get(priority, TaskPriority.medium)
            task_id = orch.submit_task(
                TaskType.analysis,
                {"query": query, "topic": topic},
                priority=p,
            )
            return {"task_id": task_id, "status": "queued", "priority": priority}
        except Exception as e:
            logger.warning("ProcessingGovernor trigger_finance_analysis failed: %s", e)
            return None

    def record_processing_result(
        self,
        phase: str,
        domain: str | None = None,
        storyline_id: int | None = None,
        success: bool = True,
    ) -> None:
        """Update last_processing_times in orchestrator state and persist."""
        del success  # reserved for future outcome-aware scheduling
        try:
            from . import orchestrator_state

            state = orchestrator_state.get_controller_state()
            last_times = state.get("last_processing_times") or {}
            key = _processing_state_key(phase, domain=domain, storyline_id=storyline_id)
            last_times[key] = datetime.now(timezone.utc).isoformat()
            state["last_processing_times"] = last_times
            orchestrator_state.save_controller_state(state)
        except Exception as e:
            logger.warning("ProcessingGovernor record_processing_result failed: %s", e)
