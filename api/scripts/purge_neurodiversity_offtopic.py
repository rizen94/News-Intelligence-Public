#!/usr/bin/env python3
"""
Decouple off-topic neurodiversity articles (fail include_keywords allowlist).

Soft-marks enrichment_status=removed, deletes storyline/topic memberships,
uncouples editorial package article members. Does not DELETE article rows.

  PYTHONPATH=api python3 api/scripts/purge_neurodiversity_offtopic.py --dry-run
  PYTHONPATH=api python3 api/scripts/purge_neurodiversity_offtopic.py --apply
  PYTHONPATH=api python3 api/scripts/purge_neurodiversity_offtopic.py --apply --limit 500
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("purge_neurodiversity_offtopic")

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report only (default)")
    parser.add_argument("--apply", action="store_true", help="Write changes")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to scan")
    args = parser.parse_args()

    if not os.environ.get("DB_PORT"):
        os.environ["DB_PORT"] = os.environ.get("DB_MAINTENANCE_PORT") or "5432"

    dry_run = not args.apply
    if args.dry_run:
        dry_run = True

    from services.neurodiversity_offtopic_purge_service import purge_neurodiversity_offtopic

    result = purge_neurodiversity_offtopic(dry_run=dry_run, limit=args.limit)
    if not result.get("ok"):
        logger.error("failed: %s", result)
        return 1
    logger.info(
        "done dry_run=%s offtopic=%s links_removed=%s articles_removed=%s "
        "packages_uncoupled=%s storylines_recounted=%s sample_ids=%s",
        result.get("dry_run"),
        result.get("offtopic_articles"),
        result.get("storyline_links_removed"),
        result.get("articles_marked_removed"),
        result.get("package_members_uncoupled"),
        result.get("storylines_recounted"),
        result.get("sample_ids"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
