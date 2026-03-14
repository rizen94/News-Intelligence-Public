#!/usr/bin/env python
"""
Export historical metal prices from Metals.dev /timeseries into a CSV suitable for
import_manual_commodity_history.py.

Usage:
  ./scripts/export_metals_dev_history_to_csv.py silver 5 data/finance/manual_history/silver_history.csv

This script:
- Reads METALS_DEV_API_KEY from the environment (.env).
- Walks backward over the requested number of years in 30-day windows.
- Calls https://api.metals.dev/v1/timeseries for each window.
- Writes a CSV with columns: date,value,unit

NOTE: This consumes Metals.dev quota (1 call per 30-day window).
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


BASE_URL = "https://api.metals.dev/v1/timeseries"


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: export_metals_dev_history_to_csv.py metal years_out output.csv")
        sys.exit(1)

    metal = sys.argv[1].lower()
    years_out = int(sys.argv[2])
    out_path = Path(sys.argv[3])

    api_key = os.environ.get("METALS_DEV_API_KEY")
    if not api_key:
        print("METALS_DEV_API_KEY not set in environment.")
        sys.exit(1)

    # Compute date range
    end_dt = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=365 * max(1, years_out))

    all_rows: list[tuple[str, float, str]] = []
    cur = start_dt
    window_days = 30

    print(f"Exporting {metal} history from {start_dt} to {end_dt} using Metals.dev...")

    while cur <= end_dt:
        window_end = min(cur + timedelta(days=window_days - 1), end_dt)
        params = {
            "api_key": api_key,
            "start_date": cur.strftime("%Y-%m-%d"),
            "end_date": window_end.strftime("%Y-%m-%d"),
        }
        url = BASE_URL
        print(f"  Window {params['start_date']} -> {params['end_date']} ...", end="", flush=True)
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                print(f" HTTP {resp.status_code}")
                sys.exit(1)
            data = resp.json()
            if data.get("status") != "success":
                print(f" ERROR: {data.get('error_code')} {data.get('error_message')}")
                sys.exit(1)
            rates = data.get("rates") or {}
            unit = data.get("unit", "toz")
            for date_str, day_data in rates.items():
                if not isinstance(day_data, dict):
                    continue
                metals = day_data.get("metals") or {}
                val = metals.get(metal)
                if val is None:
                    continue
                try:
                    value = float(val)
                except (TypeError, ValueError):
                    continue
                all_rows.append((date_str, value, f"USD/{unit}"))
            print(f" ok ({len(all_rows)} total rows)")
        except Exception as exc:
            print(f" ERROR: {exc}")
            sys.exit(1)
        # Be gentle with the API
        time.sleep(1.0)
        cur = window_end + timedelta(days=1)

    if not all_rows:
        print("No data fetched from Metals.dev.")
        sys.exit(1)

    all_rows.sort(key=lambda r: r[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value", "unit"])
        for date_str, value, unit in all_rows:
            w.writerow([date_str, value, unit])

    print(f"Wrote {len(all_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

