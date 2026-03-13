"""
Load orchestrator governance config from orchestrator_governance.yaml.
Single source of truth for coordinator and governors. Keys snake_case.
"""

import logging
from pathlib import Path
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)


def get_orchestrator_governance_config() -> dict[str, Any]:
    """
    Load orchestrator_governance.yaml. Returns nested dict with keys
    orchestrator, collection, processing, learning, resources.
    Missing file or key returns defaults for that section.
    """
    try:
        from config.paths import ORCHESTRATOR_GOVERNANCE_YAML
        yaml_path = Path(ORCHESTRATOR_GOVERNANCE_YAML)
    except Exception as e:
        logger.warning("Orchestrator config path unavailable: %s", e)
        return _default_config()

    if not yaml_path.exists():
        logger.info("Orchestrator governance YAML not found, using defaults: %s", yaml_path)
        return _default_config()

    try:
        import yaml
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Failed to load orchestrator_governance.yaml: %s — using defaults", e)
        return _default_config()

    # Merge with defaults so missing keys are filled
    defaults = _default_config()
    for section in defaults:
        if section not in cfg or not isinstance(cfg[section], dict):
            cfg[section] = defaults[section].copy()
        else:
            for k, v in defaults[section].items():
                if k not in cfg[section]:
                    cfg[section][k] = v
    return cfg


def _default_config() -> dict[str, Any]:
    """Default governance config when YAML is missing or incomplete."""
    return {
        "orchestrator": {
            "loop_interval_seconds": 60,
            "learning_rate": 0.1,
        },
        "collection": {
            "min_fetch_interval_seconds": 300,
            "max_fetch_interval_seconds": 7200,
            "empty_fetch_penalty": 2.0,
            "breaking_news_threshold": 0.8,
            "sources": [
                {"source_id": "rss", "handler": "rss"},
                {"source_id": "gold", "handler": "finance", "topic": "gold"},
                {"source_id": "silver", "handler": "finance", "topic": "silver"},
                {"source_id": "platinum", "handler": "finance", "topic": "platinum"},
            ],
        },
        "processing": {
            "batch_size": 10,
            "max_concurrent": 3,
            "context_window_days": 7,
            "phases": {},
        },
        "learning": {
            "pattern_detection_window_days": 30,
            "model_update_frequency_seconds": 21600,
            "min_confidence_threshold": 0.7,
        },
        "resources": {
            "daily_llm_tokens": 100000,
            "max_api_calls_per_hour": 1000,
            "storage_warning_threshold": 0.8,
        },
    }
