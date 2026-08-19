"""v12 MUST+THIN unit coverage: stakes, kernel scoring, hub denylist, phase order."""

from __future__ import annotations

from shared.act_verb_lexicon import count_act_verbs, text_has_act_verb
from shared.act_verb_kernel import score_event_row
from shared.assembly_phase_order import POST_SPINE_PHASE_ORDER, POST_SPINE_RETIRED_PHASES
from shared.hub_denylist import is_blocked_hub_name
from shared.link_scoring import auto_republish_enabled, blend_link_score
from shared.stakes_gate import evaluate_stakes_gate, manuscript_has_nut_graf, manuscript_has_walkaway


def test_hub_denylist_arxiv():
    assert is_blocked_hub_name("arXiv")
    assert is_blocked_hub_name("arxiv.org")
    assert is_blocked_hub_name("arXiv cs.LG preprint")
    assert not is_blocked_hub_name("OpenAI")


def test_act_verb_lexicon():
    assert text_has_act_verb("Court ruled against the agency")
    assert count_act_verbs("filed and settled the case") >= 2
    assert not text_has_act_verb("ambient wallpaper entity mention")
    assert text_has_act_verb("Dassault seeks a jet alternative")
    assert text_has_act_verb("Netanyahu vows no withdrawal")


def test_identity_from_claim_parties():
    body = (
        "## What's new\nX\n\n## Why this matters\nY\n\n## Timeline\nZ\n\n## What to watch\nW\n"
    )
    pkg = {
        "working_title": "Netanyahu Rejects Gaza Plan",
        "members": [
            {
                "status": "active",
                "member_type": "extracted_claim",
                "label": "netanyahu rejects plan",
                "parties": ["Netanyahu"],
                "excerpt": "Netanyahu rejects the US-led Gaza disarmament plan.",
                "provenance": {"url": "https://example.com/story", "quote": "Netanyahu rejects the plan today."},
            }
        ],
    }
    ok = evaluate_stakes_gate(pkg, body_md=body, require_sections=True)
    assert ok["checks"]["identity_actor"] is True
    assert ok["ok"] is True


def test_empty_members_do_not_inherit_title_identity():
    from shared.stakes_gate import package_has_identity_actor

    assert package_has_identity_actor(
        {"working_title": "Dassault Seeks Jet Alternative", "members": []}
    ) is False


def test_kernel_score_event_row():
    assert score_event_row("Acme filed 8-K", None, "filing") > 0
    assert score_event_row("arXiv weekly digest", None, None) == 0
    assert score_event_row("Market mood softens", None, None) == 0


def test_blend_link_score_shared():
    base = blend_link_score(semantic=0.8, entity_jaccard=0.5)
    assert 0.0 <= base <= 1.0


def test_auto_republish_default_on(monkeypatch):
    monkeypatch.delenv("NEWS_STORY_AUTO_REPUBLISH", raising=False)
    assert auto_republish_enabled() is True
    monkeypatch.setenv("NEWS_STORY_AUTO_REPUBLISH", "0")
    assert auto_republish_enabled() is False


def test_stakes_gate_sections():
    body = (
        "Lede sentence.\n\n"
        "## What's new\n"
        "Jane Doe filed suit today.\n\n"
        "## Why this matters (nut graf)\n"
        "Because X happened to Y.\n\n"
        "## Timeline\n"
        "- 2026-08-18: complaint filed\n\n"
        "walkaway: X changed the stakes for Y.\n"
    )
    assert manuscript_has_nut_graf(body)
    assert manuscript_has_walkaway(body)

    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "chronological_event",
                "label": "Jane Doe filed suit",
                "excerpt": "Jane Doe filed a complaint seeking damages.",
                "provenance": {
                    "url": "https://example.com/story",
                    "quote": "Jane Doe filed a complaint seeking damages today.",
                    "actors": ["Jane Doe"],
                },
            }
        ]
    }
    ok = evaluate_stakes_gate(pkg, body_md=body, require_sections=True)
    assert ok["ok"] is True

    thin = evaluate_stakes_gate(pkg, body_md="no sections here", require_sections=True)
    assert thin["ok"] is False
    assert thin["reason"] == "thin_no_stakes"


def test_stakes_gate_identity_from_provenance_label():
    body = (
        "## What's new\nX\n\n## Why this matters\nY\n\n## Timeline\nZ\n\n## What to watch\nW\n"
    )
    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "chronological_event",
                "label": None,
                "excerpt": "Jane Doe filed a complaint seeking damages.",
                "provenance": {
                    "label": "Trump administration ends humanitarian programme",
                    "source_url": "https://example.com/story",
                    "quote": "Jane Doe filed a complaint seeking damages today.",
                    "key_actors": ["Jane Doe"],
                },
            }
        ]
    }
    ok = evaluate_stakes_gate(pkg, body_md=body, require_sections=True)
    assert ok["ok"] is True
    assert ok["checks"]["identity_actor"] is True


def test_stakes_gate_act_verb_from_provenance_label():
    body = (
        "## What's new\nX\n\n## Why this matters\nY\n\n## Timeline\nZ\n\n## What to watch\nW\n"
    )
    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "chronological_event",
                "label": None,
                "provenance": {
                    "label": "Chipotle initiated a jalapeño recall",
                    "source_url": "https://example.com/story",
                    "quote": "Chipotle initiated an automated recall system today.",
                    "key_actors": ["Chipotle"],
                },
            }
        ]
    }
    ok = evaluate_stakes_gate(pkg, body_md=body, require_sections=True)
    assert ok["ok"] is True
    assert ok["checks"]["act_verb"] is True


def test_stakes_gate_accepts_evidence_brief_headings():
    body = (
        "## What We Know\n"
        "The court took the case.\n\n"
        "## Why this matters\n"
        "The ruling binds the agency.\n\n"
        "## Timeline\n"
        "- 2026-08-01: filing\n\n"
        "## Open Questions\n"
        "Will the stay hold?\n"
    )
    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "chronological_event",
                "label": "Jane Doe filed suit",
                "excerpt": "Jane Doe filed a complaint seeking damages.",
                "provenance": {
                    "url": "https://example.com/story",
                    "quote": "Jane Doe filed a complaint seeking damages today.",
                    "actors": ["Jane Doe"],
                },
            }
        ]
    }
    ok = evaluate_stakes_gate(pkg, body_md=body, require_sections=True)
    assert ok["ok"] is True


def test_ensure_reader_sections_fills_brief_spine():
    from shared.stakes_gate import ensure_reader_sections

    brief_body = (
        "## What We Know\nThe court took the case.\n\n"
        "## Timeline\n- 2026-08-01: filing\n\n"
        "## Supporting Evidence\nA cited excerpt.\n\n"
        "## Open Questions\nWill the stay hold?\n"
    )
    payload = {
        "working_title": "Court takes the case",
        "summary_stub": "A federal court agreed to hear the challenge.",
        "evidence_brief": {"lede": "The docket moved today.", "open_questions": ["Stay?"]},
        "members": [{"label": "Hearing set", "event_date": "2026-08-18"}],
    }
    filled = ensure_reader_sections(brief_body, payload)
    pkg = {
        "members": [
            {
                "status": "active",
                "member_type": "chronological_event",
                "label": "Jane Doe filed suit",
                "excerpt": "Jane Doe filed a complaint seeking damages.",
                "provenance": {
                    "url": "https://example.com/story",
                    "quote": "Jane Doe filed a complaint seeking damages today.",
                    "actors": ["Jane Doe"],
                },
            }
        ]
    }
    ok = evaluate_stakes_gate(pkg, body_md=filled, require_sections=True)
    assert ok["ok"] is True
    assert "## Why this matters" in filled


def test_post_spine_v12_order():
    assert "editorial_evidence_expand_pass" in POST_SPINE_PHASE_ORDER
    assert "editorial_room_loop" not in POST_SPINE_PHASE_ORDER
    assert "storyline_automation" not in POST_SPINE_PHASE_ORDER
    assert "editorial_room_loop" in POST_SPINE_RETIRED_PHASES
    assert "storyline_automation" in POST_SPINE_RETIRED_PHASES
    # evidence expand before reduction
    assert POST_SPINE_PHASE_ORDER.index("editorial_evidence_expand_pass") < POST_SPINE_PHASE_ORDER.index(
        "editorial_reduction_pass"
    )


def test_closed_thin_in_vocab():
    from shared.editorial_package_vocab import PACKAGE_STATUSES

    assert "closed_thin" in PACKAGE_STATUSES


def test_dual_write_default_off(monkeypatch):
    monkeypatch.delenv("STORYLINE_ARTICLES_DUAL_WRITE", raising=False)
    from shared.assembly_link_funnel import storyline_articles_dual_write_enabled

    assert storyline_articles_dual_write_enabled() is False
    monkeypatch.setenv("STORYLINE_ARTICLES_DUAL_WRITE", "1")
    assert storyline_articles_dual_write_enabled() is True


def test_storyline_articles_write_allowed_episode_mode(monkeypatch):
    from shared import assembly_link_funnel as funnel

    monkeypatch.setattr(funnel, "storyline_articles_dual_write_enabled", lambda: False)
    monkeypatch.setattr(
        "shared.episode_attach_gate.episode_container_assembly_enabled",
        lambda: True,
    )
    assert funnel.storyline_articles_write_allowed() is False
    monkeypatch.setattr(funnel, "storyline_articles_dual_write_enabled", lambda: True)
    assert funnel.storyline_articles_write_allowed() is True
    monkeypatch.setattr(
        "shared.episode_attach_gate.episode_container_assembly_enabled",
        lambda: False,
    )
    monkeypatch.setattr(funnel, "storyline_articles_dual_write_enabled", lambda: False)
    assert funnel.storyline_articles_write_allowed() is True


def test_automation_derived_membership_blocked_without_write(monkeypatch):
    """Episode-append SA fallback must not INSERT when write_allowed is false."""
    from pathlib import Path

    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[2]
        load_dotenv(root / ".env", override=False)
        load_dotenv(root / "api" / ".env", override=False)
    except Exception:
        pass

    # Avoid domain_registry DB bootstrap on import when credentials unavailable.
    monkeypatch.setattr(
        "shared.domain_registry._load_domain_entries_from_db",
        lambda: [{"domain_key": "politics", "schema_name": "politics", "is_active": True}],
    )

    from services.storyline_automation_service import StorylineAutomationService

    monkeypatch.setattr(
        "shared.assembly_link_funnel.storyline_articles_write_allowed",
        lambda: False,
    )
    svc = object.__new__(StorylineAutomationService)
    svc.domain = "politics"
    svc.schema = "politics"
    ok, reason = svc._insert_derived_membership(
        None, 1, 2, 0.9, reason="signature_overlap_append"
    )
    assert ok is False
    assert reason == "storyline_articles_write_blocked"


def test_resolve_routes_max_rounds_closed_thin(monkeypatch):
    from pathlib import Path

    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[2]
        load_dotenv(root / ".env", override=False)
        load_dotenv(root / "api" / ".env", override=False)
    except Exception:
        pass

    from services.editorial_package_narrative_service import (
        resolve_narrative_route,
        resolve_reduction_route_after_pass,
    )
    from services.editorial_package_research_service import resolve_research_route

    assert (
        resolve_narrative_route(changed=0, meta={}, round_n=3, max_r=3) == "closed_thin"
    )
    assert (
        resolve_research_route(changed=0, meta={}, round_n=3, max_r=3) == "closed_thin"
    )
    assert (
        resolve_reduction_route_after_pass(changed=0, meta={}, round_n=3, max_r=3)
        == "closed_thin"
    )
    # both-zero still clears to editor
    assert (
        resolve_narrative_route(
            changed=0,
            meta={"reduction_rounds": 1, "last_reduction_removed_count": 0},
            round_n=1,
            max_r=3,
        )
        == "editor"
    )