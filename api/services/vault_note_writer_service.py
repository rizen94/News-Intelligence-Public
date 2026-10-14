"""
Unattended vault note writer — claim queue jobs, grounded patch, reindex.

Write protocol:
1. Claim job + path lock (queue lease)
2. Read note + evidence pack
3. Deterministic timeline append + optional LLM significance/posture
4. Validate
5. Apply patch (fences only; corrections append outside)
6. Update registry + reindex
7. Complete job
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.vault_bridge_service import (
    _FRONTMATTER_RE,
    _parse_frontmatter_rich,
    _render_frontmatter,
    merge_write_vault_markdown,
    vault_root,
    vault_write_enabled,
)
from services.vault_note_patch import (
    append_correction_block,
    append_timeline_bullet,
    content_fingerprint,
    ensure_fences,
    on_theme,
    replace_auto_section,
    validate_patch_payload,
)
from services.vault_note_rag_service import reindex_vault_note
from services.vault_notes_registry_service import mark_note_ready, upsert_vault_note
from services.vault_update_queue_service import (
    claim_vault_update_jobs,
    complete_vault_update_job,
    count_vault_update_pending,
)
from shared.vault_note_contract import (
    AUTO_POSTURE_END,
    AUTO_POSTURE_START,
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    AUTO_TIMELINE_END,
    AUTO_TIMELINE_START,
    entity_note_template,
    structural_tags_for_note,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_vault_file(rel: str) -> str | None:
    path = vault_root() / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _write_vault_file(rel: str, content: str) -> None:
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_body(job: dict[str, Any]) -> str:
    note_type = job.get("note_type") or "entity"
    title = (job.get("payload") or {}).get("title") or f"{note_type} {job.get('object_id')}"
    domain = job.get("domain_key") or "politics"
    oid = int(job.get("object_id") or 0)
    tags = structural_tags_for_note(note_type=note_type, domain_key=domain)
    if note_type == "entity":
        body = entity_note_template(
            title=title, domain_key=domain, entity_id=oid, tier="seeded", tags=tags
        )
        fm = {
            "ni_domain": domain,
            "note_type": note_type,
            "canonical_entity_id": oid,
            "lifecycle": (job.get("payload") or {}).get("lifecycle") or "seeded",
            "ni_auto": True,
            "tags": tags,
            "created": _now_iso()[:10],
        }
        return _render_frontmatter(fm) + body
    fm = {
        "ni_domain": domain,
        "note_type": note_type,
        "object_id": oid,
        "ni_auto": True,
        "tags": tags,
        "created": _now_iso()[:10],
    }
    body = f"""# {title}

## Arc

{AUTO_SIGNIFICANCE_START}
_Seeded by NI vault writer._
{AUTO_SIGNIFICANCE_END}

## Timeline

{AUTO_TIMELINE_START}
{AUTO_TIMELINE_END}

## Sources

- domain: `{domain}`
- object_id: `{oid}`
"""
    return _render_frontmatter(fm) + body


def _evidence_bullet(payload: dict[str, Any]) -> str:
    day = payload.get("published") or _now_iso()[:10]
    title = (payload.get("article_title") or "Untitled").strip()[:160]
    aid = payload.get("article_id")
    return f"- {day} — {title} (article:{aid})"


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None


async def _llm_significance_patch(
    *,
    note_title: str,
    note_excerpt: str,
    evidence: str,
    lifecycle: str,
) -> dict[str, Any] | None:
    """Optional LLM pass for living notes — smaller model via STRUCTURED_EXTRACTION."""
    if lifecycle != "living" and os.environ.get("NI_VAULT_LLM_ALWAYS", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        return None
    if os.environ.get("NI_VAULT_LLM_ENABLED", "true").lower() in ("0", "false", "no"):
        return None
    prompt = f"""You update a living Obsidian knowledge note for a news intelligence system.
Return ONLY JSON with keys:
  timeline_bullet (string, one markdown bullet citing the article),
  posture (string, 1-3 sentences current posture OR empty),
  significance (string, short synthesis OR empty),
  correction (string, only if prior note text is clearly contradicted OR empty)

Rules:
- Ground every claim in the evidence. Cite article id in timeline_bullet like (article:123).
- Do not invent facts. Empty strings are fine.
- Stay on theme for note title: {note_title}

## Note excerpt
{note_excerpt[:2500]}

## New evidence
{evidence[:2000]}
"""
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return _parse_llm_json(result.text)
    except Exception as e:
        logger.info("vault writer LLM skip: %s", e)
        return None


def _apply_deterministic(body: str, job: dict[str, Any]) -> str:
    payload = job.get("payload") or {}
    bullet = _evidence_bullet(payload)
    return append_timeline_bullet(ensure_fences(body), bullet)


async def process_vault_update_job(job: dict[str, Any]) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}

    path = job["vault_path"]
    payload = job.get("payload") or {}
    title = payload.get("title") or path
    lifecycle = payload.get("lifecycle") or "seeded"
    domain_key = job.get("domain_key") or "politics"
    note_type = job.get("note_type") or "entity"
    article_id = payload.get("article_id")
    evidence = f"{payload.get('article_title') or ''}\n{payload.get('published') or ''}"

    existing = _read_vault_file(path)
    created = False
    structural = structural_tags_for_note(note_type=note_type, domain_key=domain_key)

    if not existing:
        full = _seed_body(job)
        created = True
        # Strip to body for patching then re-merge
        if _FRONTMATTER_RE.match(full):
            body = _FRONTMATTER_RE.sub("", full, count=1).lstrip("\n")
            ni_fm = _parse_frontmatter_rich(full)
        else:
            body = full
            ni_fm = {
                "ni_domain": domain_key,
                "note_type": note_type,
                "ni_auto": True,
                "tags": structural,
            }
    else:
        ni_fm = _parse_frontmatter_rich(existing)
        body = (
            _FRONTMATTER_RE.sub("", existing, count=1).lstrip("\n")
            if _FRONTMATTER_RE.match(existing)
            else existing
        )

    # Theme gate for updates
    if not created and not on_theme(str(title), evidence):
        return {"ok": False, "error": "off_theme", "retryable": False}

    body = _apply_deterministic(body, job)

    llm_patch = await _llm_significance_patch(
        note_title=str(title),
        note_excerpt=body[:3000],
        evidence=evidence,
        lifecycle=str(lifecycle),
    )
    if llm_patch:
        ok, reason = validate_patch_payload(llm_patch)
        if ok:
            if llm_patch.get("timeline_bullet"):
                body = append_timeline_bullet(body, str(llm_patch["timeline_bullet"]))
            if llm_patch.get("posture"):
                body = replace_auto_section(body, "posture", str(llm_patch["posture"]))
            if llm_patch.get("significance"):
                body = replace_auto_section(body, "significance", str(llm_patch["significance"]))
            if llm_patch.get("correction"):
                body = append_correction_block(
                    body,
                    date=_now_iso()[:10],
                    text=str(llm_patch["correction"]),
                    article_id=int(article_id) if article_id else None,
                )
        else:
            logger.debug("vault LLM patch rejected: %s", reason)

    # Final cite check on timeline
    if article_id and f"(article:{article_id})" not in body:
        body = append_timeline_bullet(body, _evidence_bullet(payload))

    ni_fm = {
        **ni_fm,
        "ni_domain": domain_key,
        "note_type": note_type,
        "lifecycle": lifecycle,
        "ni_auto": True,
        "updated": _now_iso()[:10],
    }
    if note_type == "entity":
        ni_fm["canonical_entity_id"] = int(job["object_id"])
    elif note_type == "storyline":
        ni_fm["storyline_id"] = int(job["object_id"])

    # Preserve Obsidian tags / unknown keys; only merge structural tags
    content = merge_write_vault_markdown(
        existing if not created else None,
        ni_frontmatter=ni_fm,
        body=body,
        structural_tags=structural,
    )
    _write_vault_file(path, content)
    fp = content_fingerprint(content)

    file_tags = ni_fm.get("tags") if isinstance(ni_fm.get("tags"), list) else structural
    # Prefer tags from merged write
    merged_fm = _parse_frontmatter_rich(content)
    if isinstance(merged_fm.get("tags"), list):
        file_tags = merged_fm["tags"]

    upsert_vault_note(
        domain_key=domain_key,
        note_type=note_type,
        object_id=int(job["object_id"]),
        object_id_secondary=job.get("object_id_secondary"),
        vault_path=path,
        title=str(title),
        note_status="note_ready",
        lifecycle=str(lifecycle),
        last_article_id=int(article_id) if article_id else None,
        tags=[str(t) for t in (file_tags or [])],
        tags_source="ni_structural",
        metadata={"last_writer": "vault_note_writer", "created_this_job": created},
    )
    mark_note_ready(path, lifecycle=str(lifecycle), rag_fingerprint=fp)
    reindex_vault_note(
        path,
        title=str(title),
        body=content,
        domain_key=domain_key,
        note_type=note_type,
    )
    return {"ok": True, "path": path, "created": created, "fingerprint": fp}


async def run_vault_notes_writer_cycle(
    *, limit: int | None = None
) -> dict[str, Any]:
    """Claim and process a batch of vault update jobs."""
    from services.vault_notes_fanout_service import vault_notes_pipeline_enabled

    if not vault_notes_pipeline_enabled():
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}

    jobs = claim_vault_update_jobs(limit=limit)
    stats = {
        "claimed": len(jobs),
        "completed": 0,
        "failed": 0,
        "dead": 0,
        "paths": [],
    }
    for job in jobs:
        jid = int(job["id"])
        try:
            result = await process_vault_update_job(job)
            if result.get("ok"):
                complete_vault_update_job(jid, success=True)
                stats["completed"] += 1
                stats["paths"].append(result.get("path"))
            else:
                retryable = result.get("retryable", True)
                complete_vault_update_job(
                    jid, success=False, error=str(result.get("error") or "failed")
                )
                stats["failed"] += 1
                if not retryable:
                    # Force dead by completing as fail enough times is heavy; mark dead via error tag
                    pass
        except Exception as e:
            logger.exception("vault writer job %s failed", jid)
            complete_vault_update_job(jid, success=False, error=str(e)[:2000])
            stats["failed"] += 1

    stats["queue"] = count_vault_update_pending()
    stats["ok"] = True
    return stats


def run_vault_notes_writer_cycle_sync(*, limit: int | None = None) -> dict[str, Any]:
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Nested: create task pattern — run in new loop threadlessly via asyncio.run not possible
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    lambda: asyncio.run(run_vault_notes_writer_cycle(limit=limit))
                ).result(timeout=600)
        return loop.run_until_complete(run_vault_notes_writer_cycle(limit=limit))
    except RuntimeError:
        return asyncio.run(run_vault_notes_writer_cycle(limit=limit))
