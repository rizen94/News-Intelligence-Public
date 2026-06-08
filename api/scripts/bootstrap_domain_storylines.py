#!/usr/bin/env python3
"""
Run storyline discovery + proactive detection for one domain (operator backfill).

  PYTHONPATH=api uv run python api/scripts/bootstrap_domain_storylines.py --domain medicine
  PYTHONPATH=api uv run python api/scripts/bootstrap_domain_storylines.py --domain medicine --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
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

if (
    not os.environ.get("DB_PASSWORD")
    and (_pw := _root / ".db_password_widow").is_file()
):
    try:
        os.environ["DB_PASSWORD"] = _pw.read_text(encoding="utf-8").strip()
    except OSError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domains.storyline_management.services.proactive_detection_service import (  # noqa: E402
    ProactiveDetectionService,
)
from services.ai_storyline_discovery import get_discovery_service  # noqa: E402
from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import resolve_domain_schema  # noqa: E402


def _storyline_count(schema: str) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.storylines")
            row = cur.fetchone()
            return int(row[0]) if row else 0


async def _run_proactive(domain: str, hours: int | None) -> dict:
    svc = ProactiveDetectionService(domain=domain)
    if hours is None:
        return await svc.detect_emerging_storylines()
    return await svc.detect_emerging_storylines(hours=hours)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap domain storylines via discovery + proactive")
    parser.add_argument("--domain", required=True, help="Domain key (e.g. medicine)")
    parser.add_argument("--hours", type=int, default=None, help="Proactive lookback hours (default: domain YAML)")
    parser.add_argument("--dry-run", action="store_true", help="Print config only; no pipeline runs")
    args = parser.parse_args()

    domain = args.domain.strip()
    schema = resolve_domain_schema(domain)
    before = _storyline_count(schema)
    print(f"Domain={domain} schema={schema} storylines_before={before}")

    if args.dry_run:
        from services.domain_synthesis_config import get_storyline_development_config

        dev = get_storyline_development_config(domain)
        print(
            f"discovery: sim={dev.discovery.clustering_similarity_threshold} "
            f"min_cluster={dev.discovery.min_cluster_size}"
        )
        print(
            f"proactive: kw={dev.proactive.keyword_similarity_threshold} "
            f"min_articles={dev.proactive.min_articles} outbreak={dev.narrative.allow_promote_pair_on_outbreak}"
        )
        return 0

    discovery = get_discovery_service()
    disc = discovery.discover_storylines(domain=domain, hours=None, save_to_db=True)
    summary = disc.get("summary") or {}
    print(
        f"discovery: clusters={summary.get('clusters_found')} "
        f"saved={summary.get('storylines_saved')}"
    )

    proactive_hours = args.hours
    proactive = asyncio.run(_run_proactive(domain, proactive_hours))
    pdata = proactive.get("data") or {}
    print(
        f"proactive: stored={pdata.get('stored_count')} "
        f"promoted={pdata.get('promoted_to_domain_storylines')}"
    )

    after = _storyline_count(schema)
    print(f"storylines_after={after} (delta={after - before})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
