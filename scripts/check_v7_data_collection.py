#!/usr/bin/env python3
"""
Check v7 data collection health: enrichment, documents, synthesis.
Run from project root: uv run python scripts/check_v7_data_collection.py
Or with api on path: cd api && python -c "import sys; sys.path.insert(0,'.'); exec(open('../scripts/check_v7_data_collection.py').read())"
"""
import os
import sys
from datetime import datetime, timezone, timedelta

# Allow running from project root or api
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)

# Load .env for DB
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

# Widow password file fallback
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())

def get_conn():
    try:
        from shared.database.connection import get_db_connection
        return get_db_connection()
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


def run_checks(conn):
    """
    Run data quality checks; returns list of lines to print (no header/footer).
    Used by this script and by full_system_status_check.py.
    """
    lines = []
    now = datetime.now(timezone.utc)
    last24 = now - timedelta(hours=24)
    cur = conn.cursor()

    # 1) Articles: total vs short vs enriched (content length)
    lines.append("")
    lines.append("--- Articles (by domain) ---")
    for schema, domain in [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]:
        try:
            cur.execute(
                f"""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE content IS NULL OR LENGTH(content) < 500),
                  COUNT(*) FILTER (WHERE content IS NOT NULL AND LENGTH(content) >= 500)
                FROM {schema}.articles
                """
            )
            total, short, long = cur.fetchone()
            lines.append(f"  {domain}: total={total}, short/missing={short}, enriched (>=500 chars)={long}")
        except Exception as e:
            lines.append(f"  {domain}: error - {e}")

    # 2) Last 24h runs for v7 phases (optional: table may not exist yet)
    lines.append("")
    lines.append("--- v7 phases (last 24h runs) ---")
    v7_phases = [
        "content_enrichment",
        "document_collection",
        "document_processing",
        "storyline_synthesis",
        "daily_briefing_synthesis",
    ]
    try:
        cur.execute(
            """
            SELECT phase_name, COUNT(*), MAX(finished_at)
            FROM automation_run_history
            WHERE phase_name = ANY(%s) AND finished_at >= %s AND success = true
            GROUP BY phase_name
            """,
            (v7_phases, last24),
        )
        rows = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for p in v7_phases:
            if p in rows:
                count, last = rows[p]
                lines.append(f"  {p}: {count} runs, last at {last}")
            else:
                lines.append(f"  {p}: no successful run in last 24h")
    except Exception as e:
        conn.rollback()
        lines.append(f"  (automation_run_history not available: {e})")

    # 3) Processed documents
    lines.append("")
    lines.append("--- Documents ---")
    try:
        cur.execute(
            """
            SELECT COUNT(*), COUNT(*) FILTER (WHERE extracted_sections IS NOT NULL AND extracted_sections != '[]')
            FROM intelligence.processed_documents
            """
        )
        total_docs, processed = cur.fetchone()
        lines.append(f"  processed_documents: total={total_docs}, with extracted sections={processed}")
    except Exception as e:
        conn.rollback()
        lines.append(f"  Error: {e}")

    # 4) Storylines with synthesis
    lines.append("")
    lines.append("--- Storyline synthesis ---")
    for schema, domain in [("politics", "politics"), ("finance", "finance"), ("science_tech", "science-tech")]:
        try:
            cur.execute(
                f"""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE synthesized_content IS NOT NULL AND synthesized_content != '')
                FROM {schema}.storylines
                """
            )
            total, with_synth = cur.fetchone()
            lines.append(f"  {domain}: storylines={total}, with synthesized_content={with_synth}")
        except Exception as e:
            lines.append(f"  {domain}: error - {e}")

    # 5) Contexts (article + pdf_section)
    lines.append("")
    lines.append("--- Contexts ---")
    try:
        cur.execute(
            "SELECT source_type, COUNT(*) FROM intelligence.contexts GROUP BY source_type"
        )
        for row in cur.fetchall():
            lines.append(f"  {row[0]}: {row[1]}")
    except Exception as e:
        lines.append(f"  Error: {e}")

    return lines


def main():
    conn = get_conn()
    if not conn:
        print("Cannot connect to database. Set DB_* or .db_password_widow.")
        return 1

    print("=" * 60)
    print("v7 Data Collection Health (as of now)")
    print("=" * 60)
    for line in run_checks(conn):
        print(line)
    conn.close()
    print("\n" + "=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
