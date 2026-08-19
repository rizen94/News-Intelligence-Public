"""
Find clusters of similar extracted_claims for operator / agent review.

Groups by normalized subject (echo clusters) and normalized triple across contexts
(repeat clusters). Used by scan_similar_claims.py and GET /api/context_centric/claims/similar_clusters.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

ClusterMode = Literal["subject", "triple", "both"]

_SUBJECT_MIN_LEN = 3
_SAMPLE_CLAIMS = 6


def _since_dt(since_days: int) -> datetime:
    days = max(1, min(365, int(since_days)))
    return datetime.now(timezone.utc) - timedelta(days=days)


def _generic_subject_sql(alias: str = "ec") -> str:
    try:
        from services.claim_extraction_service import claim_promotion_generic_subject_exclude_sql

        return claim_promotion_generic_subject_exclude_sql().replace("ec.", f"{alias}.")
    except Exception:
        return f"""
  AND char_length(trim(COALESCE({alias}.subject_text, ''))) >= {_SUBJECT_MIN_LEN}
"""


def _domain_filter_sql(domain_key: str | None, alias: str = "c") -> tuple[str, list[Any]]:
    if not domain_key:
        return "", []
    return f" AND {alias}.domain_key = %s ", [domain_key.strip()]


def _query_filter_sql(query: str | None, alias: str = "ec") -> tuple[str, list[Any]]:
    if not query or not str(query).strip():
        return "", []
    q = f"%{str(query).strip()}%"
    return (
        f"""
  AND (
    {alias}.subject_text ILIKE %s
    OR {alias}.predicate_text ILIKE %s
    OR {alias}.object_text ILIKE %s
  )
""",
        [q, q, q],
    )


def _fetch_sample_claims(
    cur,
    *,
    since: datetime,
    subject_norm: str | None = None,
    predicate_norm: str | None = None,
    object_norm: str | None = None,
    domain_key: str | None = None,
    limit: int = _SAMPLE_CLAIMS,
) -> list[dict[str, Any]]:
    conds = ["ec.created_at >= %s"]
    args: list[Any] = [since]
    if subject_norm is not None:
        conds.append("lower(trim(COALESCE(ec.subject_text, ''))) = %s")
        args.append(subject_norm)
    if predicate_norm is not None:
        conds.append("lower(trim(COALESCE(ec.predicate_text, ''))) = %s")
        args.append(predicate_norm)
    if object_norm is not None:
        conds.append("lower(trim(COALESCE(ec.object_text, ''))) = %s")
        args.append(object_norm)
    dom_sql, dom_args = _domain_filter_sql(domain_key)
    args.extend(dom_args)
    args.append(limit)
    cur.execute(
        f"""
        SELECT ec.id, ec.context_id, c.domain_key, c.title,
               ec.subject_text, ec.predicate_text, ec.object_text,
               ec.confidence, ec.created_at
        FROM intelligence.extracted_claims ec
        JOIN intelligence.contexts c ON c.id = ec.context_id
        WHERE {" AND ".join(conds)}
        {dom_sql}
        ORDER BY ec.confidence DESC NULLS LAST, ec.created_at DESC
        LIMIT %s
        """,
        tuple(args),
    )
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        out.append(
            {
                "id": int(row[0]),
                "context_id": int(row[1]),
                "domain_key": row[2],
                "context_title": row[3],
                "subject_text": row[4],
                "predicate_text": row[5],
                "object_text": row[6],
                "confidence": float(row[7]) if row[7] is not None else None,
                "created_at": row[8].isoformat() if row[8] else None,
            }
        )
    return out


def find_subject_echo_clusters(
    *,
    since_days: int = 7,
    min_claim_count: int = 3,
    min_context_count: int = 2,
    domain_key: str | None = None,
    query: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Same normalized subject across multiple claims/contexts — narrative echo."""
    since = _since_dt(since_days)
    generic = _generic_subject_sql("ec")
    dom_sql, dom_args = _domain_filter_sql(domain_key)
    q_sql, q_args = _query_filter_sql(query)
    clusters: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            if not conn:
                return clusters
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '90s'")
                cur.execute(
                    f"""
                    SELECT lower(trim(COALESCE(ec.subject_text, ''))) AS subject_norm,
                           COUNT(*)::bigint AS claim_count,
                           COUNT(DISTINCT ec.context_id)::bigint AS context_count,
                           COUNT(DISTINCT c.domain_key)::bigint AS domain_count,
                           array_agg(DISTINCT c.domain_key) AS domains,
                           MAX(ec.created_at) AS latest_at,
                           AVG(ec.confidence)::float AS avg_confidence
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    WHERE ec.created_at >= %s
                    {generic}
                    {dom_sql}
                    {q_sql}
                    GROUP BY 1
                    HAVING COUNT(*) >= %s AND COUNT(DISTINCT ec.context_id) >= %s
                    ORDER BY claim_count DESC, context_count DESC
                    LIMIT %s
                    """,
                    tuple(
                        [since, *dom_args, *q_args, min_claim_count, min_context_count, limit]
                    ),
                )
                for row in cur.fetchall():
                    subject_norm = row[0] or ""
                    if not subject_norm:
                        continue
                    samples = _fetch_sample_claims(
                        cur,
                        since=since,
                        subject_norm=subject_norm,
                        domain_key=domain_key,
                    )
                    clusters.append(
                        {
                            "cluster_type": "subject_echo",
                            "subject_norm": subject_norm,
                            "claim_count": int(row[1]),
                            "context_count": int(row[2]),
                            "domain_count": int(row[3]),
                            "domains": list(row[4] or []),
                            "latest_at": row[5].isoformat() if row[5] else None,
                            "avg_confidence": round(float(row[6] or 0), 3),
                            "sample_claims": samples,
                            "note_hint": (
                                f"Subject '{subject_norm}' appears in {row[1]} claims "
                                f"across {row[2]} contexts — review for emerging narrative."
                            ),
                        }
                    )
    except Exception as e:
        logger.warning("find_subject_echo_clusters: %s", e)
    return clusters


def find_triple_repeat_clusters(
    *,
    since_days: int = 7,
    min_context_count: int = 2,
    domain_key: str | None = None,
    query: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Same subject+predicate+object repeated across contexts — near-duplicate fact thread."""
    since = _since_dt(since_days)
    generic = _generic_subject_sql("ec")
    dom_sql, dom_args = _domain_filter_sql(domain_key)
    q_sql, q_args = _query_filter_sql(query)
    clusters: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            if not conn:
                return clusters
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '90s'")
                cur.execute(
                    f"""
                    SELECT lower(trim(COALESCE(ec.subject_text, ''))) AS subject_norm,
                           lower(trim(COALESCE(ec.predicate_text, ''))) AS predicate_norm,
                           lower(trim(COALESCE(ec.object_text, ''))) AS object_norm,
                           COUNT(*)::bigint AS claim_count,
                           COUNT(DISTINCT ec.context_id)::bigint AS context_count,
                           array_agg(DISTINCT c.domain_key) AS domains,
                           MAX(ec.created_at) AS latest_at,
                           AVG(ec.confidence)::float AS avg_confidence
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    WHERE ec.created_at >= %s
                    {generic}
                    {dom_sql}
                    {q_sql}
                    GROUP BY 1, 2, 3
                    HAVING COUNT(DISTINCT ec.context_id) >= %s
                    ORDER BY context_count DESC, claim_count DESC
                    LIMIT %s
                    """,
                    tuple([since, *dom_args, *q_args, min_context_count, limit]),
                )
                for row in cur.fetchall():
                    subject_norm, predicate_norm, object_norm = row[0], row[1], row[2]
                    if not subject_norm:
                        continue
                    samples = _fetch_sample_claims(
                        cur,
                        since=since,
                        subject_norm=subject_norm,
                        predicate_norm=predicate_norm,
                        object_norm=object_norm,
                        domain_key=domain_key,
                    )
                    triple_label = " / ".join(
                        x for x in (subject_norm, predicate_norm, object_norm) if x
                    )
                    clusters.append(
                        {
                            "cluster_type": "triple_repeat",
                            "subject_norm": subject_norm,
                            "predicate_norm": predicate_norm,
                            "object_norm": object_norm,
                            "claim_count": int(row[3]),
                            "context_count": int(row[4]),
                            "domains": list(row[5] or []),
                            "latest_at": row[6].isoformat() if row[6] else None,
                            "avg_confidence": round(float(row[7] or 0), 3),
                            "sample_claims": samples,
                            "note_hint": (
                                f"Repeated triple across {row[4]} contexts: {triple_label}"
                            ),
                        }
                    )
    except Exception as e:
        logger.warning("find_triple_repeat_clusters: %s", e)
    return clusters


def scan_similar_claim_clusters(
    *,
    since_days: int = 7,
    min_claim_count: int = 3,
    min_context_count: int = 2,
    domain_key: str | None = None,
    query: str | None = None,
    mode: ClusterMode = "both",
    limit: int = 40,
) -> dict[str, Any]:
    """Run subject and/or triple clustering; return merged payload for API / agent."""
    subject_clusters: list[dict[str, Any]] = []
    triple_clusters: list[dict[str, Any]] = []
    if mode in ("subject", "both"):
        subject_clusters = find_subject_echo_clusters(
            since_days=since_days,
            min_claim_count=min_claim_count,
            min_context_count=min_context_count,
            domain_key=domain_key,
            query=query,
            limit=limit,
        )
    if mode in ("triple", "both"):
        triple_clusters = find_triple_repeat_clusters(
            since_days=since_days,
            min_context_count=min_context_count,
            domain_key=domain_key,
            query=query,
            limit=min(limit, 30),
        )
    return {
        "scan_since": _since_dt(since_days).isoformat(),
        "since_days": since_days,
        "domain_key": domain_key,
        "query": query,
        "mode": mode,
        "subject_echo_clusters": subject_clusters,
        "triple_repeat_clusters": triple_clusters,
        "cluster_count": len(subject_clusters) + len(triple_clusters),
    }


def _author_overlap(a: list[str] | None, b: list[str] | None) -> bool:
    """True when author sets share a normalized name (same-group replication hint)."""
    def _norm(names: list[str] | None) -> set[str]:
        out: set[str] = set()
        for n in names or []:
            s = " ".join(str(n).lower().split())
            if s:
                out.add(s)
        return out

    left, right = _norm(a), _norm(b)
    if not left or not right:
        return False
    return bool(left & right)


def classify_replication_status(
    *,
    matching_findings: list[dict[str, Any]],
    seed_authors: list[str] | None = None,
) -> str:
    """
    Map similar findings to replication_status vocabulary.

    - no matches → single_study (or needs_follow_up when operator marks thin evidence)
    - matches with author overlap only → replicated_same_group
    - matches without author overlap → replicated_independent
    - explicit contradiction flag on a match → contradicted
    """
    from shared.evidence_grade import normalize_replication_status

    if not matching_findings:
        return normalize_replication_status("single_study")

    has_independent = False
    has_same_group = False
    for row in matching_findings:
        if row.get("contradicts"):
            return normalize_replication_status("contradicted")
        authors = row.get("authors") or row.get("document_authors")
        if _author_overlap(seed_authors, authors if isinstance(authors, list) else None):
            has_same_group = True
        else:
            has_independent = True
    if has_independent:
        return normalize_replication_status("replicated_independent")
    if has_same_group:
        return normalize_replication_status("replicated_same_group")
    return normalize_replication_status("needs_follow_up")


def find_similar_appraisal_findings(
    *,
    finding_text: str,
    domain_key: str | None = None,
    exclude_appraisal_id: int | None = None,
    limit: int = 10,
    min_similarity: float = 0.82,
) -> list[dict[str, Any]]:
    """
    Embedding-based finding match over intelligence.claim_evidence_appraisal.

    Falls back to trigram / ILIKE when embedding_chunks are empty or embedding fails.
    Distinguishes same-group vs independent via processed_documents.authors.
    """
    text = (finding_text or "").strip()
    if len(text) < 12:
        return []

    embedding: list[float] | None = None
    try:
        from services.ai_storyline_discovery import get_embedding_single

        embedding = get_embedding_single(text[:2000])
    except Exception as e:
        logger.debug("appraisal embedding unavailable: %s", e)

    results: list[dict[str, Any]] = []
    with get_db_connection_context() as conn:
        if not conn:
            return []
        with conn.cursor() as cur:
            if embedding:
                try:
                    # Match via embedding_chunks when source_type=processed_document seeded
                    cur.execute(
                        """
                        SELECT cea.id, cea.finding_text, cea.domain_key, cea.document_id,
                               cea.evidence_grade, cea.replication_status,
                               pd.authors,
                               1 - (ec.embedding <=> %s::vector) AS similarity
                        FROM intelligence.claim_evidence_appraisal cea
                        LEFT JOIN intelligence.processed_documents pd ON pd.id = cea.document_id
                        LEFT JOIN LATERAL (
                            SELECT embedding
                            FROM intelligence.embedding_chunks
                            WHERE source_type = 'processed_document'
                              AND source_id = cea.document_id
                            ORDER BY chunk_index
                            LIMIT 1
                        ) ec ON TRUE
                        WHERE cea.finding_text IS NOT NULL
                          AND (%s::text IS NULL OR cea.domain_key = %s)
                          AND (%s::bigint IS NULL OR cea.id <> %s)
                          AND ec.embedding IS NOT NULL
                        ORDER BY ec.embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (
                            embedding,
                            domain_key,
                            domain_key,
                            exclude_appraisal_id,
                            exclude_appraisal_id,
                            embedding,
                            max(1, min(50, int(limit))),
                        ),
                    )
                    for row in cur.fetchall() or []:
                        sim = float(row[7] or 0.0)
                        if sim < float(min_similarity):
                            continue
                        results.append(
                            {
                                "appraisal_id": int(row[0]),
                                "finding_text": row[1],
                                "domain_key": row[2],
                                "document_id": row[3],
                                "evidence_grade": row[4],
                                "replication_status": row[5],
                                "authors": list(row[6] or []) if row[6] is not None else [],
                                "similarity": round(sim, 4),
                                "match_method": "embedding",
                            }
                        )
                except Exception as e:
                    logger.debug("embedding finding match failed: %s", e)

            if not results:
                # Lexical fallback
                cur.execute(
                    """
                    SELECT cea.id, cea.finding_text, cea.domain_key, cea.document_id,
                           cea.evidence_grade, cea.replication_status, pd.authors
                    FROM intelligence.claim_evidence_appraisal cea
                    LEFT JOIN intelligence.processed_documents pd ON pd.id = cea.document_id
                    WHERE cea.finding_text IS NOT NULL
                      AND (%s::text IS NULL OR cea.domain_key = %s)
                      AND (%s::bigint IS NULL OR cea.id <> %s)
                      AND (
                        lower(cea.finding_text) LIKE '%%' || lower(%s) || '%%'
                        OR similarity(lower(cea.finding_text), lower(%s)) > 0.35
                      )
                    ORDER BY similarity(lower(cea.finding_text), lower(%s)) DESC NULLS LAST
                    LIMIT %s
                    """,
                    (
                        domain_key,
                        domain_key,
                        exclude_appraisal_id,
                        exclude_appraisal_id,
                        text[:200],
                        text[:500],
                        text[:500],
                        max(1, min(50, int(limit))),
                    ),
                )
                for row in cur.fetchall() or []:
                    results.append(
                        {
                            "appraisal_id": int(row[0]),
                            "finding_text": row[1],
                            "domain_key": row[2],
                            "document_id": row[3],
                            "evidence_grade": row[4],
                            "replication_status": row[5],
                            "authors": list(row[6] or []) if row[6] is not None else [],
                            "similarity": None,
                            "match_method": "lexical",
                        }
                    )
    return results


def update_appraisal_replication_status(
    appraisal_id: int,
    *,
    seed_authors: list[str] | None = None,
    min_similarity: float = 0.82,
) -> dict[str, Any]:
    """Recompute and persist replication_status for one appraisal row."""
    with get_db_connection_context() as conn:
        if not conn:
            return {"ok": False, "error": "no_db"}
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cea.finding_text, cea.domain_key, pd.authors
                FROM intelligence.claim_evidence_appraisal cea
                LEFT JOIN intelligence.processed_documents pd ON pd.id = cea.document_id
                WHERE cea.id = %s
                """,
                (int(appraisal_id),),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "not_found"}
            finding_text, domain_key, authors = row[0], row[1], list(row[2] or [])
        matches = find_similar_appraisal_findings(
            finding_text=str(finding_text or ""),
            domain_key=str(domain_key) if domain_key else None,
            exclude_appraisal_id=int(appraisal_id),
            min_similarity=min_similarity,
        )
        status = classify_replication_status(
            matching_findings=matches,
            seed_authors=seed_authors if seed_authors is not None else authors,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.claim_evidence_appraisal
                SET replication_status = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    status,
                    __import__("json").dumps(
                        {
                            "replication_match_count": len(matches),
                            "replication_match_ids": [m["appraisal_id"] for m in matches[:20]],
                            "replication_scanned_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    int(appraisal_id),
                ),
            )
        conn.commit()
    return {"ok": True, "appraisal_id": int(appraisal_id), "replication_status": status, "matches": len(matches)}

