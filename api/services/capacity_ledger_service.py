"""
Capacity ledger: estimated GPU/desk hours to drain actionable backlog vs daily budget,
plus intake-driven daily demand (Bucket A measurement).

Uses backlog_metrics pending × modeled batch size × phase duration — order-of-magnitude,
not a precise profiler. Env:
  CAPACITY_GPU_HOURS_PER_DAY (default 14) — PopOS desk hours available for NI LLM
  CAPACITY_LEDGER_PHASES — optional comma list; default = LLM-heavy contracted set
"""

from __future__ import annotations

import logging
import math
from typing import Any

from api.config.runtime import env_float, env_str

logger = logging.getLogger(__name__)

# Wall-clock seconds per scheduled run (aligned with automation_manager estimates).
_PHASE_RUN_SECONDS: dict[str, float] = {
    "entity_profile_build": 600,
    "claim_extraction": 600,
    "entity_extraction": 260,
    "event_extraction": 300,
    "storyline_discovery": 3600,
    "proactive_detection": 600,
    "storyline_assembly": 900,
    "content_refinement_queue": 420,
    "topic_clustering": 300,
    "story_continuation": 300,
}

# Fan-out: estimated full-lane LLM work units created per ingested article (steady state).
_INTAKE_WORK_UNITS_PER_ARTICLE: dict[str, float] = {
    "claim_extraction": 1.2,  # ~2.3 contexts × ~half full-lane
    "entity_extraction": 0.35,
    "event_extraction": 0.35,
    "entity_profile_build": 0.8,  # new + mention-driven refresh share
    "storyline_discovery": 0.15,
    "proactive_detection": 0.15,
    "content_refinement_queue": 0.05,  # rare 70b enqueues
}

_DEFAULT_LEDGER_PHASES = tuple(_PHASE_RUN_SECONDS.keys())


def capacity_gpu_hours_per_day() -> float:
    return max(1.0, min(24.0, env_float("CAPACITY_GPU_HOURS_PER_DAY", 14.0)))


def _ledger_phases() -> list[str]:
    raw = env_str("CAPACITY_LEDGER_PHASES", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return list(_DEFAULT_LEDGER_PHASES)


def _articles_created_24h() -> int:
    try:
        from api.shared.database import get_db_connection
        from api.shared.domain_registry import get_pipeline_schema_names_active

        conn = get_db_connection()
        if not conn:
            return 0
        total = 0
        try:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                for schema in get_pipeline_schema_names_active():
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.articles
                        WHERE created_at >= NOW() - INTERVAL '24 hours'
                        """
                    )
                    total += int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
        return total
    except Exception as e:
        logger.debug("capacity_ledger articles_24h: %s", e)
        return 0


def compute_capacity_ledger(
    pending: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Return demand vs budget snapshot.

    ``backlog_drain_hours``: hours to clear current actionable pending if we ran
    only those phases (sum of ceil(pending/batch)*run_seconds/3600).
    ``intake_demand_hours_per_day``: estimated new work from last-24h article rate.
    """
    from services.backlog_metrics import get_all_pending_counts, get_per_run_batch_size_for_phase

    if pending is None:
        try:
            pending = {
                k: int(v)
                for k, v in get_all_pending_counts(refresh_budget_s=20.0).items()
            }
        except Exception as e:
            logger.warning("capacity_ledger pending fetch: %s", e)
            pending = {}

    phases = _ledger_phases()
    by_phase: list[dict[str, Any]] = []
    backlog_hours = 0.0
    for phase in phases:
        pend = int(pending.get(phase, 0) or 0)
        batch = max(1, int(get_per_run_batch_size_for_phase(phase) or 1))
        run_sec = float(_PHASE_RUN_SECONDS.get(phase, 300))
        runs = int(math.ceil(pend / batch)) if pend > 0 else 0
        hours = runs * run_sec / 3600.0
        backlog_hours += hours
        by_phase.append(
            {
                "phase": phase,
                "pending": pend,
                "batch_per_run": batch,
                "runs_to_drain": runs,
                "est_run_seconds": run_sec,
                "drain_hours": round(hours, 2),
            }
        )

    articles_24h = _articles_created_24h()
    intake_hours = 0.0
    intake_by_phase: list[dict[str, Any]] = []
    for phase, units in _INTAKE_WORK_UNITS_PER_ARTICLE.items():
        if phase not in phases:
            continue
        batch = max(1, int(get_per_run_batch_size_for_phase(phase) or 1))
        run_sec = float(_PHASE_RUN_SECONDS.get(phase, 300))
        # work units → runs → hours
        daily_units = articles_24h * units
        runs = daily_units / batch
        hours = runs * run_sec / 3600.0
        intake_hours += hours
        intake_by_phase.append(
            {
                "phase": phase,
                "work_units_per_article": units,
                "daily_work_units": round(daily_units, 1),
                "demand_hours_per_day": round(hours, 2),
            }
        )

    budget = capacity_gpu_hours_per_day()
    by_phase.sort(key=lambda r: -float(r["drain_hours"]))
    return {
        "budget_gpu_hours_per_day": budget,
        "backlog_drain_hours": round(backlog_hours, 2),
        "backlog_vs_budget_ratio": round(backlog_hours / budget, 2) if budget else None,
        "intake_articles_24h": articles_24h,
        "intake_demand_hours_per_day": round(intake_hours, 2),
        "intake_vs_budget_ratio": round(intake_hours / budget, 2) if budget else None,
        "underwater": bool(intake_hours > budget or backlog_hours > budget * 2),
        "by_phase_backlog": by_phase[:12],
        "by_phase_intake": intake_by_phase,
        "note": (
            "Order-of-magnitude desk hours: ceil(pending÷batch)×phase_run_seconds/3600. "
            "Intake uses fan-out work-units per article × same model. "
            "Set CAPACITY_GPU_HOURS_PER_DAY to match real PopOS NI GPU window."
        ),
    }
