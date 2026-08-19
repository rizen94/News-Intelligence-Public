"""Unit tests for mega harden Pillar B: auto-add threshold, core prune, finisher trim."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API_SERVICES = _ROOT / "api" / "services"

# Shared mocks for modules that touch DB/runtime at import time
sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
sys.modules.setdefault("shared.storyline_article_counts", MagicMock())
_rt = MagicMock()
_rt.env_str = lambda k, d="": d
_rt.env_bool = MagicMock(return_value=False)
_rt.env_int = MagicMock(side_effect=lambda k, d=0: int(d) if d is not None else 0)
_rt.env_float = MagicMock(side_effect=lambda k, d=0.0: float(d) if d is not None else 0.0)
sys.modules["config.runtime"] = _rt


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Membership review first (core prune reuses compute_article_fit_score)
_membership = _load(
    "storyline_membership_review_service",
    _API_SERVICES / "storyline_membership_review_service.py",
)
sys.modules["services.storyline_membership_review_service"] = _membership

_automation = _load(
    "storyline_automation_service",
    _API_SERVICES / "storyline_automation_service.py",
)

_prune = _load(
    "storyline_core_prune_service",
    _API_SERVICES / "storyline_core_prune_service.py",
)

# Finisher needs heavier deps — load only the trim helper via exec of the function source
# Prefer loading the module with ollama mocks.
sys.modules.setdefault("shared.services.ollama_model_caller", MagicMock())
sys.modules.setdefault("shared.services.ollama_model_policy", MagicMock())
# Do NOT mock shared.llm_text_sanitize — finisher parse + trim rely on real helpers.
_ollama_pol = sys.modules["shared.services.ollama_model_policy"]
_ollama_pol.InvocationKind = MagicMock()

_finisher = _load(
    "storyline_narrative_finisher_service",
    _API_SERVICES / "storyline_narrative_finisher_service.py",
)

effective_auto_add_threshold = _automation.effective_auto_add_threshold
decide_dissimilar_member_action = _prune.decide_dissimilar_member_action
build_core_signature_from_rows = _prune.build_core_signature_from_rows
member_is_core_protected = _prune.member_is_core_protected
member_matches_title_anchor = _prune.member_matches_title_anchor
distinctive_title_anchors = _prune.distinctive_title_anchors
core_text_for_signature = _prune.core_text_for_signature
compute_article_fit_score = _membership.compute_article_fit_score
apply_sections_to_deprecate_or_trim = _finisher.apply_sections_to_deprecate_or_trim


def test_effective_auto_add_threshold_closes_060_vs_075_leak():
    """Base min_relevance 0.60 must not undercut auto_approve_combined 0.75."""
    thr = effective_auto_add_threshold(
        base_min_relevance=0.60,
        auto_approve_combined=0.75,
        article_count=20,
    )
    assert thr == 0.75


def test_effective_auto_add_threshold_size_scaling():
    """Large storylines raise the floor (+0.05 per 50 arts from 80)."""
    thr_small = effective_auto_add_threshold(
        base_min_relevance=0.75,
        auto_approve_combined=0.75,
        article_count=40,
    )
    thr_100 = effective_auto_add_threshold(
        base_min_relevance=0.75,
        auto_approve_combined=0.75,
        article_count=100,
    )
    thr_150 = effective_auto_add_threshold(
        base_min_relevance=0.75,
        auto_approve_combined=0.75,
        article_count=150,
    )
    assert thr_small == 0.75
    assert thr_100 == 0.80  # steps = (100-50)//50 = 1 → +0.05
    assert thr_150 == 0.85  # steps = (150-50)//50 = 2 → +0.10


def test_core_prune_nepal_nd_dissimilar_kathmandu_keep():
    """Nepal-like core: ND agriculture member drops; Kathmandu member keeps."""
    core_tokens = {"nepal", "earthquake", "kathmandu", "rescue"}
    core_entities = {"nepal", "kathmandu", "nepal army"}

    nd_fit = compute_article_fit_score(
        core_tokens=core_tokens,
        core_entities=core_entities,
        article_title="North Dakota farmers seek drought relief aid",
        article_entities={"north dakota", "usda"},
        relevance_score=0.55,
    )
    kt_fit = compute_article_fit_score(
        core_tokens=core_tokens,
        core_entities=core_entities,
        article_title="Kathmandu rescue teams reach Nepal earthquake zone",
        article_entities={"kathmandu", "nepal", "nepal army"},
        relevance_score=0.85,
    )
    assert nd_fit < 0.28
    assert kt_fit >= 0.55

    nd_action, nd_rationale, nd_high = decide_dissimilar_member_action(
        fit_score=nd_fit,
        entity_jaccard=0.0,
        embedding_cosine=0.20,
    )
    kt_action, _, _ = decide_dissimilar_member_action(
        fit_score=kt_fit,
        entity_jaccard=0.66,
        embedding_cosine=0.82,
    )
    assert nd_action == "unlink"
    assert nd_high is True
    assert "dissimilar_to_core" in nd_rationale
    assert kt_action == "keep"

    # Signature builder marks ND as low-fit vs Kathmandu high-fit quartile
    core = build_core_signature_from_rows(
        title="Nepal earthquake: Kathmandu rescue effort",
        summary="Rescue teams in Kathmandu after Nepal quake",
        sei_rows=[
            ("Nepal", 40, True),
            ("Kathmandu", 25, True),
            ("Nepal Army", 12, True),
        ],
        member_rows=[
            {
                "article_id": 1,
                "title": "Kathmandu rescue teams reach Nepal earthquake zone",
                "entities": {"kathmandu", "nepal", "nepal army"},
                "relevance": 0.85,
            },
            {
                "article_id": 2,
                "title": "North Dakota farmers seek drought relief aid",
                "entities": {"north dakota", "usda"},
                "relevance": 0.55,
            },
            {
                "article_id": 3,
                "title": "Nepal Army airlifts supplies to Kathmandu valley",
                "entities": {"nepal army", "kathmandu", "nepal"},
                "relevance": 0.9,
            },
            {
                "article_id": 4,
                "title": "Aftershocks rattle Kathmandu as Nepal recovery continues",
                "entities": {"kathmandu", "nepal"},
                "relevance": 0.8,
            },
        ],
    )
    by_id = {m["article_id"]: m for m in core["scored_members"]}
    assert by_id[2]["fit"] < 0.28
    assert by_id[1]["fit"] >= 0.55
    assert 2 not in (core.get("high_fit_member_ids") or [])


def test_core_signature_ignores_global_update_pollution():
    """Kitchen-sink Global Update body must not redefine core away from title."""
    polluted = (
        "**Global Update: Key Developments and Trends**\n\n"
        "In the latest batch of news, we see a mix of high-profile politics...\n\n"
        "**Politics:**\n\n* Ukraine defence minister dismissed by Zelenskyy\n"
        "* Trump escalates Iran conflict\n* North Dakota farm bill advances"
    )
    core = build_core_signature_from_rows(
        title="Nepal's Political Landscape Shifts as CM Addresses Journalists",
        summary=polluted,
        sei_rows=[
            ("Donald Trump", 88, False),
            ("Iran", 40, False),
            ("Benjamin Netanyahu", 42, False),
            ("Nepal", 5, True),
        ],
        member_rows=[
            {
                "article_id": 1,
                "title": "Balen Shah: From rebel outsider to Nepal’s next prime minister",
                "entities": {"nepal", "balen shah", "kathmandu"},
                "relevance": 0.9,
            },
            {
                "article_id": 2,
                "title": "North Dakota men who discover they were switched as newborns sue hospital",
                "entities": {"north dakota"},
                "relevance": 0.5,
            },
            {
                "article_id": 3,
                "title": "First Thing: Trump urged to end Iran escalation",
                "entities": {"trump", "iran"},
                "relevance": 0.55,
            },
            {
                "article_id": 4,
                "title": "Youth-backed RSP win signals Nepal’s new political era",
                "entities": {"nepal", "rsp"},
                "relevance": 0.85,
            },
        ],
    )
    assert core.get("polluted_body") is True
    assert "nepal" in core["core_tokens"]
    assert "ukraine" not in core["core_tokens"]
    # Title-anchored entities — not Trump/Iran SEI majority
    assert "donald trump" not in core["core_entities"]
    assert "iran" not in core["core_entities"]
    assert "nepal" in core["core_entities"]
    by_id = {m["article_id"]: m for m in core["scored_members"]}
    assert by_id[1]["fit"] >= 0.55
    assert by_id[4]["fit"] >= 0.55
    assert by_id[2]["fit"] < 0.28
    assert by_id[3]["fit"] < 0.28
    nd_action, _, _ = decide_dissimilar_member_action(
        fit_score=by_id[2]["fit"],
        entity_jaccard=0.0,
        embedding_cosine=0.15,
    )
    assert nd_action == "unlink"
    kt_action, _, _ = decide_dissimilar_member_action(
        fit_score=by_id[1]["fit"],
        entity_jaccard=0.5,
        embedding_cosine=0.8,
    )
    assert kt_action == "keep"


def test_finisher_trim_removes_span_from_narrative():
    text = (
        "Nepal earthquake recovery continues in Kathmandu.\n\n"
        "Global Update: unrelated North Dakota farm bill passage.\n\n"
        "Rescue operations expanded overnight."
    )
    new_text, applied, unmatched = apply_sections_to_deprecate_or_trim(
        text,
        ["Global Update: unrelated North Dakota farm bill passage."],
    )
    assert applied
    assert not unmatched
    assert "North Dakota farm bill" not in new_text
    assert "Kathmandu" in new_text
    assert "Rescue operations" in new_text


def test_core_protected_member_never_unlinked_even_low_fit():
    """relationship_type=core (and restore metadata) must stay keep-band."""
    assert member_is_core_protected(
        {
            "relationship_type": "core",
            "title": "Balen Shah: From rebel outsider to Nepal’s next prime minister",
            "entities": {"nepal", "balen shah"},
        }
    )
    assert member_is_core_protected(
        {
            "relationship_type": "related",
            "metadata": {
                "source": "core_prune_restore",
                "reason": "reprotect_nepal_keepers_after_pass2_drift",
            },
        }
    )
    assert not member_is_core_protected(
        {"relationship_type": "related", "metadata": {"source": "rss"}}
    )

    # Signature: protected Nepal keeper stays high-fit vs ND outlier
    core = build_core_signature_from_rows(
        title="Nepal's Political Landscape Shifts as CM Addresses Journalists",
        summary="",  # cleared body after prior prune pass
        sei_rows=[
            ("Donald Trump", 88, False),
            ("Iran", 40, False),
            ("Benjamin Netanyahu", 42, False),
        ],
        member_rows=[
            {
                "article_id": 18504,
                "title": "Balen Shah: From rebel outsider to Nepal’s next prime minister",
                "entities": {"nepal", "balen shah", "kathmandu"},
                "relevance": 0.95,
                "relationship_type": "core",
                "metadata": {
                    "source": "core_prune_restore",
                    "reason": "reprotect_nepal_keepers_after_pass2_drift",
                },
            },
            {
                "article_id": 99,
                "title": "North Dakota farmers seek drought relief aid",
                "entities": {"north dakota", "usda"},
                "relevance": 0.55,
                "relationship_type": "related",
            },
        ],
    )
    assert core.get("polluted_body") is True
    assert "nepal" in core["core_tokens"]
    assert "nepal" in core["core_entities"]
    assert "donald trump" not in core["core_entities"]
    by_id = {m["article_id"]: m for m in core["scored_members"]}
    assert by_id[18504]["core_protected"] is True
    assert by_id[18504]["fit"] >= 0.85
    assert by_id[99]["fit"] < 0.28
    # Simulated decide path: protected stays keep even if raw decide says unlink
    nd_action, _, _ = decide_dissimilar_member_action(
        fit_score=by_id[99]["fit"],
        entity_jaccard=0.0,
        embedding_cosine=0.1,
    )
    assert nd_action == "unlink"
    # Protected keeper: force-keep regardless of decide_dissimilar_member_action
    assert by_id[18504]["core_protected"]
    assert by_id[18504]["title_anchor_hit"]


def test_second_pass_polluted_sei_keeps_title_anchored_nepal():
    """
    Regression: after pass 1 cleared narrative, polluted SEI must not redefine
    core away from Nepal — title-anchored keepers survive, outliers unlink.
    """
    title = (
        "Nepal's Political Landscape Shifts as CM Addresses Journalists' "
        "Concerns, Minister Highlights Women's Empowerment"
    )
    # Empty summary mimics post-pass kitchen-sink wipe
    text, polluted = core_text_for_signature(
        title,
        "",
        sei_entities={"donald trump", "iran", "benjamin netanyahu", "congress"},
    )
    assert polluted is True
    assert "nepal" in distinctive_title_anchors(title)

    nepal_keepers = [
        {
            "article_id": aid,
            "title": tit,
            "entities": ents,
            "relevance": 0.95,
            "relationship_type": "core",
            "metadata": {"source": "core_prune_restore"},
        }
        for aid, tit, ents in [
            (
                18504,
                "Balen Shah: From rebel outsider to Nepal’s next prime minister",
                {"nepal", "balen shah"},
            ),
            (
                16247,
                "Youth-backed RSP win signals Nepal’s new political era",
                {"nepal", "rsp"},
            ),
            (
                10291,
                "Nepal: Early vote returns suggest massive political shift",
                {"nepal"},
            ),
            (
                18898,
                "Nepal: Gen Z buoys ex‑rapper's party to landslide victory",
                {"nepal", "gen z"},
            ),
            (
                14605,
                "Nepal: Rapper-turned-politician poised to become next PM",
                {"nepal"},
            ),
            (
                8950,
                "Six months after Nepal's revolution, Generation Z hopes for change",
                {"nepal"},
            ),
            (
                11942,
                "Gen-Z probe commission submits its report to Nepal Government",
                {"nepal", "gen-z"},
            ),
        ]
    ]
    outliers = [
        {
            "article_id": 1,
            "title": "North Dakota men who discover they were switched as newborns sue hospital",
            "entities": {"north dakota"},
            "relevance": 0.5,
            "relationship_type": "related",
        },
        {
            "article_id": 2,
            "title": "First Thing: Trump urged to end Iran escalation",
            "entities": {"trump", "iran"},
            "relevance": 0.55,
            "relationship_type": "related",
        },
        {
            "article_id": 3,
            "title": "Amazon Web Services customers receive bills for up to $1.5tn",
            "entities": {"amazon", "aws"},
            "relevance": 0.4,
            "relationship_type": "related",
        },
    ]
    core = build_core_signature_from_rows(
        title=title,
        summary="",
        sei_rows=[
            ("Donald Trump", 88, False),
            ("Iran", 40, False),
            ("Benjamin Netanyahu", 42, False),
            ("Congress", 31, False),
            ("Democrats", 30, False),
            ("Keir Starmer", 25, False),
            ("Hezbollah", 23, False),
            ("Andy Burnham", 22, False),
            ("Senate", 22, False),
        ],
        member_rows=nepal_keepers + outliers,
    )
    assert core.get("polluted_body") is True
    assert "nepal" in core["core_tokens"]
    assert "nepal" in core["core_entities"]
    assert "donald trump" not in core["core_entities"]
    assert "iran" not in core["core_entities"]

    by_id = {m["article_id"]: m for m in core["scored_members"]}
    for kid in (18504, 16247, 10291, 18898, 14605, 8950, 11942):
        assert by_id[kid]["core_protected"] is True
        assert by_id[kid]["title_anchor_hit"] is True
        assert by_id[kid]["fit"] >= 0.85
        # Would-keep path: never dissimilar_to_core unlink
        action, _, _ = decide_dissimilar_member_action(
            fit_score=by_id[kid]["fit"],
            entity_jaccard=0.5,
            embedding_cosine=0.8,
        )
        assert action == "keep"

    for oid in (1, 2, 3):
        assert by_id[oid]["fit"] < 0.28
        action, rationale, high = decide_dissimilar_member_action(
            fit_score=by_id[oid]["fit"],
            entity_jaccard=0.0,
            embedding_cosine=0.15,
        )
        assert action == "unlink"
        assert high is True
        assert "dissimilar_to_core" in rationale

    anchors = distinctive_title_anchors(title)
    assert member_matches_title_anchor(anchors, nepal_keepers[0]["title"], {"nepal"})
    assert not member_matches_title_anchor(
        anchors, outliers[0]["title"], {"north dakota"}
    )


def test_finisher_trim_unmatched_short_or_missing():
    text = "Canonical Nepal narrative about Kathmandu."
    new_text, applied, unmatched = apply_sections_to_deprecate_or_trim(
        text,
        ["this span does not appear anywhere in the narrative body"],
    )
    assert new_text == text
    assert not applied
    assert unmatched


# --- Shell-title magnet absorb (permanent, not freeze-only) ---

is_shell_title = _automation.is_shell_title
candidate_passes_absorb_gate = _automation.candidate_passes_absorb_gate
filter_articles_for_keeper_evidence = _prune.filter_articles_for_keeper_evidence
should_use_keeper_only_evidence = _prune.should_use_keeper_only_evidence


def test_is_shell_title_covers_magnet_patterns():
    assert is_shell_title("Ongoing: Middle East conflict")
    assert is_shell_title("Iran LIVE UPDATES")
    assert is_shell_title("Global Update")
    assert is_shell_title("Nepal")  # bare country
    assert is_shell_title("LIVE UPDATES: Israel-Iran")
    assert not is_shell_title(
        "Nepal's Gen Z Revolution: RSP and Balen Shah Reshape Politics"
    )


def test_shell_absorb_rejects_single_token_country_ilike():
    """Bare-country / Ongoing shells must not absorb on single-entity ILIKE alone."""
    shell = "Ongoing: Iran conflict"
    weak = {
        "id": 1,
        "title": "Iran markets open higher after oil spike",
        "matched_entities": ["Iran"],
        "canonical_jaccard": 0.0,
        "combined_score": 0.9,
    }
    assert candidate_passes_absorb_gate(
        weak, storyline_title=shell, article_count=10
    ) is False

    # Multi-entity + title-anchor (Iran in title + second entity) still needs anchor hit
    # Article about Iran+Tehran should pass for Iran shell
    strong = {
        "id": 2,
        "title": "Tehran officials brief Iran parliament on conflict timeline",
        "matched_entities": ["Iran", "Tehran"],
        "canonical_jaccard": 0.2,
        "combined_score": 0.9,
    }
    assert candidate_passes_absorb_gate(
        strong, storyline_title=shell, article_count=10
    ) is True

    # Unrelated multi-entity without title-anchor must fail
    glue = {
        "id": 3,
        "title": "North Dakota and Minnesota farm bill advances",
        "matched_entities": ["North Dakota", "Minnesota"],
        "canonical_jaccard": 0.0,
        "combined_score": 0.9,
    }
    assert candidate_passes_absorb_gate(
        glue, storyline_title=shell, article_count=10
    ) is False


def test_large_storyline_rejects_single_token_without_requiring_shell():
    """article_count ≥ multi_entity threshold rejects single-token ILIKE even on good titles."""
    good_title = "Nepal's Gen Z Revolution: RSP and Balen Shah Reshape Politics"
    weak = {
        "id": 1,
        "title": "Nepal tourism rebound continues",
        "matched_entities": ["Nepal"],
        "canonical_jaccard": 0.0,
    }
    assert candidate_passes_absorb_gate(
        weak, storyline_title=good_title, article_count=80
    ) is False
    multi = {
        "id": 2,
        "title": "Balen Shah and RSP surge after Nepal Gen Z vote",
        "matched_entities": ["Nepal", "Balen Shah"],
        "canonical_jaccard": 0.0,
    }
    # Non-shell large: multi-entity alone is enough (no title-anchor AND required)
    assert candidate_passes_absorb_gate(
        multi, storyline_title=good_title, article_count=80
    ) is True


def test_magnet_title_raises_auto_add_floor():
    base = effective_auto_add_threshold(
        base_min_relevance=0.75,
        auto_approve_combined=0.75,
        article_count=20,
        magnet_title=False,
    )
    magnet = effective_auto_add_threshold(
        base_min_relevance=0.75,
        auto_approve_combined=0.75,
        article_count=20,
        magnet_title=True,
    )
    assert magnet == min(0.95, base + 0.08)


def test_keeper_only_evidence_excludes_polluted_member_titles():
    """Finisher/RAG evidence must drop ND/Iran/AWS glue when regenerating from keepers."""
    title = "Nepal's Gen Z Revolution: RSP and Balen Shah Reshape Politics"
    polluted_body = (
        "**Global Update: Key Developments and Trends**\n\n"
        "Ukraine defence minister dismissed...\nTrump escalates Iran..."
    )
    assert should_use_keeper_only_evidence(
        title=title,
        summary=polluted_body,
        prefer_regenerate_from_keepers=True,
    )

    articles = [
        {
            "id": 18504,
            "title": "Balen Shah: From rebel outsider to Nepal’s next prime minister",
            "entities": {"nepal", "balen shah", "kathmandu"},
            "relationship_type": "core",
            "relevance": 0.9,
        },
        {
            "id": 16247,
            "title": "Six months after Nepal's revolution, Generation Z hopes for change",
            "entities": {"nepal", "generation z"},
            "relationship_type": "core",
            "relevance": 0.85,
        },
        {
            "id": 1,
            "title": "North Dakota men who discover they were switched as newborns sue hospital",
            "entities": {"north dakota"},
            "relationship_type": "related",
            "relevance": 0.5,
        },
        {
            "id": 2,
            "title": "First Thing: Trump urged to end Iran escalation",
            "entities": {"trump", "iran"},
            "relationship_type": "related",
            "relevance": 0.55,
        },
        {
            "id": 3,
            "title": "Amazon Web Services customers receive bills for up to $1.5tn",
            "entities": {"amazon", "aws"},
            "relationship_type": "related",
            "relevance": 0.4,
        },
    ]
    kept = filter_articles_for_keeper_evidence(
        storyline_title=title,
        storyline_summary=polluted_body,
        articles=articles,
        prefer_regenerate_from_keepers=True,
        sei_entities={"donald trump", "iran", "nepal"},
    )
    kept_ids = {a["id"] for a in kept}
    assert 18504 in kept_ids
    assert 16247 in kept_ids
    assert 1 not in kept_ids
    assert 2 not in kept_ids
    assert 3 not in kept_ids


def test_keeper_only_off_for_clean_normal_storyline():
    """Non-mega clean titles without prefer_regen keep the full evidence set."""
    title = "Federal Reserve signals slower path for rate cuts"
    articles = [
        {"id": 1, "title": "Fed officials debate September cut", "entities": {"fed"}},
        {"id": 2, "title": "Markets rally on soft CPI print", "entities": {"cpi"}},
    ]
    assert should_use_keeper_only_evidence(title=title, summary="Fed path.") is False
    kept = filter_articles_for_keeper_evidence(
        storyline_title=title,
        storyline_summary="Fed path for rate cuts remains data-dependent.",
        articles=articles,
        prefer_regenerate_from_keepers=False,
    )
    assert len(kept) == 2


def test_live_updates_title_forces_keeper_only_mode():
    assert should_use_keeper_only_evidence(
        title="Iran LIVE UPDATES",
        summary="",
        prefer_regenerate_from_keepers=False,
    )