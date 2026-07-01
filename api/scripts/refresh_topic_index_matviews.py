#!/usr/bin/env python3
"""Refresh domain mv_topic_index materialized views (CONCURRENTLY when possible)."""

from __future__ import annotations

import argparse
import logging

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def refresh_schema(schema: str, *, concurrently: bool = True) -> bool:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass(%s)",
                (f"{schema}.mv_topic_index",),
            )
            if not cur.fetchone()[0]:
                logger.warning("mv_topic_index missing in %s — run migration 243", schema)
                return False
            mode = "CONCURRENTLY" if concurrently else ""
            cur.execute(f"REFRESH MATERIALIZED VIEW {mode} {schema}.mv_topic_index")
        conn.commit()
    logger.info("Refreshed %s.mv_topic_index", schema)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", action="append")
    parser.add_argument("--no-concurrent", action="store_true")
    args = parser.parse_args()
    domains = args.domain or list(get_pipeline_active_domain_keys())
    ok = 0
    for dk in domains:
        if refresh_schema(resolve_domain_schema(dk), concurrently=not args.no_concurrent):
            ok += 1
    return 0 if ok == len(domains) else 1


if __name__ == "__main__":
    raise SystemExit(main())
