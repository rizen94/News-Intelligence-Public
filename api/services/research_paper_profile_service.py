"""
Extract research axes for scientific papers into intelligence.research_paper_profiles.

Domain-agnostic: universal axes + domain_facets jsonb filled per domain_key.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection, get_db_connection_context
from shared.domain_registry import domain_key_to_schema, pipeline_url_schema_pairs
from shared.llm_text_sanitize import parse_llm_json_response

from services.research_paper_classifier import (
    CONTENT_KIND_RESEARCH_PAPER,
    classify_research_paper,
    is_research_paper_metadata,
    paper_metadata_patch,
)

logger = logging.getLogger(__name__)

_MAX_BODY_CHARS = int(os.environ.get("RESEARCH_PAPER_PROFILE_MAX_CHARS", "24000"))
_BATCH_LIMIT = int(os.environ.get("RESEARCH_PAPER_PROFILE_BATCH_LIMIT", "8"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pending_profile_count() -> int:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT count(*)::bigint
                    FROM intelligence.research_paper_profiles
                    WHERE extraction_status IN ('pending', 'failed')
                    """
                )
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def effective_profile_batch_limit(requested: int | None = None) -> int:
    """Steady trickle when backlog is large — avoid burst-8 that trips Ollama.

    Env:
      RESEARCH_PAPER_PROFILE_BATCH_LIMIT (default 8)
      RESEARCH_PAPER_PROFILE_BACKLOG_TRICKLE_THRESHOLD (default 500)
      RESEARCH_PAPER_PROFILE_TRICKLE_BATCH (default 2)
    """
    base = max(1, int(requested if requested is not None else _BATCH_LIMIT))
    try:
        thr = int(os.environ.get("RESEARCH_PAPER_PROFILE_BACKLOG_TRICKLE_THRESHOLD", "500"))
    except ValueError:
        thr = 500
    if thr <= 0:
        return base
    try:
        trickle = int(os.environ.get("RESEARCH_PAPER_PROFILE_TRICKLE_BATCH", "2"))
    except ValueError:
        trickle = 2
    trickle = max(1, trickle)
    pending = _pending_profile_count()
    if pending >= thr:
        lim = min(base, trickle)
        if lim < base:
            logger.info(
                "research profile trickle batch=%s (pending=%s threshold=%s base=%s)",
                lim,
                pending,
                thr,
                base,
            )
        return lim
    return base


def _facet_schema_for_domain(domain_key: str) -> str:
    dk = (domain_key or "").lower().replace("_", "-")
    if dk.startswith("artificial-intelligence") or dk in ("ai",):
        return (
            '{"models":[{"name":"string","class":"llm|frontier|local|other"}],'
            '"deployment_class":"frontier|local|both|unclear",'
            '"tasks":["string"],"benchmarks":["string"]}'
        )
    if dk.startswith("medicine") or dk.startswith("health"):
        return (
            '{"study_type":"string","population":"string","intervention":"string",'
            '"outcomes":["string"]}'
        )
    if dk.startswith("finance"):
        return '{"markets":["string"],"instruments":["string"],"methods":["string"]}'
    return '{"topics":["string"],"methods":["string"],"artifacts":["string"]}'


def _build_prompt(domain_key: str, title: str, body: str) -> str:
    facets = _facet_schema_for_domain(domain_key)
    return f"""You analyze scientific research papers for a news intelligence system.
Extract structured research axes (NOT news entities or events).

Domain: {domain_key}
Title: {title[:500]}

Paper text (may be truncated):
{body[:_MAX_BODY_CHARS]}

Reply with ONLY JSON:
{{
  "research_question": "what question or gap this paper addresses",
  "methods_summary": "approach / methods in 1-3 sentences",
  "findings_summary": "key results in 1-3 sentences",
  "implications": "who/what is affected; implications for other work, models, practice, or policy",
  "subjects_studied": ["named models, organisms, datasets, systems, or artifacts studied"],
  "domain_facets": {facets}
}}
Be concrete. If unknown, use empty string or empty arrays. Do not invent citations.
"""


def ensure_pending_profile(
    domain_key: str,
    article_id: int,
    *,
    url: str | None = None,
    title: str | None = None,
    source_domain: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Insert pending profile row if this article is a research paper. Returns True if pending/ensured."""
    frag = classify_research_paper(
        url, source_domain=source_domain, title=title, metadata=metadata
    )
    if not frag and not is_research_paper_metadata(metadata or {}):
        return False
    frag = frag or {"content_kind": CONTENT_KIND_RESEARCH_PAPER}
    arxiv_id = frag.get("arxiv_id")
    preprint_id = frag.get("preprint_id")
    doi = frag.get("doi")
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.research_paper_profiles
                    (domain_key, article_id, preprint_id, doi, arxiv_id, extraction_status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (domain_key, article_id) DO NOTHING
                    """,
                    (domain_key, article_id, preprint_id, doi, arxiv_id),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.debug("ensure_pending_profile %s/%s: %s", domain_key, article_id, e)
        return False


def stamp_article_research_metadata(
    schema: str,
    article_id: int,
    url: str | None,
    *,
    title: str | None = None,
    source_domain: str | None = None,
) -> dict[str, Any]:
    """Merge paper metadata onto article row; return patch applied (may be empty)."""
    patch = paper_metadata_patch(url, source_domain=source_domain, title=title)
    if not patch:
        return {}
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {schema}.articles
                    SET metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(patch), article_id),
                )
            conn.commit()
    except Exception as e:
        logger.debug("stamp_article_research_metadata %s/%s: %s", schema, article_id, e)
    return patch


def _parse_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except Exception:
            return {}
    return {}


async def extract_profile_for_article(domain_key: str, article_id: int) -> dict[str, Any]:
    """LLM-extract axes and upsert profile. Returns status dict."""
    schema = domain_key_to_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, url, content, source_domain, metadata
                FROM {schema}.articles WHERE id = %s
                """,
                (article_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "article_not_found"}
            title, url, content, source_domain, metadata = row
            meta = _parse_metadata(metadata)
            if not is_research_paper_metadata(meta):
                patch = paper_metadata_patch(
                    url, source_domain=source_domain, title=title, existing_metadata=meta
                )
                if not patch:
                    cur.execute(
                        """
                        UPDATE intelligence.research_paper_profiles
                        SET extraction_status = 'skipped', updated_at = NOW(),
                            extraction_error = 'not_a_research_paper'
                        WHERE domain_key = %s AND article_id = %s
                        """,
                        (domain_key, article_id),
                    )
                    conn.commit()
                    return {"ok": False, "error": "not_a_research_paper"}
                cur.execute(
                    f"""
                    UPDATE {schema}.articles
                    SET metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb
                    WHERE id = %s
                    """,
                    (json.dumps(patch), article_id),
                )
                meta.update(patch)

            cur.execute(
                """
                UPDATE intelligence.research_paper_profiles
                SET extraction_status = 'processing', updated_at = NOW()
                WHERE domain_key = %s AND article_id = %s
                """,
                (domain_key, article_id),
            )
        conn.commit()

    body = (content or "").strip()
    if len(body) < 200:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.research_paper_profiles
                    SET extraction_status = 'failed', extraction_error = 'content_too_short',
                        updated_at = NOW()
                    WHERE domain_key = %s AND article_id = %s
                    """,
                    (domain_key, article_id),
                )
            conn.commit()
        return {"ok": False, "error": "content_too_short"}

    prompt = _build_prompt(domain_key, title or "", body)
    raw_text = ""
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        gen = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            approx_prompt_chars=len(prompt),
        )
        raw_text = gen.text or ""
    except Exception as e:
        logger.warning("research profile LLM failed %s/%s: %s", domain_key, article_id, e)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.research_paper_profiles
                    SET extraction_status = 'failed', extraction_error = %s, updated_at = NOW()
                    WHERE domain_key = %s AND article_id = %s
                    """,
                    (str(e)[:500], domain_key, article_id),
                )
            conn.commit()
        return {"ok": False, "error": str(e)}

    parsed, err = parse_llm_json_response(raw_text)
    if not parsed:
        m = re.search(r"\{[\s\S]*\}", raw_text or "")
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = None
    if not isinstance(parsed, dict):
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.research_paper_profiles
                    SET extraction_status = 'failed',
                        extraction_error = %s,
                        raw_extraction = %s::jsonb,
                        updated_at = NOW()
                    WHERE domain_key = %s AND article_id = %s
                    """,
                    (
                        (err or "json_parse_failed")[:500],
                        json.dumps({"raw": (raw_text or "")[:8000]}),
                        domain_key,
                        article_id,
                    ),
                )
            conn.commit()
        return {"ok": False, "error": "json_parse_failed"}

    subjects = parsed.get("subjects_studied") or []
    if not isinstance(subjects, list):
        subjects = [str(subjects)]
    facets = parsed.get("domain_facets") if isinstance(parsed.get("domain_facets"), dict) else {}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.research_paper_profiles
                SET research_question = %s,
                    methods_summary = %s,
                    findings_summary = %s,
                    implications = %s,
                    subjects_studied = %s::jsonb,
                    domain_facets = %s::jsonb,
                    raw_extraction = %s::jsonb,
                    extraction_status = 'done',
                    extraction_error = NULL,
                    extracted_at = NOW(),
                    preprint_id = COALESCE(preprint_id, %s),
                    doi = COALESCE(doi, %s),
                    arxiv_id = COALESCE(arxiv_id, %s),
                    updated_at = NOW()
                WHERE domain_key = %s AND article_id = %s
                """,
                (
                    (parsed.get("research_question") or "")[:4000] or None,
                    (parsed.get("methods_summary") or "")[:4000] or None,
                    (parsed.get("findings_summary") or "")[:4000] or None,
                    (parsed.get("implications") or "")[:4000] or None,
                    json.dumps([str(s)[:200] for s in subjects[:40]]),
                    json.dumps(facets),
                    json.dumps(parsed),
                    meta.get("preprint_id"),
                    meta.get("doi"),
                    meta.get("arxiv_id"),
                    domain_key,
                    article_id,
                ),
            )
        conn.commit()

    # Bridge into literature processed_documents so claim_evidence_appraisal can drain.
    try:
        from services.research_literature_bridge_service import bridge_after_profile

        bridge_after_profile(
            domain_key,
            article_id,
            profile_axes={
                "research_question": (parsed.get("research_question") or "")[:4000] or None,
                "methods_summary": (parsed.get("methods_summary") or "")[:4000] or None,
                "findings_summary": (parsed.get("findings_summary") or "")[:4000] or None,
                "implications": (parsed.get("implications") or "")[:4000] or None,
                "subjects_studied": [str(s)[:200] for s in subjects[:40]],
                "doi": meta.get("doi"),
                "arxiv_id": meta.get("arxiv_id"),
                "preprint_id": meta.get("preprint_id"),
            },
        )
    except Exception as bridge_err:
        logger.debug(
            "literature bridge after profile %s/%s: %s",
            domain_key,
            article_id,
            bridge_err,
        )

    return {"ok": True, "domain_key": domain_key, "article_id": article_id}


async def drain_research_paper_profiling(limit: int | None = None) -> dict[str, Any]:
    """Process pending/failed profile rows across domains."""
    lim = effective_profile_batch_limit(limit)
    done = fail = 0
    deferred_overload = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, article_id
                FROM intelligence.research_paper_profiles
                WHERE extraction_status IN ('pending', 'failed')
                ORDER BY updated_at ASC NULLS FIRST
                LIMIT %s
                """,
                (lim,),
            )
            rows = cur.fetchall()
    for domain_key, article_id in rows:
        try:
            res = await extract_profile_for_article(domain_key, int(article_id))
            if res.get("ok"):
                done += 1
            else:
                fail += 1
                err = str(res.get("error") or "").lower()
                if "timed out" in err or "overloaded" in err:
                    deferred_overload += 1
                    # Stop this batch early — leave remaining pending for next trickle.
                    break
        except Exception as e:
            msg = str(e).lower()
            if "timed out" in msg or "overloaded" in msg or "circuit breaker is open" in msg:
                deferred_overload += 1
                logger.info(
                    "profile drain pausing batch on overload/shed %s/%s: %s",
                    domain_key,
                    article_id,
                    e,
                )
                break
            fail += 1
            logger.warning("profile drain %s/%s: %s", domain_key, article_id, e)
    return {
        "processed": done + fail,
        "ok": done,
        "failed": fail,
        "limit": lim,
        "deferred_overload": deferred_overload,
    }


def enqueue_profiles_for_tagged_articles(limit_per_domain: int = 200) -> int:
    """Create pending profile rows for articles already tagged content_kind=research_paper."""
    n = 0
    for domain_key, schema in pipeline_url_schema_pairs():
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT a.id, a.url, a.title, a.source_domain, a.metadata
                        FROM {schema}.articles a
                        WHERE COALESCE(a.metadata->>'content_kind', '') = %s
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.research_paper_profiles p
                              WHERE p.domain_key = %s AND p.article_id = a.id
                          )
                        ORDER BY a.created_at DESC
                        LIMIT %s
                        """,
                        (CONTENT_KIND_RESEARCH_PAPER, domain_key, limit_per_domain),
                    )
                    for aid, url, title, source_domain, metadata in cur.fetchall():
                        meta = _parse_metadata(metadata)
                        if ensure_pending_profile(
                            domain_key,
                            int(aid),
                            url=url,
                            title=title,
                            source_domain=source_domain,
                            metadata=meta,
                        ):
                            n += 1
        except Exception as e:
            logger.debug("enqueue_profiles %s: %s", domain_key, e)
    return n


def backfill_stamp_research_papers(limit_per_domain: int = 5000) -> dict[str, int]:
    """Stamp metadata on preprint URLs and ensure pending profiles.

    Uses one connection per domain (no nested pool checkouts) so large
    stamps do not stall under pool pressure.
    """
    stamped = 0
    profiles = 0
    for domain_key, schema in pipeline_url_schema_pairs():
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, url, title, source_domain, metadata
                        FROM {schema}.articles
                        WHERE (
                               url ILIKE '%%arxiv.org/%%'
                            OR url ILIKE '%%biorxiv.org/%%'
                            OR url ILIKE '%%medrxiv.org/%%'
                            OR url ILIKE '%%chemrxiv.org/%%'
                            OR url ILIKE '%%pubmed.ncbi.nlm.nih.gov/%%'
                            OR COALESCE(metadata->>'content_kind','') = %s
                        )
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.research_paper_profiles p
                              WHERE p.domain_key = %s AND p.article_id = {schema}.articles.id
                          )
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (CONTENT_KIND_RESEARCH_PAPER, domain_key, limit_per_domain),
                    )
                    rows = cur.fetchall()
                    for aid, url, title, source_domain, metadata in rows:
                        meta = _parse_metadata(metadata)
                        patch = paper_metadata_patch(
                            url,
                            source_domain=source_domain,
                            title=title,
                            existing_metadata=meta,
                        )
                        if not patch and not is_research_paper_metadata(meta):
                            continue
                        if patch:
                            cur.execute(
                                f"""
                                UPDATE {schema}.articles
                                SET metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (json.dumps(patch), aid),
                            )
                            stamped += 1
                            meta.update(patch)
                        frag = classify_research_paper(
                            url,
                            source_domain=source_domain,
                            title=title,
                            metadata=meta,
                        ) or {"content_kind": CONTENT_KIND_RESEARCH_PAPER}
                        cur.execute(
                            """
                            INSERT INTO intelligence.research_paper_profiles
                            (domain_key, article_id, preprint_id, doi, arxiv_id, extraction_status)
                            VALUES (%s, %s, %s, %s, %s, 'pending')
                            ON CONFLICT (domain_key, article_id) DO NOTHING
                            """,
                            (
                                domain_key,
                                int(aid),
                                frag.get("preprint_id"),
                                frag.get("doi"),
                                frag.get("arxiv_id"),
                            ),
                        )
                        if cur.rowcount:
                            profiles += 1
                conn.commit()
        except Exception as e:
            logger.warning("backfill_stamp %s: %s", domain_key, e)
    return {"stamped": stamped, "profiles_ensured": profiles}
