"""
Research subject ledger — medicine / AI / neurodiversity evidence_thread and research_topic proteins.

Entity-rooted subjects (ailments, conditions, research topics) with paper/claim
verdicts. Not linear arc chronicles.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

_VALID_VERDICTS = frozenset(
    {"substantiated", "proved", "disproved", "inconclusive", "not_applicable"}
)
_RESEARCH_DOMAINS = frozenset({"medicine", "artificial-intelligence", "neurodiversity"})


def get_research_subject(
    domain_key: str,
    *,
    canonical_entity_id: int | None = None,
    entity_name: str | None = None,
    limit_claims: int = 50,
) -> dict[str, Any]:
    """Load a research subject by entity id or name (case-insensitive)."""
    dk = (domain_key or "").strip()
    if dk not in _RESEARCH_DOMAINS:
        return {"success": False, "error": "domain_not_research_kind", "domain_key": dk}

    entity = _resolve_entity(dk, canonical_entity_id=canonical_entity_id, entity_name=entity_name)
    if not entity:
        return {"success": False, "error": "entity_not_found", "domain_key": dk}

    eid = int(entity["id"])
    proteins = _list_subject_proteins(dk, eid)
    claims = _list_claims(dk, eid, limit=limit_claims)
    subtypes = [p for p in proteins if p.get("parent_entity_id") or p.get("subtype_label")]

    knowledge_profile_id = None
    assertion_counts: dict[str, int] = {}
    try:
        from services.knowledge_profile_service import get_profile

        kp = get_profile(
            domain_key=dk,
            canonical_entity_id=eid,
            include_citations=False,
        )
        if kp:
            knowledge_profile_id = int(kp["id"])
            assertion_counts = {
                "is": len(kp.get("is_assertions") or []),
                "is_not": len(kp.get("is_not_assertions") or []),
                "open": len(kp.get("open_questions") or []),
            }
    except Exception as e:
        logger.debug("knowledge profile lookup skipped: %s", e)

    return {
        "success": True,
        "domain_key": dk,
        "entity": entity,
        "proteins": proteins,
        "subtypes": subtypes,
        "claims": claims,
        "claim_verdict_counts": _verdict_counts(claims),
        "knowledge_profile_id": knowledge_profile_id,
        "knowledge_profile_assertion_counts": assertion_counts,
    }


def upsert_research_claim(
    *,
    domain_key: str,
    canonical_entity_id: int,
    hypothesis_text: str | None = None,
    finding_summary: str | None = None,
    verdict: str = "inconclusive",
    protein_id: int | None = None,
    article_id: int | None = None,
    document_id: int | None = None,
    evidence_strength: str | None = None,
    study_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dk = (domain_key or "").strip()
    if dk not in _RESEARCH_DOMAINS:
        return {"success": False, "error": "domain_not_research_kind"}
    v = (verdict or "inconclusive").strip().lower()
    if v not in _VALID_VERDICTS:
        return {"success": False, "error": "invalid_verdict", "verdict": verdict}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.research_claim_ledger (
                    domain_key, canonical_entity_id, protein_id, article_id, document_id,
                    hypothesis_text, finding_summary, verdict, evidence_strength,
                    study_type, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s::jsonb, '{}'::jsonb)
                )
                RETURNING id
                """,
                (
                    dk,
                    int(canonical_entity_id),
                    protein_id,
                    article_id,
                    document_id,
                    hypothesis_text,
                    finding_summary,
                    v,
                    evidence_strength,
                    study_type,
                    __import__("json").dumps(metadata or {}),
                ),
            )
            new_id = int(cur.fetchone()[0])
        conn.commit()
    return {"success": True, "id": new_id, "verdict": v}


def link_subject_protein(
    *,
    domain_key: str,
    canonical_entity_id: int,
    storyline_id: int,
    parent_entity_id: int | None = None,
    subtype_label: str | None = None,
    severity_label: str | None = None,
) -> dict[str, Any]:
    dk = (domain_key or "").strip()
    if dk not in _RESEARCH_DOMAINS:
        return {"success": False, "error": "domain_not_research_kind"}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.research_subject_proteins (
                    domain_key, canonical_entity_id, storyline_id,
                    parent_entity_id, subtype_label, severity_label
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (domain_key, canonical_entity_id, storyline_id) DO UPDATE SET
                    parent_entity_id = COALESCE(EXCLUDED.parent_entity_id, research_subject_proteins.parent_entity_id),
                    subtype_label = COALESCE(EXCLUDED.subtype_label, research_subject_proteins.subtype_label),
                    severity_label = COALESCE(EXCLUDED.severity_label, research_subject_proteins.severity_label),
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    dk,
                    int(canonical_entity_id),
                    int(storyline_id),
                    parent_entity_id,
                    subtype_label,
                    severity_label,
                ),
            )
            rid = int(cur.fetchone()[0])
        conn.commit()
    return {"success": True, "id": rid}


def _resolve_entity(
    domain_key: str,
    *,
    canonical_entity_id: int | None,
    entity_name: str | None,
) -> dict[str, Any] | None:
    schema = resolve_domain_schema(domain_key)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if canonical_entity_id is not None:
                cur.execute(
                    f"""
                    SELECT id, canonical_name, wikidata_qid, entity_type
                    FROM {schema}.entity_canonical WHERE id = %s
                    """,
                    (int(canonical_entity_id),),
                )
            elif entity_name:
                cur.execute(
                    f"""
                    SELECT id, canonical_name, wikidata_qid, entity_type
                    FROM {schema}.entity_canonical
                    WHERE lower(canonical_name) = lower(%s)
                    ORDER BY id ASC LIMIT 1
                    """,
                    (entity_name.strip(),),
                )
            else:
                return None
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "canonical_name": row[1],
                "wikidata_qid": row[2],
                "entity_type": row[3],
            }


def _list_subject_proteins(domain_key: str, entity_id: int) -> list[dict[str, Any]]:
    schema = resolve_domain_schema(domain_key)
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT rsp.id, rsp.storyline_id, rsp.parent_entity_id,
                           rsp.subtype_label, rsp.severity_label, rsp.updated_at,
                           s.title, s.status, COALESCE(s.total_articles, 0)
                    FROM intelligence.research_subject_proteins rsp
                    LEFT JOIN {schema}.storylines s ON s.id = rsp.storyline_id
                    WHERE rsp.domain_key = %s AND rsp.canonical_entity_id = %s
                    ORDER BY rsp.updated_at DESC
                    """.format(schema=schema),
                    (domain_key, entity_id),
                )
                for row in cur.fetchall():
                    out.append(
                        {
                            "id": int(row[0]),
                            "storyline_id": int(row[1]),
                            "parent_entity_id": int(row[2]) if row[2] is not None else None,
                            "subtype_label": row[3],
                            "severity_label": row[4],
                            "updated_at": row[5].isoformat() if row[5] else None,
                            "title": row[6],
                            "status": row[7],
                            "article_count": int(row[8] or 0),
                        }
                    )
            except Exception as e:
                logger.debug("research_subject_proteins: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
            # Fallback: storylines indexed to this entity name
            if not out:
                try:
                    cur.execute(
                        f"""
                        SELECT DISTINCT s.id, s.title, s.status, s.updated_at,
                               COALESCE(s.total_articles, 0)
                        FROM {schema}.storylines s
                        JOIN {schema}.story_entity_index sei ON sei.storyline_id = s.id
                        JOIN {schema}.entity_canonical ec
                          ON lower(ec.canonical_name) = lower(sei.entity_name)
                        WHERE ec.id = %s
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT 40
                        """,
                        (entity_id,),
                    )
                    for sid, title, status, updated_at, ac in cur.fetchall():
                        out.append(
                            {
                                "id": None,
                                "storyline_id": int(sid),
                                "parent_entity_id": None,
                                "subtype_label": None,
                                "severity_label": None,
                                "updated_at": updated_at.isoformat() if updated_at else None,
                                "title": title,
                                "status": status,
                                "article_count": int(ac or 0),
                                "inferred": True,
                            }
                        )
                except Exception as e:
                    logger.debug("research subject fallback: %s", e)
    return out


def _list_claims(domain_key: str, entity_id: int, *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT id, protein_id, article_id, document_id, hypothesis_text,
                           finding_summary, verdict, evidence_strength, study_type,
                           created_at
                    FROM intelligence.research_claim_ledger
                    WHERE domain_key = %s AND canonical_entity_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (domain_key, entity_id, limit),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                        d["created_at"] = d["created_at"].isoformat()
                    out.append(d)
            except Exception as e:
                logger.debug("research_claim_ledger list: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
    return out


def _verdict_counts(claims: list[dict[str, Any]]) -> dict[str, int]:
    counts = {v: 0 for v in sorted(_VALID_VERDICTS)}
    for c in claims:
        v = str(c.get("verdict") or "inconclusive")
        if v in counts:
            counts[v] += 1
    return counts
