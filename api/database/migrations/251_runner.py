#!/usr/bin/env python3
"""
Migration 251: Rescore keyword_score using new entity-match formula.

Formula: kw_score = LEAST(0.97, 0.65 + (mc - 1) * 0.08)
  where mc = cardinality(matched_keywords)

Idempotent — always recomputes from source data. Safe to re-run.

Usage:
    cd api/database/migrations && python3 251_runner.py
    # or directly: python3 api/database/migrations/251_runner.py
"""

import sys
import os

# Ensure we can import project config regardless of working dir
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import psycopg2
from config.runtime import env_str


def get_db_params():
    """Load DB connection params from .env (mimics connection.py logic)."""
    # Try multiple .env locations
    for env_path in [
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.join(PROJECT_ROOT, "config/.env"),
        "/etc/news_intel/.env",
    ]:
        if os.path.isfile(env_path):
            break
    else:
        env_path = ""

    params = {}
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        # Check .env file first, then os.environ as fallback
        val = None
        if env_path:
            with open(env_path) as f:
                for line in f:
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        val = v.strip().strip("\"'")
                        break
        if not val:
            val = os.environ.get(key, "")
        params[key.lower()] = val

    return {
        "host": params["db_host"],
        "port": int(params.get("db_port", 5432)),
        "dbname": params["db_name"],
        "user": params["db_user"],
        "password": params["db_password"],
    }


def main():
    print("=" * 60)
    print("Migration 251: Rescore keyword_score")
    print("=" * 60)

    db = get_db_params()
    print(f"Connecting to {db['host']}:{db['port']}/{db['dbname']} as {db['user']}...")

    conn = psycopg2.connect(**db)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Pre-migration snapshot
        cur.execute(
            "SELECT count(*), min(keyword_score), max(keyword_score), "
            "avg(keyword_score)::decimal(5,2) FROM public.storyline_article_suggestions;"
        )
        pre = cur.fetchone()
        print(f"\nBefore: count={pre[0]}, min={pre[1]}, max={pre[2]}, avg={pre[3]}")

        # Count by matched_keywords bucket
        cur.execute(
            "SELECT 'no_match' as label, count(*) FROM public.storyline_article_suggestions "
            "WHERE matched_keywords IS NULL OR matched_keywords = '{}'"
            " UNION ALL "
            "SELECT cardinality(matched_keywords::text[])::text || '_matches', count(*) "
            "FROM public.storyline_article_suggestions "
            "WHERE matched_keywords IS NOT NULL AND matched_keywords <> '{}' "
            "GROUP BY cardinality(matched_keywords::text[]) ORDER BY 1"
        )
        pre_buckets = cur.fetchall()
        print("\nPre-migration buckets:")
        for label, cnt in pre_buckets:
            print(f"  {label}: {cnt}")

        # Execute migration
        cur.execute(
            "UPDATE public.storyline_article_suggestions "
            "SET keyword_score = CASE "
            "    WHEN matched_keywords IS NULL OR matched_keywords = '{}' THEN "
            "        0.65 "
            "    ELSE LEAST(0.97, (0.65 + (cardinality(matched_keywords::text[]) - 1) * 0.08))::decimal(3,2) "
            "END;"
        )
        updated = cur.rowcount
        conn.commit()
        print(f"\n{updated} rows rescored.")

        # Post-migration snapshot
        cur.execute(
            "SELECT count(*), min(keyword_score), max(keyword_score), "
            "avg(keyword_score)::decimal(5,2) FROM public.storyline_article_suggestions;"
        )
        post = cur.fetchone()
        print(f"\nAfter:  count={post[0]}, min={post[1]}, max={post[2]}, avg={post[3]}")

        # Post-migration buckets
        cur.execute(
            "SELECT keyword_score, count(*) FROM public.storyline_article_suggestions "
            "GROUP BY keyword_score ORDER BY keyword_score;"
        )
        post_buckets = cur.fetchall()
        print("\nPost-migration buckets:")
        for score, cnt in post_buckets:
            bar = "#" * (cnt // max(post[0] // 50, 1))
            print(f"  {score:6.2f}: {cnt:6d}  {bar}")

        # Mapping verification
        print("\nScore mapping (expected):")
        for mc in range(0, 8):
            score = min(0.65 + (mc - 1) * 0.08, 0.97) if mc > 0 else 0.65
            actual_count = 0
            for s, c in post_buckets:
                if abs(float(s) - round(score, 2)) < 0.001:
                    actual_count = c
                    break
            print(f"  {mc:1d} match{'es' if mc != 1 else ''} -> "
                  f"{score:.2f} (found {actual_count} rows)")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 60)
    print("Migration 251 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
