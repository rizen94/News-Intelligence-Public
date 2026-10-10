"""
Feature registry SSOT — lifecycle tags and runtime gates (v10.1).

Loads api/config/features.yaml; optional DB overrides from intelligence.feature_registry_overrides.
Emergency env: FEATURE_OVERRIDE_<KEY>=true|false
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from config.runtime import env_bool, env_str

logger = logging.getLogger(__name__)

Lifecycle = Literal[
    "under_developed",
    "staged",
    "incorporated",
    "deprecated",
    "archived",
]

_VALID_LIFECYCLES = frozenset(
    {"under_developed", "staged", "incorporated", "deprecated", "archived"}
)

_OVERRIDE_RE = re.compile(r"^FEATURE_OVERRIDE_([A-Z0-9_]+)$", re.I)


@lru_cache(maxsize=1)
def _features_yaml_path() -> Path:
    from config.paths import CONFIG_DIR

    return CONFIG_DIR / "features.yaml"


def _load_yaml_registry() -> dict[str, dict[str, Any]]:
    path = _features_yaml_path()
    if not path.is_file():
        return {}
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("features.yaml load failed: %s", exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, val in raw.items():
        if key.startswith("_") or not isinstance(val, dict):
            continue
        out[str(key)] = dict(val)
    return out


def _db_overrides() -> dict[str, dict[str, Any]]:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT feature_key, enabled, lifecycle, notes
                    FROM intelligence.feature_registry_overrides
                    """
                )
                rows = cur.fetchall() or []
        out: dict[str, dict[str, Any]] = {}
        for key, enabled, lifecycle, notes in rows:
            out[str(key)] = {
                "enabled": enabled,
                "lifecycle": lifecycle,
                "notes": notes,
            }
        return out
    except Exception:
        return {}


def _env_override(feature_key: str) -> bool | None:
    env_name = f"FEATURE_OVERRIDE_{feature_key.upper()}"
    raw = env_str(env_name, "").strip().lower()
    if not raw:
        return None
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def _merge_entry(key: str, base: dict[str, Any]) -> dict[str, Any]:
    entry = dict(base)
    entry["key"] = key
    overrides = _db_overrides().get(key) or {}
    for field in ("enabled", "lifecycle", "notes"):
        if overrides.get(field) is not None:
            entry[field] = overrides[field]
    lifecycle = str(entry.get("lifecycle") or "under_developed")
    if lifecycle not in _VALID_LIFECYCLES:
        lifecycle = "under_developed"
    entry["lifecycle"] = lifecycle
    env_ov = _env_override(key)
    if env_ov is not None:
        entry["enabled"] = env_ov
        entry["env_override"] = env_ov
    return entry


@lru_cache(maxsize=1)
def get_feature_registry() -> dict[str, dict[str, Any]]:
    raw = _load_yaml_registry()
    return {k: _merge_entry(k, v) for k, v in raw.items()}


def get_feature(feature_key: str) -> dict[str, Any] | None:
    return get_feature_registry().get(feature_key)


def list_features(
    *,
    lifecycle: str | None = None,
    enabled: bool | None = None,
    has_replacement: bool | None = None,
    replaces: str | None = None,
) -> list[dict[str, Any]]:
    items = list(get_feature_registry().values())
    if lifecycle:
        items = [i for i in items if i.get("lifecycle") == lifecycle]
    if enabled is not None:
        items = [i for i in items if bool(is_feature_enabled(i["key"])) == enabled]
    if has_replacement is True:
        items = [i for i in items if i.get("replaced_by")]
    elif has_replacement is False:
        items = [i for i in items if not i.get("replaced_by")]
    if replaces:
        items = [
            i
            for i in items
            if replaces in (i.get("replaces") or [])
            or i.get("key") == replaces
        ]
    return sorted(items, key=lambda x: x.get("key", ""))


def is_feature_enabled(feature_key: str, *, default: bool = False) -> bool:
    entry = get_feature(feature_key)
    if not entry:
        return default
    lifecycle = entry.get("lifecycle")
    yaml_enabled = bool(entry.get("enabled", False))
    if entry.get("env_override") is not None:
        return bool(entry["env_override"])
    if lifecycle in ("archived", "under_developed"):
        return False
    if lifecycle == "staged":
        return yaml_enabled and _staged_runtime_allowed()
    if lifecycle == "deprecated":
        return yaml_enabled
    return yaml_enabled if lifecycle == "incorporated" else default


def _staged_runtime_allowed() -> bool:
    """Staged features run in shadow conductor modes or explicit env."""
    if env_bool("FEATURE_STAGED_RUNTIME_ENABLED", False):
        return True
    try:
        from shared.pipeline_resource_policy import (
            assembly_pipeline_shadow_active,
            spine_pipeline_shadow_active,
        )

        return assembly_pipeline_shadow_active() or spine_pipeline_shadow_active()
    except Exception:
        return False


def feature_lifecycle(feature_key: str) -> str | None:
    entry = get_feature(feature_key)
    if not entry:
        return None
    return str(entry.get("lifecycle") or "")


def lifecycle_counts() -> dict[str, int]:
    counts: dict[str, int] = {lc: 0 for lc in _VALID_LIFECYCLES}
    for entry in get_feature_registry().values():
        lc = entry.get("lifecycle")
        if lc in counts:
            counts[str(lc)] += 1
    return counts


def clear_feature_registry_cache() -> None:
    get_feature_registry.cache_clear()
    _load_yaml_registry.cache_clear()
