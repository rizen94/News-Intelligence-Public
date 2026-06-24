"""
Single source for environment variables (investigation / NRI unification).

Application code should import from here instead of os.environ.get.
Scripts may load dotenv before importing config modules.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def get_runtime_config() -> dict[str, Any]:
    """Merged runtime settings for NI + investigation (nri_core)."""
    return {
        # news_intel pool (see database_targets for DSN builders)
        "db_host": _env("DB_HOST", "localhost"),
        "db_port": _env_int("DB_PORT", 5432),
        "db_name": _env("DB_NAME", "news_intel"),
        "db_user": _env("DB_USER", "newsapp"),
        "db_password": _env("DB_PASSWORD", ""),
        "db_maintenance_port": _env_int("DB_MAINTENANCE_PORT", 5432),
        # identity_spine (separate database)
        "identity_spine_host": _env("IDENTITY_SPINE_HOST", _env("DB_HOST", "localhost")),
        "identity_spine_port": _env_int("IDENTITY_SPINE_PORT", 5432),
        "identity_spine_db": _env("IDENTITY_SPINE_DB", "identity_spine"),
        "identity_spine_user": _env("IDENTITY_SPINE_USER", _env("DB_USER", "newsapp")),
        "identity_spine_password": _env(
            "IDENTITY_SPINE_PASSWORD", _env("DB_PASSWORD", "")
        ),
        # Investigation schema (pre-migration: nri; post-migration: intelligence + prefix)
        "investigation_schema": _env("INVESTIGATION_SCHEMA", _env("NRI_SCHEMA", "nri")),
        "investigation_table_prefix": _env("INVESTIGATION_TABLE_PREFIX", ""),
        "use_investigation_prefixed_tables": _env_bool(
            "USE_INVESTIGATION_PREFIXED_TABLES", False
        ),
        # Legacy proxy (deprecated after unification)
        "nri_api_url": _env("NRI_API_URL", "http://127.0.0.1:8010").rstrip("/"),
        # Feature flags
        "nri_loop_enabled": _env_bool("NRI_LOOP_ENABLED", False),
        "nri_vault_write": _env_bool("NRI_VAULT_WRITE", False),
        "nri_vault_path": _env("NRI_VAULT_PATH", ""),
        "nri_lazy_mint_enabled": _env_bool("NRI_LAZY_MINT_ENABLED", True),
        "nri_skip_subject_mentions": _env_bool("NRI_SKIP_SUBJECT_MENTIONS", True),
        "nri_write_resolved_mentions": _env_bool("NRI_WRITE_RESOLVED_MENTIONS", True),
        "nri_allow_prod_news_intel": _env_bool("NRI_ALLOW_PROD_NEWS_INTEL", True),
        "nri_opensanctions_lazy_enabled": _env_bool("NRI_OPENSANCTIONS_LAZY_ENABLED", True),
        # FTM match thresholds (mention resolver / spine matcher)
        "ftm_auto_link_threshold": _env_float("FTM_AUTO_LINK_THRESHOLD", 0.92),
        "ftm_park_threshold": _env_float("FTM_PARK_THRESHOLD", 0.85),
        "nas_datasets_root": _env(
            "NAS_DATASETS_ROOT", "/mnt/nas/Data Lake Storage/nri/datasets"
        ),
        # Mention resolver / automation
        "mention_resolve_batch_limit": _env_int("NRI_MENTION_RESOLVE_BATCH_LIMIT", 500),
        "mention_resolve_budget_seconds": _env_float(
            "NRI_MENTION_RESOLVE_BUDGET_SECONDS", 900.0
        ),
        "mention_resolution_run_budget_seconds": _env_float(
            "MENTION_RESOLUTION_RUN_BUDGET_SECONDS",
            _env_float("NRI_MENTION_RESOLVE_BUDGET_SECONDS", 900.0),
        ),
        # Ollama
        "ollama_host": _env("OLLAMA_HOST", "http://localhost:11434"),
        "ollama_url": _env("OLLAMA_URL", _env("OLLAMA_HOST", "http://localhost:11434")),
        "ollama_pop_os_host": _env("OLLAMA_POP_OS_HOST", "http://192.168.93.99:11434"),
        "ollama_timeout": _env_int("OLLAMA_TIMEOUT", 300),
        "ollama_dual_host_routing_enabled": _env_bool(
            "OLLAMA_DUAL_HOST_ROUTING_ENABLED", True
        ),
    }


def investigation_schema() -> str:
    cfg = get_runtime_config()
    if cfg["use_investigation_prefixed_tables"]:
        return "intelligence"
    return str(cfg["investigation_schema"])


def investigation_table_prefix() -> str:
    cfg = get_runtime_config()
    if cfg["use_investigation_prefixed_tables"]:
        return str(cfg["investigation_table_prefix"] or "investigation_")
    return ""


def mention_resolve_batch_limit() -> int:
    return max(50, min(5000, get_runtime_config()["mention_resolve_batch_limit"]))


def mention_resolve_budget_seconds() -> float:
    return max(0.0, float(get_runtime_config()["mention_resolve_budget_seconds"]))


def ollama_host() -> str:
    return str(get_runtime_config()["ollama_host"])


def ollama_url() -> str:
    return str(get_runtime_config()["ollama_url"])


def ollama_pop_os_host() -> str:
    return str(get_runtime_config()["ollama_pop_os_host"])


def ollama_timeout_seconds() -> int:
    return int(get_runtime_config()["ollama_timeout"])


def ollama_dual_host_routing_enabled() -> bool:
    return bool(get_runtime_config()["ollama_dual_host_routing_enabled"])


def validate_runtime_config() -> list[str]:
    """Return human-readable config problems (empty list = OK)."""
    cfg = get_runtime_config()
    issues: list[str] = []
    if not cfg["db_name"]:
        issues.append("DB_NAME is empty")
    if not cfg["db_user"]:
        issues.append("DB_USER is empty")
    if not cfg["db_password"]:
        issues.append("DB_PASSWORD is empty")
    if int(cfg["db_port"]) <= 0:
        issues.append("DB_PORT must be positive")
    if not str(cfg["ollama_host"]).startswith("http"):
        issues.append("OLLAMA_HOST must be an http(s) URL")
    return issues


# Public env accessors — use these instead of os.environ in application code.
def env_str(name: str, default: str = "") -> str:
    return _env(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return _env_bool(name, default)


def env_int(name: str, default: int) -> int:
    return _env_int(name, default)


def env_float(name: str, default: float) -> float:
    return _env_float(name, default)


def env_set(name: str, value: str) -> None:
    os.environ[name] = value


def env_pop(name: str, default: str | None = None) -> str | None:
    return os.environ.pop(name, default)


def env_setdefault(name: str, value: str) -> str:
    return os.environ.setdefault(name, value)
