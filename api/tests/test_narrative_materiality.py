"""Unit tests for narrative finisher evidence materiality gate."""

from __future__ import annotations

from services.storyline_narrative_finisher_service import (
    StorylineFinisherBundle,
    build_finisher_prompt,
)
from services.storyline_narrative_materiality import (
    _classify_delta,
    _hash_parts,
    classify_narrative_materiality,
    material_article_delta_threshold,
    narrow_debt_drain_enabled,
    narrow_debt_min_age_hours,
    narrow_debt_per_domain_limit,
)


def _parts(
    *,
    articles: int = 10,
    article_ids_fp: str = "ids-a",
    fact_count: int = 5,
    fact_max_id: int = 100,
    chrono_count: int = 3,
    chrono_max_id: int = 50,
    prompt_version: str = "storyline_walkthrough.v1",
) -> dict:
    return {
        "prompt_version": prompt_version,
        "article_count": articles,
        "article_ids_fp": article_ids_fp,
        "fact_count": fact_count,
        "fact_max_id": fact_max_id,
        "chrono_count": chrono_count,
        "chrono_max_id": chrono_max_id,
    }


def test_hash_parts_stable():
    a = _hash_parts(_parts())
    b = _hash_parts(_parts())
    assert a == b
    assert len(a) == 32
    assert _hash_parts(_parts(fact_max_id=101)) != a


def test_classify_unchanged_on_fingerprint_match():
    assert (
        _classify_delta(_parts(), _parts(), fingerprint_match=True) == "unchanged"
    )


def test_classify_material_on_fact_change():
    prior = _parts()
    curr = _parts(fact_count=6)
    assert _classify_delta(prior, curr, fingerprint_match=False) == "material"
    curr2 = _parts(fact_max_id=101)
    assert _classify_delta(prior, curr2, fingerprint_match=False) == "material"


def test_classify_material_on_prompt_version_change():
    prior = _parts()
    curr = _parts(prompt_version="storyline_walkthrough.v2")
    assert _classify_delta(prior, curr, fingerprint_match=False) == "material"


def test_classify_narrow_on_single_article_drip(monkeypatch):
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA", "2")
    prior = _parts(articles=10, article_ids_fp="ids-a")
    curr = _parts(articles=11, article_ids_fp="ids-b")
    assert _classify_delta(prior, curr, fingerprint_match=False) == "narrow"


def test_classify_material_on_article_delta_threshold(monkeypatch):
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA", "2")
    prior = _parts(articles=10, article_ids_fp="ids-a")
    curr = _parts(articles=12, article_ids_fp="ids-c")
    assert _classify_delta(prior, curr, fingerprint_match=False) == "material"


def test_classify_narrow_on_chrono_only():
    prior = _parts()
    curr = _parts(chrono_count=4, chrono_max_id=51)
    assert _classify_delta(prior, curr, fingerprint_match=False) == "narrow"


def test_classify_material_on_membership_reshuffle_same_count():
    prior = _parts(articles=10, article_ids_fp="ids-a")
    curr = _parts(articles=10, article_ids_fp="ids-z")
    assert _classify_delta(prior, curr, fingerprint_match=False) == "material"


def test_classify_material_when_no_prior_parts():
    assert _classify_delta(None, _parts(), fingerprint_match=False) == "material"


def test_material_article_delta_threshold_env(monkeypatch):
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA", "3")
    assert material_article_delta_threshold() == 3
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA", "0")
    assert material_article_delta_threshold() == 1


def test_classify_force_bypasses_gate(monkeypatch):
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIALITY_GATE", "1")

    def _fake_fp(*_a, **_k):
        return {"success": True, "fingerprint": "abc", "parts": _parts()}

    monkeypatch.setattr(
        "services.storyline_narrative_materiality.compute_narrative_evidence_fingerprint",
        _fake_fp,
    )
    out = classify_narrative_materiality("politics", 1, force=True)
    assert out["action"] == "run"
    assert out["class"] == "forced"


def test_classify_gate_disabled(monkeypatch):
    monkeypatch.setenv("NARRATIVE_FINISHER_MATERIALITY_GATE", "0")

    def _fake_fp(*_a, **_k):
        return {"success": True, "fingerprint": "abc", "parts": _parts()}

    monkeypatch.setattr(
        "services.storyline_narrative_materiality.compute_narrative_evidence_fingerprint",
        _fake_fp,
    )
    out = classify_narrative_materiality("politics", 1, force=False)
    assert out["action"] == "run"
    assert out["class"] == "gate_disabled"


def test_narrow_debt_env_helpers(monkeypatch):
    monkeypatch.setenv("NARRATIVE_NARROW_DEBT_DRAIN", "0")
    assert narrow_debt_drain_enabled() is False
    monkeypatch.setenv("NARRATIVE_NARROW_DEBT_DRAIN", "1")
    assert narrow_debt_drain_enabled() is True
    monkeypatch.setenv("NARRATIVE_NARROW_DEBT_MIN_AGE_HOURS", "12")
    assert narrow_debt_min_age_hours() == 12.0
    monkeypatch.setenv("NARRATIVE_NARROW_DEBT_PER_DOMAIN", "8")
    assert narrow_debt_per_domain_limit() == 8


def test_finisher_prompt_includes_prior_canonical_even_with_bones():
    bundle = StorylineFinisherBundle(
        domain_key="politics",
        schema_name="politics",
        storyline_id=42,
        storyline_title="Senate CR talks",
        prior_canonical="## Lede\nLeaders reopen talks.\n\n## Why it matters\nFunding cliff.",
        analysis_bones="Description:\nDraft bones only.",
        article_summaries=[{"title": "Talks resume", "summary": "Short"}],
    )
    prompt = build_finisher_prompt(bundle)
    assert "Prior canonical walkthrough" in prompt
    assert "Leaders reopen talks" in prompt
    assert "Draft bones only" in prompt
    assert "REFRESH" in prompt
    # Must not drop prior canonical when bones exist
    bones_idx = prompt.find("Prior analysis / bones")
    canon_idx = prompt.find("Prior canonical walkthrough")
    assert canon_idx >= 0 and bones_idx > canon_idx


def test_membership_enqueue_skips_when_unchanged(monkeypatch):
    from services.content_refinement_queue_service import (
        maybe_enqueue_narrative_finisher_on_membership,
    )

    monkeypatch.setenv("STORYLINE_ENQUEUE_FINISHER_ON_NEW_ARTICLE", "1")
    monkeypatch.setattr(
        "services.content_refinement_queue_service.storyline_needs_initial_master_narrative",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "services.storyline_narrative_materiality.classify_narrative_materiality",
        lambda *_a, **_k: {
            "action": "skip",
            "class": "unchanged",
            "reason": "fingerprint_match",
            "fingerprint": "x",
            "parts": {},
        },
    )
    enqueued = []

    def _enq(*_a, **_k):
        enqueued.append(True)
        return {"success": True}

    monkeypatch.setattr(
        "services.content_refinement_queue_service.enqueue_content_refinement",
        _enq,
    )
    out = maybe_enqueue_narrative_finisher_on_membership(
        "politics", 1, source="membership_admit", article_id=9
    )
    assert out.get("skipped") is True
    assert out.get("reason") == "fingerprint_match"
    assert enqueued == []


def test_membership_enqueue_on_material(monkeypatch):
    from services.content_refinement_queue_service import (
        maybe_enqueue_narrative_finisher_on_membership,
    )

    monkeypatch.setenv("STORYLINE_ENQUEUE_FINISHER_ON_NEW_ARTICLE", "1")
    monkeypatch.setattr(
        "services.content_refinement_queue_service.storyline_needs_initial_master_narrative",
        lambda *_a, **_k: False,
    )
    monkeypatch.setattr(
        "services.storyline_narrative_materiality.classify_narrative_materiality",
        lambda *_a, **_k: {
            "action": "run",
            "class": "material",
            "reason": "material_delta",
            "fingerprint": "y",
            "parts": {},
        },
    )
    calls = []

    def _enq(domain_key, storyline_id, job_type, **kwargs):
        calls.append((domain_key, storyline_id, job_type, kwargs.get("metadata")))
        return {"success": True, "queue_id": 1}

    monkeypatch.setattr(
        "services.content_refinement_queue_service.enqueue_content_refinement",
        _enq,
    )
    out = maybe_enqueue_narrative_finisher_on_membership(
        "politics", 7, source="membership_admit", article_id=3, intent="automation"
    )
    assert out.get("success") is True
    assert len(calls) == 1
    assert calls[0][0] == "politics"
    assert calls[0][1] == 7
    assert calls[0][3]["source"] == "membership_admit"
    assert calls[0][3]["article_id"] == 3


def test_membership_enqueue_disabled(monkeypatch):
    from services.content_refinement_queue_service import (
        maybe_enqueue_narrative_finisher_on_membership,
    )

    monkeypatch.setenv("STORYLINE_ENQUEUE_FINISHER_ON_NEW_ARTICLE", "0")
    out = maybe_enqueue_narrative_finisher_on_membership(
        "politics", 1, source="membership_admit"
    )
    assert out.get("skipped") is True
    assert out.get("reason") == "disabled_by_env"
