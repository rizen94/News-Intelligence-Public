"""
Batch drain helpers for AutomationManager GPU/LLM phases.

Env per phase: ``{PHASE_UPPER}_RUN_BUDGET_SECONDS``. **0 = unlimited** (drain until
idle or stall). Non-zero values are optional circuit breakers only.
"""

from __future__ import annotations

import logging
import time

from config.runtime import env_str

logger = logging.getLogger(__name__)


def _governance_run_budgets() -> dict:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("pipeline_controller") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def phase_run_budget_seconds(phase: str, default: int = 0) -> int:
    """
    Wall-clock budget for one scheduled automation task invocation.

    Returns 0 for unlimited drain (steady-state default). Positive values cap runtime
    as an emergency circuit breaker only.
    """
    key = f"{(phase or '').strip().upper()}_RUN_BUDGET_SECONDS"
    try:
        raw = env_str(key, "")
        if raw is not None and str(raw).strip() != "":
            val = int(raw)
            if val <= 0:
                return 0
            return max(60, min(14_400, val))
    except (TypeError, ValueError):
        pass
    gov_key = f"{(phase or '').strip().lower().replace('-', '_')}_run_budget_seconds"
    try:
        gov_val = _governance_run_budgets().get(gov_key)
        if gov_val is not None and str(gov_val).strip() != "":
            val = int(gov_val)
            if val <= 0:
                return 0
            return max(60, min(14_400, val))
    except (TypeError, ValueError):
        pass
    if (phase or "").strip().lower().replace("-", "_") == "claim_extraction":
        try:
            raw = env_str("CLAIM_EXTRACTION_DRAIN_MAX_SECONDS", "")
            if raw is not None and str(raw).strip() != "":
                val = int(float(raw))
                if val <= 0:
                    return 0
                return max(60, min(14_400, val))
        except (TypeError, ValueError):
            pass
        gov_ce = _governance_run_budgets().get("claim_extraction_drain_max_seconds")
        if gov_ce is not None:
            try:
                val = int(gov_ce)
                if val <= 0:
                    return 0
                return max(60, min(14_400, val))
            except (TypeError, ValueError):
                pass
    if default <= 0:
        return 0
    return max(60, min(14_400, int(default)))


def phase_batch_limit(phase: str, default: int, *, env_suffix: str = "ARTICLES_PER_DOMAIN") -> int:
    """Per-round batch size (articles/contexts) for a phase."""
    p = (phase or "").strip().upper()
    for key in (f"{p}_{env_suffix}", f"{p}_BATCH_LIMIT"):
        try:
            raw = env_str(key, "")
            if raw is not None and str(raw).strip() != "":
                return max(1, min(500, int(raw)))
        except (TypeError, ValueError):
            pass
    return max(1, min(500, int(default)))


def drain_stall_round_limit() -> int:
    """Consecutive zero-progress rounds before yielding (pending must remain > 0)."""
    try:
        return max(1, min(50, int(env_str("PIPELINE_DRAIN_STALL_ROUNDS", "3"))))
    except (TypeError, ValueError):
        return 3


class RunBudget:
    """Monotonic deadline for drain loops. seconds=0 means unlimited."""

    def __init__(self, seconds: int) -> None:
        sec = int(seconds or 0)
        self._unlimited = sec <= 0
        self._deadline = time.monotonic() + float(sec) if not self._unlimited else 0.0

    def expired(self) -> bool:
        if self._unlimited:
            return False
        return time.monotonic() >= self._deadline

    @property
    def unlimited(self) -> bool:
        return self._unlimited

    @property
    def remaining(self) -> float:
        if self._unlimited:
            return float("inf")
        return max(0.0, self._deadline - time.monotonic())


class DrainStallTracker:
    """Stop drain after N consecutive rounds with zero progress while work remains."""

    def __init__(self, *, max_stall_rounds: int | None = None) -> None:
        self._max = max_stall_rounds if max_stall_rounds is not None else drain_stall_round_limit()
        self._stall_count = 0

    def record_round(self, *, processed: int, had_pending: bool) -> bool:
        """
        Returns True if drain should stop (stall detected).
        """
        if processed > 0:
            self._stall_count = 0
            return False
        if not had_pending:
            self._stall_count = 0
            return False
        self._stall_count += 1
        if self._stall_count >= self._max:
            logger.warning(
                "pipeline drain stall: %s consecutive zero-progress rounds with pending work",
                self._stall_count,
            )
            return True
        return False
