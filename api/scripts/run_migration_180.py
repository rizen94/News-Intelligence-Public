#!/usr/bin/env python3
"""Run migration 180: legal domain silo (schema legal + table parity).

From project root:
  PYTHONPATH=api uv run python api/scripts/run_migration_180.py

After SQL (default): seeds ``data_sources.rss.seed_feed_urls`` from ``api/config/domains/legal.yaml``
into ``legal.rss_feeds`` and sets ``public.domains.is_active = TRUE`` for ``legal`` (same as
``provision_domain.py`` defaults). YAML ``is_active`` is unchanged — set it true when you want
registry/RSS to include this silo.

  --sql-only           Only run the SQL file (no RSS seed, no domains update).
  --skip-rss-seed      Run SQL + activate ``public.domains`` only.
  --no-activate-in-db  Run SQL + RSS seed; do not UPDATE ``public.domains``.
  --domain-config PATH Override onboarding YAML (default: api/config/domains/legal.yaml).
"""

import argparse
import os
import sys
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

_API_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_LEGAL_YAML = _API_DIR / "config" / "domains" / "legal.yaml"


def main():
    parser = argparse.ArgumentParser(description="Run migration 180 (legal domain silo)")
    parser.add_argument(
        "--sql-only",
        action="store_true",
        help="Only apply 180_legal_domain_silo.sql (no RSS seed, no public.domains update)",
    )
    parser.add_argument(
        "--skip-rss-seed",
        action="store_true",
        help="After SQL: skip RSS seed from YAML; still activates public.domains unless --no-activate-in-db",
    )
    parser.add_argument(
        "--no-activate-in-db",
        action="store_true",
        help="After SQL: do not UPDATE public.domains SET is_active = TRUE",
    )
    parser.add_argument(
        "--domain-config",
        type=Path,
        default=_DEFAULT_LEGAL_YAML,
        help=f"Onboarding YAML for post-SQL steps (default: {_DEFAULT_LEGAL_YAML})",
    )
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    from shared.services.domain_silo_post_migration import (
        apply_domain_silo_post_sql,
        load_domain_onboarding_yaml,
    )

    try:
        from shared.migration_sql_paths import resolve_migration_sql_file

        path = resolve_migration_sql_file("180_legal_domain_silo.sql")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)

    try:
        with open(path) as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print("✅ 180_legal_domain_silo.sql applied successfully")

        if args.sql_only:
            return

        cfg_path = args.domain_config.resolve()
        if not cfg_path.is_file():
            print(
                f"⚠️  Post-SQL steps skipped: onboarding YAML not found: {cfg_path}",
                file=sys.stderr,
            )
            return

        cfg = load_domain_onboarding_yaml(cfg_path)
        if str(cfg.get("domain_key")) != "legal" or str(cfg.get("schema_name")) != "legal":
            print(
                "⚠️  Post-SQL steps skipped: YAML domain_key/schema_name must be legal/legal "
                f"(got {cfg.get('domain_key')!r} / {cfg.get('schema_name')!r})",
                file=sys.stderr,
            )
            return

        status = apply_domain_silo_post_sql(
            conn,
            cfg,
            skip_rss_seed=args.skip_rss_seed,
            no_activate_in_db=args.no_activate_in_db,
        )
        print(
            "✅ Post-SQL: "
            f"rss_seeded={status.get('rss_seeded')} rss_skipped={status.get('rss_skipped_duplicates')} "
            f"domains_updated={status.get('domains_rows_updated')}"
        )
        print(
            "   Set is_active: true in the onboarding YAML when ready for registry/RSS url_schema_pairs()."
        )
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
