"""
Collection Governor — decides when to trigger RSS and API collection.
Delegates to existing collect_rss_feeds() and FinanceOrchestrator.submit_task(refresh).
Phase 2: adaptive backoff for empty fetches, source_profiles, optional resource check.
"""

import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .resource_governor import ResourceGovernor

# Source ids used by the coordinator to decide what to run
SOURCE_RSS = "rss"
SOURCE_GOLD = "gold"
SOURCE_SILVER = "silver"
SOURCE_PLATINUM = "platinum"
SOURCE_EDGAR = "edgar"

DEFAULT_SOURCE_IDS = [SOURCE_RSS, SOURCE_GOLD, SOURCE_SILVER, SOURCE_PLATINUM, SOURCE_EDGAR]


def get_collection_source_ids(config: dict[str, Any] | None = None) -> list[str]:
    """Return ordered list of collection source ids from config or defaults."""
    if config is None:
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config
            config = get_orchestrator_governance_config()
        except Exception:
            return list(DEFAULT_SOURCE_IDS)
    sources = (config.get("collection") or {}).get("sources") or []
    if not sources:
        return list(DEFAULT_SOURCE_IDS)
    return [s.get("source_id") for s in sources if s.get("source_id")]


class CollectionGovernor:
    """
    Recommends and records collection actions. Uses last_collection_times,
    min/max_fetch_interval, and optional backoff from source_profiles.
    Can check ResourceGovernor.can_run("collection") before recommending.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        resource_governor: "ResourceGovernor | None" = None,
    ):
        if config is None:
            try:
                from config.orchestrator_governance import get_orchestrator_governance_config
                config = get_orchestrator_governance_config()
            except Exception as e:
                logger.warning("CollectionGovernor: config load failed, using defaults: %s", e)
                config = {}
        self._config = config
        self._resource_governor = resource_governor
        collection = config.get("collection") or {}
        self._min_interval_seconds = collection.get("min_fetch_interval_seconds", 300)
        self._max_interval_seconds = collection.get("max_fetch_interval_seconds", 7200)
        self._empty_fetch_penalty = float(collection.get("empty_fetch_penalty", 2.0))

    def _get_effective_config(self) -> dict[str, float]:
        """Min/max interval and penalty, merged with config_overrides from state (Phase 3 tuning)."""
        try:
            from . import orchestrator_state
            state = orchestrator_state.get_controller_state()
            overrides = state.get("config_overrides") or {}
        except Exception:
            overrides = {}
        return {
            "min_interval_seconds": float(overrides.get("min_fetch_interval_seconds", self._min_interval_seconds)),
            "max_interval_seconds": float(overrides.get("max_fetch_interval_seconds", self._max_interval_seconds)),
            "empty_fetch_penalty": float(overrides.get("empty_fetch_penalty", self._empty_fetch_penalty)),
        }

    def _effective_interval_seconds(self, source_id: str) -> float:
        """Min interval scaled by empty-fetch backoff from source profile."""
        cfg = self._get_effective_config()
        base = cfg["min_interval_seconds"]
        try:
            from . import orchestrator_state
            profile = orchestrator_state.get_source_profile(source_id)
            if not profile:
                return base
            empty_count = profile.get("last_empty_fetch_count") or 0
            if empty_count <= 0:
                return base
            # Exponential backoff: base * penalty^empty_count, cap at max_interval
            cfg = self._get_effective_config()
            effective = base * (cfg["empty_fetch_penalty"] ** min(empty_count, 10))
            return min(effective, cfg["max_interval_seconds"])
        except Exception:
            return base

    def recommend_fetch(
        self,
        last_collection_times: dict[str, str],
        *,
        now: datetime | None = None,
        check_resources: bool = True,
    ) -> dict[str, Any] | None:
        """
        Recommend one collection action or None. Uses time since last fetch,
        adaptive interval (backoff for empty fetches), and optional resource check.
        Returns e.g. {"source": "rss"} or {"source": "gold"} or None.
        """
        if check_resources and self._resource_governor and not self._resource_governor.can_run("collection"):
            return None
        now = now or datetime.now(timezone.utc)
        candidates: list[tuple[str, float]] = []
        source_ids = get_collection_source_ids(self._config)

        for source_id in source_ids:
            last = last_collection_times.get(source_id)
            effective_interval = self._effective_interval_seconds(source_id)
            if last is None:
                candidates.append((source_id, 0.0))
                continue
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                candidates.append((source_id, float("inf")))
                continue
            elapsed = (now - last_dt).total_seconds()
            if elapsed >= effective_interval:
                candidates.append((source_id, elapsed))

        if not candidates:
            return None
        source_id = max(candidates, key=lambda x: x[1])[0]
        return {"source": source_id}

    def record_fetch_result(
        self,
        source_id: str,
        success: bool,
        observations_count: int = 0,
        *,
        error: str | None = None,
    ) -> None:
        """
        Record outcome of a fetch. Updates orchestrator state (last_collection_times)
        and source_profiles (last_empty_fetch_count, historical_update_times, average_interval).
        """
        try:
            from . import orchestrator_state
            state = orchestrator_state.get_controller_state()
            times = state.get("last_collection_times") or {}
            now_iso = datetime.now(timezone.utc).isoformat()
            times[source_id] = now_iso
            state["last_collection_times"] = times
            orchestrator_state.save_controller_state(state)

            profile = orchestrator_state.get_source_profile(source_id) or {}
            hist = list(profile.get("historical_update_times") or [])
            hist.append(now_iso)
            if len(hist) > 50:
                hist = hist[-50:]
            avg_interval: float | None = None
            if len(hist) >= 2:
                try:
                    t0 = datetime.fromisoformat(hist[-2].replace("Z", "+00:00"))
                    t1 = datetime.fromisoformat(hist[-1].replace("Z", "+00:00"))
                    avg_interval = max(0.0, (t1 - t0).total_seconds())
                except (ValueError, TypeError):
                    pass
            if not success:
                empty_count = (profile.get("last_empty_fetch_count") or 0) + 1
                orchestrator_state.update_source_profile(
                    source_id,
                    historical_update_times=hist,
                    average_interval_seconds=avg_interval,
                    last_empty_fetch_count=empty_count,
                )
            else:
                orchestrator_state.update_source_profile(
                    source_id,
                    historical_update_times=hist,
                    average_interval_seconds=avg_interval,
                    last_empty_fetch_count=0,
                )
        except Exception as e:
            logger.warning("CollectionGovernor record_fetch_result failed: %s", e)
