#!/usr/bin/env python3
"""
One-time ops: reconcile storylines.article_count from EEL chain (read-only compare + UPDATE).

Usage:
  python api/scripts/reconcile_episode_counts_from_eel.py --domain politics [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema
from shared.episode_attach_gate import episode_container_assembly_enabled
from shared.episode_membership import count_episode_articles

logger = logging.getLogger(__name__)


def reconcile_domain(domain_key: str, *, dry_run: bool = False) -> int:
    if not episode_container_assembly_enabled():
        logger.warning("Episode assembly off — nothing to reconcile")
        return 0

    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")

    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, COALESCE(article_count, 0)::int
                FROM {schema}.storylines
                WHERE merged_into_id IS NULL
                ORDER BY id
                """
            )
            rows = cur.fetchall()
            for sid, stored in rows:
                eel_count = count_episode_articles(
                    cur,
                    schema=schema,
                    domain_key=domain_key,
                    episode_id=int(sid),
                )
                if stored != eel_count:
                    logger.info(
                        "episode=%s stored=%s eel=%s%s",
                        sid,
                        stored,
                        eel_count,
                        " (dry-run)" if dry_run else "",
                    )
                    if not dry_run:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET article_count = %s,
                                total_articles = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (eel_count, eel_count, int(sid)),
                        )
                    updated += 1
            if not dry_run:
                conn.commit()
    finally:
        conn.close()
    return updated


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Reconcile episode article_count from EEL")
    ap.add_argument("--domain", required=True, help="Domain key (e.g. politics)")
    ap.add_argument("--dry-run", action="store_true", help="Compare only; no UPDATE")
    args = ap.parse_args()
    n = reconcile_domain(args.domain, dry_run=args.dry_run)
    logger.info("Reconciled %s storyline(s)", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
