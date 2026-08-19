"""Unit tests for membership_store write choke point."""

from __future__ import annotations

from shared.membership_mode import MembershipMode
from shared.membership_store import MembershipIntent, admit


class _Cur:
    def __init__(self, row=("episode", False)):
        self.row = row
        self.executes: list[tuple] = []

    def execute(self, sql, params=None):
        self.executes.append((sql, params))

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Conn:
    def __init__(self, row=("episode", False)):
        self._cur = _Cur(row)

    def cursor(self):
        return self._cur


def test_episode_eel_failed_attach_no_bag_insert(monkeypatch):
    from shared import membership_store as store

    monkeypatch.setattr(store, "get_membership_mode", lambda: MembershipMode.EPISODE_EEL)

    def _attach(*_a, **_k):
        return 0, "no_events_for_article"

    monkeypatch.setattr(
        "shared.episode_attach_gate.attach_article_events_to_episode",
        _attach,
    )

    conn = _Conn()
    ok, reason = admit(
        conn,
        domain_key="politics",
        schema="politics",
        episode_id=1,
        article_id=2,
        intent=MembershipIntent.DISCOVERY_SEED,
        blend_score=0.5,
        added_by="test",
    )
    assert ok is False
    assert "no_events" in reason
    for sql, _params in conn.cursor().executes:
        assert "INSERT INTO" not in (sql or "").upper()


def test_container_index_rejected(monkeypatch):
    monkeypatch.setattr(
        "shared.membership_store.get_membership_mode",
        lambda: MembershipMode.EPISODE_EEL,
    )
    conn = _Conn(row=("container_index", False))
    ok, reason = admit(
        conn,
        domain_key="politics",
        schema="politics",
        episode_id=1,
        article_id=2,
        intent=MembershipIntent.API_MANUAL,
        added_by="test",
    )
    assert ok is False
    assert reason == "container_index_no_membership"
