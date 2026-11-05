#!/usr/bin/env python3
"""Diagnostic: home_feed index coverage audit across all active domain schemas.

Checks every expected index from migrations 239 and 249 against live domains.
Reports row counts per domain, which indexes exist vs missing, and remediation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict

try:
    import psycopg2
except ImportError:
    sys.exit("ERROR: psycopg2 not installed.  pip install psycopg2-binary")

from psycopg2 import sql


EXPECTED_INDEXES = [
    {
        "name_pattern": "{sch}_sa_storyline_added_at",
        "table": "storyline_articles",
        "columns": "(storyline_id, added_at DESC)",
        "migration": "239",
        "criticality": "high",
        "query_use": "LATERAL join on sa.storyline_id",
    },
    {
        "name_pattern": "{sch}_storylines_unmerged_updated",
        "table": "storylines",
        "columns": "(updated_at DESC) WHERE merged_into_id IS NULL",
        "migration": "239",
        "criticality": "medium",
        "query_use": "ORDER BY + filter timeline in PART A subquery",
    },
    {
        "name_pattern": "{sch}_storylines_status_timeline",
        "table": "storylines",
        "columns": "(status, updated_at DESC) WHERE merged_into_id IS NULL",
        "migration": "249",
        "criticality": "high",
        "query_use": "skip ~30% unmerged rows by status before timeline scan",
    },
    {
        "name_pattern": "{sch}_storylines_last_refinement",
        "table": "storylines",
        "columns": "(last_refinement DESC)",
        "migration": "249",
        "criticality": "high",
        "query_use": "BitmapIndexScan on OR branch for last_refinement",
    },
    {
        "name_pattern": "{sch}_sa_last_article_added_at",
        "table": "storyline_articles",
        "columns": "(added_at DESC)",
        "migration": "249",
        "criticality": "high",
        "query_use": "BitmapIndexScan on sa.added_at in EXISTS clause",
    },
]


@dataclass
class DomainStats:
    domain_key: str = ""
    schema_name: str = ""
    is_active: bool = False
    storyline_count: int = 0
    articles_count: int = 0
    found_indexes: list[str] = field(default_factory=list)
    missing_indexes: list[dict] = field(default_factory=list)
    column_last_article_added_at: bool = None   # M249 column sanity check
    column_added_at: bool = None


DOMAINS_SQL = (
    "SELECT d.domain_key, d.schema_name, d.is_active "
    "FROM public.domains d WHERE d.is_active = true ORDER BY d.domain_key"
)

ROW_COUNTS_SQL = """\
SELECT c.relname,
    (SELECT count(*) FROM pg_class cl JOIN pg_namespace ns ON ns.oid=cl.relnamespace
     WHERE cl.relname='storylines' AND ns.nspname=c.relname) AS storyline_count,
    (SELECT count(*) FROM pg_class cl JOIN pg_namespace ns ON ns.oid=cl.relname
     WHERE cl.relname='storyline_articles' AND ns.nspname=c.relname) AS articles_count
FROM   pg_class c WHERE c.relnamespace IN (
    SELECT oid FROM pg_namespace WHERE nspname IN ({schemas})
) GROUP BY c.relname"""

EXISTING_INDEXES_SQL = (
    "SELECT indexname, tablename, indexdef "
    "FROM pg_indexes WHERE schemaname = %s ORDER BY tablename, indexname"
)


def diagnose(connection):
    cur = connection.cursor()
    cur.execute(DOMAINS_SQL)
    domains = cur.fetchall()
    if not domains:
        print("WARNING: No active domains found in public.domains.")
        return []

    schema_list = [d[1] for d in domains]
    colcur = connection.cursor()  # column check cursor (separate txn scope)
    all_stats = []

    for domain_key, schema_name, is_active in domains:
        # Row counts for this specific schema
        rcur = connection.cursor()
        tbl = sql.Identifier(schema_name)
        rcur.execute(
            sql.SQL("SELECT 'storylines', count(*) FROM {tbl}.storylines UNION ALL "
                    "SELECT 'storyline_articles', count(*) FROM {tbl}.storyline_articles")
            .format(tbl=tbl),
        )
        sc = ac = 0
        for rn, cn in rcur.fetchall():
            if rn == "storylines":
                sc = cn
            else:
                ac = cn
        rcur.close()

        stats = DomainStats(
            column_last_article_added_at=False,
            column_added_at=False,
            domain_key=domain_key,
            schema_name=schema_name,
            is_active=is_active,
            storyline_count=sc or 0,
            articles_count=ac or 0,
        )

        cur.execute(EXISTING_INDEXES_SQL, (schema_name,))
        for idx_name, _tbl, _idxdef in cur.fetchall():
            if f"{schema_name}_" in idx_name:
                stats.found_indexes.append(idx_name)

        for exp in EXPECTED_INDEXES:
            pattern = exp["name_pattern"].format(sch=schema_name)
            found = any(pattern in idx for idx in stats.found_indexes)
            if not found:
                stats.missing_indexes.append(exp)

        all_stats.append(stats)

    # Column-name sanity check on first domain (M249 depends on this)
    if all_stats and all_stats[0].schema_name:
        test_sch = all_stats[0].schema_name
        colcur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = 'storyline_articles' "
            "AND column_name IN ('last_article_added_at','added_at')",
            (test_sch,),
        )
        for row in colcur.fetchall():
            for s in all_stats:
                if row[0] == "last_article_added_at":
                    s.column_last_article_added_at = True
                if row[0] == "added_at":
                    s.column_added_at = True
    colcur.close()

    cur.close()
    return all_stats


def print_report(stats_list):
    total_missing_high = 0
    has_any_gap = False

    # Domain overview with scale
    print("=" * 78)
    print("HOME FEED INDEX COVERAGE AUDIT")
    print("=" * 78)
    print()
    hdr = f"{'Domain':<24} {'Schema':<30} {'Storylines':>12} {'Articles':>12}"
    print(hdr)
    print("-" * len(hdr))
    for s in stats_list:
        print(
            f"{s.domain_key:<24} {s.schema_name:<30} "
            f"{s.storyline_count:>12,} {s.articles_count:>12,}"
        )
    print()

    # Per-domain gaps
    for s in stats_list:
        if not s.missing_indexes:
            continue
        has_any_gap = True
        total_missing_high += sum(
            1 for m in s.missing_indexes if m.get("criticality") == "high"
        )
        print(f"--- {s.domain_key} ({s.schema_name}) --- ")
        for idx in s.missing_indexes:
            crit = "HIGH" if idx["criticality"] == "high" else "MED "
            full_name = f"idx_{idx['name_pattern'].replace('{sch}', s.schema_name)}"
            print(f"  MISSING [{crit}] {full_name}")
            print(f"           Table: {idx['table']}")
            print(f"           On:    {idx['columns']}")
            print(f"           Use:   {idx['query_use']}")
        print()

    if not has_any_gap:
        print("All expected indexes are present. No remediation needed.")
        return

    # Remediation section
    missing_high_domains = [
        s for s in stats_list
        if any(m["criticality"] == "high" for m in s.missing_indexes)
    ]

    print("=" * 78)
    print("REMEDIATION")
    print("=" * 78)
    print()

    if missing_high_domains:
        schemas = ", ".join(f"'{s.schema_name}'" for s in missing_high_domains)
        print("Apply migration 249 to affected domains:")
        print(f"\n  psql -h <host> -p <port> -U postgres -d news_intel <<'EOSQL'\n")
        print(f"  SELECT d.domain_key, d.schema_name FROM public.domains d")
        print(f"    WHERE d.is_active = true AND d.schema_name IN ({schemas});\n")
        print("EOSQL\n")
        print("  Then apply the migration SQL:")
        print("    cat api/database/migrations/249_home_feed_storyline_indexes.sql | "
              "psql -h <host> -p <port> -U postgres -d news_intel")
        print("\n  Or use the helper script (hardcoded schema list):")
        print("    python3 api/database/migrations/_apply_homefeed_indexes.py")

    if total_missing_high > 0:
        print(f"\nHIGH priority gaps: {total_missing_high} across "
              f"{len(missing_high_domains)} domain(s)")

    print("\nBEFORE running migration 249, verify the column name:")
    for s in stats_list[:1]:
        if s.schema_name:
            print(f"  \\d {s.schema_name}.storyline_articles")
    # Column-mismatch detection
    sample = next((s for s in stats_list if s.column_added_at is not None), None)
    if sample and hasattr(sample, 'column_last_article_added_at'):
        has_laaa = getattr(sample, 'column_last_article_added_at', False)
        has_aa = getattr(sample, 'column_added_at', False)
        if has_laaa and has_aa:
            print("\n  Column 'last_article_added_at' EXISTS alongside 'added_at' — OK to apply as-is.")
        elif has_aa and not has_laaa:
            print("\n  WARNING: 'last_article_added_at' DOES NOT EXIST! Only 'added_at' exists.")
            print("  Migration 249 line 50 and _apply_homefeed_indexes.py line 34 WILL FAIL.")
            print("  Either:")
            print("    A) Add column last_article_added_at = added_at first (ALTER TABLE ... ADD COLUMN), or")
            print("    B) Edit both files: replace 'last_article_added_at' with 'added_at', then apply.")
        elif not has_laaa and not has_aa:
            print("\n  WARNING: Neither 'last_article_added_at' nor 'added_at' found on storyline_articles!")
            print("  Check the actual column name in your schema (may be different).")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose home_feed index coverage across active domains."
    )
    parser.add_argument("--host", default=None, help="Postgres host")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--dbname", default="news_intel")
    parser.add_argument("--passfile", default=None)
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    conn_kwargs = dict(
        host=args.host or os.environ.get("PG_HOST", "localhost"),
        port=args.port, user=args.user, dbname=args.dbname, connect_timeout=10,
    )
    if args.passfile:
        conn_kwargs["password"] = ""

    print(f"Connecting to {conn_kwargs['host']}:{conn_kwargs['port']} as "
          f"{conn_kwargs['user']}/{conn_kwargs['dbname']} ...")

    try:
        conn = psycopg2.connect(**conn_kwargs)
    except psycopg2.OperationalError as e:
        sys.exit(f"FATAL: Cannot connect to Postgres:\n  {e}")

    stats_list = diagnose(conn)
    conn.close()

    if args.json:
        print(json.dumps([asdict(s) for s in stats_list], indent=2, default=str))
    else:
        print_report(stats_list)


if __name__ == "__main__":
    main()
