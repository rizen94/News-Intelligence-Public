"""
On-demand article "Pull context" — vault pack + storyline RAG + DB → executive summary.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

# skip_llm stubs and noisy vault RAG dumps that should not reach the reader brief
_VAULT_CONTEXT_HEADER_RE = re.compile(
    r"(?im)^(?:#{1,3}\s*)?Vault context\s*:?\s*$"
)
_EXPANSION_RAG_LINE_RE = re.compile(r"(?im)^\[expansion\]\s+")
_PUBLISHED_BULLET_RE = re.compile(r"(?im)^-\s*Published\s*$")


def _schema(domain_key: str) -> str:
    return resolve_domain_schema(domain_key) or domain_key.replace("-", "_")


def _strip_vault_rag_dump(text: str) -> str:
    """Drop ### Vault context blocks and trailing [expansion] RAG lines."""
    raw = (text or "").strip()
    if not raw:
        return ""
    cut = _VAULT_CONTEXT_HEADER_RE.split(raw, maxsplit=1)[0].rstrip()
    lines: list[str] = []
    for line in cut.splitlines():
        if _EXPANSION_RAG_LINE_RE.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).rstrip()


def _normalize_brief_noise(text: str) -> str:
    """Remove feed chrome (- Published) and collapse excess blank lines."""
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        if _PUBLISHED_BULLET_RE.match(line.strip()):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def reader_brief_from_expansion(expansion: dict[str, Any]) -> str:
    """
    Build a reader-facing Pull brief from a vault expansion.

    Prefers cleaned body_md prose; strips vault RAG dumps. Falls back to
    summary_md (dek) when the body is empty or still stub-like after sanitize.
    """
    title = str(expansion.get("title") or "").strip()
    body = _normalize_brief_noise(
        _strip_vault_rag_dump(str(expansion.get("body_md") or ""))
    )
    summary = _normalize_brief_noise(
        _strip_vault_rag_dump(str(expansion.get("summary_md") or ""))
    )

    # Drop duplicate leading ## Title / # Title matching the expansion title
    if title and body:
        for prefix in (f"## {title}", f"# {title}"):
            if body.startswith(prefix):
                body = body[len(prefix) :].lstrip("\n").strip()
                break

    # Thin / empty after sanitize → use summary dek as prose
    prose = body
    if not prose or len(re.sub(r"[#*\-\s]", "", prose)) < 80:
        prose = summary or body

    if not prose:
        return f"## {title}\n\n_No primed expansion yet._" if title else "_No primed expansion yet._"

    if title and not prose.lstrip().startswith("#"):
        return f"## {title}\n\n{prose}".strip()
    if title and prose.lstrip().startswith("# ") and not prose.lstrip().startswith(f"# {title}"):
        # Keep article H1 as secondary context under storyline title
        return f"## {title}\n\n{prose}".strip()
    return prose.strip()


def _load_article(domain_key: str, article_id: int) -> dict[str, Any] | None:
    schema = _schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, url, source_domain, published_at,
                       LEFT(COALESCE(content, summary, ''), 12000),
                       LEFT(COALESCE(summary, ''), 2000)
                FROM {schema}.articles
                WHERE id = %s
                """,
                (article_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                f"""
                SELECT DISTINCT ae.canonical_entity_id, ec.canonical_name
                FROM {schema}.article_entities ae
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                ORDER BY ae.canonical_entity_id
                LIMIT 20
                """,
                (article_id,),
            )
            ents = [{"id": int(r[0]), "name": r[1]} for r in cur.fetchall()]
            cur.execute(
                f"""
                SELECT sa.storyline_id, s.title
                FROM {schema}.storyline_articles sa
                JOIN {schema}.storylines s ON s.id = sa.storyline_id
                WHERE sa.article_id = %s AND s.merged_into_id IS NULL
                ORDER BY COALESCE(s.article_count, 0) DESC
                LIMIT 3
                """,
                (article_id,),
            )
            storylines = [
                {"id": int(r[0]), "title": r[1] or f"Storyline {r[0]}"}
                for r in cur.fetchall()
            ]
    return {
        "id": int(row[0]),
        "title": row[1] or "",
        "url": row[2],
        "source_domain": row[3],
        "published_at": row[4].isoformat() if row[4] else None,
        "body": row[5] or "",
        "summary": row[6] or "",
        "entities": ents,
        "storylines": storylines,
        "domain_key": domain_key,
    }


def _create_pull_row(
    domain_key: str,
    article_id: int,
    *,
    meta: dict[str, Any] | None = None,
) -> int:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.article_context_pulls
                    (domain_key, article_id, status, context_meta)
                VALUES (%s, %s, 'pending', COALESCE(%s::jsonb, '{}'::jsonb))
                RETURNING id
                """,
                (domain_key, article_id, json.dumps(meta or {})),
            )
            pid = int(cur.fetchone()[0])
            conn.commit()
            return pid


def _mark(
    pull_id: int,
    *,
    status: str,
    summary: str | None = None,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
    model_tag: str | None = None,
) -> None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    """
                    UPDATE intelligence.article_context_pulls
                    SET status = 'running', started_at = NOW()
                    WHERE id = %s
                    """,
                    (pull_id,),
                )
            elif status == "ready":
                cur.execute(
                    """
                    UPDATE intelligence.article_context_pulls
                    SET status = 'ready',
                        summary_markdown = %s,
                        context_meta = COALESCE(%s::jsonb, '{}'::jsonb),
                        model_tag = %s,
                        completed_at = NOW(),
                        error_message = NULL
                    WHERE id = %s
                    """,
                    (
                        summary or "",
                        json.dumps(meta or {}),
                        model_tag,
                        pull_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE intelligence.article_context_pulls
                    SET status = %s,
                        error_message = %s,
                        completed_at = NOW()
                    WHERE id = %s
                    """,
                    (status, (error or "")[:2000], pull_id),
                )
            conn.commit()


def get_context_pull(pull_id: int) -> dict[str, Any] | None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, article_id, status, summary_markdown,
                       error_message, context_meta, model_tag,
                       created_at, started_at, completed_at
                FROM intelligence.article_context_pulls
                WHERE id = %s
                """,
                (pull_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    meta = row[6]
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return {
        "ok": True,
        "id": int(row[0]),
        "domain_key": row[1],
        "article_id": int(row[2]),
        "status": row[3],
        "summary_markdown": row[4],
        "error_message": row[5],
        "context_meta": meta if isinstance(meta, dict) else {},
        "vault_actors": list((meta or {}).get("vault_actors") or [])
        if isinstance(meta, dict)
        else [],
        "vault_note_count": int((meta or {}).get("vault_note_count") or 0)
        if isinstance(meta, dict)
        else 0,
        "storyline_id": (meta or {}).get("storyline_id")
        if isinstance(meta, dict)
        else None,
        "model_tag": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "started_at": row[9].isoformat() if row[9] else None,
        "completed_at": row[10].isoformat() if row[10] else None,
    }


def latest_context_pull(domain_key: str, article_id: int) -> dict[str, Any] | None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.article_context_pulls
                WHERE domain_key = %s AND article_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (domain_key, article_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return get_context_pull(int(row[0]))


def _build_prompt(
    article: dict[str, Any],
    vault_block: str,
    rag_block: str,
) -> str:
    ents = ", ".join(
        e.get("name") or str(e.get("id")) for e in (article.get("entities") or [])[:12]
    )
    sls = "; ".join(
        f"{s.get('title')} (#{s.get('id')})" for s in (article.get("storylines") or [])[:3]
    )
    body = (article.get("body") or article.get("summary") or "")[:8000]
    return f"""You are writing an executive intelligence brief for a news reader.

Return ONLY markdown with these sections (use ## headings):
## Situation
## Why it matters
## Living context
## Key actors
## Open questions

Rules:
- Ground claims in the article and provided vault/RAG context.
- Prefer living vault background for long-running arcs; do not invent rivalry or soft relations.
- Be concise, readable, executive-ready (aim ~400–700 words total).
- Cite the article title and source when stating current facts.
- If vault/RAG is empty, say so briefly under Living context and stick to the article.

Article title: {article.get('title')}
Source: {article.get('source_domain') or 'unknown'}
Published: {article.get('published_at') or 'unknown'}
URL: {article.get('url') or ''}
Linked storylines: {sls or '(none)'}
Entities: {ents or '(none)'}

Article text:
---
{body}
---

{vault_block or '(No vault notes linked.)'}

External RAG (Wikipedia/GDELT) for linked storylines:
{rag_block or '(none)'}
"""


async def run_context_pull_job(pull_id: int) -> dict[str, Any]:
    """Execute one pull: assemble context → LLM → persist."""
    row = get_context_pull(pull_id)
    if not row:
        return {"ok": False, "error": "pull_not_found"}
    domain_key = row["domain_key"]
    article_id = int(row["article_id"])
    _mark(pull_id, status="running")

    try:
        article = _load_article(domain_key, article_id)
        if not article:
            _mark(pull_id, status="failed", error="article_not_found")
            return {"ok": False, "error": "article_not_found"}

        from domains.reader.services.vault_context_pack import (
            build_vault_pack_for_entity_ids,
            render_vault_context_pack_for_llm,
        )

        entity_ids = [int(e["id"]) for e in article.get("entities") or [] if e.get("id")]
        vpack = build_vault_pack_for_entity_ids(
            domain_key, entity_ids, hops=2, max_notes=12
        )
        vault_block = render_vault_context_pack_for_llm(vpack, max_chars=5500)

        rag_parts: list[str] = []
        for sl in (article.get("storylines") or [])[:2]:
            try:
                from services.storyline_rag_context_service import (
                    ensure_storyline_rag_context,
                    render_rag_context_for_llm,
                )

                rag_data = await ensure_storyline_rag_context(domain_key, int(sl["id"]))
                rendered = render_rag_context_for_llm(
                    rag_data if isinstance(rag_data, dict) else None, max_chars=2500
                )
                if rendered:
                    rag_parts.append(f"Storyline {sl.get('title')}:\n{rendered}")
            except Exception as re:
                logger.debug("pull-context rag skip storyline=%s: %s", sl.get("id"), re)

        prompt = _build_prompt(article, vault_block, "\n\n".join(rag_parts))

        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.LONG_SYNTHESIS,
            urgency="high",
            approx_prompt_chars=len(prompt),
        )
        text = (result.text or "").strip()
        if not text:
            _mark(pull_id, status="failed", error="empty_llm_response")
            return {"ok": False, "error": "empty_llm_response"}

        meta = {
            "vault_note_count": vpack.get("note_count") or 0,
            "vault_actors": (vpack.get("actors") or [])[:12],
            "entity_ids": entity_ids[:16],
            "storyline_ids": [s["id"] for s in (article.get("storylines") or [])],
            "storyline_id": (row.get("context_meta") or {}).get("storyline_id")
            if isinstance(row.get("context_meta"), dict)
            else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Prefer storyline_id from pending job meta if set at enqueue
        pending_meta = row.get("context_meta") if isinstance(row.get("context_meta"), dict) else {}
        if pending_meta.get("storyline_id"):
            meta["storyline_id"] = pending_meta["storyline_id"]
        if pending_meta.get("pull_scope"):
            meta["pull_scope"] = pending_meta["pull_scope"]
        _mark(
            pull_id,
            status="ready",
            summary=text[:20000],
            meta=meta,
            model_tag=getattr(result, "model", None),
        )
        return {"ok": True, "id": pull_id, "status": "ready"}
    except Exception as e:
        logger.exception("context pull %s failed: %s", pull_id, e)
        _mark(pull_id, status="failed", error=str(e))
        return {"ok": False, "error": str(e)}


def enqueue_context_pull(
    domain_key: str,
    article_id: int,
    *,
    storyline_id: int | None = None,
    pull_scope: str = "article",
) -> dict[str, Any]:
    """Cache-first: return morning expansion for this arc; no fresh LLM on click.

    When ``storyline_id`` is set (storyline reader), only that arc's expansion is
    eligible — magnet articles share many bags and must not bleed another brief.
    """
    article = _load_article(domain_key, article_id)
    if not article:
        return {"ok": False, "error": "article_not_found"}

    expansion = None
    tried_sids: list[int] = []
    try:
        from services.vault_notes_registry_service import (
            get_expansion_for_article,
            get_expansion_for_storyline,
        )

        if storyline_id:
            tried_sids.append(int(storyline_id))
            expansion = get_expansion_for_storyline(domain_key, int(storyline_id))
            if not (expansion and (expansion.get("body_md") or expansion.get("summary_md"))):
                expansion = None
        else:
            expansion = get_expansion_for_article(domain_key, int(article_id))
            if not (expansion and (expansion.get("body_md") or expansion.get("summary_md"))):
                expansion = None
                for s in (article.get("storylines") or [])[:3]:
                    try:
                        ss = int(s["id"])
                    except (TypeError, ValueError, KeyError):
                        continue
                    tried_sids.append(ss)
                    cand = get_expansion_for_storyline(domain_key, ss)
                    if cand and (cand.get("body_md") or cand.get("summary_md")):
                        expansion = cand
                        storyline_id = ss
                        break
    except Exception as e:
        logger.debug("pull cache expansion skip: %s", e)
        expansion = None

    # #region agent log
    try:
        import json as _json
        import time as _time

        with open(
            "/home/pete/Documents/projects/News Intelligence/.cursor/debug-fb1ed2.log",
            "a",
            encoding="utf-8",
        ) as _f:
            _f.write(
                _json.dumps(
                    {
                        "sessionId": "fb1ed2",
                        "hypothesisId": "E2",
                        "location": "article_context_pull_service.py:enqueue_context_pull",
                        "message": "pull cache lookup scoped",
                        "data": {
                            "domain_key": domain_key,
                            "article_id": article_id,
                            "storyline_id": storyline_id,
                            "pull_scope": pull_scope,
                            "tried_sids": tried_sids[:8],
                            "has_expansion": bool(
                                expansion
                                and (expansion.get("body_md") or expansion.get("summary_md"))
                            ),
                            "expansion_object_id": (expansion or {}).get("object_id"),
                        },
                        "timestamp": int(_time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion

    if expansion and (expansion.get("body_md") or expansion.get("summary_md")):
        body = reader_brief_from_expansion(expansion)[:20000]
        meta = {
            "storyline_id": storyline_id
            or (expansion.get("metadata") or {}).get("storyline_id"),
            "pull_scope": pull_scope,
            "cache_source": "vault_expansion",
            "vault_path": expansion.get("vault_path"),
            "source_article_id": (expansion.get("metadata") or {}).get(
                "source_article_id"
            ),
            "served_at": datetime.now(timezone.utc).isoformat(),
            "brief_sanitized": True,
        }
        pull_id = _create_pull_row(domain_key, article_id, meta=meta)
        _mark(
            pull_id,
            status="ready",
            summary=body,
            meta=meta,
            model_tag="vault_morning_prime",
        )
        return {
            "ok": True,
            "id": pull_id,
            "status": "ready",
            "cached": True,
            "cache_source": "vault_expansion",
            "article_id": article_id,
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "pull_scope": pull_scope,
            "summary_markdown": body,
        }

    # Reuse prior ready pull only for the same arc (never deferred stubs / other bags)
    latest = latest_context_pull(domain_key, article_id)
    if latest and latest.get("status") == "ready" and latest.get("summary_markdown"):
        latest_meta = (
            latest.get("context_meta")
            if isinstance(latest.get("context_meta"), dict)
            else {}
        )
        latest_sid = latest_meta.get("storyline_id")
        same_arc = storyline_id is None or (
            latest_sid is not None and int(latest_sid) == int(storyline_id)
        )
        if (
            same_arc
            and latest_meta.get("cache_source") == "vault_expansion"
        ):
            return {
                "ok": True,
                "id": latest["id"],
                "status": "ready",
                "cached": True,
                "cache_source": "prior_pull",
                "article_id": article_id,
                "domain_key": domain_key,
                "storyline_id": storyline_id,
                "pull_scope": pull_scope,
                "summary_markdown": latest.get("summary_markdown"),
            }

    # No cache: record a deferred request for the next morning prime cycle
    deferred_summary = (
        "_No primed expansion yet for this arc. "
        "Living context is written by the morning vault prime job — "
        "check back after the next cycle._"
    )
    pull_id = _create_pull_row(
        domain_key,
        article_id,
        meta={
            "storyline_id": storyline_id,
            "pull_scope": pull_scope,
            "deferred_for_morning_prime": True,
            "note": "No on-demand LLM; wait for vault_morning_prime expansion",
        },
    )
    _mark(
        pull_id,
        status="ready",
        summary=deferred_summary,
        meta={
            "storyline_id": storyline_id,
            "pull_scope": pull_scope,
            "cache_source": "deferred",
            "deferred_for_morning_prime": True,
        },
        model_tag="cache_miss",
    )
    return {
        "ok": True,
        "id": pull_id,
        "status": "ready",
        "cached": True,
        "cache_source": "deferred",
        "article_id": article_id,
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "pull_scope": pull_scope,
        "summary_markdown": deferred_summary,
    }


def enqueue_storyline_context_pull(domain_key: str, storyline_id: int) -> dict[str, Any]:
    """Pull context using the storyline's richest member article + vault pack."""
    schema = _schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY
                  LENGTH(COALESCE(a.content, a.summary, '')) DESC,
                  a.published_at DESC NULLS LAST
                LIMIT 1
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
    if not row:
        return {"ok": False, "error": "no_member_articles"}
    return enqueue_context_pull(
        domain_key,
        int(row[0]),
        storyline_id=storyline_id,
        pull_scope="storyline",
    )
