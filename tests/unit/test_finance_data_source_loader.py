"""
Unit tests for dynamic data source loader (sources.yaml → registry).
"""

import pytest


def test_get_source_fred_loads(monkeypatch, tmp_path):
    """Loader instantiates fred from sources.yaml."""
    # Use real sources.yaml if it exists; else skip
    import yaml
    from config.paths import SOURCES_YAML

    if not SOURCES_YAML.exists():
        pytest.skip("sources.yaml not found")

    from domains.finance.data_sources import get_source, list_source_ids

    src = get_source("fred")
    assert src is not None
    assert hasattr(src, "fetch_observations")
    assert "fred" in list_source_ids()


def test_get_source_unknown_returns_none():
    """Unknown source id returns None."""
    from domains.finance.data_sources import get_source

    assert get_source("nonexistent_source_xyz") is None


def test_get_client_via_loader():
    """Registry get_source('fred') returns same type as get_client()."""
    from domains.finance.data_sources import get_source
    from domains.finance.data_sources.fred import get_client
    from domains.finance.data_sources.base import DataSourceBase

    src = get_source("fred")
    if src is None:
        pytest.skip("sources.yaml / fred not available")
    direct = get_client()
    assert isinstance(src, DataSourceBase)
    assert isinstance(direct, DataSourceBase)
    assert type(src) is type(direct)
