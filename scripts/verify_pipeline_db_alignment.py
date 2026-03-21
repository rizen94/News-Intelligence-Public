#!/usr/bin/env python3
"""
Compare live PostgreSQL objects to what the v8 data pipeline reads/writes.

Read-only. From repo root:
  PYTHONPATH=api uv run python scripts/verify_pipeline_db_alignment.py
  PYTHONPATH=api uv run python scripts/verify_pipeline_db_alignment.py --write-report docs/PIPELINE_DB_ALIGNMENT_REPORT.md

Exit 1 if any required table/column is missing.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
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

DOMAIN_SCHEMAS = ("politics", "finance", "science_tech")

# (area_label, schema_or_DOMAIN_TOKEN, table, columns)
# Use "__domain__" to fan out to politics, finance, science_tech
RAW_CHECKS: list[tuple[str, str, str, list[str]]] = [
    ("RSS / collection → articles", "__domain__", "articles", ["id", "title", "url", "content", "processing_status"]),
    ("RSS / collection", "__domain__", "rss_feeds", ["id", "feed_url"]),
    ("content_enrichment", "__domain__", "articles", ["enrichment_status", "enrichment_attempts"]),
    ("topic_extraction_queue (after enrich)", "__domain__", "topic_extraction_queue", ["article_id", "status"]),
    ("entity_extraction", "__domain__", "article_entities", ["article_id", "entity_name", "canonical_entity_id"]),
    ("entity_extraction", "__domain__", "entity_canonical", ["id", "canonical_name"]),
    ("event_extraction gates + UPDATE", "__domain__", "articles", ["timeline_processed", "timeline_events_generated"]),
    ("event_extraction INSERT", "public", "chronological_events", ["event_id", "source_article_id", "title", "event_fingerprint"]),
    ("event_deduplication", "public", "chronological_events", ["canonical_event_id"]),
    ("context_sync", "intelligence", "contexts", ["id", "domain_key", "content"]),
    ("context_sync", "intelligence", "article_to_context", ["article_id", "domain_key", "context_id"]),
    ("document_processing", "intelligence", "processed_documents", ["id", "metadata", "extracted_sections"]),
    ("automation_run_history", "public", "automation_run_history", ["phase_name", "finished_at", "success"]),
    ("automation_state", "public", "automation_state", ["key", "value"]),
    ("applied_migrations ledger", "public", "applied_migrations", ["migration_id", "applied_at"]),
]


def expand_raw() -> list[tuple[str, str, str, list[str]]]:
    out: list[tuple[str, str, str, list[str]]] = []
    for area, schema, table, cols in RAW_CHECKS:
        if schema == "__domain__":
            for dom in DOMAIN_SCHEMAS:
                out.append((f"{area} [{dom}]", dom, table, cols))
        else:
            out.append((area, schema, table, cols))
    return out


def merge_by_table(rows: list[tuple[str, str, str, list[str]]]):
    """(schema, table) -> (set columns, list area labels)"""
    colmap: dict[tuple[str, str], set[str]] = defaultdict(set)
    areas: dict[tuple[str, str], list[str]] = defaultdict(list)
    for area, schema, table, cols in rows:
        key = (schema, table)
        colmap[key].update(cols)
        areas[key].append(area)
    return colmap, areas


def table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def table_columns(cur, schema: str, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return {r[0] for r in cur.fetchall()}


def row_count(cur, schema: str, table: str) -> int | None:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        return cur.fetchone()[0]
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-report",
        metavar="PATH",
        help="Write markdown report under repo root unless absolute",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    lines: list[str] = []

    def out(s: str = "") -> None:
        lines.append(s)
        print(s)

    colmap, areas = merge_by_table(expand_raw())

    out(f"# Pipeline ↔ database alignment ({datetime.now(timezone.utc).isoformat()} UTC)")
    out()
    out("## Required tables and columns (merged per object)")
    out()
    out("| `schema.table` | Status | Rows | Required by (pipeline areas) |")
    out("|------------------|--------|------|------------------------------|")

    missing_any = False
    with conn.cursor() as cur:
        for (schema, table) in sorted(colmap.keys(), key=lambda x: (x[0], x[1])):
            req = sorted(colmap[(schema, table)])
            area_labels = areas[(schema, table)]
            label_short = "; ".join(sorted(set(area_labels))[:3])
            if len(set(area_labels)) > 3:
                label_short += f"; +{len(set(area_labels)) - 3} more"

            if not table_exists(cur, schema, table):
                out(f"| `{schema}.{table}` | **MISSING** | — | {label_short} |")
                missing_any = True
                continue

            cols = table_columns(cur, schema, table)
            miss = [c for c in req if c not in cols]
            rc = row_count(cur, schema, table)
            rc_s = f"{rc:,}" if rc is not None else "n/a"
            if miss:
                out(f"| `{schema}.{table}` | **INCOMPLETE** `{miss}` | {rc_s} | {label_short} |")
                missing_any = True
            else:
                note = ""
                if table == "chronological_events" and rc == 0:
                    note = " *(`event_extraction` may still be idle or LLM returned no events)*"
                out(f"| `{schema}.{table}` | OK | {rc_s} | {label_short} |{note}")

        out()
        out("## Persistence signals (processed data landing)")
        out()
        out("| Check | Meaning |")
        out("|-------|---------|")
        for dom in DOMAIN_SCHEMAS:
            if not table_exists(cur, dom, "articles"):
                continue
            cols = table_columns(cur, dom, "articles")
            if "timeline_processed" in cols:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FILTER (WHERE timeline_processed = true),
                           COUNT(*) FILTER (WHERE timeline_processed = false)
                    FROM "{dom}".articles
                    """
                )
                t, f = cur.fetchone()
                out(f"| `{dom}.articles` timeline | processed={t:,} pending={f:,} |")
        cur.execute(
            "SELECT COUNT(*) FROM public.chronological_events WHERE extraction_timestamp > NOW() - INTERVAL '7 days'"
        )
        recent_ev = cur.fetchone()[0]
        out(f"| `chronological_events` last 7d | {recent_ev:,} rows with recent extraction_timestamp |")
        cur.execute(
            """
            SELECT COUNT(*) FROM public.automation_run_history
            WHERE finished_at > NOW() - INTERVAL '24 hours' AND success = true
            """
        )
        ar24 = cur.fetchone()[0]
        out(f"| `automation_run_history` 24h | {ar24:,} successful phase finishes |")

        out()
        out("## Code ↔ DB risks (manual follow-up)")
        out()
        out(
            "- **`MetadataEnrichmentService._update_article_metadata`** — `UPDATE articles` without schema; "
            "safe only if DB `search_path` includes the target domain. Prefer `enrich_article_for_schema`."
        )
        out(
            "- **`RSSFetchingModule._save_article`** — `INSERT INTO articles` via SQLAlchemy; confirm session "
            "search_path matches the feed's domain."
        )
        out(
            "- **Deduplication `checked=0`** — normal when `chronological_events` is empty; run extraction first."
        )
        out()

    conn.close()

    if args.write_report:
        path = args.write_report if os.path.isabs(args.write_report) else os.path.join(ROOT, args.write_report)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        preamble = (
            "<!-- Auto-generated by scripts/verify_pipeline_db_alignment.py -->\n\n"
            "This report compares **live PostgreSQL objects** to tables/columns the v8 automation "
            "pipeline expects for collection, enrichment, entities, events, contexts, documents, "
            "and automation history. Regenerate after migrations or pipeline changes.\n\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(preamble)
            f.write("\n".join(lines))
        print(f"\nWrote {path}")

    if missing_any:
        out("**Result: FAIL** — fix schema/migrations before relying on pipeline writes.")
        return 1
    out("**Result: OK** — tables/columns match pipeline expectations; use signals above + logs to confirm runtime writes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
