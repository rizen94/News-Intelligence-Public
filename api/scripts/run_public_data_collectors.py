#!/usr/bin/env python3
"""
Run Phase 1 public-data collectors (feature-flagged, idempotent).

Usage (repo root):

  PYTHONPATH=api python api/scripts/run_public_data_collectors.py --source all
  PYTHONPATH=api python api/scripts/run_public_data_collectors.py --source courtlistener
  PYTHONPATH=api python api/scripts/run_public_data_collectors.py \\
      --source federal_register,edgar --json

Sources:
  courtlistener | federal_register | congress_status | ma_newton | edgar
  fred | gdelt_aid | acled | ucdp | all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

logger = logging.getLogger("run_public_data_collectors")

SOURCE_RUNNERS: dict[str, Callable[[], dict[str, Any]]] = {}


def _register() -> None:
    from collectors.congress_status_collector import collect_congress_status
    from collectors.courtlistener_collector import collect_courtlistener
    from collectors.edgar_collector import collect_edgar
    from collectors.federal_register_collector import collect_federal_register
    from collectors.gdelt_events_aid_collector import collect_gdelt_events_aid
    from collectors.ma_newton_collector import collect_ma_newton
    from services.acled_client import run_acled_incremental_sync
    from services.macro_series_service import refresh_longitudinal_macro_series
    from services.ucdp_client import run_ucdp_backfill_batch

    SOURCE_RUNNERS.update(
        {
            "courtlistener": collect_courtlistener,
            "federal_register": collect_federal_register,
            "congress_status": collect_congress_status,
            "ma_newton": collect_ma_newton,
            "edgar": collect_edgar,
            "gdelt_aid": collect_gdelt_events_aid,
            "fred": refresh_longitudinal_macro_series,
            "acled": run_acled_incremental_sync,
            "ucdp": run_ucdp_backfill_batch,
        }
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Run public-data collectors (Phase 1)")
    p.add_argument(
        "--source",
        default="all",
        help="Comma-separated sources or 'all' (default)",
    )
    p.add_argument("--json", action="store_true", help="Print JSON results")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch/preview without upsert (edgar/FR/courtlistener)",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        from dotenv import load_dotenv

        load_dotenv(_API / ".env", override=False)
        load_dotenv(_API.parent / ".env", override=False)
    except Exception:
        pass

    _register()
    wanted = [s.strip().lower() for s in args.source.split(",") if s.strip()]
    if not wanted or wanted == ["all"]:
        wanted = list(SOURCE_RUNNERS.keys())

    unknown = [s for s in wanted if s not in SOURCE_RUNNERS]
    if unknown:
        print(f"Unknown source(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Valid: {', '.join(sorted(SOURCE_RUNNERS))} | all", file=sys.stderr)
        return 2

    results: dict[str, Any] = {}
    dry_kw = {"dry_run": True} if args.dry_run else {}
    for name in wanted:
        logger.info("Running collector: %s dry_run=%s", name, args.dry_run)
        try:
            runner = SOURCE_RUNNERS[name]
            if args.dry_run and name in (
                "edgar",
                "federal_register",
                "courtlistener",
            ):
                results[name] = runner(**dry_kw)
            else:
                if args.dry_run:
                    results[name] = {
                        "skipped": True,
                        "reason": "dry_run not implemented for this source",
                    }
                else:
                    results[name] = runner()
        except Exception as e:
            logger.exception("Collector %s failed", name)
            results[name] = {"success": False, "error": str(e)}

    payload = {"success": True, "dry_run": bool(args.dry_run), "results": results}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        for name, res in results.items():
            print(f"== {name} ==")
            print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
