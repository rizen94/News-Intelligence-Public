#!/usr/bin/env python3
"""Backfill versioned_facts.sources + verification_status column (dev DB only).

Populates empty ``sources`` from claim→context→article bridges, and copies
``metadata.verification_status`` onto the top-level column when set.

Guard: refuses Widow host. Load ``.env.dev`` before running.

  set -a; source .env.dev; set +a
  PYTHONPATH=api python3 api/scripts/backfill_versioned_facts_provenance.py --limit 5000
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API)

from shared.dev_guard import DevGuardError, assert_dev_db_host_safe  # noqa: E402
from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import resolve_domain_schema  # noqa: E402


def _build_sources_for_claim(cur, claim_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT ec.context_id, atc.domain_key, atc.article_id,
               c.metadata->>'url', c.ingestion_date
        FROM intelligence.extracted_claims ec
        LEFT JOIN intelligence.article_to_context atc ON atc.context_id = ec.context_id
        LEFT JOIN intelligence.contexts c ON c.id = ec.context_id
        WHERE ec.id = %s
        LIMIT 8
        """,
        (claim_id,),
    )
    out: list[dict] = []
    for context_id, domain_key, article_id, url, ingestion_date in cur.fetchall() or []:
        if domain_key and article_id is not None:
            try:
                schema = resolve_domain_schema(str(domain_key))
                cur.execute(
                    f"SELECT url, COALESCE(ingestion_date, created_at) FROM {schema}.articles WHERE id = %s",
                    (int(article_id),),
                )
                art = cur.fetchone()
                if art:
                    url = art[0] or url
                    if art[1] is not None:
                        ingestion_date = art[1]
            except Exception:
                pass
        out.append(
            {
                "claim_id": int(claim_id),
                "context_id": int(context_id) if context_id is not None else None,
                "domain_key": domain_key,
                "article_id": int(article_id) if article_id is not None else None,
                "url": url,
                "retrieved_at": (
                    ingestion_date.isoformat()
                    if hasattr(ingestion_date, "isoformat")
                    else (str(ingestion_date) if ingestion_date else None)
                ),
                "source_type": "article",
            }
        )
    if not out:
        out.append({"claim_id": int(claim_id), "source_type": "extracted_claim"})
    return out


def main() -> int:
    try:
        assert_dev_db_host_safe()
    except DevGuardError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2

    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    updated_sources = 0
    updated_status = 0
    with get_db_connection_context() as conn:
        if not conn:
            print("no db", file=sys.stderr)
            return 1
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, metadata->>'source_claim_id',
                       metadata->>'verification_status', verification_status,
                       sources
                FROM intelligence.versioned_facts
                WHERE (
                    sources IS NULL
                    OR sources = '[]'::jsonb
                    OR sources = '{}'::jsonb
                    OR (
                        verification_status IS NULL
                        OR verification_status = 'unverified'
                    )
                    AND COALESCE(metadata->>'verification_status', '') <> ''
                )
                ORDER BY id
                LIMIT %s
                """,
                (int(args.limit),),
            )
            rows = cur.fetchall() or []
            for fid, claim_id, meta_status, col_status, sources in rows:
                if claim_id and (sources is None or sources in ([], {}, "[]", "{}")):
                    try:
                        payload = _build_sources_for_claim(cur, int(claim_id))
                    except Exception:
                        payload = [{"claim_id": int(claim_id), "source_type": "extracted_claim"}]
                    if not args.dry_run:
                        cur.execute(
                            """
                            UPDATE intelligence.versioned_facts
                            SET sources = %s::jsonb
                            WHERE id = %s
                              AND (sources IS NULL OR sources = '[]'::jsonb OR sources = '{}'::jsonb)
                            """,
                            (json.dumps(payload), int(fid)),
                        )
                    updated_sources += 1
                if meta_status and (not col_status or col_status == "unverified"):
                    if not args.dry_run:
                        cur.execute(
                            """
                            UPDATE intelligence.versioned_facts
                            SET verification_status = %s
                            WHERE id = %s
                            """,
                            (meta_status, int(fid)),
                        )
                    updated_status += 1
        if not args.dry_run:
            conn.commit()
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": bool(args.dry_run),
                "sources_backfilled": updated_sources,
                "verification_status_backfilled": updated_status,
                "db_host": os.environ.get("DB_HOST"),
                "db_name": os.environ.get("DB_NAME"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
