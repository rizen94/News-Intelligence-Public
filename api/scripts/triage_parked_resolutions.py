#!/usr/bin/env python3
"""Bulk-triage open investigation parked_resolution rows by reason bucket.

Default is dry-run. Does not mass-approve bridge_qa_mismatch rows.

Buckets:
  - mention_too_short → rejected
  - PARKED_GENERIC_MENTIONS → rejected
  - below_auto_link_threshold with candidate + score >= --approve-min-score → approved
  - bridge_qa_mismatch:* → left open (UI / separate QA)
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


def _conn():
    from shared.database.connection import get_db_connection

    return get_db_connection()


def _stats(cur, table: str) -> dict[str, int]:
    cur.execute(
        f"""
        SELECT COALESCE(reason, '(null)'), COUNT(*)::int
        FROM {table}
        WHERE review_status = 'open'
        GROUP BY 1
        ORDER BY 2 DESC
        """
    )
    return {str(r[0]): int(r[1]) for r in cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist updates (default: dry-run counts only)",
    )
    parser.add_argument(
        "--approve-min-score",
        type=float,
        default=0.85,
        help="Min match_score for below_auto_link_threshold auto-approve (default 0.85)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max rows per UPDATE statement (0 = no LIMIT)",
    )
    args = parser.parse_args()

    from config.investigation_tables import T_PARKED_RESOLUTION
    from config.nri_resolution_config import PARKED_GENERIC_MENTIONS

    generics = sorted({m.strip().lower() for m in PARKED_GENERIC_MENTIONS if m.strip()})
    limit_sql = f" LIMIT {int(args.limit)} " if args.limit and args.limit > 0 else ""

    conn = _conn()
    if not conn:
        print("ERROR: no DB connection", file=sys.stderr)
        return 1

    results: dict[str, Any] = {"dry_run": not args.apply}
    try:
        with conn.cursor() as cur:
            before = _stats(cur, T_PARKED_RESOLUTION)
            results["before_open_by_reason"] = before
            results["before_open_total"] = sum(before.values())

            # 1) mention_too_short → rejected
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {T_PARKED_RESOLUTION}
                WHERE review_status = 'open' AND reason = 'mention_too_short'
                """
            )
            n_short = int(cur.fetchone()[0] or 0)
            results["would_reject_mention_too_short"] = n_short
            if args.apply and n_short:
                cur.execute(
                    f"""
                    UPDATE {T_PARKED_RESOLUTION}
                    SET review_status = 'rejected', reviewed_at = NOW()
                    WHERE id IN (
                        SELECT id FROM {T_PARKED_RESOLUTION}
                        WHERE review_status = 'open' AND reason = 'mention_too_short'
                        ORDER BY id
                        {limit_sql}
                    )
                    """
                )
                results["rejected_mention_too_short"] = cur.rowcount

            # 2) generic tokens → rejected
            if generics:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {T_PARKED_RESOLUTION}
                    WHERE review_status = 'open'
                      AND lower(trim(mention_text)) = ANY(%s)
                    """,
                    (generics,),
                )
                n_generic = int(cur.fetchone()[0] or 0)
                results["would_reject_generic"] = n_generic
                if args.apply and n_generic:
                    cur.execute(
                        f"""
                        UPDATE {T_PARKED_RESOLUTION}
                        SET review_status = 'rejected', reviewed_at = NOW()
                        WHERE id IN (
                            SELECT id FROM {T_PARKED_RESOLUTION}
                            WHERE review_status = 'open'
                              AND lower(trim(mention_text)) = ANY(%s)
                            ORDER BY id
                            {limit_sql}
                        )
                        """,
                        (generics,),
                    )
                    results["rejected_generic"] = cur.rowcount
            else:
                results["would_reject_generic"] = 0

            # 3) below_auto_link_threshold high score + candidate → approved
            min_score = float(args.approve_min_score)
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {T_PARKED_RESOLUTION}
                WHERE review_status = 'open'
                  AND reason = 'below_auto_link_threshold'
                  AND candidate_ftm_id IS NOT NULL
                  AND trim(candidate_ftm_id) <> ''
                  AND COALESCE(match_score, 0) >= %s
                """,
                (min_score,),
            )
            n_approve = int(cur.fetchone()[0] or 0)
            results["would_approve_below_threshold"] = n_approve
            results["approve_min_score"] = min_score
            if args.apply and n_approve:
                cur.execute(
                    f"""
                    UPDATE {T_PARKED_RESOLUTION}
                    SET review_status = 'approved', reviewed_at = NOW()
                    WHERE id IN (
                        SELECT id FROM {T_PARKED_RESOLUTION}
                        WHERE review_status = 'open'
                          AND reason = 'below_auto_link_threshold'
                          AND candidate_ftm_id IS NOT NULL
                          AND trim(candidate_ftm_id) <> ''
                          AND COALESCE(match_score, 0) >= %s
                        ORDER BY id
                        {limit_sql}
                    )
                    """,
                    (min_score,),
                )
                results["approved_below_threshold"] = cur.rowcount

            # 4) bridge_qa left open — report only
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {T_PARKED_RESOLUTION}
                WHERE review_status = 'open'
                  AND reason LIKE 'bridge_qa_mismatch:%'
                """
            )
            results["left_open_bridge_qa"] = int(cur.fetchone()[0] or 0)

            if args.apply:
                conn.commit()
                after = _stats(cur, T_PARKED_RESOLUTION)
                results["after_open_by_reason"] = after
                results["after_open_total"] = sum(after.values())
            else:
                conn.rollback()
        print(results)
        return 0
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
