"""
Commodity fetcher — gold (amalgamator); all other registry ids via FRED when configured.
Silver/platinum: FRED first (optional store), then metals.dev. Oil/gas: FRED only (no metals.dev).
"""

import logging
from datetime import datetime, timedelta, timezone

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


def fetch_commodity(
    topic: str,
    start: str | None = None,
    end: str | None = None,
    store: bool = True,
) -> dict[str, list[dict] | bool | str]:
    """
    Fetch commodity data for any registry id (gold, silver, platinum, oil, gas, ...).
    Gold: amalgamator. Others: FRED when series configured; respect ``store`` for FRED persistence.
    Silver/platinum: metals.dev fallback if FRED empty. Oil/gas: no metals fallback.
    Returns {source_id: [obs, ...]}. When both sources fail, also includes "unavailable": True and "message": str.
    """
    topic = (topic or "gold").lower()
    if topic == "gold":
        from domains.finance.gold_amalgamator import fetch_all

        return fetch_all(start=start, end=end, store=store)

    # Non-gold: FRED when configured; metals.dev only for metals_dev commodities
    report_id = f"{topic}_fetch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    end_dt = None
    start_dt = None
    if end:
        from datetime import datetime as _dt

        end_dt = _dt.strptime(end, "%Y-%m-%d").date()
    if start:
        from datetime import datetime as _dt

        start_dt = _dt.strptime(start, "%Y-%m-%d").date()
    if end_dt is None:
        end_dt = datetime.now(timezone.utc).date()
    if start_dt is None:
        start_dt = end_dt - timedelta(days=90)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")

    from shared.data_result import DataResult

    from domains.finance.data.evidence_ledger import record as ledger_record

    from domains.finance.commodity_registry import get_metals_dev

    # 1) Try FRED when this commodity has a series id
    try:
        from domains.finance.data_sources.fred_commodity import fetch_commodity_history_from_fred

        fred_result = fetch_commodity_history_from_fred(
            topic, start=start_str, end=end_str, store=store
        )
        if fred_result.success and fred_result.data:
            obs = fred_result.data
            dates = [o.get("date") for o in obs if o.get("date")]
            ledger_record(
                report_id=report_id,
                source_type=f"{topic}_price",
                source_id="fred",
                evidence_data={
                    "status": "ok",
                    "observations_count": len(obs),
                    "date_range": {
                        "start": min(dates) if dates else None,
                        "end": max(dates) if dates else None,
                    },
                    "unit": obs[0].get("unit", "") if obs else "",
                    "description": f"{topic} prices via FRED",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.info("Commodity fetcher: %s via FRED (%d observations)", topic, len(obs))
            return {"fred": obs}
    except Exception as e:
        logger.debug("Commodity fetcher FRED flow failed for %s: %s", topic, e, exc_info=True)

    # 2) Fallback: metals.dev (precious metals only)
    if not get_metals_dev(topic):
        try:
            ledger_record(
                report_id=report_id,
                source_type=f"{topic}_price",
                source_id=f"unavailable_{topic}",
                evidence_data={
                    "status": "unavailable",
                    "observations_count": 0,
                    "description": f"{topic}: FRED returned no data or is not configured (oil/gas use FRED only)",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass
        logger.info("Commodity fetcher: %s unavailable (FRED only / no metals.dev)", topic)
        return {
            f"stub_{topic}": [],
            "unavailable": True,
            "message": "FRED unavailable or returned no data for this commodity.",
        }

    try:
        from domains.finance.data_sources.metals_dev import fetch_timeseries

        res = fetch_timeseries(start_str, end_str, metal=topic)
        obs = res.data or [] if isinstance(res, DataResult) and res.success else []
        status = "ok" if (isinstance(res, DataResult) and res.success) else "error"
        dates = [o.get("date") for o in obs if o.get("date")]
        evidence = {
            "status": status,
            "observations_count": len(obs),
            "date_range": {
                "start": min(dates) if dates else None,
                "end": max(dates) if dates else None,
            },
            "unit": obs[0].get("unit", "") if obs else "",
            "description": f"{topic} prices via metals.dev (fallback)",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(res, DataResult) and not res.success:
            evidence["error_type"] = res.error_type
            evidence["error"] = res.error
        ledger_record(
            report_id=report_id,
            source_type=f"{topic}_price",
            source_id="metals_dev",
            evidence_data=evidence,
        )
        logger.info(
            "Commodity fetcher: %s via metals.dev (%d observations, status=%s)",
            topic,
            len(obs),
            status,
        )
        return {"metals_dev": obs}
    except Exception as e:
        logger.debug("Commodity fetcher metals.dev flow failed: %s", e, exc_info=True)

    # 3) Both sources failed: return explicit unavailable so callers can handle
    try:
        ledger_record(
            report_id=report_id,
            source_type=f"{topic}_price",
            source_id=f"unavailable_{topic}",
            evidence_data={
                "status": "unavailable",
                "observations_count": 0,
                "description": f"{topic} collection requested; FRED and metals.dev both unavailable",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass
    logger.info("Commodity fetcher: %s unavailable (FRED and metals.dev failed)", topic)
    return {
        f"stub_{topic}": [],
        "unavailable": True,
        "message": "FRED and metals.dev unavailable; no commodity data returned.",
    }
