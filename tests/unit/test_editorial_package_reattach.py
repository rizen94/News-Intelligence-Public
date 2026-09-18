"""Unit tests for sticky uncouple / reattach policy."""

from __future__ import annotations

from shared.editorial_package_reattach import (
    build_suppress_metadata,
    clear_suppress_from_metadata,
    flags_warrant_suppress,
    member_excluded_from_compose,
    member_has_suppress_reattach,
    member_status_blocks_reattach,
)


def test_status_blocks_removed_and_quarantined():
    assert member_status_blocks_reattach("removed")
    assert member_status_blocks_reattach("quarantined")
    assert not member_status_blocks_reattach("active")
    assert not member_status_blocks_reattach(None)


def test_flags_warrant_suppress():
    assert flags_warrant_suppress(["unrelated"])
    assert flags_warrant_suppress(["geo_mismatch", "weak_link"])
    assert flags_warrant_suppress(None, "uncouple from package: deterministic:unrelated,geo_mismatch")
    assert not flags_warrant_suppress(["weak_link"])
    assert not flags_warrant_suppress(None, "uncouple from package: weak")


def test_build_and_clear_suppress_metadata():
    stamp = build_suppress_metadata(
        flags=["unrelated", "geo_mismatch"],
        rationale="deterministic:unrelated,geo_mismatch",
        actor="reduction_llm",
    )
    assert stamp["suppress_reattach"] is True
    assert "unrelated" in stamp["suppress_flags"]
    assert stamp["suppress_by"] == "reduction_llm"

    cleared = clear_suppress_from_metadata({**stamp, "other": 1})
    assert "suppress_reattach" not in cleared
    assert cleared["other"] == 1


def test_member_has_suppress_from_row_or_meta():
    assert member_has_suppress_reattach({"suppress_reattach": True})
    assert member_has_suppress_reattach({"metadata": {"suppress_reattach": True}, "status": "removed"})
    assert not member_has_suppress_reattach({"metadata": {}, "status": "active"})
    assert member_excluded_from_compose({"metadata": {"suppress_reattach": True}, "status": "active"})
