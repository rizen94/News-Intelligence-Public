"""Static backlog ↔ selection contracts (no DB)."""

from shared.backlog_selection_contracts import (
    BACKLOG_SELECTION_CONTRACTS,
    assert_backlog_contracts,
    contract_catalog,
)


def test_backlog_selection_contracts_pass():
    failures = assert_backlog_contracts()
    assert failures == [], failures


def test_contract_catalog_covers_core_phases():
    phases = {c["phase"] for c in contract_catalog()}
    assert "entity_profile_build" in phases
    assert "claim_extraction" in phases
    assert "entity_extraction" in phases
    assert "event_extraction" in phases
    assert "storyline_discovery" in phases
    assert "proactive_detection" in phases
    assert "storyline_assembly" in phases
    assert "content_refinement_queue" in phases
    assert "story_continuation" in phases
    assert len(BACKLOG_SELECTION_CONTRACTS) >= 9


def test_capacity_ledger_shape_without_db_pending():
    from services.capacity_ledger_service import compute_capacity_ledger

    ledger = compute_capacity_ledger(
        pending={
            "entity_profile_build": 100,
            "claim_extraction": 0,
            "content_refinement_queue": 8,
        }
    )
    assert ledger["budget_gpu_hours_per_day"] > 0
    assert "backlog_drain_hours" in ledger
    assert "intake_demand_hours_per_day" in ledger
    assert isinstance(ledger["by_phase_backlog"], list)
    assert ledger["backlog_drain_hours"] >= 0
