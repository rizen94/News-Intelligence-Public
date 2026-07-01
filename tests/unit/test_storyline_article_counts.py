"""Tests for storyline article count helpers."""

from dataclasses import dataclass, field

from shared.storyline_article_counts import distinct_article_count


@dataclass
class _Member:
    article_ids: list[int] = field(default_factory=list)


def test_distinct_article_count_ignores_stale_columns():
    members = [
        _Member(article_ids=[1, 2, 3]),
        _Member(article_ids=[3, 4]),
    ]
    assert distinct_article_count(members) == 4


def test_distinct_article_count_empty():
    assert distinct_article_count([]) == 0
