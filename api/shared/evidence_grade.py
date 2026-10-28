"""
Evidence-grade vocabularies and deterministic appraisal helpers (v11 SSOT).

Used by literature collectors (MeSH → study_design), claim_evidence_appraisal,
and research_claim_ledger alignment.
"""

from __future__ import annotations

from typing import Any, Mapping

STUDY_DESIGNS = frozenset(
    {
        "meta_analysis",
        "systematic_review",
        "rct",
        "cohort",
        "case_control",
        "cross_sectional",
        "case_report",
        "animal_in_vitro",
        "modeling",
        "opinion",
        "unknown",
    }
)

PEER_REVIEW_STATUSES = frozenset(
    {
        "peer_reviewed",
        "preprint",
        "registry_record",
        "gray_literature",
        "unknown",
    }
)

PAPER_SUPPORTS = frozenset(
    {
        "supported_by_own_evidence",
        "partially_supported",
        "not_supported_by_own_evidence",
        "insufficient_reporting",
    }
)

REPLICATION_STATUSES = frozenset(
    {
        "replicated_independent",
        "replicated_same_group",
        "single_study",
        "contradicted",
        "needs_follow_up",
    }
)

EVIDENCE_GRADES = frozenset(
    {
        "strong",
        "moderate",
        "limited",
        "preliminary",
        "unsubstantiated",
    }
)

# Design strength ranks (higher = stronger design ladder for grading).
_DESIGN_RANK: dict[str, int] = {
    "meta_analysis": 5,
    "systematic_review": 5,
    "rct": 4,
    "cohort": 3,
    "case_control": 3,
    "cross_sectional": 2,
    "case_report": 1,
    "animal_in_vitro": 1,
    "modeling": 1,
    "opinion": 0,
    "unknown": 0,
}

_MESH_TO_DESIGN: dict[str, str] = {
    "meta-analysis": "meta_analysis",
    "systematic review": "systematic_review",
    "randomized controlled trial": "rct",
    "controlled clinical trial": "rct",
    "clinical trial": "rct",
    "clinical trial, phase i": "rct",
    "clinical trial, phase ii": "rct",
    "clinical trial, phase iii": "rct",
    "clinical trial, phase iv": "rct",
    "pragmatic clinical trial": "rct",
    "observational study": "cohort",
    "cohort studies": "cohort",
    "longitudinal studies": "cohort",
    "prospective studies": "cohort",
    "retrospective studies": "cohort",
    "case-control studies": "case_control",
    "cross-sectional studies": "cross_sectional",
    "case reports": "case_report",
    "case series": "case_report",
    "in vitro techniques": "animal_in_vitro",
    "in vitro": "animal_in_vitro",
    "animals": "animal_in_vitro",
    "models, theoretical": "modeling",
    "computer simulation": "modeling",
    "editorial": "opinion",
    "letter": "opinion",
    "comment": "opinion",
    "news": "opinion",
    "newspaper article": "opinion",
    "interview": "opinion",
    "personal narrative": "opinion",
    "practice guideline": "systematic_review",
    "guideline": "systematic_review",
    "consensus development conference": "systematic_review",
    "review": "systematic_review",
}


def _slug(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def normalize_study_design(raw: Any) -> str:
    s = _slug(raw)
    aliases = {
        "randomized_controlled_trial": "rct",
        "randomised_controlled_trial": "rct",
        "randomized_trial": "rct",
        "metaanalysis": "meta_analysis",
        "systematicreviews": "systematic_review",
        "casecontrol": "case_control",
        "crosssectional": "cross_sectional",
        "casereport": "case_report",
        "in_vitro": "animal_in_vitro",
        "animal": "animal_in_vitro",
        "preclinical": "animal_in_vitro",
    }
    s = aliases.get(s, s)
    return s if s in STUDY_DESIGNS else "unknown"


def normalize_peer_review_status(raw: Any) -> str:
    s = _slug(raw)
    aliases = {
        "peer_review": "peer_reviewed",
        "reviewed": "peer_reviewed",
        "pre_print": "preprint",
        "biorxiv": "preprint",
        "medrxiv": "preprint",
        "registry": "registry_record",
        "trial_registry": "registry_record",
        "grey_literature": "gray_literature",
        "gray": "gray_literature",
    }
    s = aliases.get(s, s)
    return s if s in PEER_REVIEW_STATUSES else "unknown"


def normalize_paper_support(raw: Any) -> str:
    s = _slug(raw)
    aliases = {
        "supported": "supported_by_own_evidence",
        "supported_by_evidence": "supported_by_own_evidence",
        "partial": "partially_supported",
        "partial_support": "partially_supported",
        "not_supported": "not_supported_by_own_evidence",
        "unsupported": "not_supported_by_own_evidence",
        "insufficient": "insufficient_reporting",
        "insufficient_evidence": "insufficient_reporting",
        "no_quotes": "insufficient_reporting",
    }
    s = aliases.get(s, s)
    return s if s in PAPER_SUPPORTS else "insufficient_reporting"


def normalize_replication_status(raw: Any) -> str:
    s = _slug(raw)
    aliases = {
        "replicated": "replicated_independent",
        "independent_replication": "replicated_independent",
        "same_group_replication": "replicated_same_group",
        "unreplicated": "single_study",
        "single": "single_study",
        "follow_up": "needs_follow_up",
        "needs_followup": "needs_follow_up",
        "followup": "needs_follow_up",
        # Explicit: needs_follow_up must NEVER collapse to contradicted/false.
        "false": "needs_follow_up",
        "falsified": "contradicted",
        "refuted": "contradicted",
    }
    s = aliases.get(s, s)
    return s if s in REPLICATION_STATUSES else "single_study"


def normalize_evidence_grade(raw: Any) -> str:
    s = _slug(raw)
    return s if s in EVIDENCE_GRADES else "preliminary"


def mesh_publication_type_to_study_design(mesh_type: str) -> str:
    """Map MeSH / PubMed PublicationType label → STUDY_DESIGNS key."""
    raw = str(mesh_type or "").strip().lower()
    if not raw:
        return "unknown"
    if raw in _MESH_TO_DESIGN:
        return _MESH_TO_DESIGN[raw]
    # Fuzzy contains for compound labels
    for needle, design in (
        ("meta-analysis", "meta_analysis"),
        ("systematic review", "systematic_review"),
        ("randomized controlled", "rct"),
        ("randomised controlled", "rct"),
        ("clinical trial", "rct"),
        ("case-control", "case_control"),
        ("cross-sectional", "cross_sectional"),
        ("cohort", "cohort"),
        ("case report", "case_report"),
        ("in vitro", "animal_in_vitro"),
        ("editorial", "opinion"),
        ("letter", "opinion"),
        ("comment", "opinion"),
        ("review", "systematic_review"),
    ):
        if needle in raw:
            return design
    return "unknown"


def compose_evidence_grade(
    study_design: Any,
    peer_review_status: Any,
    paper_support: Any,
    replication_status: Any,
    abstract_only: bool = False,
) -> str:
    """
    Deterministic evidence grade from appraisal dimensions.

    Rules of note:
    - ``abstract_only`` can never yield ``strong``.
    - ``needs_follow_up`` is not contradicted/false — caps at ``limited``.
    - ``not_supported_by_own_evidence`` → ``unsubstantiated``.
    - ``insufficient_reporting`` → ``preliminary`` (or lower if contradicted).
    """
    sd = normalize_study_design(study_design)
    pr = normalize_peer_review_status(peer_review_status)
    ps = normalize_paper_support(paper_support)
    rs = normalize_replication_status(replication_status)

    if ps == "not_supported_by_own_evidence":
        return "unsubstantiated"
    if rs == "contradicted":
        return "unsubstantiated"
    if ps == "insufficient_reporting":
        return "preliminary"

    design_rank = _DESIGN_RANK.get(sd, 0)
    peer_ok = pr == "peer_reviewed"
    support_full = ps == "supported_by_own_evidence"
    support_partial = ps == "partially_supported"

    # needs_follow_up: never treat as contradicted; ceiling limited
    if rs == "needs_follow_up":
        if support_full and peer_ok and design_rank >= 3:
            grade = "limited"
        elif support_partial or design_rank >= 2:
            grade = "limited"
        else:
            grade = "preliminary"
        return grade

    if (
        support_full
        and peer_ok
        and rs == "replicated_independent"
        and design_rank >= 4
        and not abstract_only
    ):
        return "strong"

    if support_full and peer_ok and design_rank >= 4 and rs in (
        "replicated_independent",
        "replicated_same_group",
        "single_study",
    ):
        grade = "moderate"
    elif support_full and peer_ok and design_rank >= 3:
        grade = "moderate"
    elif support_full and design_rank >= 2:
        grade = "limited"
    elif support_partial and peer_ok and design_rank >= 3:
        grade = "limited"
    elif support_partial:
        grade = "preliminary"
    elif pr == "preprint" or pr == "gray_literature":
        grade = "preliminary"
    else:
        grade = "preliminary"

    if abstract_only and grade == "strong":
        grade = "moderate"
    if abstract_only and grade == "moderate" and design_rank < 5:
        # Abstract-only observational / single-study RCTs stay limited
        if rs != "replicated_independent" or design_rank < 4:
            grade = "limited"

    if pr in ("preprint", "gray_literature", "registry_record") and grade in (
        "strong",
        "moderate",
    ):
        grade = "limited" if grade == "moderate" else "moderate"
        if grade == "strong":
            grade = "moderate"

    if sd in ("opinion", "animal_in_vitro", "modeling") and grade in ("strong", "moderate"):
        grade = "preliminary" if sd == "opinion" else "limited"

    return grade if grade in EVIDENCE_GRADES else "preliminary"


def _valid_evidence_quotes(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            q = item.strip()
            if q:
                out.append({"quote": q})
            continue
        if not isinstance(item, Mapping):
            continue
        quote = str(item.get("quote") or "").strip()
        if not quote:
            continue
        entry = dict(item)
        entry["quote"] = quote
        out.append(entry)
    return out


def assert_valid_appraisal_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Validate / coerce grader output.

    Refusal contract: if ``paper_support`` is anything other than
    ``insufficient_reporting``, require a non-empty ``evidence_quotes`` list with
    ``quote`` strings — otherwise force ``paper_support=insufficient_reporting``
    and recompose ``evidence_grade``.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("appraisal payload must be a mapping")

    out: dict[str, Any] = dict(payload)
    quotes = _valid_evidence_quotes(out.get("evidence_quotes"))
    paper_support = normalize_paper_support(out.get("paper_support"))

    if paper_support != "insufficient_reporting" and not quotes:
        paper_support = "insufficient_reporting"
        quotes = []

    study_design = normalize_study_design(out.get("study_design"))
    peer_review_status = normalize_peer_review_status(out.get("peer_review_status"))
    replication_status = normalize_replication_status(out.get("replication_status"))
    abstract_only = bool(out.get("abstract_only", False))

    evidence_grade = compose_evidence_grade(
        study_design,
        peer_review_status,
        paper_support,
        replication_status,
        abstract_only=abstract_only,
    )

    out["study_design"] = study_design
    out["peer_review_status"] = peer_review_status
    out["paper_support"] = paper_support
    out["replication_status"] = replication_status
    out["evidence_grade"] = evidence_grade
    out["evidence_quotes"] = quotes
    out["abstract_only"] = abstract_only

    if study_design not in STUDY_DESIGNS:
        raise ValueError(f"invalid study_design: {study_design}")
    if peer_review_status not in PEER_REVIEW_STATUSES:
        raise ValueError(f"invalid peer_review_status: {peer_review_status}")
    if paper_support not in PAPER_SUPPORTS:
        raise ValueError(f"invalid paper_support: {paper_support}")
    if replication_status not in REPLICATION_STATUSES:
        raise ValueError(f"invalid replication_status: {replication_status}")
    if evidence_grade not in EVIDENCE_GRADES:
        raise ValueError(f"invalid evidence_grade: {evidence_grade}")

    return out
