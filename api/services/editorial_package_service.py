"""
Editorial package service — the artifact passed between post-processing modals (v11).

Packages hold typed research vs narrative members, links, and an append-only decision log.
Editor publishes news_stories bound to package_id with citations to active members.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_vocab import (
    ALL_MEMBER_TYPES,
    DECISION_ACTIONS,
    INFERENCE_STAGES,
    LINK_TYPES,
    MEMBER_FAMILIES,
    MEMBER_STATUSES,
    NARRATIVE_MEMBER_TYPES,
    PACKAGE_STATUSES,
    PRESENTATION_KINDS,
    RESEARCH_MEMBER_TYPES,
    compute_readiness,
    family_for_member_type,
    provenance_has_citeable_source,
)
from shared.post_processing_modals import allowed_domains_for_modal, normalize_domain_filter

logger = logging.getLogger(__name__)


def _jsonb(val: Any) -> str:
    return json.dumps(val if val is not None else {})


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _append_decision(
    cur,
    *,
    package_id: int,
    action: str,
    actor: str = "operator",
    modal: str | None = None,
    member_id: int | None = None,
    link_id: int | None = None,
    rationale: str | None = None,
    source_refs: dict[str, Any] | None = None,
    model_prompt_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> int:
    if action not in DECISION_ACTIONS:
        raise ValueError(f"Invalid decision action: {action}")
    cur.execute(
        """
        INSERT INTO intelligence.editorial_package_decisions
            (package_id, actor, modal, action, member_id, link_id,
             rationale, source_refs, model_prompt_version, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
        RETURNING id
        """,
        (
            package_id,
            actor,
            modal,
            action,
            member_id,
            link_id,
            rationale,
            _jsonb(source_refs or {}),
            model_prompt_version,
            _jsonb(metadata or {}),
        ),
    )
    return int(cur.fetchone()[0])


def _refresh_readiness(cur, package_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, member_family, member_type, role, status, provenance
        FROM intelligence.editorial_package_members
        WHERE package_id = %s
        """,
        (package_id,),
    )
    members = _rows(cur)
    cur.execute(
        """
        SELECT id, status FROM intelligence.editorial_package_links
        WHERE package_id = %s
        """,
        (package_id,),
    )
    links = _rows(cur)
    cur.execute(
        "SELECT status FROM intelligence.editorial_packages WHERE id = %s",
        (package_id,),
    )
    status_row = cur.fetchone()
    package_status = status_row[0] if status_row else None
    cur.execute(
        """
        SELECT action FROM intelligence.editorial_package_decisions
        WHERE package_id = %s AND action IN ('cleared', 'blocked')
        ORDER BY at DESC, id DESC
        LIMIT 1
        """,
        (package_id,),
    )
    last_reduction = cur.fetchone()
    reduction_cleared = bool(last_reduction and last_reduction[0] == "cleared")
    readiness = compute_readiness(
        members,
        links,
        package_status=package_status,
        reduction_cleared=reduction_cleared,
    )
    cur.execute(
        """
        UPDATE intelligence.editorial_packages
        SET readiness = %s::jsonb, updated_at = NOW()
        WHERE id = %s
        """,
        (_jsonb(readiness), package_id),
    )
    return readiness


def _assert_modal_domain_allowed(added_by_modal: str | None, domain_key: str | None) -> None:
    """Research/Narrative require domain_key on allowlist; editor/reduction allow null domain."""
    modal = (added_by_modal or "").strip().lower()
    if not modal or modal in ("intake", "system"):
        return
    allow = allowed_domains_for_modal(modal)
    if not allow:
        return
    dk = (domain_key or "").strip()
    if not dk:
        if modal in ("editor", "reduction"):
            return
        raise ValueError(f"domain_key required when adding via modal={modal}")
    if dk not in allow:
        raise ValueError(
            f"domain_key={dk!r} not in allowlist for modal={modal}: {allow}"
        )


def _sync_domain_keys(cur, package_id: int) -> list[str]:
    cur.execute(
        """
        SELECT DISTINCT domain_key
        FROM intelligence.editorial_package_members
        WHERE package_id = %s AND status = 'active'
          AND domain_key IS NOT NULL AND domain_key <> ''
        ORDER BY 1
        """,
        (package_id,),
    )
    keys = [r[0] for r in cur.fetchall()]
    cur.execute(
        """
        UPDATE intelligence.editorial_packages
        SET domain_keys = %s::text[], updated_at = NOW()
        WHERE id = %s
        """,
        (keys, package_id),
    )
    return keys


def create_package(
    *,
    working_title: str = "",
    summary_stub: str | None = None,
    primary_modal: str | None = None,
    created_by: str | None = None,
    domain_keys: list[str] | None = None,
    actor: str = "operator",
    metadata: dict[str, Any] | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    if status not in PACKAGE_STATUSES:
        raise ValueError(f"Invalid status: {status}")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.editorial_packages
                    (working_title, summary_stub, status, primary_modal,
                     domain_keys, created_by, metadata)
                VALUES (%s, %s, %s, %s, %s::text[], %s, %s::jsonb)
                RETURNING *
                """,
                (
                    (working_title or "").strip() or "Untitled package",
                    summary_stub,
                    status,
                    primary_modal,
                    domain_keys or [],
                    created_by,
                    _jsonb(metadata or {}),
                ),
            )
            pkg = _row(cur)
            assert pkg is not None
            _append_decision(
                cur,
                package_id=int(pkg["id"]),
                action="package_created",
                actor=actor,
                modal=primary_modal,
                rationale="Package created",
                metadata=metadata or {},
            )
            readiness = _refresh_readiness(cur, int(pkg["id"]))
            conn.commit()
            return {**pkg, "readiness": readiness}


def find_package_by_legacy_seed(legacy_seed: str) -> dict[str, Any] | None:
    """Lookup package by metadata.legacy_seed (migration 286 unique index)."""
    seed = (legacy_seed or "").strip()
    if not seed:
        return None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_packages
                WHERE metadata->>'legacy_seed' = %s
                LIMIT 1
                """,
                (seed,),
            )
            return _row(cur)


def get_package(package_id: int, *, include: bool = True) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.editorial_packages WHERE id = %s",
                (package_id,),
            )
            pkg = _row(cur)
            if not pkg or not include:
                return pkg
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_package_members
                WHERE package_id = %s
                ORDER BY member_family, id
                """,
                (package_id,),
            )
            members = _rows(cur)
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_package_links
                WHERE package_id = %s
                ORDER BY id
                """,
                (package_id,),
            )
            links = _rows(cur)
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_package_decisions
                WHERE package_id = %s
                ORDER BY at DESC, id DESC
                LIMIT 200
                """,
                (package_id,),
            )
            decisions = _rows(cur)
            members = _enrich_member_labels(cur, members)
            return {
                **pkg,
                "members": members,
                "links": links,
                "decisions": decisions,
            }


def _enrich_member_labels(cur, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach display_label from provenance or lightweight source lookups."""
    out: list[dict[str, Any]] = []
    for m in members:
        label = None
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        if prov.get("label"):
            label = str(prov["label"])[:240]
        elif prov.get("quote"):
            label = str(prov["quote"])[:240]
        mt = m.get("member_type")
        mid = m.get("member_id")
        if not label and mt and mid is not None:
            try:
                if mt == "chronological_event":
                    cur.execute(
                        "SELECT title FROM public.chronological_events WHERE id = %s",
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        label = str(r[0])[:240]
                elif mt in ("claim_evidence_appraisal", "hypothesis"):
                    cur.execute(
                        """
                        SELECT COALESCE(NULLIF(hypothesis_text, ''), finding_text)
                        FROM intelligence.claim_evidence_appraisal WHERE id = %s
                        """,
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        label = str(r[0])[:240]
                elif mt == "extracted_claim":
                    cur.execute(
                        """
                        SELECT COALESCE(subject_text, '') || ' ' ||
                               COALESCE(predicate_text, '') || ' ' ||
                               COALESCE(object_text, '')
                        FROM intelligence.extracted_claims WHERE id = %s
                        """,
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0] and str(r[0]).strip():
                        label = str(r[0]).strip()[:240]
                elif mt == "processed_document":
                    cur.execute(
                        "SELECT title FROM intelligence.processed_documents WHERE id = %s",
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        label = str(r[0])[:240]
                elif mt == "versioned_fact":
                    cur.execute(
                        "SELECT fact_text FROM intelligence.versioned_facts WHERE id = %s",
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        label = str(r[0])[:240]
                elif mt == "context":
                    cur.execute(
                        """
                        SELECT COALESCE(title, LEFT(content, 120))
                        FROM intelligence.contexts WHERE id = %s
                        """,
                        (mid,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        label = str(r[0])[:240]
            except Exception as e:  # pragma: no cover
                logger.debug("label enrich skip %s/%s: %s", mt, mid, e)
        out.append({**m, "display_label": label or f"{mt}#{mid}"})
    return out


def list_packages(
    *,
    status: str | None = None,
    domain_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    filters = ["1=1"]
    args: list[Any] = []
    if status:
        if status not in PACKAGE_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        filters.append("status = %s")
        args.append(status)
    if domain_key:
        filters.append("%s = ANY(domain_keys)")
        args.append(domain_key)
    where = " AND ".join(filters)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM intelligence.editorial_packages WHERE {where}",
                args,
            )
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT * FROM intelligence.editorial_packages
                WHERE {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                [*args, int(limit), int(offset)],
            )
            return {"packages": _rows(cur), "total": total}


def update_package(
    package_id: int,
    *,
    working_title: str | None = None,
    summary_stub: str | None = None,
    status: str | None = None,
    presentation_kind: str | None = None,
    primary_modal: str | None = None,
    actor: str = "operator",
    modal: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any] | None:
    sets: list[str] = ["updated_at = NOW()"]
    args: list[Any] = []
    if working_title is not None:
        sets.append("working_title = %s")
        args.append(working_title)
    if summary_stub is not None:
        sets.append("summary_stub = %s")
        args.append(summary_stub)
    if status is not None:
        if status not in PACKAGE_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        sets.append("status = %s")
        args.append(status)
    if presentation_kind is not None:
        if presentation_kind not in PRESENTATION_KINDS:
            raise ValueError(f"Invalid presentation_kind: {presentation_kind}")
        sets.append("presentation_kind = %s")
        args.append(presentation_kind)
    if primary_modal is not None:
        sets.append("primary_modal = %s")
        args.append(primary_modal)
    if len(args) == 0 and working_title is None and summary_stub is None:
        return get_package(package_id, include=False)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE intelligence.editorial_packages
                SET {", ".join(sets)}
                WHERE id = %s
                RETURNING *
                """,
                [*args, package_id],
            )
            pkg = _row(cur)
            if not pkg:
                return None
            if status is not None:
                action = {
                    "ready_for_editor": "ready_for_editor",
                    "blocked": "blocked",
                }.get(status, "status_changed")
                _append_decision(
                    cur,
                    package_id=package_id,
                    action=action,
                    actor=actor,
                    modal=modal,
                    rationale=rationale or f"status={status}",
                    metadata={"status": status},
                )
            if presentation_kind is not None:
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="kind_set",
                    actor=actor,
                    modal=modal or "editor",
                    rationale=rationale or f"presentation_kind={presentation_kind}",
                    metadata={"presentation_kind": presentation_kind},
                )
            readiness = _refresh_readiness(cur, package_id)
            conn.commit()
            return {**pkg, "readiness": readiness}


def add_member(
    package_id: int,
    *,
    member_type: str,
    member_id: int,
    member_family: str | None = None,
    domain_key: str | None = None,
    role: str = "supporting",
    added_by_modal: str | None = None,
    added_by: str | None = None,
    provenance: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    actor: str = "operator",
) -> dict[str, Any]:
    mt = (member_type or "").strip()
    if mt not in ALL_MEMBER_TYPES:
        raise ValueError(f"Invalid member_type: {mt}")
    fam = (member_family or "").strip() or family_for_member_type(mt)
    if not fam:
        raise ValueError("member_family required for ambiguous member_type")
    if fam not in MEMBER_FAMILIES:
        raise ValueError(f"Invalid member_family: {fam}")
    if fam == "research" and mt not in RESEARCH_MEMBER_TYPES:
        raise ValueError(f"{mt} is not a research member type")
    if fam == "narrative" and mt not in NARRATIVE_MEMBER_TYPES:
        raise ValueError(f"{mt} is not a narrative member type")
    _assert_modal_domain_allowed(added_by_modal, domain_key)

    from shared.editorial_package_evidence import hydrate_member_provenance

    provenance = hydrate_member_provenance(
        member_type=mt,
        member_id=int(member_id),
        domain_key=domain_key,
        provenance=provenance,
    )

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM intelligence.editorial_packages WHERE id = %s",
                (package_id,),
            )
            if not cur.fetchone():
                raise LookupError(f"Package {package_id} not found")
            cur.execute(
                """
                INSERT INTO intelligence.editorial_package_members
                    (package_id, member_family, member_type, member_id, domain_key,
                     role, status, added_by_modal, added_by, provenance, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, %s::jsonb, %s::jsonb)
                ON CONFLICT (package_id, member_family, member_type, member_id)
                DO UPDATE SET
                    role = EXCLUDED.role,
                    status = 'active',
                    provenance = EXCLUDED.provenance,
                    metadata = EXCLUDED.metadata,
                    added_by_modal = COALESCE(EXCLUDED.added_by_modal, intelligence.editorial_package_members.added_by_modal),
                    added_at = NOW()
                RETURNING *
                """,
                (
                    package_id,
                    fam,
                    mt,
                    int(member_id),
                    domain_key,
                    role or "supporting",
                    added_by_modal,
                    added_by,
                    _jsonb(provenance or {}),
                    _jsonb(metadata or {}),
                ),
            )
            member = _row(cur)
            assert member is not None
            _append_decision(
                cur,
                package_id=package_id,
                action="member_added",
                actor=actor,
                modal=added_by_modal,
                member_id=int(member["id"]),
                rationale=f"Added {fam}/{mt}:{member_id}",
                source_refs=provenance or {},
            )
            _sync_domain_keys(cur, package_id)
            readiness = _refresh_readiness(cur, package_id)
            conn.commit()
            return {**member, "package_readiness": readiness}


def set_member_status(
    package_id: int,
    member_row_id: int,
    *,
    status: str,
    actor: str = "operator",
    modal: str = "reduction",
    rationale: str | None = None,
) -> dict[str, Any] | None:
    """Set package membership status (active|quarantined|removed).

    ``removed`` / ``quarantined`` only uncouple the member from this package.
    Underlying source rows (articles, events, entities, …) are never deleted.
    """
    if status not in MEMBER_STATUSES:
        raise ValueError(f"Invalid member status: {status}")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_package_members
                SET status = %s
                WHERE id = %s AND package_id = %s
                RETURNING *
                """,
                (status, member_row_id, package_id),
            )
            member = _row(cur)
            if not member:
                return None
            action = (
                "member_quarantined"
                if status == "quarantined"
                else "member_removed"
                if status == "removed"
                else "member_added"
            )
            _append_decision(
                cur,
                package_id=package_id,
                action=action,
                actor=actor,
                modal=modal,
                member_id=member_row_id,
                rationale=rationale or f"member status={status}",
            )
            _sync_domain_keys(cur, package_id)
            readiness = _refresh_readiness(cur, package_id)
            conn.commit()
            return {**member, "package_readiness": readiness}


def add_link(
    package_id: int,
    *,
    from_member_id: int,
    to_member_id: int,
    link_type: str,
    evidence: dict[str, Any] | None = None,
    inference_stage: str = "hypothesized",
    domain_keys: list[str] | None = None,
    actor: str = "operator",
    modal: str | None = None,
) -> dict[str, Any]:
    if link_type not in LINK_TYPES:
        raise ValueError(f"Invalid link_type: {link_type}")
    if inference_stage not in INFERENCE_STAGES:
        raise ValueError(f"Invalid inference_stage: {inference_stage}")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.editorial_package_members
                WHERE package_id = %s AND id IN (%s, %s)
                """,
                (package_id, from_member_id, to_member_id),
            )
            found = {r[0] for r in cur.fetchall()}
            if from_member_id not in found or to_member_id not in found:
                raise ValueError("Both members must belong to the package")
            cur.execute(
                """
                INSERT INTO intelligence.editorial_package_links
                    (package_id, from_member_id, to_member_id, link_type,
                     evidence, inference_stage, domain_keys)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s::text[])
                RETURNING *
                """,
                (
                    package_id,
                    from_member_id,
                    to_member_id,
                    link_type,
                    _jsonb(evidence or {}),
                    inference_stage,
                    domain_keys or [],
                ),
            )
            link = _row(cur)
            assert link is not None
            _append_decision(
                cur,
                package_id=package_id,
                action="link_added",
                actor=actor,
                modal=modal,
                link_id=int(link["id"]),
                rationale=f"link {link_type}",
                source_refs=evidence or {},
            )
            readiness = _refresh_readiness(cur, package_id)
            conn.commit()
            return {**link, "package_readiness": readiness}


def set_link_status(
    package_id: int,
    link_id: int,
    *,
    status: str,
    actor: str = "operator",
    modal: str = "reduction",
    rationale: str | None = None,
) -> dict[str, Any] | None:
    """Set package link status (active|removed). ``removed`` drops the package edge only."""
    if status not in ("active", "removed"):
        raise ValueError("link status must be active|removed")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_package_links
                SET status = %s, updated_at = NOW()
                WHERE id = %s AND package_id = %s
                RETURNING *
                """,
                (status, link_id, package_id),
            )
            link = _row(cur)
            if not link:
                return None
            _append_decision(
                cur,
                package_id=package_id,
                action="link_removed" if status == "removed" else "link_added",
                actor=actor,
                modal=modal,
                link_id=link_id,
                rationale=rationale or f"link status={status}",
            )
            readiness = _refresh_readiness(cur, package_id)
            conn.commit()
            return {**link, "package_readiness": readiness}


def _member_display_label(member: dict[str, Any]) -> str:
    prov = member.get("provenance") if isinstance(member.get("provenance"), dict) else {}
    for key in ("label", "title", "headline"):
        val = str(prov.get(key) or "").strip()
        if val:
            return val
    return str(member.get("member_type") or "member").strip()


def _label_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= 4}


def seed_heuristic_editor_links(
    package_id: int,
    *,
    actor: str = "system",
    max_links: int = 24,
) -> dict[str, Any]:
    """Seed hypothesized connections when Narrative/Research left the graph empty.

    Prefer title-overlapping anchors → supporting articles (corroborates) and
    overlapping core claims (supports). Idempotent when active links already exist.
    """
    pkg = get_package(package_id)
    if not pkg:
        raise LookupError(f"Package {package_id} not found")
    existing = [
        ln
        for ln in (pkg.get("links") or [])
        if (ln.get("status") or "active") == "active"
    ]
    if existing:
        return {"seeded": 0, "skipped": True, "reason": "links_already_present"}

    active = [m for m in (pkg.get("members") or []) if m.get("status") == "active"]
    title_tokens = _label_tokens(str(pkg.get("working_title") or ""))
    stub_tokens = _label_tokens(str(pkg.get("summary_stub") or ""))
    focus_tokens = title_tokens | stub_tokens

    anchors = [
        m
        for m in active
        if m.get("role") == "anchor_event"
        or m.get("member_type") == "chronological_event"
    ]
    articles = [m for m in active if m.get("member_type") == "article"]
    # Prefer explicit supporting articles; fall back to any article.
    supporting_articles = [m for m in articles if m.get("role") == "supporting"] or articles
    claims = [
        m
        for m in active
        if m.get("role") == "core_claim"
        or m.get("member_type")
        in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal", "hypothesis")
    ]

    def _overlap_score(member: dict[str, Any]) -> int:
        return len(_label_tokens(_member_display_label(member)) & focus_tokens)

    anchors_ranked = sorted(anchors, key=_overlap_score, reverse=True)
    primary = [a for a in anchors_ranked if _overlap_score(a) > 0][:3] or anchors_ranked[:2]
    if not primary:
        return {"seeded": 0, "skipped": True, "reason": "no_anchor_members"}

    proposals: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()

    def _propose(frm: int, to: int, link_type: str) -> None:
        if frm == to:
            return
        key = (frm, to)
        if key in seen:
            return
        seen.add(key)
        proposals.append((frm, to, link_type))

    for anchor in primary:
        aid = int(anchor["id"])
        a_tokens = _label_tokens(_member_display_label(anchor)) | focus_tokens
        art_ranked = sorted(
            supporting_articles,
            key=lambda m: len(_label_tokens(_member_display_label(m)) & a_tokens),
            reverse=True,
        )
        for art in art_ranked[:3]:
            _propose(aid, int(art["id"]), "corroborates")
        claim_ranked = sorted(
            claims,
            key=lambda m: len(_label_tokens(_member_display_label(m)) & a_tokens),
            reverse=True,
        )
        for claim in claim_ranked:
            if len(_label_tokens(_member_display_label(claim)) & a_tokens) < 1:
                continue
            _propose(aid, int(claim["id"]), "supports")
            if sum(1 for p in proposals if p[0] == aid and p[2] == "supports") >= 3:
                break
        if len(proposals) >= max_links:
            break

    # Near-in-time among overlapping primary anchors (optional connective tissue).
    for i, left in enumerate(primary):
        for right in primary[i + 1 :]:
            if (
                len(
                    _label_tokens(_member_display_label(left))
                    & _label_tokens(_member_display_label(right))
                )
                >= 2
            ):
                _propose(int(left["id"]), int(right["id"]), "near_in_time")

    seeded = 0
    domain_keys = list(pkg.get("domain_keys") or [])
    for frm, to, link_type in proposals[:max_links]:
        try:
            add_link(
                package_id,
                from_member_id=frm,
                to_member_id=to,
                link_type=link_type,
                evidence={
                    "seeded_by": "editor_scaffold",
                    "heuristic": "title_token_overlap",
                },
                inference_stage="hypothesized",
                domain_keys=domain_keys,
                actor=actor,
                modal="editor",
            )
            seeded += 1
        except Exception as e:
            logger.debug("scaffold link skip %s→%s: %s", frm, to, e)

    return {
        "seeded": seeded,
        "skipped": False,
        "primary_anchor_ids": [int(a["id"]) for a in primary],
        "proposed": len(proposals),
    }


def reduction_clear_or_block(
    package_id: int,
    *,
    clear: bool,
    actor: str = "operator",
    rationale: str | None = None,
) -> dict[str, Any] | None:
    """Reduction clears → ready_for_editor; blocks → blocked + editor alert via handoff."""
    new_status = "ready_for_editor" if clear else "blocked"
    action = "cleared" if clear else "blocked"
    pkg = update_package(
        package_id,
        status=new_status,
        primary_modal="reduction",
        actor=actor,
        modal="reduction",
        rationale=rationale,
    )
    if not pkg:
        return None
    # Re-write decision with cleared/blocked action (update_package already logged status)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            _append_decision(
                cur,
                package_id=package_id,
                action=action,
                actor=actor,
                modal="reduction",
                rationale=rationale or action,
            )
            conn.commit()
    from services.modal_handoff_service import create_handoff, dismiss_open_process_handoffs

    if clear:
        dismiss_open_process_handoffs(
            package_id,
            rationale=rationale or "reduction_cleared",
        )
    create_handoff(
        package_id=package_id,
        source_modal="reduction",
        target_modal="editor",
        reason_code="reduction_cleared" if clear else "reduction_blocked",
        note=rationale,
        created_by=actor,
        domain_keys=list(pkg.get("domain_keys") or []),
    )
    if clear:
        try:
            from services.news_story_service import ensure_editor_scaffold

            ensure_editor_scaffold(package_id, actor=actor)
        except Exception as e:
            logger.warning(
                "ensure_editor_scaffold failed for package %s: %s", package_id, e
            )
    return get_package(package_id)


def close_package_thin(
    package_id: int,
    *,
    actor: str = "operator",
    rationale: str | None = None,
    reason: str = "thin_no_stakes",
    from_modal: str = "reduction",
) -> dict[str, Any] | None:
    """v12 escape: close as closed_thin instead of parking at ready_for_editor."""
    pkg = get_package(package_id, include=False)
    if not pkg:
        return None
    meta = dict(pkg.get("metadata") or {})
    if isinstance(pkg.get("metadata"), str):
        try:
            meta = json.loads(pkg["metadata"])
        except Exception:
            meta = {}
    meta["thin_close"] = {
        "reason": reason,
        "actor": actor,
        "rationale": rationale or reason,
    }
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET status = 'closed_thin',
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (_jsonb({"thin_close": meta["thin_close"]}), package_id),
            )
            row = _row(cur)
            _append_decision(
                cur,
                package_id=package_id,
                action="blocked",
                actor=actor,
                modal=from_modal,
                rationale=rationale or f"closed_thin:{reason}",
                source_refs={"thin_reason": reason},
            )
            conn.commit()
    try:
        from services.modal_handoff_service import dismiss_open_process_handoffs

        dismiss_open_process_handoffs(
            package_id,
            rationale=rationale or f"closed_thin:{reason}",
        )
    except Exception as e:
        logger.warning("dismiss handoffs after thin close failed: %s", e)
    return get_package(package_id) if row else None


def mark_ready_for_editor(
    package_id: int,
    *,
    from_modal: str = "narrative",
    actor: str = "operator",
    rationale: str | None = None,
) -> dict[str, Any] | None:
    pkg = update_package(
        package_id,
        status="ready_for_editor",
        primary_modal=from_modal,
        actor=actor,
        modal=from_modal,
        rationale=rationale,
    )
    if not pkg:
        return None
    from services.modal_handoff_service import create_handoff, dismiss_open_process_handoffs

    dismiss_open_process_handoffs(
        package_id,
        rationale=rationale or "package_ready_for_editor",
    )
    create_handoff(
        package_id=package_id,
        source_modal=from_modal,
        target_modal="editor",
        reason_code="package_ready",
        note=rationale,
        created_by=actor,
        domain_keys=list(pkg.get("domain_keys") or []),
    )
    try:
        from services.news_story_service import ensure_editor_scaffold

        ensure_editor_scaffold(package_id, actor=actor)
    except Exception as e:
        logger.warning("ensure_editor_scaffold failed for package %s: %s", package_id, e)
    return get_package(package_id)


def list_decisions(
    package_id: int,
    *,
    modal: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    filters = ["package_id = %s"]
    args: list[Any] = [package_id]
    if modal:
        filters.append("modal = %s")
        args.append(modal)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM intelligence.editorial_package_decisions
                WHERE {" AND ".join(filters)}
                ORDER BY at DESC, id DESC
                LIMIT %s
                """,
                [*args, int(limit)],
            )
            return _rows(cur)


def audit_replay(package_id: int) -> dict[str, Any]:
    """Retrace package → members → provenance / source refs for anti-hallucination audit."""
    pkg = get_package(package_id)
    if not pkg:
        raise LookupError(f"Package {package_id} not found")
    active = [m for m in pkg.get("members", []) if m.get("status") == "active"]
    chain = []
    for m in active:
        prov = m.get("provenance") or {}
        chain.append(
            {
                "member_row_id": m["id"],
                "member_family": m["member_family"],
                "member_type": m["member_type"],
                "member_id": m["member_id"],
                "domain_key": m.get("domain_key"),
                "role": m.get("role"),
                "source_url": prov.get("source_url") or prov.get("url"),
                "quote": prov.get("quote") or prov.get("quote_span"),
                "evidence_grade": prov.get("evidence_grade"),
                "provenance": prov,
            }
        )
    return {
        "package": {
            "id": pkg["id"],
            "working_title": pkg.get("working_title"),
            "status": pkg.get("status"),
            "presentation_kind": pkg.get("presentation_kind"),
            "readiness": pkg.get("readiness"),
        },
        "citation_eligible_members": chain,
        "decisions": pkg.get("decisions", []),
        "links": [lnk for lnk in pkg.get("links", []) if lnk.get("status") == "active"],
    }


# ---------------------------------------------------------------------------
# Cross-domain search (attach as members)
# ---------------------------------------------------------------------------

def _quote_from_sources(sources: Any) -> tuple[str | None, str | None]:
    """Extract first quote/url from versioned_facts.sources jsonb."""
    if isinstance(sources, dict):
        sources = [sources]
    if not isinstance(sources, list):
        return None, None
    for s in sources:
        if not isinstance(s, dict):
            continue
        url = s.get("url") or s.get("source_url")
        quote = s.get("quote") or s.get("snippet") or s.get("text")
        if url or quote:
            return (str(quote)[:500] if quote else None), (str(url) if url else None)
    return None, None


def search_attachable(
    *,
    modal: str,
    q: str,
    domains: list[str] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """
    Cross-domain search within a modal allowlist.
    Returns attachable hits tagged with suggested member_family/type.
    """
    domain_list = normalize_domain_filter(modal, domains)
    if not domain_list:
        return {"hits": [], "allowed_domains": [], "query": q}
    query = (q or "").strip()
    if len(query) < 2:
        return {"hits": [], "allowed_domains": domain_list, "query": q}

    hits: list[dict[str, Any]] = []
    like = f"%{query}%"
    research_modals = ("research", "reduction", "editor")
    narrative_modals = ("narrative", "reduction", "editor")

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if modal in research_modals:
                # Appraisals (findings)
                try:
                    cur.execute(
                        """
                        SELECT id, domain_key, finding_text AS text, evidence_grade,
                               evidence_quotes, document_id
                        FROM intelligence.claim_evidence_appraisal
                        WHERE domain_key = ANY(%s)
                          AND finding_text ILIKE %s
                        ORDER BY updated_at DESC NULLS LAST, id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, limit),
                    )
                    for r in _rows(cur):
                        quotes = r.get("evidence_quotes") or []
                        quote = None
                        if isinstance(quotes, list) and quotes:
                            first = quotes[0]
                            if isinstance(first, str):
                                quote = first
                            elif isinstance(first, dict):
                                quote = first.get("quote") or first.get("text")
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "claim_evidence_appraisal",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key"),
                                "label": (r.get("text") or "")[:240],
                                "role": "core_claim",
                                "provenance": {
                                    "label": (r.get("text") or "")[:240],
                                    "evidence_grade": r.get("evidence_grade"),
                                    "quote": quote or (r.get("text") or "")[:500],
                                    "document_id": r.get("document_id"),
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search appraisals: %s", e)

                # Hypotheses from appraisals
                try:
                    cur.execute(
                        """
                        SELECT id, domain_key, hypothesis_text, evidence_quotes, document_id
                        FROM intelligence.claim_evidence_appraisal
                        WHERE domain_key = ANY(%s)
                          AND COALESCE(hypothesis_text, '') <> ''
                          AND hypothesis_text ILIKE %s
                        ORDER BY updated_at DESC NULLS LAST, id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, limit),
                    )
                    for r in _rows(cur):
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "hypothesis",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key"),
                                "label": (r.get("hypothesis_text") or "")[:240],
                                "role": "hypothesis",
                                "provenance": {
                                    "label": (r.get("hypothesis_text") or "")[:240],
                                    "quote": (r.get("hypothesis_text") or "")[:500],
                                    "document_id": r.get("document_id"),
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search hypotheses: %s", e)

                try:
                    cur.execute(
                        """
                        SELECT ec.id,
                               COALESCE(ec.subject_text, '') || ' ' ||
                               COALESCE(ec.predicate_text, '') || ' ' ||
                               COALESCE(ec.object_text, '') AS text,
                               ec.context_id,
                               c.domain_key
                        FROM intelligence.extracted_claims ec
                        LEFT JOIN intelligence.contexts c ON c.id = ec.context_id
                        WHERE (c.domain_key = ANY(%s) OR c.domain_key IS NULL)
                          AND (
                            ec.subject_text ILIKE %s
                            OR ec.predicate_text ILIKE %s
                            OR ec.object_text ILIKE %s
                          )
                        ORDER BY ec.id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, like, like, limit),
                    )
                    for r in _rows(cur):
                        text = (r.get("text") or "").strip()
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "extracted_claim",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key"),
                                "label": text[:240],
                                "role": "core_claim",
                                "provenance": {
                                    "label": text[:240],
                                    "quote": text[:500] or None,
                                    "context_id": r.get("context_id"),
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search extracted_claims: %s", e)

                try:
                    cur.execute(
                        """
                        SELECT vf.id, vf.fact_text, vf.sources, ep.domain_key
                        FROM intelligence.versioned_facts vf
                        JOIN intelligence.entity_profiles ep
                          ON ep.id = vf.entity_profile_id
                        WHERE ep.domain_key = ANY(%s)
                          AND vf.fact_text ILIKE %s
                          AND vf.superseded_by_id IS NULL
                        ORDER BY vf.id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, limit),
                    )
                    for r in _rows(cur):
                        quote, url = _quote_from_sources(r.get("sources"))
                        if not quote:
                            quote = (r.get("fact_text") or "")[:500]
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "versioned_fact",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key"),
                                "label": (r.get("fact_text") or "")[:240],
                                "role": "supporting_fact",
                                "provenance": {
                                    "label": (r.get("fact_text") or "")[:240],
                                    "quote": quote,
                                    "source_url": url,
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search versioned_facts: %s", e)

                try:
                    cur.execute(
                        """
                        SELECT id, title, source_url, metadata
                        FROM intelligence.processed_documents
                        WHERE (title ILIKE %s OR COALESCE(source_url, '') ILIKE %s)
                          AND (
                            metadata->>'domain_key' = ANY(%s)
                            OR metadata->>'domain_key' IS NULL
                            OR metadata->>'domain_key' = ''
                          )
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (like, like, domain_list, limit),
                    )
                    for r in _rows(cur):
                        meta = r.get("metadata") if isinstance(r.get("metadata"), dict) else {}
                        dk = meta.get("domain_key") if isinstance(meta, dict) else None
                        if dk and dk not in domain_list:
                            continue
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "processed_document",
                                "member_id": r["id"],
                                "domain_key": dk or (domain_list[0] if domain_list else None),
                                "label": (r.get("title") or "")[:240],
                                "role": "supporting",
                                "provenance": {
                                    "label": (r.get("title") or "")[:240],
                                    "source_url": r.get("source_url"),
                                    # Title alone is not a citeable quote; URL carries citeability.
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search processed_documents: %s", e)

                try:
                    cur.execute(
                        """
                        SELECT id, domain_key, title, LEFT(content, 400) AS snippet
                        FROM intelligence.contexts
                        WHERE domain_key = ANY(%s)
                          AND (title ILIKE %s OR content ILIKE %s)
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, like, limit),
                    )
                    for r in _rows(cur):
                        hits.append(
                            {
                                "member_family": "research",
                                "member_type": "context",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key"),
                                "label": (r.get("title") or r.get("snippet") or "")[:240],
                                "role": "supporting",
                                "provenance": {
                                    "label": (r.get("title") or "")[:240],
                                    # Prefer body snippet; never treat title-as-quote for publish.
                                    "quote": (r.get("snippet") or "")[:500] or None,
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search contexts: %s", e)

                # Per-domain articles
                try:
                    from shared.domain_registry import resolve_domain_schema

                    for dk in domain_list:
                        try:
                            schema = resolve_domain_schema(dk)
                        except Exception:
                            continue
                        cur.execute(
                            f"""
                            SELECT id, title, url
                            FROM {schema}.articles
                            WHERE title ILIKE %s
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (like, max(5, limit // max(1, len(domain_list)))),
                        )
                        for r in _rows(cur):
                            hits.append(
                                {
                                    "member_family": "research",
                                    "member_type": "article",
                                    "member_id": r["id"],
                                    "domain_key": dk,
                                    "label": (r.get("title") or "")[:240],
                                    "role": "supporting",
                                    "provenance": {
                                        "label": (r.get("title") or "")[:240],
                                        "source_url": r.get("url"),
                                        "article_id": r["id"],
                                    },
                                }
                            )
                except Exception as e:
                    logger.debug("search articles: %s", e)

            if modal in narrative_modals:
                try:
                    cur.execute(
                        """
                        SELECT ce.id, ce.title, ce.description, ce.actual_event_date,
                               ce.source_article_id, ce.source_text, ce.location,
                               ce.tags, ce.key_actors
                        FROM public.chronological_events ce
                        WHERE (ce.title ILIKE %s OR ce.description ILIKE %s
                               OR ce.source_text ILIKE %s)
                        ORDER BY ce.actual_event_date DESC NULLS LAST, ce.id DESC
                        LIMIT %s
                        """,
                        (like, like, like, limit * 3),
                    )
                    event_count = 0
                    for r in _rows(cur):
                        tags = r.get("tags") or []
                        if not isinstance(tags, list):
                            tags = []
                        dk = next((d for d in domain_list if d in tags), None)
                        if tags and dk is None and domain_list:
                            tagged_domains = [
                                t
                                for t in tags
                                if t
                                in (
                                    "politics",
                                    "finance",
                                    "legal",
                                    "medicine",
                                    "artificial-intelligence",
                                    "neurodiversity",
                                )
                            ]
                            if tagged_domains and not any(
                                t in domain_list for t in tagged_domains
                            ):
                                continue
                        dk = dk or (domain_list[0] if domain_list else None)
                        source_text = (r.get("source_text") or "").strip()
                        quote = source_text[:500] if source_text else None
                        hits.append(
                            {
                                "member_family": "narrative",
                                "member_type": "chronological_event",
                                "member_id": r["id"],
                                "domain_key": dk,
                                "label": (r.get("title") or r.get("description") or "")[:240],
                                "role": "anchor_event",
                                "provenance": {
                                    "label": (r.get("title") or "")[:240],
                                    "quote": quote,
                                    "article_id": r.get("source_article_id"),
                                    "event_date": str(r["actual_event_date"])
                                    if r.get("actual_event_date")
                                    else None,
                                    "location": r.get("location"),
                                    "key_actors": r.get("key_actors"),
                                },
                            }
                        )
                        # Place / actor hints stay on event provenance only —
                        # do not emit location/entity members keyed by event id.
                        event_count += 1
                        if event_count >= limit:
                            break
                except Exception as e:
                    logger.debug("search chronological_events: %s", e)

                # Entities via story_entity_index
                try:
                    from shared.domain_registry import resolve_domain_schema

                    for dk in domain_list:
                        try:
                            schema = resolve_domain_schema(dk)
                        except Exception:
                            continue
                        cur.execute(
                            f"""
                            SELECT id, entity_name, entity_type
                            FROM {schema}.story_entity_index
                            WHERE entity_name ILIKE %s
                            ORDER BY mention_count DESC NULLS LAST, id DESC
                            LIMIT %s
                            """,
                            (like, max(5, limit // max(1, len(domain_list)))),
                        )
                        for r in _rows(cur):
                            hits.append(
                                {
                                    "member_family": "narrative",
                                    "member_type": "entity",
                                    "member_id": r["id"],
                                    "domain_key": dk,
                                    "label": (r.get("entity_name") or "")[:240],
                                    "role": "actor",
                                    "provenance": {
                                        "label": (r.get("entity_name") or "")[:240],
                                        "entity_type": r.get("entity_type"),
                                        # Entity name alone is not a publishable quote.
                                    },
                                }
                            )
                except Exception as e:
                    logger.debug("search entities: %s", e)

                try:
                    cur.execute(
                        """
                        SELECT id, domain_key, left_kind, left_id, right_kind, right_id,
                               link_role, evidence
                        FROM intelligence.graph_connection_links
                        WHERE status = 'active'
                          AND (domain_key = ANY(%s) OR domain_key IS NULL)
                          AND (
                            link_role ILIKE %s
                            OR evidence::text ILIKE %s
                          )
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (domain_list, like, like, limit),
                    )
                    for r in _rows(cur):
                        label = (
                            f"{r.get('left_kind')}:{r.get('left_id')} "
                            f"—{r.get('link_role')}→ "
                            f"{r.get('right_kind')}:{r.get('right_id')}"
                        )
                        ev = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
                        hits.append(
                            {
                                "member_family": "narrative",
                                "member_type": "graph_link",
                                "member_id": r["id"],
                                "domain_key": r.get("domain_key")
                                or (domain_list[0] if domain_list else None),
                                "label": label[:240],
                                "role": "supporting",
                                "provenance": {
                                    "label": label[:240],
                                    "quote": (ev.get("quote") or None)
                                    if isinstance(ev, dict)
                                    else None,
                                    "source_url": ev.get("url") if isinstance(ev, dict) else None,
                                },
                            }
                        )
                except Exception as e:
                    logger.debug("search graph_links: %s", e)

    return {
        "hits": hits[: limit * 3],
        "allowed_domains": domain_list,
        "query": query,
        "modal": modal,
    }


def attach_search_hits(
    package_id: int,
    hits: list[dict[str, Any]],
    *,
    modal: str,
    actor: str = "operator",
) -> list[dict[str, Any]]:
    added = []
    for h in hits:
        prov = h.get("provenance") if isinstance(h.get("provenance"), dict) else {}
        if h.get("label") and not prov.get("label"):
            prov = {**prov, "label": str(h["label"])[:240]}
        member = add_member(
            package_id,
            member_type=str(h["member_type"]),
            member_id=int(h["member_id"]),
            member_family=str(h.get("member_family") or ""),
            domain_key=h.get("domain_key"),
            role=str(h.get("role") or "supporting"),
            added_by_modal=modal,
            added_by=actor,
            provenance=prov,
            actor=actor,
        )
        added.append(member)
    # Promote draft packages into the modal queue on first attach.
    status_map = {
        "research": "in_research",
        "narrative": "in_narrative",
        "reduction": "in_reduction",
    }
    new_status = status_map.get((modal or "").strip().lower())
    if new_status and added:
        pkg = get_package(package_id, include=False)
        if pkg and pkg.get("status") == "draft":
            try:
                update_package(
                    package_id,
                    status=new_status,
                    primary_modal=modal,
                    actor=actor,
                    modal=modal,
                    rationale=f"promoted from draft on {modal} attach",
                )
            except Exception as e:
                logger.debug("draft promote skipped: %s", e)
    return added


_CITATION_MARKER_RE = re.compile(r"\[@m(\d+)\]")
_MIN_PUBLISH_PROSE_CHARS = 40


def prose_text_without_markers(body_md: str) -> str:
    """Strip citation markers; leftover text is the prose the reader sees."""
    text = _CITATION_MARKER_RE.sub(" ", body_md or "")
    return re.sub(r"\s+", " ", text).strip()


def emit_citation_gap_handoff(
    package_id: int,
    citation_check: dict[str, Any],
    *,
    actor: str = "operator",
) -> None:
    """Open an Editor alert when draft/publish fails the citation gate.

    Idempotent: if an open citation_gap → editor already exists for this package,
    do not create a second alert (avoids system+editor duplicate pairs).
    """
    if citation_check.get("ok"):
        return
    from services.modal_handoff_service import create_handoff, find_open_handoff

    existing = find_open_handoff(
        package_id=package_id,
        target_modal="editor",
        reason_code="citation_gap",
    )
    if existing:
        logger.debug(
            "citation_gap already open for package_id=%s handoff_id=%s — skip emit",
            package_id,
            existing.get("id"),
        )
        return
    create_handoff(
        package_id=package_id,
        source_modal="editor",
        target_modal="editor",
        reason_code="citation_gap",
        note="Citation gate refused markers or body has zero valid citations",
        created_by=actor,
        metadata={
            "refused": citation_check.get("refused") or [],
            "markers": citation_check.get("markers") or [],
        },
    )


def enrich_package_cite_provenance(package_id: int) -> dict[str, int]:
    """
    Fill missing source_url on active members from article_id / context_id.

    Soft claim titles and chronological_events often seed with ids only;
    publish validation requires a URL (or a non-title quote).
    """
    from shared.domain_registry import resolve_domain_schema

    filled = 0
    scanned = 0
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, member_type, domain_key, provenance
                FROM intelligence.editorial_package_members
                WHERE package_id = %s AND status = 'active'
                """,
                (int(package_id),),
            )
            rows = _rows(cur)
            for row in rows:
                scanned += 1
                prov = row.get("provenance")
                if isinstance(prov, str):
                    try:
                        prov = json.loads(prov)
                    except Exception:
                        continue
                if not isinstance(prov, dict):
                    continue
                if provenance_has_citeable_source(prov, for_publish=True):
                    continue
                if (prov.get("source_url") or prov.get("url") or "").strip():
                    continue

                resolved: str | None = None
                article_id = prov.get("article_id")
                domain_key = (row.get("domain_key") or "").strip()

                if article_id is not None and domain_key:
                    schema = resolve_domain_schema(domain_key)
                    if schema:
                        try:
                            cur.execute(
                                f"""
                                SELECT url FROM {schema}.articles
                                WHERE id = %s AND COALESCE(url, '') <> ''
                                LIMIT 1
                                """,
                                (int(article_id),),
                            )
                            hit = cur.fetchone()
                            if hit and hit[0]:
                                resolved = str(hit[0]).strip()
                        except Exception:
                            logger.debug(
                                "cite enrich article lookup failed member=%s",
                                row.get("id"),
                                exc_info=True,
                            )

                if not resolved:
                    ctx_id = prov.get("context_id")
                    if ctx_id is not None:
                        try:
                            cur.execute(
                                """
                                SELECT domain_key, article_id
                                FROM intelligence.article_to_context
                                WHERE context_id = %s
                                LIMIT 1
                                """,
                                (int(ctx_id),),
                            )
                            link = cur.fetchone()
                            if link and link[1] is not None:
                                dk = str(link[0] or domain_key or "").strip()
                                schema = resolve_domain_schema(dk) if dk else None
                                if schema:
                                    cur.execute(
                                        f"""
                                        SELECT url FROM {schema}.articles
                                        WHERE id = %s AND COALESCE(url, '') <> ''
                                        LIMIT 1
                                        """,
                                        (int(link[1]),),
                                    )
                                    hit = cur.fetchone()
                                    if hit and hit[0]:
                                        resolved = str(hit[0]).strip()
                                        if not prov.get("article_id"):
                                            prov["article_id"] = int(link[1])
                        except Exception:
                            logger.debug(
                                "cite enrich context lookup failed member=%s",
                                row.get("id"),
                                exc_info=True,
                            )

                if not resolved:
                    continue
                prov["source_url"] = resolved
                cur.execute(
                    """
                    UPDATE intelligence.editorial_package_members
                    SET provenance = %s::jsonb
                    WHERE id = %s
                    """,
                    (_jsonb(prov), int(row["id"])),
                )
                filled += 1
            if filled:
                _refresh_readiness(cur, int(package_id))
                conn.commit()

    return {"filled": filled, "scanned": scanned}


def validate_prose_citations(
    package_id: int,
    body_md: str,
) -> dict[str, Any]:
    """
    Hallucination gate: every [@mMEMBER_ROW_ID] must resolve to an active member
    with quote or URL provenance. Non-empty body with zero valid citations fails.
    """
    enrich_package_cite_provenance(package_id)
    pkg = get_package(package_id)
    if not pkg:
        raise LookupError(f"Package {package_id} not found")
    active = {
        int(m["id"]): m
        for m in pkg.get("members", [])
        if m.get("status") == "active"
    }
    body = (body_md or "").strip()
    markers = [int(x) for x in _CITATION_MARKER_RE.findall(body_md or "")]
    refused: list[dict[str, Any]] = []
    bound: list[dict[str, Any]] = []
    prose = prose_text_without_markers(body_md or "")
    if body and len(prose) < _MIN_PUBLISH_PROSE_CHARS:
        refused.append(
            {
                "member_row_id": None,
                "reason": "marker_only_body",
                "prose_chars": len(prose),
                "min_required": _MIN_PUBLISH_PROSE_CHARS,
            }
        )
    for mid in markers:
        m = active.get(mid)
        if not m:
            refused.append({"member_row_id": mid, "reason": "not_active_or_missing"})
            continue
        prov = m.get("provenance") or {}
        if not provenance_has_citeable_source(prov, for_publish=True):
            url_s = str(prov.get("source_url") or prov.get("url") or "").strip()
            quote_s = str(prov.get("quote") or prov.get("quote_span") or "").strip()
            label = str(prov.get("label") or "").strip()
            if not url_s and not quote_s:
                reason = "missing_url_and_quote"
            elif not url_s and (quote_s == label or prov.get("quote_is_title") or prov.get("soft_title")):
                reason = "soft_title_needs_url"
            else:
                reason = "missing_quote_or_url"
            refused.append(
                {
                    "member_row_id": mid,
                    "reason": reason,
                    "member_type": m.get("member_type"),
                    "label": label[:120],
                }
            )
            continue
        bound.append({"member_row_id": mid, "member": m})
    if body and not bound:
        if not any(r.get("reason") == "zero_citations" for r in refused):
            refused.append({"member_row_id": None, "reason": "zero_citations"})
    ok = len(refused) == 0 and (not body or bool(bound))
    result = {
        "ok": ok,
        "bound": bound,
        "refused": refused,
        "markers": markers,
        "unsupported_publish": not ok,
        "cite_coverage": round((len(bound) / len(markers)), 4) if markers else 1.0,
    }
    return result


def package_from_selection(
    *,
    working_title: str = "",
    primary_modal: str | None = None,
    domain_keys: list[str] | None = None,
    hits: list[dict[str, Any]],
    modal: str,
    actor: str = "operator",
    created_by: str | None = None,
    package_id: int | None = None,
) -> dict[str, Any]:
    """Create (or reuse) a package and attach selection hits in one call."""
    if package_id:
        pid = int(package_id)
        if not get_package(pid, include=False):
            raise LookupError(f"Package {pid} not found")
    else:
        pkg = create_package(
            working_title=working_title or "Package from selection",
            primary_modal=primary_modal or modal,
            domain_keys=domain_keys,
            created_by=created_by or actor,
            actor=actor,
        )
        pid = int(pkg["id"])
    members = attach_search_hits(pid, hits, modal=modal, actor=actor)
    full = get_package(pid)
    assert full is not None
    return {**full, "attached_members": members}


def ensure_package_from_kernel(
    *,
    domain_key: str | None = None,
    day=None,
    limit: int | None = None,
    actor: str = "act_verb_kernel",
    modal: str = "narrative",
    package_id: int | None = None,
) -> dict[str, Any]:
    """
    v12 THIN: rank act-verb CE for a day and seed a package (clone of package_from_selection).
    """
    from shared.act_verb_kernel import list_act_verb_events_for_day

    events = list_act_verb_events_for_day(
        day=day, domain_key=domain_key, limit=limit
    )
    hits: list[dict[str, Any]] = []
    for ev in events:
        hits.append(
            {
                "member_type": "chronological_event",
                "member_id": int(ev["id"]),
                "label": ev.get("title") or f"event {ev['id']}",
                "score": ev.get("score"),
                "provenance": {
                    "source": "act_verb_kernel",
                    "event_type": ev.get("event_type"),
                    "source_article_id": ev.get("source_article_id"),
                    "url": None,
                },
            }
        )
    title = "Act-verb kernel package"
    if events:
        title = f"Kernel: {str(events[0].get('title') or '')[:80]}"
    dks = [domain_key] if domain_key else None
    if not hits:
        pkg = create_package(
            working_title=title,
            primary_modal=modal,
            domain_keys=dks,
            created_by=actor,
            actor=actor,
        )
        return {**pkg, "attached_members": [], "kernel_events": []}
    out = package_from_selection(
        working_title=title,
        primary_modal=modal,
        domain_keys=dks,
        hits=hits,
        modal=modal,
        actor=actor,
        created_by=actor,
        package_id=package_id,
    )
    out["kernel_events"] = events
    return out


def legacy_seed_for_storyline(domain_key: str, storyline_id: int) -> str:
    """Stable metadata.legacy_seed key (migration 286)."""
    return f"storyline:{(domain_key or '').strip()}:{int(storyline_id)}"


def primary_modal_for_domain(domain_key: str) -> str:
    """Prefer research or narrative rail for a domain tag (not reduction/editor)."""
    from shared.post_processing_modals import domain_in_modal

    dk = (domain_key or "").strip()
    in_research = domain_in_modal(dk, "research")
    in_narrative = domain_in_modal(dk, "narrative")
    if in_research and not in_narrative:
        return "research"
    if in_narrative:
        return "narrative"
    if in_research:
        return "research"
    return "narrative"


def _load_storyline_seed_rows(
    *,
    domain_key: str,
    storyline_id: int,
    max_articles: int,
    max_claims: int,
    max_events: int,
) -> dict[str, Any]:
    """Pull storyline title + attachable members for package seeding."""
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    if not schema:
        raise ValueError(f"Unknown domain_key={domain_key!r}")
    sid = int(storyline_id)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, status
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (sid,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError(f"Storyline {domain_key}/{sid} not found")
            title = (row[1] or f"Storyline {sid}").strip()

            cur.execute(
                f"""
                SELECT a.id, a.title, a.url,
                       LEFT(COALESCE(a.content, a.summary, ''), 400) AS snippet
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                ORDER BY sa.article_id
                LIMIT %s
                """,
                (sid, int(max_articles)),
            )
            articles = [
                {"id": r[0], "title": r[1], "url": r[2], "snippet": r[3]}
                for r in cur.fetchall()
            ]
            article_ids = [int(a["id"]) for a in articles]

            contexts: list[dict[str, Any]] = []
            if article_ids:
                cur.execute(
                    """
                    SELECT DISTINCT c.id, c.title,
                           LEFT(COALESCE(c.content, ''), 400) AS snippet,
                           atc.article_id, c.domain_key
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE atc.domain_key = %s AND atc.article_id = ANY(%s)
                    ORDER BY c.id
                    LIMIT 120
                    """,
                    (domain_key, article_ids),
                )
                contexts = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "snippet": r[2],
                        "article_id": r[3],
                        "domain_key": r[4],
                    }
                    for r in cur.fetchall()
                ]

            context_ids = [int(c["id"]) for c in contexts]
            claims: list[dict[str, Any]] = []
            if context_ids:
                cur.execute(
                    """
                    SELECT ec.id, ec.context_id,
                           COALESCE(ec.subject_text, '') || ' ' ||
                           COALESCE(ec.predicate_text, '') || ' ' ||
                           COALESCE(ec.object_text, '') AS text,
                           ec.confidence
                    FROM intelligence.extracted_claims ec
                    WHERE ec.context_id = ANY(%s)
                    ORDER BY ec.confidence DESC NULLS LAST, ec.id DESC
                    LIMIT %s
                    """,
                    (context_ids, int(max_claims)),
                )
                claims = [
                    {
                        "id": r[0],
                        "context_id": r[1],
                        "text": (r[2] or "").strip(),
                        "confidence": r[3],
                    }
                    for r in cur.fetchall()
                ]

            events: list[dict[str, Any]] = []
            try:
                # storyline_id is varchar; compare as text so empty-string rows do not
                # blow up the query with "invalid input syntax for type integer".
                sid_text = str(sid)
                if article_ids:
                    cur.execute(
                        """
                        SELECT id, title, source_text, source_article_id, location
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                           OR source_article_id = ANY(%s)
                        ORDER BY actual_event_date DESC NULLS LAST, id DESC
                        LIMIT %s
                        """,
                        (sid_text, article_ids, int(max_events)),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, title, source_text, source_article_id, location
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                        ORDER BY actual_event_date DESC NULLS LAST, id DESC
                        LIMIT %s
                        """,
                        (sid_text, int(max_events)),
                    )
                events = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "source_text": r[2],
                        "source_article_id": r[3],
                        "location": r[4],
                    }
                    for r in cur.fetchall()
                ]
            except Exception as e:
                logger.warning("chronological_events lookup skipped: %s", e)

    return {
        "title": title,
        "articles": articles,
        "contexts": contexts,
        "claims": claims,
        "events": events,
    }


def _attach_storyline_seed_members(
    package_id: int,
    *,
    domain_key: str,
    seed: str,
    rows: dict[str, Any],
    actor: str,
    article_family: str,
    modal: str = "intake",
) -> int:
    """Attach articles/contexts/claims/events; returns count of members written.

    ``modal`` should be the destination rail (``research`` / ``narrative``) so a
    draft package is promoted into that queue after the first attach. Legacy
    ``intake`` remains accepted for provenance but does not promote.
    """
    added = 0
    article_urls: dict[int, str] = {
        int(a["id"]): (a.get("url") or "").strip()
        for a in (rows.get("articles") or [])
        if a.get("id") is not None and (a.get("url") or "").strip()
    }
    ctx_article: dict[int, int] = {
        int(c["id"]): int(c["article_id"])
        for c in (rows.get("contexts") or [])
        if c.get("id") is not None and c.get("article_id") is not None
    }

    for a in rows.get("articles") or []:
        url = (a.get("url") or "").strip()
        if not url:
            continue
        add_member(
            package_id,
            member_type="article",
            member_id=int(a["id"]),
            member_family=article_family,
            domain_key=domain_key,
            role="supporting",
            added_by_modal=modal,
            added_by=actor,
            provenance={
                "label": (a.get("title") or "")[:240],
                "source_url": url,
                "quote": (a.get("snippet") or "").strip()[:500] or None,
                "article_id": a["id"],
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for c in rows.get("contexts") or []:
        aid = c.get("article_id")
        url = article_urls.get(int(aid), "") if aid is not None else ""
        add_member(
            package_id,
            member_type="context",
            member_id=int(c["id"]),
            member_family=article_family,
            domain_key=c.get("domain_key") or domain_key,
            role="supporting",
            added_by_modal=modal,
            added_by=actor,
            provenance={
                "label": (c.get("title") or "")[:240],
                "quote": (c.get("snippet") or "").strip()[:500] or None,
                "article_id": aid,
                "source_url": url or None,
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for cl in rows.get("claims") or []:
        ctx_id = cl.get("context_id")
        aid = ctx_article.get(int(ctx_id)) if ctx_id is not None else None
        url = article_urls.get(int(aid), "") if aid is not None else ""
        add_member(
            package_id,
            member_type="extracted_claim",
            member_id=int(cl["id"]),
            member_family="research",
            domain_key=domain_key,
            role="core_claim",
            added_by_modal=modal,
            added_by=actor,
            provenance={
                "label": (cl.get("text") or "")[:240],
                "quote": (cl.get("text") or "")[:500] or None,
                "context_id": ctx_id,
                "article_id": aid,
                "source_url": url or None,
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for ev in rows.get("events") or []:
        quote = (ev.get("source_text") or "").strip()[:500] or None
        aid = ev.get("source_article_id")
        url = article_urls.get(int(aid), "") if aid is not None else ""
        add_member(
            package_id,
            member_type="chronological_event",
            member_id=int(ev["id"]),
            member_family="narrative",
            domain_key=domain_key,
            role="anchor_event",
            added_by_modal=modal,
            added_by=actor,
            provenance={
                "label": (ev.get("title") or "")[:240],
                "quote": quote,
                "article_id": aid,
                "source_url": url or None,
                "location": ev.get("location"),
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    # Promote draft into the rail queue even when members were added via add_member
    # (attach_search_hits already does this; seed path needs the same).
    status_map = {
        "research": "in_research",
        "narrative": "in_narrative",
        "reduction": "in_reduction",
    }
    new_status = status_map.get((modal or "").strip().lower())
    if new_status and added:
        pkg = get_package(package_id, include=False)
        if pkg and pkg.get("status") == "draft":
            try:
                update_package(
                    package_id,
                    status=new_status,
                    primary_modal=modal,
                    actor=actor,
                    modal=modal,
                    rationale=f"promoted from draft on {modal} storyline seed",
                )
            except Exception as e:
                logger.debug("storyline seed promote skipped: %s", e)
    return added


def ensure_package_from_storyline(
    *,
    domain_key: str,
    storyline_id: int,
    target_modal: str | None = None,
    actor: str = "operator",
    refresh_members: bool = False,
    max_articles: int = 80,
    max_claims: int = 40,
    max_events: int = 50,
) -> dict[str, Any]:
    """Find or create an editorial_package linked via metadata.legacy_seed.

    Seeds members from storyline articles / contexts / claims / chronological
    events (same shape as legacy backfill). Existing packages are returned as-is
    unless refresh_members=True.
    """
    dk = (domain_key or "").strip()
    if not dk:
        raise ValueError("domain_key required")
    sid = int(storyline_id)
    seed = legacy_seed_for_storyline(dk, sid)

    modal = (target_modal or "").strip().lower() or primary_modal_for_domain(dk)
    if modal not in ("research", "narrative", "reduction", "editor", "intake"):
        raise ValueError("target_modal must be research|narrative|reduction|editor")
    # Packages should open on research/narrative rails; reduction/editor keep rail.
    create_modal = modal if modal in ("research", "narrative") else primary_modal_for_domain(dk)
    article_family = "research" if create_modal == "research" else "narrative"

    existing = find_package_by_legacy_seed(seed)
    created = False
    members_added = 0

    if existing:
        package_id = int(existing["id"])
        if refresh_members:
            rows = _load_storyline_seed_rows(
                domain_key=dk,
                storyline_id=sid,
                max_articles=max_articles,
                max_claims=max_claims,
                max_events=max_events,
            )
            members_added = _attach_storyline_seed_members(
                package_id,
                domain_key=dk,
                seed=seed,
                rows=rows,
                actor=actor,
                article_family=article_family,
                modal=create_modal,
            )
    else:
        rows = _load_storyline_seed_rows(
            domain_key=dk,
            storyline_id=sid,
            max_articles=max_articles,
            max_claims=max_claims,
            max_events=max_events,
        )
        try:
            pkg = create_package(
                working_title=(rows["title"] or f"Storyline {sid}")[:500],
                summary_stub=f"From {dk} storyline {sid}",
                primary_modal=create_modal,
                created_by=actor,
                domain_keys=[dk],
                actor=actor,
                metadata={
                    "legacy_seed": seed,
                    "source_storyline_id": sid,
                    "source_domain_key": dk,
                    "seeded_by": "storyline_bridge",
                },
                status="draft",
            )
            package_id = int(pkg["id"])
            created = True
        except Exception as e:
            # Concurrent create on unique legacy_seed — reuse winner.
            raced = find_package_by_legacy_seed(seed)
            if not raced:
                raise
            logger.info(
                "ensure_package_from_storyline race on %s; reusing package %s (%s)",
                seed,
                raced.get("id"),
                e,
            )
            package_id = int(raced["id"])
            created = False

        members_added = _attach_storyline_seed_members(
            package_id,
            domain_key=dk,
            seed=seed,
            rows=rows,
            actor=actor,
            article_family=article_family,
            modal=create_modal,
        )

    full = get_package(package_id)
    assert full is not None
    out = {
        **full,
        "created": created,
        "legacy_seed": seed,
        "source_storyline_id": sid,
        "source_domain_key": dk,
        "members_added": members_added,
        "suggested_modal": modal,
    }
    # Published product: append newly attached members into the news_story and
    # stay published — do not bounce through Research/Narrative/Reduction.
    try:
        from services.news_story_service import auto_republish_for_new_members

        out["auto_republish"] = auto_republish_for_new_members(
            package_id,
            actor=actor,
        )
    except Exception as e:
        logger.warning(
            "auto_republish after storyline seed failed package=%s: %s",
            package_id,
            e,
        )
        out["auto_republish"] = {"skipped": True, "reason": "error", "error": str(e)}
    return out


def legacy_seed_for_entity(domain_key: str, canonical_entity_id: int) -> str:
    """Stable metadata.legacy_seed for entity Research packages (knowledge profiles)."""
    return f"entity:{(domain_key or '').strip()}:{int(canonical_entity_id)}"


def _load_entity_seed_rows(
    *,
    domain_key: str,
    canonical_entity_id: int,
    entity_name: str,
    max_appraisals: int,
    max_documents: int,
    max_articles: int,
    max_claims: int,
) -> dict[str, Any]:
    """Pull appraisals / docs / articles / claims matching the research entity."""
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    if not schema:
        raise ValueError(f"Unknown domain_key={domain_key!r}")
    eid = int(canonical_entity_id)
    name = (entity_name or "").strip()
    pattern = f"%{name}%" if name else None

    appraisals: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    versioned_facts: list[dict[str, Any]] = []

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Articles linked via domain article_entities
            try:
                cur.execute(
                    f"""
                    SELECT DISTINCT a.id, a.title, a.url,
                           LEFT(COALESCE(a.content, a.summary, ''), 400) AS snippet
                    FROM {schema}.article_entities ae
                    JOIN {schema}.articles a ON a.id = ae.article_id
                    WHERE ae.canonical_entity_id = %s
                       OR (
                            %s IS NOT NULL
                            AND (
                                lower(COALESCE(ae.entity_name, '')) = lower(%s)
                                OR lower(COALESCE(a.title, '')) LIKE lower(%s)
                            )
                       )
                    ORDER BY a.id DESC
                    LIMIT %s
                    """,
                    (eid, name or None, name or "", pattern or "", int(max_articles)),
                )
                articles = [
                    {"id": r[0], "title": r[1], "url": r[2], "snippet": r[3]}
                    for r in cur.fetchall()
                ]
            except Exception as e:
                logger.warning("entity seed articles skipped: %s", e)
                # Fallback: title ILIKE only
                if pattern:
                    try:
                        cur.execute(
                            f"""
                            SELECT id, title, url,
                                   LEFT(COALESCE(content, summary, ''), 400) AS snippet
                            FROM {schema}.articles
                            WHERE lower(COALESCE(title, '')) LIKE lower(%s)
                               OR lower(COALESCE(summary, '')) LIKE lower(%s)
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (pattern, pattern, int(max_articles)),
                        )
                        articles = [
                            {"id": r[0], "title": r[1], "url": r[2], "snippet": r[3]}
                            for r in cur.fetchall()
                        ]
                    except Exception as e2:
                        logger.warning("entity seed article title fallback skipped: %s", e2)

            article_ids = [int(a["id"]) for a in articles]

            # Appraisals by domain + text / article match
            try:
                if article_ids and pattern:
                    cur.execute(
                        """
                        SELECT id, finding_text, hypothesis_text, evidence_grade,
                               replication_status, paper_support, document_id,
                               article_id, evidence_quotes, limitations_quote
                        FROM intelligence.claim_evidence_appraisal
                        WHERE domain_key = %s
                          AND (
                                article_id = ANY(%s)
                                OR lower(COALESCE(finding_text, '')) LIKE lower(%s)
                                OR lower(COALESCE(hypothesis_text, '')) LIKE lower(%s)
                          )
                        ORDER BY
                          CASE evidence_grade
                            WHEN 'strong' THEN 1
                            WHEN 'moderate' THEN 2
                            WHEN 'limited' THEN 3
                            ELSE 4
                          END,
                          id DESC
                        LIMIT %s
                        """,
                        (domain_key, article_ids, pattern, pattern, int(max_appraisals)),
                    )
                elif pattern:
                    cur.execute(
                        """
                        SELECT id, finding_text, hypothesis_text, evidence_grade,
                               replication_status, paper_support, document_id,
                               article_id, evidence_quotes, limitations_quote
                        FROM intelligence.claim_evidence_appraisal
                        WHERE domain_key = %s
                          AND (
                                lower(COALESCE(finding_text, '')) LIKE lower(%s)
                                OR lower(COALESCE(hypothesis_text, '')) LIKE lower(%s)
                          )
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (domain_key, pattern, pattern, int(max_appraisals)),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, finding_text, hypothesis_text, evidence_grade,
                               replication_status, paper_support, document_id,
                               article_id, evidence_quotes, limitations_quote
                        FROM intelligence.claim_evidence_appraisal
                        WHERE domain_key = %s
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (domain_key, int(max_appraisals)),
                    )
                for r in cur.fetchall():
                    quote = None
                    eq = r[8]
                    if isinstance(eq, list) and eq:
                        first = eq[0]
                        quote = (
                            str(first.get("quote") or first.get("text") or first)
                            if isinstance(first, dict)
                            else str(first)
                        )
                    elif isinstance(eq, str):
                        quote = eq
                    quote = (quote or r[9] or "")[:500] or None
                    appraisals.append(
                        {
                            "id": r[0],
                            "finding_text": r[1],
                            "hypothesis_text": r[2],
                            "evidence_grade": r[3],
                            "replication_status": r[4],
                            "paper_support": r[5],
                            "document_id": r[6],
                            "article_id": r[7],
                            "quote": quote,
                        }
                    )
            except Exception as e:
                logger.warning("entity seed appraisals skipped: %s", e)

            doc_ids = [
                int(a["document_id"])
                for a in appraisals
                if a.get("document_id") is not None
            ]
            try:
                if doc_ids or pattern:
                    if doc_ids and pattern:
                        cur.execute(
                            """
                            SELECT id, title, source_url,
                                   LEFT(COALESCE(title, ''), 400) AS snippet
                            FROM intelligence.processed_documents
                            WHERE id = ANY(%s)
                               OR lower(COALESCE(title, '')) LIKE lower(%s)
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (doc_ids, pattern, int(max_documents)),
                        )
                    elif doc_ids:
                        cur.execute(
                            """
                            SELECT id, title, source_url,
                                   LEFT(COALESCE(title, ''), 400) AS snippet
                            FROM intelligence.processed_documents
                            WHERE id = ANY(%s)
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (doc_ids, int(max_documents)),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT id, title, source_url,
                                   LEFT(COALESCE(title, ''), 400) AS snippet
                            FROM intelligence.processed_documents
                            WHERE lower(COALESCE(title, '')) LIKE lower(%s)
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (pattern, int(max_documents)),
                        )
                    documents = [
                        {
                            "id": r[0],
                            "title": r[1],
                            "url": r[2],
                            "snippet": r[3],
                        }
                        for r in cur.fetchall()
                    ]
            except Exception as e:
                logger.warning("entity seed documents skipped: %s", e)

            if article_ids:
                try:
                    cur.execute(
                        """
                        SELECT DISTINCT ec.id, ec.context_id,
                               COALESCE(ec.subject_text, '') || ' ' ||
                               COALESCE(ec.predicate_text, '') || ' ' ||
                               COALESCE(ec.object_text, '') AS text,
                               ec.confidence, atc.article_id
                        FROM intelligence.article_to_context atc
                        JOIN intelligence.extracted_claims ec
                          ON ec.context_id = atc.context_id
                        WHERE atc.domain_key = %s AND atc.article_id = ANY(%s)
                        ORDER BY ec.confidence DESC NULLS LAST, ec.id DESC
                        LIMIT %s
                        """,
                        (domain_key, article_ids, int(max_claims)),
                    )
                    claims = [
                        {
                            "id": r[0],
                            "context_id": r[1],
                            "text": (r[2] or "").strip(),
                            "confidence": r[3],
                            "article_id": r[4],
                        }
                        for r in cur.fetchall()
                    ]
                except Exception as e:
                    logger.warning("entity seed claims skipped: %s", e)

            if pattern:
                try:
                    cur.execute(
                        """
                        SELECT id, fact_text, sources
                        FROM intelligence.versioned_facts
                        WHERE lower(COALESCE(fact_text, '')) LIKE lower(%s)
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (pattern, int(max_claims)),
                    )
                    for r in cur.fetchall():
                        sources = r[2] if isinstance(r[2], dict) else {}
                        versioned_facts.append(
                            {
                                "id": r[0],
                                "text": r[1],
                                "article_id": sources.get("article_id"),
                                "url": sources.get("source_url") or sources.get("url"),
                            }
                        )
                except Exception as e:
                    logger.debug("entity seed versioned_facts skipped: %s", e)

    return {
        "title": name or f"Entity {eid}",
        "articles": articles,
        "appraisals": appraisals,
        "documents": documents,
        "claims": claims,
        "versioned_facts": versioned_facts,
    }


def _attach_entity_seed_members(
    package_id: int,
    *,
    domain_key: str,
    seed: str,
    rows: dict[str, Any],
    actor: str,
) -> int:
    """Attach research members for an entity package; promote draft → in_research."""
    added = 0
    article_urls: dict[int, str] = {
        int(a["id"]): (a.get("url") or "").strip()
        for a in (rows.get("articles") or [])
        if a.get("id") is not None and (a.get("url") or "").strip()
    }

    for a in rows.get("articles") or []:
        url = (a.get("url") or "").strip()
        if not url:
            continue
        add_member(
            package_id,
            member_type="article",
            member_id=int(a["id"]),
            member_family="research",
            domain_key=domain_key,
            role="supporting",
            added_by_modal="research",
            added_by=actor,
            provenance={
                "label": (a.get("title") or "")[:240],
                "source_url": url,
                "quote": (a.get("snippet") or "").strip()[:500] or None,
                "article_id": a["id"],
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for d in rows.get("documents") or []:
        add_member(
            package_id,
            member_type="processed_document",
            member_id=int(d["id"]),
            member_family="research",
            domain_key=domain_key,
            role="supporting",
            added_by_modal="research",
            added_by=actor,
            provenance={
                "label": (d.get("title") or "")[:240],
                "source_url": (d.get("url") or "").strip() or None,
                "quote": (d.get("snippet") or "").strip()[:500] or None,
                "document_id": d["id"],
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for ap in rows.get("appraisals") or []:
        aid = ap.get("article_id")
        url = article_urls.get(int(aid), "") if aid is not None else ""
        text = (ap.get("finding_text") or ap.get("hypothesis_text") or "")[:240]
        add_member(
            package_id,
            member_type="claim_evidence_appraisal",
            member_id=int(ap["id"]),
            member_family="research",
            domain_key=domain_key,
            role="core_claim",
            added_by_modal="research",
            added_by=actor,
            provenance={
                "label": text,
                "quote": ap.get("quote"),
                "source_url": url or None,
                "article_id": aid,
                "document_id": ap.get("document_id"),
                "evidence_grade": ap.get("evidence_grade"),
                "verdict": ap.get("replication_status"),
                "paper_support": ap.get("paper_support"),
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for cl in rows.get("claims") or []:
        aid = cl.get("article_id")
        url = article_urls.get(int(aid), "") if aid is not None else ""
        add_member(
            package_id,
            member_type="extracted_claim",
            member_id=int(cl["id"]),
            member_family="research",
            domain_key=domain_key,
            role="supporting",
            added_by_modal="research",
            added_by=actor,
            provenance={
                "label": (cl.get("text") or "")[:240],
                "quote": (cl.get("text") or "")[:500] or None,
                "context_id": cl.get("context_id"),
                "article_id": aid,
                "source_url": url or None,
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    for vf in rows.get("versioned_facts") or []:
        aid = vf.get("article_id")
        url = (vf.get("url") or "").strip() or (
            article_urls.get(int(aid), "") if aid is not None else ""
        )
        add_member(
            package_id,
            member_type="versioned_fact",
            member_id=int(vf["id"]),
            member_family="research",
            domain_key=domain_key,
            role="core_claim",
            added_by_modal="research",
            added_by=actor,
            provenance={
                "label": (vf.get("text") or "")[:240],
                "quote": (vf.get("text") or "")[:500] or None,
                "article_id": aid,
                "source_url": url or None,
                "legacy_seed": seed,
            },
            actor=actor,
        )
        added += 1

    if added:
        pkg = get_package(package_id, include=False)
        if pkg and pkg.get("status") == "draft":
            try:
                update_package(
                    package_id,
                    status="in_research",
                    primary_modal="research",
                    actor=actor,
                    modal="research",
                    rationale="promoted from draft on entity research seed",
                )
            except Exception as e:
                logger.debug("entity seed promote skipped: %s", e)
    return added


def ensure_package_from_entity(
    *,
    domain_key: str,
    canonical_entity_id: int,
    actor: str = "operator",
    refresh_members: bool = False,
    max_appraisals: int = 40,
    max_documents: int = 40,
    max_articles: int = 60,
    max_claims: int = 40,
) -> dict[str, Any]:
    """Find or create an editorial_package seeded for a research entity.

    Uses metadata.legacy_seed = entity:{domain_key}:{canonical_entity_id}.
    Promotes to in_research. Does not require Reduction/Editor for knowledge
    profile merge (handled by knowledge_profile_service.auto_merge_from_package).
    """
    from shared.domain_registry import resolve_domain_schema
    from services.knowledge_profile_service import (
        KNOWLEDGE_PROFILE_DOMAINS,
        get_or_create_profile,
    )

    dk = (domain_key or "").strip()
    if dk not in KNOWLEDGE_PROFILE_DOMAINS:
        raise ValueError(
            f"domain_key must be one of {sorted(KNOWLEDGE_PROFILE_DOMAINS)}"
        )
    eid = int(canonical_entity_id)
    seed = legacy_seed_for_entity(dk, eid)

    schema = resolve_domain_schema(dk)
    if not schema:
        raise ValueError(f"Unknown domain_key={dk!r}")

    entity_name = f"Entity {eid}"
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name FROM {schema}.entity_canonical
                WHERE id = %s
                """,
                (eid,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError(f"Entity {dk}/{eid} not found")
            entity_name = (row[1] or entity_name).strip()

    existing = find_package_by_legacy_seed(seed)
    created = False
    members_added = 0

    rows = None
    if existing and not refresh_members:
        package_id = int(existing["id"])
    else:
        rows = _load_entity_seed_rows(
            domain_key=dk,
            canonical_entity_id=eid,
            entity_name=entity_name,
            max_appraisals=max_appraisals,
            max_documents=max_documents,
            max_articles=max_articles,
            max_claims=max_claims,
        )
        if existing:
            package_id = int(existing["id"])
            members_added = _attach_entity_seed_members(
                package_id,
                domain_key=dk,
                seed=seed,
                rows=rows,
                actor=actor,
            )
        else:
            try:
                pkg = create_package(
                    working_title=(entity_name or f"Entity {eid}")[:500],
                    summary_stub=f"Research package for {dk} entity {eid} ({entity_name})",
                    primary_modal="research",
                    created_by=actor,
                    domain_keys=[dk],
                    actor=actor,
                    metadata={
                        "legacy_seed": seed,
                        "source_canonical_entity_id": eid,
                        "source_domain_key": dk,
                        "seeded_by": "entity_bridge",
                    },
                    status="draft",
                )
                package_id = int(pkg["id"])
                created = True
            except Exception as e:
                raced = find_package_by_legacy_seed(seed)
                if not raced:
                    raise
                logger.info(
                    "ensure_package_from_entity race on %s; reusing package %s (%s)",
                    seed,
                    raced.get("id"),
                    e,
                )
                package_id = int(raced["id"])
                created = False

            members_added = _attach_entity_seed_members(
                package_id,
                domain_key=dk,
                seed=seed,
                rows=rows,
                actor=actor,
            )

    profile = get_or_create_profile(
        dk,
        eid,
        title=entity_name,
        package_id=package_id,
        actor=actor,
    )

    full = get_package(package_id)
    assert full is not None
    return {
        **full,
        "created": created,
        "legacy_seed": seed,
        "source_canonical_entity_id": eid,
        "source_domain_key": dk,
        "entity_name": entity_name,
        "members_added": members_added,
        "suggested_modal": "research",
        "knowledge_profile_id": int(profile["id"]),
    }
