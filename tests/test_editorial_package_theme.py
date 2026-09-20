"""Unit tests for title-spine theme matching (kitchen-sink prune)."""

from __future__ import annotations

from shared.editorial_package_theme import (
    extract_case_party_tokens,
    is_theme_mismatch,
    package_spine_tokens,
    parse_case_caption_parties,
)


def test_spine_keeps_case_names_drops_court_noise():
    spine = package_spine_tokens(
        "Supreme Court Affirms Heller and Bruen in Hemani and Wolford",
        "Serial SCOTUS Second Amendment rulings",
    )
    assert "hemani" in spine
    assert "bruen" in spine
    assert "heller" in spine
    # Generic institutional tokens should not be the only spine.
    assert "court" not in spine
    assert "supreme" not in spine


def test_theme_mismatch_flags_unrelated_scotus_noise():
    title = "Supreme Court Affirms Heller and Bruen in Hemani and Wolford"
    assert is_theme_mismatch(
        "Supreme Court declines to hear Nebraska abortion clinic dispute",
        title=title,
    )
    assert not is_theme_mismatch(
        "United States v. Hemani affirms Bruen framework 9-0",
        title=title,
    )


def test_parse_case_caption_parties():
    parties = parse_case_caption_parties(
        "United States v. Hemani: Court affirms conviction under Bruen"
    )
    assert any("Hemani" in p for p in parties)
    assert any("United States" in p for p in parties)
    toks = extract_case_party_tokens("District of Columbia v. Heller")
    assert "heller" in toks
