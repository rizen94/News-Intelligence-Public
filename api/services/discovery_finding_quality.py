"""Rank / filter connection_findings so editorial only sees attachable leads.

Global day-bucket temporal patterns (no domain, hundreds of contexts) were
winning the bridge queue on raw confidence and producing empty LLM packages.
"""

from __future__ import annotations

from typing import Any

TYPE_RANK = {
    "research_entity": 0,
    "cross_domain": 1,
    "graph_proposal": 2,
    "research_event": 3,
    "pattern": 4,
    "temporal": 5,
}

# Skip harvest/bridge for these reasons.
SKIP_REASONS = frozenset(
    {
        "global_temporal_pattern",
        "bulk_temporal_pattern",
        "thin_network",
        "temporal_missing_events",
        "no_domain",
        "graph_no_endpoints",
        "no_seed_members",
    }
)

INCOHERENCE_NEEDLES = (
    "no logical bridge",
    "no evidence linking",
    "two distinct",
    "unrelated topic",
    "unrelated artifacts",
    "no shared methodology",
    "conflates",
    "requiring separation",
    "no core claim",
    "not a single",
)


def _domains(finding: dict[str, Any]) -> list[str]:
    return [str(d).strip() for d in (finding.get("domain_keys") or []) if str(d).strip()]


def _evidence(finding: dict[str, Any]) -> dict[str, Any]:
    ev = finding.get("evidence") or {}
    return ev if isinstance(ev, dict) else {}


def finding_skip_reason(finding: dict[str, Any]) -> str | None:
    """Return a skip code, or None if the finding is worth bridging."""
    ftype = str(finding.get("finding_type") or "").strip()
    evidence = _evidence(finding)
    domains = _domains(finding)

    if ftype == "pattern":
        ptype = str(evidence.get("pattern_type") or "").strip()
        ents = list(evidence.get("entity_profile_ids") or [])
        ctx = list(evidence.get("context_ids") or [])
        data = evidence.get("data") if isinstance(evidence.get("data"), dict) else {}
        ctx_count = int(data.get("context_count") or len(ctx) or 0)
        if ptype == "temporal" and not domains:
            return "global_temporal_pattern"
        if ptype == "temporal" and not ents and ctx_count > 30:
            return "bulk_temporal_pattern"
        if ptype == "network" and len(ents) < 2:
            return "thin_network"
        if not domains and not ents and not ctx:
            return "no_domain"
        if not domains and ptype == "temporal":
            return "global_temporal_pattern"

    if ftype == "temporal":
        if not finding.get("left_id") or not finding.get("right_id"):
            return "temporal_missing_events"
        if not domains:
            return "no_domain"
        # Research domains: bridge as single-event packages (bridge truncates pair).
        return None

    if ftype == "graph_proposal":
        evidence = _evidence(finding)
        ep = evidence.get("endpoints") if isinstance(evidence.get("endpoints"), dict) else {}
        sids = ep.get("storyline_ids") or []
        ents = ep.get("entity_profile_ids") or ep.get("canonical_entity_ids") or []
        if not sids and not ents:
            return "graph_no_endpoints"
        return None

    if ftype == "pattern" and not domains:
        return "no_domain"

    return None


def is_bridgeable(finding: dict[str, Any]) -> bool:
    return finding_skip_reason(finding) is None


def type_rank(finding: dict[str, Any]) -> int:
    return TYPE_RANK.get(str(finding.get("finding_type") or ""), 9)


# Knowledge domains that can seed claimish research packages.
RESEARCH_SEED_DOMAINS = frozenset(
    {"medicine", "neurodiversity", "artificial-intelligence"}
)


def bridge_sort_key(finding: dict[str, Any]) -> tuple:
    """Lower is better: skip last, then type, then entity-rich patterns, then confidence."""
    skip = 0 if is_bridgeable(finding) else 1
    conf = float(finding.get("confidence") or 0.0)
    evidence = _evidence(finding)
    ents = len(list(evidence.get("entity_profile_ids") or []))
    endpoints = evidence.get("endpoints") if isinstance(evidence.get("endpoints"), dict) else {}
    if endpoints:
        ents = max(
            ents,
            len(list(endpoints.get("entity_profile_ids") or [])),
            len(list(endpoints.get("canonical_entity_ids") or [])),
            len(list(endpoints.get("storyline_ids") or [])),
        )
    # Prefer network patterns that already carry shared entities.
    entity_boost = 0
    ftype = str(finding.get("finding_type") or "")
    if ftype == "pattern":
        if str(evidence.get("pattern_type") or "") == "network" and ents >= 2:
            entity_boost = -1
        else:
            entity_boost = 1
    domains = _domains(finding)
    research_boost = -1 if any(d in RESEARCH_SEED_DOMAINS for d in domains) else 0
    return (skip, type_rank(finding), research_boost, entity_boost, -ents, -conf)


def package_default_domain(package: dict[str, Any] | None) -> str | None:
    if not package:
        return None
    for dk in list(package.get("domain_keys") or []):
        s = str(dk or "").strip()
        if s:
            return s
    for m in package.get("members") or []:
        if m.get("status") not in (None, "active"):
            continue
        s = str(m.get("domain_key") or "").strip()
        if s:
            return s
    return None


def resolve_attach_domain_key(
    candidate: dict[str, Any] | None,
    package: dict[str, Any] | None,
    *,
    modal: str,
) -> str | None:
    """Pick a domain allowed for this modal so add_member does not raise."""
    from shared.post_processing_modals import allowed_domains_for_modal

    allow = set(allowed_domains_for_modal(modal) or [])
    candidates: list[str] = []
    if candidate:
        dk = str(candidate.get("domain_key") or "").strip()
        if dk:
            candidates.append(dk)
        prov = candidate.get("provenance") if isinstance(candidate.get("provenance"), dict) else {}
        pdk = str(prov.get("domain_key") or "").strip()
        if pdk:
            candidates.append(pdk)
    pkg_dk = package_default_domain(package)
    if pkg_dk:
        candidates.append(pkg_dk)
    if package:
        for m in package.get("members") or []:
            s = str(m.get("domain_key") or "").strip()
            if s:
                candidates.append(s)
    for s in candidates:
        if not allow or s in allow:
            return s
    return candidates[0] if candidates else None


def discovery_finalize_action(
    validated: dict[str, Any] | None,
    *,
    changed: int = 0,
    pass_name: str = "research",
) -> tuple[str, str]:
    """Return (status, research_decision) for a finding after an editorial pass."""
    payload = validated or {}
    rejected = list(payload.get("rejected") or [])
    discovery_rejects = [r for r in rejected if str(r).startswith("discovery:")]
    gaps = [str(g).lower() for g in (payload.get("gaps") or [])]
    llm_unavailable = any("llm_unavailable" in g for g in gaps)
    discovery_attached = any(
        ((a.get("candidate") or {}).get("source") == "discovery")
        for a in (payload.get("attach") or [])
        if isinstance(a, dict)
    )
    if llm_unavailable and int(changed or 0) <= 0 and not discovery_attached:
        return "queued_research", "deferred_llm_unavailable"
    if int(changed or 0) > 0 or discovery_attached:
        return "linked", f"{pass_name}_attached"
    if discovery_rejects:
        return "dismissed", f"rejected_by_{pass_name}"
    return "dismissed", "no_attach"


def _text_blob(*parts: Any) -> str:
    bits: list[str] = []
    for part in parts:
        if isinstance(part, list):
            bits.extend(str(x) for x in part)
        elif part:
            bits.append(str(part))
    return " ".join(bits).lower()


def active_chronological_event_ids(package: dict[str, Any] | None) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for m in (package or {}).get("members") or []:
        if m.get("status") not in (None, "active"):
            continue
        if str(m.get("member_type") or "") != "chronological_event":
            continue
        try:
            eid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        ids.append(eid)
    return ids


def gaps_indicate_incoherence(validated: dict[str, Any] | None) -> bool:
    payload = validated or {}
    blob = _text_blob(payload.get("gaps"), payload.get("summary_stub"))
    return any(n in blob for n in INCOHERENCE_NEEDLES)


def should_split_incoherent_package(
    package: dict[str, Any] | None,
    validated: dict[str, Any] | None,
    *,
    used_fallback: bool = False,
) -> bool:
    """True when research found 2+ unrelated events and should not rework as one packet."""
    if used_fallback:
        return False
    events = active_chronological_event_ids(package)
    if len(events) < 2:
        return False
    meta = (package or {}).get("metadata") or {}
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    temporal = str(meta.get("discovery_source") or "") == "temporal"
    incoherent = gaps_indicate_incoherence(validated)
    insufficient = bool((validated or {}).get("insufficient_evidence"))
    if temporal and (incoherent or insufficient):
        return True
    return incoherent
