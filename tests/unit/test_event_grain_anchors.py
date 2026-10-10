"""Event-grain anchors: CE-local actors, not whole-article entity soup."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GATE = _ROOT / "api" / "shared" / "episode_attach_gate.py"


def _load_gate():
    name = "episode_attach_gate_under_test"
    if name in sys.modules:
        return sys.modules[name]
    # Lightweight stubs so gate loads without DB / services package
    cfg = types.ModuleType("config")
    runtime = types.ModuleType("config.runtime")
    runtime.env_bool = lambda *a, **k: False
    sys.modules.setdefault("config", cfg)
    sys.modules["config.runtime"] = runtime
    spec = importlib.util.spec_from_file_location(name, _GATE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


g = _load_gate()


def test_names_from_ce_json_objects_and_strings():
    assert g._names_from_ce_json(
        [{"name": "Lindsey Graham"}, {"name": "South Carolina"}]
    ) == ["Lindsey Graham", "South Carolina"]
    assert g._names_from_ce_json(["Zelenskyy"]) == ["Zelenskyy"]
    assert g._names_from_ce_json(json.dumps([{"name": "Modi"}])) == ["Modi"]


class _FakeCursor:
    def __init__(self, rows_by_sql: dict):
        self._rows_by_sql = rows_by_sql
        self._last = None
        self.description = None

    def execute(self, sql, params=None):
        key = " ".join(sql.split())
        for needle, rows in self._rows_by_sql.items():
            if needle in key:
                self._last = rows
                return
        self._last = []

    def fetchone(self):
        if not self._last:
            return None
        return self._last[0]

    def fetchall(self):
        return list(self._last or [])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, rows_by_sql: dict):
        self._rows_by_sql = rows_by_sql

    def cursor(self):
        return _FakeCursor(self._rows_by_sql)


def test_classify_event_anchors_prefers_ce_actors_over_article_entities():
    # CE has Graham only; article_entities would also have Modi / India (liveblog bleed).
    conn = _FakeConn(
        {
            "FROM intelligence.entity_anchor_class": [],
            "FROM public.chronological_events": [
                (
                    999,  # source_article_id
                    "Lindsey Graham dies",
                    "Senator Graham of South Carolina",
                    [{"name": "Lindsey Graham"}],
                    [],
                )
            ],
            # Must not be used when CE actors present
            "FROM politics.article_entities": [
                (1, "person", "Narendra Modi"),
                (2, "person", "Lindsey Graham"),
            ],
        }
    )
    out = g.classify_event_anchors(
        conn,
        domain_key="politics",
        schema="politics",
        event_id=42,
        article_id=999,
    )
    idents = {x.lower() for x in (out.get("identity") or [])}
    assert "lindsey graham" in idents
    assert "narendra modi" not in idents


def test_classify_falls_back_to_article_entities_when_ce_empty():
    conn = _FakeConn(
        {
            "FROM intelligence.entity_anchor_class": [],
            "FROM public.chronological_events": [
                (999, "Untitled beat", "", [], []),
            ],
            "FROM politics.article_entities": [
                (None, None, "Bev Craig"),
            ],
        }
    )
    out = g.classify_event_anchors(
        conn,
        domain_key="politics",
        schema="politics",
        event_id=7,
        article_id=999,
    )
    idents = {x.lower() for x in (out.get("identity") or [])}
    assert "bev craig" in idents


class _DescCursor(_FakeCursor):
    """Cursor that exposes column names for allow_event_episode_attach."""

    def execute(self, sql, params=None):
        key = " ".join(sql.split())
        for needle, rows in self._rows_by_sql.items():
            if needle in key:
                self._last = rows
                if rows and isinstance(rows[0], dict):
                    self.description = [(k,) for k in rows[0].keys()]
                    self._last = [tuple(r.values()) for r in rows]
                else:
                    self.description = None
                return
        self._last = []
        self.description = None


class _DescConn(_FakeConn):
    def cursor(self):
        return _DescCursor(self._rows_by_sql)


def test_continuation_requires_locked_signature():
    """Unlocked soft bags must not absorb via continuation."""
    from datetime import datetime, timezone

    conn = _DescConn(
        {
            "FROM politics.storylines": [
                {
                    "id": 1,
                    "title": "Focused arc",
                    "story_kind": "event_narrative",
                    "is_mega_storyline": False,
                    "episode_state": "active",
                    "anchor_signature": {
                        "identity": ["Benjamin Netanyahu"],
                        "supporting": ["Gaza"],
                    },
                    "signature_locked_at": None,
                    "metadata": {},
                }
            ],
            "FROM intelligence.entity_anchor_class": [],
            "FROM public.chronological_events": [
                (
                    10,
                    "Netanyahu rejects plan",
                    "PM Netanyahu",
                    [{"name": "Benjamin Netanyahu"}],
                    [],
                )
            ],
            "FROM politics.article_entities": [],
        }
    )
    ok, reason, _details = g.allow_event_episode_attach(
        conn,
        domain_key="politics",
        schema="politics",
        episode_id=1,
        event_id=99,
        article_id=10,
    )
    assert ok is False
    assert reason == "signature_not_locked"

    # Same row with lock → continuation may proceed (match path).
    locked = datetime.now(timezone.utc)
    conn2 = _DescConn(
        {
            "FROM politics.storylines": [
                {
                    "id": 1,
                    "title": "Focused arc",
                    "story_kind": "event_narrative",
                    "is_mega_storyline": False,
                    "episode_state": "active",
                    "anchor_signature": {
                        "identity": ["Benjamin Netanyahu"],
                        "supporting": ["Gaza"],
                    },
                    "signature_locked_at": locked,
                    "metadata": {},
                }
            ],
            "FROM intelligence.entity_anchor_class": [],
            "FROM public.chronological_events": [
                (
                    10,
                    "Netanyahu rejects plan",
                    "PM Netanyahu",
                    [{"name": "Benjamin Netanyahu"}],
                    [],
                )
            ],
            "FROM politics.article_entities": [],
        }
    )
    ok2, reason2, details2 = g.allow_event_episode_attach(
        conn2,
        domain_key="politics",
        schema="politics",
        episode_id=1,
        event_id=99,
        article_id=10,
    )
    assert reason2 != "signature_not_locked"
    # Past the lock gate: match or thin-identity reject — not unlock
    assert details2.get("link_type") == "continuation" or reason2 in {
        "identity_too_thin",
        "continuation_needs_identity",
        "insufficient_identity",
        "insufficient_supporting",
        "no_overlap",
    }
