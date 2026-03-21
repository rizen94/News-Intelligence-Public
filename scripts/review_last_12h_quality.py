#!/usr/bin/env python3
"""
Review material assembled in the last 12 hours and assess quality (post-v8).
Compares last 12h vs previous 12h for articles, storylines, automation runs.
Run from project root: PYTHONPATH=api .venv/bin/python scripts/review_last_12h_quality.py
"""
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)

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


def run_review(conn):
    now = datetime.now(timezone.utc)
    last_12h = now - timedelta(hours=12)
    prev_12h = last_12h - timedelta(hours=12)  # 12–24h ago
    lines = []

    lines.append("=" * 70)
    lines.append("Last 12 hours review (v8) — quality and assembly")
    lines.append(f"  Now (UTC): {now.isoformat()}")
    lines.append(f"  Window: {last_12h.isoformat()} → now")
    lines.append("=" * 70)

    cur = conn.cursor()

    # --- Automation runs (last 12h): v8 phases
    lines.append("")
    lines.append("--- Automation runs (last 12h) ---")
    try:
        cur.execute(
            """
            SELECT phase_name, COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END), MAX(finished_at)
            FROM automation_run_history
            WHERE started_at >= %s
            GROUP BY phase_name
            ORDER BY phase_name
            """,
            (last_12h,),
        )
        rows = cur.fetchall()
        if not rows:
            lines.append("  No runs in last 12h (table empty or no activity).")
        else:
            for phase_name, total, success_count, last_fin in rows:
                lines.append(f"  {phase_name}: {success_count}/{total} ok, last {last_fin}")
    except Exception as e:
        conn.rollback()
        lines.append(f"  Error: {e}")

    # --- Articles: last 12h vs previous 12h by domain (count, quality, content)
    lines.append("")
    lines.append("--- Articles: last 12h vs previous 12h (by domain) ---")
    for schema in ("politics", "finance", "science_tech"):
        try:
            # Created in last 12h
            cur.execute(
                f"""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE quality_score IS NOT NULL AND quality_score > 0),
                  ROUND(AVG(quality_score)::numeric, 3),
                  COUNT(*) FILTER (WHERE quality_tier IS NOT NULL),
                  COUNT(*) FILTER (WHERE content IS NOT NULL AND LENGTH(content) >= 500),
                  ROUND(AVG(LENGTH(content))::numeric, 0)
                FROM {schema}.articles
                WHERE created_at >= %s
                """,
                (last_12h,),
            )
            r = cur.fetchone()
            c_12, q_12_n, avg_q_12, tier_12, enriched_12, avg_len_12 = r or (0, 0, None, 0, 0, None)

            # Created in previous 12h (12–24h ago)
            cur.execute(
                f"""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE quality_score IS NOT NULL AND quality_score > 0),
                  ROUND(AVG(quality_score)::numeric, 3),
                  COUNT(*) FILTER (WHERE content IS NOT NULL AND LENGTH(content) >= 500),
                  ROUND(AVG(LENGTH(content))::numeric, 0)
                FROM {schema}.articles
                WHERE created_at >= %s AND created_at < %s
                """,
                (prev_12h, last_12h),
            )
            r2 = cur.fetchone()
            c_prev, q_prev_n, avg_q_prev, enriched_prev, avg_len_prev = r2 or (0, 0, None, 0, None)

            lines.append(f"  {schema}:")
            lines.append(f"    Last 12h:  created={c_12}, with_quality={q_12_n}, avg_quality={avg_q_12}, quality_tier_set={tier_12}, enriched(>=500)={enriched_12}, avg_content_len={avg_len_12}")
            lines.append(f"    Prev 12h:  created={c_prev}, with_quality={q_prev_n}, avg_quality={avg_q_prev}, enriched(>=500)={enriched_prev}, avg_content_len={avg_len_prev}")
        except Exception as e:
            conn.rollback()
            lines.append(f"  {schema}: error - {e}")

    # --- Storylines: updated or created in last 12h
    lines.append("")
    lines.append("--- Storylines: last 12h activity ---")
    for schema in ("politics", "finance", "science_tech"):
        try:
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE created_at >= %s),
                  COUNT(*) FILTER (WHERE updated_at >= %s),
                  COUNT(*) FILTER (WHERE updated_at >= %s AND editorial_document IS NOT NULL AND editorial_document != '{{}}'),
                  COUNT(*) FILTER (WHERE updated_at >= %s AND analysis_summary IS NOT NULL AND analysis_summary != '')
                FROM {schema}.storylines
                WHERE created_at >= %s OR updated_at >= %s
                """,
                (last_12h, last_12h, last_12h, last_12h, last_12h, last_12h),
            )
            r = cur.fetchone()
            new_s, updated_s, with_ed, with_analysis = r or (0, 0, 0, 0)
            lines.append(f"  {schema}: new={new_s}, updated={updated_s}, with editorial_document={with_ed}, with analysis_summary={with_analysis}")
        except Exception as e:
            conn.rollback()
            # editorial_document may not exist in all schemas
            try:
                cur.execute(
                    f"""
                    SELECT
                      COUNT(*) FILTER (WHERE created_at >= %s),
                      COUNT(*) FILTER (WHERE updated_at >= %s)
                    FROM {schema}.storylines
                    WHERE created_at >= %s OR updated_at >= %s
                    """,
                    (last_12h, last_12h, last_12h, last_12h),
                )
                r = cur.fetchone()
                lines.append(f"  {schema}: new={r[0]}, updated={r[1]} (no editorial_document column)")
            except Exception as e2:
                lines.append(f"  {schema}: error - {e2}")

    # --- Contexts: last 12h
    lines.append("")
    lines.append("--- Contexts (intelligence) last 12h ---")
    try:
        cur.execute(
            """
            SELECT source_type, COUNT(*)
            FROM intelligence.contexts
            WHERE created_at >= %s
            GROUP BY source_type
            """,
            (last_12h,),
        )
        for row in cur.fetchall():
            lines.append(f"  {row[0]}: {row[1]}")
        if not cur.rowcount:
            cur.execute("SELECT COUNT(*) FROM intelligence.contexts WHERE created_at >= %s", (last_12h,))
            if cur.fetchone()[0] == 0:
                lines.append("  (no new contexts in last 12h)")
    except Exception as e:
        conn.rollback()
        lines.append(f"  Error: {e}")

    # --- Topic assignments (last 12h)
    lines.append("")
    lines.append("--- Topic assignments (last 12h) ---")
    for schema in ("politics", "finance", "science_tech"):
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.article_topic_assignments WHERE created_at >= %s
                """,
                (last_12h,),
            )
            n = cur.fetchone()[0]
            lines.append(f"  {schema}: new topic assignments (last 12h): {n}")
        except Exception as e:
            conn.rollback()
            lines.append(f"  {schema}: error - {e}")

    # --- Summary verdict
    lines.append("")
    lines.append("--- Summary ---")
    try:
        cur.execute(
            """
            SELECT phase_name FROM automation_run_history
            WHERE started_at >= %s AND success = true
            """,
            (last_12h,),
        )
        phases_run = set(r[0] for r in cur.fetchall())
        collection_ran = "collection_cycle" in phases_run
        analysis_phases = {"context_sync", "entity_extraction", "topic_clustering", "storyline_discovery", "storyline_processing"}
        analysis_ran = bool(phases_run & analysis_phases)
        lines.append(f"  collection_cycle ran: {collection_ran}")
        lines.append(f"  analysis phases ran: {analysis_ran} (e.g. context_sync, entity_extraction, topic_clustering, storyline_*)")
    except Exception as e:
        lines.append(f"  (summary check failed: {e})")

    return lines


def main():
    conn = get_conn()
    if not conn:
        return 1
    try:
        for line in run_review(conn):
            print(line)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
