"""Unit tests for event coreference (soft band, hard merge, chain collapse)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _load_dedup():
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "event_deduplication_service.py"
    )
    spec = importlib.util.spec_from_file_location("event_deduplication_service", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_soft_min_below_hard_threshold(monkeypatch):
    dedup = _load_dedup()
    monkeypatch.setenv("EVENT_DEDUP_SIMILARITY_THRESHOLD", "0.85")
    monkeypatch.setenv("EVENT_DEDUP_SOFT_MIN", "0.75")
    assert dedup._dedup_soft_min() < dedup._dedup_similarity_threshold()
    assert dedup._dedup_soft_min() == 0.75


def test_soft_band_does_not_set_canonical(monkeypatch):
    """Soft link path must not set canonical_event_id."""
    dedup = _load_dedup()
    conn = MagicMock()
    svc = dedup.EventDeduplicationService(conn)
    svc._has_cluster_col = True
    svc._has_coref_table = True
    svc.resolve_cluster_root = MagicMock(return_value=10)

    cur = MagicMock()
    conn.cursor.return_value = cur
    # UPDATE cluster + upsert link
    executed = []

    def _execute(sql, params=None):
        executed.append((sql, params))

    cur.execute.side_effect = _execute

    import asyncio

    asyncio.get_event_loop().run_until_complete(
        svc._link_soft(5, 10, score=0.80, evidence={"tier": "embedding"})
    )

    # Soft must not assign chronological_events.canonical_event_id
    for sql, params in executed:
        normalized = " ".join((sql or "").split())
        if (
            "UPDATE chronological_events" in normalized
            and "SET canonical_event_id" in normalized
        ):
            raise AssertionError("soft link must not SET chronological_events.canonical_event_id")


def test_hard_merge_sets_canonical(monkeypatch):
    dedup = _load_dedup()
    conn = MagicMock()
    svc = dedup.EventDeduplicationService(conn)
    svc._has_cluster_col = True
    svc._has_coref_table = False
    svc.resolve_cluster_root = MagicMock(return_value=10)
    svc._maybe_harvest_causal_edge = MagicMock()

    cur = MagicMock()
    conn.cursor.return_value = cur
    # key_actors fetches
    cur.fetchone.side_effect = [([{"name": "A"}],), ([{"name": "B"}],)]
    executed = []

    def _execute(sql, params=None):
        executed.append((sql, params))

    cur.execute.side_effect = _execute

    import asyncio

    asyncio.get_event_loop().run_until_complete(
        svc._merge(5, 10, match_tier="fingerprint", score=1.0)
    )

    set_canon = [
        (sql, params)
        for sql, params in executed
        if "SET canonical_event_id" in (sql or "").replace("\n", " ")
    ]
    assert set_canon, "hard merge must SET canonical_event_id"
    # First update should point member 5 at root 10
    assert any(params and 10 in params and 5 in params for _, params in set_canon)


def test_collapse_coref_chains_rewrites_to_root():
    """A→B, B→C collapses A→C."""
    dedup = _load_dedup()
    conn = MagicMock()
    svc = dedup.EventDeduplicationService(conn)
    svc._has_cluster_col = True
    svc._has_coref_table = False

    # Graph: 1→2, 2→3, 3 is root
    pointers = {1: 2, 2: 3, 3: None}

    def resolve(eid: int) -> int:
        seen = set()
        cur = eid
        while cur in pointers and pointers[cur] is not None:
            if cur in seen:
                break
            seen.add(cur)
            cur = pointers[cur]
        return cur

    svc.resolve_cluster_root = resolve

    cur = MagicMock()
    conn.cursor.return_value = cur
    # First fetchall: pairs needing collapse check
    cur.fetchall.return_value = [(1, 2), (2, 3)]
    updates = []

    def _execute(sql, params=None):
        if params and "UPDATE chronological_events" in (sql or ""):
            updates.append(params)

    cur.execute.side_effect = _execute

    n = svc._collapse_coref_chains()
    assert n >= 1
    # Event 1 should be rewritten to root 3
    assert any(params and params[0] == 3 and params[-1] == 1 for params in updates)


def test_score_fingerprint_returns_tier():
    dedup = _load_dedup()
    conn = MagicMock()
    svc = dedup.EventDeduplicationService(conn)
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (42,)
    hit = svc._score_fingerprint(1, "fp-abc")
    assert hit is not None
    assert hit["candidate_id"] == 42
    assert hit["match_tier"] == "fingerprint"
    assert hit["score"] == 1.0
