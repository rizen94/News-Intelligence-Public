#!/usr/bin/env python3
"""
Verify arc historical context respects as_of cutoff (point-in-time doctrine).

Usage:
  PYTHONPATH=api uv run python api/scripts/verify_arc_point_in_time.py
  PYTHONPATH=api uv run python api/scripts/verify_arc_point_in_time.py --arc resource_geopolitics
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from services.arc_historical_context_service import build_arc_historical_context


def _parse_dt(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def verify_arc(arc_id: str, as_of: datetime) -> list[str]:
    errors: list[str] = []
    bundle = build_arc_historical_context(arc_id, as_of)
    if not bundle.get("success"):
        return [f"{arc_id}: {bundle.get('error', 'failed')}"]

    for ev in bundle.get("reference_events") or []:
        ed = _parse_dt(ev.get("event_date"))
        if ed and ed > as_of:
            errors.append(f"reference_event {ev.get('id')} event_date {ed} > as_of")
        ing = _parse_dt(ev.get("ingestion_date"))
        if ing and ing > as_of:
            errors.append(f"reference_event {ev.get('id')} ingestion_date {ing} > as_of")

    for fact in bundle.get("living_facts") or []:
        ing = _parse_dt(fact.get("ingestion_date"))
        if ing and ing > as_of:
            errors.append(f"versioned_fact {fact.get('id')} ingestion_date {ing} > as_of")

    for ext in bundle.get("external_events") or []:
        ed = _parse_dt(ext.get("event_date"))
        if ed and ed > as_of:
            errors.append(f"external_event {ext.get('id')} event_date {ed} > as_of")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify arc point-in-time context")
    parser.add_argument("--arc", default="resource_geopolitics")
    parser.add_argument(
        "--as-of",
        default="1990-06-01T00:00:00+00:00",
        help="ISO UTC cutoff (default: 1990-06-01 — should exclude post-1990 events)",
    )
    args = parser.parse_args()
    as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    errors = verify_arc(args.arc, as_of)
    if errors:
        print(f"FAIL {args.arc} as_of={as_of.isoformat()}:")
        for e in errors:
            print(f"  - {e}")
        return 1

    bundle = build_arc_historical_context(args.arc, as_of)
    n_ref = len(bundle.get("reference_events") or [])
    n_facts = len(bundle.get("living_facts") or [])
    print(
        f"OK {args.arc} as_of={as_of.date()} "
        f"reference_events={n_ref} living_facts={n_facts}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
