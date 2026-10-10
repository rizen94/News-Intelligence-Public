"""
Situation brief for vault cluster hubs — cached executive summary anytime.

Reuses hub indexes only; never merges storyline_articles.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

BRIEF_STALE_HOURS = float(os.environ.get("NI_HUB_BRIEF_STALE_HOURS", "6"))
BRIEF_MAX_PER_CYCLE = int(os.environ.get("NI_HUB_BRIEF_MAX_PER_CYCLE", "4"))
BRIEF_MAX_CHARS = 1200


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_brief_fingerprint(
    *,
    member_storyline_ids: list[int],
    domain_key: str,
) -> str:
    """Hash of sorted member ids + latest article activity per member."""
    members = sorted({int(x) for x in member_storyline_ids if int(x) > 0})
    if not members:
        return hashlib.sha256(b"empty").hexdigest()[:40]
    schema = resolve_domain_schema(domain_key)
    stamps: list[str] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT sa.storyline_id,
                           MAX(COALESCE(a.published_at, sa.added_at))::text
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = ANY(%s)
                    GROUP BY sa.storyline_id
                    """,
                    (members,),
                )
                by_sid = {int(r[0]): (r[1] or "") for r in (cur.fetchall() or [])}
        for sid in members:
            stamps.append(f"{sid}:{by_sid.get(sid, '')}")
    except Exception as e:
        logger.debug("brief fingerprint fallback: %s", e)
        stamps = [str(s) for s in members]
    raw = f"{domain_key}|{'|'.join(stamps)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _brief_is_stale(meta: dict[str, Any], fingerprint: str) -> bool:
    if not (meta.get("current_brief") or "").strip():
        return True
    if str(meta.get("brief_fingerprint") or "") != fingerprint:
        return True
    updated = meta.get("brief_updated_at")
    if not updated:
        return True
    try:
        dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
        return age_h >= BRIEF_STALE_HOURS
    except Exception:
        return True


def _build_evidence_text(hub: dict[str, Any]) -> str:
    domain_key = str(hub.get("domain_key") or "politics")
    members = [int(x) for x in (hub.get("member_storyline_ids") or [])]
    seeds = [int(x) for x in (hub.get("seed_entity_ids") or [])]
    schema = resolve_domain_schema(domain_key)
    parts: list[str] = [
        f"Situation: {hub.get('title') or hub.get('cluster_key')}",
        f"Domain: {domain_key}",
        f"Cluster key: {hub.get('cluster_key')}",
    ]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if members:
                cur.execute(
                    f"""
                    SELECT id, COALESCE(title, ''), COALESCE(article_count, 0)::int
                    FROM {schema}.storylines
                    WHERE id = ANY(%s) AND status = 'active'
                    ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST
                    LIMIT 12
                    """,
                    (members,),
                )
                parts.append("Member episodes:")
                for sid, title, ac in cur.fetchall() or []:
                    parts.append(f"- [{sid}] {(title or '')[:120]} ({ac} arts)")
                cur.execute(
                    f"""
                    SELECT a.published_at::date, a.title, a.id, sa.storyline_id
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = ANY(%s)
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT 16
                    """,
                    (members,),
                )
                parts.append("Recent timeline:")
                seen: set[int] = set()
                for pub, title, aid, sid in cur.fetchall() or []:
                    if int(aid) in seen:
                        continue
                    seen.add(int(aid))
                    day = pub.isoformat() if pub else "undated"
                    parts.append(
                        f"- {day} — {(title or 'Untitled')[:140]} (art:{aid}, ep:{sid})"
                    )
    try:
        from domains.reader.services.vault_context_pack import (
            build_vault_context_pack,
            render_vault_context_pack_for_llm,
        )

        vpack = build_vault_context_pack(
            domain_key=domain_key,
            entity_ids=seeds[:10],
            hops=1,
            max_notes=8,
        )
        rendered = render_vault_context_pack_for_llm(vpack, max_chars=2500)
        if rendered:
            parts.append("Vault context:")
            parts.append(rendered)
    except Exception as e:
        logger.debug("hub brief vault pack skip: %s", e)
    return "\n".join(parts)


def _prompt(title: str, evidence: str) -> str:
    return f"""You are a news intelligence analyst. Write a CURRENT BRIEF for this situation hub.

Rules:
- 2–4 short paragraphs (or tight bullets), max ~180 words
- Ground only in the evidence below; no speculation
- Lead with what is happening now, then why it matters
- Do not invent membership merges or claim one mega-storyline
- Plain prose; no markdown headings

Situation title: {title}

Evidence:
{evidence[:9000]}
"""


async def _llm_brief(prompt: str) -> str:
    from shared.services.ollama_model_caller import get_ollama_model_caller
    from shared.services.ollama_model_policy import InvocationKind

    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.INTERACTIVE_SUMMARY,
        urgency="standard",
        approx_prompt_chars=len(prompt),
    )
    return (result.text or "").strip()


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=180)
    return asyncio.run(coro)


def _persist_brief(hub: dict[str, Any], brief: str, fingerprint: str) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_note_patch import patch_auto_sections
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.vault_note_contract import cluster_object_id

    domain_key = str(hub.get("domain_key") or "politics")
    cluster_key = str(hub.get("cluster_key") or hub.get("id"))
    vault_path = hub.get("vault_path") or ""
    brief_clean = (brief or "").strip()[:BRIEF_MAX_CHARS]
    now = _now_iso()
    meta_patch = {
        "current_brief": brief_clean,
        "brief_updated_at": now,
        "brief_fingerprint": fingerprint,
        "hub": True,
        "cluster_key": cluster_key,
        "member_storyline_ids": list(hub.get("member_storyline_ids") or []),
        "seed_entity_ids": list(hub.get("seed_entity_ids") or []),
        "domain_key": domain_key,
    }

    if vault_path:
        try:
            path = vault_root() / vault_path
            if path.is_file():
                existing = path.read_text(encoding="utf-8")
                patched = patch_auto_sections(existing, brief=brief_clean)
                path.write_text(patched, encoding="utf-8")
        except Exception as e:
            logger.warning("hub brief vault patch %s: %s", vault_path, e)

    oid = int(hub.get("object_id") or 0) or cluster_object_id(cluster_key)
    upsert_vault_note(
        domain_key=domain_key,
        note_type="cluster",
        object_id=oid,
        vault_path=vault_path,
        title=hub.get("title"),
        note_status="note_ready",
        lifecycle="living",
        tags=list(hub.get("tags") or []) or None,
        metadata=meta_patch,
        tags_source="ni_structural",
    )
    return {
        "ok": True,
        "cluster_key": cluster_key,
        "current_brief": brief_clean,
        "brief_updated_at": now,
        "brief_fingerprint": fingerprint,
        "brief_chars": len(brief_clean),
    }


def refresh_hub_brief(
    hub: dict[str, Any],
    *,
    force: bool = False,
    dry_run: bool = False,
    extra_evidence: str | None = None,
) -> dict[str, Any]:
    """Regenerate current_brief when fingerprint drifted or force=True."""
    from services.vault_cluster_hub_service import vault_cluster_hubs_enabled

    if not vault_cluster_hubs_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}

    domain_key = str(hub.get("domain_key") or "politics")
    members = list(hub.get("member_storyline_ids") or [])
    meta = hub.get("metadata") if isinstance(hub.get("metadata"), dict) else {}
    # list_cluster_hubs already flattens brief fields; merge for stale check
    flat_meta = {
        **meta,
        "current_brief": hub.get("current_brief") or meta.get("current_brief"),
        "brief_updated_at": hub.get("brief_updated_at") or meta.get("brief_updated_at"),
        "brief_fingerprint": hub.get("brief_fingerprint") or meta.get("brief_fingerprint"),
    }
    fp = compute_brief_fingerprint(
        member_storyline_ids=members, domain_key=domain_key
    )
    if extra_evidence:
        # Clip/wiki express updates should refresh even when storyline stamp is unchanged.
        fp = hashlib.sha256(f"{fp}|mvp:{extra_evidence[:800]}".encode("utf-8")).hexdigest()[:40]
    if not force and not _brief_is_stale(flat_meta, fp):
        return {
            "ok": True,
            "skipped": True,
            "reason": "fingerprint_fresh",
            "cluster_key": hub.get("cluster_key"),
            "brief_fingerprint": fp,
        }

    evidence = _build_evidence_text(hub)
    if extra_evidence:
        evidence = f"{extra_evidence.strip()}\n\n{evidence}"
    title = str(hub.get("title") or hub.get("cluster_key") or "Situation")
    prompt = _prompt(title, evidence)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "cluster_key": hub.get("cluster_key"),
            "prompt_chars": len(prompt),
            "brief_fingerprint": fp,
        }

    try:
        text = _run_async(_llm_brief(prompt))
    except Exception as e:
        logger.warning("hub brief LLM %s: %s", hub.get("cluster_key"), e)
        return {"ok": False, "error": str(e), "cluster_key": hub.get("cluster_key")}

    if not text:
        return {"ok": False, "error": "empty_llm", "cluster_key": hub.get("cluster_key")}

    return _persist_brief(hub, text, fp)


def _title_tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "watch",
        "live",
        "new",
        "says",
        "after",
        "over",
        "into",
        "onto",
        "about",
        "against",
        "amid",
        "near",
        "case",
    }
    return {
        t.lower()
        for t in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text or "")
        if t.lower() not in stop
    }


def _persist_wiki_thread_brief(
    *,
    domain_key: str,
    vault_path: str,
    title: str,
    brief: str,
    article_id: int | None = None,
) -> dict[str, Any]:
    """Express onto a wiki note (entity/cluster) when no Situation hub matched."""
    from services.vault_bridge_service import vault_root, vault_write_enabled
    from services.vault_note_patch import patch_auto_sections
    from services.vault_notes_registry_service import get_vault_note_by_path, upsert_vault_note

    if not vault_write_enabled():
        return {"ok": False, "error": "vault_write_disabled"}
    if not vault_path:
        return {"ok": False, "error": "no_path"}
    path = vault_root() / vault_path
    if not path.is_file():
        return {"ok": False, "error": "missing_file", "path": vault_path}

    brief_clean = (brief or "").strip()[:BRIEF_MAX_CHARS]
    if not brief_clean:
        return {"ok": False, "error": "empty_brief"}

    note = None
    try:
        note = get_vault_note_by_path(vault_path)
    except Exception:
        note = None
    meta = dict((note or {}).get("metadata") or {}) if isinstance(note, dict) else {}
    # Hand-curated entity/cluster briefs (e.g. Trump grounding) must not be
    # overwritten by thin MVP wiki-thread express.
    if meta.get("brief_locked") is True or str(meta.get("brief_locked") or "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return {
            "ok": True,
            "skipped": True,
            "reason": "brief_locked",
            "path": vault_path,
            "current_brief": meta.get("current_brief"),
            "express_kind": "wiki_thread",
        }

    try:
        existing = path.read_text(encoding="utf-8")
        patched = patch_auto_sections(existing, brief=brief_clean)
        path.write_text(patched, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": str(e), "path": vault_path}

    meta.update(
        {
            "current_brief": brief_clean,
            "brief_updated_at": _now_iso(),
            "express_thread": True,
            "last_express_article_id": article_id,
        }
    )
    try:
        upsert_vault_note(
            domain_key=domain_key,
            note_type=str((note or {}).get("note_type") or "entity"),
            object_id=int((note or {}).get("object_id") or 0),
            vault_path=vault_path,
            title=title or (note or {}).get("title"),
            note_status="note_ready",
            lifecycle=str((note or {}).get("lifecycle") or "living"),
            metadata=meta,
            tags_source="ni_structural",
        )
    except Exception as e:
        logger.debug("wiki thread brief registry %s: %s", vault_path, e)
    return {
        "ok": True,
        "path": vault_path,
        "current_brief": brief_clean,
        "express_kind": "wiki_thread",
    }


def express_briefs_from_mvp(
    domain_key: str,
    *,
    article: dict[str, Any],
    clipping_path: str | None,
    clipping_summary: str | None,
    targets: list[dict[str, Any]],
    max_hubs: int = 2,
) -> dict[str, Any]:
    """Express step: refresh Situation briefs for hubs touched by this filing.

    Matching order:
    1) seed entity / vault_path hits
    2) title-token overlap with hub title / cluster_key
    3) similar cluster vault notes
    4) fallback: brief fence on the strongest distilled wiki target (thin one-offs)
    """
    from services.vault_cluster_hub_service import list_cluster_hubs, vault_cluster_hubs_enabled
    from services.vault_note_rag_service import find_similar_vault_notes

    if not vault_cluster_hubs_enabled():
        return {"ok": False, "skipped": True, "reason": "hubs_disabled"}

    entity_ids = {
        int(t["object_id"])
        for t in targets
        if t.get("object_id") and str(t.get("note_type") or "") == "entity"
    }
    target_paths = {str(t.get("vault_path") or "") for t in targets if t.get("vault_path")}
    article_toks = _title_tokens(
        f"{article.get('title') or ''} {clipping_summary or ''}"
    )

    # Prefer same-domain hubs, then a small cross-domain sweep for thin silos.
    hubs = list_cluster_hubs(domain_key=domain_key, limit=60)
    if len(hubs) < 3:
        try:
            hubs = list_cluster_hubs(domain_key=None, limit=80)
        except Exception:
            pass

    matched: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(h: dict[str, Any], reason: str) -> None:
        key = str(h.get("cluster_key") or h.get("vault_path") or h.get("id"))
        if not key or key in seen:
            return
        seen.add(key)
        hh = dict(h)
        hh["_express_match"] = reason
        matched.append(hh)

    for h in hubs:
        seeds = {int(x) for x in (h.get("seed_entity_ids") or []) if int(x) > 0}
        path = str(h.get("vault_path") or "")
        if (seeds & entity_ids) or (path and path in target_paths):
            _add(h, "seed_or_path")

    if len(matched) < max_hubs and article_toks:
        scored: list[tuple[int, dict[str, Any]]] = []
        for h in hubs:
            key = str(h.get("cluster_key") or h.get("vault_path") or h.get("id"))
            if key in seen:
                continue
            hub_toks = _title_tokens(
                f"{h.get('title') or ''} {h.get('cluster_key') or ''}"
            )
            overlap = len(article_toks & hub_toks)
            if overlap >= 2:
                scored.append((overlap, h))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("cluster_key") or "")))
        for _, h in scored[: max(0, max_hubs - len(matched))]:
            _add(h, "title_overlap")

    if len(matched) < max_hubs:
        query = f"{article.get('title') or ''} {clipping_summary or ''}"[:1500]
        try:
            sims = find_similar_vault_notes(
                domain_key=domain_key,
                note_type="cluster",
                query_text=query,
                limit=6,
            )
        except Exception:
            sims = []
        sim_paths = {
            str(s.get("vault_path") or ""): float(s.get("score") or 0)
            for s in sims
            if s.get("vault_path") and float(s.get("score") or 0) >= 0.08
        }
        for h in hubs:
            path = str(h.get("vault_path") or "")
            if path and path in sim_paths:
                _add(h, "similarity")
            if len(matched) >= max_hubs:
                break

    clip_bits = [
        f"Latest clipping: {(article.get('title') or '')[:160]}",
        f"article_id={article.get('id')}",
    ]
    if clipping_path:
        clip_bits.append(f"path={clipping_path}")
    if clipping_summary:
        clip_bits.append((clipping_summary or "")[:1200])
    wiki = ", ".join(
        f"{t.get('title') or t.get('vault_path')}"
        for t in targets[:8]
        if t.get("title") or t.get("vault_path")
    )
    if wiki:
        clip_bits.append(f"Wiki threads updated: {wiki}")
    extra = "\n".join(clip_bits)

    results: list[dict[str, Any]] = []
    refreshed = 0
    for hub in matched[: max(0, int(max_hubs))]:
        try:
            r = refresh_hub_brief(hub, force=True, extra_evidence=extra)
            r = dict(r)
            r["express_match"] = hub.get("_express_match")
            results.append(r)
            if r.get("ok") and not r.get("skipped"):
                refreshed += 1
        except Exception as e:
            logger.warning("mvp express brief %s: %s", hub.get("cluster_key"), e)
            results.append({"ok": False, "error": str(e), "cluster_key": hub.get("cluster_key")})

    wiki_express: dict[str, Any] | None = None
    if not matched and targets:
        # Thin one-offs: put a short brief on the best distilled wiki target.
        prefer = sorted(
            targets,
            key=lambda t: (
                0 if t.get("reason") in ("entity", "similarity", "similarity_gap", "title_match") else 1,
                0 if t.get("note_type") == "cluster" else 1,
                0 if not t.get("seed") else 1,
            ),
        )
        t0 = prefer[0]
        prompt = _prompt(
            str(t0.get("title") or article.get("title") or "Thread"),
            extra,
        )
        try:
            text = _run_async(_llm_brief(prompt))
            if text:
                wiki_express = _persist_wiki_thread_brief(
                    domain_key=domain_key,
                    vault_path=str(t0.get("vault_path") or ""),
                    title=str(t0.get("title") or ""),
                    brief=text,
                    article_id=int(article.get("id") or 0) or None,
                )
                if wiki_express.get("ok"):
                    refreshed += 1
                    results.append(wiki_express)
        except Exception as e:
            logger.debug("mvp wiki-thread express: %s", e)
            wiki_express = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "matched_hubs": len(matched),
        "refreshed": refreshed,
        "results": results,
        "wiki_thread_express": wiki_express,
    }


def refresh_stale_hub_briefs(
    *,
    domain_key: str | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    from services.vault_cluster_hub_service import list_cluster_hubs

    cap = BRIEF_MAX_PER_CYCLE if limit is None else max(1, int(limit))
    hubs = list_cluster_hubs(domain_key=domain_key, limit=80)
    stats: dict[str, Any] = {
        "ok": True,
        "checked": len(hubs),
        "refreshed": 0,
        "skipped": 0,
        "failed": 0,
        "results": [],
    }
    for h in hubs:
        if stats["refreshed"] >= cap and not force:
            break
        try:
            r = refresh_hub_brief(h, force=force)
            stats["results"].append(r)
            if r.get("skipped"):
                stats["skipped"] += 1
            elif r.get("ok"):
                stats["refreshed"] += 1
            else:
                stats["failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            logger.warning("refresh_stale_hub_briefs %s: %s", h.get("id"), e)
    return stats


def ensure_hub_brief_for_pack(
    hub: dict[str, Any],
    *,
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Stale-on-read: refresh brief if drifted; return brief fields for pack."""
    domain_key = str(hub.get("domain_key") or "politics")
    members = list(hub.get("member_storyline_ids") or [])
    meta = hub.get("metadata") if isinstance(hub.get("metadata"), dict) else {}
    flat = {
        **meta,
        "current_brief": hub.get("current_brief") or meta.get("current_brief"),
        "brief_updated_at": hub.get("brief_updated_at") or meta.get("brief_updated_at"),
        "brief_fingerprint": hub.get("brief_fingerprint") or meta.get("brief_fingerprint"),
    }
    fp = compute_brief_fingerprint(
        member_storyline_ids=members, domain_key=domain_key
    )
    refreshed = False
    if allow_llm and _brief_is_stale(flat, fp):
        # On-read: only regenerate when fingerprint changed (not mere age),
        # unless there is no brief at all.
        needs = not (flat.get("current_brief") or "").strip() or (
            str(flat.get("brief_fingerprint") or "") != fp
        )
        if needs:
            r = refresh_hub_brief(hub, force=False)
            refreshed = bool(r.get("ok") and not r.get("skipped"))
            if refreshed and r.get("current_brief"):
                flat["current_brief"] = r.get("current_brief")
                flat["brief_updated_at"] = r.get("brief_updated_at")
                flat["brief_fingerprint"] = r.get("brief_fingerprint")
            elif refreshed:
                from services.vault_cluster_hub_service import get_cluster_hub

                fresh = get_cluster_hub(
                    domain_key=domain_key,
                    hub_id=int(hub["id"]),
                )
                if fresh:
                    flat["current_brief"] = fresh.get("current_brief")
                    flat["brief_updated_at"] = fresh.get("brief_updated_at")
                    flat["brief_fingerprint"] = fresh.get("brief_fingerprint")
    return {
        "current_brief": flat.get("current_brief"),
        "brief_updated_at": flat.get("brief_updated_at"),
        "brief_fingerprint": flat.get("brief_fingerprint") or fp,
        "brief_refreshed": refreshed,
    }
