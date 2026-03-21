#!/usr/bin/env python3
"""
Poll the database for extracted timeline events (public.chronological_events) and
trace why generation might be idle: article gates, entity rows, recent automation runs.

This is about **discrete extracted events** (Events page / GET /api/{domain}/events),
not intelligence.tracked_events (Investigate / dashboard "Events" count).

Run from project root:
  PYTHONPATH=api uv run python scripts/poll_extracted_events_and_pipeline.py
  # or: cd api && PYTHONPATH=. python ../scripts/poll_extracted_events_and_pipeline.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load .env for DB (same pattern as check_v7_data_collection.py)
env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key, val.strip().strip('"').strip("'"))


def get_conn():
    try:
        from shared.database.connection import get_db_connection

        return get_db_connection()
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


def table_columns(cur, schema: str, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return {r[0] for r in cur.fetchall()}


def table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def main() -> int:
    conn = get_conn()
    if not conn:
        return 1
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=48)

    print("=== Extracted events (public.chronological_events) ===")
    try:
        cur.execute("SELECT COUNT(*) FROM public.chronological_events")
        total = cur.fetchone()[0]
        print(f"  Total rows: {total}")
    except Exception as e:
        print(f"  ERROR (table missing?): {e}")
        conn.close()
        return 1

    schemas = [
        ("politics", "politics"),
        ("finance", "finance"),
        ("science_tech", "science-tech"),
    ]
    print("\n  By domain (event.source_article_id resolves to domain articles):")
    for schema, label in schemas:
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM public.chronological_events ce
                WHERE EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id)
                """
            )
            n = cur.fetchone()[0]
            print(f"    {label}: {n}")
        except Exception as e:
            print(f"    {label}: (skip) {e}")

    print("\n=== Article pipeline gates (matches automation event_extraction selection) ===")
    print(
        "  Phase `event_extraction` only reads articles where:\n"
        "    timeline_processed = false, content length > 100,\n"
        "    processing_status = 'completed' OR enrichment_status IN ('completed','enriched').\n"
        "  It runs in analysis **step 3** (after collection_cycle opens the analysis window).\n"
        "  Entity extraction (`entity_extraction`) is a **separate** earlier phase; events do not require\n"
        "  article_entities rows, but articles must pass processing/enrichment gates above.\n"
    )

    for schema, label in schemas:
        acols = table_columns(cur, schema, "articles")
        need = {"id", "content", "published_at"}
        if not need <= acols:
            print(f"  {label}: articles table missing columns {need - acols}")
            continue

        has_tp = "timeline_processed" in acols
        has_ps = "processing_status" in acols
        has_es = "enrichment_status" in acols

        where_parts = [
            "a.content IS NOT NULL",
            "LENGTH(a.content) > 100",
        ]
        if has_tp:
            where_parts.append("a.timeline_processed = false")
        if has_ps and has_es:
            where_parts.append(
                "(a.processing_status = 'completed' OR a.enrichment_status IN ('completed', 'enriched'))"
            )
        elif has_ps:
            where_parts.append("a.processing_status = 'completed'")
        elif has_es:
            where_parts.append("a.enrichment_status IN ('completed', 'enriched')")

        where_sql = " AND ".join(where_parts)
        try:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.articles a WHERE {where_sql}")
            eligible = cur.fetchone()[0]
        except Exception as e:
            print(f"  {label}: eligible count failed: {e}")
            continue

        backlog_note = ""
        if not has_tp:
            backlog_note = " (no timeline_processed column — migration may be missing; automation may skip events)"

        print(f"  {label}: eligible_for_event_extraction ≈ {eligible}{backlog_note}")

        if has_tp:
            cur.execute(
                f"""
                SELECT COUNT(*) FILTER (WHERE timeline_processed = true),
                       COUNT(*) FILTER (WHERE timeline_processed = false)
                FROM {schema}.articles
                """
            )
            done, pending = cur.fetchone()
            print(f"         timeline_processed: true={done}, false={pending}")

        # Entity extraction footprint (optional table)
        if table_exists(cur, schema, "article_entities"):
            cur.execute(f"SELECT COUNT(DISTINCT article_id) FROM {schema}.article_entities")
            ent_arts = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {schema}.article_entities")
            ent_rows = cur.fetchone()[0]
            print(f"         article_entities: {ent_rows} rows across {ent_arts} distinct articles")
        else:
            print("         article_entities: (table missing)")

    print("\n=== Recent automation runs (automation_run_history, last 48h) ===")
    hist_cols = table_columns(cur, "public", "automation_run_history")
    if not hist_cols:
        print("  Table automation_run_history not found (run migration 161).")
    else:
        phases = (
            "collection_cycle",
            "content_enrichment",
            "entity_extraction",
            "event_extraction",
            "event_deduplication",
            "timeline_generation",
        )
        for phase in phases:
            cur.execute(
                """
                SELECT COUNT(*), MAX(finished_at), BOOL_OR(success)
                FROM public.automation_run_history
                WHERE phase_name = %s AND finished_at >= %s
                """,
                (phase, since),
            )
            cnt, last_fin, any_ok = cur.fetchone()
            last_s = last_fin.isoformat() if last_fin else "never"
            print(f"  {phase}: runs_48h={cnt}, last_finished={last_s}, any_success={any_ok}")

    print("\n=== Interpretation ===")
    print(
        "  • If chronological_events total is 0 but articles are eligible: check LLM/Ollama, API logs\n"
        "    during event_extraction, and automation_run_history for failures.\n"
        "  • If eligible_for_event_extraction is 0: fix processing_status / enrichment / content length\n"
        "    first; event_extraction will not dequeue work.\n"
        "  • If all articles have timeline_processed=true and events are still low: extraction already\n"
        "    ran; new articles need to arrive or reset timeline_processed (operational choice).\n"
        "  • Dashboard 'Events' (tracked_events) is separate — see docs/EVENTS_ZERO_AND_HOW_TO_POPULATE.md\n"
    )

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
