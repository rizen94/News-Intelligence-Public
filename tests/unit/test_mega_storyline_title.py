"""Mega-storyline title derivation."""

from services.storyline_consolidation_service import (
    StorylineInfo,
    derive_mega_storyline_title,
)
from datetime import datetime, timezone

_NOW = datetime.now(timezone.utc)


def _child(title: str, entities: set[str] | None = None) -> StorylineInfo:
    return StorylineInfo(
        id=1,
        title=title,
        description="",
        article_count=6,
        created_at=_NOW,
        updated_at=_NOW,
        entities=entities or set(),
    )


def test_rate_roundup_cluster_not_named_apy():
    children = [
        _child(
            "Best CD rates today, May 3, 2026 (lock in up to 4.05% APY)",
            {"apy", "cd", "rates"},
        ),
        _child(
            "Best money market account rates today, May 2, 2026 (4.01% APY)",
            {"apy", "money", "market"},
        ),
    ]
    title = derive_mega_storyline_title(children)
    assert title == "Ongoing: CD & money market rate roundups"
    assert "Apy" not in title


def test_earnings_reports_mega_title_not_bare_reports():
    children = [
        _child("Apple Q2 earnings report", {"apple", "tim cook"}),
        _child("Apple supply chain earnings impact", {"apple", "foxconn"}),
        _child("Microsoft Q2 earnings beat", {"microsoft"}),
    ]
    title = derive_mega_storyline_title(children)
    assert "Apple" in title
    assert title.lower() != "ongoing: reports"
