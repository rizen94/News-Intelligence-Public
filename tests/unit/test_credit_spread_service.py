"""Unit tests for credit spread service — no live FRED/Yahoo calls."""

from __future__ import annotations

import pytest


def test_percent_to_bps():
    from domains.finance.credit_spread_service import percent_to_bps

    assert percent_to_bps(2.78) == 278.0
    assert percent_to_bps(0.76) == 76.0


def test_compute_spread_status_hy_boundaries():
    from domains.finance.credit_spread_service import compute_spread_status

    assert compute_spread_status(299, "hy") == "Normal"
    assert compute_spread_status(300, "hy") == "Elevated"
    assert compute_spread_status(449, "hy") == "Elevated"
    assert compute_spread_status(450, "hy") == "Warning"
    assert compute_spread_status(599, "hy") == "Warning"
    assert compute_spread_status(600, "hy") == "Danger"
    assert compute_spread_status(799, "hy") == "Danger"
    assert compute_spread_status(800, "hy") == "Crisis"
    assert compute_spread_status(1200, "hy") == "Crisis"


def test_compute_spread_status_ig_boundaries():
    from domains.finance.credit_spread_service import compute_spread_status

    assert compute_spread_status(99, "ig") == "Normal"
    assert compute_spread_status(100, "ig") == "Elevated"
    assert compute_spread_status(149, "ig") == "Elevated"
    assert compute_spread_status(150, "ig") == "Warning"
    assert compute_spread_status(199, "ig") == "Warning"
    assert compute_spread_status(200, "ig") == "Crisis"
    assert compute_spread_status(250, "ig") == "Crisis"


def test_fetch_recession_periods_parses_runs(monkeypatch):
    from domains.finance.credit_spread_service import fetch_recession_periods

    class FakeClient:
        def fetch_observations(self, series_id, start=None, end=None, store=False):
            assert series_id == "USREC"
            from shared.data_result import DataResult

            return DataResult.ok(
                [
                    {"date": "2020-01-01", "value": 0},
                    {"date": "2020-02-01", "value": 1},
                    {"date": "2020-03-01", "value": 1},
                    {"date": "2020-04-01", "value": 0},
                    {"date": "2020-05-01", "value": 0},
                ]
            )

    monkeypatch.setattr("domains.finance.credit_spread_service.FRED_API_KEY", "test")
    monkeypatch.setattr(
        "domains.finance.credit_spread_service.get_client", lambda: FakeClient()
    )

    periods = fetch_recession_periods("2020-01-01", "2020-05-01")
    assert periods == [{"start": "2020-02-01", "end": "2020-04-01"}]


def test_fetch_recession_periods_open_ended(monkeypatch):
    from domains.finance.credit_spread_service import fetch_recession_periods

    class FakeClient:
        def fetch_observations(self, series_id, start=None, end=None, store=False):
            from shared.data_result import DataResult

            return DataResult.ok(
                [
                    {"date": "2020-03-01", "value": 1},
                    {"date": "2020-04-01", "value": 1},
                ]
            )

    monkeypatch.setattr("domains.finance.credit_spread_service.FRED_API_KEY", "test")
    monkeypatch.setattr(
        "domains.finance.credit_spread_service.get_client", lambda: FakeClient()
    )

    periods = fetch_recession_periods("2020-03-01", "2020-04-30")
    assert periods == [{"start": "2020-03-01", "end": "2020-04-30"}]


@pytest.fixture(autouse=True)
def _fred_key(monkeypatch):
    monkeypatch.setattr("domains.finance.credit_spread_service.FRED_API_KEY", "test_key")


def test_build_fred_payload_latest_status(monkeypatch):
    from domains.finance.credit_spread_service import build_fred_credit_spread_payload

    class FakeClient:
        def fetch_observations(self, series_id, start=None, end=None, store=False):
            from shared.data_result import DataResult

            if series_id == "USREC":
                return DataResult.ok([{"date": "2024-06-01", "value": 0}])
            if series_id == "BAMLH0A0HYM2":
                return DataResult.ok(
                    [{"date": "2024-06-01", "value": 3.5}, {"date": "2024-06-02", "value": 4.0}]
                )
            if series_id == "BAMLC0A0CM":
                return DataResult.ok([{"date": "2024-06-02", "value": 1.2}])
            return DataResult.fail("unknown", "no_data")

    monkeypatch.setattr(
        "domains.finance.credit_spread_service.get_client", lambda: FakeClient()
    )

    payload = build_fred_credit_spread_payload(days=90)
    assert payload["hy_spread"][-1]["value_bps"] == 400.0
    assert payload["ig_spread"][-1]["value_bps"] == 120.0
    assert payload["latest"]["hy_status"] == "Elevated"
    assert payload["latest"]["ig_status"] == "Elevated"


def test_compute_etf_spread_bps(monkeypatch):
    from domains.finance.data_sources.yahoo_etf_yields import compute_etf_spread_bps

    yields = {"HYG": 7.2, "TLT": 4.5}

    def fake_yield(ticker):
        return yields.get(ticker.upper())

    monkeypatch.setattr(
        "domains.finance.data_sources.yahoo_etf_yields.fetch_etf_yield_pct", fake_yield
    )

    out = compute_etf_spread_bps("HYG", "TLT")
    assert out is not None
    assert out["spread_bps"] == 270.0
    assert out["status"] == "Normal"
