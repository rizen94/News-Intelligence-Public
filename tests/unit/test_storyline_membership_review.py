"""Unit tests for storyline membership review banding and safety."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_API = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "services"
    / "storyline_membership_review_service.py"
)

sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
sys.modules.setdefault("shared.storyline_article_counts", MagicMock())
_rt = MagicMock()
_rt.env_str = lambda k, d="": d
_rt.env_bool = MagicMock(return_value=False)
_rt.env_int = MagicMock(side_effect=lambda k, d=0: d)
_rt.env_float = MagicMock(side_effect=lambda k, d=0.0: d)
sys.modules["config.runtime"] = _rt

_spec = importlib.util.spec_from_file_location("storyline_membership_review_service", _API)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["storyline_membership_review_service"] = _mod
_spec.loader.exec_module(_mod)

compute_article_fit_score = _mod.compute_article_fit_score
decide_membership_article_action = _mod.decide_membership_article_action


def test_fit_score_high_overlap():
    score = compute_article_fit_score(
        core_tokens={"treasury", "yield", "curve"},
        core_entities={"us treasury", "federal reserve"},
        article_title="Treasury yield curve steepens after Fed remarks",
        article_entities={"us treasury", "federal reserve", "bonds"},
        relevance_score=0.9,
    )
    assert score >= 0.55


def test_fit_score_offtopic_low():
    score = compute_article_fit_score(
        core_tokens={"treasury", "yield", "curve"},
        core_entities={"us treasury", "federal reserve"},
        article_title="Local sports team wins championship",
        article_entities={"toronto maple leafs"},
        relevance_score=0.2,
    )
    assert score < 0.28


def test_decide_keep_band():
    action, _, queue_only = decide_membership_article_action(
        0.7,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=10,
        min_remain=3,
        unlinks_done=0,
        max_unlinks=25,
    )
    assert action == "keep"
    assert queue_only is False


def test_decide_demote_band():
    action, _, queue_only = decide_membership_article_action(
        0.4,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=10,
        min_remain=3,
        unlinks_done=0,
        max_unlinks=25,
    )
    assert action == "demote_relevance"
    assert queue_only is False


def test_dry_run_status_constant_in_service_source():
    """Propose-by-default: dry_run default false; review_state + dedupe present."""
    text = _API.read_text(encoding="utf-8")
    assert 'STORYLINE_MEMBERSHIP_REVIEW_DRY_RUN", "false"' in text
    assert 'STORYLINE_MEMBERSHIP_REVIEW_ENABLED", "true"' in text
    assert "membership_auto_apply" in text
    assert "membership_mega_auto_apply" in text
    assert "_mark_storyline_reviewed" in text
    assert "_membership_fingerprint_sql" in text
    assert "IS NOT DISTINCT FROM" in text  # pending dedupe



def test_decide_unlink_band():
    action, _, queue_only = decide_membership_article_action(
        0.1,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=10,
        min_remain=3,
        unlinks_done=0,
        max_unlinks=25,
    )
    assert action == "unlink"
    assert queue_only is False


def test_decide_mid_band_queues():
    action, rationale, queue_only = decide_membership_article_action(
        0.31,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=10,
        min_remain=3,
        unlinks_done=0,
        max_unlinks=25,
    )
    assert queue_only is True
    assert action in ("unlink", "demote_relevance")
    assert "mid-band" in rationale


def test_min_remaining_blocks_unlink():
    action, rationale, queue_only = decide_membership_article_action(
        0.1,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=3,
        min_remain=3,
        unlinks_done=0,
        max_unlinks=25,
    )
    assert action == "demote_relevance"
    assert queue_only is False
    assert "min_remaining" in rationale or "max_unlinks" in rationale


def test_max_unlinks_blocks_unlink():
    action, rationale, queue_only = decide_membership_article_action(
        0.05,
        keep=0.55,
        demote_floor=0.35,
        unlink_floor=0.28,
        remaining=100,
        min_remain=3,
        unlinks_done=25,
        max_unlinks=25,
    )
    assert action == "demote_relevance"
    assert queue_only is False
    assert "max_unlinks" in rationale or "min_remaining" in rationale
