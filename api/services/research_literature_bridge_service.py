"""
Bridge profiled research papers → intelligence.processed_documents (literature).

Appraisal drains literature-stamped processed_documents. Profiling alone never
created those rows — this upsert closes that gap so claim_evidence_appraisal
can run on the research corpus.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import domain_key_to_schema, resolve_domain_schema

logger = logging.getLogger(__name__)

RESEARCH_BRIDGE_DOMAINS = frozenset(
    {"medicine", "neurodiversity", "artificial-intelligence"}
)

_SOURCE_TYPE = "literature"


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except Exception:
            return {}
    return {}


def _pub_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _sections_from_article_and_profile(
    *,
    content: str | None,
    title: str | None,
    profile: dict[str, Any] | None,
) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    body = (content or "").strip()
    if body:
        sections.append({"heading": "Full text", "content": body[:100_000]})
    if profile:
        for heading, key in (
            ("Research question", "research_question"),
            ("Methods", "methods_summary"),
            ("Findings", "findings_summary"),
            ("Implications", "implications"),
        ):
            val = (profile.get(key) or "").strip()
            if val:
                sections.append({"heading": heading, "content": val[:8000]})
        subjects = profile.get("subjects_studied")
        if isinstance(subjects, list) and subjects:
            sections.append(
                {
                    "heading": "Subjects studied",
                    "content": ", ".join(str(s)[:200] for s in subjects[:40]),
                }
            )
    if not sections and title:
        sections.append({"heading": "Title", "content": str(title)[:2000]})
    return sections


def find_literature_document_id(*, domain_key: str, article_id: int) -> int | None:
    """Return existing processed_documents id for this domain article, if any."""
    dk = (domain_key or "").strip()
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM intelligence.processed_documents
                    WHERE source_type = %s
                      AND COALESCE(metadata->>'domain_key', '') = %s
                      AND (metadata->>'article_id')::bigint = %s
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (_SOURCE_TYPE, dk, int(article_id)),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as e:
        logger.debug("find_literature_document_id failed: %s", e)
        return None


def upsert_literature_document_from_paper(
    domain_key: str,
    article_id: int,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Idempotent upsert of a literature processed_documents row for a profiled paper.

    Returns ``{ok, document_id, created|updated, skipped?}``.
    """
    dk = (domain_key or "").strip()
    if dk not in RESEARCH_BRIDGE_DOMAINS:
        return {"ok": False, "skipped": True, "reason": "domain_not_research"}

    try:
        schema = domain_key_to_schema(dk)
    except Exception:
        schema = resolve_domain_schema(dk)

    aid = int(article_id)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, url, content, published_at, source_domain, metadata
                    FROM {schema}.articles
                    WHERE id = %s
                    """,
                    (aid,),
                )
                art = cur.fetchone()
                if not art:
                    return {"ok": False, "error": "article_not_found"}

                _art_id, title, url, content, published_at, source_domain, art_meta = art
                art_meta = _parse_meta(art_meta)

                prof = profile
                if prof is None:
                    cur.execute(
                        """
                        SELECT research_question, methods_summary, findings_summary,
                               implications, subjects_studied, domain_facets,
                               extraction_status, doi, arxiv_id, preprint_id
                        FROM intelligence.research_paper_profiles
                        WHERE domain_key = %s AND article_id = %s
                        """,
                        (dk, aid),
                    )
                    prow = cur.fetchone()
                    if prow:
                        cols = [d[0] for d in cur.description]
                        prof = dict(zip(cols, prow))
                    if not prof or (prof.get("extraction_status") or "") != "done":
                        return {
                            "ok": False,
                            "skipped": True,
                            "reason": "profile_not_done",
                        }

                sections = _sections_from_article_and_profile(
                    content=content, title=title, profile=prof
                )
                if not sections:
                    return {"ok": False, "skipped": True, "reason": "no_text"}

                source_url = (url or "").strip() or f"ni://{dk}/articles/{aid}"
                meta = {
                    "literature": "true",
                    "domain_key": dk,
                    "article_id": aid,
                    "bridge": "research_literature_bridge",
                    "source_domain": source_domain,
                    "doi": (prof or {}).get("doi") or art_meta.get("doi"),
                    "arxiv_id": (prof or {}).get("arxiv_id") or art_meta.get("arxiv_id"),
                    "preprint_id": (prof or {}).get("preprint_id")
                    or art_meta.get("preprint_id"),
                    "subjects_studied": (prof or {}).get("subjects_studied") or [],
                }
                pub = _pub_date(published_at)
                abstract_only = not bool((content or "").strip()) or len((content or "").strip()) < 2000
                meta["abstract_only"] = abstract_only

                cur.execute(
                    """
                    SELECT id FROM intelligence.processed_documents
                    WHERE source_type = %s
                      AND COALESCE(metadata->>'domain_key', '') = %s
                      AND (metadata->>'article_id')::bigint = %s
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (_SOURCE_TYPE, dk, aid),
                )
                existing = cur.fetchone()
                if existing:
                    doc_id = int(existing[0])
                    cur.execute(
                        """
                        UPDATE intelligence.processed_documents
                        SET title = %s,
                            source_url = %s,
                            source_name = COALESCE(%s, source_name),
                            publication_date = COALESCE(%s, publication_date),
                            document_type = 'research_paper',
                            extracted_sections = %s::jsonb,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                            extraction_method = 'research_literature_bridge',
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            (title or "")[:2000] or None,
                            source_url,
                            source_domain,
                            pub,
                            json.dumps(sections),
                            json.dumps(meta),
                            doc_id,
                        ),
                    )
                    conn.commit()
                    return {"ok": True, "document_id": doc_id, "updated": True}

                cur.execute(
                    """
                    INSERT INTO intelligence.processed_documents (
                        source_type, source_name, source_url, title, publication_date,
                        document_type, extracted_sections, metadata, extraction_method
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        'research_paper', %s::jsonb, %s::jsonb, 'research_literature_bridge'
                    )
                    RETURNING id
                    """,
                    (
                        _SOURCE_TYPE,
                        source_domain,
                        source_url,
                        (title or "")[:2000] or None,
                        pub,
                        json.dumps(sections),
                        json.dumps(meta),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return {
                    "ok": True,
                    "document_id": int(row[0]),
                    "created": True,
                }
    except Exception as e:
        logger.warning(
            "upsert_literature_document_from_paper %s/%s failed: %s", dk, aid, e
        )
        return {"ok": False, "error": str(e)[:500]}


def bridge_after_profile(
    domain_key: str,
    article_id: int,
    *,
    profile_axes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call after a successful profile write. Best-effort; never raises."""
    try:
        prof = None
        if profile_axes:
            prof = {
                **profile_axes,
                "extraction_status": "done",
            }
        return upsert_literature_document_from_paper(
            domain_key, article_id, profile=prof
        )
    except Exception as e:
        logger.debug("bridge_after_profile: %s", e)
        return {"ok": False, "error": str(e)[:300]}


def backfill_literature_docs_from_profiles(
    *,
    limit: int = 100,
    domain_key: str | None = None,
) -> dict[str, Any]:
    """
    Create/update literature docs for done profiles that lack a bridged document.

    Prefer neurodiversity → artificial-intelligence → medicine when domain unset.
    """
    lim = max(1, min(int(limit), 2000))
    domains: list[str]
    if domain_key:
        domains = [domain_key.strip()]
    else:
        domains = ["neurodiversity", "artificial-intelligence", "medicine"]

    created = updated = skipped = errors = 0
    for dk in domains:
        if dk not in RESEARCH_BRIDGE_DOMAINS:
            continue
        remaining = lim - (created + updated + skipped + errors)
        if remaining <= 0:
            break
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT p.domain_key, p.article_id
                        FROM intelligence.research_paper_profiles p
                        WHERE p.domain_key = %s
                          AND p.extraction_status = 'done'
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.processed_documents pd
                              WHERE pd.source_type = %s
                                AND COALESCE(pd.metadata->>'domain_key', '') = p.domain_key
                                AND (pd.metadata->>'article_id')::bigint = p.article_id
                          )
                        ORDER BY p.extracted_at DESC NULLS LAST, p.id DESC
                        LIMIT %s
                        """,
                        (dk, _SOURCE_TYPE, remaining),
                    )
                    rows = cur.fetchall() or []
        except Exception as e:
            logger.warning("backfill load %s failed: %s", dk, e)
            errors += 1
            continue

        for row_dk, aid in rows:
            res = upsert_literature_document_from_paper(str(row_dk), int(aid))
            if res.get("created"):
                created += 1
            elif res.get("updated"):
                updated += 1
            elif res.get("skipped") or not res.get("ok"):
                if res.get("ok") is False and res.get("error"):
                    errors += 1
                else:
                    skipped += 1
            else:
                skipped += 1

    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "limit": lim,
        "domains": domains,
    }
