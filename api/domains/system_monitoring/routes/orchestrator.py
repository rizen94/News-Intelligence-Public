"""
Orchestrator coordination API — status, metrics, decision log, learning stats, manual override.
Used by OrchestratorCoordinator and governors. See docs/ORCHESTRATOR_DEVELOPMENT_PLAN.md.
"""

import logging
from typing import Any

from fastapi import APIRouter, Request, Query, Body

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/orchestrator",
    tags=["Orchestrator"],
    responses={404: {"description": "Not found"}},
)


@router.get("/status")
async def orchestrator_status(request: Request) -> dict[str, Any]:
    """Current coordinator state: cycle, last_collection_times, running, interval."""
    coordinator = getattr(request.app.state, "orchestrator_coordinator", None)
    if coordinator is None:
        return {"running": False, "error": "Orchestrator coordinator not available"}
    return coordinator.get_status()


@router.get("/metrics")
async def orchestrator_metrics(
    request: Request,
    metric_name: str | None = Query(None, description="Filter by metric name"),
    resource_type: str | None = Query(None, description="Filter resource usage by type"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Recent performance_metrics and resource_usage from orchestrator state."""
    try:
        from services.orchestrator_state import (
            get_recent_metrics,
            get_recent_resource_usage,
        )
        metrics = get_recent_metrics(metric_name=metric_name, limit=limit)
        usage = get_recent_resource_usage(resource_type=resource_type, limit=limit)
        return {
            "performance_metrics": metrics,
            "resource_usage": usage,
        }
    except Exception as e:
        logger.warning("Orchestrator metrics failed: %s", e)
        return {"performance_metrics": [], "resource_usage": [], "error": str(e)}


@router.get("/decision_log")
async def orchestrator_decision_log(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    since: str | None = Query(None, description="ISO timestamp, filter entries from this time"),
) -> dict[str, Any]:
    """Paginated decision history from orchestrator state."""
    try:
        from services.orchestrator_state import get_decision_log
        return get_decision_log(limit=limit, offset=offset, since=since)
    except Exception as e:
        logger.warning("Orchestrator decision_log failed: %s", e)
        return {"entries": [], "total": 0, "limit": limit, "offset": offset, "error": str(e)}


@router.get("/learning_stats")
async def orchestrator_learning_stats(request: Request) -> dict[str, Any]:
    """Learning governor stats: pattern counts by type, recent patterns sample."""
    coordinator = getattr(request.app.state, "orchestrator_coordinator", None)
    if coordinator is None or not hasattr(coordinator, "_learning_governor"):
        try:
            from services.learning_governor import LearningGovernor
            lg = LearningGovernor()
            return lg.get_learning_stats()
        except Exception as e:
            return {"pattern_counts_by_type": {}, "total_patterns": 0, "error": str(e)}
    return coordinator._learning_governor.get_learning_stats()


@router.get("/predictions")
async def orchestrator_predictions(request: Request) -> dict[str, Any]:
    """Predictions: next source update times, breaking_news_likelihood placeholder."""
    coordinator = getattr(request.app.state, "orchestrator_coordinator", None)
    if coordinator and hasattr(coordinator, "_learning_governor"):
        return coordinator._learning_governor.get_predictions()
    try:
        from services.learning_governor import LearningGovernor
        return LearningGovernor().get_predictions()
    except Exception as e:
        return {"next_source_updates": {}, "breaking_news_likelihood": 0.0, "error": str(e)}


@router.get("/dashboard")
async def orchestrator_dashboard(
    request: Request,
    decision_log_limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Single payload for dashboard: status, decision_log excerpt, learning_stats, predictions, recent metrics."""
    try:
        from services.orchestrator_state import get_decision_log, get_recent_metrics, get_recent_resource_usage
        from services.learning_governor import LearningGovernor
        coordinator = getattr(request.app.state, "orchestrator_coordinator", None)
        status = coordinator.get_status() if coordinator else {"running": False}
        lg = coordinator._learning_governor if (coordinator and hasattr(coordinator, "_learning_governor")) else LearningGovernor()
        return {
            "status": status,
            "decision_log": get_decision_log(limit=decision_log_limit, offset=0),
            "learning_stats": lg.get_learning_stats(),
            "predictions": lg.get_predictions(),
            "recent_metrics": get_recent_metrics(limit=10),
            "recent_resource_usage": get_recent_resource_usage(limit=10),
        }
    except Exception as e:
        logger.warning("Orchestrator dashboard failed: %s", e)
        return {"status": {}, "error": str(e)}


@router.post("/manual_override")
async def orchestrator_manual_override(
    request: Request,
    body: dict[str, Any] = Body(..., embed=False),
) -> dict[str, Any]:
    """
    One-off override: force_collect_now, pause_learning, resume_learning, set_config_override.
    Body: { "action": "...", "source": "rss"|"gold"|"silver"|"platinum" (force_collect_now), "config_overrides": {...} (set_config_override) }.
    """
    action = (body.get("action") or "").strip().lower()
    if not action:
        return {"success": False, "error": "action required"}
    try:
        from services import orchestrator_state
        if action == "pause_learning":
            state = orchestrator_state.get_controller_state()
            state["pause_learning"] = True
            orchestrator_state.save_controller_state(state)
            orchestrator_state.append_decision_log("manual_override", outcome="pause_learning")
            return {"success": True, "message": "Learning paused"}
        if action == "resume_learning":
            state = orchestrator_state.get_controller_state()
            state["pause_learning"] = False
            orchestrator_state.save_controller_state(state)
            orchestrator_state.append_decision_log("manual_override", outcome="resume_learning")
            return {"success": True, "message": "Learning resumed"}
        if action == "set_config_override":
            overrides = body.get("config_overrides")
            if not isinstance(overrides, dict):
                return {"success": False, "error": "config_overrides must be a dict"}
            allowed = {"min_fetch_interval_seconds", "max_fetch_interval_seconds", "empty_fetch_penalty"}
            overrides = {k: v for k, v in overrides.items() if k in allowed}
            state = orchestrator_state.get_controller_state()
            state["config_overrides"] = {**(state.get("config_overrides") or {}), **overrides}
            orchestrator_state.save_controller_state(state)
            orchestrator_state.append_decision_log("manual_override", outcome="set_config_override", factors=overrides)
            return {"success": True, "message": "Config overrides updated", "config_overrides": state["config_overrides"]}
        if action == "force_collect_now":
            source = (body.get("source") or "rss").strip().lower()
            try:
                from services.collection_governor import get_collection_source_ids
                allowed_sources = get_collection_source_ids()
            except Exception:
                allowed_sources = ["rss", "gold", "silver", "platinum"]
            if source not in allowed_sources:
                return {"success": False, "error": f"source must be one of: {', '.join(allowed_sources)}"}
            coordinator = getattr(request.app.state, "orchestrator_coordinator", None)
            if coordinator and hasattr(coordinator, "run_manual_collect"):
                result = await coordinator.run_manual_collect(source)
                return {"success": True, "result": result}
            # Fallback: run collect directly and record
            if source == "rss":
                from collectors.rss_collector import collect_rss_feeds
                count = collect_rss_feeds()
                orchestrator_state.append_decision_log("manual_override", outcome=f"force_rss_{count}")
                return {"success": True, "result": {"source": "rss", "articles_collected": count}}
            if source in ("gold", "silver", "platinum"):
                orch = getattr(request.app.state, "finance_orchestrator", None)
                if not orch:
                    return {"success": False, "error": "Finance orchestrator not available"}
                from domains.finance.orchestrator_types import TaskType, TaskPriority
                task_id = orch.submit_task(TaskType.refresh, {"topic": source}, priority=TaskPriority.high)
                orchestrator_state.append_decision_log("manual_override", outcome=f"force_{source}_{task_id}")
                return {"success": True, "result": {"source": source, "task_id": task_id}}
        return {"success": False, "error": f"unknown action: {action}"}
    except Exception as e:
        logger.warning("Orchestrator manual_override failed: %s", e)
        return {"success": False, "error": str(e)}
