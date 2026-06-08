#!/usr/bin/env python3
"""Backfill wikidata_qid on entity_canonical from Wikidata SPARQL label lookup.

  PYTHONPATH=api uv run python api/scripts/backfill_wikidata_qids.py --domain politics --limit 200
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

import requests

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from shared.database.connection import get_db_connection_context
from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

logger = logging.getLogger(__name__)
_WD_SPARQL = "https://query.wikidata.org/sparql"


def _lookup_qid(label: str) -> str | None:
    query = f"""
    SELECT ?item WHERE {{
      ?item rdfs:label "{label.replace('"', "")}"@en .
    }} LIMIT 1
    """
    try:
        r = requests.get(
            _WD_SPARQL,
            params={"query": query, "format": "json"},
            headers={"User-Agent": "NewsIntelligence/1.0 (wikidata backfill)"},
            timeout=30,
        )
        r.raise_for_status()
        bindings = (r.json().get("results") or {}).get("bindings") or []
        if not bindings:
            return None
        uri = bindings[0].get("item", {}).get("value", "")
        m = re.search(r"(Q\d+)$", uri)
        return m.group(1) if m else None
    except Exception as e:
        logger.debug("wikidata lookup %s: %s", label, e)
        return None


def backfill_domain(domain_key: str, *, limit: int = 200, dry_run: bool = False) -> dict:
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": "invalid_domain"}
    schema = resolve_domain_schema(domain_key)
    updated = 0
    skipped = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name FROM {schema}.entity_canonical
                WHERE wikidata_qid IS NULL OR wikidata_qid = ''
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            for eid, name in rows:
                qid = _lookup_qid(name)
                if not qid:
                    skipped += 1
                    continue
                if dry_run:
                    updated += 1
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.entity_canonical
                    SET wikidata_qid = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (qid, eid),
                )
                updated += 1
        if not dry_run:
            conn.commit()
    return {"success": True, "updated": updated, "skipped": skipped, "domain": domain_key}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    p.add_argument("--domain", default="politics")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    print(backfill_domain(args.domain, limit=args.limit, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
