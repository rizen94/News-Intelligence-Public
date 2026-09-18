"""Deterministic congressional trade scoring (disclosure-dated; no LLM sizing)."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AMOUNT_NUM = re.compile(r"[\d,]+")


@lru_cache(maxsize=1)
def load_congress_trade_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parent.parent / "config" / "congress_trade_signals.yaml"
    try:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        logger.warning("congress_trade_signals.yaml load failed: %s", e)
        return {}


def normalize_side(transaction_type: str | None) -> str:
    t = (transaction_type or "").strip().lower()
    if "purchase" in t or t == "buy":
        return "buy"
    if "sale" in t or t == "sell":
        return "sell"
    return "other"


def amount_bucket(amount_range: str | None, cfg: dict[str, Any] | None = None) -> tuple[float | None, int]:
    """Return (midpoint, ordinal 0–8) from Quiver amount_range text."""
    cfg = cfg or load_congress_trade_config()
    text = amount_range or ""
    best_mid: float | None = None
    best_ord = 0
    for bucket in cfg.get("amount_buckets") or []:
        match = str(bucket.get("match") or "")
        if match and match in text:
            mid = float(bucket.get("mid") or 0)
            ord_v = int(bucket.get("ordinal") or 0)
            if ord_v >= best_ord:
                best_ord = ord_v
                best_mid = mid
    if best_ord == 0 and text:
        nums = [int(x.replace(",", "")) for x in _AMOUNT_NUM.findall(text)]
        if nums:
            best_mid = float(sum(nums) / len(nums))
            best_ord = 1
    return best_mid, best_ord


def issuer_sector(ticker: str | None, cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_congress_trade_config()
    sym = (ticker or "").strip().upper()
    sectors = cfg.get("issuer_sectors") or {}
    return str(sectors.get(sym) or "other")


def leadership_weight(bioguide_id: str | None, cfg: dict[str, Any] | None = None) -> float:
    cfg = cfg or load_congress_trade_config()
    mapping = cfg.get("leadership_bioguides") or {}
    if not bioguide_id:
        return 1.0
    try:
        return float(mapping.get(bioguide_id) or 1.0)
    except (TypeError, ValueError):
        return 1.0


def committee_sector_overlap(
    committee_names: list[str] | None,
    sector: str | None,
    cfg: dict[str, Any] | None = None,
) -> float:
    """1.0 if any committee maps to issuer sector, else 0.0."""
    cfg = cfg or load_congress_trade_config()
    sector_n = (sector or "other").strip().lower()
    if sector_n in ("", "other", "broad_market"):
        return 0.0
    cmap = cfg.get("committee_sector_map") or {}
    for name in committee_names or []:
        for needle, mapped in cmap.items():
            if needle.lower() in (name or "").lower() and str(mapped).lower() == sector_n:
                return 1.0
    return 0.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def score_enriched_trade(
    *,
    side: str,
    amount_ordinal: int,
    lag_days: int | None,
    has_bipartisan_cluster: bool,
    committee_overlap: float,
    leadership_w: float,
    disclosure_freshness_days: int | None,
    cfg: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any], bool]:
    """
    Return (signal_score, score_parts, eligible).
    Eligible when score >= min_score and lag_days <= max_lag_days (missing lag → ineligible).
    """
    cfg = cfg or load_congress_trade_config()
    scoring = cfg.get("scoring") or {}
    weights = scoring.get("weights") or {}
    side_scores = scoring.get("side_scores") or {}
    min_score = float(scoring.get("min_score") or 0.55)
    max_lag = int(scoring.get("max_lag_days") or 45)
    lag_full = float(scoring.get("lag_full_penalty_days") or max_lag)
    half_life = float(scoring.get("freshness_half_life_days") or 21)

    side_v = float(side_scores.get(side) or side_scores.get("other") or 0.15)
    size_v = _clamp01(int(amount_ordinal or 0) / 8.0)
    if lag_days is None:
        lag_v = 0.0
    else:
        lag_v = _clamp01(1.0 - (float(lag_days) / max(1.0, lag_full)))
    cluster_v = 1.0 if has_bipartisan_cluster else 0.0
    committee_v = _clamp01(committee_overlap)
    lead_v = _clamp01((float(leadership_w) - 1.0) / 0.5) if leadership_w > 1.0 else 0.0
    if disclosure_freshness_days is None:
        fresh_v = 0.5
    else:
        # Exponential decay: newer disclosures score higher
        fresh_v = _clamp01(math.exp(-float(disclosure_freshness_days) / max(1.0, half_life)))

    parts = {
        "side": side_v,
        "size": size_v,
        "lag": lag_v,
        "bipartisan_cluster": cluster_v,
        "committee_sector": committee_v,
        "leadership": lead_v,
        "freshness": fresh_v,
    }
    score = 0.0
    for key, val in parts.items():
        w = float(weights.get(key) or 0.0)
        score += w * float(val)
    score = _clamp01(score)

    lag_ok = lag_days is not None and int(lag_days) <= max_lag
    eligible = bool(score >= min_score and lag_ok)
    parts["weights"] = {k: float(weights.get(k) or 0.0) for k in parts if k != "weights"}
    parts["min_score"] = min_score
    parts["max_lag_days"] = max_lag
    parts["lag_ok"] = lag_ok
    return score, parts, eligible


def lag_days(traded: date | None, filed: date | None) -> int | None:
    if not traded or not filed:
        return None
    return max(0, (filed - traded).days)


def freshness_days(filed: date | None, *, today: date | None = None) -> int | None:
    if not filed:
        return None
    today = today or datetime.now(timezone.utc).date()
    return max(0, (today - filed).days)
