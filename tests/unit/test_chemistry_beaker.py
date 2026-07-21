"""Unit tests for chemistry beaker enablement + phase order."""

from __future__ import annotations

import os

from shared.chemistry_beaker import (
    POST_INTAKE_BEAKER_PHASES,
    chemistry_beaker_enabled,
    collision_sampling_enabled,
    get_post_intake_beaker_phases,
)


def test_post_intake_phase_order():
    phases = get_post_intake_beaker_phases()
    assert phases[0] == "graph_connection_distillation"
    assert "collision_sampling" in phases
    assert "protein_harden" in phases
    assert list(POST_INTAKE_BEAKER_PHASES) == phases or set(phases) <= set(
        POST_INTAKE_BEAKER_PHASES
    )


def test_master_default_enables_collision(monkeypatch):
    monkeypatch.delenv("CHEMISTRY_BEAKER_ENABLED", raising=False)
    monkeypatch.delenv("COLLISION_SAMPLING_ENABLED", raising=False)
    assert chemistry_beaker_enabled() is True
    assert collision_sampling_enabled() is True


def test_per_phase_override_disables(monkeypatch):
    monkeypatch.setenv("CHEMISTRY_BEAKER_ENABLED", "true")
    monkeypatch.setenv("COLLISION_SAMPLING_ENABLED", "false")
    assert chemistry_beaker_enabled() is True
    assert collision_sampling_enabled() is False


def test_master_off_disables_phases(monkeypatch):
    monkeypatch.setenv("CHEMISTRY_BEAKER_ENABLED", "false")
    monkeypatch.delenv("COLLISION_SAMPLING_ENABLED", raising=False)
    assert chemistry_beaker_enabled() is False
    assert collision_sampling_enabled() is False
