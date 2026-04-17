"""
Single source of truth for URL domain keys and Postgres schema names.

**Authoritative list: ``public.domains``** (rows with ``is_active`` true). YAML files under
``api/config/domains/*.yaml`` **merge into** DB rows for the same ``domain_key`` (prompts, RSS seeds,
focus hints) but **cannot** introduce a domain that is not present in the database.

Loader rules (keep in sync with api/config/domains/README.md):
- Skip any ``*.yaml`` file whose name starts with ``_``.
- Strip every key whose name starts with ``_`` from each loaded document.
- When the DB is empty or unreachable, fall back to **YAML-only** (developer bootstrap / tests).

``data_sources.rss.seed_feed_urls`` are inserted by ``provision_domain.py`` / ``seed_domain_rss_from_yaml.py``.

See docs/DOMAIN_EXTENSION_TEMPLATE.md and api/config/domains/README.md.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "domains"

# Schemas that must never be targeted by provision_domain as a *new* YAML silo (system + legacy dumps).
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
        out.append(_strip_doc_keys(raw))
    return out


def _load_domain_entries_from_db() -> list[dict[str, Any]] | None:
    """Return domain dicts from ``public.domains``, or None if DB unavailable."""
    try:
        from psycopg2.extras import RealDictCursor

        from shared.database.connection import get_ui_db_connection
    except Exception as e:  # pragma: no cover
        logger.debug("domain_registry DB load skipped: %s", e)
        return None

    conn = get_ui_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT domain_key, schema_name, name, display_order, is_active
                FROM public.domains
                ORDER BY display_order NULLS LAST, domain_key
                """
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.warning("domain_registry: could not read public.domains: %s", e)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    out: list[dict[str, Any]] = []
    for r in rows:
        dk = str(r.get("domain_key") or "").strip()
        sch = str(r.get("schema_name") or "").strip()
        if not dk or not sch:
            continue
        name = r.get("name")
        out.append(
            {
                "domain_key": dk,
                "schema_name": sch,
                "display_name": (str(name).strip() if name else dk),
                "display_order": int(r.get("display_order") or 99),
                "is_active": bool(r.get("is_active", True)),
            }
        )
    return out


def get_domain_entries() -> list[dict[str, Any]]:
    """
    All domains: **DB first**, merged with YAML for matching ``domain_key``.
    If ``public.domains`` is empty/unavailable, active YAML files only (bootstrap).
    """
    db_rows = _load_domain_entries_from_db()
    yaml_docs = _load_yaml_domain_files()
    yaml_by_key = {d["domain_key"]: d for d in yaml_docs if d.get("domain_key")}

    if db_rows is not None and len(db_rows) > 0:
        by_key: dict[str, dict[str, Any]] = {}
        for e in db_rows:
            by_key[e["domain_key"]] = dict(e)
        for k, y in yaml_by_key.items():
            if k not in by_key:
                continue
            merged = {**y, **by_key[k]}
            by_key[k] = merged
        return sorted(by_key.values(), key=lambda x: (x.get("display_order", 99), x["domain_key"]))

    # Bootstrap: no DB rows — use YAML-only (tests / pre-migration dev).
    if not yaml_docs:
        logger.warning(
            "domain_registry: public.domains is empty and no active YAML domains; registry is empty"
        )
        return []
    logger.info("domain_registry: using YAML-only domain list (public.domains empty or unreachable)")
    return sorted(yaml_docs, key=lambda x: (x.get("display_order", 99), x["domain_key"]))


def first_active_domain_key(fallback: str = "politics") -> str:
    """First active registry domain key — for API defaults when no domain is specified."""
    keys = get_active_domain_keys()
    return keys[0] if keys else fallback


def resolve_domain_schema(domain_key: str) -> str:
    """
    Map URL ``domain_key`` to Postgres ``schema_name`` for active entries.
    Fallback: ``hyphen → underscore`` (for stale rows or tests).
    """
    for e in get_domain_entries():
        if e["domain_key"] == domain_key:
            return str(e["schema_name"])
    return str(domain_key).replace("-", "_")


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
    """URL/route domain keys included in pipeline processing."""
    return tuple(dk for dk, _sch in iter_pipeline_url_schema_pairs())


# FastAPI Path: shape-only so YAML-onboarded silos work without restarting the API process.
DOMAIN_PATH_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

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
