#!/usr/bin/env python3
"""Triage editorial packages stuck in reduction/research parking (v12).

Dry-run by default. Max-rounds / converged packages → closed_thin (not editor).

  PYTHONPATH=api python api/scripts/triage_editorial_parking_lot.py --dry-run
  PYTHONPATH=api python api/scripts/triage_editorial_parking_lot.py --apply --limit 50
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("triage_parking_lot")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true", help="Write closed_thin")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    apply = bool(args.apply)
    dry_run = not apply

    try:
        from dotenv import load_dotenv

        load_dotenv(_API / ".env", override=False)
        load_dotenv(_API.parent / ".env", override=False)
    except Exception:
        pass

    from services.editorial_package_service import close_package_thin, list_packages

    stuck: list[dict] = []
    for status in ("in_reduction", "in_research", "in_narrative"):
        listed = list_packages(status=status, limit=args.limit)
        rows = listed.get("packages") if isinstance(listed, dict) else listed
        if not isinstance(rows, list):
            rows = []
        for pkg in rows:
            if not isinstance(pkg, dict):
                continue
            meta = pkg.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            rounds = int(
                meta.get("reduction_rounds")
                or meta.get("research_rounds")
                or meta.get("narrative_rounds")
                or 0
            )
            converged = bool(meta.get("reduction_converged"))
            if rounds >= 3 or converged or meta.get("escape") == "max_rounds":
                stuck.append(
                    {
                        "id": pkg["id"],
                        "status": pkg.get("status"),
                        "working_title": pkg.get("working_title"),
                        "rounds": rounds,
                        "converged": converged,
                    }
                )

    results = []
    for item in stuck[: args.limit]:
        if dry_run:
            results.append({**item, "action": "would_close_thin"})
            continue
        out = close_package_thin(
            int(item["id"]),
            actor="triage_parking_lot",
            rationale="parking lot triage → closed_thin",
            reason="parking_lot_triage",
        )
        results.append({**item, "action": "closed_thin", "ok": bool(out)})

    payload = {
        "dry_run": dry_run,
        "candidates": len(stuck),
        "processed": len(results),
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        logger.info(
            "triage candidates=%s processed=%s dry_run=%s",
            payload["candidates"],
            payload["processed"],
            dry_run,
        )
        for r in results[:20]:
            logger.info("  %s", r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
