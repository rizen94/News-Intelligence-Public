"""Event-identity-first storyline seed (politics pilot)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"


def _ensure_api_path() -> None:
    if str(_API) not in sys.path:
        sys.path.insert(0, str(_API))


def test_flag_off_by_default():
    _ensure_api_path()
    from config.settings import event_identity_storyline_seed_enabled

    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("EVENT_IDENTITY_STORYLINE_SEED", None)
        with patch(
            "services.domain_synthesis_config.get_domain_synthesis_config",
            side_effect=RuntimeError("no yaml"),
        ):
            assert event_identity_storyline_seed_enabled("politics") is False
            assert event_identity_storyline_seed_enabled("finance") is False


def test_flag_politics_only_gating():
    _ensure_api_path()
    from config.settings import (
        event_identity_storyline_seed_domains,
        event_identity_storyline_seed_enabled,
    )

    with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "politics"}):
        assert event_identity_storyline_seed_domains() == frozenset({"politics"})
        assert event_identity_storyline_seed_enabled("politics") is True
        assert event_identity_storyline_seed_enabled("finance") is False
        assert event_identity_storyline_seed_enabled("legal") is False


def test_flag_true_still_politics_only():
    _ensure_api_path()
    from config.settings import event_identity_storyline_seed_enabled

    with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "true"}):
        assert event_identity_storyline_seed_enabled("politics") is True
        assert event_identity_storyline_seed_enabled("finance") is False


def test_flag_finance_in_list_ignored():
    """This slice hard-allows only politics even if finance is listed."""
    _ensure_api_path()
    from config.settings import (
        event_identity_storyline_seed_domains,
        event_identity_storyline_seed_enabled,
    )

    with patch.dict(
        "os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "politics,finance"}
    ):
        assert event_identity_storyline_seed_domains() == frozenset({"politics"})
        assert event_identity_storyline_seed_enabled("finance") is False


def test_flag_off_values():
    _ensure_api_path()
    from config.settings import event_identity_storyline_seed_enabled

    for val in ("off", "0", "false", "no"):
        with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": val}):
            assert event_identity_storyline_seed_enabled("politics") is False


def _load_event_tracking_mod():
    """Load event_tracking_service with lightweight stubs (avoid full LLM stack)."""
    _ensure_api_path()
    sys.modules.setdefault(
        "shared.services.llm_service",
        types.SimpleNamespace(LLMService=object, ModelType=object),
    )
    sys.modules.setdefault(
        "services.commodity_event_bridge",
        types.SimpleNamespace(maybe_append_finance_domain_key=lambda *a, **k: None),
    )
    if "config.runtime" not in sys.modules:
        sys.modules["config.runtime"] = types.SimpleNamespace(
            env_bool=lambda *a, **k: False,
            env_float=lambda *a, **k: 0.0,
            env_int=lambda *a, **k: 0,
            env_pop=lambda *a, **k: None,
            env_set=lambda *a, **k: None,
            env_setdefault=lambda *a, **k: None,
            env_str=lambda name, default="": __import__("os").environ.get(name, default),
        )
    path = _API / "services" / "event_tracking_service.py"
    name = "event_tracking_seed_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_promote_skipped_when_flag_off():
    mod = _load_event_tracking_mod()
    with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "off"}):
        result = mod.promote_storylines_from_tracked_events("politics", limit=5)
    assert result["skipped_flag"] is True
    assert result["promoted"] == 0


def test_promote_finance_always_noop():
    mod = _load_event_tracking_mod()
    with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "politics"}):
        result = mod.promote_storylines_from_tracked_events("finance", limit=5)
    assert result["skipped_flag"] is True
    assert result["promoted"] == 0


class _QueuedConn:
    """Minimal connection: each cursor() drains from a shared FIFO of fetch results."""

    def __init__(self, queue: list):
        self.queue = queue
        self.commits = 0

    def cursor(self):
        conn = self

        class Cur:
            rowcount = 1

            def execute(self, sql, params=None):
                self._last_sql = sql

            def fetchall(self):
                if not conn.queue:
                    return []
                val = conn.queue.pop(0)
                if val is None:
                    return []
                return val

            def fetchone(self):
                if not conn.queue:
                    return None
                val = conn.queue.pop(0)
                if val is None:
                    return None
                if isinstance(val, list):
                    return val[0] if val else None
                return val

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Cur()

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        pass


def test_promote_when_missing_storyline(monkeypatch):
    """INSERT storyline + bind tracked_events when storyline_id is null."""
    mod = _load_event_tracking_mod()

    queue = [
        # SELECT unbound events → fetchall
        [(101, "US-Israel military strikes on Iran (March 2026)", "Brief", "")],
        # re-check storyline_id → fetchone
        None,
        # developments → fetchall (via _chronicle_context_ids)
        [([{"context_id": 11}, {"context_id": 12}, {"context_id": 13}],)],
        # article_to_context → fetchall
        [(501,), (502,), (503,)],
        # article titles → fetchall
        [
            (501, "US strikes Iran nuclear sites", "summary a"),
            (502, "Israel joins US operation", "summary b"),
            (503, "Iran responds to strikes", "summary c"),
        ],
        # unlinked ids → fetchall
        [(501,), (502,), (503,)],
        # INSERT RETURNING → fetchone
        (77,),
    ]

    conn = _QueuedConn(queue)

    monkeypatch.setattr(mod, "_event_identity_seed_enabled", lambda dk: dk == "politics")
    monkeypatch.setattr(mod, "_domain_key_to_schema", lambda dk: "politics")
    monkeypatch.setattr(mod, "_active_schema_set", lambda: frozenset({"politics"}))
    monkeypatch.setattr(mod, "_event_tracking_min_articles", lambda: 2)

    fake_db = types.ModuleType("shared.database.connection")
    fake_db.get_db_connection = lambda: conn
    sys.modules["shared.database.connection"] = fake_db

    admit_calls: list[dict] = []

    def fake_admit_batch(conn_arg, **kwargs):
        admit_calls.append(kwargs)
        return [(aid, True, "ok") for aid in kwargs.get("article_ids") or []]

    fake_ms = types.ModuleType("shared.membership_store")
    fake_ms.MembershipIntent = types.SimpleNamespace(DISCOVERY_SEED="discovery_seed")
    fake_ms.admit_batch = fake_admit_batch
    sys.modules["shared.membership_store"] = fake_ms

    fake_guard = types.ModuleType("services.storyline_coherence_guardrails")
    fake_guard.is_overly_generic_storyline_title = lambda t, d="": False
    fake_guard.assess_cluster_coherence = lambda *a, **k: (True, "ok")
    sys.modules["services.storyline_coherence_guardrails"] = fake_guard

    fake_auto = types.ModuleType("services.storyline_automation_service")

    class _Svc:
        def __init__(self, domain=None):
            pass

        def _merge_article_entities_to_storyline(self, *a, **k):
            return None

    fake_auto.StorylineAutomationService = _Svc
    sys.modules["services.storyline_automation_service"] = fake_auto

    result = mod.promote_storylines_from_tracked_events("politics", limit=10)

    assert result["promoted"] == 1, result
    assert result["articles_linked"] == 3
    assert result["skipped_flag"] is False
    assert admit_calls and admit_calls[0]["episode_id"] == 77
    assert set(admit_calls[0]["article_ids"]) == {501, 502, 503}
    assert conn.commits == 1


def test_promote_noop_when_storyline_exists(monkeypatch):
    mod = _load_event_tracking_mod()

    queue = [
        [(202, "Named Happening Event Title Here", "x", "")],
        ("politics:9",),  # re-check finds existing
    ]
    conn = _QueuedConn(queue)

    monkeypatch.setattr(mod, "_event_identity_seed_enabled", lambda dk: True)
    monkeypatch.setattr(mod, "_domain_key_to_schema", lambda dk: "politics")
    monkeypatch.setattr(mod, "_active_schema_set", lambda: frozenset({"politics"}))

    fake_db = types.ModuleType("shared.database.connection")
    fake_db.get_db_connection = lambda: conn
    sys.modules["shared.database.connection"] = fake_db

    fake_guard = types.ModuleType("services.storyline_coherence_guardrails")
    fake_guard.is_overly_generic_storyline_title = lambda t, d="": False
    fake_guard.assess_cluster_coherence = lambda *a, **k: (True, "ok")
    sys.modules["services.storyline_coherence_guardrails"] = fake_guard

    result = mod.promote_storylines_from_tracked_events("politics", limit=5)
    assert result["promoted"] == 0
    assert result["skipped_existing"] == 1


def test_promote_rejects_generic_title(monkeypatch):
    mod = _load_event_tracking_mod()

    queue = [
        [(303, "News Updates", "x", "")],
        None,  # no storyline yet
    ]
    conn = _QueuedConn(queue)

    monkeypatch.setattr(mod, "_event_identity_seed_enabled", lambda dk: True)
    monkeypatch.setattr(mod, "_domain_key_to_schema", lambda dk: "politics")
    monkeypatch.setattr(mod, "_active_schema_set", lambda: frozenset({"politics"}))

    fake_db = types.ModuleType("shared.database.connection")
    fake_db.get_db_connection = lambda: conn
    sys.modules["shared.database.connection"] = fake_db

    # Force-reject generic titles (avoid stale stub from earlier tests in sys.modules)
    fake_guard = types.ModuleType("services.storyline_coherence_guardrails")
    fake_guard.is_overly_generic_storyline_title = lambda t, d="": True
    fake_guard.assess_cluster_coherence = lambda *a, **k: (True, "ok")
    sys.modules["services.storyline_coherence_guardrails"] = fake_guard

    result = mod.promote_storylines_from_tracked_events("politics", limit=5)
    assert result["promoted"] == 0
    assert result["rejected_generic"] == 1


def test_real_guardrail_rejects_generic_news_updates():
    """Sanity: coherence guardrails treat bare 'News Updates' as generic."""
    _ensure_api_path()
    # Load by path so prior stubs in sys.modules cannot shadow
    path = _API / "services" / "storyline_coherence_guardrails.py"
    name = "guardrails_real_under_test"
    if name in sys.modules:
        del sys.modules[name]
    if "config.runtime" not in sys.modules:
        sys.modules["config.runtime"] = types.SimpleNamespace(
            env_bool=lambda *a, **k: True,
            env_float=lambda *a, **k: 0.0,
            env_int=lambda *a, **k: 0,
            env_pop=lambda *a, **k: None,
            env_set=lambda *a, **k: None,
            env_setdefault=lambda *a, **k: None,
            env_str=lambda *a, **k: a[1] if len(a) > 1 else "",
        )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    assert mod.is_overly_generic_storyline_title("News Updates", "politics") is True
    assert (
        mod.is_overly_generic_storyline_title(
            "US-Israel military strikes on Iran (March 2026)", "politics"
        )
        is False
    )


def test_assembly_wires_seed_and_discovery_skip():
    path = _API / "services" / "storyline_assembly_service.py"
    text = path.read_text(encoding="utf-8")
    assert "event_identity_seed" in text
    assert "seed_from_tracked_events" in text
    assert "event_identity_storyline_seed_enabled" in text

    _ensure_api_path()
    from config.settings import event_identity_storyline_seed_enabled

    with patch.dict("os.environ", {"EVENT_IDENTITY_STORYLINE_SEED": "politics"}):
        assert event_identity_storyline_seed_enabled("politics") is True
        assert event_identity_storyline_seed_enabled("finance") is False
