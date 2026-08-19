"""
Research findings query surface — corpus evidence appraisal with citation chains.

GET /api/research/{domain}/findings
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from schemas.response_schemas import APIResponse
from shared.database.connection import get_ui_db_connection_context
from shared.domain_processing_mode import get_domain_processing_mode
from shared.domain_registry import resolve_domain_schema
from shared.evidence_grade import (
    EVIDENCE_GRADES,
    PEER_REVIEW_STATUSES,
    REPLICATION_STATUSES,
    STUDY_DESIGNS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["Research corpus findings"])


def _citation_chain(row: dict[str, Any]) -> dict[str, Any]:
    """Auditable chain from graded finding → document → quotes."""
    quotes = row.get("evidence_quotes") or []
    if isinstance(quotes, str):
        quotes = []
    return {
        "appraisal_id": row.get("id"),
        "document_id": row.get("document_id"),
        "article_id": row.get("article_id"),
        "document_title": row.get("document_title"),
        "document_url": row.get("source_url"),
        "doi": (row.get("doc_metadata") or {}).get("doi")
        if isinstance(row.get("doc_metadata"), dict)
        else None,
        "pmid": (row.get("doc_metadata") or {}).get("pmid")
        if isinstance(row.get("doc_metadata"), dict)
        else None,
        "evidence_quotes": quotes,
        "limitations_quote": row.get("limitations_quote"),
        "grader_model": row.get("grader_model"),
        "prompt_version": row.get("prompt_version"),
    }


@router.get("/{domain_key}/findings")
async def list_research_findings(
    domain_key: str,
    evidence_grade: str | None = Query(default=None),
    study_design: str | None = Query(default=None),
    peer_review_status: str | None = Query(default=None),
    replication_status: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Substring match on finding_text"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """
    List graded findings for a domain with full citation chains.

    Intended for corpus-mode domains (e.g. neurodiversity) but readable for any
    domain that has claim_evidence_appraisal rows.
    """
    dk = (domain_key or "").strip()
    if not dk:
        raise HTTPException(status_code=400, detail="domain_key required")
    try:
        resolve_domain_schema(dk)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {dk}") from e

    filters: list[str] = ["cea.domain_key = %s"]
    args: list[Any] = [dk]

    def _add_enum(col: str, raw: str | None, allowed: frozenset[str]) -> None:
        if not raw:
            return
        val = raw.strip().lower()
        if val not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {col}={raw!r}; allowed={sorted(allowed)}",
            )
        filters.append(f"cea.{col} = %s")
        args.append(val)

    _add_enum("evidence_grade", evidence_grade, EVIDENCE_GRADES)
    _add_enum("study_design", study_design, STUDY_DESIGNS)
    _add_enum("peer_review_status", peer_review_status, PEER_REVIEW_STATUSES)
    _add_enum("replication_status", replication_status, REPLICATION_STATUSES)

    if q and q.strip():
        filters.append("cea.finding_text ILIKE %s")
        args.append(f"%{q.strip()}%")

    where_sql = " AND ".join(filters)
    sql = f"""
        SELECT cea.id, cea.domain_key, cea.document_id, cea.article_id,
               cea.finding_text, cea.hypothesis_text,
               cea.study_design, cea.peer_review_status, cea.paper_support,
               cea.replication_status, cea.evidence_grade,
               cea.sample_size_text, cea.reported_effect_text, cea.limitations_quote,
               cea.evidence_quotes, cea.grader_model, cea.prompt_version,
               cea.metadata, cea.created_at, cea.updated_at,
               pd.title AS document_title, pd.source_url, pd.metadata AS doc_metadata,
               pd.authors AS document_authors
        FROM intelligence.claim_evidence_appraisal cea
        LEFT JOIN intelligence.processed_documents pd ON pd.id = cea.document_id
        WHERE {where_sql}
        ORDER BY cea.created_at DESC, cea.id DESC
        LIMIT %s OFFSET %s
    """
    args.extend([int(limit), int(offset)])

    rows_out: list[dict[str, Any]] = []
    total = 0
    try:
        with get_ui_db_connection_context() as conn:
            if not conn:
                raise HTTPException(status_code=503, detail="Database unavailable")
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM intelligence.claim_evidence_appraisal cea WHERE {where_sql}",
                    args[:-2],
                )
                total = int(cur.fetchone()[0] or 0)
                cur.execute(sql, args)
                cols = [d[0] for d in cur.description]
                for raw in cur.fetchall() or []:
                    row = dict(zip(cols, raw))
                    # JSONB may already be dict via psycopg2
                    meta = row.get("metadata")
                    if not isinstance(meta, dict):
                        meta = {}
                    doc_meta = row.get("doc_metadata")
                    if not isinstance(doc_meta, dict):
                        doc_meta = {}
                    row["metadata"] = meta
                    row["doc_metadata"] = doc_meta
                    rows_out.append(
                        {
                            "id": row["id"],
                            "domain_key": row["domain_key"],
                            "finding_text": row["finding_text"],
                            "hypothesis_text": row["hypothesis_text"],
                            "study_design": row["study_design"],
                            "peer_review_status": row["peer_review_status"],
                            "paper_support": row["paper_support"],
                            "replication_status": row["replication_status"],
                            "evidence_grade": row["evidence_grade"],
                            "sample_size_text": row["sample_size_text"],
                            "reported_effect_text": row["reported_effect_text"],
                            "created_at": row["created_at"].isoformat()
                            if hasattr(row["created_at"], "isoformat")
                            else row["created_at"],
                            "citation": _citation_chain(row),
                            "processing_mode": get_domain_processing_mode(dk),
                        }
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("list_research_findings failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return APIResponse(
        success=True,
        data={
            "domain_key": dk,
            "processing_mode": get_domain_processing_mode(dk),
            "total": total,
            "limit": limit,
            "offset": offset,
            "findings": rows_out,
        },
    )
