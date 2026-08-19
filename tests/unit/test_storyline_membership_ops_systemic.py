"""Unit tests for membership freeze, action allowlist, and SEI cleanup helpers."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_API_SERVICES = _API / "services"

sys.path.insert(0, str(_API))

sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
sys.modules.setdefault("shared.storyline_article_counts", MagicMock())
_rt = MagicMock()
_rt.env_str = lambda k, d="": d
_rt.env_bool = MagicMock(return_value=False)
_rt.env_int = MagicMock(side_effect=lambda k, d=0: int(d) if d is not None else 0)
_rt.env_float = MagicMock(side_effect=lambda k, d=0.0: float(d) if d is not None else 0.0)
sys.modules["config.runtime"] = _rt
sys.modules.setdefault("config.settings", MagicMock())


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_lock = _load(
    "storyline_membership_ops_lock",
    _API_SERVICES / "storyline_membership_ops_lock.py",
)
_membership = _load(
    "storyline_membership_review_service",
    _API_SERVICES / "storyline_membership_review_service.py",
)
sys.modules["services.storyline_membership_review_service"] = _membership
_prune = _load(
    "storyline_core_prune_service",
    _API_SERVICES / "storyline_core_prune_service.py",
)

is_membership_frozen = _lock.is_membership_frozen
membership_freeze_patch = _lock.membership_freeze_patch
MEMBERSHIP_ACTIONS_ALLOWED = _membership.MEMBERSHIP_ACTIONS_ALLOWED
_enqueue_action = _membership._enqueue_action
cleanup_sei_after_unlinks = _prune.cleanup_sei_after_unlinks
sei_diverges_from_title_anchors = _prune.sei_diverges_from_title_anchors
core_text_for_signature = _prune.core_text_for_signature


def test_membership_freeze_active_until_expiry():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    patch = membership_freeze_patch(
        "narrative_finisher", ttl_hours=2.0, now=now
    )
    frozen, reason = is_membership_frozen(patch, now=now + timedelta(minutes=30))
    assert frozen is True
    assert reason == "narrative_finisher"
    expired, _ = is_membership_frozen(patch, now=now + timedelta(hours=3))
    assert expired is False


def test_membership_freeze_missing_or_empty():
    assert is_membership_frozen({}) == (False, None)
    assert is_membership_frozen({"membership_frozen_until": ""}) == (False, None)
    assert is_membership_frozen(None) == (False, None)


def test_membership_actions_allowlist_matches_check_constraint():
    assert MEMBERSHIP_ACTIONS_ALLOWED == frozenset(
        {
            "unlink",
            "demote_relevance",
            "quarantine_graph",
            "demote_entity",
            "unlink_tracked_event",
        }
    )
    assert "trim_narrative_chunk" not in MEMBERSHIP_ACTIONS_ALLOWED
    assert "detach_chronological_event" not in MEMBERSHIP_ACTIONS_ALLOWED


def test_enqueue_action_skips_unsupported_without_db_insert():
    cur = MagicMock()
    result = _enqueue_action(
        cur,
        domain_key="politics",
        storyline_id=3570,
        action="trim_narrative_chunk",
        fit_score=None,
        rationale="should never insert",
        status="pending",
        metadata={"chunk_excerpt": "Global Update blah"},
    )
    assert result is None
    cur.execute.assert_not_called()


def test_enqueue_action_uses_savepoint_for_allowed():
    cur = MagicMock()
    # pending dedup miss, then insert returning id
    cur.fetchone.side_effect = [None, (42,)]
    result = _enqueue_action(
        cur,
        domain_key="politics",
        storyline_id=1,
        action="unlink",
        fit_score=0.1,
        rationale="dissimilar",
        article_id=99,
        status="pending",
    )
    assert result == 42
    # SAVEPOINT + SELECT + INSERT + RELEASE
    assert cur.execute.call_count >= 3
    first_sql = cur.execute.call_args_list[0][0][0]
    assert "SAVEPOINT" in first_sql


def test_sei_diverges_trump_bag_under_nepal_title():
    assert sei_diverges_from_title_anchors(
        "Nepal's Political Landscape Shifts",
        {"donald trump", "iran", "benjamin netanyahu", "congress", "hezbollah"},
    )


def test_empty_narrative_plus_polluted_sei_stays_title_sticky():
    text, polluted = core_text_for_signature(
        "Iran LIVE UPDATES: Escalation Watch",
        "",
        sei_entities={"donald trump", "ukraine", "nato", "congress"},
    )
    assert polluted is True
    assert "iran" in text.lower()
    assert "ukraine" not in text.lower()


def test_cleanup_sei_after_unlinks_deletes_orphans_and_demotes():
    cur = MagicMock()
    # 1) dropped article entity names
    # 2) DELETE rowcount
    # 3) SELECT core entities to demote
    # 4) UPDATE demote
    # Then _enqueue_action SAVEPOINT path — keep simple by stubbing enqueue
    cur.fetchall.side_effect = [
        [("donald trump",), ("ukraine",), ("iran",)],
        [("Donald Trump", True), ("Ukraine", True)],
    ]
    cur.rowcount = 2

    # Patch enqueue to no-op inside cleanup
    _membership._enqueue_action = MagicMock(return_value=1)  # type: ignore[attr-defined]

    stats = cleanup_sei_after_unlinks(
        cur,
        "politics",
        3570,
        "Iran Escalation Watch",
        [101, 102],
        domain_key="politics",
    )
    assert stats["sei_deleted"] == 2
    assert stats["sei_demoted"] >= 1
    # iran overlaps title anchor → not demoted; trump/ukraine are
    demote_calls = [
        c
        for c in cur.execute.call_args_list
        if "is_core_entity = false" in str(c)
    ]
    assert demote_calls
