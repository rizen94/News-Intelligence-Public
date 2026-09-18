#!/usr/bin/env python3
"""
Audit kitchen-sink / incoherent active storylines (large article bags).

Uses assess_cluster_coherence on a capped sample of member article titles,
plus leaked-title detectors. Default is report-only (dry-run).

  PYTHONPATH=api python3 api/scripts/audit_kitchen_sink_storylines.py --domain legal
  PYTHONPATH=api python3 api/scripts/audit_kitchen_sink_storylines.py --domain legal --min-articles 50
  PYTHONPATH=api python3 api/scripts/audit_kitchen_sink_storylines.py --domain legal --apply
    # --apply only enqueues membership review dry-run for flagged ids (no hard deletes)
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("audit_kitchen_sink_storylines")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain",
        action="append",
        help="Domain key (repeatable). Default: all pipeline-active.",
    )
    parser.add_argument("--min-articles", type=int, default=50)
    parser.add_argument("--sample-size", type=int, default=40)
    parser.add_argument(
        "--csv",
        type=str,
        default="",
        help="Optional path to write CSV report",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Enqueue membership review dry-run for flagged storylines",
    )
    parser.add_argument(
        "--storyline-id",
        type=int,
        default=None,
        help="Audit a single storyline id (still requires --domain)",
    )
    args = parser.parse_args()

    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from shared.database.connection import get_db_connection
    from services.storyline_coherence_guardrails import (
        assess_cluster_coherence,
        assess_kitchen_sink_risk,
        is_leaked_storyline_title,
        is_placeholder_mega_title,
    )

    domains = args.domain or list(get_pipeline_active_domain_keys())
    rows_out: list[dict] = []

    for domain_key in domains:
        schema = resolve_domain_schema(domain_key)
        conn = get_db_connection()
        if not conn:
            logger.error("[%s] no db connection", domain_key)
            continue
        try:
            with conn.cursor() as cur:
                if args.storyline_id is not None:
                    cur.execute(
                        f"""
                        SELECT id, title, COALESCE(article_count, 0), status
                        FROM {schema}.storylines
                        WHERE id = %s AND merged_into_id IS NULL
                        """,
                        (args.storyline_id,),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT id, title, COALESCE(article_count, 0), status
                        FROM {schema}.storylines
                        WHERE merged_into_id IS NULL
                          AND status = 'active'
                          AND COALESCE(is_mega_storyline, FALSE) = FALSE
                          AND COALESCE(article_count, 0) >= %s
                        ORDER BY article_count DESC NULLS LAST
                        """,
                        (args.min_articles,),
                    )
                storylines = cur.fetchall()

            for sid, title, art_n, status in storylines:
                suggested = "ok"
                reason = "ok"
                title_s = title or ""

                if is_leaked_storyline_title(title_s):
                    suggested = "archive_title"
                    reason = "leaked_title"
                elif is_placeholder_mega_title(title_s):
                    suggested = "archive_title"
                    reason = "placeholder_title"
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT a.title
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.articles a ON a.id = sa.article_id
                            WHERE sa.storyline_id = %s
                            ORDER BY COALESCE(sa.relevance_score, 0) DESC NULLS LAST, sa.article_id
                            LIMIT %s
                            """,
                            (sid, max(5, args.sample_size)),
                        )
                        articles = [
                            {"title": r[0] or "", "summary": "", "content": ""}
                            for r in cur.fetchall()
                        ]
                    if len(articles) < 2:
                        reason = "too_few_sample_articles"
                        suggested = "ok"
                    else:
                        sink, sreason = assess_kitchen_sink_risk(title_s, articles)
                        if sink:
                            reason = sreason
                            suggested = "membership_review"
                        else:
                            ok, creason = assess_cluster_coherence(
                                domain_key, title_s, articles
                            )
                            if not ok:
                                reason = creason
                                suggested = "membership_review"

                rec = {
                    "domain": domain_key,
                    "id": sid,
                    "title": title_s[:120],
                    "article_count": int(art_n or 0),
                    "status": status,
                    "reason": reason,
                    "suggested_action": suggested,
                }
                rows_out.append(rec)
                if suggested != "ok":
                    logger.info(
                        "[%s] id=%s arts=%s action=%s reason=%s title=%r",
                        domain_key,
                        sid,
                        art_n,
                        suggested,
                        reason,
                        title_s[:80],
                    )

                if args.apply and suggested == "membership_review":
                    from services.storyline_membership_review_service import (
                        review_storyline_membership,
                    )

                    stats = review_storyline_membership(
                        domain_key, int(sid), dry_run=True
                    )
                    logger.info(
                        "[%s] membership dry-run id=%s scored=%s queued=%s",
                        domain_key,
                        sid,
                        stats.get("scored"),
                        stats.get("queued"),
                    )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    flagged = [r for r in rows_out if r["suggested_action"] != "ok"]
    logger.info(
        "Done. scanned=%s flagged=%s apply=%s",
        len(rows_out),
        len(flagged),
        bool(args.apply),
    )

    if args.csv:
        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "domain",
                    "id",
                    "title",
                    "article_count",
                    "status",
                    "reason",
                    "suggested_action",
                ],
            )
            w.writeheader()
            w.writerows(rows_out)
        logger.info("Wrote %s", path)

    # Non-zero exit if legal 3651 expected and missing when auditing legal
    if args.domain and "legal" in args.domain and not args.storyline_id:
        hit = any(r["domain"] == "legal" and int(r["id"]) == 3651 for r in flagged)
        if not hit:
            # Still OK if 3651 not flagged by coherence but scanned
            scanned_3651 = any(
                r["domain"] == "legal" and int(r["id"]) == 3651 for r in rows_out
            )
            if scanned_3651:
                logger.warning(
                    "legal 3651 scanned but not flagged by coherence "
                    "(may still need membership review)"
                )
            else:
                logger.warning("legal 3651 not in scan set")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
