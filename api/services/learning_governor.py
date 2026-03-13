"""
Learning Governor — pattern detection from decision_history and performance_metrics.
Writes summaries to orchestrator_learned_patterns. Feedback loop: outcomes already
recorded in decision_history by the coordinator.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)


class LearningGovernor:
    """
    Consumes decision_history and performance_metrics; produces learned_patterns
    (e.g. source_patterns, outcome_patterns). Run run_pattern_analysis() periodically.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        if config is None:
            try:
                from config.orchestrator_governance import get_orchestrator_governance_config
                config = get_orchestrator_governance_config()
            except Exception as e:
                logger.warning("LearningGovernor: config load failed: %s", e)
                config = {}
        self._config = config
        learning = config.get("learning") or {}
        self._pattern_detection_window_days = int(learning.get("pattern_detection_window_days", 30))
        self._min_confidence_threshold = float(learning.get("min_confidence_threshold", 0.7))

    def run_pattern_analysis(self) -> dict[str, Any]:
        """
        Read recent decision_history, derive patterns, save to learned_patterns.
        Returns summary dict (counts, patterns_saved) for learning_stats.
        """
        try:
            from . import orchestrator_state
            since = (
                datetime.now(timezone.utc) - timedelta(days=self._pattern_detection_window_days)
            ).isoformat()
            log = orchestrator_state.get_decision_log(limit=500, offset=0, since=since)
            entries = log.get("entries", [])

            # Outcome counts by decision type (e.g. collect_rss, collect_gold, no_action)
            decision_outcomes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for e in entries:
                dec = e.get("decision") or "unknown"
                out = (e.get("outcome") or "unknown").strip()
                if out.startswith("error_"):
                    out = "error"
                elif out.startswith("rss_collected_"):
                    out = "rss_collected"
                elif out.startswith("gold_refresh_submitted_"):
                    out = "gold_submitted"
                decision_outcomes[dec][out] += 1

            # Source success pattern: from collect_* decisions, success vs error
            source_pattern = {
                "by_decision": {k: dict(v) for k, v in decision_outcomes.items()},
                "total_entries": len(entries),
                "window_days": self._pattern_detection_window_days,
            }
            success_count = sum(
                c for dec, out_dict in decision_outcomes.items()
                for out, c in out_dict.items()
                if out not in ("error", "idle", "no_handler")
            )
            error_count = sum(
                out_dict.get("error", 0) for out_dict in decision_outcomes.values()
            )
            source_pattern["success_count"] = success_count
            source_pattern["error_count"] = error_count
            if (success_count + error_count) > 0:
                source_pattern["success_rate"] = round(success_count / (success_count + error_count), 3)
            else:
                source_pattern["success_rate"] = 0.0

            confidence = self._min_confidence_threshold if (success_count + error_count) >= 10 else 0.5
            orchestrator_state.save_learned_pattern(
                pattern_type="source_patterns",
                pattern_data=source_pattern,
                confidence=confidence,
            )

            return {
                "entries_analyzed": len(entries),
                "patterns_saved": 1,
                "success_rate": source_pattern.get("success_rate"),
                "by_decision": source_pattern.get("by_decision"),
            }
        except Exception as e:
            logger.warning("LearningGovernor run_pattern_analysis failed: %s", e)
            return {"entries_analyzed": 0, "patterns_saved": 0, "error": str(e)}

    def get_learning_stats(self) -> dict[str, Any]:
        """Stats for API: pattern counts by type, last analysis summary."""
        try:
            from . import orchestrator_state
            counts = orchestrator_state.get_learned_pattern_counts_by_type()
            patterns = orchestrator_state.get_learned_patterns(limit=5)
            return {
                "pattern_counts_by_type": counts,
                "total_patterns": sum(counts.values()),
                "recent_patterns_sample": [
                    {"id": p["id"], "pattern_type": p["pattern_type"], "confidence": p["confidence"], "updated_at": p["updated_at"]}
                    for p in patterns
                ],
            }
        except Exception as e:
            logger.warning("LearningGovernor get_learning_stats failed: %s", e)
            return {"pattern_counts_by_type": {}, "total_patterns": 0, "error": str(e)}

    def get_predictions(self) -> dict[str, Any]:
        """
        Predictions for API: next source update times (from source_profiles),
        optional breaking_news_likelihood placeholder from recent activity.
        """
        try:
            from . import orchestrator_state
            from .collection_governor import SOURCE_RSS, SOURCE_GOLD
            now = datetime.now(timezone.utc)
            next_updates: dict[str, str | None] = {}
            for source_id in (SOURCE_RSS, SOURCE_GOLD):
                profile = orchestrator_state.get_source_profile(source_id)
                if not profile:
                    next_updates[source_id] = None
                    continue
                last_times = profile.get("historical_update_times") or []
                avg_sec = profile.get("average_interval_seconds")
                if last_times and avg_sec:
                    try:
                        last = datetime.fromisoformat(last_times[-1].replace("Z", "+00:00"))
                        next_ts = last + timedelta(seconds=float(avg_sec))
                        next_updates[source_id] = next_ts.isoformat()
                    except (ValueError, TypeError):
                        next_updates[source_id] = None
                else:
                    next_updates[source_id] = None
            # Placeholder: breaking news likelihood from recent decision outcomes (idle vs activity)
            state = orchestrator_state.get_controller_state()
            last_times = state.get("last_collection_times") or {}
            log = orchestrator_state.get_decision_log(limit=20, offset=0)
            recent = log.get("entries", [])
            idle_count = sum(1 for e in recent if (e.get("outcome") or "").strip() == "idle")
            activity_count = len(recent) - idle_count
            total = len(recent) or 1
            breaking_news_likelihood = round(min(1.0, activity_count / total + 0.1), 2)
            return {
                "next_source_updates": next_updates,
                "breaking_news_likelihood": breaking_news_likelihood,
                "generated_at": now.isoformat(),
            }
        except Exception as e:
            logger.warning("LearningGovernor get_predictions failed: %s", e)
            return {"next_source_updates": {}, "breaking_news_likelihood": 0.0, "error": str(e)}
