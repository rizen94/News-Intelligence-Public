"""
V-Dem and Freedom House CSV imports into intelligence.macro_series_observations.

Drop CSV exports at:
  api/config/imports/vdem_export.csv  (columns: year, country, v2x_polyarchy)
  api/config/imports/freedom_house_export.csv  (columns: year, country, score)
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.macro_series_service import upsert_macro_observations

logger = logging.getLogger(__name__)

_DEFAULT_VDEM = Path(__file__).resolve().parent.parent / "config" / "imports" / "vdem_export.csv"
_DEFAULT_FH = Path(__file__).resolve().parent.parent / "config" / "imports" / "freedom_house_export.csv"


def _parse_annual_csv(
    path: Path,
    *,
    series_prefix: str,
    value_col: str,
    year_col: str = "year",
    country_col: str = "country",
    source: str,
) -> list[dict[str, Any]]:
    if not path.is_file():
        logger.info("CSV not found (skip): %s", path)
        return []
    rows: list[dict[str, Any]] = []
    vintage = datetime.now(timezone.utc)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year = (row.get(year_col) or "").strip()
            country = (row.get(country_col) or "global").strip().upper().replace(" ", "_")[:32]
            raw_val = row.get(value_col)
            if not year or raw_val in (None, ""):
                continue
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                continue
            obs_date = f"{year[:4]}-01-01"
            rows.append(
                {
                    "series_id": f"{series_prefix}_{country}",
                    "observation_date": obs_date,
                    "value": val,
                    "vintage_date": vintage,
                    "source": source,
                }
            )
    return rows


def import_vdem_freedom_house_from_config() -> dict[str, Any]:
    vdem_path = Path(os.environ.get("VDEM_CSV_PATH", str(_DEFAULT_VDEM)))
    fh_path = Path(os.environ.get("FREEDOM_HOUSE_CSV_PATH", str(_DEFAULT_FH)))
    vdem_rows = _parse_annual_csv(
        vdem_path,
        series_prefix="VDEM_POLYARCHY",
        value_col="v2x_polyarchy",
        source="vdem_csv",
    )
    fh_rows = _parse_annual_csv(
        fh_path,
        series_prefix="FH_SCORE",
        value_col="score",
        source="freedom_house_csv",
    )
    n = upsert_macro_observations(vdem_rows + fh_rows)
    return {
        "success": True,
        "inserted": n,
        "vdem_rows": len(vdem_rows),
        "freedom_house_rows": len(fh_rows),
    }
