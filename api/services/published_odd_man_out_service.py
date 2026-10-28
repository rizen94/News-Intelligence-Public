"""Published-safe odd-man-out prune (shared by batch script + auto-republish).

Unlike ``run_reduction_pass``, this does **not** change package status / route
(published products stay published). It reuses reduction's deterministic + optional
LLM scoring, applies sticky uncouple, scrubs dead ``[@m]`` markers, and stamps
``metadata.last_odd_man_out_at`` so readiness can detect membership drift.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[@m(\d+)\]")


def published_story_id(package_id: int) -> int | None:
    from shared.database.connection import get_ui_db_connection_context

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.news_stories
                WHERE package_id = %s AND status = 'published'
                ORDER BY published_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (package_id,),
            )
            row = cur.fetchone()
    return int(row[0]) if row else None


def scrub_story_citations(story_id: int, removed_member_ids: set[int]) -> int:
    """Drop [@mID] for uncoupled members from the published manuscript."""
    if not removed_member_ids:
        return 0
    from shared.database.connection import get_ui_db_connection_context

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT body_md, lede FROM intelligence.news_stories WHERE id = %s",
                (story_id,),
            )
            row = cur.fetchone()
            if not row:
                return 0
            body, lede = row[0] or "", row[1] or ""

            def _drop(text: str) -> tuple[str, int]:
                n = 0

                def repl(mo: re.Match[str]) -> str:
                    nonlocal n
                    if int(mo.group(1)) in removed_member_ids:
                        n += 1
                        return ""
                    return mo.group(0)

                return _CITATION.sub(repl, text), n

            new_body, n_body = _drop(body)
            new_lede, n_lede = _drop(lede)
            new_body = re.sub(r"[ \t]{2,}", " ", new_body)
            new_body = re.sub(r"\n{3,}", "\n\n", new_body)
            if n_body or n_lede:
                cur.execute(
                    """
                    UPDATE intelligence.news_stories
                    SET body_md = %s, lede = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (new_body, new_lede or None, story_id),
                )
                conn.commit()
            return n_body + n_lede


def _apply_member_actions_fast(
    package_id: int,
    actions: list[dict[str, Any]],
) -> dict[str, int]:
    """Bulk uncouple members with suppress stamp (one transaction)."""
    from shared.database.connection import get_ui_db_connection_context
    from shared.editorial_package_reattach import (
        build_suppress_metadata,
        flags_warrant_suppress,
    )
    from services.editorial_package_service import set_link_status

    counts = {"removed": 0, "quarantined": 0, "unlinked": 0, "kept": 0}
    member_ops: list[tuple[int, str, dict[str, Any], str]] = []
    for a in actions:
        if a.get("action") == "keep":
            counts["kept"] += 1
            continue
        if a.get("target") == "link" and a.get("action") == "remove":
            reason = a.get("reason") or f"reduction:{','.join(a.get('flags') or [])}"
            if not str(reason).lower().startswith("uncouple"):
                reason = f"uncouple from package: {reason}"
            try:
                set_link_status(
                    package_id,
                    int(a["id"]),
                    status="removed",
                    actor="odd_man_out_prune",
                    modal="reduction",
                    rationale=reason,
                )
                counts["unlinked"] += 1
            except Exception as e:
                logger.warning(
                    "link uncouple failed package=%s link=%s: %s",
                    package_id,
                    a.get("id"),
                    e,
                )
            continue
        if a.get("target") != "member" or a.get("action") not in ("remove", "quarantine"):
            continue
        status = "removed" if a["action"] == "remove" else "quarantined"
        flags = list(a.get("flags") or [])
        reason = a.get("reason") or f"reduction:{','.join(flags)}"
        if not str(reason).lower().startswith("uncouple"):
            reason = f"uncouple from package: {reason}"
        meta_patch: dict[str, Any] = {}
        if flags_warrant_suppress(flags, reason):
            meta_patch = build_suppress_metadata(
                flags=flags,
                rationale=reason,
                actor="odd_man_out_prune",
                modal="reduction",
            )
            meta_patch["suppress_at"] = datetime.now(timezone.utc).isoformat()
        member_ops.append((int(a["id"]), status, meta_patch, reason))

    if not member_ops:
        return counts

    stamp = build_suppress_metadata(
        flags=["unrelated", "geo_mismatch", "theme_mismatch", "entity_mismatch"],
        rationale="odd-man-out prune (deterministic)",
        actor="odd_man_out_prune",
        modal="reduction",
    )
    stamp["suppress_at"] = datetime.now(timezone.utc).isoformat()

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            by_status: dict[str, list[int]] = {"removed": [], "quarantined": []}
            for mid, status, _meta_patch, _reason in member_ops:
                by_status.setdefault(status, []).append(mid)
            for status, ids in by_status.items():
                if not ids:
                    continue
                cur.execute(
                    """
                    UPDATE intelligence.editorial_package_members
                    SET status = %s,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE package_id = %s AND id = ANY(%s)
                    """,
                    (status, json.dumps(stamp), package_id, ids),
                )
                if status == "removed":
                    counts["removed"] += len(ids)
                else:
                    counts["quarantined"] += len(ids)

            cur.execute(
                """
                INSERT INTO intelligence.editorial_package_decisions
                    (package_id, actor, modal, action, rationale, metadata)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    package_id,
                    "odd_man_out_prune",
                    "reduction",
                    "reduction_pass",
                    f"odd-man-out prune: removed={counts['removed']} quarantined={counts['quarantined']}",
                    json.dumps(
                        {
                            "batch": True,
                            "removed": counts["removed"],
                            "quarantined": counts["quarantined"],
                            "unlinked": counts["unlinked"],
                            "suppress_reattach": True,
                            "member_ids_sample": [m[0] for m in member_ops[:40]],
                        }
                    ),
                ),
            )
            conn.commit()
    return counts


def stamp_last_odd_man_out(
    package_id: int,
    *,
    active_member_count: int | None = None,
) -> None:
    """Record prune time + active count so readiness can detect post-prune drift."""
    from shared.database.connection import get_ui_db_connection_context

    now = datetime.now(timezone.utc).isoformat()
    patch: dict[str, Any] = {
        "last_odd_man_out_at": now,
    }
    if active_member_count is not None:
        patch["last_odd_man_out_active_count"] = int(active_member_count)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(patch), package_id),
            )
            conn.commit()


def load_package_light(package_id: int) -> dict[str, Any] | None:
    """Package row + active members/links only (no N+1 labels)."""
    from shared.database.connection import get_ui_db_connection_context

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.editorial_packages WHERE id = %s",
                (package_id,),
            )
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            if not row:
                return None
            pkg = dict(zip(cols, row))
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_package_members
                WHERE package_id = %s AND status = 'active'
                ORDER BY id
                """,
                (package_id,),
            )
            mcols = [d[0] for d in cur.description]
            members = [dict(zip(mcols, r)) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT * FROM intelligence.editorial_package_links
                WHERE package_id = %s AND status = 'active'
                ORDER BY id
                """,
                (package_id,),
            )
            lcols = [d[0] for d in cur.description]
            links = [dict(zip(lcols, r)) for r in cur.fetchall()]
    return {**pkg, "members": members, "links": links, "decisions": []}


def membership_drifted_since_prune(pkg: dict[str, Any] | None) -> bool:
    """Re-export for callers; logic lives in shared attach gate."""
    from shared.editorial_package_attach_gate import membership_drifted_since_prune as _drift

    return _drift(pkg)


async def prune_package(
    package_id: int,
    *,
    apply: bool = True,
    use_llm: bool = False,
    stamp_metadata: bool = True,
) -> dict[str, Any]:
    """Score odd members and optionally uncouple with suppress_reattach (no status route)."""
    from services.editorial_package_reduction_service import (
        _call_reduction_llm,
        _deterministic_flags,
        build_review_payload,
        merge_reduction_actions,
        validate_reduction_payload,
    )

    pkg = load_package_light(package_id)
    if not pkg:
        return {"ok": False, "package_id": package_id, "error": "not_found"}
    if str(pkg.get("status") or "") != "published":
        return {
            "ok": False,
            "package_id": package_id,
            "skipped": True,
            "reason": f"status={pkg.get('status')}",
        }

    payload = build_review_payload(pkg)
    known_members = {int(m["member_row_id"]) for m in payload["members"]}
    known_links = {int(ln["link_id"]) for ln in payload["links"]}
    det_actions = _deterministic_flags(payload)

    llm_actions: list[dict[str, Any]] = []
    used_fallback = False
    model: str | None = None
    if use_llm:
        parsed, model = await _call_reduction_llm(payload)
        if not parsed:
            used_fallback = True
            parsed = {
                "summary": "LLM unavailable; deterministic odd-man-out only.",
                "actions": det_actions,
            }
        validated = validate_reduction_payload(
            parsed,
            known_member_ids=known_members,
            known_link_ids=known_links,
        )
        llm_actions = validated["actions"]
        if not llm_actions and not used_fallback:
            used_fallback = True
    else:
        validated = {
            "summary": "deterministic odd-man-out prune (no LLM)",
            "actions": det_actions,
        }

    actions = merge_reduction_actions(det_actions, llm_actions)
    remove_actions = [a for a in actions if a.get("action") in ("remove", "quarantine")]

    active_ids = {int(m["member_row_id"]) for m in payload.get("members") or []}
    remove_member_ids = {
        int(a["id"]) for a in remove_actions if a.get("target") == "member"
    }
    remaining = active_ids - remove_member_ids
    min_keep = 2
    if len(remaining) < min_keep and remove_member_ids:
        scored = sorted(
            [
                m
                for m in (payload.get("members") or [])
                if int(m["member_row_id"]) in remove_member_ids
            ],
            key=lambda m: float(m.get("title_jaccard") or 0.0),
            reverse=True,
        )
        keep_ids = {
            int(m["member_row_id"]) for m in scored[: max(0, min_keep - len(remaining))]
        }
        if keep_ids:
            remove_actions = [
                a
                for a in remove_actions
                if not (a.get("target") == "member" and int(a["id"]) in keep_ids)
            ]
            remove_member_ids -= keep_ids

    proposed_member_ids = {
        int(a["id"]) for a in remove_actions if a.get("target") == "member"
    }

    counts = {"removed": 0, "quarantined": 0, "unlinked": 0, "kept": 0}
    if apply and remove_actions:
        counts = _apply_member_actions_fast(package_id, remove_actions)
    elif not apply:
        for a in remove_actions:
            if a["action"] == "remove" and a["target"] == "member":
                counts["removed"] += 1
            elif a["action"] == "quarantine" and a["target"] == "member":
                counts["quarantined"] += 1
            elif a["target"] == "link" and a["action"] == "remove":
                counts["unlinked"] += 1

    scrubbed = 0
    story_id = published_story_id(package_id)
    if apply and story_id and proposed_member_ids and (
        counts["removed"] + counts["quarantined"] > 0
    ):
        scrubbed = scrub_story_citations(story_id, proposed_member_ids)

    active_after = len(active_ids) - (
        counts["removed"] + counts["quarantined"] if apply else 0
    )
    if apply and stamp_metadata:
        stamp_last_odd_man_out(package_id, active_member_count=max(0, active_after))

    return {
        "ok": True,
        "package_id": package_id,
        "story_id": story_id,
        "active_before": len(payload.get("members") or []),
        "active_after": active_after if apply else len(payload.get("members") or []),
        "det_flags": len(det_actions),
        "proposed": len(remove_actions),
        "removed": counts["removed"],
        "quarantined": counts["quarantined"],
        "unlinked": counts["unlinked"],
        "scrubbed_markers": scrubbed,
        "used_llm": bool(use_llm),
        "used_fallback": used_fallback,
        "model": model,
        "summary": (validated.get("summary") or "")[:240],
        "member_ids": sorted(proposed_member_ids)[:40],
    }


def prune_package_sync(
    package_id: int,
    *,
    apply: bool = True,
    use_llm: bool = False,
) -> dict[str, Any]:
    """Sync wrapper for auto-republish and other non-async callers."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Nested event loop (rare in sync API paths) — run in a thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    prune_package(package_id, apply=apply, use_llm=use_llm)
                )
            ).result()
    return asyncio.run(prune_package(package_id, apply=apply, use_llm=use_llm))
