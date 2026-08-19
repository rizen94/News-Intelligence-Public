"""Unit tests for narrative Phases 2–4: cluster resolve, causal boost, contradictions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api" / "services"


def _stub_runtime():
    import os

    _rt = MagicMock()

    def _env_str(k, d=""):
        return os.environ.get(k, d)

    def _env_int(k, d=0):
        try:
            return int(os.environ.get(k, str(d)))
        except ValueError:
            return int(d) if d != "" else 0

    def _env_float(k, d=0.0):
        try:
            return float(os.environ.get(k, str(d)))
        except ValueError:
            return float(d)

    def _env_bool(k, d=False):
        v = os.environ.get(k)
        if v is None:
            return bool(d)
        return str(v).lower() in ("1", "true", "yes")

    _rt.env_str = _env_str
    _rt.env_int = _env_int
    _rt.env_float = _env_float
    _rt.env_bool = _env_bool
    sys.modules["config.runtime"] = _rt
    sys.modules.setdefault("shared.database.connection", MagicMock())
    sys.modules.setdefault(
        "shared.domain_registry",
        MagicMock(
            get_pipeline_active_domain_keys=lambda: ["politics"],
            resolve_domain_schema=lambda k: k.replace("-", "_"),
        ),
    )
    sys.modules.setdefault("shared.storyline_article_counts", MagicMock())


def _load(name: str, path: Path):
    _stub_runtime()
    # Unique module name avoids cross-test cache pollution
    mod_name = f"{name}_{path.stem}"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_canonical_event_id_follows_chain():
    dedup = _load("dedup", _API / "event_deduplication_service.py")
    conn = MagicMock()
    svc = dedup.EventDeduplicationService(conn)
    svc._has_cluster_col = True
    # 1 → canon 2, cluster None; 2 → canon None, cluster 3; 3 root
    rows = {
        1: (2, None),
        2: (None, 3),
        3: (None, 3),
    }
    cur = MagicMock()
    conn.cursor.return_value = cur

    def _execute(sql, params=None):
        eid = int(params[0]) if params else None
        cur.fetchone.return_value = rows.get(eid, (None, None))

    cur.execute.side_effect = _execute
    assert svc.resolve_cluster_root(1) == 3

    coref = _load("coref", _API / "event_coreference_service.py")
    # Patch EventDeduplicationService used inside resolve
    sys.modules["services.event_deduplication_service"] = dedup
    # Re-bind resolve to use our svc
    coref.resolve_cluster_root = lambda _c, eid: svc.resolve_cluster_root(eid)
    assert coref.resolve_canonical_event_id(conn, 1) == 3
    assert coref.resolve_canonical_event_id(conn, 3) == 3


def test_blend_link_score_causal_boost():
    emb = _load("emb", _API / "embedding_link_candidate_service.py")
    base = emb.blend_link_score(semantic=0.8, entity_jaccard=0.5)
    boosted = emb.blend_link_score(
        semantic=0.8, entity_jaccard=0.5, causal_boost=1.0
    )
    assert boosted > base
    assert boosted - base <= 0.06 + 1e-9
    assert 0.0 <= boosted <= 1.0


def test_extract_causal_predicates_from_claim():
    causal = _load("causal", _API / "causal_edges_service.py")
    hit = causal.extract_causal_predicates_from_claim(
        "Sanctions", "caused", "recession fears"
    )
    assert hit is not None
    assert hit["relation"] == "causes"
    assert hit["matched_cue"] == "caused"
    miss = causal.extract_causal_predicates_from_claim("A", "mentioned", "B")
    assert miss is None
    led = causal.extract_causal_predicates_from_claim("Vote", "led to", "protests")
    assert led and led["relation"] == "leads_to"


def test_detect_claim_contradictions():
    mem = _load("mem", _API / "storyline_membership_review_service.py")
    claims = [
        {
            "id": 1,
            "subject": "Fed",
            "predicate": "raised rates to",
            "object": "5.5 percent",
            "article_id": 10,
        },
        {
            "id": 2,
            "subject": "Fed",
            "predicate": "raised rates to",
            "object": "2.0 percent",
            "article_id": 11,
        },
        {
            "id": 3,
            "subject": "Fed",
            "predicate": "met with",
            "object": "Treasury",
            "article_id": 12,
        },
    ]
    groups = mem.detect_claim_contradictions(claims)
    assert len(groups) == 1
    assert groups[0]["reason_code"] == "claim_contradiction"
    assert set(groups[0]["article_ids"]) == {10, 11}

    # Negation mismatch
    neg = mem.detect_claim_contradictions(
        [
            {
                "subject": "Bill",
                "predicate": "passed",
                "object": "senate",
                "article_id": 1,
            },
            {
                "subject": "Bill",
                "predicate": "passed",
                "object": "not senate",
                "article_id": 2,
            },
        ]
    )
    assert len(neg) == 1


def test_temporal_confidence_decay():
    drift = _load("drift", _API / "graph_link_drift_service.py")
    fresh = drift.temporal_confidence_decay(0.8, age_days=0, half_life_days=21)
    aged = drift.temporal_confidence_decay(0.8, age_days=21, half_life_days=21)
    assert abs(fresh - 0.8) < 1e-9
    assert abs(aged - 0.4) < 1e-6
    none_age = drift.temporal_confidence_decay(0.8, age_days=None)
    assert abs(none_age - 0.76) < 1e-9


def test_narrative_eval_harness_mock_perfect():
    harness_path = _ROOT / "api" / "scripts" / "run_narrative_eval_harness.py"
    harness = _load("harness", harness_path)
    gold_path = _ROOT / "tests" / "fixtures" / "gold_narrative" / "starter_gold.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    result = harness.run_eval(gold, predictor=harness.mock_perfect_predictions)
    assert result["article_storyline"]["precision"] == 1.0
    assert result["article_storyline"]["recall"] == 1.0
    assert result["event_coreference"]["f1"] == 1.0
    empty = harness.run_eval(gold, predictor=harness.mock_empty_predictions)
    assert empty["article_storyline"]["tp"] == 0
    assert empty["article_storyline"]["fn"] > 0
