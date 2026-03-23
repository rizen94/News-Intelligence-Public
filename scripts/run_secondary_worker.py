#!/usr/bin/env python3
"""
News Intelligence — Secondary worker (Widow).
Runs RSS collection every 10 minutes. No API, no ML (handled on primary).

On the main GPU host set AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true so AutomationManager
does not duplicate RSS inside collection_cycle (see docs/WIDOW_DB_ADJACENT_CRON.md).
Usage: python scripts/run_secondary_worker.py
"""

import os
import sys
import time
import logging
from pathlib import Path

# Project layout
PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "api"
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env before DB connect
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file, override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

INTERVAL_SEC = 600  # 10 minutes
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_registry_domains_for_rss() -> None:
    """Same ``url_schema_pairs()`` as main API — Widow must deploy identical ``api/config/domains/*.yaml``."""
    try:
        from shared.domain_registry import url_schema_pairs

        pairs = url_schema_pairs()
        summary = ", ".join(f"{k}→{s}" for k, s in pairs)
        logger.info("RSS domain registry (must match main PC): %s", summary)
    except Exception as e:
        logger.warning("Could not read domain registry: %s", e)


def run_rss_collection():
    try:
        from collectors.rss_collector import collect_rss_feeds
        return collect_rss_feeds()
    except Exception as e:
        logger.error("RSS collection failed: %s", e)
        return 0


def main():
    logger.info("Starting secondary worker (RSS every %d min)", INTERVAL_SEC // 60)
    logger.info("DB: %s:%s/%s", os.getenv("DB_HOST", "127.0.0.1"), os.getenv("DB_PORT", "5432"), os.getenv("DB_NAME", "news_intel"))
    _log_registry_domains_for_rss()

    cycle = 0
    while True:
        cycle += 1
        logger.info("=== Cycle %d ===", cycle)
        count = run_rss_collection()
        logger.info("RSS cycle %d: %d activity (new + updated)", cycle, count)
        logger.info("Sleeping %ds until next run", INTERVAL_SEC)
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
