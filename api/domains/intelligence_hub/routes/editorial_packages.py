"""
Editorial packages, modal handoffs, news stories API (v11).

Routes under /api/editorial/...
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query

from shared.post_processing_modals import list_modals, allowed_domains_for_modal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/editorial", tags=["Editorial packages"])


def _ok(data: Any, message: str | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def _err(message: str, status: int = 400) -> None:
    raise HTTPException(status_code=status, detail=message)


@router.get("/modals")
def get_modals_catalog() -> dict[str, Any]:
    return _ok({"modals": list_modals()})


@router.post("/packages/from_selection")
def api_package_from_selection(
    hits: list[dict[str, Any]] = Body(...),
    modal: str = Body(...),
    working_title: str = Body(""),
    domain_keys: list[str] | None = Body(None),
    package_id: int | None = Body(None),
    actor: str = Body("operator"),
    created_by: str | None = Body(None),
) -> dict[str, Any]:
    from services.editorial_package_service import package_from_selection

    if modal not in ("research", "narrative", "reduction", "editor"):
        _err("modal must be research|narrative|reduction|editor")
    if not hits:
        _err("hits required")
    try:
        result = package_from_selection(
            working_title=working_title,
            primary_modal=modal,
            domain_keys=domain_keys,
            hits=hits,
            modal=modal,
            actor=actor,
            created_by=created_by,
            package_id=package_id,
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    return _ok(result)


@router.post("/packages/from_kernel")
def api_package_from_kernel(
    domain_key: str | None = Body(None),
    day: str | None = Body(None),
    limit: int | None = Body(None),
    modal: str = Body("narrative"),
    actor: str = Body("act_verb_kernel"),
    package_id: int | None = Body(None),
    dry_run: bool = Body(False),
) -> dict[str, Any]:
    """v12 THIN: seed a package from act-verb chronological_events top-K."""
    from datetime import date as date_cls

    from services.editorial_package_service import ensure_package_from_kernel
    from shared.act_verb_kernel import list_act_verb_events_for_day

    if modal not in ("research", "narrative", "reduction", "editor"):
        _err("modal must be research|narrative|reduction|editor")
    day_obj = None
    if day:
        try:
            day_obj = date_cls.fromisoformat(str(day)[:10])
        except ValueError:
            _err("day must be YYYY-MM-DD")
    if dry_run:
        events = list_act_verb_events_for_day(
            day=day_obj, domain_key=domain_key, limit=limit
        )
        return _ok(
            {
                "dry_run": True,
                "count": len(events),
                "kernel_events": events,
            }
        )
    try:
        result = ensure_package_from_kernel(
            domain_key=domain_key,
            day=day_obj,
            limit=limit,
            actor=actor,
            modal=modal,
            package_id=package_id,
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    return _ok(result)


@router.post("/packages/from_storyline")
def api_package_from_storyline(
    domain_key: str = Body(...),
    storyline_id: int = Body(..., ge=1),
    target_modal: str | None = Body(None),
    actor: str = Body("operator"),
    refresh_members: bool = Body(False),
) -> dict[str, Any]:
    """Find or create an editorial_package for a storyline (metadata.legacy_seed)."""
    from services.editorial_package_service import ensure_package_from_storyline

    modal = (target_modal or "").strip().lower() or None
    if modal and modal not in ("research", "narrative", "reduction", "editor"):
        _err("target_modal must be research|narrative|reduction|editor")
    try:
        result = ensure_package_from_storyline(
            domain_key=domain_key,
            storyline_id=storyline_id,
            target_modal=modal,
            actor=actor,
            refresh_members=bool(refresh_members),
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    return _ok(result)


@router.get("/packages/by_legacy_seed")
def api_package_by_legacy_seed(
    seed: str = Query(..., min_length=3, max_length=200),
) -> dict[str, Any]:
    """Lookup package by metadata.legacy_seed (e.g. storyline:politics:42)."""
    from services.editorial_package_service import find_package_by_legacy_seed, get_package

    pkg = find_package_by_legacy_seed(seed.strip())
    if not pkg:
        _err("Package not found", 404)
    full = get_package(int(pkg["id"]))
    return _ok(full or pkg)


@router.get("/packages")
def api_list_packages(
    status: str | None = Query(None),
    domain_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    from services.editorial_package_service import list_packages

    try:
        return _ok(list_packages(status=status, domain_key=domain_key, limit=limit, offset=offset))
    except ValueError as e:
        _err(str(e))


@router.post("/packages")
def api_create_package(
    working_title: str = Body(""),
    summary_stub: str | None = Body(None),
    primary_modal: str | None = Body(None),
    created_by: str | None = Body(None),
    domain_keys: list[str] | None = Body(None),
    status: str = Body("draft"),
) -> dict[str, Any]:
    from services.editorial_package_service import create_package

    try:
        pkg = create_package(
            working_title=working_title,
            summary_stub=summary_stub,
            primary_modal=primary_modal,
            created_by=created_by,
            domain_keys=domain_keys,
            status=status,
        )
    except ValueError as e:
        _err(str(e))
    return _ok(pkg)


@router.get("/packages/{package_id}")
def api_get_package(package_id: int = Path(..., ge=1)) -> dict[str, Any]:
    from services.editorial_package_service import get_package

    pkg = get_package(package_id)
    if not pkg:
        _err("Package not found", 404)
    return _ok(pkg)


@router.patch("/packages/{package_id}")
def api_patch_package(
    package_id: int,
    working_title: str | None = Body(None),
    summary_stub: str | None = Body(None),
    status: str | None = Body(None),
    presentation_kind: str | None = Body(None),
    primary_modal: str | None = Body(None),
    actor: str = Body("operator"),
    modal: str | None = Body(None),
    rationale: str | None = Body(None),
) -> dict[str, Any]:
    from services.editorial_package_service import update_package

    try:
        pkg = update_package(
            package_id,
            working_title=working_title,
            summary_stub=summary_stub,
            status=status,
            presentation_kind=presentation_kind,
            primary_modal=primary_modal,
            actor=actor,
            modal=modal,
            rationale=rationale,
        )
    except ValueError as e:
        _err(str(e))
    if not pkg:
        _err("Package not found", 404)
    return _ok(pkg)


@router.post("/packages/{package_id}/members")
def api_add_member(
    package_id: int,
    member_type: str = Body(...),
    member_id: int = Body(...),
    member_family: str | None = Body(None),
    domain_key: str | None = Body(None),
    role: str = Body("supporting"),
    added_by_modal: str | None = Body(None),
    added_by: str | None = Body(None),
    provenance: dict[str, Any] | None = Body(None),
    metadata: dict[str, Any] | None = Body(None),
    actor: str = Body("operator"),
) -> dict[str, Any]:
    from services.editorial_package_service import add_member

    try:
        member = add_member(
            package_id,
            member_type=member_type,
            member_id=member_id,
            member_family=member_family,
            domain_key=domain_key,
            role=role,
            added_by_modal=added_by_modal,
            added_by=added_by,
            provenance=provenance,
            metadata=metadata,
            actor=actor,
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    return _ok(member)


@router.patch("/packages/{package_id}/members/{member_row_id}")
def api_set_member_status(
    package_id: int,
    member_row_id: int,
    status: str = Body(..., embed=True),
    actor: str = Body("operator", embed=True),
    modal: str = Body("reduction", embed=True),
    rationale: str | None = Body(None, embed=True),
) -> dict[str, Any]:
    from services.editorial_package_service import set_member_status

    try:
        member = set_member_status(
            package_id,
            member_row_id,
            status=status,
            actor=actor,
            modal=modal,
            rationale=rationale,
        )
    except ValueError as e:
        _err(str(e))
    if not member:
        _err("Member not found", 404)
    return _ok(member)


@router.post("/packages/{package_id}/links")
def api_add_link(
    package_id: int,
    from_member_id: int = Body(...),
    to_member_id: int = Body(...),
    link_type: str = Body(...),
    evidence: dict[str, Any] | None = Body(None),
    inference_stage: str = Body("hypothesized"),
    domain_keys: list[str] | None = Body(None),
    actor: str = Body("operator"),
    modal: str | None = Body(None),
) -> dict[str, Any]:
    from services.editorial_package_service import add_link

    try:
        link = add_link(
            package_id,
            from_member_id=from_member_id,
            to_member_id=to_member_id,
            link_type=link_type,
            evidence=evidence,
            inference_stage=inference_stage,
            domain_keys=domain_keys,
            actor=actor,
            modal=modal,
        )
    except ValueError as e:
        _err(str(e))
    return _ok(link)


@router.patch("/packages/{package_id}/links/{link_id}")
def api_set_link_status(
    package_id: int,
    link_id: int,
    status: str = Body(..., embed=True),
    actor: str = Body("operator", embed=True),
    modal: str = Body("reduction", embed=True),
    rationale: str | None = Body(None, embed=True),
) -> dict[str, Any]:
    from services.editorial_package_service import set_link_status

    try:
        link = set_link_status(
            package_id,
            link_id,
            status=status,
            actor=actor,
            modal=modal,
            rationale=rationale,
        )
    except ValueError as e:
        _err(str(e))
    if not link:
        _err("Link not found", 404)
    return _ok(link)


@router.post("/packages/{package_id}/ready")
def api_mark_ready(
    package_id: int,
    from_modal: str = Body("narrative", embed=True),
    actor: str = Body("operator", embed=True),
    rationale: str | None = Body(None, embed=True),
) -> dict[str, Any]:
    from services.editorial_package_service import mark_ready_for_editor

    pkg = mark_ready_for_editor(
        package_id, from_modal=from_modal, actor=actor, rationale=rationale
    )
    if not pkg:
        _err("Package not found", 404)
    return _ok(pkg)


@router.post("/packages/{package_id}/reduction")
def api_reduction(
    package_id: int,
    clear: bool = Body(..., embed=True),
    actor: str = Body("operator", embed=True),
    rationale: str | None = Body(None, embed=True),
) -> dict[str, Any]:
    from services.editorial_package_service import reduction_clear_or_block

    pkg = reduction_clear_or_block(
        package_id, clear=clear, actor=actor, rationale=rationale
    )
    if not pkg:
        _err("Package not found", 404)
    return _ok(pkg)


@router.post("/packages/{package_id}/reduction/run")
async def api_reduction_run(
    package_id: int,
    dry_run: bool = Body(False, embed=True),
    force: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """LLM-assisted Reduction pass: prune unrelated/weak/geo-mismatched members, then route back."""
    from services.editorial_package_reduction_service import run_reduction_pass

    try:
        result = await run_reduction_pass(
            package_id, dry_run=bool(dry_run), force=bool(force)
        )
    except Exception as e:
        logger.exception("reduction/run failed package_id=%s", package_id)
        _err(str(e), 500)
    if result.get("error") == "not_found":
        _err("Package not found", 404)
    return _ok(result)


@router.post("/packages/{package_id}/narrative/run")
async def api_narrative_run(
    package_id: int,
    dry_run: bool = Body(False, embed=True),
    force: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """LLM-assisted Narrative assembly: attach events/entities/links, then route to Reduction/Editor."""
    from services.editorial_package_narrative_service import run_narrative_pass

    try:
        result = await run_narrative_pass(
            package_id, dry_run=bool(dry_run), force=bool(force)
        )
    except Exception as e:
        logger.exception("narrative/run failed package_id=%s", package_id)
        _err(str(e), 500)
    if result.get("error") == "not_found":
        _err("Package not found", 404)
    return _ok(result)


@router.post("/packages/{package_id}/compose/run")
async def api_compose_run(
    package_id: int,
    dry_run: bool = Body(False, embed=True),
    force: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """LLM Editor compose: source-grounded news_story draft with [@m] citations."""
    from services.editorial_package_compose_service import run_compose_pass

    try:
        result = await run_compose_pass(
            package_id, dry_run=bool(dry_run), force=bool(force)
        )
    except Exception as e:
        logger.exception("compose/run failed package_id=%s", package_id)
        _err(str(e), 500)
    if result.get("error") == "not_found":
        _err("Package not found", 404)
    return _ok(result)


@router.get("/packages/{package_id}/evidence_brief")
def api_get_evidence_brief(package_id: int) -> dict[str, Any]:
    """Package-bound cited educational brief (Narrative expand + Research parity)."""
    from services.package_evidence_brief_service import get_brief, get_or_create_brief

    brief = get_brief(package_id)
    if not brief:
        # Ensure row exists for UI without forcing expand.
        try:
            brief = get_or_create_brief(package_id, actor="api")
        except LookupError:
            _err("Package not found", 404)
    return _ok({"brief": brief})


@router.post("/packages/{package_id}/evidence_brief")
def api_update_evidence_brief(
    package_id: int,
    brief_md: str | None = Body(None),
    lede: str | None = Body(None),
    open_questions: list[Any] | None = Body(None),
    status: str | None = Body(None),
    actor: str = Body("operator"),
) -> dict[str, Any]:
    from services.package_evidence_brief_service import update_brief

    try:
        brief = update_brief(
            package_id,
            brief_md=brief_md,
            lede=lede,
            open_questions=open_questions,
            status=status,
            actor=actor or "operator",
        )
    except LookupError:
        _err("Package not found", 404)
    except ValueError as e:
        _err(str(e), 400)
    return _ok({"brief": brief})


@router.post("/packages/{package_id}/evidence_expand/run")
async def api_evidence_expand_run(
    package_id: int,
    dry_run: bool = Body(False, embed=True),
    force: bool = Body(False, embed=True),
    include_web: bool | None = Body(None, embed=True),
) -> dict[str, Any]:
    """Gap-driven multi-source expand → package_evidence_briefs → Reduction."""
    from services.editorial_package_evidence_expand_service import (
        run_evidence_expand_pass,
    )

    try:
        result = await run_evidence_expand_pass(
            package_id,
            dry_run=bool(dry_run),
            force=bool(force),
            include_web=include_web,
        )
    except Exception as e:
        logger.exception("evidence_expand/run failed package_id=%s", package_id)
        _err(str(e), 500)
    if result.get("error") == "not_found":
        _err("Package not found", 404)
    return _ok(result)


@router.post("/packages/{package_id}/research/run")
async def api_research_run(
    package_id: int,
    dry_run: bool = Body(False, embed=True),
    force: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """LLM-assisted Research assembly: extract/promote/appraise spine + attach claims/facts/papers."""
    from services.editorial_package_research_service import run_research_pass

    try:
        result = await run_research_pass(
            package_id, dry_run=bool(dry_run), force=bool(force)
        )
    except Exception as e:
        logger.exception("research/run failed package_id=%s", package_id)
        _err(str(e), 500)
    if result.get("error") == "not_found":
        _err("Package not found", 404)
    return _ok(result)


@router.get("/packages/{package_id}/decisions")
def api_list_decisions(
    package_id: int,
    modal: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    from services.editorial_package_service import list_decisions

    return _ok({"decisions": list_decisions(package_id, modal=modal, limit=limit)})


@router.get("/packages/{package_id}/audit")
def api_audit_replay(package_id: int) -> dict[str, Any]:
    from services.editorial_package_service import audit_replay

    try:
        return _ok(audit_replay(package_id))
    except LookupError as e:
        _err(str(e), 404)


@router.get("/search")
def api_cross_domain_search(
    modal: str = Query(..., description="research|narrative|reduction|editor"),
    q: str = Query(..., min_length=2),
    domains: list[str] | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    from services.editorial_package_service import search_attachable

    if modal not in ("research", "narrative", "reduction", "editor"):
        _err("modal must be research|narrative|reduction|editor")
    return _ok(
        search_attachable(modal=modal, q=q, domains=domains, limit=limit)
    )


@router.post("/packages/{package_id}/attach")
def api_attach_hits(
    package_id: int,
    modal: str = Body(...),
    hits: list[dict[str, Any]] = Body(...),
    actor: str = Body("operator"),
) -> dict[str, Any]:
    from services.editorial_package_service import attach_search_hits

    try:
        added = attach_search_hits(package_id, hits, modal=modal, actor=actor)
    except (LookupError, ValueError) as e:
        _err(str(e), 404 if isinstance(e, LookupError) else 400)
    return _ok({"members": added})


@router.post("/handoffs")
def api_create_handoff(
    package_id: int | None = Body(None),
    source_modal: str = Body(...),
    target_modal: str = Body(...),
    reason_code: str = Body("manual"),
    note: str | None = Body(None),
    focus_member_id: int | None = Body(None),
    domain_keys: list[str] | None = Body(None),
    created_by: str = Body("operator"),
) -> dict[str, Any]:
    from services.modal_handoff_service import create_handoff

    if package_id is None:
        _err("package_id is required for handoffs")
    row = create_handoff(
        package_id=package_id,
        source_modal=source_modal,
        target_modal=target_modal,
        reason_code=reason_code,
        note=note,
        focus_member_id=focus_member_id,
        domain_keys=domain_keys,
        created_by=created_by,
    )
    return _ok(row)


@router.get("/handoffs")
def api_list_handoffs(
    target_modal: str | None = Query(None),
    status: str | None = Query("open"),
    package_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    from services.modal_handoff_service import list_handoffs

    return _ok(
        {
            "handoffs": list_handoffs(
                target_modal=target_modal,
                status=status,
                package_id=package_id,
                limit=limit,
            )
        }
    )


@router.patch("/handoffs/{handoff_id}")
def api_patch_handoff(
    handoff_id: int,
    status: str = Body(..., embed=True),
) -> dict[str, Any]:
    from services.modal_handoff_service import update_handoff_status

    try:
        row = update_handoff_status(handoff_id, status=status)
    except ValueError as e:
        _err(str(e))
    if not row:
        _err("Handoff not found", 404)
    return _ok(row)


@router.get("/editor/alerts")
def api_editor_alerts(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    from services.modal_handoff_service import editor_alerts

    return _ok({"alerts": editor_alerts(limit=limit)})


@router.post("/packages/{package_id}/rework")
def api_request_rework(
    package_id: int,
    target_modal: str = Body(...),
    note: str | None = Body(None),
    actor: str = Body("operator"),
) -> dict[str, Any]:
    from services.modal_handoff_service import request_rework

    try:
        row = request_rework(
            package_id, target_modal=target_modal, note=note, actor=actor
        )
    except ValueError as e:
        _err(str(e))
    return _ok(row)


@router.get("/stories")
def api_list_stories(
    status: str | None = Query(None),
    package_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    from services.news_story_service import list_stories

    return _ok({"stories": list_stories(status=status, package_id=package_id, limit=limit)})


@router.post("/stories")
def api_draft_story(
    package_id: int = Body(...),
    title: str = Body(""),
    lede: str | None = Body(None),
    body_md: str = Body(""),
    presentation_kind: str | None = Body(None),
    created_by: str | None = Body(None),
    actor: str = Body("operator"),
    story_id: int | None = Body(None),
) -> dict[str, Any]:
    from services.news_story_service import create_or_update_draft

    try:
        result = create_or_update_draft(
            package_id,
            title=title,
            lede=lede,
            body_md=body_md,
            presentation_kind=presentation_kind,
            created_by=created_by,
            actor=actor,
            story_id=story_id,
        )
    except (LookupError, ValueError) as e:
        _err(str(e), 404 if isinstance(e, LookupError) else 400)
    return _ok(result)


@router.post("/stories/{story_id}/publish")
async def api_publish_story(
    story_id: int,
    actor: str = Body("operator", embed=True),
    assemble: bool = Body(True, embed=True),
) -> dict[str, Any]:
    """Assemble final report from linked sources, then citation-gate and publish."""
    import asyncio

    from services.news_story_service import publish_story

    try:
        result = await asyncio.to_thread(
            publish_story, story_id, actor=actor, assemble=bool(assemble)
        )
    except LookupError as e:
        _err(str(e), 404)
    if result.get("blocked"):
        return {
            "success": False,
            "data": result,
            "message": f"Publish blocked: {result.get('block_reason') or 'citation_refused'}",
        }
    return _ok(result)


@router.get("/stories/{story_id}")
def api_get_story(story_id: int) -> dict[str, Any]:
    from services.news_story_service import get_story

    story = get_story(story_id)
    if not story:
        _err("Story not found", 404)
    return _ok(story)


@router.get("/stories/{story_id}/audit")
def api_story_audit(story_id: int) -> dict[str, Any]:
    from services.news_story_service import story_audit_chain

    try:
        return _ok(story_audit_chain(story_id))
    except LookupError as e:
        _err(str(e), 404)


@router.post("/packages/from_entity")
def api_package_from_entity(
    domain_key: str = Body(...),
    canonical_entity_id: int = Body(..., ge=1),
    actor: str = Body("operator"),
    refresh_members: bool = Body(False),
) -> dict[str, Any]:
    """Find or create an entity-seeded Research package (knowledge profile feed)."""
    from services.editorial_package_service import ensure_package_from_entity

    try:
        result = ensure_package_from_entity(
            domain_key=domain_key,
            canonical_entity_id=canonical_entity_id,
            actor=actor,
            refresh_members=bool(refresh_members),
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    return _ok(result)


@router.get("/knowledge_profiles")
def api_list_knowledge_profiles(
    domain_key: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    from services.knowledge_profile_service import list_profiles

    return _ok({"profiles": list_profiles(domain_key=domain_key, status=status, limit=limit)})


@router.get("/knowledge_profiles/by_entity")
def api_knowledge_profile_by_entity(
    domain_key: str = Query(...),
    canonical_entity_id: int = Query(..., ge=1),
) -> dict[str, Any]:
    from services.knowledge_profile_service import get_profile

    profile = get_profile(
        domain_key=domain_key,
        canonical_entity_id=canonical_entity_id,
    )
    if not profile:
        _err("Knowledge profile not found", 404)
    return _ok(profile)


@router.get("/knowledge_profiles/{profile_id}")
def api_get_knowledge_profile(profile_id: int) -> dict[str, Any]:
    from services.knowledge_profile_service import get_profile

    profile = get_profile(profile_id)
    if not profile:
        _err("Knowledge profile not found", 404)
    return _ok(profile)


@router.post("/knowledge_profiles/ensure")
def api_ensure_knowledge_profile(
    domain_key: str = Body(...),
    canonical_entity_id: int = Body(..., ge=1),
    actor: str = Body("operator"),
    refresh_package: bool = Body(True),
) -> dict[str, Any]:
    """Ensure entity package + profile exist; optionally refresh package members."""
    from services.editorial_package_service import ensure_package_from_entity
    from services.knowledge_profile_service import get_profile

    try:
        pkg = ensure_package_from_entity(
            domain_key=domain_key,
            canonical_entity_id=canonical_entity_id,
            actor=actor,
            refresh_members=bool(refresh_package),
        )
    except LookupError as e:
        _err(str(e), 404)
    except ValueError as e:
        _err(str(e))
    profile = get_profile(int(pkg["knowledge_profile_id"]))
    return _ok({"package": pkg, "profile": profile})


@router.post("/knowledge_profiles/{profile_id}/publish")
def api_publish_knowledge_profile(
    profile_id: int,
    actor: str = Body("operator", embed=True),
) -> dict[str, Any]:
    from services.knowledge_profile_service import publish_profile

    try:
        return _ok(publish_profile(profile_id, actor=actor))
    except LookupError as e:
        _err(str(e), 404)


@router.post("/knowledge_profiles/{profile_id}/regenerate")
def api_regenerate_knowledge_profile(
    profile_id: int,
    use_llm: bool = Body(False, embed=True),
) -> dict[str, Any]:
    from services.knowledge_profile_service import regenerate_report_md

    try:
        return _ok(regenerate_report_md(profile_id, use_llm=bool(use_llm)))
    except LookupError as e:
        _err(str(e), 404)


@router.post("/knowledge_profiles/merge_from_package")
def api_merge_knowledge_profile_from_package(
    package_id: int = Body(..., ge=1),
    actor: str = Body("operator"),
    publish: bool = Body(True),
) -> dict[str, Any]:
    """Manual merge endpoint (also called automatically after research pass)."""
    from services.knowledge_profile_service import auto_merge_from_package

    result = auto_merge_from_package(
        int(package_id),
        actor=actor,
        publish=bool(publish),
        regenerate=True,
    )
    return _ok(result)


@router.get("/modal/{modal_key}/domains")
def api_modal_domains(modal_key: str) -> dict[str, Any]:
    domains = allowed_domains_for_modal(modal_key)
    if not domains and modal_key not in (
        "research",
        "narrative",
        "reduction",
        "editor",
    ):
        _err("Unknown modal", 404)
    return _ok({"modal": modal_key, "allowed_domains": domains})
