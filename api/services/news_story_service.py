"""
News stories — longform product bound to editorial packages (v11).

Publish requires citation markers that resolve to active package members with
source refs; otherwise citation_refused is logged and publish is blocked.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_vocab import PRESENTATION_KINDS
from services.editorial_package_service import (
    _append_decision,
    emit_citation_gap_handoff,
    get_package,
    update_package,
    validate_prose_citations,
)

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


def create_or_update_draft(
    package_id: int,
    *,
    title: str = "",
    lede: str | None = None,
    body_md: str = "",
    presentation_kind: str | None = None,
    created_by: str | None = None,
    actor: str = "operator",
    story_id: int | None = None,
    advance_status: bool = True,
) -> dict[str, Any]:
    pkg = get_package(package_id, include=False)
    if not pkg:
        raise LookupError(f"Package {package_id} not found")
    kind = presentation_kind or pkg.get("presentation_kind") or "unset"
    if kind not in PRESENTATION_KINDS:
        raise ValueError(f"Invalid presentation_kind: {kind}")

    citation_check = validate_prose_citations(package_id, body_md)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if story_id:
                cur.execute(
                    """
                    UPDATE intelligence.news_stories
                    SET title = %s, lede = %s, body_md = %s,
                        presentation_kind = %s, domain_keys = %s::text[],
                        updated_at = NOW()
                    WHERE id = %s AND package_id = %s
                    RETURNING *
                    """,
                    (
                        title,
                        lede,
                        body_md,
                        kind,
                        list(pkg.get("domain_keys") or []),
                        story_id,
                        package_id,
                    ),
                )
                story = _row(cur)
                if not story:
                    raise LookupError(f"Story {story_id} not found for package")
            else:
                # Prefer single draft per package
                cur.execute(
                    """
                    SELECT id FROM intelligence.news_stories
                    WHERE package_id = %s AND status = 'draft'
                    ORDER BY id DESC LIMIT 1
                    """,
                    (package_id,),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE intelligence.news_stories
                        SET title = %s, lede = %s, body_md = %s,
                            presentation_kind = %s, domain_keys = %s::text[],
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (
                            title,
                            lede,
                            body_md,
                            kind,
                            list(pkg.get("domain_keys") or []),
                            int(existing[0]),
                        ),
                    )
                    story = _row(cur)
                else:
                    cur.execute(
                        """
                        INSERT INTO intelligence.news_stories
                            (package_id, title, lede, body_md, status,
                             presentation_kind, domain_keys, created_by)
                        VALUES (%s, %s, %s, %s, 'draft', %s, %s::text[], %s)
                        RETURNING *
                        """,
                        (
                            package_id,
                            title,
                            lede,
                            body_md,
                            kind,
                            list(pkg.get("domain_keys") or []),
                            created_by,
                        ),
                    )
                    story = _row(cur)
            assert story is not None
            cur.execute(
                """
                INSERT INTO intelligence.news_story_revisions
                    (story_id, title, lede, body_md, editor_actor)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (int(story["id"]), title, lede, body_md, actor),
            )
            # Replace citations for this draft
            cur.execute(
                "DELETE FROM intelligence.news_story_citations WHERE story_id = %s",
                (int(story["id"]),),
            )
            for b in citation_check.get("bound") or []:
                m = b["member"]
                prov = m.get("provenance") or {}
                cur.execute(
                    """
                    INSERT INTO intelligence.news_story_citations
                        (story_id, package_member_id, citation_marker,
                         source_table, source_row_id, source_url, quote)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(story["id"]),
                        int(m["id"]),
                        f"[@m{m['id']}]",
                        m.get("member_type"),
                        m.get("member_id"),
                        prov.get("source_url") or prov.get("url"),
                        prov.get("quote") or prov.get("quote_span"),
                    ),
                )
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="citation_bound",
                    actor=actor,
                    modal="editor",
                    member_id=int(m["id"]),
                    rationale="citation bound on draft",
                    source_refs=prov if isinstance(prov, dict) else {},
                )
            for ref in citation_check.get("refused") or []:
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="citation_refused",
                    actor=actor,
                    modal="editor",
                    member_id=ref.get("member_row_id"),
                    rationale=ref.get("reason") or "citation_refused",
                    source_refs=ref,
                )
            _append_decision(
                cur,
                package_id=package_id,
                action="prose_drafted",
                actor=actor,
                modal="editor",
                rationale="draft saved",
                metadata={"story_id": int(story["id"]), "citation_ok": citation_check["ok"]},
            )
            conn.commit()
    if not citation_check.get("ok"):
        emit_citation_gap_handoff(package_id, citation_check, actor=actor)
    if advance_status:
        update_package(
            package_id,
            status="in_editing",
            presentation_kind=kind if kind != "unset" else None,
            primary_modal="editor",
            actor=actor,
            modal="editor",
        )
    return {
        "story": story,
        "citation_check": citation_check,
    }


def _scaffold_body_md(package: dict[str, Any]) -> str:
    """Build a starter composer body from summary_stub + citeable members."""
    from shared.editorial_package_vocab import provenance_has_citeable_source

    stub = str(package.get("summary_stub") or "").strip()
    title = str(package.get("working_title") or "").strip()
    active = [m for m in (package.get("members") or []) if m.get("status") == "active"]
    citeable = [
        m
        for m in active
        if provenance_has_citeable_source(m.get("provenance"), for_publish=True)
    ]

    def _label(m: dict[str, Any]) -> str:
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        return str(prov.get("label") or prov.get("title") or m.get("member_type") or "").strip()

    preferred: list[dict[str, Any]] = []
    for role in ("anchor_event", "supporting", "core_claim"):
        preferred.extend(m for m in citeable if m.get("role") == role)
    # Fill with remaining citeable if needed
    seen = {int(m["id"]) for m in preferred}
    for m in citeable:
        mid = int(m["id"])
        if mid not in seen:
            preferred.append(m)
            seen.add(mid)

    cite_ids = [int(m["id"]) for m in preferred[:8]]
    markers = " ".join(f"[@m{mid}]" for mid in cite_ids)
    prose = stub or (f"{title}." if title else "Draft pending editorial composition.")
    lines = [prose]
    if markers:
        lines.append("")
        lines.append(markers)
    source_lines = []
    for m in preferred[:12]:
        label = _label(m)[:120] or f"member {m['id']}"
        source_lines.append(f"- {label} [@m{int(m['id'])}]")
    if source_lines:
        lines.append("")
        lines.append("## Source anchors")
        lines.extend(source_lines)
    return "\n".join(lines).strip() + "\n"


def ensure_editor_scaffold(
    package_id: int,
    *,
    actor: str = "system",
    compose: bool = True,
) -> dict[str, Any]:
    """Seed links + a source-grounded draft when Editor opens empty/thin.

    Prefer LLM compose (excerpt-backed prose). Fall back to a thin stub only if
    compose is disabled or fails. Does not advance package status to in_editing.
    """
    from services.editorial_package_service import seed_heuristic_editor_links

    pkg = get_package(package_id)
    if not pkg:
        raise LookupError(f"Package {package_id} not found")

    links_result = seed_heuristic_editor_links(package_id, actor=actor)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, body_md, title, status
                FROM intelligence.news_stories
                WHERE package_id = %s
                ORDER BY CASE WHEN status = 'published' THEN 0
                              WHEN status = 'draft' THEN 1
                              ELSE 2 END, id DESC
                LIMIT 1
                """,
                (package_id,),
            )
            existing = _row(cur)

    body_present = bool(existing and str(existing.get("body_md") or "").strip())
    from services.editorial_package_compose_service import is_thin_scaffold_body

    thin = is_thin_scaffold_body((existing or {}).get("body_md") if existing else None)

    compose_result: dict[str, Any] | None = None
    if compose and (not body_present or thin):
        try:
            from services.editorial_package_compose_service import (
                is_enabled as compose_enabled,
                run_compose_pass_sync,
            )

            if compose_enabled():
                compose_result = run_compose_pass_sync(
                    package_id, force=True
                )
                if compose_result.get("ok"):
                    return {
                        "package_id": package_id,
                        "draft": {
                            "seeded": True,
                            "reason": "composed_from_sources",
                            "story": compose_result.get("story"),
                            "citation_check": compose_result.get("citation_check"),
                        },
                        "links": links_result,
                        "compose": compose_result,
                    }
        except Exception as e:
            logger.warning(
                "ensure_editor_scaffold compose failed package_id=%s: %s",
                package_id,
                e,
            )
            compose_result = {"ok": False, "error": str(e)}

    draft_result: dict[str, Any] | None = None
    if body_present and not thin:
        draft_result = {"seeded": False, "reason": "story_body_present", "story": existing}
    elif body_present and thin and compose_result and not compose_result.get("ok"):
        # Keep existing thin body; compose failed
        draft_result = {
            "seeded": False,
            "reason": "compose_failed_kept_scaffold",
            "story": existing,
        }
    else:
        body = _scaffold_body_md(pkg)
        title = str(pkg.get("working_title") or "").strip() or "Untitled package"
        draft_result = create_or_update_draft(
            package_id,
            title=title,
            lede=(str(pkg.get("summary_stub") or "").strip()[:400] or None),
            body_md=body,
            presentation_kind=pkg.get("presentation_kind"),
            created_by=actor,
            actor=actor,
            story_id=int(existing["id"]) if existing else None,
            advance_status=False,
        )
        draft_result = {
            "seeded": True,
            "reason": "seeded_from_summary_stub",
            **draft_result,
        }

    return {
        "package_id": package_id,
        "draft": draft_result,
        "links": links_result,
        "compose": compose_result,
    }


def publish_story(
    story_id: int,
    *,
    actor: str = "operator",
    assemble: bool = True,
) -> dict[str, Any]:
    """Final assembly + publish.

    When assemble=True (default), rebuild the manuscript from linked package
    sources into a detailed cited report, then run the citation gate and mark
    published. Publish is the productization step — not a status flip on a stub.
    """
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.news_stories WHERE id = %s",
                (story_id,),
            )
            story = _row(cur)
            if not story:
                raise LookupError(f"Story {story_id} not found")
            package_id = int(story["package_id"])

    assemble_result: dict[str, Any] | None = None
    if assemble:
        from services.editorial_package_compose_service import run_compose_pass_sync

        try:
            assemble_result = run_compose_pass_sync(
                package_id,
                force=True,
                mode="publish",
                story_id=story_id,
            )
        except Exception as e:
            logger.exception(
                "publish assemble failed story_id=%s package_id=%s",
                story_id,
                package_id,
            )
            return {
                "published": False,
                "blocked": True,
                "block_reason": "assemble_failed",
                "assemble": {"ok": False, "error": str(e)},
                "story": story,
            }
        if not assemble_result.get("ok"):
            return {
                "published": False,
                "blocked": True,
                "block_reason": "assemble_insufficient",
                "assemble": assemble_result,
                "story": assemble_result.get("story") or story,
            }

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.news_stories WHERE id = %s",
                (story_id,),
            )
            story = _row(cur)
            if not story:
                raise LookupError(f"Story {story_id} not found")
            package_id = int(story["package_id"])
            body = (story.get("body_md") or "").strip()
            if not body:
                refused = {"ok": False, "bound": [], "refused": [{"member_row_id": None, "reason": "empty_body"}], "markers": [], "unsupported_publish": True}
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="citation_refused",
                    actor=actor,
                    modal="editor",
                    rationale="publish blocked — empty body after assemble",
                    source_refs={"refused": refused["refused"]},
                )
                conn.commit()
                emit_citation_gap_handoff(package_id, refused, actor=actor)
                return {
                    "published": False,
                    "blocked": True,
                    "citation_check": refused,
                    "story": story,
                    "block_reason": "empty_body",
                    "assemble": assemble_result,
                }
            pkg = get_package(package_id)
            readiness = (pkg or {}).get("readiness") or {}
            if not readiness.get("reduction_cleared"):
                refused = {
                    "ok": False,
                    "bound": [],
                    "refused": [{"member_row_id": None, "reason": "not_reduction_cleared"}],
                    "markers": [],
                    "unsupported_publish": True,
                }
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="citation_refused",
                    actor=actor,
                    modal="editor",
                    rationale="publish blocked — package not reduction-cleared / ready_for_editor",
                    source_refs={"readiness": readiness},
                )
                conn.commit()
                return {
                    "published": False,
                    "blocked": True,
                    "citation_check": refused,
                    "story": story,
                    "block_reason": "not_reduction_cleared",
                    "readiness": readiness,
                    "assemble": assemble_result,
                }
            check = validate_prose_citations(package_id, story.get("body_md") or "")
            if not check["ok"]:
                _append_decision(
                    cur,
                    package_id=package_id,
                    action="citation_refused",
                    actor=actor,
                    modal="editor",
                    rationale="publish blocked — unsupported citations",
                    source_refs={"refused": check["refused"]},
                )
                conn.commit()
                emit_citation_gap_handoff(package_id, check, actor=actor)
                return {
                    "published": False,
                    "blocked": True,
                    "citation_check": check,
                    "story": story,
                    "block_reason": "citation_gate",
                    "assemble": assemble_result,
                }
            cur.execute(
                """
                UPDATE intelligence.news_stories
                SET status = 'published', published_at = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (story_id,),
            )
            story = _row(cur)
            _append_decision(
                cur,
                package_id=package_id,
                action="prose_published",
                actor=actor,
                modal="editor",
                rationale="published after final assembly",
                metadata={
                    "story_id": story_id,
                    "assembled": bool(assemble),
                    "assemble_model": (assemble_result or {}).get("model"),
                    "assemble_fallback": (assemble_result or {}).get("used_fallback"),
                    "body_len": len(body),
                    "used_member_ids": (assemble_result or {}).get("used_member_ids"),
                },
            )
            conn.commit()
    update_package(
        package_id,
        status="published",
        primary_modal="editor",
        actor=actor,
        modal="editor",
        rationale="news story published",
    )
    # Stale citation_gap / package_ready alerts must not linger after a successful publish.
    try:
        from services.modal_handoff_service import dismiss_open_editor_handoffs

        dismiss_open_editor_handoffs(
            package_id,
            rationale="prose_published",
        )
    except Exception:
        logger.exception(
            "dismiss editor handoffs after publish failed package_id=%s",
            package_id,
        )
    return {
        "published": True,
        "blocked": False,
        "citation_check": check,
        "story": story,
        "assemble": assemble_result,
    }


_AUTO_REPUBLISH_MEMBER_TYPES = (
    "chronological_event",
    "article",
)


def auto_republish_for_new_members(
    package_id: int,
    *,
    actor: str = "story_continuation",
    max_new: int = 5,
) -> dict[str, Any]:
    """
    If this package already has a published news_story and uncited citeable
    members arrived (continuation), reassemble + republish via publish_story.

    Stub "Update: title" appends are retired — new members must enter the
    full report assembly so the published product stays substantive.
    """
    from shared.editorial_package_vocab import provenance_has_citeable_source
    from services.editorial_package_service import (
        _CITATION_MARKER_RE,
        enrich_package_cite_provenance,
        get_package,
    )

    pid = int(package_id)
    enrich_package_cite_provenance(pid)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intelligence.news_stories
                WHERE package_id = %s AND status = 'published'
                ORDER BY published_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (pid,),
            )
            story = _row(cur)

    if not story:
        return {"skipped": True, "reason": "no_published_story", "package_id": pid}

    body = story.get("body_md") or ""
    cited = {int(x) for x in _CITATION_MARKER_RE.findall(body)}
    pkg = get_package(pid)
    if not pkg:
        return {"skipped": True, "reason": "package_missing", "package_id": pid}

    type_rank = {t: i for i, t in enumerate(_AUTO_REPUBLISH_MEMBER_TYPES)}
    candidates: list[dict[str, Any]] = []
    for m in pkg.get("members") or []:
        if m.get("status") != "active":
            continue
        mid = int(m["id"])
        if mid in cited:
            continue
        mt = str(m.get("member_type") or "")
        if mt not in type_rank:
            continue
        if not provenance_has_citeable_source(m.get("provenance") or {}, for_publish=True):
            continue
        candidates.append(m)

    candidates.sort(
        key=lambda m: (
            type_rank.get(str(m.get("member_type") or ""), 99),
            -int(m.get("id") or 0),
        )
    )
    to_add = candidates[: max(1, int(max_new))]
    if not to_add:
        return {
            "skipped": True,
            "reason": "no_uncited_citeable_members",
            "package_id": pid,
            "story_id": int(story["id"]),
        }

    from shared.link_scoring import auto_republish_enabled

    if not auto_republish_enabled():
        return {
            "skipped": True,
            "reason": "NEWS_STORY_AUTO_REPUBLISH=false",
            "package_id": pid,
            "story_id": int(story["id"]),
            "pending_member_ids": [int(m["id"]) for m in to_add],
        }

    story_id = int(story["id"])
    added_ids = [int(m["id"]) for m in to_add]
    # Full reassemble+publish — not stub "Update: title" appends.
    result = publish_story(story_id, actor=actor, assemble=True)
    if result.get("published"):
        return {
            "skipped": False,
            "published": True,
            "package_id": pid,
            "story_id": story_id,
            "added_member_ids": added_ids,
            "auto_republish": True,
            "assemble": True,
            "publish": result,
            "story": result.get("story"),
            "citation_check": result.get("citation_check"),
        }

    return {
        "skipped": True,
        "reason": result.get("block_reason") or "assemble_or_citation_blocked",
        "package_id": pid,
        "story_id": story_id,
        "attempted_member_ids": added_ids,
        "publish": result,
    }


def list_stories(
    *,
    status: str | None = None,
    package_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = ["1=1"]
    args: list[Any] = []
    if status:
        filters.append("status = %s")
        args.append(status)
    if package_id is not None:
        filters.append("package_id = %s")
        args.append(package_id)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.*, p.working_title AS package_title
                FROM intelligence.news_stories s
                LEFT JOIN intelligence.editorial_packages p ON p.id = s.package_id
                WHERE {" AND ".join(filters)}
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT %s
                """,
                [*args, int(limit)],
            )
            return _rows(cur)


def get_story(story_id: int) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.news_stories WHERE id = %s",
                (story_id,),
            )
            story = _row(cur)
            if not story:
                return None
            cur.execute(
                """
                SELECT * FROM intelligence.news_story_citations
                WHERE story_id = %s ORDER BY id
                """,
                (story_id,),
            )
            citations = _rows(cur)
            cur.execute(
                """
                SELECT * FROM intelligence.news_story_revisions
                WHERE story_id = %s ORDER BY created_at DESC LIMIT 20
                """,
                (story_id,),
            )
            revisions = _rows(cur)
            return {**story, "citations": citations, "revisions": revisions}


def story_audit_chain(story_id: int) -> dict[str, Any]:
    """Replay: story → citations → package members → source URL/quote → decisions."""
    from services.editorial_package_service import audit_replay

    story = get_story(story_id)
    if not story:
        raise LookupError(f"Story {story_id} not found")
    package_audit = audit_replay(int(story["package_id"]))
    return {
        "story": {
            "id": story["id"],
            "title": story.get("title"),
            "status": story.get("status"),
            "package_id": story.get("package_id"),
            "presentation_kind": story.get("presentation_kind"),
        },
        "citations": story.get("citations") or [],
        "package_audit": package_audit,
    }
