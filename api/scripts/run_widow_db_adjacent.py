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


def _run_context_sync() -> int:
    from datetime import datetime, timezone

    from services.context_processor_service import sync_domain_articles_to_contexts
    from shared.domain_registry import get_active_domain_keys

    total = 0
    for domain_key in get_active_domain_keys():
        try:
            n = sync_domain_articles_to_contexts(domain_key, limit=100)
            total += int(n or 0)
            if n > 0:
                logging.info("context_sync %s: %s contexts", domain_key, n)
        except Exception as e:
            logging.warning("context_sync %s failed: %s", domain_key, e)
    return total


def _run_entity_profile_sync() -> int:
    from services.entity_profile_sync_service import sync_domain_entity_profiles
    from shared.domain_registry import get_active_domain_keys

    total = 0
    for domain_key in get_active_domain_keys():
        try:
            n = sync_domain_entity_profiles(domain_key)
            total += int(n or 0)
            if n > 0:
                logging.info("entity_profile_sync %s: %s mappings", domain_key, n)
        except Exception as e:
            logging.warning("entity_profile_sync %s failed: %s", domain_key, e)
    return total


def _persist_cron_phase_run(phase_name: str, started, finished, *, success: bool, detail: str | None = None) -> None:
    try:
        from shared.services.automation_run_history_writer import persist_automation_run_history

        persist_automation_run_history(phase_name, started, finished, success, detail)
    except Exception as e:
        logging.warning("persist %s run history failed: %s", phase_name, e)


def _run_timed_cron_phase(phase_name: str, runner) -> None:
    from datetime import datetime, timezone

    started = datetime.now(timezone.utc)
    ok = True
    detail: str | None = None
    try:
        result = runner()
        if isinstance(result, int):
            detail = f"cron rows={result}"
    except Exception as e:
        ok = False
        detail = str(e)[:500]
        logging.warning("%s cron failed: %s", phase_name, e)
    finished = datetime.now(timezone.utc)
    _persist_cron_phase_run(phase_name, started, finished, success=ok, detail=detail)


def _run_pending_db_flush() -> None:
    from shared.database.pending_db_writes import flush_pending_writes

    stats = flush_pending_writes()
    logging.info("pending_db_flush: %s", stats)


def _run_terminate_idle_in_transaction(minutes: int = 5) -> int:
    """Terminate stale idle-in-transaction sessions (pool leak recovery)."""
    from shared.database.connection import get_ephemeral_db_connection_context

    terminated = 0
    with get_ephemeral_db_connection_context() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND state = 'idle in transaction'
                  AND pid <> pg_backend_pid()
                  AND state_change < NOW() - (%s || ' minutes')::interval
                """,
                (str(max(1, minutes)),),
            )
            terminated = cur.rowcount
    logging.info(
        "idle_in_tx_cleanup: terminated %s session(s) older than %s min",
        terminated,
        minutes,
    )
    return terminated


def main() -> int:
    parser = argparse.ArgumentParser(description="Widow DB-adjacent batch (no API)")
    parser.add_argument("--rss", action="store_true", help="Run collect_rss_feeds (omit if newsplatform-secondary runs RSS)")
    parser.add_argument("--context-sync", action="store_true")
    parser.add_argument("--entity-profile-sync", action="store_true")
    parser.add_argument("--pending-db-flush", action="store_true")
    parser.add_argument(
        "--terminate-idle-in-tx",
        action="store_true",
        help="Terminate idle-in-transaction sessions older than --idle-in-tx-minutes",
    )
    parser.add_argument(
        "--idle-in-tx-minutes",
        type=int,
        default=5,
        help="Age threshold for --terminate-idle-in-tx (default 5)",
    )
    args = parser.parse_args()

    if not any(
        (
            args.rss,
            args.context_sync,
            args.entity_profile_sync,
            args.pending_db_flush,
            args.terminate_idle_in_tx,
        )
    ):
        parser.print_help()
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _load_env()

    from services.pipeline_schedule_service import db_adjacent_sync_allowed, rss_collection_allowed

    if args.rss:
        if rss_collection_allowed():
            _run_rss()
        else:
            logging.info("RSS skipped (pipeline quiet window)")
    if args.context_sync:
        if db_adjacent_sync_allowed():
            _run_timed_cron_phase("context_sync", _run_context_sync)
        else:
            logging.info("context_sync skipped (pipeline quiet window)")
    if args.entity_profile_sync:
        if db_adjacent_sync_allowed():
            _run_timed_cron_phase("entity_profile_sync", _run_entity_profile_sync)
        else:
            logging.info("entity_profile_sync skipped (pipeline quiet window)")
    if args.pending_db_flush:
        _run_pending_db_flush()
    if args.terminate_idle_in_tx:
        _run_terminate_idle_in_transaction(minutes=args.idle_in_tx_minutes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
