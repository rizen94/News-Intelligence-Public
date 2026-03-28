#!/usr/bin/env python3
"""
Copy row data from one domain Postgres schema to another (same table set), preserving primary keys.

Use case: bootstrap ``politics_2`` from ``politics`` while legacy ``politics`` keeps running.
Reads are ``SELECT`` on the source (normal MVCC; no writes to source). All writes go to the target
schema only.

Requirements:
  - Target tables must exist and largely match the source (migration 201 + parity with ``politics``).
  - Known mismatch: ``articles.extracted_entities`` may be ``text[]`` on source and ``text`` on
    target (clone from older ``create_domain_table``) — this script casts ``::text``.

Safety:
  - Default: refuse if the target already has rows in any shared table (use ``--replace`` to
    ``TRUNCATE ... CASCADE`` target tables first).
  - ``storylines`` self-FKs are satisfied by repeated INSERT passes (no ``session_replication_role``;
    that setting requires superuser on many deployments).

After copy, runs ``sync_domain_entity_profiles`` for ``--target-domain-key`` so claim resolution
can match on ``politics-2`` (or your chosen key).

Examples::

  PYTHONPATH=api uv run python api/scripts/copy_domain_silo_table_data.py \\
    --source-schema politics --target-schema politics_2 --target-domain-key politics-2 --dry-run

  PYTHONPATH=api uv run python api/scripts/copy_domain_silo_table_data.py \\
    --source-schema politics --target-schema politics_2 --target-domain-key politics-2

  # Re-copy from scratch (wipes target silo tables only):
  PYTHONPATH=api uv run python api/scripts/copy_domain_silo_table_data.py \\
    --source-schema politics --target-schema politics_2 --target-domain-key politics-2 --replace

RSS: if the same ``feed_url`` exists in both schemas and neither domain is excluded by
``RSS_INGEST_EXCLUDE_DOMAIN_KEYS``, collection may write duplicates — exclude one domain or
deactivate overlapping feeds in one silo.

Tables that exist only on the source are **not** copied until the target has matching DDL.
For **finance → finance_2**, run migration **206** so ``topic_extraction_queue``,
``research_topics``, ``market_patterns``, ``corporate_announcements``, and
``financial_indicators`` exist on ``finance_2``, then re-run this script for those tables.
Template silos (201) stay minimal; per-silo extensions use follow-on migrations (see
``docs/DOMAIN_EXTENSION_TEMPLATE.md`` § Per-silo DDL extensions).
"""

from __future__ import annotations

import argparse
import os
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(API_ROOT)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(API_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(PROJECT_ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(PROJECT_ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass


def _tables_in_schema(cur, schema: str) -> list[str]:
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (schema,),
    )
    return [r[0] for r in cur.fetchall()]


def _column_meta(cur, schema: str, table: str) -> list[tuple[str, str, str]]:
    """Return (column_name, data_type, udt_name) in ordinal order."""
    cur.execute(
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )
    return [(r[0], r[1], r[2]) for r in cur.fetchall()]


def _shared_tables(source: str, target: str, cur) -> list[str]:
    a = set(_tables_in_schema(cur, source))
    b = set(_tables_in_schema(cur, target))
    # Stable order: dependency-friendly (replica mode relaxes strict order)
    preferred = [
        "rss_feeds",
        "topics",
        "storylines",
        "articles",
        "entity_canonical",
        "topic_clusters",
        "article_topic_assignments",
        "storyline_articles",
        "article_entities",
        "story_entity_index",
        # finance (and finance_2 post-206): after articles for FKs / queue
        "research_topics",
        "market_patterns",
        "financial_indicators",
        "corporate_announcements",
        "topic_extraction_queue",
    ]
    shared = a & b
    out = [t for t in preferred if t in shared]
    # Any other shared tables (future parity), append alphabetically
    rest = sorted(shared - set(out))
    return out + rest


def _target_nonempty(cur, target: str, tables: list[str]) -> list[tuple[str, int]]:
    counts: list[tuple[str, int]] = []
    for t in tables:
        cur.execute(f"SELECT COUNT(*)::bigint FROM {target}.{t}")
        n = int(cur.fetchone()[0])
        if n:
            counts.append((t, n))
    return counts


def _build_insert_select(source: str, target: str, table: str, cur) -> str:
    src_cols = _column_meta(cur, source, table)
    tgt_cols = _column_meta(cur, target, table)
    tgt_names = [c[0] for c in tgt_cols]
    src_by_name = {c[0]: c for c in src_cols}

    select_parts: list[str] = []
    for name in tgt_names:
        if name not in src_by_name:
            raise RuntimeError(f"{target}.{table}: column {name!r} missing on source {source}")
        sdt, sudt = src_by_name[name][1], src_by_name[name][2]
        tdt, tudt = next(c[1] for c in tgt_cols if c[0] == name), next(c[2] for c in tgt_cols if c[0] == name)
        if name == "extracted_entities" and table == "articles" and sudt != tudt:
            select_parts.append(f"src.{name}::text AS {name}")
        elif sdt != tdt or sudt != tudt:
            raise RuntimeError(
                f"{table}.{name}: type mismatch source {sdt}/{sudt} vs target {tdt}/{tudt}"
            )
        else:
            select_parts.append(f"src.{name}")

    cols_sql = ", ".join(f'"{c}"' for c in tgt_names)
    sel_sql = ", ".join(select_parts)
    return f'INSERT INTO {target}.{table} ({cols_sql}) SELECT {sel_sql} FROM {source}.{table} AS src'


def _copy_storylines_layered(source: str, target: str, cur) -> int:
    """Copy storylines in waves so parent/merge FK targets exist (same ids as source)."""
    total = 0
    max_passes = 500
    for _ in range(max_passes):
        base = _build_insert_select(source, target, "storylines", cur)
        layered = (
            base
            + " WHERE NOT EXISTS (SELECT 1 FROM "
            + target
            + ".storylines x WHERE x.id = src.id)"
            + " AND (src.parent_storyline_id IS NULL OR EXISTS (SELECT 1 FROM "
            + target
            + ".storylines p WHERE p.id = src.parent_storyline_id))"
            + " AND (src.merged_into_id IS NULL OR EXISTS (SELECT 1 FROM "
            + target
            + ".storylines m WHERE m.id = src.merged_into_id))"
        )
        cur.execute(layered)
        n = cur.rowcount
        total += n
        if n == 0:
            break
    else:
        raise RuntimeError("storylines copy exceeded max passes — possible FK cycle")
    cur.execute(f"SELECT COUNT(*)::bigint FROM {source}.storylines")
    src_n = int(cur.fetchone()[0])
    cur.execute(f"SELECT COUNT(*)::bigint FROM {target}.storylines")
    tgt_n = int(cur.fetchone()[0])
    if tgt_n != src_n:
        raise RuntimeError(f"storylines row count mismatch: source={src_n} target={tgt_n}")
    return total


def _truncate_target(cur, target: str, tables: list[str]) -> None:
    # Single TRUNCATE lists all tables so FKs among them are satisfied
    qn = ", ".join(f"{target}.{t}" for t in tables)
    cur.execute(f"TRUNCATE TABLE {qn} RESTART IDENTITY CASCADE")


def _sync_sequences(cur, target: str, tables: list[str]) -> None:
    for t in tables:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
              AND column_default LIKE 'nextval%%'
            """,
            (target, t),
        )
        for (col,) in cur.fetchall():
            cur.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{target}.{t}', %s),
                    COALESCE((SELECT MAX("{col}") FROM {target}.{t}), 1),
                    true
                )
                """,
                (col,),
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-schema", required=True, help="e.g. politics")
    p.add_argument("--target-schema", required=True, help="e.g. politics_2")
    p.add_argument(
        "--target-domain-key",
        required=True,
        help="Registry domain_key for entity_profiles sync, e.g. politics-2",
    )
    p.add_argument("--dry-run", action="store_true", help="Print counts and SQL preview only")
    p.add_argument(
        "--replace",
        action="store_true",
        help="TRUNCATE target shared tables (CASCADE) before copy",
    )
    p.add_argument(
        "--skip-profile-sync",
        action="store_true",
        help="Do not run sync_domain_entity_profiles after copy",
    )
    args = p.parse_args()

    src = args.source_schema.strip()
    tgt = args.target_schema.strip()
    if not src.isidentifier() or not tgt.isidentifier():
        print("ERROR: schema names must be plain identifiers")
        return 1

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            shared = _shared_tables(src, tgt, cur)
            if not shared:
                print("ERROR: no shared tables between schemas")
                return 1
            print(f"Shared tables ({len(shared)}): {', '.join(shared)}")

            nonempty = _target_nonempty(cur, tgt, shared)
            if nonempty and not args.replace:
                print("ERROR: target schema has data; use --replace to truncate first:")
                for t, n in nonempty:
                    print(f"  {t}: {n}")
                return 1

            for t in shared:
                cur.execute(f"SELECT COUNT(*)::bigint FROM {src}.{t}")
                n = cur.fetchone()[0]
                print(f"  source {src}.{t}: {n} rows")

            if args.dry_run:
                sql = _build_insert_select(src, tgt, shared[0], cur)
                print("\nDry-run — example first table SQL:\n", sql[:500], "...\n")
                conn.rollback()
                return 0

            if args.replace:
                print("TRUNCATE target tables …")
                _truncate_target(cur, tgt, shared)

            cur.execute("SET LOCAL statement_timeout = 0")

            for t in shared:
                if t == "storylines":
                    n = _copy_storylines_layered(src, tgt, cur)
                    print(f"  copied storylines: {n} rows (layered)")
                else:
                    sql = _build_insert_select(src, tgt, t, cur)
                    cur.execute(sql)
                    print(f"  copied {t}: {cur.rowcount} rows")

            _sync_sequences(cur, tgt, shared)
            conn.commit()
            print("Committed copy + sequence sync.")

        if not args.skip_profile_sync:
            from services.entity_profile_sync_service import sync_domain_entity_profiles

            n = sync_domain_entity_profiles(args.target_domain_key)
            print(f"sync_domain_entity_profiles({args.target_domain_key!r}): {n} new profile mappings")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
