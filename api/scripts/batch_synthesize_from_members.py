#!/usr/bin/env python3
"""Synthesize storyline narrative from cited members (LLM, persists editorial_document)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)


async def run_domain(domain: str, *, storyline_id: int | None, min_members: int, limit: int, dry_run: bool) -> int:
    from api.shared.database import get_db_connection_context
    from api.shared.domain_registry import resolve_domain_schema
    from services.storyline_member_synthesis_service import synthesize_and_persist_member_narrative

    schema = resolve_domain_schema(domain)
    ids: list[int] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if storyline_id:
                ids = [int(storyline_id)]
            else:
                cur.execute(
                    f"""
                    SELECT s.id
                    FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND COALESCE(s.status, 'active') NOT IN ('archived', 'merged', 'deleted')
                      AND COALESCE(s.article_count, 0) >= %s
                      AND (
                        char_length(COALESCE(s.description, '')) < 400
                        OR s.editorial_document IS NULL
                        OR COALESCE(s.document_status, 'draft') = 'draft'
                      )
                    ORDER BY s.updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (min_members, limit if limit > 0 else 50000),
                )
                ids = [int(r[0]) for r in (cur.fetchall() or [])]

    ok = 0
    for sid in ids:
        if dry_run:
            print(f"[dry-run] synthesize {domain}/{sid}")
            continue
        result = await synthesize_and_persist_member_narrative(domain, sid)
        if result.get("success"):
            ok += 1
            print(
                f"ok {domain}/{sid} articles={result.get('articles_used')} "
                f"chars={result.get('analysis_chars')}"
            )
        else:
            print(f"fail {domain}/{sid}: {result.get('error')}")
    print(f"Done {domain}: {ok}/{len(ids)} synthesized")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain", required=True)
    p.add_argument("--storyline-id", type=int, default=None)
    p.add_argument("--min-members", type=int, default=3)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    return asyncio.run(
        run_domain(
            args.domain,
            storyline_id=args.storyline_id,
            min_members=args.min_members,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())