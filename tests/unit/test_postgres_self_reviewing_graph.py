"""Unit tests for Postgres self-reviewing graph helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API_GC = _ROOT / "api" / "services" / "graph_connection_queue_service.py"
_API_EMB = _ROOT / "api" / "services" / "embedding_link_candidate_service.py"


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    sys.modules.setdefault("shared.database.connection", MagicMock())
    sys.modules.setdefault(
        "shared.domain_registry",
        MagicMock(
            get_pipeline_active_domain_keys=lambda: ["politics"],
            resolve_domain_schema=lambda k: k.replace("-", "_"),
        ),
    )
    _rt = MagicMock()
    _rt.env_str = lambda k, d="": d
    _rt.env_int = lambda k, d=0: int(d) if d != "" else 0
    _rt.env_float = lambda k, d=0.0: float(d)
    sys.modules["config.runtime"] = _rt
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_edge_evidence_contract():
    gc = _load_module("gcq_test1", _API_GC)
    ev = gc.build_edge_evidence(
        phase="embedding_link_candidates",
        method="cosine_chunk",
        score_parts={"semantic": 0.8, "overall": 0.72},
        anchors={"article_ids": [1]},
    )
    assert ev["phase"] == "embedding_link_candidates"
    assert ev["method"] == "cosine_chunk"
    assert ev["score_parts"]["semantic"] == 0.8
    assert ev["anchors"]["article_ids"] == [1]


def test_merge_edge_evidence_lifts_legacy_keys():
    gc = _load_module("gcq_test2", _API_GC)
    merged = gc.merge_edge_evidence(
        {"semantic": 0.7, "entity": 0.4, "article_id": 99},
        phase="graph_connection_distillation",
        method="cosine_chunk",
    )
    assert merged["score_parts"]["semantic"] == 0.7
    assert merged["score_parts"]["entity"] == 0.4
    assert merged.get("article_id") == 99


def test_blend_link_score():
    emb = _load_module("emb_test1", _API_EMB)
    score = emb.blend_link_score(semantic=0.8, entity_jaccard=0.5)
    assert 0.7 <= score <= 0.85


def test_cross_domain_endpoint_kinds_differ():
    ep = {
        "left": {"domain_key": "politics", "kind": "entity", "id": 10},
        "right": {"domain_key": "finance", "kind": "entity", "id": 10},
    }
    lk = f"entity:{ep['left']['domain_key']}"
    rk = f"entity:{ep['right']['domain_key']}"
    assert lk != rk
