#!/usr/bin/env python3
"""
Manually run v5 event extraction (and optional deduplication) to validate commits.

Use after migrations **177** (timeline_processed, article_entities) and **178**
(timeline_events_generated). Compare `public.chronological_events` counts before/after.

From repo root:
  PYTHONPATH=api uv run python scripts/run_event_pipeline_manual.py
  PYTHONPATH=api uv run python scripts/run_event_pipeline_manual.py --domain finance --limit 2
  PYTHONPATH=api uv run python scripts/run_event_pipeline_manual.py --dry-run   # LLM only, no DB writes

Requires a working **Ollama** endpoint (same as the API) for non-dry-run extraction.

API alternative (enqueue automation task):
  curl -s -X POST http://localhost:8000/api/system_monitoring/monitoring/trigger_phase \\
    -H "Content-Type: application/json" -d '{"phase":"event_extraction"}'
  # then event_deduplication:
  curl -s -X POST ... -d '{"phase":"event_deduplication"}'
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

DOMAIN_TO_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def _count_events(cur) -> int:
    cur.execute("SELECT COUNT(*) FROM public.chronological_events")
    return cur.fetchone()[0]


async def run_extraction_for_schema(
    schema: str,
    domain_key: str,
    limit: int,
    dry_run: bool,
) -> tuple[int, int, int]:
    """Returns (articles_tried, events_extracted, events_saved)."""
    from shared.database.connection import get_db_connection
    from services.event_extraction_service import EventExtractionService

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("No database connection")

    svc = EventExtractionService()
    articles_tried = 0
    events_extracted = 0
    events_saved = 0

    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT a.id, a.content, a.published_at,
                   (
                       SELECT sa.storyline_id::text
                       FROM {schema}.storyline_articles sa
                       WHERE sa.article_id = a.id
                       ORDER BY sa.added_at DESC NULLS LAST
                       LIMIT 1
                   ) AS storyline_id
            FROM {schema}.articles a
            WHERE a.timeline_processed = false
              AND a.content IS NOT NULL
              AND LENGTH(a.content) > 100
              AND (
                  a.processing_status = 'completed'
                  OR a.enrichment_status IN ('completed', 'enriched')
              )
            ORDER BY a.published_at DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()

        for article_id, content, pub_date, storyline_id in rows:
            articles_tried += 1
            if pub_date is None:
                pub_date = datetime.now(timezone.utc)
            events = await svc.extract_events_from_article(
                article_id=article_id,
                content=content,
                pub_date=pub_date,
                storyline_id=storyline_id,
                domain=domain_key,
            )
            events_extracted += len(events)
            print(f"  article_id={article_id} LLM returned {len(events)} event(s)")
            if dry_run:
                continue
            saved = await svc.save_events(events, conn)
            events_saved += saved
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET timeline_processed = true,
                    timeline_events_generated = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (len(events), article_id),
            )
            cur.close()
            conn.commit()
            print(f"    saved={saved} rows to public.chronological_events; article marked timeline_processed")

    finally:
        await svc.close()
        conn.close()

    return articles_tried, events_extracted, events_saved


async def run_dedup() -> dict:
    from shared.database.connection import get_db_connection
    from services.event_deduplication_service import EventDeduplicationService

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("No database connection")
    try:
        svc = EventDeduplicationService(conn)
        stats = await svc.deduplicate_recent(limit=100)
        return stats
    finally:
        conn.close()


async def async_main(args: argparse.Namespace) -> int:
    from shared.database.connection import get_db_connection

    schema = DOMAIN_TO_SCHEMA.get(args.domain)
    if not schema:
        print(f"Unknown --domain {args.domain}; use one of: {list(DOMAIN_TO_SCHEMA)}")
        return 1

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB connection")
        return 1
    try:
        cur = conn.cursor()
        before = _count_events(cur)
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = 'articles'
              AND column_name IN ('timeline_processed', 'timeline_events_generated')
            """,
            (schema,),
        )
        cols = {r[0] for r in cur.fetchall()}
        cur.close()
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    print("=== Manual event pipeline ===")
    print(f"  domain={args.domain} schema={schema} limit={args.limit} dry_run={args.dry_run}")
    print(f"  public.chronological_events count before: {before}")
    need = {"timeline_processed", "timeline_events_generated"}
    missing = need - cols
    if missing:
        print(f"  WARNING: {schema}.articles missing columns {missing} — apply migrations 177/178")

    tried, extracted, saved = await run_extraction_for_schema(
        schema, args.domain, args.limit, args.dry_run
    )
    print(f"  articles_tried={tried} events_from_llm={extracted} events_saved={saved}")

    if not args.dry_run and not args.skip_dedup:
        stats = await run_dedup()
        print(f"  deduplication: checked={stats['checked']} merged={stats['merged']}")

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            after = _count_events(cur)
            cur.close()
            print(f"  public.chronological_events count after: {after} (delta {after - before})")
        finally:
            conn.close()

    if tried == 0:
        print(
            "\nNo eligible articles (timeline_processed=false, content>100, "
            "processing/enrichment completed). Check poll_extracted_events_and_pipeline.py."
        )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Manual event extraction + dedup validation")
    p.add_argument("--domain", default="politics", choices=list(DOMAIN_TO_SCHEMA.keys()))
    p.add_argument("--limit", type=int, default=1, help="Max articles to process per run")
    p.add_argument("--dry-run", action="store_true", help="Call LLM but do not write DB")
    p.add_argument("--skip-dedup", action="store_true", help="Skip event_deduplication step")
    args = p.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
