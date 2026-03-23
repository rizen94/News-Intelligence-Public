"""
Collection Governor — decides when to trigger RSS and API collection.
Delegates to existing collect_rss_feeds() and FinanceOrchestrator.submit_task(refresh).
Phase 2: adaptive backoff for empty fetches, source_profiles, optional resource check.
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

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

# Commodity price sources: use longer intervals; off-hours use off_hours_interval (markets closed)
COMMODITY_PRICE_SOURCE_IDS = {SOURCE_GOLD, SOURCE_SILVER, SOURCE_PLATINUM}

DEFAULT_SOURCE_IDS = [SOURCE_RSS, SOURCE_GOLD, SOURCE_SILVER, SOURCE_PLATINUM, SOURCE_EDGAR]


def _is_us_market_hours(now: datetime | None = None) -> bool:
    """True if current time is within US market hours (NYSE/NYMEX ~9:30–16:00 Eastern). Uses UTC for consistency."""
    from datetime import timezone as tz

    utc = now or datetime.now(tz.utc)
    if utc.tzinfo is None:
        utc = utc.replace(tzinfo=tz.utc)
    # Weekday in UTC: Mon=0 .. Fri=4
    if utc.weekday() >= 5:
        return False
    # 13:30–21:00 UTC ≈ 8:30–16:00 Eastern (EST/EDT)
    hour, minute = utc.hour, utc.minute
    if hour < 13:
        return False
    if hour > 21:
        return False
    if hour == 13 and minute < 30:
        return False
    return True


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
            "min_interval_seconds": float(
                overrides.get("min_fetch_interval_seconds", self._min_interval_seconds)
            ),
            "max_interval_seconds": float(
                overrides.get("max_fetch_interval_seconds", self._max_interval_seconds)
            ),
            "empty_fetch_penalty": float(
                overrides.get("empty_fetch_penalty", self._empty_fetch_penalty)
            ),
        }

    def _base_interval_seconds(self, source_id: str, now: datetime | None = None) -> float:
        """Base min interval for this source: per-source config, or global. Commodity price sources use longer off-hours."""
        cfg = self._get_effective_config()
        collection = (self._config or {}).get("collection") or {}
        sources = collection.get("sources") or []
        for s in sources:
            if s.get("source_id") != source_id:
                continue
            base = float(s.get("min_fetch_interval_seconds") or cfg["min_interval_seconds"])
            if source_id in COMMODITY_PRICE_SOURCE_IDS:
                off_hours = s.get("off_hours_interval_seconds")
                if off_hours is not None and not _is_us_market_hours(now):
                    base = max(base, float(off_hours))
            return base
        return cfg["min_interval_seconds"]

    def _effective_interval_seconds(self, source_id: str, now: datetime | None = None) -> float:
        """Min interval: per-source base (with off-hours for commodity prices), then scaled by empty-fetch backoff."""
        base = self._base_interval_seconds(source_id, now)
        cfg = self._get_effective_config()
        try:
            from . import orchestrator_state

            profile = orchestrator_state.get_source_profile(source_id)
            if not profile:
                return base
            empty_count = profile.get("last_empty_fetch_count") or 0
            if empty_count <= 0:
                return base
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
        if (
            check_resources
            and self._resource_governor
            and not self._resource_governor.can_run("collection")
        ):
            return None
        now = now or datetime.now(timezone.utc)
        candidates: list[tuple[str, float]] = []
        source_ids = get_collection_source_ids(self._config)

        for source_id in source_ids:
            last = last_collection_times.get(source_id)
            effective_interval = self._effective_interval_seconds(source_id, now)
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
        # Tie-break by source reliability (use source_rankings: prefer higher-reliability when due)
        reliability_by_source: dict[str, float] = {}
        try:
            from services.quality_feedback_service import get_source_rankings

            result = get_source_rankings(limit=100)
            if result.get("success") and result.get("rankings"):
                for r in result.get("rankings", []):
                    name = r.get("source_name")
                    score = r.get("accuracy_score")
                    if name is not None and score is not None:
                        reliability_by_source[name] = float(score)
                # Map generic source_id (e.g. "rss") to avg of matching rankings or neutral
                for sid in source_ids:
                    if sid in reliability_by_source:
                        continue
                    matches = [
                        v
                        for k, v in reliability_by_source.items()
                        if sid in k.lower() or k.lower() in sid
                    ]
                    reliability_by_source[sid] = sum(matches) / len(matches) if matches else 0.5
        except Exception as e:
            logger.debug("CollectionGovernor source_rankings failed: %s", e)

        # Sort by elapsed desc, then reliability desc (prefer due + high-reliability)
        def sort_key(item: tuple[str, float]) -> tuple[float, float]:
            sid, elapsed = item
            rel = reliability_by_source.get(sid, 0.5)
            return (elapsed, rel)

        source_id = max(candidates, key=sort_key)[0]
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
            # RSS: observations_count is new inserts + same-URL updates (see collect_rss_feeds). Zero => backoff.
            is_empty_fetch = (not success) or (
                source_id == "rss" and (observations_count or 0) <= 0
            )
            if is_empty_fetch:
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
