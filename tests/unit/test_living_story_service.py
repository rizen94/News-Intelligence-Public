"""Unit tests for living republish throttle + quality gates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from services import living_story_service as lss


class _SeqCur:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self._i = 0
        self.description = [("col",)]

    def execute(self, *a, **k):
        pass

    def fetchone(self):
        if self._i >= len(self._responses):
            return None
        val = self._responses[self._i]
        self._i += 1
        if isinstance(val, tuple) and val and val[0] == "__fetchall__":
            return None
        return val

    def fetchall(self):
        if self._i >= len(self._responses):
            return []
        val = self._responses[self._i]
        self._i += 1
        if isinstance(val, tuple) and val and val[0] == "__fetchall__":
            return val[1]
        return val if isinstance(val, list) else []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, responses: list):
        self._cur = _SeqCur(responses)

    def cursor(self):
        return self._cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _FakeCtx:
    def __init__(self, responses: list):
        self._responses = responses

    def __enter__(self):
        return _FakeConn(self._responses)

    def __exit__(self, *a):
        pass


def test_living_republish_not_living_allows(monkeypatch):
    monkeypatch.setattr(
        lss, "get_ui_db_connection_context", lambda: _FakeCtx([None])
    )
    ok, reason = lss.living_republish_allowed(99, 1)
    assert ok is True
    assert reason == "not_living_tracked"


def test_living_republish_blocks_over_cap(monkeypatch):
    # follow lookup
    follow = ("politics", 7, "episode", {})
    # storyline title + count over narrative HITL default (150)
    story = ("Some Story", 200)
    # articles (won't be reached if cap blocks first — but quality loads them after cap check)
    # Actually cap check happens before articles query, so second context call for articles
    # Our implementation uses one connection for storyline+articles.

    responses = [
        follow,  # first connection: follow
    ]
    # Second connection inside _living_episode_quality_ok
    quality_responses = [
        story,  # title, count
        # articles not reached
    ]

    calls = {"n": 0}

    def fake_ctx():
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCtx(responses)
        return _FakeCtx(quality_responses)

    monkeypatch.setattr(lss, "get_ui_db_connection_context", fake_ctx)
    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "politics")
    ok, reason = lss.living_republish_allowed(1, 5)
    assert ok is False
    assert "over_attach_hard_cap" in reason


def test_living_republish_blocks_kitchen_sink_title(monkeypatch):
    follow = ("politics", 7, "episode", {})
    story = ("War Amid Chaos and Diplomacy", 10)
    articles = [("a", "s", "c"), ("b", "s", "c")]

    calls = {"n": 0}

    def fake_ctx():
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCtx([follow])
        return _FakeCtx([story, ("__fetchall__", articles)])

    monkeypatch.setattr(lss, "get_ui_db_connection_context", fake_ctx)
    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "politics")
    ok, reason = lss.living_republish_allowed(1, 5)
    assert ok is False
    assert reason.startswith("kitchen_sink:")


def test_living_republish_blocks_cohesion_fail(monkeypatch):
    follow = ("politics", 7, "episode", {})
    story = ("Specific Event Title", 10)
    articles = [("a", "s", "c"), ("b", "s", "c")]

    calls = {"n": 0}

    def fake_ctx():
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCtx([follow])
        return _FakeCtx([story, ("__fetchall__", articles)])

    monkeypatch.setattr(lss, "get_ui_db_connection_context", fake_ctx)
    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "politics")
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_kitchen_sink_risk",
        lambda title, arts: (False, "ok"),
    )
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_cluster_coherence",
        lambda dk, title, arts: (False, "insufficient_entity_specificity"),
    )
    ok, reason = lss.living_republish_allowed(1, 5)
    assert ok is False
    assert reason.startswith("cohesion_fail:")


def test_living_republish_quality_pass_enough_members(monkeypatch):
    follow = ("politics", 7, "episode", {"last_republish_at": datetime.now(timezone.utc).isoformat()})
    story = ("Specific Event Title", 10)
    articles = [("a", "s", "c"), ("b", "s", "c")]

    calls = {"n": 0}

    def fake_ctx():
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCtx([follow])
        return _FakeCtx([story, ("__fetchall__", articles)])

    monkeypatch.setattr(lss, "get_ui_db_connection_context", fake_ctx)
    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "politics")
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_kitchen_sink_risk",
        lambda title, arts: (False, "ok"),
    )
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_cluster_coherence",
        lambda dk, title, arts: (True, "ok"),
    )
    monkeypatch.setattr(lss, "living_republish_min_new_members", lambda: 2)
    ok, reason = lss.living_republish_allowed(1, 3)
    assert ok is True
    assert reason == "enough_new_members"


def test_living_republish_quality_pass_then_throttle(monkeypatch):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    follow = ("politics", 7, "episode", {"last_republish_at": recent})
    story = ("Specific Event Title", 10)
    articles = [("a", "s", "c"), ("b", "s", "c")]

    calls = {"n": 0}

    def fake_ctx():
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeCtx([follow])
        return _FakeCtx([story, ("__fetchall__", articles)])

    monkeypatch.setattr(lss, "get_ui_db_connection_context", fake_ctx)
    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "politics")
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_kitchen_sink_risk",
        lambda title, arts: (False, "ok"),
    )
    monkeypatch.setattr(
        "services.storyline_coherence_guardrails.assess_cluster_coherence",
        lambda dk, title, arts: (True, "ok"),
    )
    monkeypatch.setattr(lss, "living_republish_min_new_members", lambda: 10)
    monkeypatch.setattr(lss, "living_republish_min_hours", lambda: 24)
    ok, reason = lss.living_republish_allowed(1, 1)
    assert ok is False
    assert reason.startswith("throttled_")


# Preserve existing entity-id tests from original file
def test_resolve_episode_entity_id_from_anchor_signature(monkeypatch):
    class FakeCur:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return (
                json.dumps({"identity": ["cid:42"], "supporting": []}),
                {},
            )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCur()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class FakeCtx:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "medicine")
    monkeypatch.setattr(lss, "get_ui_db_connection_context", lambda: FakeCtx())
    assert lss._resolve_episode_entity_id("medicine", 7) == 42


def test_resolve_episode_entity_id_ambiguous_returns_none(monkeypatch):
    class FakeCur:
        def execute(self, *a, **k):
            pass

        def fetchone(self):
            return (
                json.dumps({"identity": ["cid:1", "cid:2"], "supporting": []}),
                {},
            )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCur()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class FakeCtx:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(lss, "resolve_domain_schema", lambda dk: "medicine")
    monkeypatch.setattr(lss, "get_ui_db_connection_context", lambda: FakeCtx())
    assert lss._resolve_episode_entity_id("medicine", 7) is None
