"""
Credit spread dashboard — FRED OAS series + recession overlay + ETF yield spreads.
"""

from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from config.settings import FRED_API_KEY
from domains.finance.data_sources.fred import get_client

logger = logging.getLogger(__name__)

# FRED series (validated on FRED as of 2026-06)
FRED_HY_OAS_SERIES = "BAMLH0A0HYM2"
FRED_IG_OAS_SERIES = "BAMLC0A0CM"
FRED_RECESSION_SERIES = "USREC"

# Chart display windows (days). Historic anchors always use max available FRED span.
MAX_DISPLAY_DAYS = 365 * 40  # allow decade+ requests; FRED returns what it has
ANCHOR_LOOKBACK_DAYS = 365 * 40
FLAT_BPS_EPSILON = 1.0

SpreadKind = Literal["hy", "ig"]
SpreadStatus = Literal["Normal", "Elevated", "Warning", "Danger", "Crisis"]
DeltaDirection = Literal["widen", "narrow", "flat"]

HY_THRESHOLDS_BPS: list[tuple[float, SpreadStatus]] = [
    (300, "Normal"),
    (450, "Elevated"),
    (600, "Warning"),
    (800, "Danger"),
]

IG_THRESHOLDS_BPS: list[tuple[float, SpreadStatus]] = [
    (100, "Normal"),
    (150, "Elevated"),
    (200, "Warning"),
]

# Curated multi-decade ICE BofA OAS teaching anchors (citation constants).
# Not live-recomputed: FRED currently truncates these series to ~3y of observations.
# Sources: Trading Economics / published former-FRED ICE history (see project docs).
HISTORIC_CRISIS_REFS: dict[str, list[dict[str, Any]]] = {
    "hy": [
        {
            "id": "gfc_high",
            "label": "GFC",
            "short_label": "GFC 2182",
            "bps": 2182.0,
            "date": "2008-12-15",
            "kind": "high",
            "chart_priority": "crisis_scale",
            "source": "Trading Economics / former FRED ICE BofA HY OAS",
        },
        {
            "id": "covid_high",
            "label": "COVID",
            "short_label": "COVID 1087",
            "bps": 1087.0,
            "date": "2020-03-23",
            "kind": "high",
            "chart_priority": "crisis_scale",
            "source": "Published ICE BofA HY OAS peak (eco3min / Raven Quant)",
        },
        {
            "id": "pre_gfc_low",
            "label": "pre-GFC tight",
            "short_label": "tight 241",
            "bps": 241.0,
            "date": "2007-06",
            "kind": "low",
            "chart_priority": "always",
            "source": "Trading Economics record low (former FRED ICE history)",
        },
    ],
    "ig": [
        {
            "id": "gfc_high",
            "label": "GFC",
            "short_label": "IG GFC 656",
            "bps": 656.0,
            "date": "2008-12",
            "kind": "high",
            # Far above recent IG (~70–130 bps); only plot when crisis scale is on.
            "chart_priority": "crisis_scale",
            "source": "Trading Economics / former FRED ICE BofA IG OAS",
        },
    ],
}

HISTORIC_CRISIS_CITATION_NOTE = (
    "Crisis refs are curated published ICE BofA OAS peaks (citation constants), "
    "not live-recomputed. FRED live window for these series is ~3y."
)


def historic_crisis_refs_payload(series_key: SpreadKind) -> list[dict[str, Any]]:
    """Copy of curated crisis anchors for one OAS series."""
    return [dict(row) for row in HISTORIC_CRISIS_REFS.get(series_key, [])]


# Scannable legend for UI / API consumers. Only live-wired series + labeled futures.
INDICATOR_REFS: list[dict[str, Any]] = [
    {
        "id": "hy_oas",
        "label": "HY OAS",
        "series_id": FRED_HY_OAS_SERIES,
        "source": "FRED / ICE BofA",
        "live": True,
        "what": "Option-adjusted spread of US high-yield corporates over Treasuries.",
        "warning": "Widening → credit stress, risk-off, refinancing pressure.",
        "progress": "Narrowing / stable → relief, risk appetite, easier credit.",
        "bands": [
            {"range": "< 300 bps", "status": "Normal"},
            {"range": "300–450 bps", "status": "Elevated"},
            {"range": "450–600 bps", "status": "Warning"},
            {"range": "600–800 bps", "status": "Danger"},
            {"range": "> 800 bps", "status": "Crisis"},
        ],
    },
    {
        "id": "ig_oas",
        "label": "IG OAS",
        "series_id": FRED_IG_OAS_SERIES,
        "source": "FRED / ICE BofA",
        "live": True,
        "what": "Option-adjusted spread of US investment-grade corporates over Treasuries.",
        "warning": "Widening → IG funding stress; often leads HY in calm→stress turns.",
        "progress": "Narrowing / stable → IG credit normalising.",
        "bands": [
            {"range": "< 100 bps", "status": "Normal"},
            {"range": "100–150 bps", "status": "Elevated"},
            {"range": "150–200 bps", "status": "Warning"},
            {"range": "> 200 bps", "status": "Crisis"},
        ],
    },
    {
        "id": "usrec",
        "label": "USREC (NBER)",
        "series_id": FRED_RECESSION_SERIES,
        "source": "FRED",
        "live": True,
        "what": "Binary US recession indicator (NBER dates). Chart gray bands when active.",
        "warning": "Active (=1) → recession window; treat as stress context, not a spread.",
        "progress": "Inactive (=0) → expansion; remove recession shading.",
        "bands": [
            {"range": "0", "status": "Expansion"},
            {"range": "1", "status": "Recession"},
        ],
    },
    {
        "id": "hyg_tlt",
        "label": "HYG − TLT",
        "series_id": None,
        "source": "Yahoo / yfinance",
        "live": True,
        "what": "Daily ETF yield proxy: high-yield bond ETF minus long Treasury ETF.",
        "warning": "Widening → same directional stress signal as HY OAS (noisier).",
        "progress": "Narrowing / stable → relief vs Treasuries.",
        "bands": [
            {"range": "< 300 bps", "status": "Normal"},
            {"range": "300–450 bps", "status": "Elevated"},
            {"range": "450–600 bps", "status": "Warning"},
            {"range": "600–800 bps", "status": "Danger"},
            {"range": "> 800 bps", "status": "Crisis"},
        ],
    },
    {
        "id": "lqd_tlt",
        "label": "LQD − TLT",
        "series_id": None,
        "source": "Yahoo / yfinance",
        "live": True,
        "what": "Daily ETF yield proxy: IG corporate ETF minus long Treasury ETF.",
        "warning": "Widening → IG stress proxy (can print near-zero/negative in calm markets).",
        "progress": "Narrowing / stable → IG relief vs Treasuries.",
        "bands": [
            {"range": "< 100 bps", "status": "Normal"},
            {"range": "100–150 bps", "status": "Elevated"},
            {"range": "150–200 bps", "status": "Warning"},
            {"range": "> 200 bps", "status": "Crisis"},
        ],
    },
    {
        "id": "move",
        "label": "MOVE (future)",
        "series_id": None,
        "source": None,
        "live": False,
        "what": "ICE BofA US bond-market volatility index — not fetched yet.",
        "warning": "Rising vol → rates/credit uncertainty (when wired).",
        "progress": "Falling vol → calmer rates backdrop (when wired).",
        "bands": [],
    },
    {
        "id": "sofr",
        "label": "SOFR (future)",
        "series_id": None,
        "source": None,
        "live": False,
        "what": "Secured Overnight Financing Rate — funding backdrop; not fetched yet.",
        "warning": "Sharp rises → funding stress context (when wired).",
        "progress": "Stable/easing → calmer funding (when wired).",
        "bands": [],
    },
]


def indicator_refs_payload() -> list[dict[str, Any]]:
    """Copy of indicator legend for API responses."""
    return [dict(row) for row in INDICATOR_REFS]


def percent_to_bps(value: float) -> float:
    """FRED OAS values are percent; dashboard uses basis points."""
    return round(value * 100.0, 2)


def compute_spread_status(spread_bps: float, kind: SpreadKind) -> SpreadStatus:
    """Map spread level to interpretive status."""
    thresholds = HY_THRESHOLDS_BPS if kind == "hy" else IG_THRESHOLDS_BPS
    for limit, status in thresholds:
        if spread_bps < limit:
            return status
    return "Crisis"


def fetch_fred_spread_series(
    series_id: str,
    start: str,
    end: str,
    *,
    store: bool = True,
) -> list[dict[str, Any]]:
    """Fetch one FRED series and return [{date, value_bps}]."""
    if not FRED_API_KEY:
        return []
    client = get_client()
    result = client.fetch_observations(series_id, start=start, end=end, store=store)
    if not result.success or not result.data:
        logger.warning("FRED fetch failed for %s: %s", series_id, result.error)
        return []
    out: list[dict[str, Any]] = []
    for row in result.data:
        date = row.get("date")
        value = row.get("value")
        if not date or value is None:
            continue
        out.append({"date": date, "value_bps": percent_to_bps(float(value))})
    return out


def fetch_recession_periods(start: str, end: str) -> list[dict[str, str]]:
    """Fetch USREC and convert value=1 runs into {start, end} intervals."""
    if not FRED_API_KEY:
        return []
    client = get_client()
    result = client.fetch_observations(
        FRED_RECESSION_SERIES, start=start, end=end, store=False
    )
    if not result.success or not result.data:
        logger.warning("USREC fetch failed: %s", result.error)
        return []

    periods: list[dict[str, str]] = []
    in_recession = False
    period_start: str | None = None

    for row in result.data:
        date = row.get("date")
        value = row.get("value")
        if not date:
            continue
        try:
            active = float(value) >= 1.0
        except (TypeError, ValueError):
            active = False
        if active and not in_recession:
            in_recession = True
            period_start = date
        elif not active and in_recession and period_start:
            periods.append({"start": period_start, "end": date})
            in_recession = False
            period_start = None

    if in_recession and period_start:
        periods.append({"start": period_start, "end": end})

    return periods


def _latest_bps(observations: list[dict[str, Any]]) -> float | None:
    if not observations:
        return None
    return observations[-1].get("value_bps")


def _observation_at_lag(
    observations: list[dict[str, Any]], lag_days: int
) -> dict[str, Any] | None:
    """Last observation on or before (latest_date - lag_days)."""
    if not observations:
        return None
    try:
        end = date.fromisoformat(str(observations[-1]["date"]))
    except (TypeError, ValueError):
        return None
    target = (end - timedelta(days=lag_days)).isoformat()
    hit: dict[str, Any] | None = None
    for row in observations:
        row_date = row.get("date")
        if not row_date:
            continue
        if str(row_date) <= target:
            hit = row
        else:
            break
    return hit


def _delta_direction(latest_bps: float | None, ref_bps: float | None) -> DeltaDirection | None:
    if latest_bps is None or ref_bps is None:
        return None
    delta = latest_bps - ref_bps
    if abs(delta) < FLAT_BPS_EPSILON:
        return "flat"
    return "widen" if delta > 0 else "narrow"


def _lag_level_ref(
    observations: list[dict[str, Any]],
    latest_bps: float | None,
    lag_days: int,
    label: str,
) -> dict[str, Any] | None:
    hit = _observation_at_lag(observations, lag_days)
    if not hit or hit.get("value_bps") is None:
        return None
    ref_bps = float(hit["value_bps"])
    delta = None if latest_bps is None else round(latest_bps - ref_bps, 2)
    return {
        "label": label,
        "lag_days": lag_days,
        "date": hit.get("date"),
        "bps": ref_bps,
        "delta_bps": delta,
        "direction": _delta_direction(latest_bps, ref_bps),
    }


def _historic_extremes(
    observations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """High / low / median from the full available FRED span (anchors, not a dense plot)."""
    if not observations:
        return None
    scored = [
        (float(row["value_bps"]), row.get("date"))
        for row in observations
        if row.get("value_bps") is not None
    ]
    if not scored:
        return None
    high_bps, high_date = max(scored, key=lambda t: t[0])
    low_bps, low_date = min(scored, key=lambda t: t[0])
    values = [v for v, _ in scored]
    available_from = str(observations[0].get("date") or "")
    available_to = str(observations[-1].get("date") or "")
    try:
        span_days = (
            date.fromisoformat(available_to) - date.fromisoformat(available_from)
        ).days
    except ValueError:
        span_days = 0
    # ICE BofA OAS on FRED currently starts ~2023-09; flag when well short of a decade.
    history_limited = span_days < 365 * 8
    note = None
    if history_limited and available_from:
        note = (
            f"FRED history for this series currently starts {available_from} "
            f"(~{max(1, round(span_days / 365))}y available). "
            "High/low/median are from that span only — not a multi-decade ICE dump."
        )
    return {
        "available_from": available_from or None,
        "available_to": available_to or None,
        "observation_count": len(scored),
        "span_days": span_days,
        "history_limited": history_limited,
        "history_note": note,
        "high": {"bps": high_bps, "date": high_date},
        "low": {"bps": low_bps, "date": low_date},
        "median_bps": round(float(statistics.median(values)), 2),
    }


def build_level_refs_for_series(
    observations: list[dict[str, Any]],
    *,
    series_key: SpreadKind,
) -> dict[str, Any] | None:
    """1w / 1m deltas + FRED-window hi/lo/med + curated crisis refs for one OAS series."""
    if not observations:
        return None
    latest_bps = _latest_bps(observations)
    week = _lag_level_ref(observations, latest_bps, 7, "1w")
    month = _lag_level_ref(observations, latest_bps, 30, "1m")
    historic = _historic_extremes(observations)
    return {
        "series": series_key,
        "latest_bps": latest_bps,
        "as_of": observations[-1].get("date"),
        "week": week,
        "month": month,
        "historic": historic,
        "historic_crisis_refs": historic_crisis_refs_payload(series_key),
    }


def _slice_observations(
    observations: list[dict[str, Any]], start: str, end: str
) -> list[dict[str, Any]]:
    return [
        row
        for row in observations
        if row.get("date") and start <= str(row["date"]) <= end
    ]


def _data_window_note(
    requested_days: int,
    hy: list,
    ig: list,
    *,
    hy_historic: dict[str, Any] | None = None,
    ig_historic: dict[str, Any] | None = None,
) -> str | None:
    if not hy and not ig and requested_days > 0:
        if not FRED_API_KEY:
            return (
                "No FRED observations: FRED_API_KEY is not set on the API host. "
                "ETF view still works via yfinance when network is available."
            )
        return (
            "No FRED observations returned for HY/IG OAS. "
            "Verify FRED_API_KEY and series access (BAMLH0A0HYM2, BAMLC0A0CM)."
        )
    notes: list[str] = []
    for hist in (hy_historic, ig_historic):
        if hist and hist.get("history_note"):
            notes.append(str(hist["history_note"]))
            break
    if notes:
        return notes[0]
    return None


def build_fred_credit_spread_payload(days: int) -> dict[str, Any]:
    """Build HY/IG OAS history with recession shading + level/historic anchors.

    Chart series follow ``days`` (display window). Level refs (1w/1m + historic
    high/low/median) are computed from the full FRED-available span so anchors
    teach abnormal vs normal without dumping decades of daily points on the plot.
    """
    days = max(1, min(int(days), MAX_DISPLAY_DAYS))
    end_dt = datetime.now(timezone.utc).date()
    display_start = (end_dt - timedelta(days=days)).strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")
    anchor_start = (end_dt - timedelta(days=ANCHOR_LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    # One long fetch per series → slice for chart; reuse for anchors.
    hy_full = fetch_fred_spread_series(FRED_HY_OAS_SERIES, anchor_start, end)
    ig_full = fetch_fred_spread_series(FRED_IG_OAS_SERIES, anchor_start, end)
    hy_spread = _slice_observations(hy_full, display_start, end)
    ig_spread = _slice_observations(ig_full, display_start, end)

    # USREC has deep history; fetch for the display window (shading on the plot).
    recession_periods = fetch_recession_periods(display_start, end)

    hy_bps = _latest_bps(hy_full) if hy_full else _latest_bps(hy_spread)
    ig_bps = _latest_bps(ig_full) if ig_full else _latest_bps(ig_spread)
    latest: dict[str, Any] = {}
    if hy_bps is not None:
        latest["hy_bps"] = hy_bps
        latest["hy_status"] = compute_spread_status(hy_bps, "hy")
    if ig_bps is not None:
        latest["ig_bps"] = ig_bps
        latest["ig_status"] = compute_spread_status(ig_bps, "ig")

    hy_refs = build_level_refs_for_series(hy_full, series_key="hy")
    ig_refs = build_level_refs_for_series(ig_full, series_key="ig")
    hy_historic = (hy_refs or {}).get("historic")
    ig_historic = (ig_refs or {}).get("historic")

    return {
        "hy_spread": hy_spread,
        "ig_spread": ig_spread,
        "recession_periods": recession_periods,
        "latest": latest,
        "level_refs": {
            "hy": hy_refs,
            "ig": ig_refs,
        },
        "historic_crisis_refs": {
            "hy": historic_crisis_refs_payload("hy"),
            "ig": historic_crisis_refs_payload("ig"),
            "citation_note": HISTORIC_CRISIS_CITATION_NOTE,
        },
        "series_ids": {
            "hy_oas": FRED_HY_OAS_SERIES,
            "ig_oas": FRED_IG_OAS_SERIES,
            "recession": FRED_RECESSION_SERIES,
        },
        "days": days,
        "anchor_lookback_days": ANCHOR_LOOKBACK_DAYS,
        "data_window_note": _data_window_note(
            days,
            hy_spread,
            ig_spread,
            hy_historic=hy_historic,
            ig_historic=ig_historic,
        ),
        "indicator_refs": indicator_refs_payload(),
    }


def build_etf_credit_spread_payload() -> dict[str, Any]:
    """Build HYG-TLT and LQD-TLT ETF yield spread snapshot."""
    from domains.finance.data_sources.yahoo_etf_yields import build_etf_spread_snapshot

    payload = build_etf_spread_snapshot()
    payload["indicator_refs"] = indicator_refs_payload()
    return payload
