"""
Narrative evidence-expand — iterative multi-source research into package briefs (v11).

Keep Research literature-focused. This loop runs on Narrative packages
(politics / finance / legal): DB → Wiki/spine → web → vault (retrieve for
background + write brief scratchpad), then synthesizes
intelligence.package_evidence_briefs for Editor publish.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_int
from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_theme import is_theme_mismatch, package_spine_tokens

logger = logging.getLogger(__name__)

PROMPT_VERSION = "package_evidence_expand.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "narrative"
    / "package_evidence_expand.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9]+")


def is_enabled() -> bool:
    return env_bool("EDITORIAL_EVIDENCE_EXPAND_ENABLED", True)


def max_rounds() -> int:
    return max(1, env_int("EVIDENCE_EXPAND_MAX_ROUNDS", 3))


def web_expand_enabled() -> bool:
    return env_bool("EVIDENCE_EXPAND_WEB_ENABLED", True)


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Write JSON with lede, brief_md (required sections), open_questions, "
            "gaps, summary_stub. Cite only [@mN] from provided members."
        )


def _parse_json_obj(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except Exception:
                return None
    return None


def _member_blob(m: dict[str, Any]) -> str:
    prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
    parts = [
        m.get("display_label"),
        prov.get("label"),
        prov.get("quote"),
        prov.get("outcome"),
        prov.get("holding"),
        " ".join(str(x) for x in (prov.get("parties") or [])),
    ]
    return " ".join(str(p or "") for p in parts)


def _deterministic_gaps(package: dict[str, Any]) -> list[dict[str, Any]]:
    title = str(package.get("working_title") or "")
    stub = str(package.get("summary_stub") or "")
    members = [m for m in (package.get("members") or []) if m.get("status") == "active"]
    has_parties = any(
        isinstance(m.get("provenance"), dict) and m["provenance"].get("parties")
        for m in members
    )
    has_holding = any(
        isinstance(m.get("provenance"), dict)
        and (m["provenance"].get("holding") or m["provenance"].get("outcome"))
        for m in members
    )
    has_ce = any(m.get("member_type") == "chronological_event" for m in members)
    has_article = any(m.get("member_type") == "article" for m in members)
    gaps: list[dict[str, Any]] = []
    if not has_parties:
        gaps.append(
            {
                "id": "parties",
                "question": f"Who are the key parties / actors in: {title[:120]}?",
                "priority": 1,
                "status": "open",
            }
        )
    if not has_holding:
        gaps.append(
            {
                "id": "holding",
                "question": f"What was decided / held / ordered regarding: {title[:120]}?",
                "priority": 2,
                "status": "open",
            }
        )
    if not has_ce:
        gaps.append(
            {
                "id": "timeline_events",
                "question": f"Which chronological events belong on the timeline for: {title[:120]}?",
                "priority": 3,
                "status": "open",
            }
        )
    if not has_article:
        gaps.append(
            {
                "id": "reporting",
                "question": f"What contemporaneous reporting corroborates: {title[:80]}? {stub[:80]}",
                "priority": 4,
                "status": "open",
            }
        )
    gaps.append(
        {
            "id": "prior_context",
            "question": f"What prior law / precedent / context frames: {title[:120]}?",
            "priority": 5,
            "status": "open",
        }
    )
    return gaps[:8]


def _upsert_external_context(
    *,
    title: str,
    content: str,
    domain_key: str | None,
    source_url: str | None,
    source_type: str,
    metadata: dict[str, Any] | None = None,
) -> int | None:
    """Insert intelligence.contexts row for wiki/web evidence; return id."""
    meta = dict(metadata or {})
    if source_url:
        meta["source_url"] = source_url
    meta["evidence_expand"] = True
    meta["source_type_hint"] = source_type
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                # Reuse by URL when present.
                if source_url:
                    cur.execute(
                        """
                        SELECT id FROM intelligence.contexts
                        WHERE metadata->>'source_url' = %s
                        ORDER BY id DESC LIMIT 1
                        """,
                        (source_url,),
                    )
                    row = cur.fetchone()
                    if row:
                        return int(row[0])
                cur.execute(
                    """
                    INSERT INTO intelligence.contexts (
                        source_type, domain_key, title, content, raw_content, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        (source_type or "external")[:64],
                        (domain_key or "")[:64] or None,
                        (title or "")[:500],
                        content or "",
                        content or "",
                        json.dumps(meta),
                    ),
                )
                rid = cur.fetchone()
                conn.commit()
                return int(rid[0]) if rid else None
    except Exception as e:
        logger.debug("upsert_external_context failed: %s", e)
        return None


def _theme_ok(package: dict[str, Any], text: str) -> bool:
    title = str(package.get("working_title") or "")
    stub = str(package.get("summary_stub") or "")
    spine = package_spine_tokens(title, stub)
    if len(spine) < 1:
        return True
    return not is_theme_mismatch(text, title=title, stub=stub)


def _retrieve_db_candidates(
    package: dict[str, Any],
    gap: dict[str, Any],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    from services.editorial_package_service import search_attachable

    title = str(package.get("working_title") or "")
    q = f"{title} {gap.get('question') or ''}".strip()
    domain_keys = list(package.get("domain_keys") or []) or None
    out: list[dict[str, Any]] = []
    try:
        result = search_attachable(
            modal="narrative",
            q=q,
            domains=domain_keys,
            limit=limit,
        )
        for row in result.get("hits") or []:
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "member_type": row.get("member_type"),
                    "member_id": row.get("member_id"),
                    "domain_key": row.get("domain_key"),
                    "label": row.get("label")
                    or (row.get("provenance") or {}).get("label"),
                    "quote": (row.get("provenance") or {}).get("quote"),
                    "source_url": (row.get("provenance") or {}).get("source_url"),
                }
            )
    except Exception as e:
        logger.debug("search_attachable expand failed: %s", e)

    try:
        from services.embeddings_worker_service import search_embedding_chunks

        dk = (domain_keys or [None])[0]
        chunks = search_embedding_chunks(
            q,
            limit=min(6, limit),
            domain_key=dk,
            source_types=["article", "wikipedia", "reference_event"],
        )
        for ch in chunks or []:
            out.append(
                {
                    "member_type": "embedding_chunk",
                    "source_type": ch.get("source_type"),
                    "source_id": ch.get("source_id"),
                    "domain_key": ch.get("domain_key") or dk,
                    "label": (ch.get("title") or ch.get("source_id") or "")[:200],
                    "quote": (ch.get("chunk_text") or ch.get("text") or "")[:900],
                    "score": ch.get("score"),
                }
            )
    except Exception as e:
        logger.debug("embedding search expand failed: %s", e)
    return out[:limit]


def _retrieve_wiki(gap: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    query = str(gap.get("question") or package.get("working_title") or "").strip()
    # Prefer short search term from title spine.
    title = str(package.get("working_title") or "")
    search_term = title.split(":")[0].strip()[:80] or query[:80]
    try:
        from services.wikipedia_knowledge_service import (
            lookup_entity_with_fallback,
            search_entities,
        )

        ent = lookup_entity_with_fallback(search_term)
        if ent:
            hits.append(
                {
                    "source": "wikipedia",
                    "title": ent.get("title") or search_term,
                    "url": ent.get("url") or ent.get("page_url"),
                    "excerpt": (ent.get("summary") or ent.get("extract") or "")[:1200],
                }
            )
        for row in search_entities(search_term, limit=3) or []:
            hits.append(
                {
                    "source": "wikipedia",
                    "title": row.get("title"),
                    "url": row.get("url") or row.get("page_url"),
                    "excerpt": (row.get("summary") or row.get("extract") or "")[:900],
                }
            )
    except Exception as e:
        logger.debug("wikipedia expand failed: %s", e)

    try:
        from services.fact_verification_service import (
            wikidata_reference_check,
            wikipedia_reference_check,
        )

        claim = query[:400]
        wp = wikipedia_reference_check(claim, subject=search_term)
        wd = wikidata_reference_check(claim, subject=search_term)
        if wp.get("status") in ("supported", "partial") or wp.get("extract"):
            hits.append(
                {
                    "source": "wikipedia_verify",
                    "title": wp.get("title") or search_term,
                    "url": wp.get("url"),
                    "excerpt": (wp.get("extract") or wp.get("snippet") or "")[:900],
                    "status": wp.get("status"),
                }
            )
        if wd.get("label") or wd.get("id"):
            hits.append(
                {
                    "source": "wikidata",
                    "title": wd.get("label") or wd.get("id"),
                    "url": (
                        f"https://www.wikidata.org/wiki/{wd.get('id')}"
                        if wd.get("id")
                        else None
                    ),
                    "excerpt": (wd.get("description") or "")[:500],
                    "status": wd.get("status"),
                }
            )
    except Exception as e:
        logger.debug("wiki verify expand failed: %s", e)

    # Identity spine mention match (best-effort).
    try:
        from nri_core.spine.api.lookup import match_mention

        matched = match_mention(search_term)
        if matched is not None:
            data = matched
            if hasattr(matched, "__dict__"):
                data = {
                    "ftm_id": getattr(matched, "ftm_id", None)
                    or getattr(matched, "entity_id", None),
                    "name": getattr(matched, "caption", None)
                    or getattr(matched, "name", None)
                    or search_term,
                    "schema": getattr(matched, "schema_name", None)
                    or getattr(matched, "schema", None),
                }
            elif isinstance(matched, dict):
                data = matched
            else:
                data = {"name": str(matched)}
            hits.append(
                {
                    "source": "identity_spine",
                    "title": data.get("name") or search_term,
                    "url": None,
                    "excerpt": json.dumps(data, default=str)[:900],
                }
            )
    except Exception as e:
        logger.debug("spine match expand failed: %s", e)

    return hits[:6]


def _retrieve_vault(gap: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    """Situation / entity vault notes as background hits (not auto-attached members)."""
    del gap  # title/package drive retrieval; gaps still trigger the round
    try:
        from services.package_vault_context_service import (
            retrieve_vault_context_for_package,
        )

        pack = retrieve_vault_context_for_package(package, limit=6, max_chars=3200)
        if not pack.get("ok"):
            return []
        hits: list[dict[str, Any]] = []
        for n in pack.get("notes") or []:
            hits.append(
                {
                    "source": "vault_note",
                    "title": n.get("title"),
                    "url": None,
                    "vault_path": n.get("vault_path"),
                    "note_type": n.get("note_type"),
                    "excerpt": (n.get("excerpt") or "")[:1200],
                    "rank": n.get("rank"),
                    "background_only": True,
                }
            )
        return hits
    except Exception as e:
        logger.debug("vault retrieve expand failed: %s", e)
        return []


def _retrieve_web(gap: dict[str, Any], package: dict[str, Any]) -> list[dict[str, Any]]:
    if not web_expand_enabled():
        return []
    title = str(package.get("working_title") or "")
    q = (title or str(gap.get("question") or ""))[:120]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = "2020-01-01"
    hits: list[dict[str, Any]] = []
    try:
        from services.historic_context_sources import fetch_news_api, fetch_wikipedia

        for fn, src in ((fetch_wikipedia, "wikipedia_api"), (fetch_news_api, "newsapi")):
            try:
                findings = fn(q, start, today, limit=5) or []
            except TypeError:
                findings = []
            for f in findings:
                if hasattr(f, "__dict__"):
                    d = dict(f.__dict__) if not isinstance(f, dict) else f
                elif isinstance(f, dict):
                    d = f
                else:
                    continue
                hits.append(
                    {
                        "source": src,
                        "title": d.get("title") or d.get("headline"),
                        "url": d.get("url") or d.get("source_url"),
                        "excerpt": (d.get("snippet") or d.get("summary") or d.get("text") or "")[
                            :900
                        ],
                    }
                )
    except Exception as e:
        logger.debug("web historic expand failed: %s", e)

    # Queue fulltext pull for promising URLs (court / FR / news).
    try:
        from services.rag_evidence_pull_service import enqueue_evidence_pull

        dk = (list(package.get("domain_keys") or []) or ["legal"])[0]
        for h in hits[:3]:
            url = (h.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            enqueue_evidence_pull(
                domain_key=str(dk),
                pdf_url=url,
                selection_reason=f"evidence_expand:{gap.get('id')}",
                auto_queue=True,
                source_type="url_fetch",
            )
    except Exception as e:
        logger.debug("rag enqueue expand failed: %s", e)
    return hits[:8]


def _attach_db_hit(
    package_id: int,
    package: dict[str, Any],
    hit: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any] | None:
    from services.editorial_package_service import add_member

    mt = str(hit.get("member_type") or hit.get("type") or "").strip()
    mid = hit.get("member_id") or hit.get("id")
    # Promote embedding chunks → article/context (or external context for wiki/ref).
    if mt == "embedding_chunk":
        return _attach_embedding_chunk_hit(
            package_id, package, hit, actor=actor
        )
    if mt not in (
        "chronological_event",
        "article",
        "extracted_claim",
        "entity",
        "context",
    ):
        return None
    if mid is None:
        return None
    label = str(hit.get("label") or hit.get("title") or hit.get("display_label") or "")
    quote = str(hit.get("quote") or hit.get("snippet") or hit.get("excerpt") or "")
    blob = f"{label} {quote}"
    if not _theme_ok(package, blob):
        return None
    dk = hit.get("domain_key") or (list(package.get("domain_keys") or []) or [None])[0]
    try:
        member = add_member(
            package_id,
            member_type=mt,
            member_id=int(mid),
            domain_key=dk,
            role="supporting",
            added_by_modal="narrative",
            added_by=actor,
            provenance={
                "label": label[:240],
                "quote": quote[:900] or None,
                "source_url": hit.get("source_url") or hit.get("url"),
                "evidence_expand": True,
                "gap_id": hit.get("gap_id"),
            },
            metadata={"evidence_expand": True},
            actor=actor,
        )
        return member
    except Exception as e:
        logger.debug("attach db hit failed: %s", e)
        return None


def _attach_embedding_chunk_hit(
    package_id: int,
    package: dict[str, Any],
    hit: dict[str, Any],
    *,
    actor: str,
) -> dict[str, Any] | None:
    """Map embedding_chunk hits to attachable article/context members."""
    from services.editorial_package_service import add_member

    source_type = str(hit.get("source_type") or "").strip()
    source_id = str(hit.get("source_id") or hit.get("member_id") or "").strip()
    label = str(hit.get("label") or hit.get("title") or "")[:240]
    quote = str(hit.get("quote") or hit.get("excerpt") or "")[:900]
    blob = f"{label} {quote}"
    if not _theme_ok(package, blob):
        return None
    dk = hit.get("domain_key") or (list(package.get("domain_keys") or []) or [None])[0]

    # article chunks: source_id like "politics:12345"
    if source_type == "article" and ":" in source_id:
        parts = source_id.split(":", 1)
        try:
            article_dk, article_id = parts[0], int(parts[1])
        except (TypeError, ValueError):
            article_dk, article_id = dk, None
        if article_id is not None:
            try:
                return add_member(
                    package_id,
                    member_type="article",
                    member_id=int(article_id),
                    domain_key=article_dk or dk,
                    role="supporting",
                    added_by_modal="narrative",
                    added_by=actor,
                    provenance={
                        "label": label or f"article:{article_id}",
                        "quote": quote or None,
                        "evidence_expand": True,
                        "from_embedding_chunk": True,
                        "gap_id": hit.get("gap_id"),
                    },
                    metadata={"evidence_expand": True, "from_embedding_chunk": True},
                    actor=actor,
                )
            except Exception as e:
                logger.debug("attach embedding article failed: %s", e)

    # context chunks: source_id is context id
    if source_type == "context":
        try:
            ctx_id = int(source_id)
            return add_member(
                package_id,
                member_type="context",
                member_id=ctx_id,
                domain_key=dk,
                role="supporting",
                added_by_modal="narrative",
                added_by=actor,
                provenance={
                    "label": label or f"context:{ctx_id}",
                    "quote": quote or None,
                    "evidence_expand": True,
                    "from_embedding_chunk": True,
                    "gap_id": hit.get("gap_id"),
                },
                metadata={"evidence_expand": True, "from_embedding_chunk": True},
                actor=actor,
            )
        except Exception as e:
            logger.debug("attach embedding context failed: %s", e)

    # wikipedia / reference_event → external context member
    return _attach_external_hit(
        package_id,
        package,
        {
            "title": label or f"{source_type}:{source_id}",
            "excerpt": quote,
            "url": hit.get("url") or hit.get("source_url"),
            "source": f"embedding_chunk:{source_type or 'unknown'}",
        },
        actor=actor,
        gap_id=hit.get("gap_id"),
    )


def promote_members_before_compose(
    package_id: int,
    package: dict[str, Any],
    *,
    actor: str = "editor_compose",
    chunk_limit: int = 4,
    rag_limit: int = 4,
) -> dict[str, Any]:
    """Promote embedding_chunks + completed RAG pulls into members before compose.

    Safe to call when expand already ran — attach helpers theme-gate and
    add_member should no-op / skip duplicates via existing membership.
    """
    chunk_attached = 0
    title = str(package.get("working_title") or "").strip()
    stub = str(package.get("summary_stub") or "").strip()
    q = f"{title} {stub}".strip()[:200]
    domain_keys = list(package.get("domain_keys") or []) or None
    if q:
        try:
            from services.embeddings_worker_service import search_embedding_chunks

            dk = (domain_keys or [None])[0]
            chunks = search_embedding_chunks(
                q,
                limit=chunk_limit + 2,
                domain_key=dk,
                source_types=["article", "wikipedia", "reference_event", "context"],
            )
            for ch in chunks or []:
                hit = {
                    "member_type": "embedding_chunk",
                    "source_type": ch.get("source_type"),
                    "source_id": ch.get("source_id"),
                    "domain_key": ch.get("domain_key") or dk,
                    "label": (ch.get("title") or ch.get("source_id") or "")[:200],
                    "quote": (ch.get("chunk_text") or ch.get("text") or "")[:900],
                    "gap_id": "pre_compose_chunk",
                }
                if _attach_embedding_chunk_hit(
                    package_id, package, hit, actor=actor
                ):
                    chunk_attached += 1
                if chunk_attached >= chunk_limit:
                    break
        except Exception as e:
            logger.debug("pre-compose embedding promote failed: %s", e)

    rag_attached = 0
    try:
        rag_attached = _attach_completed_rag_pulls(
            package_id, package, actor=actor, limit=rag_limit
        )
    except Exception as e:
        logger.debug("pre-compose rag promote failed: %s", e)

    return {
        "ok": True,
        "chunk_attached": chunk_attached,
        "rag_pull_attached": rag_attached,
        "attached": chunk_attached + rag_attached,
    }


def _attach_completed_rag_pulls(
    package_id: int,
    package: dict[str, Any],
    *,
    actor: str = "evidence_expand",
    limit: int = 4,
) -> int:
    """Attach completed rag_evidence_pull → processed_documents as context members."""
    from shared.database.connection import get_db_connection_context

    domains = [str(d) for d in (package.get("domain_keys") or []) if d]
    attached = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT q.id, q.domain_key, q.pdf_url, q.selection_reason,
                           q.processed_document_id, pd.title, pd.source_url,
                           LEFT(
                             COALESCE(
                               pd.key_findings::text,
                               pd.extracted_sections::text,
                               pd.metadata->>'snippet',
                               pd.metadata->>'summary',
                               ''
                             ),
                             1200
                           )
                    FROM intelligence.rag_evidence_pull_queue q
                    LEFT JOIN intelligence.processed_documents pd
                      ON pd.id = q.processed_document_id
                    WHERE q.status = 'complete'
                      AND q.processed_document_id IS NOT NULL
                      AND (
                        %s::text[] IS NULL
                        OR cardinality(%s::text[]) = 0
                        OR q.domain_key = ANY(%s)
                      )
                      AND q.updated_at >= NOW() - INTERVAL '120 days'
                    ORDER BY q.updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (domains or None, domains or None, domains or None, limit * 3),
                )
                rows = cur.fetchall() or []
    except Exception as e:
        logger.debug("load completed rag pulls: %s", e)
        return 0

    for (
        qid,
        domain_key,
        pdf_url,
        reason,
        doc_id,
        doc_title,
        source_url,
        excerpt,
    ) in rows:
        del domain_key, doc_id  # used via join only
        # Theme on document title+excerpt only. Do not fold selection_reason into
        # the theme blob (e.g. "timeline_events" falsely mismatches), and never
        # prepend the package title (that made the gate always pass).
        excerpt_s = (excerpt or "").strip()
        if len(excerpt_s) < 40:
            continue
        blob = f"{doc_title or ''} {excerpt_s}"
        if not _theme_ok(package, blob):
            continue
        hit = {
            "title": (doc_title or f"RAG evidence #{qid}")[:240],
            "excerpt": excerpt_s[:1200],
            "url": source_url or pdf_url,
            "source": "rag_evidence_pull",
        }
        if _attach_external_hit(
            package_id,
            package,
            hit,
            actor=actor,
            gap_id=f"rag_pull:{qid}",
            skip_theme=True,
        ):
            attached += 1
        if attached >= limit:
            break
    return attached


def _attach_external_hit(
    package_id: int,
    package: dict[str, Any],
    hit: dict[str, Any],
    *,
    actor: str,
    gap_id: str | None,
    skip_theme: bool = False,
) -> dict[str, Any] | None:
    from services.editorial_package_service import add_member

    title = str(hit.get("title") or "")[:240]
    excerpt = str(hit.get("excerpt") or "")[:1200]
    url = hit.get("url")
    if not title and not excerpt:
        return None
    blob = f"{title} {excerpt}"
    if not skip_theme and not _theme_ok(package, blob):
        return None
    dk = (list(package.get("domain_keys") or []) or [None])[0]
    ctx_id = _upsert_external_context(
        title=title or "External evidence",
        content=excerpt,
        domain_key=str(dk) if dk else None,
        source_url=url,
        source_type=str(hit.get("source") or "external")[:64],
        metadata={"gap_id": gap_id, "evidence_expand": True},
    )
    if not ctx_id:
        return None
    try:
        return add_member(
            package_id,
            member_type="context",
            member_id=int(ctx_id),
            member_family="narrative",
            domain_key=dk,
            role="supporting",
            added_by_modal="narrative",
            added_by=actor,
            provenance={
                "label": title,
                "quote": excerpt[:900],
                "source_url": url,
                "evidence_expand": True,
                "gap_id": gap_id,
                "external_source": hit.get("source"),
            },
            metadata={"evidence_expand": True},
            actor=actor,
        )
    except Exception as e:
        logger.debug("attach external hit failed: %s", e)
        return None


def _sync_vault_note(
    package: dict[str, Any],
    brief: dict[str, Any],
) -> str | None:
    try:
        from services.vault_bridge_service import vault_root, vault_write_enabled
        from services.vault_bridge_service import _render_frontmatter  # type: ignore
    except Exception:
        return None
    if not vault_write_enabled():
        return brief.get("vault_rel_path")
    pid = int(package["id"])
    title = str(package.get("working_title") or f"package-{pid}")
    slug = _SLUG.sub("-", title.lower()).strip("-")[:50] or "pkg"
    rel = brief.get("vault_rel_path") or f"20_Investigations/pkg-{pid}-{slug}.md"
    try:
        root = vault_root()
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        gaps = brief.get("gap_ledger") or []
        fm = {
            "package_id": pid,
            "expand_round": brief.get("expand_round") or 0,
            "brief_status": brief.get("status"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "kind": "package_evidence_brief",
        }
        body_parts = [
            f"# {title}",
            "",
            "_Operator scratchpad — vault is not fact SSOT. Cite package members._",
            "",
            "## Gap checklist",
            "",
        ]
        for g in gaps:
            if isinstance(g, dict):
                st = g.get("status") or "open"
                body_parts.append(
                    f"- [{ 'x' if st == 'closed' else ' ' }] "
                    f"{g.get('id')}: {g.get('question')}"
                )
        body_parts.extend(["", "## Brief mirror", "", brief.get("brief_md") or "_empty_", ""])
        path.write_text(_render_frontmatter(fm) + "\n".join(body_parts), encoding="utf-8")
        # A4: register PG mirror so packages↔vault handoff is queryable (not binder).
        try:
            from services.vault_notes_registry_service import upsert_vault_note
            from shared.vault_note_contract import structural_tags_for_note

            domain_key = "global"
            dks = package.get("domain_keys") or []
            if isinstance(dks, list) and dks:
                domain_key = str(dks[0])
            tags = structural_tags_for_note(
                note_type="cluster",
                domain_key=domain_key,
                extra=["package_evidence_brief", f"package/{pid}"],
            )
            body = "\n".join(body_parts)
            upsert_vault_note(
                domain_key=domain_key,
                note_type="cluster",
                object_id=pid,
                vault_path=rel,
                title=title,
                note_status="note_ready",
                lifecycle="living",
                tags=tags,
                body_md=body[:12000],
                summary_md=(brief.get("lede") or "")[:320],
                metadata={
                    "package_id": pid,
                    "package_evidence_brief": True,
                    "expand_round": brief.get("expand_round") or 0,
                },
                tags_source="ni_structural",
            )
        except Exception as reg_e:
            logger.debug("vault_notes registry for package brief: %s", reg_e)
        return rel
    except Exception as e:
        logger.debug("vault note sync failed: %s", e)
        return brief.get("vault_rel_path")


def _fallback_brief_md(package: dict[str, Any]) -> str:
    members = [m for m in (package.get("members") or []) if m.get("status") == "active"]
    lines = [
        "## What We Know",
        "",
    ]
    for m in members[:12]:
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        label = prov.get("label") or m.get("display_label") or m.get("member_type")
        mid = m.get("id")
        quote = (prov.get("quote") or "")[:240]
        lines.append(f"- {label}: {quote} [@m{mid}]".strip())
    lines.extend(
        [
            "",
            "## Timeline",
            "",
        ]
    )
    for m in members:
        if m.get("member_type") != "chronological_event":
            continue
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        date = prov.get("event_date") or ""
        label = prov.get("label") or ""
        lines.append(f"- {date} — {label} [@m{m.get('id')}]".strip())
    lines.extend(
        [
            "",
            "## Supporting Evidence",
            "",
            "See cited members above.",
            "",
            "## Contested / Uncertain",
            "",
            "- Evidence still being expanded; treat unverified claims cautiously.",
            "",
            "## Open Questions",
            "",
        ]
    )
    for g in _deterministic_gaps(package):
        lines.append(f"- {g.get('question')}")
    return "\n".join(lines)


async def _llm_synthesize(
    package: dict[str, Any],
    gaps: list[dict[str, Any]],
    *,
    vault_background: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    members = [m for m in (package.get("members") or []) if m.get("status") == "active"]
    member_rows = []
    for m in members[:40]:
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        member_rows.append(
            {
                "member_row_id": m.get("id"),
                "member_type": m.get("member_type"),
                "label": prov.get("label") or m.get("display_label"),
                "quote": (prov.get("quote") or "")[:600],
                "parties": prov.get("parties"),
                "outcome": prov.get("outcome") or prov.get("holding"),
                "event_date": prov.get("event_date"),
                "url": prov.get("source_url") or prov.get("url"),
            }
        )
    payload: dict[str, Any] = {
        "package_id": package.get("id"),
        "working_title": package.get("working_title"),
        "summary_stub": package.get("summary_stub"),
        "gaps": gaps,
        "members": member_rows,
    }
    if vault_background and vault_background.get("note_n"):
        payload["vault_background"] = {
            "policy": "background_only_not_citeable",
            "note_n": vault_background.get("note_n"),
            "notes": vault_background.get("notes") or [],
            "evidence_text": (vault_background.get("evidence_text") or "")[:3500],
        }
    prompt = (
        _load_prompt()
        + "\n\nINPUT:\n```json\n"
        + json.dumps(payload, default=str)[:100_000]
        + "\n```\n"
    )
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STORYLINE_NARRATIVE_FINISH,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        parsed = _parse_json_obj(getattr(result, "text", None) or "")
        return parsed, getattr(result, "model", None)
    except Exception as e:
        logger.warning("evidence expand LLM failed package_id=%s: %s", package.get("id"), e)
        return None, None


def _build_citation_registry(package: dict[str, Any]) -> dict[str, Any]:
    reg: dict[str, Any] = {}
    for m in package.get("members") or []:
        if m.get("status") != "active":
            continue
        mid = int(m["id"])
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        reg[f"m{mid}"] = {
            "package_member_id": mid,
            "member_type": m.get("member_type"),
            "member_id": m.get("member_id"),
            "url": prov.get("source_url") or prov.get("url"),
            "quote": (prov.get("quote") or "")[:500] or None,
            "label": prov.get("label") or m.get("display_label"),
        }
    return reg


def run_expand_retrieval(
    package_id: int,
    *,
    actor: str = "evidence_expand",
    include_web: bool | None = None,
) -> dict[str, Any]:
    """DB + wiki (+ optional web) attach; vault notes as background (not members)."""
    from services.editorial_package_service import get_package
    from services.package_evidence_brief_service import get_or_create_brief

    pkg = get_package(package_id)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    brief = get_or_create_brief(package_id, actor=actor)
    gaps = list(brief.get("gap_ledger") or []) or _deterministic_gaps(pkg)
    do_web = web_expand_enabled() if include_web is None else bool(include_web)

    attached = 0
    attempted = 0
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        if gap.get("status") == "closed":
            continue
        gap_id = str(gap.get("id") or "gap")
        for hit in _retrieve_db_candidates(pkg, gap):
            attempted += 1
            hit["gap_id"] = gap_id
            if _attach_db_hit(package_id, pkg, hit, actor=actor):
                attached += 1
        for hit in _retrieve_wiki(gap, pkg):
            attempted += 1
            if _attach_external_hit(
                package_id, pkg, hit, actor=actor, gap_id=gap_id
            ):
                attached += 1
        if do_web:
            for hit in _retrieve_web(gap, pkg):
                attempted += 1
                if _attach_external_hit(
                    package_id, pkg, hit, actor=actor, gap_id=gap_id
                ):
                    attached += 1

    vault_background: dict[str, Any] = {}
    try:
        from services.package_vault_context_service import (
            retrieve_vault_context_for_package,
        )

        vault_background = retrieve_vault_context_for_package(
            pkg, limit=6, max_chars=3200
        )
    except Exception as e:
        logger.debug("vault background retrieve failed: %s", e)
        vault_background = {"ok": False, "error": str(e), "note_n": 0}

    rag_attached = 0
    try:
        rag_attached = _attach_completed_rag_pulls(
            package_id, pkg, actor=actor, limit=4
        )
        attached += rag_attached
    except Exception as e:
        logger.debug("attach completed rag pulls failed: %s", e)

    return {
        "ok": True,
        "package_id": package_id,
        "attached": attached,
        "attempted": attempted,
        "gaps": gaps,
        "vault_background": vault_background,
        "vault_hits": int(vault_background.get("note_n") or 0),
        "rag_pull_attached": rag_attached,
    }


async def run_evidence_expand_pass(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    include_web: bool | None = None,
) -> dict[str, Any]:
    from services.editorial_package_service import (
        get_package,
        update_package,
    )
    from services.modal_handoff_service import request_rework
    from services.package_evidence_brief_service import (
        compute_density,
        get_or_create_brief,
        update_brief,
    )

    if not is_enabled() and not force:
        return {
            "ok": False,
            "skipped": True,
            "reason": "EDITORIAL_EVIDENCE_EXPAND_ENABLED=false",
            "package_id": package_id,
        }

    pkg = get_package(package_id)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    brief = get_or_create_brief(package_id, actor="evidence_expand")
    prior_round = int(brief.get("expand_round") or 0)
    if prior_round >= max_rounds() and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "max_rounds",
            "package_id": package_id,
            "expand_round": prior_round,
        }

    gaps = list(brief.get("gap_ledger") or []) or _deterministic_gaps(pkg)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "package_id": package_id,
            "gaps": gaps,
            "expand_round": prior_round + 1,
        }

    retrieval = run_expand_retrieval(
        package_id, actor="evidence_expand", include_web=include_web
    )
    pkg = get_package(package_id) or pkg
    vault_bg = retrieval.get("vault_background") if isinstance(retrieval, dict) else None

    parsed, model = await _llm_synthesize(
        pkg, gaps, vault_background=vault_bg if isinstance(vault_bg, dict) else None
    )
    used_fallback = parsed is None
    if used_fallback:
        brief_md = _fallback_brief_md(pkg)
        lede = (pkg.get("summary_stub") or pkg.get("working_title") or "")[:400]
        open_q = [g.get("question") for g in gaps if isinstance(g, dict)]
        summary_stub = lede
        new_gaps = gaps
    else:
        assert parsed is not None
        brief_md = str(parsed.get("brief_md") or "").strip() or _fallback_brief_md(pkg)
        lede = str(parsed.get("lede") or "")[:600] or None
        open_q = list(parsed.get("open_questions") or [])[:20]
        summary_stub = str(parsed.get("summary_stub") or "")[:2000] or None
        raw_gaps = parsed.get("gaps") or gaps
        new_gaps = []
        for g in raw_gaps:
            if isinstance(g, dict):
                new_gaps.append(
                    {
                        "id": str(g.get("id") or "gap")[:64],
                        "question": str(g.get("question") or "")[:400],
                        "priority": int(g.get("priority") or 5),
                        "status": "open",
                    }
                )
            elif g:
                new_gaps.append(
                    {"id": "gap", "question": str(g)[:400], "priority": 5, "status": "open"}
                )

    # Mark gaps closed when we have rich parties/holding after attach.
    has_parties = any(
        isinstance(m.get("provenance"), dict) and m["provenance"].get("parties")
        for m in (pkg.get("members") or [])
        if m.get("status") == "active"
    )
    has_holding = any(
        isinstance(m.get("provenance"), dict)
        and (m["provenance"].get("holding") or m["provenance"].get("outcome"))
        for m in (pkg.get("members") or [])
        if m.get("status") == "active"
    )
    for g in new_gaps:
        if g.get("id") == "parties" and has_parties:
            g["status"] = "closed"
        if g.get("id") == "holding" and has_holding:
            g["status"] = "closed"

    reg = _build_citation_registry(pkg)
    density = compute_density(brief_md, reg)
    status = "ready" if density.get("passes_gate") else "expanding"
    round_n = prior_round + 1

    updated = update_brief(
        package_id,
        brief_md=brief_md,
        lede=lede,
        open_questions=open_q,
        citation_registry=reg,
        gap_ledger=new_gaps,
        status=status,
        expand_round=round_n,
        actor="evidence_expand",
        prompt_version=PROMPT_VERSION,
        metadata_patch={
            "model": model,
            "used_fallback": used_fallback,
            "retrieval": {
                "attached": retrieval.get("attached"),
                "attempted": retrieval.get("attempted"),
                "vault_hits": retrieval.get("vault_hits"),
                "vault_paths": [
                    n.get("vault_path")
                    for n in ((vault_bg or {}).get("notes") or [])
                    if isinstance(n, dict)
                ][:8],
            },
        },
    )
    vault_path = _sync_vault_note(pkg, updated or brief)
    if vault_path and (updated or {}).get("vault_rel_path") != vault_path:
        updated = update_brief(
            package_id,
            vault_rel_path=vault_path,
            actor="evidence_expand",
            write_revision=False,
        )

    if summary_stub:
        try:
            update_package(
                package_id,
                summary_stub=summary_stub,
                actor="evidence_expand",
                modal="narrative",
                rationale="evidence expand summary_stub pointer",
            )
        except Exception as e:
            logger.debug("update summary_stub after expand failed: %s", e)

    routed = None
    try:
        routed = request_rework(
            package_id,
            target_modal="reduction",
            note=f"post-evidence-expand round {round_n}",
            actor="evidence_expand",
            source_modal="narrative",
        )
    except Exception as e:
        logger.warning("evidence_expand→reduction route failed: %s", e)
        routed = {"error": str(e)}

    return {
        "ok": True,
        "package_id": package_id,
        "expand_round": round_n,
        "status": status,
        "density": density,
        "used_fallback": used_fallback,
        "model": model,
        "retrieval": retrieval,
        "vault_rel_path": vault_path,
        "route_target": "reduction",
        "routed": routed,
        "brief": updated,
    }


def run_evidence_expand_pass_sync(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    include_web: bool | None = None,
) -> dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    run_evidence_expand_pass(
                        package_id,
                        dry_run=dry_run,
                        force=force,
                        include_web=include_web,
                    )
                )
            ).result(timeout=300)
    return asyncio.run(
        run_evidence_expand_pass(
            package_id,
            dry_run=dry_run,
            force=force,
            include_web=include_web,
        )
    )


def list_evidence_expand_due(*, limit: int = 10) -> list[int]:
    """Narrative-domain packages with missing/incomplete evidence briefs."""
    lim = max(1, min(int(limit), 50))
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id
                FROM intelligence.editorial_packages p
                LEFT JOIN intelligence.package_evidence_briefs b
                  ON b.package_id = p.id
                WHERE p.primary_modal IN ('narrative', 'reduction')
                  AND p.status IN (
                    'in_narrative', 'in_reduction', 'ready_for_editor', 'draft'
                  )
                  AND (
                    b.id IS NULL
                    OR b.status IN ('draft', 'expanding', 'stale')
                    OR coalesce(b.expand_round, 0) < %s
                  )
                  AND p.domain_keys && ARRAY['politics','finance','legal']::text[]
                ORDER BY p.updated_at ASC, p.id ASC
                LIMIT %s
                """,
                (max_rounds(), lim),
            )
            return [int(r[0]) for r in cur.fetchall()]


def run_evidence_expand_batch(*, limit: int | None = None) -> dict[str, Any]:
    """Drain Narrative-domain packages needing expand."""
    if not is_enabled():
        return {"skipped": True, "reason": "disabled", "processed": 0}

    lim = max(1, int(limit or env_int("EVIDENCE_EXPAND_BATCH_LIMIT", 3)))
    ids = list_evidence_expand_due(limit=lim)

    processed = 0
    results = []
    for pid in ids:
        try:
            # Prefer sync path via new event loop when called from thread.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        r = pool.submit(
                            lambda: asyncio.run(
                                run_evidence_expand_pass(pid, include_web=True)
                            )
                        ).result(timeout=300)
                else:
                    r = loop.run_until_complete(
                        run_evidence_expand_pass(pid, include_web=True)
                    )
            except RuntimeError:
                r = asyncio.run(run_evidence_expand_pass(pid, include_web=True))
            results.append(r)
            if r.get("ok") and not r.get("skipped"):
                processed += 1
        except Exception as e:
            logger.warning("evidence expand batch item failed id=%s: %s", pid, e)
            results.append({"ok": False, "package_id": pid, "error": str(e)})

    return {
        "processed": processed,
        "attempted": len(ids),
        "results": results,
        "routed_to_reduction": sum(
            1 for r in results if r.get("route_target") == "reduction"
        ),
    }


def merge_research_findings_into_brief(
    package_id: int,
    *,
    actor: str = "research_parity",
) -> dict[str, Any]:
    """Research parity: dump literature package members into the shared brief table."""
    from services.editorial_package_service import get_package
    from services.package_evidence_brief_service import update_brief

    pkg = get_package(package_id)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    brief_md = _fallback_brief_md(pkg)
    # Prefer research-oriented section labels while keeping required headings.
    if "## What We Know" in brief_md:
        brief_md = (
            brief_md.replace(
                "## Supporting Evidence",
                "## Supporting Evidence\n\n_Literature / claim appraisal members._",
                1,
            )
        )
    reg = _build_citation_registry(pkg)
    gaps = _deterministic_gaps(pkg)
    open_q = [
        str(g)
        for g in (pkg.get("metadata") or {}).get("last_research_gaps") or []
        if g
    ][:20]
    if not open_q:
        open_q = [g.get("question") for g in gaps]

    updated = update_brief(
        package_id,
        brief_md=brief_md,
        lede=(pkg.get("summary_stub") or pkg.get("working_title") or "")[:400],
        open_questions=open_q,
        citation_registry=reg,
        gap_ledger=gaps,
        status="expanding",
        actor=actor,
        prompt_version="research_parity.v1",
        metadata_patch={"source": "editorial_research_pass"},
    )
    vault_path = _sync_vault_note(pkg, updated)
    if vault_path:
        updated = update_brief(
            package_id,
            vault_rel_path=vault_path,
            actor=actor,
            write_revision=False,
        )
    return {"ok": True, "package_id": package_id, "brief": updated}
