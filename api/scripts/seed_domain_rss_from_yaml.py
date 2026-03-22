#!/usr/bin/env python3
"""
Insert ``data_sources.rss.seed_feed_urls`` from a domain YAML into ``{schema}.rss_feeds``.

Use when the silo was provisioned before RSS seeding ran, or after editing seed URLs.

  PYTHONPATH=api uv run python api/scripts/seed_domain_rss_from_yaml.py \\
    --config api/config/domains/medicine.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api_dir = Path(__file__).resolve().parent.parent
    load_dotenv(_api_dir / ".env", override=False)
    load_dotenv(_api_dir.parent / ".env", override=False)
except ImportError:
    pass

if (
    not os.environ.get("DB_PASSWORD")
    and Path(Path(__file__).resolve().parent.parent.parent / ".db_password_widow").is_file()
):
    try:
        with open(Path(__file__).resolve().parent.parent.parent / ".db_password_widow") as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except OSError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from shared.database.connection import get_db_connection  # noqa: E402
from shared.services.domain_rss_seed import seed_from_domain_config  # noqa: E402


def _load_config(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or not isinstance(data, dict):
        raise SystemExit("YAML must be a mapping at top level")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill rss_feeds from domain YAML seed_feed_urls"
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to api/config/domains/{key}.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print URL count only; do not connect to DB",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    schema_name = cfg.get("schema_name")
    domain_key = cfg.get("domain_key")
    if not schema_name:
        raise SystemExit("YAML must define schema_name")

    if args.dry_run:
        from shared.services.domain_rss_seed import extract_seed_feed_urls

        urls = extract_seed_feed_urls(cfg)
        print(f"dry-run: domain_key={domain_key!r} schema={schema_name!r} urls={len(urls)}")
        return

    conn = get_db_connection()
    if not conn:
        raise SystemExit("No database connection")
    try:
        added, skipped = seed_from_domain_config(conn, cfg, schema_name)
        conn.commit()
        print(
            f"Done: {schema_name}.rss_feeds — inserted {added}, skipped (duplicate URL) {skipped}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
