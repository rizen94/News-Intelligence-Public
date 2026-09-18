"""Unit tests for editorial package attach gate."""

from shared.editorial_package_attach_gate import (
    attach_allowed,
    package_title_is_thin,
    resolve_attach_spine,
)


def test_package_title_is_thin_storyline_stub():
    assert package_title_is_thin("News", "From politics storyline 7697")
    assert not package_title_is_thin(
        "US Senate Confirms Todd Blanche as Attorney General",
        "From politics storyline 7697",
    )


def test_resolve_attach_spine_uses_storyline_when_thin():
    title, stub = resolve_attach_spine(
        "News",
        "From politics storyline 7697",
        storyline_title="US Senate Confirms Todd Blanche as Attorney General",
    )
    assert "Blanche" in title


def test_attach_allowed_blocks_unrelated():
    ok, flags = attach_allowed(
        title="Lopez v. United States gun ban Lincoln",
        stub="",
        provenance={"label": "SCOTUS hears unrelated tax case", "quote": "tax regulations"},
    )
    assert not ok
    assert "theme_mismatch" in flags or "unrelated" in flags


def test_attach_allowed_passes_on_theme_overlap():
    ok, flags = attach_allowed(
        title="Diagnostics Firm Sued Over Data Breach",
        stub="",
        provenance={
            "label": "Patients sue diagnostics company over data breach",
            "quote": "lawsuit filed over exposed records",
        },
    )
    assert ok
    assert not flags
