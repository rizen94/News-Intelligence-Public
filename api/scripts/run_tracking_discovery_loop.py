#!/usr/bin/env python3
"""
Headless tracking discovery loop — Widow cron (replaces OWUI-only tracking discovery).

1. vault_bridge.read_cursors()
2. tracking_discovery.run(since=last_tracking_scan_at)
3. vault_bridge.write_candidates()
4. promotion_bridge.apply(top_n)
5. vault_bridge.update_cursors(now)
6. optional session log append
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _run(*, top_n: int, dry_run: bool) -> int:
    from services import tracking_discovery_service as discovery
    from services import tracking_promotion_service as promotion
    from services import vault_bridge_service as vault

    cursors = vault.read_cursors()
    since = cursors.get("last_tracking_scan_at")
    logger.info("Starting tracking discovery loop since=%s", since)

    result = discovery.run_tracking_discovery(since=since, include_vault_reconcile=True)
    candidates = result.get("all_candidates") or result.get("items") or []
    ranked = result.get("items") or []

    if dry_run:
        logger.info(
            "DRY RUN: raw=%s ranked=%s",
            result.get("raw_candidate_count"),
            result.get("ranked_candidate_count"),
        )
        return 0

    vault.write_candidates(
        candidates,
        scan_since=str(result.get("scan_since", "")),
        domains_scanned=list(result.get("domains_scanned") or []),
    )

    promo = await promotion.apply_promotions(candidates, top_n=top_n)
    now = datetime.now(timezone.utc).isoformat()
    vault.update_cursors(last_tracking_scan_at=now)

    top = ranked[0] if ranked else {}
    summary = (
        f"- Raw candidates: {result.get('raw_candidate_count')}\n"
        f"- Ranked: {result.get('ranked_candidate_count')}\n"
        f"- Promoted: {promo.get('promoted_count')}\n"
        f"- Top: {top.get('type', 'n/a')} — {top.get('title', 'n/a')} "
        f"(score {top.get('score', 'n/a')}/25)"
    )
    vault.append_session_log(summary)
    logger.info("Tracking discovery loop complete promoted=%s", promo.get("promoted_count"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Widow tracking discovery + vault loop")
    parser.add_argument("--top-n", type=int, default=5, help="Max promotions per run")
    parser.add_argument("--dry-run", action="store_true", help="Discovery only; no vault/promote writes")
    args = parser.parse_args()
    return asyncio.run(_run(top_n=args.top_n, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
