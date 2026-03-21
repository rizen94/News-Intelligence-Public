#!/usr/bin/env python3
"""
Read-only database diagnostic: legacy data and schema compatibility.
Reports column presence, NULL counts, orphan rows, and pruning candidates.
Run from project root: .venv/bin/python api/scripts/diagnose_db_legacy_data.py
"""

import os
import sys
import re
from pathlib import Path

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


def run(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def run_one(conn, sql, params=None):
    rows = run(conn, sql, params)
    return rows[0] if rows else None


def set_search_path(conn, path):
    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {path}")


def scan_runtime_sql_alignment():
    """
    Static SQL alignment scan for runtime code.
    Flags unqualified table references likely to hit public schema by accident.
    """
    api_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    runtime_roots = (
        api_root / "services",
        api_root / "domains",
        api_root / "shared",
        api_root / "modules",
    )
    excluded_markers = ("/tests/", "/scripts/", "/archive/", "/compatibility/")
    sql_pattern = re.compile(
        r"\b(FROM|JOIN|UPDATE|INTO|DELETE\s+FROM)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        re.IGNORECASE,
    )
    risky_tables = {"articles", "storylines", "rss_feeds", "storyline_articles"}
    findings = []

    for root in runtime_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            path_str = str(py_file).replace("\\", "/")
            if any(marker in path_str for marker in excluded_markers):
                continue
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for idx, line in enumerate(text.splitlines(), start=1):
                if "." in line:
                    # Skip obviously schema-qualified lines (e.g. politics.articles).
                    continue
                for match in sql_pattern.finditer(line):
                    table = match.group(2).lower()
                    if table in risky_tables:
                        rel = str(py_file.relative_to(api_root))
                        findings.append((rel, idx, table, line.strip()))

    return findings


def main():
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)

    try:
        print("=" * 60)
        print("News Intelligence — legacy data & schema diagnostic (read-only)")
        print("=" * 60)

        # --- 1. Column presence for key tables (one domain as sample) ---
        print("\n--- 1. Column presence (politics.articles sample) ---")
        cols_sql = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'politics' AND table_name = 'articles'
            ORDER BY ordinal_position
        """
        cols = run(conn, cols_sql)
        if not cols:
            print("  No politics.articles table or empty schema.")
        else:
            for r in cols:
                print(f"  {r[0]}: {r[1]} (nullable={r[2]})")
            # Check for naming that app code might expect
            col_names = [r[0] for r in cols]
            for expected in ("rss_feed_id", "feed_id", "category", "source_domain", "source_name", "entities", "topics", "extracted_entities"):
                status = "present" if expected in col_names else "MISSING"
                print(f"  >> {expected}: {status}")

        # --- 2. NULL counts for important columns (all domains) ---
        print("\n--- 2. NULL / empty counts (articles, key columns) ---")
        for schema in ("politics", "finance", "science_tech"):
            try:
                set_search_path(conn, f"{schema}, public")
                # Count rows and nulls for entities/topics/created_at
                q = f"""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(created_at) AS has_created_at,
                        COUNT(entities) AS has_entities,
                        COUNT(topics) AS has_topics,
                        COUNT(CASE WHEN entities IS NULL OR entities::text = 'null' THEN 1 END) AS null_entities,
                        COUNT(CASE WHEN topics IS NULL OR topics::text = 'null' THEN 1 END) AS null_topics
                    FROM {schema}.articles
                """
                row = run_one(conn, q)
                if row:
                    print(f"  {schema}: total={row[0]}, created_at present={row[1]}, entities present={row[2]}, topics present={row[3]}, null entities={row[4]}, null topics={row[5]}")
            except Exception as e:
                print(f"  {schema}: error - {e}")

        # --- 3. Orphan checks ---
        print("\n--- 3. Orphan rows (join tables pointing to missing parents) ---")
        for schema in ("politics", "finance", "science_tech"):
            try:
                set_search_path(conn, f"{schema}, public")
                # storyline_articles.article_id not in articles
                q1 = f"""
                    SELECT COUNT(*) FROM {schema}.storyline_articles sa
                    WHERE NOT EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = sa.article_id)
                """
                o1 = run_one(conn, q1)
                # storyline_articles.storyline_id not in storylines
                q2 = f"""
                    SELECT COUNT(*) FROM {schema}.storyline_articles sa
                    WHERE NOT EXISTS (SELECT 1 FROM {schema}.storylines s WHERE s.id = sa.storyline_id)
                """
                o2 = run_one(conn, q2)
                if (o1 and o1[0] and int(o1[0]) > 0) or (o2 and o2[0] and int(o2[0]) > 0):
                    print(f"  {schema}: orphan storyline_articles (bad article_id)={o1[0] if o1 else 0}, (bad storyline_id)={o2[0] if o2 else 0}")
                else:
                    print(f"  {schema}: no storyline_articles orphans")
            except Exception as e:
                print(f"  {schema}: error - {e}")

        # --- 4. Pipeline / logging tables: row counts and pruning candidates ---
        print("\n--- 4. Pipeline & log tables (pruning candidates) ---")
        set_search_path(conn, "public")
        for table, age_col in (
            ("pipeline_traces", "start_time"),
            ("pipeline_checkpoints", "timestamp"),
            ("pipeline_error_log", "created_at"),
        ):
            try:
                total = run_one(conn, f"SELECT COUNT(*) FROM {table}")
                old = run_one(conn, f"SELECT COUNT(*) FROM {table} WHERE {age_col} < NOW() - INTERVAL '90 days'")
                if total and total[0] is not None:
                    print(f"  {table}: total={total[0]}, older than 90 days={old[0] if old else '?'}")
            except Exception as e:
                print(f"  {table}: error - {e}")

        # --- 5. Public vs domain: any rows left in public.articles / public.storylines? ---
        print("\n--- 5. Public schema leftovers (migration 125 moved data to domains) ---")
        set_search_path(conn, "public")
        try:
            for tbl in ("articles", "storylines", "rss_feeds"):
                exists = run_one(conn, "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s", (tbl,))
                if exists:
                    c = run_one(conn, f"SELECT COUNT(*) FROM public.{tbl}")
                    print(f"  public.{tbl}: {c[0] if c else 0} rows")
                else:
                    print(f"  public.{tbl}: table not present")
        except Exception as e:
            print(f"  public check: {e}")

        # --- 6. Runtime SQL static alignment scan ---
        print("\n--- 6. Runtime SQL alignment scan (static code check) ---")
        findings = scan_runtime_sql_alignment()
        if not findings:
            print("  No risky unqualified runtime SQL table references found.")
        else:
            table_counts = {}
            file_counts = {}
            for rel, _, table, _ in findings:
                table_counts[table] = table_counts.get(table, 0) + 1
                file_counts[rel] = file_counts.get(rel, 0) + 1

            print(f"  Findings: {len(findings)} potential unqualified table references")
            print("  By table:")
            for table, count in sorted(table_counts.items(), key=lambda x: (-x[1], x[0])):
                print(f"    - {table}: {count}")

            print("  Top files:")
            for rel, count in sorted(file_counts.items(), key=lambda x: (-x[1], x[0]))[:15]:
                print(f"    - {rel}: {count}")

            print("  Sample findings:")
            for rel, line_no, table, line in findings[:20]:
                print(f"    - {rel}:{line_no} [{table}] {line}")

        print("\n" + "=" * 60)
        print("Done. No data was modified. See docs/DATA_CLEANUP_AND_COMPATIBILITY.md for cleanup options.")
        print("=" * 60)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
