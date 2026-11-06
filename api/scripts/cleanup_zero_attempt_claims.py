#!/usr/bin/env python3
"""Identify and optionally delete extracted_claims rows with zero resolution attempts.

A claim has "zero resolution attempts" when:
  - It was inserted into extracted_claims but never matched to an entity_profiles row, OR
  - Its subject matches no known alias/canonical in the seeded entity pool.

This typically happens for:
  1. Seeded-domain claims rejected because subject is unknown variant (e.g., "Minoru Kihara" vs known "Kihara Minoris")
  2. Old context-anchored data where the underlying article/context is already gone
  3. Very short/generic subjects that were never promoted

Usage:
    # Dry-run preview (default)
    PYTHONPATH=api uv run python api/scripts/cleanup_zero_attempt_claims.py

    # Show per-domain breakdown
    PYTHONPATH=api uv run python api/scripts/cleanup_zero_attempt_claims.py --breakdown

    # Delete claims older than 7 days (DRY-RUN by default — add --execute to confirm)
    PYTHONPATH=api uv run python api/scripts/cleanup_zero_attempt_claims.py --max-age-days 7 --execute
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(API_ROOT)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(API_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(PROJECT_ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(PROJECT_ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

logger = logging.getLogger(__name__)


def _zero_attempt_where(age_days: int | None) -> tuple[str, list]:
    clauses, p = ["ec.subject_text IS NOT NULL", "length(trim(ec.subject_text)) > 1"], []
    if age_days is not None:
        clauses.append("ec.inserted_at < NOW() - INTERVAL %s")
        p.append(f"{age_days} days")
    return " AND ".join(clauses), p


def build_count_query(age_days: int | None = None) -> tuple[str, list]:
    w, p = _zero_attempt_where(age_days)
    q = f"""
        SELECT COUNT(*)
        FROM intelligence.extracted_claims ec
        WHERE COALESCE((
            SELECT COUNT(DISTINCT ep.id)
            FROM intelligence.entity_profiles ep
            WHERE lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
               OR lower(trim(COALESCE(ep.metadata->>'display_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
        ), 0) = 0
          AND {w}
    """
    return q, p


def build_query(age_days: int | None = None) -> tuple[str, list]:
    w, p = _zero_attempt_where(age_days)
    return f"""
        SELECT ec.context_id, ec.subject_text, ec.predicate_text, ec.object_text,
               ec.confidence, ec.inserted_at,
               COALESCE((
                   SELECT COUNT(DISTINCT ep.id)
                   FROM intelligence.entity_profiles ep
                   WHERE ep.domain_key = a2.domain_key
                     AND (
                         lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
                         OR lower(trim(COALESCE(ep.metadata->>'display_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
                     )
               ), 0) AS resolution_attempts,
               a2.domain_key
        FROM intelligence.extracted_claims ec
        LEFT JOIN (
            SELECT context_id, domain_key
            FROM intelligence.article_to_context GROUP BY context_id, domain_key
        ) a2 ON ec.context_id = a2.context_id
        WHERE {w} ORDER BY ec.inserted_at DESC
    """, p


def build_breakdown_query(age_days: int | None = None) -> str:
    w, _ = _zero_attempt_where(age_days)
    return f"""
        SELECT COALESCE(dk.domain_key, 'unattributed') AS domain_key, COUNT(*) AS claim_count
        FROM intelligence.extracted_claims ec
        LEFT JOIN (SELECT context_id, domain_key FROM intelligence.article_to_context GROUP BY context_id, domain_key) dk
            ON ec.context_id = dk.context_id
        WHERE COALESCE((
            SELECT COUNT(DISTINCT ep.id) FROM intelligence.entity_profiles ep
            WHERE ep.domain_key = dk.domain_key
              AND (lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
                OR lower(trim(COALESCE(ep.metadata->>'display_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%')
        ), 0) = 0 AND {w}
        GROUP BY dk.domain_key ORDER BY claim_count DESC
    """


def build_age_buckets_query(age_days: int | None = None) -> str:
    w, _ = _zero_attempt_where(age_days)
    return f"""
        SELECT CASE
            WHEN ec.inserted_at > NOW() - INTERVAL '6 hours' THEN '0-6h'
            WHEN ec.inserted_at > NOW() - INTERVAL '24 hours' THEN '6-24h'
            WHEN ec.inserted_at > NOW() - INTERVAL '3 days'  THEN '1-3d'
            WHEN ec.inserted_at > NOW() - INTERVAL '7 days'  THEN '3-7d'
            WHEN ec.inserted_at > NOW() - INTERVAL '30 days' THEN '7-30d'
            ELSE '30d+' END AS age_bucket, COUNT(*) AS claim_count
        FROM intelligence.extracted_claims ec
        WHERE COALESCE((
            SELECT COUNT(DISTINCT ep.id) FROM intelligence.entity_profiles ep
            WHERE lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
               OR lower(trim(COALESCE(ep.metadata->>'display_name', ''))) LIKE '%%' || lower(trim(ec.subject_text)) || '%%'
        ), 0) = 0 AND {w}
        GROUP BY age_bucket ORDER BY min(ec.inserted_at)
    """


def run(args: argparse.Namespace) -> int:
    from api.shared.database import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: No database connection")
        return 1
    age_days = args.max_age_days
    total_q, total_p = build_count_query(age_days)
    with conn.cursor() as cur:
        cur.execute(total_q, total_p)
        total = cur.fetchone()[0] or 0
        print(f"\n{'='*70}")
        print("Zero-attempt extracted_claims inventory")
        print(f"{'='*70}")
        print(f"Total matching claims: {total}")
        if args.breakdown:
            cur.execute(build_breakdown_query(age_days))
            print("\n--- Breakdown by domain ---")
            for row in cur.fetchall():
                print(f"  {row[0]:30s}  {row[1]:>8d} claims")
        cur.execute(build_age_buckets_query(age_days))
        print("\n--- Breakdown by age ---")
        for row in cur.fetchall():
            print(f"  {row[0]:12s}  {row[1]:>8d} claims")
        query, params = build_query(age_days)
        cur.execute(query, params)
        rows = cur.fetchall()
        sample = rows[: args.limit]
        if sample:
            print(f"\n--- Sample of first {len(sample)} records ---")
            hdr = f"{'context_id':>12s} {'subject_text':<40s} {'domain_key':<25s} {'inserted_at':<28s}"
            print(hdr + "\n" + "-" * 110)
            for r in sample:
                subj = (r[1] or "")[:38]
                dk = str(r[6] or "unattributed")[:23]
                ts = str(r[5] or "")[:26]
                print(f"{r[0]:>12d} {subj:<40s} {dk:<25s} {ts:<28s}")
        if args.execute and sample:
            ids_str = ",".join(str(r[0]) for r in sample)
            cur.execute(f"DELETE FROM intelligence.extracted_claims WHERE id IN ({ids_str})")
            print(f"\n>>> DELETED {cur.rowcount} claims (use --execute to confirm)")
        elif args.execute and not sample:
            print("\n>>> No claims matched the criteria")
    try:
        conn.close()
    except Exception:
        pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Identify and optionally delete extracted_claims with zero resolution attempts."
    )
    parser.add_argument("--max-age-days", type=int, default=None, help="Only consider claims older than N days (default: all)")
    parser.add_argument("--breakdown", action="store_true", help="Show per-domain and per-age breakdown")
    parser.add_argument("--limit", type=int, default=20, help="Max sample rows to display (default: 20)")
    parser.add_argument("--execute", action="store_true", help="Actually delete matching claims (default: dry-run)")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

