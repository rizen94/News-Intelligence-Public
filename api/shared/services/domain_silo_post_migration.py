"""
After a domain silo SQL migration: seed RSS from onboarding YAML and activate public.domains.

Pure SQL migrations cannot write Git-tracked YAML or insert ``rss_feeds`` from URLs; migration
runners (e.g. ``api/scripts/run_migration_NNN.py``) call this module after ``execute(sql)``.

YAML ``is_active`` is not modified here — operators set ``is_active: true`` when the silo should
appear in ``domain_registry`` / RSS ``url_schema_pairs()`` (see api/config/domains/README.md).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from shared.services.domain_rss_seed import seed_from_domain_config

logger = logging.getLogger(__name__)


def load_domain_onboarding_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or not isinstance(data, dict):
        raise ValueError(f"Invalid or empty YAML: {path}")
    return data


def activate_domain_row(conn, domain_key: str) -> int:
    """UPDATE public.domains SET is_active = TRUE. Returns cursor.rowcount."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.domains SET is_active = TRUE WHERE domain_key = %s",
            (domain_key,),
        )
        n = cur.rowcount
    if n == 0:
        logger.warning(
            "domain_silo_post_migration: no public.domains row for domain_key=%r",
            domain_key,
        )
    return n


def apply_domain_silo_post_sql(
    conn,
    cfg: dict[str, Any],
    *,
    skip_rss_seed: bool = False,
    no_activate_in_db: bool = False,
) -> dict[str, Any]:
    """
    On an open psycopg2 connection (caller may have just applied silo SQL):
    optionally insert seed RSS feeds, optionally UPDATE public.domains SET is_active = TRUE.

    Returns a small status dict for logging.
    """
    domain_key = cfg.get("domain_key")
    schema_name = cfg.get("schema_name")
    if not domain_key or not schema_name:
        raise ValueError("YAML must define domain_key and schema_name")

    out: dict[str, Any] = {"domain_key": domain_key, "schema_name": schema_name}

    if not skip_rss_seed:
        added, skipped = seed_from_domain_config(conn, cfg, str(schema_name))
        out["rss_seeded"] = added
        out["rss_skipped_duplicates"] = skipped
        logger.info(
            "domain_silo_post_migration: rss seed schema=%s inserted=%s skipped=%s",
            schema_name,
            added,
            skipped,
        )
    else:
        out["rss_seeded"] = 0
        out["rss_skipped_duplicates"] = 0

    if not no_activate_in_db:
        out["domains_rows_updated"] = activate_domain_row(conn, str(domain_key))
    else:
        out["domains_rows_updated"] = None

    conn.commit()
    return out
