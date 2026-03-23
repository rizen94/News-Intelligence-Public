#!/usr/bin/env python3
"""
Align optional domain silos across YAML registry and ``public.domains``.

Use after migrations + ``provision_domain`` so automation (``get_all_domains()``) and RSS
(``url_schema_pairs()``) see the same silos on **every host** (main GPU, dev PC, Widow worker)
that shares this repo and DB.

  PYTHONPATH=api uv run python api/scripts/ensure_domain_silo_alignment.py
  PYTHONPATH=api uv run python api/scripts/ensure_domain_silo_alignment.py --dry-run

By default (unless ``--dry-run`` or ``--no-activate-db``): ``UPDATE public.domains SET is_active = TRUE``
for each YAML-active domain_key that has a ``public.domains`` row. Safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root / api on path (same pattern as provision_domain.py)
_API = Path(__file__).resolve().parent.parent
_ROOT = _API.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync public.domains.is_active with YAML-active silos; report RSS feed coverage."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions only; do not UPDATE public.domains",
    )
    parser.add_argument(
        "--no-activate-db",
        action="store_true",
        help="Skip UPDATE public.domains (report only)",
    )
    args = parser.parse_args()

    env_file = _ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass

    from shared.database.connection import get_db_connection
    from shared.domain_registry import get_domain_entries
    from shared.services.domain_silo_post_migration import activate_domain_row

    conn = get_db_connection()
    if not conn:
        raise SystemExit("No database connection")

    activate_db = not args.no_activate_db and not args.dry_run

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            existing = {r[0] for r in cur.fetchall()}

        print("Domain silo alignment (registry YAML + Postgres)")
        print("-" * 60)
        any_warn = False
        for e in get_domain_entries():
            if not e.get("is_active", True):
                continue
            dk = e["domain_key"]
            schema = str(e["schema_name"])
            if schema not in existing:
                print(f"  [skip] {dk}: schema {schema!r} missing — apply migration first")
                any_warn = True
                continue

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_active FROM public.domains WHERE domain_key = %s",
                    (dk,),
                )
                row = cur.fetchone()
                cur.execute(
                    f"SELECT COUNT(*) FROM {schema}.rss_feeds WHERE is_active = true"
                )
                n_feeds = cur.fetchone()[0]

            issues: list[str] = []
            if row is None:
                issues.append("no public.domains row — run migration / provision_domain")
                any_warn = True
            elif row[0] is False:
                issues.append(
                    "public.domains.is_active is FALSE (catalog drift; pipeline uses YAML + schema)"
                )
                any_warn = True
            if n_feeds == 0:
                issues.append(f"zero active rows in {schema}.rss_feeds")
                any_warn = True

            tag = "ok" if not issues else "warn"
            print(f"  [{tag}] {dk}: schema={schema}, active_feeds={n_feeds}")
            for msg in issues:
                print(f"         — {msg}")

            if activate_db and row is not None:
                n = activate_domain_row(conn, dk)
                if n:
                    print(f"         → set public.domains.is_active=TRUE for {dk!r}")
                conn.commit()

        print("-" * 60)
        if args.dry_run:
            print("dry-run: no DB updates performed")
        if any_warn:
            print(
                "Warnings: fix migrations, provision_domain, or RSS seed; "
                "deploy the same api/config/domains/*.yaml to Widow and main."
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
