"""Golden / regression tests for cyclospora outbreak storyline linking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.entity_resolution_service import normalize_entity_match_key
from services.storyline_automation_service import StorylineAutomationService


# Core politics article IDs assembled into storyline 3716 (Widow, Jul 2026)
CYCLOSPORA_ARTICLE_IDS = (351991, 352661, 352646, 352911, 353210, 353674)


def test_cyclospora_surface_forms_share_equivalence_bucket():
    keys = {
        normalize_entity_match_key(n, "subject")
        for n in (
            "cyclospora",
            "cyclosporiasis",
            "cyclospora outbreak",
            "cyclosporiasis outbreak",
            "Cyclospora outbreak",
        )
    }
    assert len(keys) == 1
    assert next(iter(keys)).startswith("eq:")


def test_politics_outbreak_config_allows_promote_pair():
    from services.domain_synthesis_config import get_domain_synthesis_config

    cfg = get_domain_synthesis_config("politics")
    nar = cfg.storyline_development.narrative
    assert nar.allow_promote_pair_on_outbreak is True
    assert "cyclospora" in nar.outbreak_keywords
    assert "lettuce recall" in nar.outbreak_keywords


def test_subject_specificity_blocks_kitchen_sink_attach():
    """Cyclospora article must not auto-attach to an Iran storyline with no disease overlap."""
    svc = StorylineAutomationService(domain="politics")
    cur = MagicMock()

    # First call: article subjects; second: story_entity_index; third: storyline articles; fourth: storyline row
    cur.fetchall.side_effect = [
        [("cyclospora outbreak", 578854)],  # article subjects
        [("Iran", None), ("Trump", None)],  # SEI
        [],  # storyline article entities
    ]
    cur.fetchone.return_value = (
        ["Iran", "Trump"],
        ["war", "oil"],
        "Ongoing: Iran Over Apache Helicopter Crash",
    )

    article = {"id": 353674, "title": "RFK Jr says cyclospora outbreak is under control"}
    assert svc._subject_specificity_blocks_attach(cur, 3701, article) is True


def test_subject_specificity_allows_matching_outbreak_storyline():
    svc = StorylineAutomationService(domain="politics")
    cur = MagicMock()
    cur.fetchall.side_effect = [
        [("cyclospora outbreak", 578854)],
        [("Cyclospora", 578854), ("FDA", 13540)],
        [],
    ]
    cur.fetchone.return_value = (
        ["cyclospora", "Taylor Farms", "Taco Bell"],
        ["lettuce recall"],
        "2026 Cyclospora lettuce outbreak",
    )
    article = {"id": 353674, "title": "RFK Jr says cyclospora outbreak is under control"}
    assert svc._subject_specificity_blocks_attach(cur, 3716, article) is False


def test_cyclospora_golden_article_id_set_is_stable():
    """Regression anchor: the six Guardian pieces that define this arc."""
    assert len(CYCLOSPORA_ARTICLE_IDS) == 6
    assert 353674 in CYCLOSPORA_ARTICLE_IDS  # RFK under control
    assert 352661 in CYCLOSPORA_ARTICLE_IDS  # what is cyclosporiasis
