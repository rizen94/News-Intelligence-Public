#!/usr/bin/env python
"""
Export historical metal prices from a FRED series into a CSV suitable for
import_manual_commodity_history.py.

Usage:
  ./scripts/export_fred_history_to_csv.py SERIES_ID years_out output.csv

Example (you choose the correct FRED series IDs):
  ./scripts/export_fred_history_to_csv.py PLATINUM_SERIES_ID 10 data/finance/manual_history/platinum_history.csv

This script:
  - Reads FRED_API_KEY from the environment (.env).
  - Calls fred/series/observations for the chosen series.
  - Writes a CSV with columns: date,value,unit
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Load .env from project root so FRED_API_KEY is available when not set in shell
_project_root = Path(__file__).resolve().parent.parent
_env = _project_root / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env)
    except ImportError:
        pass


BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


def main() -> None:
  if len(sys.argv) != 4:
    print("Usage: export_fred_history_to_csv.py SERIES_ID years_out output.csv")
    sys.exit(1)

  series_id = sys.argv[1]
  years_out = int(sys.argv[2])
  out_path = Path(sys.argv[3])

  api_key = os.environ.get("FRED_API_KEY")
  if not api_key:
    print("FRED_API_KEY not set in environment.")
    sys.exit(1)

  end_dt = datetime.now(timezone.utc).date()
  start_dt = end_dt - timedelta(days=365 * max(1, years_out))

  params = {
    "series_id": series_id,
    "api_key": api_key,
    "file_type": "json",
    "observation_start": start_dt.strftime("%Y-%m-%d"),
    "observation_end": end_dt.strftime("%Y-%m-%d"),
  }

  print(f"Exporting FRED series {series_id} from {params['observation_start']} to {params['observation_end']}...")

  try:
    resp = requests.get(BASE_URL, params=params, timeout=30)
    if resp.status_code != 200:
      print(f"HTTP {resp.status_code} from FRED")
      sys.exit(1)
    data = resp.json()
    observations = data.get("observations") or []
  except Exception as exc:
    print(f"Error calling FRED: {exc}")
    sys.exit(1)

  if not observations:
    print("No observations returned from FRED.")
    sys.exit(0)

  rows: list[tuple[str, float, str]] = []
  for obs in observations:
    date_str = obs.get("date")
    value_str = obs.get("value")
    if not date_str or value_str in (None, ".", ""):
      continue
    try:
      value = float(value_str)
    except ValueError:
      continue
    rows.append((date_str, value, "USD/toz"))

  if not rows:
    print("No numeric observations parsed from FRED.")
    sys.exit(0)

  rows.sort(key=lambda r: r[0])
  out_path.parent.mkdir(parents=True, exist_ok=True)
  with out_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "value", "unit"])
    for date_str, value, unit in rows:
      w.writerow([date_str, value, unit])

  print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
  main()

