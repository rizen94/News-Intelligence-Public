"""
Claim evidence appraisal service (v11 corpus scaffolding).

Loads literature documents lacking appraisal, calls Ollama structured extraction,
validates with shared.evidence_grade.assert_valid_appraisal_payload, inserts rows.

Gated by CLAIM_EVIDENCE_APPRAISAL_ENABLED (default false).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_int, env_str
from shared.database.connection import get_db_connection_context
from shared.domain_processing_mode import corpus_domain_keys, is_corpus_domain
from shared.domain_registry import resolve_domain_schema
from shared.evidence_grade import assert_valid_appraisal_payload

logger = logging.getLogger(__name__)

PROMPT_VERSION = "evidence_appraisal.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "prompts" / "research" / "evidence_appraisal.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def is_enabled() -> bool:
    return env_bool("CLAIM_EVIDENCE_APPRAISAL_ENABLED", False)


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("evidence appraisal prompt missing: %s", e)
        return (
            "Appraise this research text. Return JSON with finding_text, study_design, "
            "peer_review_status, paper_support, replication_status, evidence_grade, "
            "evidence_quotes. Never invent quotes; if none → paper_support=insufficient_reporting."
        )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # Find outermost braces
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _doc_text_from_row(row: dict[str, Any]) -> tuple[str, bool]:
    """Return (text, abstract_only) from processed_documents row."""
    sections = row.get("extracted_sections") or []
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    abstract_only = bool(meta.get("abstract_only", True))
    bits: list[str] = []
    if isinstance(sections, list):
        for sec in sections:
            if isinstance(sec, dict):
                heading = str(sec.get("heading") or "")
                content = str(sec.get("content") or sec.get("text") or "")
                if content.strip():
                    bits.append(f"## {heading}\n{content}" if heading else content)
                    if heading.lower() not in ("abstract",) and len(content) > 2000:
                        abstract_only = False
            elif isinstance(sec, str) and sec.strip():
                bits.append(sec)
    text = "\n\n".join(bits).strip()
    if not text and row.get("title"):
        text = str(row["title"])
    return text[:120_000], abstract_only


def count_claim_evidence_appraisal_due(*, domain_key: str | None = None) -> int:
    """
    SSOT counter: processed_documents (literature / corpus domains) lacking an
    appraisal row. Optional domain_key filter.
    """
    domains = [domain_key] if domain_key else corpus_domain_keys()
    if domain_key and not domains:
        domains = [domain_key]
    # If no corpus domains registered yet, still allow explicit domain_key;
    # otherwise count docs tagged with literature metadata or known source types.
    total = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                if domains:
                    for dk in domains:
                        if domain_key is None and not is_corpus_domain(dk):
                            continue
                        cur.execute(
                            """
                            SELECT COUNT(*) FROM intelligence.processed_documents pd
                            WHERE NOT EXISTS (
                                SELECT 1 FROM intelligence.claim_evidence_appraisal a
                                WHERE a.document_id = pd.id
                                  AND a.domain_key = %s
                            )
                            AND (
                                COALESCE(pd.metadata->>'domain_key', '') = %s
                                OR pd.source_type IN ('europepmc', 'pubmed', 'literature')
                            )
                            """,
                            (dk, dk),
                        )
                        row = cur.fetchone()
                        total += int(row[0] or 0) if row else 0
                else:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM intelligence.processed_documents pd
                        WHERE NOT EXISTS (
                            SELECT 1 FROM intelligence.claim_evidence_appraisal a
                            WHERE a.document_id = pd.id
                        )
                        AND (
                            COALESCE(pd.metadata->>'literature', '') IN ('true', '1')
                            OR pd.source_type IN ('europepmc', 'pubmed', 'literature')
                        )
                        """
                    )
                    row = cur.fetchone()
                    total = int(row[0] or 0) if row else 0
    except Exception as e:
        logger.debug("count_claim_evidence_appraisal_due failed: %s", e)
        return 0
    return total


def _load_due_documents(
    *,
    domain_key: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    limit = max(1, min(100, limit))
    dk = (domain_key or "").strip() or None
    sql = """
        SELECT pd.id, pd.title, pd.source_url, pd.source_type, pd.extracted_sections,
               pd.metadata, pd.publication_date, pd.citations
        FROM intelligence.processed_documents pd
        WHERE NOT EXISTS (
            SELECT 1 FROM intelligence.claim_evidence_appraisal a
            WHERE a.document_id = pd.id
              AND (%s::text IS NULL OR a.domain_key = %s)
        )
        AND (
            COALESCE(pd.metadata->>'literature', '') IN ('true', '1')
            OR pd.source_type IN ('europepmc', 'pubmed', 'literature')
            OR (%s::text IS NOT NULL AND COALESCE(pd.metadata->>'domain_key', '') = %s)
        )
        ORDER BY pd.id ASC
        LIMIT %s
    """
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (dk, dk, dk, dk, limit))
                cols = [d[0] for d in cur.description or []]
                for row in cur.fetchall() or []:
                    item = dict(zip(cols, row))
                    # psycopg2 may return dict-like already via RealDict — handle tuple
                    out.append(item)
    except Exception as e:
        logger.warning("load due appraisal docs failed: %s", e)
    return out


def _resolve_row_domain(row: dict[str, Any], fallback: str | None) -> str:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    dk = str(meta.get("domain_key") or fallback or "neurodiversity").strip()
    return dk or "neurodiversity"


async def _appraise_document(row: dict[str, Any], *, domain_key: str) -> dict[str, Any] | None:
    """
    Call Ollama (when available) and return validated appraisal payload.
    Returns None on hard failure.
    """
    text, abstract_only = _doc_text_from_row(row)
    if not text.strip():
        return assert_valid_appraisal_payload(
            {
                "finding_text": None,
                "paper_support": "insufficient_reporting",
                "evidence_quotes": [],
                "abstract_only": True,
                "study_design": (row.get("metadata") or {}).get("study_design")
                if isinstance(row.get("metadata"), dict)
                else "unknown",
            }
        )

    prompt = (
        f"{_load_prompt()}\n\n"
        f"## Document\n"
        f"Title: {row.get('title') or ''}\n"
        f"URL: {row.get('source_url') or ''}\n"
        f"Domain: {domain_key}\n"
        f"Abstract-only hint: {abstract_only}\n\n"
        f"### Text\n{text}\n"
    )

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
        parsed = _parse_json_object(result.text)
        if not parsed:
            logger.info(
                "appraisal JSON parse miss document_id=%s model=%s",
                row.get("id"),
                result.model,
            )
            parsed = {
                "paper_support": "insufficient_reporting",
                "evidence_quotes": [],
                "finding_text": None,
            }
        parsed.setdefault("abstract_only", abstract_only)
        validated = assert_valid_appraisal_payload(parsed)
        validated["_grader_model"] = result.model
        return validated
    except Exception as e:
        logger.warning("appraisal LLM failed document_id=%s: %s", row.get("id"), e)
        # Deterministic refusal fallback (no invented quotes)
        return assert_valid_appraisal_payload(
            {
                "finding_text": None,
                "paper_support": "insufficient_reporting",
                "evidence_quotes": [],
                "abstract_only": abstract_only,
                "replication_status": "needs_follow_up",
            }
        )


def _insert_appraisal(
    *,
    domain_key: str,
    document_id: int,
    article_id: int | None,
    payload: dict[str, Any],
    publication_date: Any = None,
) -> int | None:
    now = datetime.now(timezone.utc)
    meta = {k: v for k, v in payload.items() if k.startswith("_")}
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.claim_evidence_appraisal (
                        domain_key, document_id, article_id,
                        finding_text, hypothesis_text,
                        study_design, peer_review_status, paper_support,
                        replication_status, evidence_grade,
                        sample_size_text, reported_effect_text, limitations_quote,
                        evidence_quotes, grader_model, prompt_version, metadata,
                        event_date, ingestion_date, vintage_date
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s::jsonb, %s, %s, %s::jsonb,
                        %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        domain_key,
                        document_id,
                        article_id,
                        payload.get("finding_text"),
                        payload.get("hypothesis_text"),
                        payload.get("study_design"),
                        payload.get("peer_review_status"),
                        payload.get("paper_support"),
                        payload.get("replication_status"),
                        payload.get("evidence_grade"),
                        payload.get("sample_size_text"),
                        payload.get("reported_effect_text"),
                        payload.get("limitations_quote"),
                        json.dumps(payload.get("evidence_quotes") or []),
                        payload.get("_grader_model") or env_str("CLAIM_EVIDENCE_GRADER_MODEL", ""),
                        PROMPT_VERSION,
                        json.dumps(meta),
                        publication_date,
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning("insert appraisal failed document_id=%s: %s", document_id, e)
        return None


def _article_id_from_meta(row: dict[str, Any]) -> int | None:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return None
    aid = meta.get("article_id")
    try:
        return int(aid) if aid is not None else None
    except (TypeError, ValueError):
        return None


def run_claim_evidence_appraisal_batch(
    *,
    domain_key: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Process up to ``limit`` due documents. Returns summary dict.
    """
    if not is_enabled():
        return {"skipped": True, "reason": "CLAIM_EVIDENCE_APPRAISAL_ENABLED=false", "processed": 0}

    batch = limit if limit is not None else env_int("CLAIM_EVIDENCE_APPRAISAL_BATCH", 5)
    rows = _load_due_documents(domain_key=domain_key, limit=batch)
    processed = 0
    inserted = 0
    errors = 0

    async def _run_one(row: dict[str, Any]) -> None:
        nonlocal processed, inserted, errors
        dk = _resolve_row_domain(row, domain_key)
        try:
            payload = await _appraise_document(row, domain_key=dk)
            if not payload:
                errors += 1
                return
            aid = _article_id_from_meta(row)
            # Ensure schema name resolution does not throw for unknown domains
            try:
                resolve_domain_schema(dk)
            except Exception:
                pass
            new_id = _insert_appraisal(
                domain_key=dk,
                document_id=int(row["id"]),
                article_id=aid,
                payload=payload,
                publication_date=row.get("publication_date"),
            )
            processed += 1
            if new_id:
                inserted += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            logger.warning("appraisal batch item failed: %s", e)

    async def _run_all() -> None:
        for row in rows:
            await _run_one(row)

    try:
        asyncio.run(_run_all())
    except RuntimeError as e:
        # Never create a nested loop while another is running — that binds the
        # shared httpx AsyncClient to a loop that is then closed.
        if "running event loop" in str(e).lower():
            raise RuntimeError(
                "run_claim_evidence_appraisal_batch called from a running event loop; "
                "use asyncio.to_thread(run_claim_evidence_appraisal_batch, ...) "
                "or await an async drain"
            ) from e
        raise

    due_after = count_claim_evidence_appraisal_due(domain_key=domain_key)
    logger.info(
        "claim_evidence_appraisal batch: candidates=%s processed=%s inserted=%s errors=%s due=%s",
        len(rows),
        processed,
        inserted,
        errors,
        due_after,
    )
    return {
        "skipped": False,
        "candidates": len(rows),
        "processed": processed,
        "inserted": inserted,
        "errors": errors,
        "due_remaining": due_after,
        "prompt_version": PROMPT_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_documents_by_ids(document_ids: list[int]) -> list[dict[str, Any]]:
    """Load processed_documents rows that still lack an appraisal (package-scoped)."""
    uniq = sorted({int(x) for x in document_ids if x is not None})
    if not uniq:
        return []
    sql = """
        SELECT pd.id, pd.title, pd.source_url, pd.source_type, pd.extracted_sections,
               pd.metadata, pd.publication_date, pd.citations
        FROM intelligence.processed_documents pd
        WHERE pd.id = ANY(%s)
          AND NOT EXISTS (
            SELECT 1 FROM intelligence.claim_evidence_appraisal a
            WHERE a.document_id = pd.id
          )
        ORDER BY pd.id ASC
    """
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (uniq,))
                cols = [d[0] for d in cur.description or []]
                for row in cur.fetchall() or []:
                    out.append(dict(zip(cols, row)))
    except Exception as e:
        logger.warning("load appraisal docs by id failed: %s", e)
    return out


def run_claim_evidence_appraisal_for_documents(
    document_ids: list[int],
    *,
    domain_key: str | None = None,
) -> dict[str, Any]:
    """
    Sync wrapper for package-scoped appraisal.

    Safe from threads / CLI (no running loop). From async code, await
    ``run_claim_evidence_appraisal_for_documents_async`` instead — nesting
    ``asyncio.run`` poisons shared Ollama httpx clients.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_claim_evidence_appraisal_for_documents_async(
                document_ids, domain_key=domain_key
            )
        )
    raise RuntimeError(
        "run_claim_evidence_appraisal_for_documents called from a running event loop; "
        "await run_claim_evidence_appraisal_for_documents_async(...)"
    )


async def run_claim_evidence_appraisal_for_documents_async(
    document_ids: list[int],
    *,
    domain_key: str | None = None,
) -> dict[str, Any]:
    """
    Appraise specific literature documents (editorial Research spine).

    Skips when CLAIM_EVIDENCE_APPRAISAL_ENABLED is off. Does not drain the
    global due queue — only the provided document_ids lacking appraisals.
    """
    if not is_enabled():
        return {
            "skipped": True,
            "reason": "CLAIM_EVIDENCE_APPRAISAL_ENABLED=false",
            "processed": 0,
            "inserted": 0,
            "candidates": 0,
        }

    rows = _load_documents_by_ids(document_ids)
    processed = 0
    inserted = 0
    errors = 0
    appraisal_ids: list[int] = []

    async def _run_one(row: dict[str, Any]) -> None:
        nonlocal processed, inserted, errors
        dk = _resolve_row_domain(row, domain_key)
        try:
            payload = await _appraise_document(row, domain_key=dk)
            if not payload:
                errors += 1
                return
            aid = _article_id_from_meta(row)
            try:
                resolve_domain_schema(dk)
            except Exception:
                pass
            new_id = _insert_appraisal(
                domain_key=dk,
                document_id=int(row["id"]),
                article_id=aid,
                payload=payload,
                publication_date=row.get("publication_date"),
            )
            processed += 1
            if new_id:
                inserted += 1
                appraisal_ids.append(int(new_id))
            else:
                errors += 1
        except Exception as e:
            errors += 1
            logger.warning("scoped appraisal failed document_id=%s: %s", row.get("id"), e)

    for row in rows:
        await _run_one(row)

    return {
        "skipped": False,
        "candidates": len(rows),
        "processed": processed,
        "inserted": inserted,
        "errors": errors,
        "appraisal_ids": appraisal_ids,
        "prompt_version": PROMPT_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json as _json
    import os
    import sys

    if "--force" in sys.argv:
        os.environ["CLAIM_EVIDENCE_APPRAISAL_ENABLED"] = "true"
    print(_json.dumps(run_claim_evidence_appraisal_batch(), indent=2, default=str))
