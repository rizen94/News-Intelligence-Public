"""Finance catchup signal gate — skip no-feed historical UIE stamp mountain."""

from services.chronological_events_catchup_service import _finance_signal_gate_sql


def test_finance_signal_gate_only_on_finance_schema():
    assert _finance_signal_gate_sql("politics") == ""
    assert _finance_signal_gate_sql("medicine") == ""
    gate = _finance_signal_gate_sql("finance")
    assert "feed_id IS NOT NULL" in gate
    assert "finance.storyline_articles" in gate
    assert "published_at >=" in gate
