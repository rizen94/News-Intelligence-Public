"""
GPR + EPU CSV import into intelligence.macro_series_observations.

Expects CSV files at paths configured via env or api/config/macro_csv_imports.yaml.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.macro_series_service import upsert_macro_observations
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

_DEFAULT_GPR = Path(__file__).resolve().parent.parent / "config" / "imports" / "gpr_export.csv"
_DEFAULT_EPU = Path(__file__).resolve().parent.parent / "config" / "imports" / "epu_export.csv"


def _parse_monthly_csv(
    path: Path,
    *,
    series_id: str,
    date_col: str = "month",
    value_col: str = "value",
    source: str = "csv_import",
) -> list[dict[str, Any]]:
    if not path.is_file():
        logger.info("CSV not found (skip): %s", path)
        return []
    rows: list[dict[str, Any]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_date = (row.get(date_col) or row.get("date") or "").strip()
            raw_val = row.get(value_col) or row.get(series_id)
            if not raw_date or raw_val in (None, ""):
                continue
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                continue
            obs_date = raw_date[:10] if len(raw_date) >= 10 else f"{raw_date[:7]}-01"
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": obs_date,
                    "value": val,
                    "vintage_date": datetime.now(timezone.utc),
                    "source": source,
                }
            )
    return rows


def import_gpr_epu_from_config() -> dict[str, Any]:
    gpr_path = Path(env_str("GPR_CSV_PATH", str(_DEFAULT_GPR)))
    epu_path = Path(env_str("EPU_CSV_PATH", str(_DEFAULT_EPU)))
    gpr_rows = _parse_monthly_csv(gpr_path, series_id="GPRTOT", value_col="GPR", source="gpr_csv")
    epu_rows = _parse_monthly_csv(epu_path, series_id="GEPUCURRENT", value_col="EPU", source="epu_csv")
    n = upsert_macro_observations(gpr_rows + epu_rows)
    return {
        "success": True,
        "inserted": n,
        "gpr_rows": len(gpr_rows),
        "epu_rows": len(epu_rows),
    }
