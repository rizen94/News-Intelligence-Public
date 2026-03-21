"""
Newsroom Orchestrator v6 — configuration loading.

Config file: api/config/newsroom.yaml (optional).
Feature flag: NEWSROOM_ORCHESTRATOR_ENABLED (env overrides file).
"""

import logging
import os
from typing import Any

logger = logging.getLogger("orchestration")

# Defaults when file is missing or key absent
DEFAULTS = {
    "enabled": False,
    "reporter": {
        "poll_interval_seconds": 600,
        "new_article_window_minutes": 15,
        "breaking_news_keywords": [],
        "priority_entities": [],
    },
    "journalist": {
        "investigation_triggers": {
            "multiple_entity_mentions": 3,
            "pattern_confidence": 0.8,
            "user_watchlist_hit": True,
        },
        "max_concurrent_investigations": 5,
    },
    "editor": {
        "quality_threshold": 0.7,
        "narrative_update_frequency": 3600,
    },
    "event_handling": {
        "max_retries": 3,
        "backoff_base_seconds": 2,
        "dead_letter_after_retries": True,
    },
    "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_minutes": 15,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_newsroom_config() -> dict[str, Any]:
    """
    Load newsroom config from api/config/newsroom.yaml.
    Env NEWSROOM_ORCHESTRATOR_ENABLED overrides newsroom.enabled.
    """
    try:
        from config.paths import NEWSROOM_YAML
    except ImportError:
        NEWSROOM_YAML = None

    config = dict(DEFAULTS)
    if NEWSROOM_YAML and NEWSROOM_YAML.exists():
        try:
            import yaml

            with open(NEWSROOM_YAML) as f:
                file_config = yaml.safe_load(f) or {}
            newsroom = file_config.get("newsroom") or {}
            config = _deep_merge(config, newsroom)
        except Exception as e:
            logger.warning("Failed to load newsroom.yaml: %s — using defaults", e)
    else:
        logger.debug(
            "newsroom.yaml not found at %s — using defaults",
            getattr(NEWSROOM_YAML, "resolve", lambda: None)(),
        )

    # Env overrides enabled
    env_val = os.getenv("NEWSROOM_ORCHESTRATOR_ENABLED", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        config["enabled"] = True
    elif env_val in ("0", "false", "no"):
        config["enabled"] = False

    return config
