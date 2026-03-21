"""
Finance data sources — FRED, (future) GDELT, EDGAR.

Dynamic loader reads sources.yaml and instantiates adapters from module_path.
Registry keyed by source name; adding a source = write adapter + YAML entry.
"""

import importlib
import logging

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.paths import SOURCES_YAML

from domains.finance.data_sources.base import DataSourceBase

_REGISTRY: dict[str, DataSourceBase] = {}
_LOADED = False


def _load_registry() -> None:
    """Read sources.yaml, instantiate adapters, populate registry. Fail loudly on error."""
    global _REGISTRY, _LOADED
    if _LOADED:
        return

    if not SOURCES_YAML.exists():
        logger.warning("sources.yaml not found at %s — data source registry empty", SOURCES_YAML)
        _LOADED = True
        return

    try:
        import yaml

        with open(SOURCES_YAML) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to load sources.yaml: %s", e)
        raise

    for source_id, entry in cfg.items():
        if not isinstance(entry, dict):
            continue
        module_path = entry.get("module_path")
        if not module_path:
            continue

        try:
            mod = importlib.import_module(module_path)
            get_client = getattr(mod, "get_client", None)
            if not get_client or not callable(get_client):
                raise ValueError(f"{module_path}: no get_client(config) function")
            client = get_client(entry)
            if not isinstance(client, DataSourceBase):
                raise TypeError(
                    f"{module_path}.get_client() returned {type(client)}, not DataSourceBase"
                )
            _REGISTRY[source_id] = client
            logger.info("Data source loaded: %s (%s)", source_id, client.name)
        except Exception as e:
            logger.error("Failed to load data source %s from %s: %s", source_id, module_path, e)
            raise

    _LOADED = True


def get_source(source_id: str) -> DataSourceBase | None:
    """Get data source by id. Loads registry on first access."""
    _load_registry()
    return _REGISTRY.get(source_id)


def get_all_sources() -> dict[str, DataSourceBase]:
    """Return full registry. Loads on first access."""
    _load_registry()
    return dict(_REGISTRY)


def list_source_ids() -> list[str]:
    """List registered source ids."""
    _load_registry()
    return list(_REGISTRY.keys())
