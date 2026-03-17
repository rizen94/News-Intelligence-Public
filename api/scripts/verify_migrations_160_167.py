#!/usr/bin/env python3
"""Verify migrations 160–167 are fully applied (tables/columns exist). Run after migration 167 completes.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/verify_migrations_160_167.py
"""

import os
import sys

try:
    from dotenv import load_dotenv
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
):
    pw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
    try:
        with open(pw_path) as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_column(cur, schema: str, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (schema, table, column),
    )
    return cur.fetchone() is not None


def check_index(cur, schema: str, index_name: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM pg_indexes WHERE schemaname = %s AND indexname = %s
        """,
        (schema, index_name),
    )
    return cur.fetchone() is not None


def check_table(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def main():
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        sys.exit(1)

    ok = []
    missing = []
    try:
        cur = conn.cursor()
        # 160: intelligence.processed_documents
        if check_table(cur, "intelligence", "processed_documents"):
            ok.append("160: intelligence.processed_documents")
        else:
            missing.append("160: intelligence.processed_documents")

        # 161: automation_run_history (public)
        if check_table(cur, "public", "automation_run_history"):
            ok.append("161: public.automation_run_history")
        else:
            missing.append("161: public.automation_run_history")

        # 164: articles.quality_tier
        if check_column(cur, "politics", "articles", "quality_tier"):
            ok.append("164: politics.articles.quality_tier")
        else:
            missing.append("164: politics.articles.quality_tier")

        # 165: storylines.min_quality_tier
        if check_column(cur, "politics", "storylines", "min_quality_tier"):
            ok.append("165: politics.storylines.min_quality_tier")
        else:
            missing.append("165: politics.storylines.min_quality_tier")

        # 166: article_topic_assignments.assignment_context
        if check_column(cur, "politics", "article_topic_assignments", "assignment_context"):
            ok.append("166: politics.article_topic_assignments.assignment_context")
        else:
            missing.append("166: politics.article_topic_assignments.assignment_context")

        # 167: enrichment_attempts, enrichment_status, partial index (all 3 domains)
        for schema in ("politics", "finance", "science_tech"):
            if check_column(cur, schema, "articles", "enrichment_attempts") and check_column(
                cur, schema, "articles", "enrichment_status"
            ):
                ok.append(f"167: {schema}.articles.enrichment_attempts/status")
            else:
                missing.append(f"167: {schema}.articles.enrichment_attempts/status")
        if check_index(cur, "politics", "idx_politics_articles_enrichment_backlog"):
            ok.append("167: idx_politics_articles_enrichment_backlog")
        else:
            missing.append("167: idx_politics_articles_enrichment_backlog")

        cur.close()
    finally:
        conn.close()

    print("=" * 60)
    print("Migration verification (160–167)")
    print("=" * 60)
    for s in ok:
        print(f"  OK   {s}")
    for s in missing:
        print(f"  MISS {s}")
    print("=" * 60)
    if missing:
        print("Apply missing migrations, then run this script again.")
        sys.exit(1)
    print("All checked migrations are present. Database consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
