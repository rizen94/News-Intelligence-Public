#!/usr/bin/env python3
"""
One-time bulk cleanup: remove garbage entity names from entity_canonical
and article_entities across all domain schemas.

Run AFTER taking a database snapshot.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from shared.database.connection import get_db_connection

GARBAGE_NAMES_SQL = (
    "''", "'None'", "'none'", "'None found'", "'None specified'",
    "'N/A'", "'n/a'", "'NA'", "'Unknown'", "'unknown'",
    "'Not specified'", "'Not applicable'", "'Not mentioned'",
    "'Not available'", "'No one'", "'No entity'",
    "'Unspecified'", "'Unnamed'", "'Anonymous'", "'Various'",
    "'Undisclosed'", "'null'", "'empty'", "'The article'",
    "'This article'", "'The author'", "'The reporter'",
    "'Staff reporter'", "'Staff writer'",
    "'None provided'", "'None found in headline'",
    "'None found in body'", "'None mentioned'",
    "'None identified'", "'None listed'", "'None given'",
    "'None available'", "'None applicable'",
    "'Not found'", "'Not identified'", "'Not listed'",
    "'Not given'", "'Not provided'",
)

GARBAGE_IN_LIST = ", ".join(GARBAGE_NAMES_SQL)

# Targeted regex: catches "None found in ...", "Not yet ...", etc.
# without matching real entities like "No Kings", "No 10"
GARBAGE_REGEX = r"'^(None (found|provided|specified|mentioned|identified|listed|given|available|applicable)|Not (found|provided|specified|mentioned|identified|listed|given|available|applicable)|None$)'"


def get_domain_schemas(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT table_schema
            FROM information_schema.tables
            WHERE table_name = 'entity_canonical'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema
        """)
        return [r[0] for r in cur.fetchall()]


def cleanup_schema(conn, schema, dry_run=True):
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{'='*60}")
    print(f"{prefix}Schema: {schema}")
    print(f"{'='*60}")

    with conn.cursor() as cur:
        cur.execute(f"SET search_path TO {schema}, public")

        # 1. Count garbage in entity_canonical
        cur.execute(f"""
            SELECT canonical_name, entity_type, COUNT(*) as refs
            FROM {schema}.entity_canonical
            WHERE LOWER(TRIM(canonical_name)) IN (
                {', '.join(f"LOWER({g})" for g in GARBAGE_NAMES_SQL)}
            )
            OR TRIM(canonical_name) = ''
            OR canonical_name ~* {GARBAGE_REGEX}
            GROUP BY canonical_name, entity_type
            ORDER BY refs DESC
        """)
        garbage_canonicals = cur.fetchall()
        if garbage_canonicals:
            print(f"\n  Garbage canonical entities found:")
            for name, etype, refs in garbage_canonicals:
                print(f"    {name!r:40s}  type={etype:20s}")
        else:
            print(f"  No garbage canonical entities found.")

        # 2. Get IDs of garbage canonicals
        cur.execute(f"""
            SELECT id, canonical_name FROM {schema}.entity_canonical
            WHERE LOWER(TRIM(canonical_name)) IN (
                {', '.join(f"LOWER({g})" for g in GARBAGE_NAMES_SQL)}
            )
            OR TRIM(canonical_name) = ''
            OR canonical_name ~* {GARBAGE_REGEX}
        """)
        garbage_ids = [(r[0], r[1]) for r in cur.fetchall()]

        if not garbage_ids:
            print(f"  Nothing to clean.")
            return 0

        id_list = [g[0] for g in garbage_ids]
        print(f"\n  {len(id_list)} garbage canonical entities to remove")

        # 3. Count article_entities that reference them
        cur.execute(f"""
            SELECT COUNT(*) FROM {schema}.article_entities
            WHERE canonical_entity_id = ANY(%s)
        """, (id_list,))
        ae_count = cur.fetchone()[0]
        print(f"  {ae_count} article_entities rows reference garbage canonicals")

        # 4. Count article_entities with garbage names (no canonical)
        cur.execute(f"""
            SELECT COUNT(*) FROM {schema}.article_entities
            WHERE LOWER(TRIM(entity_name)) IN (
                {', '.join(f"LOWER({g})" for g in GARBAGE_NAMES_SQL)}
            )
            OR TRIM(entity_name) = ''
            OR entity_name ~* {GARBAGE_REGEX}
        """)
        ae_garbage_direct = cur.fetchone()[0]
        print(f"  {ae_garbage_direct} article_entities rows have garbage entity_name directly")

        if dry_run:
            print(f"\n  {prefix}Would delete {len(id_list)} canonical + {ae_count + ae_garbage_direct} article_entity rows")
            return len(id_list)

        # 5. Delete article_entities referencing garbage canonicals
        cur.execute(f"""
            DELETE FROM {schema}.article_entities
            WHERE canonical_entity_id = ANY(%s)
        """, (id_list,))
        print(f"  Deleted {cur.rowcount} article_entities (by canonical_id)")

        # 6. Delete article_entities with garbage names directly
        cur.execute(f"""
            DELETE FROM {schema}.article_entities
            WHERE LOWER(TRIM(entity_name)) IN (
                {', '.join(f"LOWER({g})" for g in GARBAGE_NAMES_SQL)}
            )
            OR TRIM(entity_name) = ''
            OR entity_name ~* {GARBAGE_REGEX}
        """)
        print(f"  Deleted {cur.rowcount} article_entities (by garbage name)")

        # 7. Delete garbage canonical entities
        cur.execute(f"""
            DELETE FROM {schema}.entity_canonical
            WHERE id = ANY(%s)
        """, (id_list,))
        print(f"  Deleted {cur.rowcount} entity_canonical rows")

        return len(id_list)


def main():
    dry_run = "--execute" not in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE — pass --execute to actually delete")
        print("=" * 60)

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)

    try:
        schemas = get_domain_schemas(conn)
        print(f"Found {len(schemas)} domain schemas: {schemas}")

        total = 0
        for schema in schemas:
            total += cleanup_schema(conn, schema, dry_run=dry_run)

        if not dry_run:
            conn.commit()
            print(f"\n{'='*60}")
            print(f"COMMITTED — {total} garbage canonical entities removed")
            print(f"{'='*60}")
        else:
            conn.rollback()
            print(f"\n{'='*60}")
            print(f"DRY RUN COMPLETE — {total} garbage entities would be removed")
            print(f"Run with --execute to apply changes")
            print(f"{'='*60}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
