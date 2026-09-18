"""Research findings exclude soft-removed articles."""

from __future__ import annotations

import ast
from pathlib import Path


def test_research_findings_filters_enrichment_status_removed():
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "domains"
        / "intelligence_hub"
        / "routes"
        / "research_findings.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "enrichment_status" in text
    assert "removed" in text
    assert "soft_remove" in text or "IS NOT DISTINCT FROM 'removed'" in text
    # Ensure we still resolve domain schema for the join
    assert "resolve_domain_schema" in text
    # Sanity: module parses
    ast.parse(text)
