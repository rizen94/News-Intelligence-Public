"""
Single source of truth for URL domain keys and Postgres schema names.

Core domains (politics, finance, science-tech) are always registered.
Additional silos use the same pipeline once onboarded: load ``api/config/domains/*.yaml`` when ``is_active`` is true.

Loader rules (keep in sync with api/config/domains/README.md):
- Skip any ``*.yaml`` file whose name starts with ``_`` (e.g. ``_template.example.yaml``).
- Skip files where ``is_active`` is false (missing key defaults to true — templates should set false explicitly).
- Strip every key whose name starts with ``_`` from each loaded document (human-only comments).
- Ignore YAML that tries to redefine politics, finance, or science-tech.

``data_sources.rss.seed_feed_urls`` (and optional ``seed_feed_category``) are **not** read here.
They are inserted into ``{schema_name}.rss_feeds`` by ``api/scripts/provision_domain.py`` (after SQL)
and ``api/scripts/seed_domain_rss_from_yaml.py`` (backfill).

``DOMAIN_PATH_PATTERN`` only constrains URL shape; ``is_valid_domain_key()`` re-reads YAML each call
so newly onboarded silos work without restarting the API. ``ACTIVE_DOMAIN_KEYS*`` at import is a snapshot only.

See docs/DOMAIN_EXTENSION_TEMPLATE.md and api/config/domains/README.md.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "domains"

# Built-in silos — never removed via YAML; YAML cannot deactivate these.
_BUILTIN: tuple[dict[str, Any], ...] = (
    {
        "domain_key": "politics",
        "schema_name": "politics",
        "display_name": "Politics",
        "display_order": 1,
        "is_active": True,
    },
    {
        "domain_key": "finance",
        "schema_name": "finance",
        "display_name": "Finance",
        "display_order": 2,
        "is_active": True,
    },
    {
        "domain_key": "science-tech",
        "schema_name": "science_tech",
        "display_name": "Science & Technology",
        "display_order": 3,
        "is_active": True,
    },
)

# Schemas that must never be targeted by provision_domain as a "new" silo.
RESERVED_SCHEMA_NAMES: frozenset[str] = frozenset(
    {
        "public",
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "politics",
        "finance",
        "science_tech",
        "politics_2",
        "finance_2",
        "intelligence",
        "artificial_intelligence",
    }
)


def resolve_domain_schema(domain_key: str) -> str:
    """
    Map URL ``domain_key`` to Postgres ``schema_name`` for active/builtin entries.
    Fallback: ``hyphen → underscore`` (for stale rows or tests).
    """
    for e in get_domain_entries():
        if e["domain_key"] == domain_key:
            return str(e["schema_name"])
    return str(domain_key).replace("-", "_")


def _strip_doc_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Remove human-only keys (prefix _) from merged domain config."""
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def _load_yaml_domain_files() -> list[dict[str, Any]]:
    if yaml is None or not _CONFIG_DIR.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(_CONFIG_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not raw or not isinstance(raw, dict):
            continue
        if not raw.get("is_active", True):
            continue
        key = raw.get("domain_key")
        if not key or not isinstance(key, str):
            continue
        # Do not allow YAML to redefine core keys (avoid hijack / drift).
        if key in ("politics", "finance", "science-tech"):
            continue
        out.append(_strip_doc_keys(raw))
    return out


def get_domain_entries() -> list[dict[str, Any]]:
    """All domains (builtin + active YAML), sorted by display_order then key."""
    by_key: dict[str, dict[str, Any]] = {e["domain_key"]: dict(e) for e in _BUILTIN}
    for d in _load_yaml_domain_files():
        k = d["domain_key"]
        merged = {**by_key.get(k, {}), **d}
        by_key[k] = merged
    return sorted(by_key.values(), key=lambda x: (x.get("display_order", 99), x["domain_key"]))


def get_active_domain_keys() -> tuple[str, ...]:
    return tuple(e["domain_key"] for e in get_domain_entries() if e.get("is_active", True))


def get_schema_names_active() -> tuple[str, ...]:
    return tuple(e["schema_name"] for e in get_domain_entries() if e.get("is_active", True))


def domain_key_to_schema(key: str) -> str:
    for e in get_domain_entries():
        if e["domain_key"] == key:
            return str(e["schema_name"])
    raise KeyError(key)


def schema_to_domain_key(schema: str) -> tuple[str, ...]:
    """Map DB schema to URL key(s); normally one. Returns tuple for API symmetry."""
    keys = [e["domain_key"] for e in get_domain_entries() if e["schema_name"] == schema]
    return tuple(keys)


def schema_to_primary_domain_key(schema: str) -> str:
    keys = schema_to_domain_key(schema)
    if not keys:
        raise KeyError(schema)
    return keys[0]


def iter_url_schema_pairs() -> Iterator[tuple[str, str]]:
    for e in get_domain_entries():
        if not e.get("is_active", True):
            continue
        yield (e["domain_key"], str(e["schema_name"]))


def url_schema_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(iter_url_schema_pairs())


def get_pipeline_excluded_domain_keys() -> frozenset[str]:
    """
    Domain keys excluded from **automation / enrichment / backlog processing** (comma-separated env).

    Set ``PIPELINE_EXCLUDE_DOMAIN_KEYS=politics,finance`` when ingest and work have moved to
    ``politics-2`` / ``finance-2``. RSS collection uses ``RSS_INGEST_EXCLUDE_DOMAIN_KEYS`` separately.
    Comparison is case-insensitive.
    """
    import os

    raw = os.environ.get("PIPELINE_EXCLUDE_DOMAIN_KEYS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def get_pipeline_included_domain_keys() -> frozenset[str] | None:
    """
    Optional allowlist: when ``PIPELINE_INCLUDE_DOMAIN_KEYS`` is non-empty, only those URL keys
    (must also be active in the registry) participate in pipeline iteration. Exclusions still apply after.
    """
    import os

    raw = os.environ.get("PIPELINE_INCLUDE_DOMAIN_KEYS", "").strip()
    if not raw:
        return None
    return frozenset(x.strip().lower().replace("_", "-") for x in raw.split(",") if x.strip())


def iter_pipeline_url_schema_pairs() -> Iterator[tuple[str, str]]:
    skip = get_pipeline_excluded_domain_keys()
    include = get_pipeline_included_domain_keys()
    for dk, sch in iter_url_schema_pairs():
        k = str(dk).strip().lower()
        if include is not None and k not in include:
            continue
        if k in skip:
            continue
        yield dk, sch


def pipeline_url_schema_pairs() -> tuple[tuple[str, str], ...]:
    return tuple(iter_pipeline_url_schema_pairs())


def get_pipeline_schema_names_active() -> tuple[str, ...]:
    return tuple(sch for _dk, sch in iter_pipeline_url_schema_pairs())


def get_pipeline_active_domain_keys() -> tuple[str, ...]:
    """URL/route domain keys included in pipeline processing (``PIPELINE_INCLUDE_*`` then ``PIPELINE_EXCLUDE_*``)."""
    return tuple(dk for dk, _sch in iter_pipeline_url_schema_pairs())


# FastAPI Path: shape-only so new YAML-onboarded silos work without restarting the API process.
# Authoritative allowlist is ``get_active_domain_keys()`` / ``is_valid_domain_key`` (YAML + builtins).
DOMAIN_PATH_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Snapshot at import — prefer ``get_active_domain_keys()`` when the list must reflect current YAML.
ACTIVE_DOMAIN_KEYS: tuple[str, ...] = get_active_domain_keys()
ACTIVE_DOMAIN_KEYS_SET: frozenset[str] = frozenset(ACTIVE_DOMAIN_KEYS)


def is_valid_domain_key(key: str) -> bool:
    return key in get_active_domain_keys()


def rss_feed_lookup_union_sql() -> str:
    """Build UNION ALL for resolving feed_url -> schema_name (single placeholder per branch)."""
    parts = []
    for _url_key, schema in iter_url_schema_pairs():
        parts.append(f"SELECT '{schema}' AS schema FROM {schema}.rss_feeds WHERE feed_url = %s")
    return " UNION ALL ".join(parts) + " LIMIT 1"


def rss_feed_lookup_param_count() -> int:
    return len(url_schema_pairs())
