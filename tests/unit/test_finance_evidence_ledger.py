"""
Unit tests for finance evidence ledger (SQLite).
"""

import pytest


@pytest.fixture(autouse=True)
def _finance_ledger_db(monkeypatch, tmp_path):
    db = tmp_path / "test_ledger.db"
    monkeypatch.setattr("domains.finance.data.evidence_ledger.LEDGER_DB", db)


def test_ledger_record_and_get():
    from domains.finance.data.evidence_ledger import record, get_by_report

    rowid = record(
        report_id="test_rpt_1",
        source_type="gold_price",
        source_id="freegoldapi",
        evidence_data={"observations_count": 5, "unit": "USD/oz"},
    )
    assert rowid > 0

    entries = get_by_report("test_rpt_1")
    assert len(entries) == 1
    assert entries[0]["source_type"] == "gold_price"
    assert entries[0]["source_id"] == "freegoldapi"
    assert entries[0]["evidence_data"]["observations_count"] == 5


def test_ledger_list_entries():
    from domains.finance.data.evidence_ledger import record, list_entries

    record("r1", "orchestrator_refresh", "gold", {"status": "success"})
    record("r2", "orchestrator_refresh", "edgar", {"status": "success"})
    record("r3", "orchestrator_refresh", "gold", {"status": "error", "error": "timeout"})

    data = list_entries(limit=10)
    assert data["total"] == 3
    assert len(data["entries"]) == 3

    gold_only = list_entries(source_id="gold")
    assert gold_only["total"] == 2
    assert all(e["source_id"] == "gold" for e in gold_only["entries"])


def test_ledger_get_recent_by_source():
    from domains.finance.data.evidence_ledger import record, get_recent_by_source

    record("r1", "orchestrator_refresh", "gold", {"status": "success"})
    record("r2", "orchestrator_refresh", "gold", {"status": "error", "error": "network"})

    recent = get_recent_by_source(limit_per_source=5)
    assert "gold" in recent
    assert len(recent["gold"]) >= 1
    assert recent["gold"][0]["status"] in ("success", "error")
