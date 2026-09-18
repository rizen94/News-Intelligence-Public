"""Unit tests for graph pattern refuse ledger and sticky upsert behavior."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
_GQ_PATH = _ROOT / "api" / "services" / "graph_connection_queue_service.py"
_PROC_PATH = _ROOT / "api" / "services" / "graph_connection_processor_service.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Stub services package so processor's lazy import does not load services/__init__.py.
if "services" not in sys.modules:
    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = [str(_ROOT / "api" / "services")]  # type: ignore[attr-defined]
    sys.modules["services"] = services_pkg

gq = _load("services.graph_connection_queue_service", _GQ_PATH)
proc = _load("services.graph_connection_processor_service", _PROC_PATH)


def test_endpoint_key_from_endpoints_entity_pair():
    ek = gq.endpoint_key_from_endpoints("politics", {"entity_ids": [22, 10]})
    assert ek == "entity|politics|10|22"


def test_upsert_skips_when_refused():
    with patch.object(gq, "is_pattern_refused", return_value=True):
        pid = gq.upsert_graph_connection_proposal(
            dedupe_key="merge|entity|politics|10|22",
            proposal_kind="merge",
            domain_key="politics",
            confidence=0.7,
            source="test",
            endpoints={"domain_key": "politics", "entity_ids": [10, 22]},
        )
    assert pid is None


def test_upsert_sticky_reject_does_not_reopen_without_flag():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.return_value = (99, "rejected")

    with patch.object(gq, "is_pattern_refused", return_value=False), patch(
        "shared.database.connection.get_db_connection",
        return_value=mock_conn,
    ):
        pid = gq.upsert_graph_connection_proposal(
            dedupe_key="merge|entity|politics|10|22",
            proposal_kind="merge",
            domain_key="politics",
            confidence=0.9,
            source="test",
            endpoints={"domain_key": "politics", "entity_ids": [10, 22]},
            reopen=False,
        )
    assert pid == 99
    executed = " ".join(str(c) for c in mock_cur.execute.call_args_list)
    assert "INSERT INTO intelligence.graph_connection_proposals" not in executed


def test_processor_leaves_t2_entity_merge_pending():
    rows = [
        {
            "id": 1,
            "proposal_kind": "merge",
            "confidence": 0.65,
            "domain_key": "politics",
            "endpoints": {"entity_ids": [10, 22]},
            "evidence": {"keep_canonical_id": 10, "merge_canonical_id": 22},
        }
    ]
    marked: list = []

    def _mark(pid, status, note=None):
        marked.append((pid, status, note))
        return True

    consol = MagicMock()
    consol_mod = types.ModuleType("services.storyline_consolidation_service")
    consol_mod.MERGE_SIMILARITY_THRESHOLD = 0.7
    consol_mod.get_consolidation_service = MagicMock(return_value=consol)
    sys.modules["services.storyline_consolidation_service"] = consol_mod

    with patch.object(gq, "fetch_pending_proposals", return_value=rows), patch.object(
        gq, "mark_proposal_resolved", side_effect=_mark
    ), patch.object(gq, "insert_graph_connection_link_pair", return_value=True):
        stats = proc.process_graph_connection_proposals_batch(limit=10)

    assert stats.get("left_pending_editorial") == 1
    assert marked == []
