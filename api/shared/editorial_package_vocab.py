"""
Editorial package vocabulary and helpers (v11).
"""

from __future__ import annotations

from typing import Any

PACKAGE_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "in_research",
        "in_narrative",
        "in_reduction",
        "ready_for_editor",
        "in_editing",
        "published",
        "blocked",
        "archived",
        "closed_thin",
    }
)

PRESENTATION_KINDS: frozenset[str] = frozenset(
    {"unset", "research_brief", "event_narrative", "hybrid"}
)

MEMBER_FAMILIES: frozenset[str] = frozenset({"research", "narrative"})

RESEARCH_MEMBER_TYPES: frozenset[str] = frozenset(
    {
        "extracted_claim",
        "versioned_fact",
        "claim_evidence_appraisal",
        "hypothesis",
        "processed_document",
        "article",
        "context",
    }
)

NARRATIVE_MEMBER_TYPES: frozenset[str] = frozenset(
    {
        "chronological_event",
        "entity",
        "location",
        "graph_link",
        "article",
        "context",
    }
)

# Deferred — not attachable until real identity tables exist (do not re-add to hot path).
DEFERRED_MEMBER_TYPES: frozenset[str] = frozenset({"time_span", "movement_edge"})

ALL_MEMBER_TYPES: frozenset[str] = RESEARCH_MEMBER_TYPES | NARRATIVE_MEMBER_TYPES

MEMBER_STATUSES: frozenset[str] = frozenset({"active", "quarantined", "removed"})

LINK_TYPES: frozenset[str] = frozenset(
    {
        "supports",
        "contradicts",
        "same_event",
        "near_in_time",
        "same_place",
        "movement",
        "caused_by",
        "corroborates",
        "derived_from",
    }
)

INFERENCE_STAGES: frozenset[str] = frozenset(
    {"hypothesized", "candidate", "established", "quarantined"}
)

DECISION_ACTIONS: frozenset[str] = frozenset(
    {
        "member_added",
        "member_removed",
        "member_quarantined",
        "link_added",
        "link_removed",
        "kind_set",
        "ready_for_editor",
        "cleared",
        "blocked",
        "rework_requested",
        "prose_drafted",
        "prose_published",
        "citation_bound",
        "citation_refused",
        "status_changed",
        "package_created",
        "converged",
        "reduction_pass",
        "narrative_pass",
        "research_pass",
    }
)

MODALS: frozenset[str] = frozenset(
    {"intake", "research", "narrative", "reduction", "editor", "system"}
)


def family_for_member_type(member_type: str) -> str | None:
    mt = (member_type or "").strip()
    if mt in RESEARCH_MEMBER_TYPES and mt in NARRATIVE_MEMBER_TYPES:
        return None  # ambiguous — caller must pass family
    if mt in RESEARCH_MEMBER_TYPES:
        return "research"
    if mt in NARRATIVE_MEMBER_TYPES:
        return "narrative"
    return None


def provenance_has_citeable_source(
    prov: Any,
    *,
    for_publish: bool = False,
) -> bool:
    """True when provenance has a quote or URL (ids alone are insufficient).

    When for_publish=True, reject soft title-as-quote (quote equals label with no URL,
    or explicit quote_is_title / soft_title markers).
    """
    if not isinstance(prov, dict):
        return False
    quote = prov.get("quote") or prov.get("quote_span") or ""
    if isinstance(quote, dict):
        quote = quote.get("quote") or quote.get("text") or ""
    quote_s = str(quote).strip() if quote is not None else ""
    url = prov.get("source_url") or prov.get("url") or ""
    url_s = str(url).strip() if url is not None else ""
    if url_s:
        return True
    if not quote_s:
        return False
    if for_publish:
        if prov.get("quote_is_title") or prov.get("soft_title"):
            return False
        label = str(prov.get("label") or "").strip()
        if label and quote_s == label:
            return False
    return True


def compute_readiness(
    members: list[dict[str, Any]],
    links: list[dict[str, Any]],
    *,
    package_status: str | None = None,
    reduction_cleared: bool = False,
) -> dict[str, Any]:
    """Checklist snapshot for Editor gate."""
    active = [m for m in members if m.get("status") == "active"]
    quarantined = [m for m in members if m.get("status") == "quarantined"]
    research = [m for m in active if m.get("member_family") == "research"]
    narrative = [m for m in active if m.get("member_family") == "narrative"]
    has_claimish = any(
        m.get("member_type")
        in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal", "hypothesis")
        for m in research
    )
    has_event = any(m.get("member_type") == "chronological_event" for m in narrative)
    has_anchor = any(m.get("role") == "anchor_event" for m in narrative) or has_event
    active_links = [lnk for lnk in links if lnk.get("status") == "active"]
    citeable = sum(
        1
        for m in active
        if provenance_has_citeable_source(m.get("provenance"), for_publish=True)
    )
    coverage = (citeable / len(active)) if active else 0.0
    status = (package_status or "").strip()
    # in_editing alone is not clearance — need explicit cleared decision or ready_for_editor+.
    cleared = bool(reduction_cleared) or status in (
        "ready_for_editor",
        "published",
    )
    research_brief_ready = has_claimish and citeable > 0
    event_narrative_ready = has_anchor and len(narrative) >= 1
    return {
        "active_member_count": len(active),
        "research_member_count": len(research),
        "narrative_member_count": len(narrative),
        "active_link_count": len(active_links),
        "has_research_core": has_claimish,
        "has_narrative_anchor": has_anchor,
        "research_brief_ready": research_brief_ready,
        "event_narrative_ready": event_narrative_ready,
        "hybrid_ready": research_brief_ready and event_narrative_ready,
        "citeable_member_count": citeable,
        "citation_coverage": round(coverage, 3),
        "contested_or_quarantined_count": len(quarantined),
        "reduction_cleared": cleared,
        "package_status": status or None,
    }
