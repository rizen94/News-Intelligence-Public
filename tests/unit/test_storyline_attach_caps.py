"""Unit tests for chemistry storyline attach caps."""

from __future__ import annotations


def test_medicine_chemistry_cap_from_yaml():
    from shared.storyline_attach_caps import attach_hard_cap, chemistry_member_cap

    assert chemistry_member_cap("medicine") == 48
    assert attach_hard_cap("medicine") == 48


def test_politics_uses_higher_hitl_cap():
    from shared.storyline_attach_caps import attach_hard_cap

    assert attach_hard_cap("politics") >= 50


def test_oversize_needs_prune():
    from shared.storyline_attach_caps import chemistry_oversize_needs_prune

    assert chemistry_oversize_needs_prune("medicine", 650) is True
    assert chemistry_oversize_needs_prune("medicine", 20) is False
    assert chemistry_oversize_needs_prune("politics", 650) is False
