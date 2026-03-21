"""
OrchestratorCoordinator — central loop: assess state, plan, execute, learn, sleep.
Coordinates CollectionGovernor, LearningGovernor, ResourceGovernor. Phase 2: resource
tracking, pattern analysis, manual override.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)

from shared.services.pipeline_trace_writer import log_pipeline_trace

from .collection_governor import SOURCE_RSS, CollectionGovernor, get_collection_source_ids
from .learning_governor import LearningGovernor
from .processing_governor import ProcessingGovernor
from .resource_governor import RESOURCE_API_CALLS, ResourceGovernor

# Run pattern analysis every this many cycles (~30 min at 60s)
PATTERN_ANALYSIS_INTERVAL_CYCLES = 30

# Throttle decision log so we don't flood with repeated idle / process_phase entries
DECISION_LOG_IDLE_THROTTLE_SECONDS = 300  # Log "no_action"/"idle" at most every 5 min
DECISION_LOG_PHASE_THROTTLE_SECONDS = 120  # Log same "process_phase"/"queued" at most every 2 min


class OrchestratorCoordinator:
    """
    Master coordination loop: assess state, plan next action, execute one task,
    learn from result, update metrics, sleep. Uses ResourceGovernor for budget
    and LearningGovernor for pattern analysis (every N cycles).
    """

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        collection_governor: CollectionGovernor | None = None,
        resource_governor: ResourceGovernor | None = None,
        learning_governor: LearningGovernor | None = None,
        processing_governor: ProcessingGovernor | None = None,
        get_finance_orchestrator: Callable[[], Any] | None = None,
        get_automation: Callable[[], Any] | None = None,
        get_db_connection: Callable[[], Any] | None = None,
        collect_rss_feeds_fn: Callable[[], int] | None = None,
        loop_interval_seconds: int | None = None,
    ):
        if config is None:
            try:
                from config.orchestrator_governance import get_orchestrator_governance_config

                config = get_orchestrator_governance_config()
            except Exception as e:
                logger.warning("OrchestratorCoordinator: config load failed: %s", e)
                config = {}
        self._config = config
        self._resource_governor = resource_governor or ResourceGovernor(config=config)
        self._learning_governor = learning_governor or LearningGovernor(config=config)
        self._collection_governor = collection_governor or CollectionGovernor(
            config=config,
            resource_governor=self._resource_governor,
        )
        self._get_finance_orchestrator = get_finance_orchestrator
        self._get_automation = get_automation
        self._get_db_connection = get_db_connection
        self._collect_rss_feeds_fn = collect_rss_feeds_fn
        self._processing_governor = processing_governor or ProcessingGovernor(
            get_automation=get_automation,
            get_finance_orchestrator=get_finance_orchestrator,
        )
        orch = config.get("orchestrator") or {}
        self._loop_interval_seconds = loop_interval_seconds or orch.get("loop_interval_seconds", 60)
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="orch_coord")
        self._last_idle_log_at: datetime | None = None
        self._last_process_phase_log_at: datetime | None = None
        self._last_process_phase_name: str | None = None

    def start_loop(self) -> None:
        """Start the primary coordination loop (assess, plan, execute, learn, sleep)."""
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "OrchestratorCoordinator loop started (interval=%ss)", self._loop_interval_seconds
        )

    def stop_loop(self) -> None:
        """Stop the coordination loop."""
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                self._task.result()
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        logger.info("OrchestratorCoordinator loop stopped")

    async def _run_loop(self) -> None:
        """Primary loop: assess → plan → execute → learn → sleep."""
        while not self._stop.is_set():
            try:
                # 1. Assess current state
                from . import orchestrator_state

                state = orchestrator_state.get_controller_state()
                current_cycle = (state.get("current_cycle") or 0) + 1
                state["current_cycle"] = current_cycle

                # 2. Plan next action
                last_times = state.get("last_collection_times") or {}
                action = self._collection_governor.recommend_fetch(last_times)

                if action:
                    source = action.get("source")
                    # 3. Execute (format request from collection config)
                    success = False
                    observations_count = 0
                    outcome = "skipped"
                    try:
                        if source == SOURCE_RSS and self._collect_rss_feeds_fn:
                            orch_trace = (
                                f"orch_rss_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{current_cycle}"
                            )
                            log_pipeline_trace(
                                orch_trace, "orchestrator_rss_collection", "started"
                            )
                            try:
                                loop = asyncio.get_event_loop()
                                observations_count = await loop.run_in_executor(
                                    self._executor,
                                    self._collect_rss_feeds_fn,
                                )
                            except Exception as rss_exc:
                                logger.warning(
                                    "Orchestrator RSS collect failed: %s", rss_exc
                                )
                                log_pipeline_trace(
                                    orch_trace,
                                    "orchestrator_rss_collection",
                                    "error",
                                    {
                                        "error": str(rss_exc),
                                        "source": source,
                                        "cycle": current_cycle,
                                    },
                                )
                                raise
                            # Only treat RSS as "successful" if it actually adds new articles.
                            # If dedup rejects everything (adds=0), we want adaptive backoff.
                            success = (observations_count or 0) > 0
                            outcome = f"rss_collected_{observations_count}"
                            log_pipeline_trace(
                                orch_trace,
                                "orchestrator_rss_collection",
                                "completed",
                                {
                                    "articles_added": observations_count,
                                    "source": source,
                                    "cycle": current_cycle,
                                },
                            )
                        else:
                            # Finance (gold, silver, platinum) or other handlers from config
                            handler, topic = self._collection_handler_and_topic(source)
                            if handler == "finance" and self._get_finance_orchestrator:
                                orch = self._get_finance_orchestrator()
                                if orch:
                                    from domains.finance.orchestrator_types import (
                                        TaskPriority,
                                        TaskType,
                                    )

                                    task_id = orch.submit_task(
                                        TaskType.refresh,
                                        {"topic": topic or source},
                                        priority=TaskPriority.low,
                                    )
                                    success = True
                                    outcome = f"{source}_refresh_submitted_{task_id}"
                            else:
                                outcome = "no_handler"
                    except Exception as e:
                        logger.warning("Orchestrator execute %s failed: %s", source, e)
                        outcome = f"error_{str(e)[:100]}"

                    # 4. Learn: record result and decision log (each may fail independently)
                    try:
                        self._collection_governor.record_fetch_result(
                            source,
                            success=success,
                            observations_count=observations_count,
                        )
                    except Exception as e:
                        logger.warning("Orchestrator record_fetch_result failed: %s", e)
                    try:
                        orchestrator_state.append_decision_log(
                            f"collect_{source}",
                            factors={"source": source, "cycle": current_cycle},
                            outcome=outcome,
                        )
                    except Exception as e:
                        logger.warning("Orchestrator append_decision_log failed: %s", e)
                    try:
                        self._resource_governor.record_usage(RESOURCE_API_CALLS, 1.0)
                    except Exception as e:
                        logger.debug("Orchestrator record_usage failed: %s", e)
                    # Reload state so we don't overwrite last_collection_times just saved by record_fetch_result
                    state = orchestrator_state.get_controller_state()
                else:
                    try:
                        now_ts = datetime.now(timezone.utc)
                        if (
                            self._last_idle_log_at is None
                            or (now_ts - self._last_idle_log_at).total_seconds()
                            >= DECISION_LOG_IDLE_THROTTLE_SECONDS
                        ):
                            orchestrator_state.append_decision_log(
                                "no_action",
                                factors={"cycle": current_cycle},
                                outcome="idle",
                            )
                            self._last_idle_log_at = now_ts
                    except Exception as e:
                        logger.warning("Orchestrator append_decision_log failed: %s", e)

                # Processing: recommend and run one phase (importance + user guidance)
                state = orchestrator_state.get_controller_state()
                resource_ok = (
                    self._resource_governor.can_run("processing")
                    if self._resource_governor
                    else True
                )
                processing_action = self._processing_governor.recommend_next_processing(
                    state, resource_ok, get_db_connection=self._get_db_connection
                )
                if processing_action and self._get_automation:
                    automation = self._get_automation()
                    if automation and hasattr(automation, "request_phase"):
                        try:
                            automation.request_phase(
                                processing_action["phase"],
                                domain=processing_action.get("domain"),
                                storyline_id=processing_action.get("storyline_id"),
                            )
                            self._processing_governor.record_processing_result(
                                processing_action["phase"],
                                domain=processing_action.get("domain"),
                                storyline_id=processing_action.get("storyline_id"),
                                success=True,
                            )
                            try:
                                phase_name = processing_action["phase"]
                                now_ts = datetime.now(timezone.utc)
                                skip = (
                                    self._last_process_phase_name == phase_name
                                    and self._last_process_phase_log_at is not None
                                    and (now_ts - self._last_process_phase_log_at).total_seconds()
                                    < DECISION_LOG_PHASE_THROTTLE_SECONDS
                                )
                                if not skip:
                                    orchestrator_state.append_decision_log(
                                        "process_phase",
                                        factors={
                                            "cycle": current_cycle,
                                            "phase": phase_name,
                                            "domain": processing_action.get("domain"),
                                            "storyline_id": processing_action.get("storyline_id"),
                                        },
                                        outcome="queued",
                                    )
                                    self._last_process_phase_log_at = now_ts
                                    self._last_process_phase_name = phase_name
                            except Exception as e:
                                logger.warning("Orchestrator append_decision_log failed: %s", e)
                        except Exception as e:
                            logger.warning("Orchestrator request_phase failed: %s", e)
                            self._processing_governor.record_processing_result(
                                processing_action["phase"],
                                domain=processing_action.get("domain"),
                                storyline_id=processing_action.get("storyline_id"),
                                success=False,
                            )

                state["current_cycle"] = current_cycle
                state["last_collection_times"] = state.get("last_collection_times") or {}
                state["last_finance_interest_analysis"] = (
                    state.get("last_finance_interest_analysis") or {}
                )

                # Finance areas of interest: trigger one background analysis per due topic per cycle
                areas = (self._config or {}).get("finance_areas_of_interest") or []
                if areas and self._processing_governor:
                    now = datetime.now(timezone.utc)
                    last_run = state["last_finance_interest_analysis"]
                    triggered = False
                    for entry in areas:
                        if triggered:
                            break
                        if not isinstance(entry, dict):
                            continue
                        topic = (entry.get("topic") or "").strip()
                        query = (entry.get("query") or "").strip()
                        interval_days = int(entry.get("interval_days") or 7)
                        priority = (entry.get("priority") or "low").strip().lower()
                        if not topic or not query:
                            continue
                        last = last_run.get(topic)
                        due = True
                        if last:
                            try:
                                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                                if (now - last_dt).total_seconds() < interval_days * 86400:
                                    due = False
                            except (ValueError, TypeError):
                                pass
                        if not due:
                            continue
                        result = self._processing_governor.trigger_finance_analysis(
                            query, topic, priority=priority
                        )
                        if result and result.get("task_id"):
                            last_run[topic] = now.isoformat()
                            state["last_finance_interest_analysis"] = last_run
                            triggered = True
                            try:
                                orchestrator_state.append_decision_log(
                                    "finance_interest_analysis",
                                    factors={"topic": topic, "task_id": result.get("task_id")},
                                    outcome="queued",
                                )
                            except Exception as e:
                                logger.debug("Orchestrator append_decision_log failed: %s", e)
                            logger.info(
                                "Orchestrator queued finance area-of-interest analysis: topic=%s task_id=%s",
                                topic,
                                result.get("task_id"),
                            )

                # Phase 2 T2.3: event chronicle updates (when due)
                event_tracking = (self._config or {}).get("event_tracking") or {}
                if event_tracking.get("enabled") and self._get_db_connection:
                    interval_sec = int(event_tracking.get("update_interval_seconds") or 86400)
                    last_ts = state.get("last_event_chronicle_update")
                    due = True
                    if last_ts:
                        try:
                            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                            if (
                                datetime.now(timezone.utc) - last_dt
                            ).total_seconds() < interval_sec:
                                due = False
                        except (ValueError, TypeError):
                            pass
                    if due:
                        max_events = int(event_tracking.get("max_events_per_cycle") or 3)
                        try:
                            from .event_chronicle_builder_service import (
                                _run_scheduled_chronicle_updates,
                            )

                            loop = asyncio.get_event_loop()
                            updated = await loop.run_in_executor(
                                self._executor,
                                _run_scheduled_chronicle_updates,
                                max_events,
                                self._get_db_connection,
                            )
                            state["last_event_chronicle_update"] = datetime.now(
                                timezone.utc
                            ).isoformat()
                            if updated:
                                logger.info(
                                    "Orchestrator ran event chronicle updates for %s event(s)",
                                    updated,
                                )
                        except Exception as e:
                            logger.debug("Orchestrator event chronicle updates failed: %s", e)

                # Phase 5: dossier compilation (when entity_tracking enabled and interval due)
                entity_tracking = (self._config or {}).get("entity_tracking") or {}
                if entity_tracking.get("enabled") and self._get_db_connection:
                    interval_sec = int(
                        entity_tracking.get("dossier_compile_interval_seconds") or 86400
                    )
                    last_ts = state.get("last_dossier_compile_run")
                    due = True
                    if last_ts:
                        try:
                            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                            if (
                                datetime.now(timezone.utc) - last_dt
                            ).total_seconds() < interval_sec:
                                due = False
                        except (ValueError, TypeError):
                            pass
                    if due:
                        max_dossiers = int(entity_tracking.get("max_dossiers_per_cycle") or 2)
                        try:
                            from .dossier_compiler_service import _run_scheduled_dossier_compiles

                            loop = asyncio.get_event_loop()
                            compiled = await loop.run_in_executor(
                                self._executor,
                                _run_scheduled_dossier_compiles,
                                max_dossiers,
                                self._get_db_connection,
                            )
                            state["last_dossier_compile_run"] = datetime.now(
                                timezone.utc
                            ).isoformat()
                            if compiled:
                                logger.info(
                                    "Orchestrator ran dossier compilation for %s entity(ies)",
                                    compiled,
                                )
                        except Exception as e:
                            logger.debug("Orchestrator dossier compile failed: %s", e)

                try:
                    orchestrator_state.save_controller_state(state)
                except Exception as e:
                    logger.warning("Orchestrator save_controller_state failed: %s", e)

                # Periodic pattern analysis (every N cycles, unless pause_learning)
                if current_cycle % PATTERN_ANALYSIS_INTERVAL_CYCLES == 0 and not state.get(
                    "pause_learning"
                ):
                    try:
                        self._learning_governor.run_pattern_analysis()
                    except Exception as e:
                        logger.debug("Orchestrator pattern analysis failed: %s", e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Orchestrator loop iteration failed: %s", e)
                try:
                    from . import orchestrator_state

                    orchestrator_state.append_decision_log(
                        "loop_error",
                        outcome=str(e)[:200],
                    )
                except Exception:
                    pass

            # 5. Sleep until next cycle
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=float(self._loop_interval_seconds)
                )
            except asyncio.TimeoutError:
                pass

    def _collection_handler_and_topic(self, source_id: str) -> tuple[str | None, str | None]:
        """Return (handler, topic) for source from config. handler e.g. 'rss' or 'finance'."""
        collection = (self._config or {}).get("collection") or {}
        sources = collection.get("sources") or []
        for s in sources:
            if s.get("source_id") == source_id:
                return (s.get("handler"), s.get("topic"))
        # Backward compat: gold/silver/platinum -> finance
        if source_id in ("gold", "silver", "platinum"):
            return ("finance", source_id)
        return (None, None)

    def get_status(self) -> dict[str, Any]:
        """Current status for API: cycle, last_collection_times, collection_sources, next run hint, budget hint."""
        try:
            from . import orchestrator_state

            state = orchestrator_state.get_controller_state()
            out = {
                "current_cycle": state.get("current_cycle", 0),
                "last_collection_times": state.get("last_collection_times") or {},
                "collection_sources": get_collection_source_ids(self._config),
                "updated_at": state.get("updated_at"),
                "loop_interval_seconds": self._loop_interval_seconds,
                "running": self._task is not None and not self._task.done(),
            }
            if self._resource_governor:
                out["resource_budget"] = self._resource_governor.get_budget_status()
            return out
        except Exception as e:
            logger.warning("Orchestrator get_status failed: %s", e)
            return {"running": False, "error": str(e)}

    async def run_manual_collect(self, source: str) -> dict[str, Any]:
        """Run one collection now (rss or finance topic). Used by manual_override API."""
        if source == SOURCE_RSS and self._collect_rss_feeds_fn:
            loop = asyncio.get_event_loop()
            count = await loop.run_in_executor(self._executor, self._collect_rss_feeds_fn)
            self._collection_governor.record_fetch_result(
                SOURCE_RSS, success=True, observations_count=count
            )
            self._resource_governor.record_usage(RESOURCE_API_CALLS, 1.0)
            return {"source": "rss", "articles_collected": count}
        handler, topic = self._collection_handler_and_topic(source)
        if handler == "finance" and self._get_finance_orchestrator:
            orch = self._get_finance_orchestrator()
            if not orch:
                return {"source": source, "error": "Finance orchestrator not available"}
            from domains.finance.orchestrator_types import TaskPriority, TaskType

            task_id = orch.submit_task(
                TaskType.refresh,
                {"topic": topic or source},
                priority=TaskPriority.high,
            )
            self._collection_governor.record_fetch_result(source, success=True)
            self._resource_governor.record_usage(RESOURCE_API_CALLS, 1.0)
            return {"source": source, "task_id": task_id}
        return {"source": source, "error": "no handler"}
