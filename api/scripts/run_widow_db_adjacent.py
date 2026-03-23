#!/usr/bin/env python3
"""
Widow (or any DB-local host): run DB-adjacent automation steps without FastAPI or AutomationManager.

Use when the main GPU machine runs the API + AutomationManager but RSS and light SQL-heavy sync run next to Postgres.

Typical cron (every 15 min for sync; RSS often stays on newsplatform-secondary.service instead):
  cd /opt/news-intelligence && PYTHONPATH=api \\
    .venv/bin/python api/scripts/run_widow_db_adjacent.py --context-sync --entity-profile-sync --pending-db-flush

See docs/WIDOW_DB_ADJACENT_CRON.md
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def _run_rss() -> int:
    from collectors.rss_collector import collect_rss_feeds
    from shared.domain_registry import url_schema_pairs

    pairs = url_schema_pairs()
    logging.info(
        "RSS domain registry (deploy same api/config/domains/*.yaml as main): %s",
        ", ".join(f"{k}→{s}" for k, s in pairs),
    )

    n = collect_rss_feeds()
    logging.info("RSS: %s articles added", n)
    return int(n)


def _run_context_sync() -> None:
    from services.context_processor_service import sync_domain_articles_to_contexts
    from shared.domain_registry import get_active_domain_keys

    for domain_key in get_active_domain_keys():
        try:
            total = sync_domain_articles_to_contexts(domain_key, limit=100)
            if total > 0:
                logging.info("context_sync %s: %s contexts", domain_key, total)
        except Exception as e:
            logging.warning("context_sync %s failed: %s", domain_key, e)


def _run_entity_profile_sync() -> None:
    from services.entity_profile_sync_service import sync_domain_entity_profiles
    from shared.domain_registry import get_active_domain_keys

    for domain_key in get_active_domain_keys():
        try:
            total = sync_domain_entity_profiles(domain_key)
            if total > 0:
                logging.info("entity_profile_sync %s: %s mappings", domain_key, total)
        except Exception as e:
            logging.warning("entity_profile_sync %s failed: %s", domain_key, e)


def _run_pending_db_flush() -> None:
    from shared.database.pending_db_writes import flush_pending_writes

    stats = flush_pending_writes()
    logging.info("pending_db_flush: %s", stats)


def main() -> int:
    parser = argparse.ArgumentParser(description="Widow DB-adjacent batch (no API)")
    parser.add_argument("--rss", action="store_true", help="Run collect_rss_feeds (omit if newsplatform-secondary runs RSS)")
    parser.add_argument("--context-sync", action="store_true")
    parser.add_argument("--entity-profile-sync", action="store_true")
    parser.add_argument("--pending-db-flush", action="store_true")
    args = parser.parse_args()

    if not any(
        (args.rss, args.context_sync, args.entity_profile_sync, args.pending_db_flush)
    ):
        parser.print_help()
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _load_env()

    if args.rss:
        _run_rss()
    if args.context_sync:
        _run_context_sync()
    if args.entity_profile_sync:
        _run_entity_profile_sync()
    if args.pending_db_flush:
        _run_pending_db_flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
