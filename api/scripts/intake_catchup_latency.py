#!/usr/bin/env python3
"""
Intake → full-process catchup latency report (RSS created_at → core stages done).

Default SLA: CATCHUP_SLA_HOURS=6. Stages: enrich, unified intake, context_sync,
topic_clustering, storyline link (not assembly/EPB).

  cd /path/to/repo && PYTHONPATH=api uv run python api/scripts/intake_catchup_latency.py
  PYTHONPATH=api uv run python api/scripts/intake_catchup_latency.py --json --sla-hours 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api = Path(__file__).resolve().parent.parent
    load_dotenv(_api / ".env", override=False)
    load_dotenv(_api.parent / ".env", override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_db_password() -> None:
    import os

    root = Path(__file__).resolve().parent.parent.parent
    pw_file = root / ".db_password_widow"
    if not os.environ.get("DB_PASSWORD") and pw_file.is_file():
        os.environ.setdefault("DB_PASSWORD", pw_file.read_text().splitlines()[0].strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Intake→full-process catchup latency")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument(
        "--sla-hours",
        type=float,
        default=None,
        help="SLA hours (default CATCHUP_SLA_HOURS or 6)",
    )
    parser.add_argument(
        "--window-hours",
        type=int,
        default=None,
        help="Cohort window (default MONITOR_INTAKE_WINDOW_HOURS or 72)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass in-process cache",
    )
    args = parser.parse_args()

    _load_db_password()

    from shared.intake_catchup_latency import compute_intake_catchup_latency

    report = compute_intake_catchup_latency(
        window_hours=args.window_hours,
        sla_hours=args.sla_hours,
        use_cache=not args.no_cache,
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    sla = report.get("sla_hours")
    print("Intake → full-process catchup latency")
    print(f"  window_hours={report.get('window_hours')}  sla_hours={sla}")
    print(f"  stages: {', '.join(report.get('stages') or [])}")
    print(
        f"  cohort={report.get('cohort_n')}  completed={report.get('sample_n_completed')}  "
        f"inflight={report.get('inflight_n')}"
    )
    print(
        f"  p50_hours={report.get('p50_hours')}  p95_hours={report.get('p95_hours')}  "
        f"over_sla_n={report.get('over_sla_n')}"
    )
    print(
        f"  max_inflight_age_hours={report.get('max_inflight_age_hours')}  "
        f"p95_inflight_age_hours={report.get('p95_inflight_age_hours')}"
    )
    ok = report.get("ok_under_sla")
    print(f"  ok_under_sla={ok}  (needs sample_n_completed >= {report.get('min_samples_for_sla')})")
    if report.get("note"):
        print(f"  note: {report['note']}")
    if report.get("errors"):
        print(f"  errors: {report['errors']}")
    print("  per_domain:")
    for d in report.get("per_domain") or []:
        print(
            f"    {d.get('domain_key')}: p95={d.get('p95_hours')}h  "
            f"inflight={d.get('inflight_n')}  max_age={d.get('max_inflight_age_hours')}h  "
            f"ok={d.get('ok_under_sla')}"
        )
    return 0 if not report.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
