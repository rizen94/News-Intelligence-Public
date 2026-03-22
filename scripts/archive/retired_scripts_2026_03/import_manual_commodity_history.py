#!/usr/bin/env python
"""
Import manual commodity history (e.g. silver, platinum) into the manual store.

Usage:
  ./scripts/import_manual_commodity_history.py metal path/to/history.csv

CSV format (header required):
  date,value,unit
  2023-01-01,23.95,USD/toz
  2023-01-02,24.10,USD/toz

This script does NOT call external APIs; it simply seeds the local market_data_store
so that /finance/commodity/{metal}/history can serve data without using Metals.dev
timeseries. Daily spot updates will be appended via the spot endpoint.
"""

import csv
import sys
from pathlib import Path

from domains.finance.commodity_store import upsert_manual_observations


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: import_manual_commodity_history.py metal path/to/history.csv")
        sys.exit(1)

    metal = sys.argv[1].lower()
    csv_path = Path(sys.argv[2])
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        sys.exit(1)

    observations = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = (row.get("date") or "").strip()
            value_str = (row.get("value") or "").strip()
            unit = (row.get("unit") or "USD/toz").strip()
            if not date_str or not value_str:
                continue
            try:
                value = float(value_str)
            except ValueError:
                continue
            observations.append(
                {
                    "date": date_str,
                    "value": value,
                    "metadata": {"unit": unit, "source_id": "manual_import"},
                }
            )

    if not observations:
        print("No valid observations found in CSV.")
        sys.exit(0)

    res = upsert_manual_observations(metal, observations)
    if res.success:
        print(f"Imported {len(observations)} observations for {metal}.")
        sys.exit(0)
    print(f"Import failed for {metal}: {res.error}")
    sys.exit(1)


if __name__ == "__main__":
    main()

