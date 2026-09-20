"""Tests for remote phase worker ownership (Widow vs PopOS)."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clear_remote_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "REMOTE_PHASE_WORKER_OWNED_PHASES",
        "REMOTE_PHASE_WORKER_ENABLED",
        "WORKER_EXECUTION_HOST",
        "WORKER_PHASES",
    ):
        monkeypatch.delenv(key, raising=False)


def test_remote_owned_empty_by_default() -> None:
    from shared.remote_phase_worker import phase_owned_by_remote_worker, remote_owned_phases

    assert remote_owned_phases() == frozenset()
    assert not phase_owned_by_remote_worker("unified_intake_extraction")


def test_remote_enabled_defaults_to_uie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMOTE_PHASE_WORKER_ENABLED", "true")
    from shared.remote_phase_worker import phase_owned_by_remote_worker, remote_owned_phases

    assert remote_owned_phases() == frozenset({"unified_intake_extraction"})
    assert phase_owned_by_remote_worker("unified_intake_extraction")
    assert not phase_owned_by_remote_worker("collection_cycle")


def test_remote_owned_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "REMOTE_PHASE_WORKER_OWNED_PHASES",
        "unified_intake_extraction,claim_extraction",
    )
    from shared.remote_phase_worker import remote_owned_phases

    assert remote_owned_phases() == frozenset(
        {"unified_intake_extraction", "claim_extraction"}
    )


def test_worker_process_not_owned_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_EXECUTION_HOST", "popos")
    monkeypatch.setenv("REMOTE_PHASE_WORKER_OWNED_PHASES", "unified_intake_extraction")
    from shared.remote_phase_worker import (
        is_remote_phase_worker_process,
        phase_owned_by_remote_worker,
        worker_phases,
    )

    assert is_remote_phase_worker_process()
    assert worker_phases() == frozenset({"unified_intake_extraction"})
    # On the worker host, ownership gate must not skip drains.
    assert not phase_owned_by_remote_worker("unified_intake_extraction")


def test_phase_owned_gate_matches_controller_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Controller _phase_eligible must call phase_owned_by_remote_worker; assert the gate itself."""
    monkeypatch.setenv("REMOTE_PHASE_WORKER_ENABLED", "true")
    from shared.remote_phase_worker import phase_owned_by_remote_worker

    assert phase_owned_by_remote_worker("unified_intake_extraction")
    assert not phase_owned_by_remote_worker("collection_cycle")


def test_supported_phases_subset_of_drainable() -> None:
    """Every PopOS allowlisted phase must have a drain_phase callable."""
    from shared.phase_drain_dispatch import DRAINABLE_PHASES
    from shared.remote_phase_worker import (
        POPOS_WORKER_EXPAND_PHASES,
        POPOS_WORKER_SUPPORTED_PHASES,
        phase_supported_by_popos_worker,
    )

    assert POPOS_WORKER_SUPPORTED_PHASES <= DRAINABLE_PHASES
    assert frozenset(POPOS_WORKER_EXPAND_PHASES) == POPOS_WORKER_SUPPORTED_PHASES
    for phase in POPOS_WORKER_SUPPORTED_PHASES:
        assert phase_supported_by_popos_worker(phase)


def test_unsupported_phase_not_allowlisted() -> None:
    from shared.remote_phase_worker import phase_supported_by_popos_worker

    assert not phase_supported_by_popos_worker("storyline_synthesis")
    assert not phase_supported_by_popos_worker("document_processing")
    assert not phase_supported_by_popos_worker("mention_resolution")
