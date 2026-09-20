"""Unit tests for episode attach gate (Event → Episode SSOT)."""

from __future__ import annotations

from shared.episode_attach_gate import (
    episode_container_assembly_enabled,
    parse_anchor_signature,
    signature_match,
)


def test_parse_anchor_signature_normalizes():
    sig = parse_anchor_signature(
        {"identity": ["Abbott", "cid:12", ""], "supporting": [12, "FDA"]}
    )
    assert "abbott" in sig["identity"]
    assert "cid:12" in sig["identity"]
    assert "cid:12" in sig["supporting"] or "fda" in sig["supporting"]


def test_admit_article_refuses_container_index(monkeypatch):
    """Container indexes never accept membership suggestions (v12 SSOT)."""
    from shared import episode_attach_gate as gate

    class _Cur:
        def execute(self, *a, **k):
            return None

        def fetchone(self):
            return ("container_index", False)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    monkeypatch.setattr(gate, "episode_container_assembly_enabled", lambda: True)
    ok, reason = gate.admit_article_to_episode_or_storyline(
        _Conn(),
        domain_key="politics",
        schema="politics",
        storyline_id=1,
        article_id=2,
        blend_score=0.9,
    )
    assert not ok
    assert reason == "container_index_no_membership"


def test_signature_match_identity_needs_two():
    # Single-token identity is magnet fuel — not enough for candidacy.
    ok, matched, reason = signature_match(
        {"identity": ["cid:100"], "supporting": []},
        {"identity": ["cid:100"], "supporting": [], "hub": ["scotus"]},
    )
    assert not ok and reason == "identity_too_thin"
    assert "cid:100" in matched

    ok2, matched2, reason2 = signature_match(
        {"identity": ["cid:100", "cid:200"], "supporting": []},
        {"identity": ["cid:100", "cid:200"], "supporting": [], "hub": []},
    )
    assert ok2 and reason2 == "identity_match"
    assert set(matched2) >= {"cid:100", "cid:200"}


def test_institutional_and_junk_helpers():
    from shared.episode_attach_gate import _looks_institutional, _looks_junk_identity

    assert _looks_institutional("department of justice")
    assert _looks_institutional("emergency services")
    assert not _looks_institutional("meng wanzhou")
    assert _looks_junk_identity("full name (no mention of a person's name)")
    assert not _looks_junk_identity("stefan kornelius")


def test_classify_bare_cid_supporting_person_identity():
    """Institutional org → supporting; person → identity."""
    from shared.episode_attach_gate import classify_event_anchors

    class _Cur:
        def __init__(self):
            self._sql = ""

        def execute(self, sql, params=None):
            self._sql = sql or ""

        def fetchall(self):
            if "entity_anchor_class" in self._sql:
                return []
            if "article_entities" in self._sql:
                return [
                    (99, "organization", "Department of Justice"),
                    (100, "person", "Meng Wanzhou"),
                    (101, "organization", "Some Random LLC"),
                ]
            return []

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    out = classify_event_anchors(
        _Conn(),
        domain_key="politics",
        schema="politics",
        article_id=1,
    )
    assert "meng wanzhou" in out["identity"] or "cid:100" in out["identity"]
    assert "department of justice" not in out["identity"]
    # DOJ is a politics hub_facet → hub (token may be cid or name)
    assert (
        "department of justice" in out["supporting"]
        or "cid:99" in out["supporting"]
        or "department of justice" in out["hub"]
        or "cid:99" in out["hub"]
    )


def test_signature_match_supporting_needs_two():
    ok, _, reason = signature_match(
        {"identity": [], "supporting": ["a", "b", "c"]},
        {"identity": [], "supporting": ["a"], "hub": []},
        min_supporting=2,
    )
    assert not ok and reason == "signature_mismatch"
    ok2, matched, reason2 = signature_match(
        {"identity": [], "supporting": ["a", "b", "c"]},
        {"identity": [], "supporting": ["a", "b"], "hub": []},
        min_supporting=2,
    )
    assert ok2 and reason2 == "supporting_match"
    assert len(matched) >= 2


def test_hub_only_rejected():
    ok, _, reason = signature_match(
        {"identity": ["cid:1"], "supporting": ["x"]},
        {"identity": [], "supporting": [], "hub": ["supreme court"]},
    )
    assert not ok
    assert "hub" in reason


def test_episode_container_flag_v12_feature_default(monkeypatch):
    monkeypatch.delenv("EPISODE_CONTAINER_ASSEMBLY_ENABLED", raising=False)
    monkeypatch.delenv("FEATURE_OVERRIDE_EPISODE_CONTAINER_ASSEMBLY", raising=False)
    # v12: features.yaml enables episode_container_assembly
    assert episode_container_assembly_enabled() is True


def test_episode_container_flag_env_forces_on(monkeypatch):
    monkeypatch.setenv("EPISODE_CONTAINER_ASSEMBLY_ENABLED", "true")
    assert episode_container_assembly_enabled() is True


def test_automation_auto_attach_defaults_off(monkeypatch):
    monkeypatch.delenv("STORYLINE_AUTOMATION_AUTO_ATTACH", raising=False)
    from shared.assembly_link_funnel import automation_auto_attach_enabled

    assert automation_auto_attach_enabled() is False


def test_admit_refuses_container_index(monkeypatch):
    monkeypatch.setenv("EPISODE_CONTAINER_ASSEMBLY_ENABLED", "true")

    class _Cur:
        def __init__(self):
            self.row = ("container_index", True)

        def execute(self, *_a, **_k):
            return None

        def fetchone(self):
            return self.row

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

    from shared.episode_attach_gate import admit_article_to_episode_or_storyline

    ok, reason = admit_article_to_episode_or_storyline(
        _Conn(),
        domain_key="politics",
        schema="politics",
        storyline_id=1,
        article_id=2,
        blend_score=0.9,
    )
    assert ok is False
    assert "container" in reason
