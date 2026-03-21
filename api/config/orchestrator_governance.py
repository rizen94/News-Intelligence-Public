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
                {"source_id": "gold", "handler": "finance", "topic": "gold", "min_fetch_interval_seconds": 3600, "off_hours_interval_seconds": 14400},
                {"source_id": "silver", "handler": "finance", "topic": "silver", "min_fetch_interval_seconds": 3600, "off_hours_interval_seconds": 14400},
                {"source_id": "platinum", "handler": "finance", "topic": "platinum", "min_fetch_interval_seconds": 3600, "off_hours_interval_seconds": 14400},
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
        "event_tracking": {
            "enabled": False,
            "update_interval_seconds": 86400,
            "max_events_per_cycle": 3,
        },
        "entity_tracking": {
            "enabled": True,
            "dossier_compile_interval_seconds": 86400,
            "max_dossiers_per_cycle": 2,
        },
        "quality_thresholds": {
            "min_quality_score": 0.5,
            "min_importance_for_processing": 0.3,
        },
        "source_credibility": {
            "enabled": True,
            "apply_to_quality_score": True,
            "disabled_multiplier": 1.0,
            "default_tier": "tier_3",
            "tier_order": ["tier_1", "tier_2", "tier_3"],
            "tiers": {
                "tier_1": {
                    "label": "Government / primary official / major wires",
                    "multiplier": 1.0,
                    "requires_corroboration": False,
                    "host_suffixes": [".gov", ".mil", ".edu"],
                    "host_contains": [],
                    "name_keywords": ["reuters", "associated press"],
                },
                "tier_2": {
                    "label": "Established media and institutions",
                    "multiplier": 0.88,
                    "requires_corroboration": False,
                    "host_suffixes": [],
                    "host_contains": ["bbc.", "nytimes.com", "bloomberg"],
                    "name_keywords": [],
                },
                "tier_3": {
                    "label": "Long tail / default RSS",
                    "multiplier": 0.72,
                    "requires_corroboration": False,
                    "host_suffixes": [],
                    "host_contains": [],
                    "name_keywords": [],
                },
            },
        },
        "document_sources": {
            "source_priorities": ["government", "think_tank", "research"],
            "document_types": ["report", "analysis", "briefing"],
            "ingest_urls": [],
        },
    }
