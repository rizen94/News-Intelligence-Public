"""Project published editorial packages into durable storyline/event editorial fields.

Package compose/publish writes news_stories + package_evidence_briefs. The v2 reader
and home feed still read storylines.editorial_document / tracked_events briefing
columns — this module is the bridge.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

logger = logging.getLogger(__name__)

PROJECTED_DOCUMENT_STATUS = "package_projected"

# Statuses considered durable enough for reader preference over thin seeds.
QUALITY_DOCUMENT_STATUSES: frozenset[str] = frozenset(
    {
        "package_projected",
        "desk_promoted",
        "refined",
        "rag_analyzed",
        "draft",
    }
)


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _first_paragraph(text: str, *, max_len: int = 480) -> str:
    blob = (text or "").strip()
    if not blob:
        return ""
    for part in re.split(r"\n\s*\n", blob):
        line = part.strip().lstrip("#").strip()
        if len(line) >= 24:
            return line[:max_len].rstrip()
    return blob[:max_len].rstrip()


def _bullet_lines(text: str, *, limit: int = 6) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ", "• ")):
            item = s[2:].strip()
            if len(item) >= 12:
                out.append(item)
        elif re.match(r"^\d+\.\s+", s):
            item = re.sub(r"^\d+\.\s+", "", s).strip()
            if len(item) >= 12:
                out.append(item)
        if len(out) >= limit:
            break
    return out


def prose_to_editorial_patch(
    *,
    title: str | None = None,
    lede: str | None = None,
    body_md: str | None = None,
    brief_md: str | None = None,
) -> dict[str, Any]:
    """Map package/story prose into the runtime 5W1H editorial_document shape (no LLM)."""
    body = (body_md or "").strip()
    brief = (brief_md or "").strip()
    preferred = brief if len(brief) >= 80 else body
    lede_text = (lede or "").strip() or _first_paragraph(preferred) or _first_paragraph(body)
    bullets = _bullet_lines(preferred) or _bullet_lines(body)
    analysis = ""
    if preferred:
        # Prefer a mid-length stretch after the lede for analysis.
        paras = [p.strip() for p in re.split(r"\n\s*\n", preferred) if p.strip()]
        for p in paras[1:4] if len(paras) > 1 else paras:
            cleaned = p.lstrip("#").strip()
            if len(cleaned) >= 60 and cleaned != lede_text:
                analysis = cleaned[:900]
                break
        if not analysis and len(preferred) > len(lede_text) + 40:
            analysis = preferred[:900].strip()
    outlook = ""
    for marker in ("outlook", "what next", "what to watch", "looking ahead"):
        m = re.search(
            rf"(?im)^#+\s*.*{re.escape(marker)}.*$\n+(.+?)(?=\n#+|\Z)",
            preferred or body,
        )
        if m:
            outlook = _first_paragraph(m.group(1), max_len=320)
            break

    patch: dict[str, Any] = {
        "lede": lede_text,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if title:
        patch["title"] = title
    if bullets:
        patch["what"] = bullets
        patch["developments"] = bullets[:4]
    if analysis:
        patch["analysis"] = analysis
    if outlook:
        patch["outlook"] = outlook
    elif bullets:
        patch["outlook"] = bullets[-1][:320]
    return {k: v for k, v in patch.items() if v not in (None, "", [], {})}


def parse_storyline_legacy_seed(seed: str | None) -> tuple[str, int] | None:
    raw = (seed or "").strip()
    if not raw.startswith("storyline:"):
        return None
    parts = raw.split(":")
    if len(parts) < 3:
        return None
    domain = parts[1].strip()
    try:
        sid = int(parts[2])
    except ValueError:
        return None
    if not domain or sid <= 0:
        return None
    return domain, sid


def resolve_package_storyline_targets(package: dict[str, Any]) -> list[tuple[str, int]]:
    """Storylines to update: legacy_seed first, then article membership (capped)."""
    found: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    def _add(domain: str, sid: int) -> None:
        key = (domain, sid)
        if key in seen:
            return
        seen.add(key)
        found.append(key)

    meta = _as_dict(package.get("metadata"))
    seeded = parse_storyline_legacy_seed(str(meta.get("legacy_seed") or ""))
    if seeded:
        _add(*seeded)

    members = list(package.get("members") or [])
    article_ids = [
        int(m["member_id"])
        for m in members
        if (m.get("status") or "active") == "active"
        and m.get("member_type") == "article"
        and m.get("member_id") is not None
    ][:40]
    domain_keys = [d for d in (package.get("domain_keys") or []) if d]
    if not domain_keys and seeded:
        domain_keys = [seeded[0]]

    if article_ids and domain_keys:
        from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

        try:
            active = set(get_pipeline_active_domain_keys())
        except Exception:
            active = set(domain_keys)
        for dk in domain_keys:
            if dk not in active and dk not in domain_keys:
                continue
            schema = resolve_domain_schema(dk)
            if not schema:
                continue
            try:
                with get_ui_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT DISTINCT sa.storyline_id
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.storylines s ON s.id = sa.storyline_id
                            WHERE sa.article_id = ANY(%s)
                              AND s.merged_into_id IS NULL
                            ORDER BY sa.storyline_id
                            LIMIT 8
                            """,
                            (article_ids,),
                        )
                        for (sid,) in cur.fetchall():
                            _add(dk, int(sid))
            except Exception as e:
                logger.debug("storyline resolve via articles %s: %s", dk, e)

    return found[:12]


def resolve_package_tracked_event_ids(package: dict[str, Any]) -> list[int]:
    """Best-effort tracked_event ids from chronological_event members."""
    members = [
        m
        for m in (package.get("members") or [])
        if (m.get("status") or "active") == "active"
        and m.get("member_type") == "chronological_event"
        and m.get("member_id") is not None
    ]
    ce_ids = [int(m["member_id"]) for m in members][:30]
    if not ce_ids:
        return []
    out: list[int] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                # Common linkage patterns — tolerate missing columns.
                try:
                    cur.execute(
                        """
                        SELECT DISTINCT te.id
                        FROM intelligence.tracked_events te
                        WHERE te.id = ANY(%s)
                        LIMIT 20
                        """,
                        (ce_ids,),
                    )
                    out.extend(int(r[0]) for r in cur.fetchall())
                except Exception:
                    conn.rollback()
                if not out:
                    try:
                        cur.execute(
                            """
                            SELECT DISTINCT te.id
                            FROM intelligence.tracked_events te
                            WHERE te.metadata->>'chronological_event_id' ~ '^[0-9]+$'
                              AND (te.metadata->>'chronological_event_id')::int = ANY(%s)
                            LIMIT 20
                            """,
                            (ce_ids,),
                        )
                        out.extend(int(r[0]) for r in cur.fetchall())
                    except Exception:
                        conn.rollback()
    except Exception as e:
        logger.debug("tracked_event resolve: %s", e)
    # Dedupe
    seen: set[int] = set()
    uniq: list[int] = []
    for i in out:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq[:20]


def project_package_to_editorial(
    package_id: int,
    *,
    story_id: int | None = None,
    source: str = "package_publish",
) -> dict[str, Any]:
    """
    Merge published package prose into linked storyline editorial_document
    and optionally tracked_event briefing fields.
    """
    from services.desk_promotion_service import (
        merge_editorial_document,
        patch_tracked_event_narrative,
    )
    from services.editorial_package_service import get_package
    from shared.domain_registry import resolve_domain_schema

    pkg = get_package(int(package_id), include=True)
    if not pkg:
        return {"ok": False, "error": "package_not_found", "package_id": package_id}

    story: dict[str, Any] | None = None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if story_id:
                cur.execute(
                    "SELECT id, package_id, title, lede, body_md, status FROM intelligence.news_stories WHERE id = %s",
                    (int(story_id),),
                )
            else:
                cur.execute(
                    """
                    SELECT id, package_id, title, lede, body_md, status
                    FROM intelligence.news_stories
                    WHERE package_id = %s AND status = 'published'
                    ORDER BY published_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """,
                    (int(package_id),),
                )
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                story = dict(zip(cols, row))

    brief_md = ""
    try:
        from services.package_evidence_brief_service import get_brief

        brief = get_brief(int(package_id)) or {}
        brief_md = str(brief.get("brief_md") or "")
    except Exception:
        brief_md = ""

    title = (story or {}).get("title") or pkg.get("working_title") or ""
    lede = (story or {}).get("lede") or pkg.get("summary_stub") or ""
    body_md = (story or {}).get("body_md") or ""
    if not body_md and not brief_md and not lede:
        return {
            "ok": False,
            "error": "no_prose",
            "package_id": package_id,
            "story_id": (story or {}).get("id"),
        }

    patch = prose_to_editorial_patch(
        title=str(title) if title else None,
        lede=str(lede) if lede else None,
        body_md=str(body_md) if body_md else None,
        brief_md=brief_md or None,
    )
    if not patch.get("lede"):
        return {"ok": False, "error": "empty_lede_patch", "package_id": package_id}

    targets = resolve_package_storyline_targets(pkg)
    storyline_results: list[dict[str, Any]] = []
    for domain_key, sid in targets:
        try:
            # Prefer package_projected status via direct update after merge helper.
            with get_db_connection_context() as conn:
                schema = resolve_domain_schema(domain_key)
                if not schema:
                    storyline_results.append(
                        {"domain_key": domain_key, "storyline_id": sid, "ok": False, "error": "bad_schema"}
                    )
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT editorial_document, document_status
                        FROM {schema}.storylines WHERE id = %s
                        """,
                        (sid,),
                    )
                    row = cur.fetchone()
                    if not row:
                        storyline_results.append(
                            {
                                "domain_key": domain_key,
                                "storyline_id": sid,
                                "ok": False,
                                "error": "storyline_not_found",
                            }
                        )
                        continue
                    existing = _as_dict(row[0])
                    prev_status = str(row[1] or "")
                    # Do not overwrite human desk promote with thinner package text.
                    if prev_status == "desk_promoted" and source == "package_publish":
                        storyline_results.append(
                            {
                                "domain_key": domain_key,
                                "storyline_id": sid,
                                "ok": True,
                                "skipped": True,
                                "reason": "desk_promoted_preserved",
                            }
                        )
                        continue
                    merged = merge_editorial_document(
                        existing,
                        patch,
                        provenance={
                            "source": source,
                            "package_id": int(package_id),
                            "story_id": int((story or {}).get("id") or 0) or None,
                            "projected_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET editorial_document = %s::jsonb,
                            document_status = %s,
                            document_version = COALESCE(document_version, 0) + 1,
                            last_refinement = NOW(),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(merged), PROJECTED_DOCUMENT_STATUS, sid),
                    )
                conn.commit()
            storyline_results.append(
                {
                    "domain_key": domain_key,
                    "storyline_id": sid,
                    "ok": True,
                    "document_status": PROJECTED_DOCUMENT_STATUS,
                }
            )
        except Exception as e:
            logger.warning(
                "project_package_to_editorial storyline %s/%s: %s",
                domain_key,
                sid,
                e,
            )
            storyline_results.append(
                {"domain_key": domain_key, "storyline_id": sid, "ok": False, "error": str(e)}
            )

    event_results: list[dict[str, Any]] = []
    briefing_text = patch.get("lede") or ""
    if patch.get("analysis"):
        briefing_text = f"{briefing_text}\n\n{patch['analysis']}".strip()
    briefing_json = {
        "headline": patch.get("lede") or title,
        "summary": patch.get("analysis") or patch.get("lede") or "",
        "chronology": patch.get("developments") or patch.get("what") or [],
        "impact": "",
        "what_next": patch.get("outlook") or "",
        "key_participants": [],
        "package_id": int(package_id),
        "projected_at": datetime.now(timezone.utc).isoformat(),
    }
    for eid in resolve_package_tracked_event_ids(pkg):
        try:
            res = patch_tracked_event_narrative(
                eid,
                editorial_briefing=briefing_text[:2000] if briefing_text else None,
                narrative_lenses={"package_projection": briefing_json},
                source=source,
            )
            # Also set editorial_briefing_json when column exists
            try:
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE intelligence.tracked_events
                            SET editorial_briefing_json = COALESCE(editorial_briefing_json, '{}'::jsonb)
                                  || %s::jsonb,
                                briefing_status = COALESCE(briefing_status, 'package_projected'),
                                last_briefing_update = NOW()
                            WHERE id = %s
                            """,
                            (json.dumps(briefing_json), eid),
                        )
                    conn.commit()
            except Exception:
                pass
            event_results.append({"tracked_event_id": eid, **(res if isinstance(res, dict) else {"ok": True})})
        except Exception as e:
            event_results.append({"tracked_event_id": eid, "ok": False, "error": str(e)})

    ok = any(r.get("ok") and not r.get("skipped") for r in storyline_results) or any(
        r.get("ok") for r in event_results
    )
    if not targets and not event_results:
        return {
            "ok": False,
            "error": "no_targets",
            "package_id": int(package_id),
            "story_id": (story or {}).get("id"),
            "patch_keys": sorted(patch.keys()),
            "storylines": storyline_results,
            "tracked_events": event_results,
            "targets_found": 0,
        }
    return {
        "ok": ok,
        "package_id": int(package_id),
        "story_id": (story or {}).get("id"),
        "patch_keys": sorted(patch.keys()),
        "storylines": storyline_results,
        "tracked_events": event_results,
        "targets_found": len(targets),
    }


def backfill_published_packages(*, limit: int = 50, only_missing: bool = True) -> dict[str, Any]:
    """Project already-published packages (ops / catch-up)."""
    from shared.domain_registry import resolve_domain_schema

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (p.id) p.id, s.id AS story_id
                FROM intelligence.editorial_packages p
                JOIN intelligence.news_stories s ON s.package_id = p.id AND s.status = 'published'
                WHERE p.status = 'published'
                ORDER BY p.id, s.published_at DESC NULLS LAST, s.id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall()

    results = []
    for package_id, story_id in rows:
        if only_missing:
            pkg = None
            try:
                from services.editorial_package_service import get_package

                pkg = get_package(int(package_id), include=True)
            except Exception:
                pkg = None
            targets = resolve_package_storyline_targets(pkg or {}) if pkg else []
            needs = False
            for domain_key, sid in targets:
                schema = resolve_domain_schema(domain_key)
                if not schema:
                    continue
                try:
                    with get_ui_db_connection_context() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                f"""
                                SELECT document_status,
                                       editorial_document IS NULL
                                         OR editorial_document = '{{}}'::jsonb AS empty_doc
                                FROM {schema}.storylines WHERE id = %s
                                """,
                                (sid,),
                            )
                            row = cur.fetchone()
                            if not row:
                                continue
                            status, empty = row[0], bool(row[1])
                            if empty or str(status or "") in ("", "auto_seeded", "parse_failed"):
                                needs = True
                                break
                except Exception:
                    needs = True
                    break
            if targets and not needs:
                results.append(
                    {"package_id": package_id, "skipped": True, "reason": "already_projected"}
                )
                continue
        results.append(project_package_to_editorial(int(package_id), story_id=int(story_id)))

    return {
        "ok": True,
        "processed": len(results),
        "results": results,
    }
