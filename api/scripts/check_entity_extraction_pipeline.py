#!/usr/bin/env python3
"""
Per-domain entity_extraction pipeline status (articles missing article_entities).

Confirms medicine/legal are in pipeline_url_schema_pairs() and reports backlog depth.

  PYTHONPATH=api uv run python api/scripts/check_entity_extraction_pipeline.py
  PYTHONPATH=api uv run python api/scripts/check_entity_extraction_pipeline.py --domain medicine
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(_root / "api" / ".env", override=False)
    load_dotenv(_root / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and (_pw := _root / ".db_password_widow").is_file():
    os.environ["DB_PASSWORD"] = _pw.read_text(encoding="utf-8").strip()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    get_pipeline_excluded_domain_keys,
    get_pipeline_included_domain_keys,
    pipeline_url_schema_pairs,
)


def _pending_without_entities(schema: str) -> tuple[int, int, int]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.articles")
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM {schema}.articles a
                LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                WHERE ae.id IS NULL
                  AND a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                  AND COALESCE(
                    (a.metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean,
                    false
                  ) = false
                """
            )
            pending = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*) FROM {schema}.article_entities")
            entities = int(cur.fetchone()[0])
    return total, pending, entities


def main() -> int:
    parser = argparse.ArgumentParser(description="Entity extraction pipeline status by domain")
    parser.add_argument("--domain", help="Single domain key")
    args = parser.parse_args()

    print("PIPELINE_INCLUDE_DOMAIN_KEYS:", os.environ.get("PIPELINE_INCLUDE_DOMAIN_KEYS") or "(unset)")
    print("PIPELINE_EXCLUDE_DOMAIN_KEYS:", os.environ.get("PIPELINE_EXCLUDE_DOMAIN_KEYS") or "(unset)")
    print("included:", get_pipeline_included_domain_keys())
    print("excluded:", get_pipeline_excluded_domain_keys())
    print("pipeline_active:", get_pipeline_active_domain_keys())
    print()

    pairs = pipeline_url_schema_pairs()
    if args.domain:
        pairs = [(dk, sch) for dk, sch in pairs if dk == args.domain]
        if not pairs:
            print(f"Domain {args.domain!r} not in pipeline_url_schema_pairs()")
            return 1

    exit_code = 0
    for domain_key, schema in pairs:
        try:
            total, pending, entities = _pending_without_entities(schema)
            in_pipeline = domain_key in get_pipeline_active_domain_keys()
            print(
                f"{domain_key:25} schema={schema:20} in_pipeline={in_pipeline} "
                f"articles={total} pending_entity_extraction={pending} article_entities_rows={entities}"
            )
            if in_pipeline and total > 0 and entities == 0 and pending > 0:
                print(
                    f"  -> entity_extraction is scheduled for this silo but has not written rows yet "
                    f"({pending} articles eligible). Check automation phase backlog / errors."
                )
                exit_code = 1
        except Exception as e:
            print(f"{domain_key}: ERROR {e}")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
