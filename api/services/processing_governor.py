"""
Processing Governor — delegates to AutomationManager and FinanceOrchestrator.
Recommends next processing action (phase + domain/storyline) using last run times,
user guidance (watchlist, automation storylines), and importance. Value-based
prioritization: watchlist > high importance > scheduled.
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
    """
    Delegates to existing AutomationManager (phases) and FinanceOrchestrator (analysis).
    Callers pass get_automation and get_finance_orchestrator so the governor
    can trigger or query without holding app references.
    """

    def __init__(
        self,
        *,
        get_automation: Callable[[], Any] | None = None,
        get_finance_orchestrator: Callable[[], Any] | None = None,
    ):
        self._get_automation = get_automation
        self._get_finance_orchestrator = get_finance_orchestrator

    def get_processing_status(self) -> dict[str, Any]:
        """Summary of automation and finance processing state for API."""
        out: dict[str, Any] = {"automation": None, "finance": None}
        try:
            if self._get_automation:
                automation = self._get_automation()
                if automation and hasattr(automation, "get_status"):
                    out["automation"] = automation.get_status()
                elif automation and hasattr(automation, "is_running"):
                    out["automation"] = {"running": automation.is_running}
        except Exception as e:
            logger.warning("ProcessingGovernor get_automation status failed: %s", e)
        try:
            if self._get_finance_orchestrator:
                orch = self._get_finance_orchestrator()
                if orch and hasattr(orch, "get_schedule_status"):
                    out["finance"] = {"schedule_status": orch.get_schedule_status()}
        except Exception as e:
            logger.warning("ProcessingGovernor get_finance status failed: %s", e)
        return out

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

    def recommend_next_processing(
        self,
        state: dict[str, Any],
        resource_ok: bool,
        *,
        get_db_connection: Callable[[], Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Recommend one next processing action (phase, domain?, storyline_id?) or None.
        Uses state["last_processing_times"], config processing.phases, and user guidance.
        priority: watchlist > high_importance > scheduled.
        """
        if not resource_ok:
            return None
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config

            config = get_orchestrator_governance_config()
            phases_cfg = (config.get("processing") or {}).get("phases") or {}
            if not phases_cfg:
                return None
        except Exception as e:
            logger.debug("ProcessingGovernor recommend config failed: %s", e)
            return None
        last_times = state.get("last_processing_times") or {}
        now = datetime.now(timezone.utc)
        user_guidance = {}
        if get_db_connection:
            try:
                from services.user_guidance_service import get_user_guidance

                user_guidance = get_user_guidance(get_db_connection)
            except Exception as e:
                logger.debug("ProcessingGovernor user_guidance failed: %s", e)
        watchlist_ids = [
            (d, int(sid)) for d, sid in user_guidance.get("watchlist_storyline_ids", [])
        ]
        automation_storylines = user_guidance.get("automation_storylines", [])

        candidates: list[tuple[float, str, dict[str, Any]]] = []  # (priority_sort, key, action)

        for phase_name, phase_spec in phases_cfg.items():
            if not isinstance(phase_spec, dict):
                continue
            interval = int(phase_spec.get("interval_seconds") or 1200)
            scope = phase_spec.get("scope")
            if scope == "domain":
                from shared.domain_registry import get_pipeline_schema_names_active

                for domain in get_pipeline_schema_names_active():
                    key = _processing_state_key(phase_name, domain=domain)
                    last = last_times.get(key)
                    if last:
                        try:
                            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                            if (now - last_dt).total_seconds() < interval:
                                continue
                        except (ValueError, TypeError):
                            pass
                    priority = 1.0
                    candidates.append(
                        (
                            priority,
                            key,
                            {
                                "phase": phase_name,
                                "domain": domain,
                                "storyline_id": None,
                                "priority": "scheduled",
                            },
                        )
                    )
            elif scope == "storyline":
                from services.user_guidance_service import compute_storyline_importance

                for s in automation_storylines:
                    sid = s.get("id")
                    domain = s.get("domain")
                    if not sid or not domain:
                        continue
                    key = _processing_state_key(phase_name, domain=domain, storyline_id=sid)
                    last = last_times.get(key)
                    due = True
                    if last:
                        try:
                            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                            freq_hours = s.get("automation_frequency_hours") or 24
                            if (now - last_dt).total_seconds() < freq_hours * 3600:
                                due = False
                        except (ValueError, TypeError):
                            pass
                    if not due:
                        continue
                    imp = compute_storyline_importance(
                        sid,
                        domain,
                        watchlist_ids=watchlist_ids,
                        automation_storylines=automation_storylines,
                    )
                    priority = 2.0 if (domain, sid) in watchlist_ids else (1.0 + imp)
                    candidates.append(
                        (
                            priority,
                            key,
                            {
                                "phase": phase_name,
                                "domain": domain,
                                "storyline_id": sid,
                                "priority": "watchlist"
                                if (domain, sid) in watchlist_ids
                                else "scheduled",
                            },
                        )
                    )
            else:
                key = _processing_state_key(phase_name)
                last = last_times.get(key)
                if last:
                    try:
                        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                        if (now - last_dt).total_seconds() < interval:
                            continue
                    except (ValueError, TypeError):
                        pass
                candidates.append(
                    (
                        1.0,
                        key,
                        {
                            "phase": phase_name,
                            "domain": None,
                            "storyline_id": None,
                            "priority": "scheduled",
                        },
                    )
                )

        if not candidates:
            return None
        # Optional: boost priority for phases with higher extraction quality (from extraction_metrics)
        try:
            from services.quality_feedback_service import get_extraction_metrics

            metrics_result = get_extraction_metrics(since_days=30)
            if metrics_result.get("success") and metrics_result.get("metrics"):
                phase_quality: dict[str, float] = {}
                for m in metrics_result.get("metrics", []):
                    phase_name = m.get("phase") or "claim_extraction"
                    avg = m.get("avg_accuracy_score")
                    if avg is not None and phase_name:
                        phase_quality[phase_name] = float(avg)
                if phase_quality:
                    for i, (pri, key, action) in enumerate(candidates):
                        phase = action.get("phase")
                        boost = phase_quality.get(phase, 0.5)
                        if boost > 0.7:
                            candidates[i] = (pri + 0.1, key, action)
        except Exception as e:
            logger.debug("ProcessingGovernor extraction_metrics boost failed: %s", e)
        candidates.sort(key=lambda x: (-x[0], x[1]))
        return candidates[0][2]

    def record_processing_result(
        self,
        phase: str,
        domain: str | None = None,
        storyline_id: int | None = None,
        success: bool = True,
    ) -> None:
        """Update last_processing_times in orchestrator state and persist."""
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
