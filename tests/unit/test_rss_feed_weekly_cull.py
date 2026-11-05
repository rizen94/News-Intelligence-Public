"""Pure selection tests for weekly RSS feed quality cull (no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "api" / "services" / "rss_feed_health_service.py"
import sys
import types

_SPEC = importlib.util.spec_from_file_location("rss_feed_health_service_under_test", _PATH)
assert _SPEC and _SPEC.loader
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _mod

# Stub config.runtime so module import does not need the full package graph.
_runtime = types.ModuleType("config.runtime")


def _env_bool(key: str, default: bool = False) -> bool:
    return default


def _env_float(key: str, default: float = 0.0) -> float:
    return float(default)


def _env_int(key: str, default: int = 0) -> int:
    return int(default)


def _env_str(key: str, default: str = "") -> str:
    return default


_runtime.env_bool = _env_bool
_runtime.env_float = _env_float
_runtime.env_int = _env_int
_runtime.env_str = _env_str
sys.modules.setdefault("config", types.ModuleType("config"))
sys.modules["config.runtime"] = _runtime
_SPEC.loader.exec_module(_mod)

FeedQualityScore = _mod.FeedQualityScore
select_weekly_cull_drops = _mod.select_weekly_cull_drops


def _score(
    feed_id: int,
    avg: float,
    *,
    n: int = 10,
    schema: str = "politics",
    name: str | None = None,
) -> FeedQualityScore:
    return FeedQualityScore(
        domain_key=schema,
        schema=schema,
        feed_id=feed_id,
        feed_name=name or f"feed-{feed_id}",
        article_count=n,
        avg_quality=avg,
    )


def test_select_drops_lowest_below_bar_capped():
    scores = [
        _score(1, 0.40),
        _score(2, 0.50),
        _score(3, 0.70),
        _score(4, 0.55),
    ]
    drops = select_weekly_cull_drops(
        scores,
        target_avg_quality=0.65,
        drops_per_review=2,
        min_articles_for_score=5,
    )
    assert [d.feed_id for d in drops] == [1, 2]


def test_select_no_drops_when_all_above_bar():
    scores = [_score(1, 0.70), _score(2, 0.80)]
    drops = select_weekly_cull_drops(
        scores,
        target_avg_quality=0.65,
        drops_per_review=2,
        min_articles_for_score=5,
    )
    assert drops == []


def test_select_ignores_under_min_articles():
    scores = [
        _score(1, 0.20, n=2),  # unscored — too few articles
        _score(2, 0.50, n=10),
        _score(3, 0.90, n=10),
    ]
    drops = select_weekly_cull_drops(
        scores,
        target_avg_quality=0.65,
        drops_per_review=2,
        min_articles_for_score=5,
    )
    assert [d.feed_id for d in drops] == [2]


def test_select_zero_drops_per_review():
    scores = [_score(1, 0.10)]
    drops = select_weekly_cull_drops(
        scores,
        target_avg_quality=0.65,
        drops_per_review=0,
        min_articles_for_score=5,
    )
    assert drops == []


def test_select_only_below_bar_not_above():
    """Feeds already at/above target are never culled even if drops budget remains."""
    scores = [
        _score(1, 0.40),
        _score(2, 0.90),
        _score(3, 0.95),
    ]
    drops = select_weekly_cull_drops(
        scores,
        target_avg_quality=0.65,
        drops_per_review=5,
        min_articles_for_score=5,
    )
    assert [d.feed_id for d in drops] == [1]
