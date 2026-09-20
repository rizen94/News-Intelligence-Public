"""Unit tests for pulse movement stub helpers."""

from __future__ import annotations

from services.pulse_service import _stub_overlaps_events


def test_stub_overlap_accepts_matching_event_token():
    movement = [{"event_id": 1, "title": "FDA approves new migraine treatment"}]
    assert _stub_overlaps_events(
        "Regulators approved a new migraine treatment after clinical review.",
        movement,
    )


def test_stub_overlap_rejects_unrelated_text():
    movement = [{"event_id": 2, "title": "Congress passes budget bill"}]
    assert not _stub_overlaps_events(
        "Markets rallied on unrelated tech earnings news.",
        movement,
    )


def test_stub_overlap_requires_movement_summary():
    assert not _stub_overlaps_events("Congress passes budget bill", [])
