#!/usr/bin/env python3
"""
Backfill story_entity_index.entity_role from hub facets + matter/party mapping.

Sets who|what|where for configured hub institutions and party/matter for
non-hub durables. Runs across all pipeline-active domain schemas.

Usage:
  PYTHONPATH=api uv run python api/scripts/backfill_sei_hub_roles.py
  PYTHONPATH=api uv run python api/scripts/backfill_sei_hub_roles.py --domain legal
  PYTHONPATH=api uv run python api/scripts/backfill_sei_hub_roles.py --dry-run
  PYTHONPATH=api uv run python api/scripts/backfill_sei_hub_roles.py --domain politics --limit 500
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.story_entity_index import resolve_entity_role_for_sei

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def backfill_domain(
    domain_key: str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    summary: dict[str, Any] = {
        "domain": domain_key,
        "schema": schema,
        "scanned": 0,
        "updated": 0,
        "skipped": 0,
        "unchanged": 0,
        "dry_run": dry_run,
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            where = ""
            if not force:
                where = "WHERE entity_role IS NULL OR TRIM(entity_role) = ''"
            lim_sql = ""
            params: list[Any] = []
            if limit is not None:
                lim_sql = " LIMIT %s"
                params.append(max(0, int(limit)))
            cur.execute(
                f"""
                SELECT id, entity_name, entity_type, entity_role
                FROM {schema}.story_entity_index
                {where}
                ORDER BY id
                {lim_sql}
                """,
                params or None,
            )
            rows = cur.fetchall() or []
            summary["scanned"] = len(rows)
            for row_id, name, etype, current_role in rows:
                role, _hub_key = resolve_entity_role_for_sei(
                    domain_key=domain_key,
                    entity_name=name,
                    entity_type=etype,
                )
                if not role:
                    summary["skipped"] += 1
                    continue
                if (current_role or "").strip().lower() == role and not force:
                    summary["unchanged"] += 1
                    continue
                if dry_run:
                    summary["updated"] += 1
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.story_entity_index
                    SET entity_role = %s
                    WHERE id = %s
                    """,
                    (role, int(row_id)),
                )
                summary["updated"] += 1
        if not dry_run:
            conn.commit()
    logger.info(
        "%s: scanned=%s updated=%s skipped=%s unchanged=%s dry_run=%s",
        domain_key,
        summary["scanned"],
        summary["updated"],
        summary["skipped"],
        summary["unchanged"],
        dry_run,
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", help="Single domain key (default: all pipeline-active)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Recompute even when entity_role set")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    domains = (
        [args.domain.strip().lower()]
        if args.domain
        else list(get_pipeline_active_domain_keys())
    )
    if not args.domain:
        try:
            from shared.domain_registry import get_active_domain_keys

            for dk in get_active_domain_keys():
                if dk not in domains:
                    domains.append(dk)
        except Exception:
            pass

    totals = []
    for dk in domains:
        try:
            totals.append(
                backfill_domain(
                    dk, dry_run=args.dry_run, limit=args.limit, force=args.force
                )
            )
        except Exception as e:
            logger.error("%s failed: %s", dk, e)
            totals.append({"domain": dk, "error": str(e)})
    updated = sum(int(t.get("updated") or 0) for t in totals if "error" not in t)
    logger.info("done domains=%s updated=%s", len(totals), updated)
    return 0 if all("error" not in t for t in totals) else 1


if __name__ == "__main__":
    sys.exit(main())
