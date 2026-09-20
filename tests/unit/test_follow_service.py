"""Unit tests for follow registry guards."""

from __future__ import annotations

import pytest

from services import follow_service as fs


def test_follow_rejects_living_for_container():
    with pytest.raises(ValueError, match="tier=living"):
        fs.follow("container", "politics", 1, tier="living")


def test_follow_requires_domain_for_episode(monkeypatch):
    class FakeCur:
        def execute(self, *a, **k):
            pass
        def fetchone(self):
            return None

    class FakeConn:
        def cursor(self):
            return FakeCur()
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    class FakeCtx:
        def __enter__(self):
            return FakeConn()
        def __exit__(self, *a):
            pass

    monkeypatch.setattr(fs, "get_ui_db_connection_context", lambda: FakeCtx())
    with pytest.raises(ValueError, match="domain_key required"):
        fs.follow("episode", None, 42, tier="quiet")
