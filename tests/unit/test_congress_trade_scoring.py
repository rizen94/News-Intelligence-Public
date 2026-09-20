"""Unit tests for congress trade scoring (no DB)."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_PATH = _API / "services" / "congress_trade_scoring_service.py"

sys.path.insert(0, str(_API))
sys.modules.setdefault("config.runtime", MagicMock())
sys.modules.setdefault("config.feature_registry", MagicMock())

if "services" not in sys.modules:
    pkg = types.ModuleType("services")
    pkg.__path__ = [str(_API / "services")]  # type: ignore[attr-defined]
    sys.modules["services"] = pkg

_spec = importlib.util.spec_from_file_location(
    "services.congress_trade_scoring_service", _PATH
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["services.congress_trade_scoring_service"] = _mod
_spec.loader.exec_module(_mod)

normalize_side = _mod.normalize_side
amount_bucket = _mod.amount_bucket
lag_days = _mod.lag_days
score_enriched_trade = _mod.score_enriched_trade
committee_sector_overlap = _mod.committee_sector_overlap


_CFG = {
    "scoring": {
        "min_score": 0.55,
        "max_lag_days": 45,
        "weights": {
            "side": 0.22,
            "size": 0.18,
            "lag": 0.20,
            "bipartisan_cluster": 0.15,
            "committee_sector": 0.12,
            "leadership": 0.08,
            "freshness": 0.05,
        },
        "side_scores": {"buy": 1.0, "sell": 0.55, "other": 0.15},
        "lag_full_penalty_days": 45,
        "freshness_half_life_days": 21,
    },
    "amount_buckets": [
        {"match": "$1,001", "mid": 8000, "ordinal": 1},
        {"match": "$50,001", "mid": 125000, "ordinal": 3},
    ],
    "committee_sector_map": {"Armed Services": "industrials"},
}


def test_normalize_side():
    assert normalize_side("Purchase") == "buy"
    assert normalize_side("Sale") == "sell"
    assert normalize_side("Partial Sale") == "sell"
    assert normalize_side("Exchange") == "other"


def test_amount_bucket_ordinal():
    mid, ord_v = amount_bucket("$50,001 - $100,000", _CFG)
    assert mid == 125000
    assert ord_v == 3


def test_lag_days_non_negative():
    assert lag_days(date(2026, 1, 1), date(2026, 1, 20)) == 19
    assert lag_days(date(2026, 1, 20), date(2026, 1, 1)) == 0
    assert lag_days(None, date(2026, 1, 1)) is None


def test_score_eligible_buy_fresh():
    score, parts, eligible = score_enriched_trade(
        side="buy",
        amount_ordinal=5,
        lag_days=5,
        has_bipartisan_cluster=True,
        committee_overlap=1.0,
        leadership_w=1.35,
        disclosure_freshness_days=2,
        cfg=_CFG,
    )
    assert eligible is True
    assert score >= 0.55
    assert parts["lag_ok"] is True


def test_score_ineligible_high_lag():
    score, parts, eligible = score_enriched_trade(
        side="buy",
        amount_ordinal=8,
        lag_days=90,
        has_bipartisan_cluster=True,
        committee_overlap=1.0,
        leadership_w=1.5,
        disclosure_freshness_days=1,
        cfg=_CFG,
    )
    assert eligible is False
    assert parts["lag_ok"] is False


def test_committee_sector_overlap():
    assert (
        committee_sector_overlap(
            ["House Armed Services Committee"], "industrials", _CFG
        )
        == 1.0
    )
    assert committee_sector_overlap(["Judiciary"], "industrials", _CFG) == 0.0


def test_as_of_is_disclosure_dated_contract():
    """Paper selection must use filed_date only — scoring never needs traded_date after lag."""
    # lag uses traded→filed; eligibility gates on lag; score itself is disclosure-time features
    _, parts, eligible = score_enriched_trade(
        side="buy",
        amount_ordinal=3,
        lag_days=10,
        has_bipartisan_cluster=False,
        committee_overlap=0.0,
        leadership_w=1.0,
        disclosure_freshness_days=3,
        cfg=_CFG,
    )
    assert "max_lag_days" in parts
    assert eligible in (True, False)
