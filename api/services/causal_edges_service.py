"""Phase A: typed causal edges (Postgres SSOT) + optional Neo4j projection hooks.

Mode C (assembly link modes): consequences are **proposals / typed edges only**.
Never use this module to silently insert storyline_articles or scan the full
corpus for “related” membership. Callers must pass explicit cause/effect ids.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_ALLOWED_KINDS = frozenset(
    {"tracked_event", "chronological_event", "storyline", "entity", "context"}
)
_ALLOWED_GRADES = frozenset({"strong", "moderate", "weak", "speculative"})


def upsert_causal_edge(
    *,
    cause_kind: str,
    cause_id: int,
    effect_kind: str,
    effect_id: int,
    relation: str = "contributes_to",
    confidence: float = 0.5,
    evidence_grade: str = "weak",
    evidence_context_ids: list[int] | None = None,
    reasoning_steps: list[dict[str, Any]] | list[str] | None = None,
    domain_key: str | None = None,
    source: str = "editorial_room",
    source_proposal_id: int | None = None,
) -> int | None:
    if cause_kind not in _ALLOWED_KINDS or effect_kind not in _ALLOWED_KINDS:
        raise ValueError(f"invalid causal kind: {cause_kind}->{effect_kind}")
    grade = evidence_grade if evidence_grade in _ALLOWED_GRADES else "weak"
    conf = max(0.0, min(1.0, float(confidence)))
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.causal_edges (
                        cause_kind, cause_id, effect_kind, effect_id, relation,
                        confidence, evidence_grade, evidence_context_ids,
                        reasoning_steps, domain_key, source, source_proposal_id, status,
                        updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s,
                        'active', NOW()
                    )
                    ON CONFLICT (cause_kind, cause_id, effect_kind, effect_id, relation)
                    DO UPDATE SET
                        confidence = GREATEST(intelligence.causal_edges.confidence, EXCLUDED.confidence),
                        evidence_grade = EXCLUDED.evidence_grade,
                        evidence_context_ids = EXCLUDED.evidence_context_ids,
                        reasoning_steps = EXCLUDED.reasoning_steps,
                        domain_key = COALESCE(EXCLUDED.domain_key, intelligence.causal_edges.domain_key),
                        updated_at = NOW(),
                        status = 'active'
                    RETURNING id
                    """,
                    (
                        cause_kind,
                        int(cause_id),
                        effect_kind,
                        int(effect_id),
                        relation or "contributes_to",
                        conf,
                        grade,
                        json.dumps(evidence_context_ids or []),
                        json.dumps(reasoning_steps or []),
                        domain_key,
                        source,
                        source_proposal_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning("upsert_causal_edge failed: %s", e)
        return None


def list_causal_edges(
    *,
    domain_key: str | None = None,
    cause_kind: str | None = None,
    cause_id: int | None = None,
    effect_kind: str | None = None,
    effect_id: int | None = None,
    min_confidence: float = 0.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = ["status = 'active'", "confidence >= %s"]
    params: list[Any] = [float(min_confidence)]
    if domain_key:
        clauses.append("domain_key = %s")
        params.append(domain_key)
    if cause_kind and cause_id is not None:
        clauses.append("cause_kind = %s AND cause_id = %s")
        params.extend([cause_kind, int(cause_id)])
    if effect_kind and effect_id is not None:
        clauses.append("effect_kind = %s AND effect_id = %s")
        params.extend([effect_kind, int(effect_id)])
    params.append(max(1, min(int(limit), 200)))
    sql = f"""
        SELECT id, created_at, cause_kind, cause_id, effect_kind, effect_id,
               relation, confidence, evidence_grade, evidence_context_ids,
               reasoning_steps, domain_key, source, status
        FROM intelligence.causal_edges
        WHERE {' AND '.join(clauses)}
        ORDER BY confidence DESC, updated_at DESC
        LIMIT %s
    """
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
                return [dict(r) for r in rows]
    except Exception as e:
        logger.debug("list_causal_edges: %s", e)
        return []


def edges_for_storyline(domain_key: str, storyline_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
    out = list_causal_edges(
        cause_kind="storyline",
        cause_id=storyline_id,
        domain_key=domain_key,
        limit=limit,
    )
    out.extend(
        list_causal_edges(
            effect_kind="storyline",
            effect_id=storyline_id,
            domain_key=domain_key,
            limit=limit,
        )
    )
    # de-dupe by id
    seen: set[int] = set()
    deduped: list[dict[str, Any]] = []
    for e in out:
        eid = int(e.get("id") or 0)
        if eid and eid not in seen:
            seen.add(eid)
            deduped.append(e)
    return deduped[:limit]


def edges_for_tracked_event(event_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
    out = list_causal_edges(cause_kind="tracked_event", cause_id=event_id, limit=limit)
    out.extend(list_causal_edges(effect_kind="tracked_event", effect_id=event_id, limit=limit))
    seen: set[int] = set()
    deduped: list[dict[str, Any]] = []
    for e in out:
        eid = int(e.get("id") or 0)
        if eid and eid not in seen:
            seen.add(eid)
            deduped.append(e)
    return deduped[:limit]


def project_edges_to_neo4j(limit: int = 500) -> dict[str, Any]:
    """Optional read projection. No-op unless NEO4J_URI is configured."""
    from config.runtime import env_str

    uri = (env_str("NEO4J_URI", "") or "").strip()
    if not uri:
        return {"synced": 0, "skipped": True, "reason": "NEO4J_URI unset"}
    edges = list_causal_edges(limit=limit)
    # Soft import — Neo4j driver optional
    try:
        from neo4j import GraphDatabase  # type: ignore
    except ImportError:
        return {"synced": 0, "skipped": True, "reason": "neo4j driver not installed"}
    user = env_str("NEO4J_USER", "neo4j")
    password = env_str("NEO4J_PASSWORD", "")
    synced = 0
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            for e in edges:
                session.run(
                    """
                    MERGE (c:CausalNode {kind: $ck, id: $cid})
                    MERGE (f:CausalNode {kind: $ek, id: $eid})
                    MERGE (c)-[r:CAUSES {relation: $rel}]->(f)
                    SET r.confidence = $conf, r.evidence_grade = $grade, r.edge_id = $edge_id
                    """,
                    ck=e["cause_kind"],
                    cid=int(e["cause_id"]),
                    ek=e["effect_kind"],
                    eid=int(e["effect_id"]),
                    rel=e.get("relation") or "contributes_to",
                    conf=float(e.get("confidence") or 0),
                    grade=e.get("evidence_grade") or "weak",
                    edge_id=int(e["id"]),
                )
                synced += 1
        driver.close()
    except Exception as ex:
        logger.warning("neo4j causal projection failed: %s", ex)
        return {"synced": synced, "error": str(ex)}
    return {"synced": synced, "skipped": False}


def has_causal_edge_between(
    kind_a: str,
    id_a: int,
    kind_b: str,
    id_b: int,
    *,
    domain_key: str | None = None,
) -> bool:
    """True when an active causal edge exists in either direction between the pair."""
    if kind_a not in _ALLOWED_KINDS or kind_b not in _ALLOWED_KINDS:
        return False
    try:
        from shared.database.connection import get_ui_db_connection_context

        clauses = [
            "status = 'active'",
            "( (cause_kind = %s AND cause_id = %s AND effect_kind = %s AND effect_id = %s)",
            "   OR (cause_kind = %s AND cause_id = %s AND effect_kind = %s AND effect_id = %s) )",
        ]
        params: list[Any] = [
            kind_a,
            int(id_a),
            kind_b,
            int(id_b),
            kind_b,
            int(id_b),
            kind_a,
            int(id_a),
        ]
        if domain_key:
            clauses.append("domain_key = %s")
            params.append(domain_key)
        sql = f"""
            SELECT 1 FROM intelligence.causal_edges
            WHERE {' AND '.join(clauses)}
            LIMIT 1
        """
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() is not None
    except Exception as e:
        logger.debug("has_causal_edge_between: %s", e)
        return False


# Claim-text predicates that suggest a directed causal relation.
_CAUSAL_PREDICATE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("caused", "causes"),
    ("cause", "causes"),
    ("led to", "leads_to"),
    ("leads to", "leads_to"),
    ("resulted in", "results_in"),
    ("results in", "results_in"),
    ("triggered", "triggers"),
    ("contributed to", "contributes_to"),
    ("sparked", "sparks"),
)


def _normalize_claim_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def extract_causal_predicates_from_claim(
    subject: str,
    predicate: str,
    obj: str,
) -> dict[str, Any] | None:
    """
    If predicate text matches a causal cue, return a candidate edge skeleton.

    Does not write to DB — callers batch-upsert via ``harvest_causal_edges_from_claims``.
    """
    pred = _normalize_claim_text(predicate)
    if not pred or not (subject or "").strip() or not (obj or "").strip():
        return None
    for needle, relation in _CAUSAL_PREDICATE_PATTERNS:
        if needle in pred or pred == needle:
            return {
                "cause_text": (subject or "").strip(),
                "effect_text": (obj or "").strip(),
                "relation": relation,
                "predicate": predicate,
                "matched_cue": needle,
            }
    return None


def harvest_causal_edges_from_claims(
    *,
    domain_key: str | None = None,
    limit: int = 50,
    min_confidence: float = 0.55,
    source: str = "claim_predicate_harvest",
) -> dict[str, int]:
    """
    Batch: scan recent extracted_claims for causal cue predicates.

    When subject/object resolve to distinct entity ids in the domain silo,
    upsert a speculative entity→entity causal edge. Otherwise count as matched
    but skip write (candidates stay in stats / logs via reasoning-ready shape).
    """
    stats = {"scanned": 0, "matched": 0, "written": 0, "skipped": 0}
    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import resolve_domain_schema
        from psycopg2.extras import RealDictCursor

        clauses = ["ec.confidence >= %s"]
        params: list[Any] = [float(min_confidence)]
        if domain_key:
            clauses.append("c.domain_key = %s")
            params.append(domain_key)
        params.append(max(1, min(int(limit), 500)))
        sql = f"""
            SELECT ec.id, ec.context_id, ec.subject_text, ec.predicate_text,
                   ec.object_text, ec.confidence, c.domain_key
            FROM intelligence.extracted_claims ec
            JOIN intelligence.contexts c ON c.id = ec.context_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ec.created_at DESC NULLS LAST, ec.id DESC
            LIMIT %s
        """

        def _resolve_entity_id(cur, schema: str, name: str) -> int | None:
            if not name or not schema:
                return None
            cur.execute(
                f"""
                SELECT id FROM {schema}.entity_canonical
                WHERE lower(canonical_name) = lower(%s)
                ORDER BY id ASC
                LIMIT 1
                """,
                (name,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None

        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = list(cur.fetchall() or [])
            for row in rows:
                stats["scanned"] += 1
                cand = extract_causal_predicates_from_claim(
                    row.get("subject_text") or "",
                    row.get("predicate_text") or "",
                    row.get("object_text") or "",
                )
                if not cand:
                    continue
                stats["matched"] += 1
                dk = row.get("domain_key") or domain_key
                if not dk:
                    stats["skipped"] += 1
                    continue
                try:
                    schema = resolve_domain_schema(str(dk))
                except Exception:
                    stats["skipped"] += 1
                    continue
                with conn.cursor() as cur:
                    cause_id = _resolve_entity_id(cur, schema, cand["cause_text"])
                    effect_id = _resolve_entity_id(cur, schema, cand["effect_text"])
                if not cause_id or not effect_id or cause_id == effect_id:
                    stats["skipped"] += 1
                    continue
                ctx_id = row.get("context_id")
                eid = upsert_causal_edge(
                    cause_kind="entity",
                    cause_id=int(cause_id),
                    effect_kind="entity",
                    effect_id=int(effect_id),
                    relation=cand["relation"],
                    confidence=min(0.55, float(row.get("confidence") or 0.5)),
                    evidence_grade="speculative",
                    evidence_context_ids=[int(ctx_id)] if ctx_id is not None else [],
                    reasoning_steps=[
                        {
                            "step": "claim_predicate_harvest",
                            "claim_id": row.get("id"),
                            "cause_text": cand["cause_text"],
                            "effect_text": cand["effect_text"],
                            "matched_cue": cand["matched_cue"],
                        }
                    ],
                    domain_key=str(dk),
                    source=source,
                )
                if eid:
                    stats["written"] += 1
                else:
                    stats["skipped"] += 1
            conn.commit()
    except Exception as e:
        logger.warning("harvest_causal_edges_from_claims: %s", e)
    return stats


def seed_edges_from_correlations(*, days: int = 30, min_strength: float = 0.6, limit: int = 25) -> int:
    """Promote strong cross-domain correlations into typed causal edges (weak grade)."""
    written = 0
    try:
        from shared.database.connection import get_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT correlation_id, event_ids, correlation_strength, domain_1
                    FROM intelligence.cross_domain_correlations
                    WHERE discovered_at >= NOW() - (%s * INTERVAL '1 day')
                      AND correlation_strength >= %s
                    ORDER BY correlation_strength DESC
                    LIMIT %s
                    """,
                    (max(1, days), min_strength, limit),
                )
                for corr in cur.fetchall() or []:
                    event_ids = corr.get("event_ids") or []
                    if isinstance(event_ids, str):
                        try:
                            event_ids = json.loads(event_ids)
                        except Exception:
                            event_ids = []
                    ids = [int(x) for x in event_ids if isinstance(x, (int, float))]
                    if len(ids) < 2:
                        continue
                    for i in range(len(ids) - 1):
                        eid = upsert_causal_edge(
                            cause_kind="tracked_event",
                            cause_id=ids[i],
                            effect_kind="tracked_event",
                            effect_id=ids[i + 1],
                            relation="precedes_correlated",
                            confidence=float(corr.get("correlation_strength") or 0.5),
                            evidence_grade="weak",
                            domain_key=corr.get("domain_1"),
                            source="correlation_seed",
                            reasoning_steps=[
                                {
                                    "step": "correlation_promote",
                                    "correlation_id": corr.get("correlation_id"),
                                }
                            ],
                        )
                        if eid:
                            written += 1
            conn.commit()
    except Exception as e:
        logger.warning("seed_edges_from_correlations: %s", e)
    return written
