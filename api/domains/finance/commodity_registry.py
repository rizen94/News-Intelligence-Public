"""
Commodity registry — config-driven list and per-commodity rules for relevance and price.
Loads api/config/commodity_registry.yaml; used by news_orchestrator, finance routes, and FRED.
"""

import logging
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

try:
    from config.logging_config import get_component_logger
    from config.paths import CONFIG_DIR

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)
    CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

_REGISTRY_PATH = CONFIG_DIR / "commodity_registry.yaml"
_cached: dict[str, Any] | None = None


def _load_registry() -> dict[str, Any]:
    global _cached
    if _cached is not None:
        return _cached
    out: dict[str, Any] = {"commodities": [], "financial_signals_default": []}
    if not _REGISTRY_PATH.exists():
        logger.warning("Commodity registry not found at %s — using empty list", _REGISTRY_PATH)
        _cached = out
        return _cached
    if not yaml:
        logger.warning("PyYAML not available — commodity registry not loaded")
        _cached = out
        return _cached
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        out["financial_signals_default"] = raw.get("financial_signals_default") or []
        commodities = raw.get("commodities") or []
        default_signals = out["financial_signals_default"]
        for c in commodities:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            # Merge financial_signals: use per-commodity list or default
            signals = c.get("financial_signals")
            if not signals:
                signals = list(default_signals)
            c = dict(c)
            c["financial_signals"] = signals
            out["commodities"].append(c)
        _cached = out
    except Exception as e:
        logger.warning("Failed to load commodity_registry.yaml: %s — using empty list", e)
        _cached = out
    return _cached


def get_commodity_ids() -> list[str]:
    """Return list of commodity ids (e.g. ['gold', 'silver', 'platinum'])."""
    reg = _load_registry()
    return [c["id"] for c in reg["commodities"] if c.get("id")]


def get_commodity_config(commodity_id: str) -> dict[str, Any] | None:
    """Return full config for one commodity, or None if not in registry."""
    reg = _load_registry()
    cid = (commodity_id or "").lower()
    for c in reg["commodities"]:
        if (c.get("id") or "").lower() == cid:
            return dict(c)
    return None


def get_topic_keywords(commodity_id: str) -> list[str]:
    """Topic keywords for relevance scoring; empty if commodity not in registry."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return []
    return list(cfg.get("topic_keywords") or [])


def get_word_boundary_terms(commodity_id: str) -> list[str]:
    """Terms that must match as whole words (e.g. gold vs Goldman Sachs)."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return []
    return list(cfg.get("word_boundary_terms") or [])


def get_financial_signals(commodity_id: str) -> list[str]:
    """Terms that indicate financial/market context; used to boost relevance."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return []
    return list(cfg.get("financial_signals") or [])


def get_non_financial_exclude(commodity_id: str) -> list[str]:
    """Terms/phrases that indicate non-financial context; content matching these is excluded."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return []
    return list(cfg.get("non_financial_exclude") or [])


def get_commodity_list_for_api() -> list[dict[str, Any]]:
    """Minimal list for GET /{domain}/finance/commodities: [{ id, label }, ...]."""
    reg = _load_registry()
    return [
        {"id": c["id"], "label": c.get("label") or c["id"]}
        for c in reg["commodities"]
        if c.get("id")
    ]


def get_fred_series_id(commodity_id: str) -> str | None:
    """FRED series ID for this commodity: from registry fred_series_id, then env FRED_{ID}_SERIES_ID."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return None
    sid = (cfg.get("fred_series_id") or "").strip()
    if not sid:
        env_key = "FRED_" + (commodity_id or "").upper().replace("-", "_") + "_SERIES_ID"
        sid = (os.environ.get(env_key) or "").strip()
    return sid or None


def get_unit(commodity_id: str) -> str:
    """Display unit for price (e.g. USD/oz, USD/bbl). Default USD/toz for unknown."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return "USD/toz"
    return (cfg.get("unit") or "USD/toz").strip()


def get_metals_dev(commodity_id: str) -> bool:
    """True if this commodity can use metals.dev (gold, silver, platinum only)."""
    cfg = get_commodity_config(commodity_id)
    if not cfg:
        return False
    return bool(cfg.get("metals_dev"))
