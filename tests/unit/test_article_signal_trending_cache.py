"""Unit tests for cached trending cluster IDs in signal SQL."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_API = Path(__file__).resolve().parents[2] / "api" / "shared" / "article_signal_gate.py"
_spec = importlib.util.spec_from_file_location("article_signal_gate", _API)
assert _spec and _spec.loader
asg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(asg)


class TestTrendingClusterCache:
    def test_sql_uses_cached_ids_not_subquery(self, monkeypatch):
        monkeypatch.setenv("ARTICLE_SIGNAL_ENABLED", "true")
        asg.invalidate_trending_caches()
        asg._TRENDING_CLUSTER_CACHE["finance"] = (9999999999.0, {11, 22, 33})

        sql = asg.sql_article_in_trending_cluster("finance", "a")
        compact = sql.replace(" ", "").replace("\n", "")
        assert "IN(11,22,33)" in compact
        assert "GROUPBY" not in compact
        assert "topic_clusterstc" not in compact

    def test_empty_cluster_ids_is_false(self, monkeypatch):
        asg.invalidate_trending_caches()
        asg._TRENDING_CLUSTER_CACHE["politics"] = (9999999999.0, set())
        assert asg.sql_article_in_trending_cluster("politics") == "FALSE"
