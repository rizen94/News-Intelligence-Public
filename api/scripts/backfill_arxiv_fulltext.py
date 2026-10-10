#!/usr/bin/env python3
"""
Backfill full arXiv paper text for articles that only stored RSS abstracts.

Uses the same HTML → PDF path as article_content_enrichment_service._fetch_arxiv_full_text.

Examples:
  PYTHONPATH=api uv run python api/scripts/backfill_arxiv_fulltext.py --domain artificial-intelligence --limit 5
  PYTHONPATH=api uv run python api/scripts/backfill_arxiv_fulltext.py --domain artificial-intelligence --until-empty --skip-context
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_arxiv_fulltext")


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / "configs" / ".env", override=False)
        load_dotenv(ROOT / ".env", override=False)
        load_dotenv(API_DIR / ".env", override=False)
    except Exception:
        pass
    if not os.environ.get("DB_PASSWORD"):
        for candidate in (ROOT / ".db_password_widow", Path.home() / ".db_password_widow"):
            if candidate.is_file():
                os.environ["DB_PASSWORD"] = candidate.read_text().strip()
                break


def _fetch_candidates(schema: str, limit: int, max_len: int):
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, url, LENGTH(COALESCE(content, '')) AS content_len,
                       LEFT(COALESCE(content, ''), 40) AS content_prefix
                FROM {schema}.articles
                WHERE url ILIKE '%%arxiv.org/abs/%%'
                  AND LENGTH(COALESCE(content, '')) < %s
                  AND (
                    content ILIKE '%%Abstract:%%'
                    OR content ILIKE 'arxiv:%%'
                    OR LENGTH(COALESCE(content, '')) BETWEEN 1 AND %s
                  )
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (max_len, max_len, limit),
            )
            return cur.fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain",
        default="artificial-intelligence",
        help="Domain key (default artificial-intelligence)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max articles per batch (default 10). With --until-empty, re-selects until empty.",
    )
    parser.add_argument(
        "--until-empty",
        action="store_true",
        help="Keep selecting batches until no short arXiv abs articles remain",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=0,
        help="Stop after this many attempts (0 = no cap)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--min-gain",
        type=int,
        default=2000,
        help="Require new content at least this many chars longer than old (default 2000)",
    )
    parser.add_argument("--sleep", type=float, default=0.35, help="Seconds between fetches")
    parser.add_argument(
        "--skip-context",
        action="store_true",
        help="Skip per-article context sync (faster bulk; topic queue still requeued)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Log aggregate progress every N successes",
    )
    args = parser.parse_args()
    _load_env()

    from shared.domain_registry import resolve_domain_schema
    from services.article_content_enrichment_service import (
        ARXIV_ABSTRACT_CONTENT_MAX,
        enrich_article_content,
    )

    schema = resolve_domain_schema(args.domain)
    if not schema:
        logger.error("Unknown domain %s", args.domain)
        return 1

    sync_context = None
    if not args.skip_context and not args.dry_run:
        from services.context_processor_service import sync_context_from_article_after_content_change

        sync_context = sync_context_from_article_after_content_change

    from shared.database.connection import get_db_connection_context

    ok = fail = attempted = 0
    t0 = time.time()
    batch_num = 0

    while True:
        batch_num += 1
        rows = _fetch_candidates(schema, args.limit, ARXIV_ABSTRACT_CONTENT_MAX)
        if not rows:
            logger.info("No more candidates after %s batches", batch_num - 1)
            break

        logger.info(
            "Batch %s: selected %s candidates in %s (ok=%s fail=%s so far)",
            batch_num,
            len(rows),
            schema,
            ok,
            fail,
        )

        if args.dry_run:
            for article_id, url, old_len, prefix in rows:
                logger.info("dry-run id=%s len=%s url=%s prefix=%r", article_id, old_len, url, prefix)
            break

        for article_id, url, old_len, prefix in rows:
            if args.max_total and attempted >= args.max_total:
                logger.info("Hit --max-total=%s", args.max_total)
                logger.info("done ok=%s fail=%s elapsed=%.0fs", ok, fail, time.time() - t0)
                return 0 if ok > 0 else 1

            attempted += 1
            text, success = enrich_article_content(url)
            new_len = len(text or "")
            if not success or new_len < int(old_len or 0) + args.min_gain:
                logger.warning(
                    "skip persist id=%s old=%s new=%s (need +%s)",
                    article_id,
                    old_len,
                    new_len,
                    args.min_gain,
                )
                fail += 1
                time.sleep(args.sleep)
                continue

            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles
                        SET content = %s,
                            enrichment_status = 'enriched',
                            enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1,
                            updated_at = NOW(),
                            entities = NULL
                        WHERE id = %s
                        """,
                        (text, article_id),
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.topic_extraction_queue (article_id, status, priority, created_at)
                        VALUES (%s, 'pending', 3, NOW())
                        ON CONFLICT (article_id) DO UPDATE
                          SET status = 'pending', priority = 3, created_at = NOW()
                        """,
                        (article_id,),
                    )
                conn.commit()

            if sync_context is not None:
                try:
                    sync_context(args.domain, article_id)
                except Exception as e:
                    logger.debug("context sync %s: %s", article_id, e)

            ok += 1
            if ok % max(1, args.progress_every) == 0:
                rate = ok / max(0.001, time.time() - t0)
                logger.info(
                    "progress ok=%s fail=%s rate=%.2f/s elapsed=%.0fs last id=%s %s→%s",
                    ok,
                    fail,
                    rate,
                    time.time() - t0,
                    article_id,
                    old_len,
                    new_len,
                )
            else:
                logger.info("enriched id=%s %s → %s chars", article_id, old_len, new_len)
            time.sleep(args.sleep)

        if not args.until_empty:
            break

    logger.info("done ok=%s fail=%s attempted=%s elapsed=%.0fs", ok, fail, attempted, time.time() - t0)
    return 0 if ok > 0 or args.dry_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
