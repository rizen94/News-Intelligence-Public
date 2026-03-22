#!/usr/bin/env python3
"""Verify critical DB migrations are applied (133, 160–172, 176 ledger, 177–179 domain event pipeline, 183 temporal_status, 184 processed_documents provenance).

Run from project root (requires DB_PASSWORD and network to DB):

  PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py

Checks:
  133  public.chronological_events (is_ongoing, date_precision)
  160  intelligence.processed_documents
  161  public.automation_run_history
  164–167 domain articles/storylines quality & enrichment (as before)
  168  public.automation_state
  169  intelligence.storyline_rag_context
  170  intelligence.wikipedia_knowledge + politics.entity_canonical.description
  171  intelligence.tracked_events.storyline_id
  172  public.automation_run_history_daily, public.log_archive_daily_rollup
  176  public.applied_migrations (operational ledger)
  177  politics.articles.timeline_processed + politics.article_entities (domain event/entity pipeline)
  178  politics.articles.timeline_events_generated (event_extraction article UPDATE)
  179  politics (sample) story_entity_index for story_continuation matching
  180  legal.* core tables — only when public.domains.domain_key = 'legal' exists (optional domain)
  183  public.chronological_events.temporal_status (scheduled vs occurred)
  184  intelligence.processed_documents file_hash, file_size_bytes, extraction_method
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

        # --- 133: event extraction v5 columns ---
        for col in ("is_ongoing", "date_precision", "source_count"):
            if check_column(cur, "public", "chronological_events", col):
                ok.append(f"133: public.chronological_events.{col}")
            else:
                missing.append(f"133: public.chronological_events.{col}")

        # --- 160 ---
        if check_table(cur, "intelligence", "processed_documents"):
            ok.append("160: intelligence.processed_documents")
        else:
            missing.append("160: intelligence.processed_documents")

        # --- 161 ---
        if check_table(cur, "public", "automation_run_history"):
            ok.append("161: public.automation_run_history")
        else:
            missing.append("161: public.automation_run_history")

        # --- 164–167 (domain samples) ---
        if check_column(cur, "politics", "articles", "quality_tier"):
            ok.append("164: politics.articles.quality_tier")
        else:
            missing.append("164: politics.articles.quality_tier")

        if check_column(cur, "politics", "storylines", "min_quality_tier"):
            ok.append("165: politics.storylines.min_quality_tier")
        else:
            missing.append("165: politics.storylines.min_quality_tier")

        if check_column(cur, "politics", "article_topic_assignments", "assignment_context"):
            ok.append("166: politics.article_topic_assignments.assignment_context")
        else:
            missing.append("166: politics.article_topic_assignments.assignment_context")

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

        # --- 168 ---
        if check_table(cur, "public", "automation_state"):
            ok.append("168: public.automation_state")
        else:
            missing.append("168: public.automation_state")

        # --- 169 ---
        if check_table(cur, "intelligence", "storyline_rag_context"):
            ok.append("169: intelligence.storyline_rag_context")
        else:
            missing.append("169: intelligence.storyline_rag_context")

        # --- 170 ---
        if check_table(cur, "intelligence", "wikipedia_knowledge"):
            ok.append("170: intelligence.wikipedia_knowledge")
        else:
            missing.append("170: intelligence.wikipedia_knowledge")
        if check_column(cur, "politics", "entity_canonical", "description"):
            ok.append("170: politics.entity_canonical.description")
        else:
            missing.append("170: politics.entity_canonical.description")

        # --- 171 ---
        if check_column(cur, "intelligence", "tracked_events", "storyline_id"):
            ok.append("171: intelligence.tracked_events.storyline_id")
        else:
            missing.append("171: intelligence.tracked_events.storyline_id")

        # --- 172 ---
        if check_table(cur, "public", "automation_run_history_daily"):
            ok.append("172: public.automation_run_history_daily")
        else:
            missing.append("172: public.automation_run_history_daily")
        if check_table(cur, "public", "log_archive_daily_rollup"):
            ok.append("172: public.log_archive_daily_rollup")
        else:
            missing.append("172: public.log_archive_daily_rollup")

        # --- 176 ---
        if check_table(cur, "public", "applied_migrations"):
            ok.append("176: public.applied_migrations")
        else:
            missing.append("176: public.applied_migrations")

        # --- 177 (domain timeline + article_entities; sample politics) ---
        if check_column(cur, "politics", "articles", "timeline_processed"):
            ok.append("177: politics.articles.timeline_processed")
        else:
            missing.append("177: politics.articles.timeline_processed")
        if check_table(cur, "politics", "article_entities"):
            ok.append("177: politics.article_entities")
        else:
            missing.append("177: politics.article_entities")

        # --- 178 ---
        if check_column(cur, "politics", "articles", "timeline_events_generated"):
            ok.append("178: politics.articles.timeline_events_generated")
        else:
            missing.append("178: politics.articles.timeline_events_generated")

        # --- 179 (story_entity_index per domain; sample politics) ---
        if check_table(cur, "politics", "story_entity_index"):
            ok.append("179: politics.story_entity_index")
        else:
            missing.append("179: politics.story_entity_index")

        # --- 183 ---
        if check_column(cur, "public", "chronological_events", "temporal_status"):
            ok.append("183: public.chronological_events.temporal_status")
        else:
            missing.append("183: public.chronological_events.temporal_status")

        # --- 184 (processed_documents provenance) ---
        if check_column(cur, "intelligence", "processed_documents", "file_hash") and check_column(
            cur, "intelligence", "processed_documents", "file_size_bytes"
        ) and check_column(cur, "intelligence", "processed_documents", "extraction_method"):
            ok.append("184: intelligence.processed_documents file provenance columns")
        else:
            missing.append("184: intelligence.processed_documents file provenance columns")

        cur.close()
    finally:
        conn.close()

    print("=" * 60)
    print("Migration verification (133, 160–172, 176, 177, 178, 179, 180 if legal, 183, 184)")
    print("=" * 60)
    for s in ok:
        print(f"  OK   {s}")
    for s in missing:
        print(f"  MISS {s}")
    print("=" * 60)
    if missing:
        print(
            "Apply missing migrations (active: api/database/migrations/; "
            "archived: api/database/migrations/archive/historical/), then run this script again."
        )
        sys.exit(1)
    print("All checked migrations are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
