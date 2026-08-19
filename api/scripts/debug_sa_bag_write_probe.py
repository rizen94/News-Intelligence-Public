#!/usr/bin/env python3
"""Probe bag-write gates and optionally run one politics discovery cycle."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


def _log_gates() -> dict:
    from shared.assembly_link_funnel import (
        automation_auto_attach_enabled,
        storyline_articles_dual_write_enabled,
        storyline_articles_write_allowed,
    )
    from shared.episode_attach_gate import episode_container_assembly_enabled
    from shared.membership_mode import get_membership_mode

    gates = {
        "membership_mode": get_membership_mode().value,
        "episode": episode_container_assembly_enabled(),
        "dual_write": storyline_articles_dual_write_enabled(),
        "write_allowed": storyline_articles_write_allowed(),
        "absorb": automation_auto_attach_enabled(),
    }
    return gates


def _recent_sa_stats() -> dict:
    import os

    import psycopg2

    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(added_by,'(null)'), COALESCE(relationship_type,'(null)'), count(*)
        FROM politics.storyline_articles
        WHERE created_at > now() - interval '1 hour'
        GROUP BY 1,2 ORDER BY 3 DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return {"last_hour_breakdown": rows}


async def _run_assembly(domain: str) -> dict:
    from services.storyline_assembly_service import run_storyline_assembly_for_domain

    return await run_storyline_assembly_for_domain(domain)


def _run_discovery_only(domain: str, *, article_limit: int = 80) -> dict:
    from services.ai_storyline_discovery import get_discovery_service

    svc = get_discovery_service()
    return svc.discover_storylines(
        domain=domain,
        hours=24,
        save_to_db=True,
        article_limit=article_limit,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug SA bag-write probe")
    parser.add_argument("--domain", default="politics")
    parser.add_argument("--run-assembly", action="store_true")
    parser.add_argument("--run-discovery-only", action="store_true")
    parser.add_argument("--article-limit", type=int, default=80)
    args = parser.parse_args()

    gates = _log_gates()
    stats = _recent_sa_stats()
    print(json.dumps({"gates": gates, "stats": stats}, indent=2, default=str))

    if args.run_discovery_only:
        print(f"Running discovery-only for {args.domain} (limit={args.article_limit})...")
        result = _run_discovery_only(args.domain, article_limit=args.article_limit)
        print(
            json.dumps(
                {
                    "discovery": result.get("summary"),
                    "saved": len(result.get("saved_storylines") or []),
                },
                indent=2,
                default=str,
            )
        )

    if args.run_assembly:
        print(f"Running storyline assembly for {args.domain}...")
        result = asyncio.run(_run_assembly(args.domain))
        print(json.dumps({"assembly": result}, indent=2, default=str)[:4000])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
