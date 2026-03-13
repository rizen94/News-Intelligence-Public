"""
Resource Governor — track LLM token and API call usage, enforce budgets.
Used by OrchestratorCoordinator to decide if a task can run (can_run, remaining_llm_budget).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)

RESOURCE_LLM_TOKENS = "llm_tokens"
RESOURCE_API_CALLS = "api_calls"


class ResourceGovernor:
    """
    Tracks resource usage and exposes budget checks. Reads config for
    daily_llm_tokens and max_api_calls_per_hour; persists usage via orchestrator_state.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        if config is None:
            try:
                from config.orchestrator_governance import get_orchestrator_governance_config
                config = get_orchestrator_governance_config()
            except Exception as e:
                logger.warning("ResourceGovernor: config load failed: %s", e)
                config = {}
        self._config = config
        resources = config.get("resources") or {}
        self._daily_llm_tokens = int(resources.get("daily_llm_tokens", 100000))
        self._max_api_calls_per_hour = int(resources.get("max_api_calls_per_hour", 1000))

    def record_usage(self, resource_type: str, amount: float, limit: float | None = None) -> None:
        """Record usage snapshot (e.g. llm_tokens or api_calls)."""
        try:
            from . import orchestrator_state
            orchestrator_state.record_resource_usage(
                resource_type=resource_type,
                usage=amount,
                limit_value=limit,
            )
        except Exception as e:
            logger.warning("ResourceGovernor record_usage failed: %s", e)

    def remaining_llm_budget(self) -> float:
        """Remaining LLM token budget for today (UTC)."""
        try:
            from . import orchestrator_state
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            used = orchestrator_state.get_resource_usage_sum(RESOURCE_LLM_TOKENS, today_start)
            return max(0.0, float(self._daily_llm_tokens) - used)
        except Exception as e:
            logger.warning("ResourceGovernor remaining_llm_budget failed: %s", e)
            return float(self._daily_llm_tokens)

    def api_calls_used_last_hour(self) -> float:
        """Sum of api_calls usage in the last 60 minutes."""
        try:
            from . import orchestrator_state
            now = datetime.now(timezone.utc)
            since = (now - timedelta(hours=1)).isoformat()
            return orchestrator_state.get_resource_usage_sum(RESOURCE_API_CALLS, since)
        except Exception as e:
            logger.warning("ResourceGovernor api_calls_used_last_hour failed: %s", e)
            return 0.0

    def can_run(self, task_type: str) -> bool:
        """
        True if there is budget to run the task. High-priority tasks can be
        allowed even when over budget (caller can pass priority).
        task_type: e.g. "collection", "analysis", "processing".
        """
        # For Phase 2 we only check API rate; LLM budget can be checked for analysis tasks
        if task_type in ("analysis", "synthesis"):
            if self.remaining_llm_budget() <= 0:
                return False
        used = self.api_calls_used_last_hour()
        return used < self._max_api_calls_per_hour

    def get_budget_status(self) -> dict[str, Any]:
        """Current budget status for API/metrics."""
        return {
            "daily_llm_tokens_limit": self._daily_llm_tokens,
            "remaining_llm_budget": self.remaining_llm_budget(),
            "max_api_calls_per_hour": self._max_api_calls_per_hour,
            "api_calls_used_last_hour": self.api_calls_used_last_hour(),
        }
