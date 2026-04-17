#!/usr/bin/env python3
"""
Delete (or preview) articles that would be rejected by the *current* RSS ingest filters.

Uses the same predicates as api/collectors/rss_collector.py:
  - is_excluded_content (sports/entertainment + merged domain_synthesis defaults)
  - is_clickbait_title
  - is_advertisement (affiliate URLs, financial native ads, title roundups, etc.)

This keeps pruning behavior aligned with ingestion. Child rows tied to articles are removed
via ON DELETE CASCADE on domain schemas.

Typical workflow
----------------
  1. Dry-run one domain and inspect counts + samples::

       cd api && PYTHONPATH=. python scripts/prune_articles_failing_ingest_filters.py \\
         --domain politics-2 --dry-run --limit 5000

  2. Take a DB snapshot/backup if the counts look right.

  3. Execute (batched commits)::

       cd api && PYTHONPATH=. python scripts/prune_articles_failing_ingest_filters.py \\
         --domain politics-2 --execute --batch-size 500

  4. Optional: VACUUM ANALYZE the affected schemas (or whole DB) after a large purge.

Notes
-----
- Does **not** re-apply quality_score / impact_score gates (those can differ per run and need
  full feed context). For stricter cleanup, run with ``--also-low-quality`` which drops rows
  whose stored title+content+url score below 0.3 using calculate_article_quality_score
  (approximation of the RSS quality filter when body text exists).

- The automation task ``data_cleanup`` deletes by **age** only; it does not use these filters.
  Prefer this script for filter-aligned pruning.

Advertisement check and long bodies
-------------------------------------
``is_advertisement`` uses naive substrings like ``sale`` / ``deal`` on the **full** text. That
matches legitimate news (e.g. "Al **Sale**m air base", "no **deal** struck"). For **prune**,
the default is ``--ad-scope title-url``: run the ad check on **title + URL only** (empty body),
which matches thin RSS-at-ingest behavior and avoids mass false positives. Use
``--ad-scope full-text`` only if you accept aggressive deletion.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path

# api/ on path (parent of scripts/)
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from collectors.rss_collector import (  # noqa: E402
    calculate_article_quality_score,
    is_advertisement,
    is_clickbait_title,
    is_excluded_content,
)
from shared.database.connection import get_db_connection  # noqa: E402
from shared.domain_registry import url_schema_pairs  # noqa: E402

logger = logging.getLogger(__name__)


def _pairs_for_domains(domain_keys: list[str] | None) -> list[tuple[str, str]]:
    pairs = list(url_schema_pairs())
    if not domain_keys:
        return pairs
    want = {k.strip().lower().replace("_", "-") for k in domain_keys if k.strip()}
    out = [(dk, sch) for dk, sch in pairs if dk.strip().lower() in want]
    if not out:
        raise SystemExit(f"No matching active domains for: {domain_keys!r}. Registry: {[p[0] for p in pairs]}")
    return out


def _row_would_prune(
    title: str,
    content: str,
    url: str,
    source_domain: str,
    domain_key: str,
    *,
    also_low_quality: bool,
    ad_scope: str,
) -> tuple[bool, str]:
    """Return (should_delete, reason_code)."""
    t = title or ""
    c = content or ""
    u = url or ""
    src = source_domain or ""

    if is_excluded_content(t, c, src, "", domain=domain_key):
        return True, "excluded_content"
    if is_clickbait_title(t):
        return True, "clickbait"
    ad_body = c if ad_scope == "full-text" else ""
    if is_advertisement(t, ad_body, u):
        return True, "advertisement"
    if also_low_quality:
        q = calculate_article_quality_score(t, c, src, u)
        if q < 0.3:
            return True, f"low_quality_{q:.2f}"
    return False, ""


def _schema_has_table(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _delete_articles_chunk(cur, schema: str, chunk: list[int]) -> int:
    """Delete articles; remove topic-assignment rows first if FK is not CASCADE."""
    if not chunk:
        return 0
    ph = ",".join(["%s"] * len(chunk))
    if _schema_has_table(cur, schema, "article_topic_assignments"):
        cur.execute(
            f"DELETE FROM {schema}.article_topic_assignments WHERE article_id IN ({ph})",
            chunk,
        )
    cur.execute(f"DELETE FROM {schema}.articles WHERE id IN ({ph})", chunk)
    return int(cur.rowcount or 0)


def _fetch_batch(cur, schema: str, last_id: int, batch_size: int) -> list[tuple]:
    cur.execute(
        f"""
        SELECT id, COALESCE(title, ''), COALESCE(content, ''), COALESCE(url, ''),
               COALESCE(source_domain, '')
        FROM {schema}.articles
        WHERE id > %s
        ORDER BY id ASC
        LIMIT %s
        """,
        (last_id, batch_size),
    )
    return cur.fetchall()


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        metavar="DOMAIN_KEY",
        help="Domain key (repeatable), e.g. politics-2. Default: all active registry domains.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count and sample only; no DELETE.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually DELETE matching rows (batched).",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Rows scanned per SELECT batch (default 500).")
    parser.add_argument(
        "--delete-chunk",
        type=int,
        default=500,
        help="How many IDs per DELETE statement (default 500).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max rows scanned per domain (0 = no limit).",
    )
    parser.add_argument(
        "--also-low-quality",
        action="store_true",
        help="Also remove rows with calculate_article_quality_score < 0.3 (extra aggressive).",
    )
    parser.add_argument(
        "--ad-scope",
        choices=("title-url", "full-text"),
        default="title-url",
        help="Advertisement filter: title+URL only (default, avoids deal/sale false positives in "
        "article bodies) or full title+content+URL (matches current RSS when body is long).",
    )
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.dry_run and args.execute:
        parser.error("Choose only one of --dry-run or --execute")

    if not args.dry_run and not args.execute:
        parser.error("Specify --dry-run or --execute")

    try:
        from services.domain_synthesis_config import reload_config

        reload_config()
    except Exception as e:
        logger.debug("domain_synthesis_config reload skipped: %s", e)

    pairs = _pairs_for_domains(args.domains)
    total_deleted = 0
    overall_reasons: Counter[str] = Counter()

    conn = get_db_connection()
    if not conn:
        logger.error("No database connection")
        return 1

    try:
        with conn.cursor() as cur:
            for domain_key, schema in pairs:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = 'articles'
                    """,
                    (schema,),
                )
                if not cur.fetchone():
                    logger.warning(
                        "[%s] skip: schema %s has no articles table (domain not provisioned?)",
                        domain_key,
                        schema,
                    )
                    continue

                scanned = 0
                last_id = 0
                to_delete: list[int] = []
                reasons: Counter[str] = Counter()
                sample: list[tuple[int, str, str]] = []

                while True:
                    rows = _fetch_batch(cur, schema, last_id, args.batch_size)
                    if not rows:
                        break
                    hit_limit = False
                    for row in rows:
                        if args.limit and scanned >= args.limit:
                            hit_limit = True
                            break
                        aid, title, content, url, src = row
                        last_id = aid
                        scanned += 1
                        prune, reason = _row_would_prune(
                            title,
                            content,
                            url,
                            src,
                            domain_key,
                            also_low_quality=args.also_low_quality,
                            ad_scope=args.ad_scope,
                        )
                        if prune:
                            to_delete.append(aid)
                            bucket = "low_quality" if reason.startswith("low_quality") else reason
                            reasons[bucket] += 1
                            overall_reasons[reason] += 1
                            if len(sample) < 15:
                                sample.append((aid, reason, (title or "")[:120]))
                    if hit_limit:
                        break

                logger.info(
                    "[%s] scanned=%s match=%s (dry_run=%s)",
                    domain_key,
                    scanned,
                    len(to_delete),
                    args.dry_run,
                )
                for r, c in reasons.most_common():
                    logger.info("  %s: %s", r, c)
                if sample:
                    logger.info("Sample matches (id, reason, title):")
                    for aid, reason, tit in sample:
                        logger.info("  %s | %s | %s", aid, reason, tit)

                if args.execute and to_delete:
                    for i in range(0, len(to_delete), args.delete_chunk):
                        chunk = to_delete[i : i + args.delete_chunk]
                        total_deleted += _delete_articles_chunk(cur, schema, chunk)
                    conn.commit()
                    logger.info("[%s] deleted %s rows", domain_key, len(to_delete))

        if args.execute:
            logger.info("Total deleted (all domains): %s", total_deleted)
        logger.info("Reason breakdown (detailed): %s", dict(overall_reasons))
        return 0
    except Exception as e:
        logger.exception("prune failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(run())
