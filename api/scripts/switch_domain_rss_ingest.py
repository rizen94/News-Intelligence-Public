#!/usr/bin/env python3
"""
Flip RSS ingest from a legacy silo to a template silo by updating ``rss_feeds.is_active`` only.

- Deactivates all rows in the source domain's ``rss_feeds`` (no deletes — safe to reverse).
- Activates all rows in the target domain's ``rss_feeds``.

``collect_rss_feeds`` only loads ``WHERE is_active = true``, so new articles stop landing in the
legacy schema and go to the target (given the same feed URLs in the target table).

Pair with ``RSS_INGEST_EXCLUDE_DOMAIN_KEYS`` (e.g. ``politics``) so any code path that still
iterates domains cannot accidentally double-collect if a feed URL appears in two schemas later.

  PYTHONPATH=api uv run python api/scripts/switch_domain_rss_ingest.py \\
    --deactivate politics --activate politics-2

  PYTHONPATH=api uv run python api/scripts/switch_domain_rss_ingest.py \\
    --deactivate politics --activate politics-2 --dry-run
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--deactivate", required=True, help="domain_key to turn off (e.g. politics)")
    p.add_argument("--activate", required=True, help="domain_key to turn on (e.g. politics-2)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    from shared.database.connection import get_db_connection
    from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

    for k in (args.deactivate, args.activate):
        if not is_valid_domain_key(k):
            print(f"ERROR: unknown domain_key {k!r}")
            return 1

    src_sch = resolve_domain_schema(args.deactivate)
    tgt_sch = resolve_domain_schema(args.activate)

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM {src_sch}.rss_feeds"
            )
            src_on, src_all = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*) FILTER (WHERE is_active), COUNT(*) FROM {tgt_sch}.rss_feeds"
            )
            tgt_on, tgt_all = cur.fetchone()
            print(f"Before: {args.deactivate} ({src_sch}) active={src_on} total={src_all}")
            print(f"Before: {args.activate} ({tgt_sch}) active={tgt_on} total={tgt_all}")

            if args.dry_run:
                print("Dry-run — no updates")
                conn.rollback()
                return 0

            cur.execute(
                f"UPDATE {src_sch}.rss_feeds SET is_active = false, updated_at = NOW() "
                f"WHERE is_active = true"
            )
            off = cur.rowcount
            cur.execute(
                f"UPDATE {tgt_sch}.rss_feeds SET is_active = true, updated_at = NOW() "
                f"WHERE is_active = false"
            )
            on = cur.rowcount
            conn.commit()
            print(f"Updated: deactivated {off} feed(s) on {src_sch}, activated {on} feed(s) on {tgt_sch}")

        print(
            "\nRecommended .env (restart API/workers after edit):\n"
            f"  RSS_INGEST_EXCLUDE_DOMAIN_KEYS={args.deactivate}\n"
            f"  POLITICS_PG_CONTENT_DOMAIN_KEY={args.activate}\n"
        )
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
