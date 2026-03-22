"""
Insert RSS feeds from optional domain YAML ``data_sources.rss.seed_feed_urls``.

Used by ``provision_domain.py`` after the silo exists, and by ``seed_domain_rss_from_yaml.py``
for one-off backfill (e.g. medicine already provisioned before seeding existed).

``seed_feed_urls`` may be a list of URL strings or objects
``{feed_name, feed_url, fetch_interval_seconds?}`` (``url`` / ``name`` aliases allowed).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from psycopg2 import sql as psql

logger = logging.getLogger(__name__)

# Domain silo rss_feeds (cloned from science_tech) requires category NOT NULL.
DEFAULT_SEED_FEED_CATEGORY = "General"


@dataclass(frozen=True)
class SeedFeedEntry:
    feed_url: str
    feed_name: str | None = None
    fetch_interval_seconds: int | None = None


def _schema_sql_identifier(schema_name: str) -> bool:
    return bool(schema_name) and schema_name.replace("_", "").isalnum() and schema_name.islower()


def _feed_name_from_url(url: str, idx: int) -> str:
    url = (url or "").strip()
    if not url:
        return f"Feed {idx + 1}"
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower().removeprefix("www.")
        path = (p.path or "").strip("/")
        slug = path.split("/")[0][:50] if path else ""
        parts = [x for x in (host, slug) if x]
        name = " — ".join(parts) if len(parts) > 1 else (parts[0] if parts else "feed")
        name = re.sub(r"\s+", " ", name).strip()
        return (name[:200] if name else f"Feed {idx + 1}")[:200]
    except Exception:
        return f"Feed {idx + 1}"


def extract_seed_feed_entries(cfg: dict[str, Any]) -> list[SeedFeedEntry]:
    """Parse ``data_sources.rss.seed_feed_urls`` into structured entries."""
    ds = cfg.get("data_sources")
    if not isinstance(ds, dict):
        return []
    rss = ds.get("rss")
    if not isinstance(rss, dict):
        return []
    raw = rss.get("seed_feed_urls")
    if not isinstance(raw, list):
        return []
    out: list[SeedFeedEntry] = []
    for idx, item in enumerate(raw):
        if isinstance(item, str) and item.strip():
            out.append(SeedFeedEntry(feed_url=item.strip()))
            continue
        if isinstance(item, dict):
            url = (item.get("feed_url") or item.get("url") or "").strip()
            if not url:
                continue
            name = item.get("feed_name") or item.get("name")
            name_s = name.strip()[:200] if isinstance(name, str) and name.strip() else None
            interval: int | None = None
            if item.get("fetch_interval_seconds") is not None:
                try:
                    interval = int(item["fetch_interval_seconds"])
                except (TypeError, ValueError):
                    interval = None
            elif item.get("update_interval") is not None:
                try:
                    interval = int(item["update_interval"]) * 60
                except (TypeError, ValueError):
                    interval = None
            out.append(
                SeedFeedEntry(
                    feed_url=url,
                    feed_name=name_s,
                    fetch_interval_seconds=interval,
                )
            )
            continue
        logger.debug("domain_rss_seed: skip unsupported seed_feed_urls item at %s", idx)
    return out


def extract_seed_feed_urls(cfg: dict[str, Any]) -> list[str]:
    """Backward-compatible list of URLs only."""
    return [e.feed_url for e in extract_seed_feed_entries(cfg)]


def extract_seed_feed_category(cfg: dict[str, Any]) -> str:
    """Label for ``rss_feeds.category`` (VARCHAR, NOT NULL on silo tables)."""
    ds = cfg.get("data_sources")
    if not isinstance(ds, dict):
        return DEFAULT_SEED_FEED_CATEGORY
    rss = ds.get("rss")
    if not isinstance(rss, dict):
        return DEFAULT_SEED_FEED_CATEGORY
    raw = rss.get("seed_feed_category")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:100]
    return DEFAULT_SEED_FEED_CATEGORY


def seed_feed_entries_into_schema(
    conn,
    schema_name: str,
    entries: list[SeedFeedEntry],
    *,
    default_fetch_interval_seconds: int = 3600,
    is_active: bool = True,
    feed_category: str = DEFAULT_SEED_FEED_CATEGORY,
) -> tuple[int, int]:
    """
    Insert feeds; skip rows where feed_url already exists.
    Returns (inserted_count, skipped_count).
    """
    if not entries:
        return 0, 0
    if not _schema_sql_identifier(schema_name):
        raise ValueError(f"invalid schema_name: {schema_name!r}")

    inserted = 0
    skipped = 0
    cat = feed_category[:100] if feed_category else DEFAULT_SEED_FEED_CATEGORY
    with conn.cursor() as cur:
        for idx, ent in enumerate(entries):
            feed_url = ent.feed_url
            feed_name = ent.feed_name or _feed_name_from_url(feed_url, idx)
            fetch_iv = ent.fetch_interval_seconds or default_fetch_interval_seconds
            cur.execute(
                psql.SQL("SELECT 1 FROM {}.rss_feeds WHERE feed_url = %s").format(
                    psql.Identifier(schema_name)
                ),
                (feed_url,),
            )
            if cur.fetchone():
                skipped += 1
                continue
            cur.execute(
                psql.SQL(
                    """
                    INSERT INTO {}.rss_feeds
                    (feed_name, feed_url, is_active, fetch_interval_seconds, created_at, category)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                ).format(psql.Identifier(schema_name)),
                (
                    feed_name,
                    feed_url,
                    is_active,
                    fetch_iv,
                    datetime.now(),
                    cat,
                ),
            )
            inserted += 1
    logger.info(
        "domain_rss_seed: schema=%s inserted=%s skipped_duplicates=%s",
        schema_name,
        inserted,
        skipped,
    )
    return inserted, skipped


def seed_from_domain_config(
    conn,
    cfg: dict[str, Any],
    schema_name: str,
) -> tuple[int, int]:
    entries = extract_seed_feed_entries(cfg)
    category = extract_seed_feed_category(cfg)
    return seed_feed_entries_into_schema(
        conn, schema_name, entries, feed_category=category
    )
