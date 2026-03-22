#!/usr/bin/env python3
"""
Investigate storyline automation: counts, schema, and narrative assembly.
Run from project root: PYTHONPATH=api .venv/bin/python scripts/investigate_storyline_automation.py
"""
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)
for _ in (ROOT, os.path.join(ROOT, "api")):
    if _ not in sys.path:
        sys.path.insert(0, _)

# Env
if os.path.isfile(os.path.join(ROOT, ".env")):
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ["DB_PASSWORD"] = f.read().splitlines()[0].strip()


def main():
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("DB connection failed")
        return 1

    cur = conn.cursor()
    print("=" * 60)
    print("Storyline automation investigation")
    print("=" * 60)

    # 1) Storylines per schema: total, automation_enabled, with editorial_document / analysis_summary
    print("\n--- Storylines by schema ---")
    for schema in ("politics", "finance", "science_tech"):
        try:
            cur.execute(f"""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE automation_enabled = true),
                  COUNT(*) FILTER (WHERE status = 'active'),
                  COUNT(*) FILTER (WHERE (editorial_document IS NOT NULL AND editorial_document != '{{}}'::jsonb)),
                  COUNT(*) FILTER (WHERE LENGTH(COALESCE(analysis_summary, '')) >= 100),
                  COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id))
                FROM {schema}.storylines s
            """)
            r = cur.fetchone()
            total, auto_on, active, with_ed, with_analysis, with_articles = r
            print(f"  {schema}: total={total}, automation_enabled={auto_on}, active={active}, with editorial_doc={with_ed}, with analysis(>=100)={with_analysis}, with articles={with_articles}")
        except Exception as e:
            print(f"  {schema}: error - {e}")
            conn.rollback()

    # 2) public.storylines if exists (legacy)
    try:
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'storylines'
        """)
        if cur.fetchone()[0]:
            cur.execute("SELECT COUNT(*) FROM public.storylines")
            print(f"\n  public.storylines: count={cur.fetchone()[0]} (legacy; automation uses domain schemas)")
    except Exception as e:
        conn.rollback()
        print(f"  public check: {e}")

    # 3) storyline_article_suggestions (pending)
    print("\n--- Storyline article suggestions (public) ---")
    try:
        cur.execute("""
            SELECT status, COUNT(*) FROM public.storyline_article_suggestions
            GROUP BY status ORDER BY status
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
    except Exception as e:
        print(f"  Error: {e}")
        conn.rollback()

    # 4) Last 24h automation runs for storyline_automation
    print("\n--- storyline_automation phase (last 24h) ---")
    try:
        cur.execute("""
            SELECT COUNT(*), MAX(finished_at)
            FROM automation_run_history
            WHERE phase_name = 'storyline_automation' AND started_at >= NOW() - INTERVAL '24 hours'
        """)
        r = cur.fetchone()
        print(f"  runs: {r[0]}, last: {r[1]}")
    except Exception as e:
        print(f"  Error: {e}")
        conn.rollback()

    # 5) storyline_processing phase (last 24h)
    print("\n--- storyline_processing phase (last 24h) ---")
    try:
        cur.execute("""
            SELECT COUNT(*), MAX(finished_at)
            FROM automation_run_history
            WHERE phase_name = 'storyline_processing' AND started_at >= NOW() - INTERVAL '24 hours'
        """)
        r = cur.fetchone()
        print(f"  runs: {r[0]}, last: {r[1]}")
    except Exception as e:
        print(f"  Error: {e}")
        conn.rollback()

    conn.close()
    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
