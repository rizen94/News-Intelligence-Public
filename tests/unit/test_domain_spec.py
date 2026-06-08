"""Unit tests for domain onboarding JSON specs."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared.domain_spec import DomainSpec
from shared.domain_silo_contract import SILO_CORE_TABLES, SILO_CRITICAL_TABLES

_SPECS = Path(__file__).resolve().parents[2] / "api" / "config" / "domains" / "specs"


def test_silo_contract_covers_verify_critical():
    assert "articles" in SILO_CRITICAL_TABLES
    assert len(SILO_CORE_TABLES) == 11


def test_medicine_spec_round_trip():
    path = _SPECS / "medicine.domain.json"
    if not path.is_file():
        pytest.skip("medicine.domain.json not present")
    spec = DomainSpec.from_json_file(path)
    y = yaml.safe_load(spec.render_yaml().split("\n", 1)[-1])
    assert y["domain_key"] == "medicine"
    assert y["schema_name"] == "medicine"
    assert len(y["data_sources"]["rss"]["seed_feed_urls"]) >= 5


def test_generated_sql_includes_topic_clusters():
    spec = DomainSpec(
        domain_key="test-domain",
        schema_name="test_domain",
        display_name="Test",
        database={"include_article_topic_clusters": True},
    )
    sql = spec.render_sql_migration(999)
    assert "article_topic_clusters" in sql
    assert "create_domain_table('test_domain', 'articles'" in sql


@pytest.mark.parametrize(
    "name",
    [
        p.name
        for p in _SPECS.glob("*.domain.json")
        if not p.name.startswith("_")
    ],
)
def test_all_committed_specs_validate(name: str):
    DomainSpec.from_json_file(_SPECS / name)
