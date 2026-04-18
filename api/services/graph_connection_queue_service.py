"""
Queue for high-level graph connections (merge, associate, hyperedge).

Persists proposals into intelligence.graph_connection_proposals so we can:
- track many-to-many / multi-endpoint clusters (JSONB endpoints),
- dedupe repeated signals (dedupe_key),
- auto-merge or auto-link later via confidence thresholds (min_confidence_for_auto).

Storyline consolidation is the first writer; entity/topic/cross-domain paths can enqueue here too.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE_FOR_AUTO = float(
    os.environ.get("GRAPH_CONNECTION_AUTO_MERGE_MIN", "0.72") or 0.72
)


def storyline_pair_dedupe_key(domain_key: str, id_a: int, id_b: int) -> str:
    lo, hi = (id_a, id_b) if id_a <= id_b else (id_b, id_a)
    return f"merge|storyline|{domain_key}|{lo}|{hi}"


def storyline_hyperedge_dedupe_key(domain_key: str, storyline_ids: list[int]) -> str:
    s = ",".join(str(x) for x in sorted(set(storyline_ids)))
    h = hashlib.sha256(s.encode()).hexdigest()[:24]
    return f"hyperedge|storyline|{domain_key}|{h}"


def _normalize_endpoints(
    domain_key: str | None,
    *,
    storyline_ids: list[int] | None = None,
    topic_ids: list[int] | None = None,
    entity_ids: list[int] | None = None,
    tracked_event_ids: list[int] | None = None,
) -> dict[str, Any]:
    ep: dict[str, Any] = {"domain_key": domain_key}
    if storyline_ids is not None:
        ep["storyline_ids"] = sorted(set(int(x) for x in storyline_ids))
    if topic_ids is not None:
        ep["topic_ids"] = sorted(set(int(x) for x in topic_ids))
    if entity_ids is not None:
        ep["entity_ids"] = sorted(set(int(x) for x in entity_ids))
    if tracked_event_ids is not None:
        ep["tracked_event_ids"] = sorted(set(int(x) for x in tracked_event_ids))
    return ep


def upsert_graph_connection_proposal(
    *,
    dedupe_key: str,
    proposal_kind: str,
    domain_key: str | None,
    confidence: float,
    source: str,
    endpoints: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    subject_summary: str | None = None,
    min_confidence_for_auto: float | None = None,
) -> int | None:
    """
    Insert or update one proposal (confidence/evidence monotonic on conflict).
    Returns proposal id, or None if DB unavailable.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    mca = (
        float(min_confidence_for_auto)
        if min_confidence_for_auto is not None
        else DEFAULT_MIN_CONFIDENCE_FOR_AUTO
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.graph_connection_proposals (
                    proposal_kind, domain_key, confidence, min_confidence_for_auto,
                    source, subject_summary, endpoints, evidence, dedupe_key, status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, 'pending'
                )
                ON CONFLICT (dedupe_key) DO UPDATE SET
                    confidence = GREATEST(
                        intelligence.graph_connection_proposals.confidence,
                        EXCLUDED.confidence
                    ),
                    evidence = CASE
                        WHEN EXCLUDED.confidence
                             >= intelligence.graph_connection_proposals.confidence
                        THEN EXCLUDED.evidence
                        ELSE intelligence.graph_connection_proposals.evidence
                    END,
                    subject_summary = COALESCE(EXCLUDED.subject_summary,
                        intelligence.graph_connection_proposals.subject_summary),
                    proposal_kind = EXCLUDED.proposal_kind,
                    min_confidence_for_auto = EXCLUDED.min_confidence_for_auto,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    proposal_kind,
                    domain_key,
                    float(confidence),
                    mca,
                    source,
                    subject_summary,
                    json.dumps(endpoints),
                    json.dumps(evidence or {}),
                    dedupe_key,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.debug("graph_connection upsert failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_storyline_merge_applied(domain_key: str, primary_id: int, secondary_id: int) -> None:
    """Mark pairwise storyline merge proposal as auto_applied after DB merge succeeds."""
    dk = storyline_pair_dedupe_key(domain_key, primary_id, secondary_id)
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.graph_connection_proposals
                SET status = 'auto_applied',
                    resolved_at = NOW(),
                    resolution_note = %s,
                    updated_at = NOW()
                WHERE dedupe_key = %s
                """,
                (f"merged_into={primary_id}", dk),
            )
            conn.commit()
    except Exception as e:
        logger.debug("mark_storyline_merge_applied: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def record_storyline_merge_candidates(
    domain_key: str,
    merge_candidates: list[tuple[Any, Any, dict[str, float]]],
    *,
    source: str = "storyline_consolidation",
) -> int:
    """Upsert one proposal per merge candidate (pairwise). Returns count attempted."""
    n = 0
    for primary, secondary, similarity in merge_candidates:
        try:
            pid, sid = int(primary.id), int(secondary.id)
        except (TypeError, ValueError, AttributeError):
            continue
        dk = storyline_pair_dedupe_key(domain_key, pid, sid)
        ep = _normalize_endpoints(domain_key, storyline_ids=[pid, sid])
        ev = {k: float(v) for k, v in similarity.items() if isinstance(v, (int, float))}
        ev["primary_storyline_id"] = int(pid)
        ev["secondary_storyline_id"] = int(sid)
        if upsert_graph_connection_proposal(
            dedupe_key=dk,
            proposal_kind="merge",
            domain_key=domain_key,
            confidence=float(similarity.get("overall", 0.0) or 0.0),
            source=source,
            endpoints=ep,
            evidence=ev,
            subject_summary=f"storylines {pid} <-> {sid}",
        ):
            n += 1
    return n


def record_storyline_hyperedge_groups(
    domain_key: str,
    groups: list[list[Any]],
    *,
    pairwise_confidence_fn: Any,
    source: str = "storyline_consolidation",
) -> int:
    """
    Record mega-style clusters as hyperedge proposals (many storylines, one high-level connection).

    pairwise_confidence_fn(a, b) -> float overall similarity in [0,1].
    """
    n = 0
    for group in groups:
        if not group or len(group) < 2:
            continue
        try:
            ids = [int(s.id) for s in group]
        except (TypeError, ValueError, AttributeError):
            continue
        best = 0.0
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                try:
                    sim = pairwise_confidence_fn(group[i], group[j])
                    if isinstance(sim, dict):
                        best = max(best, float(sim.get("overall", 0.0) or 0.0))
                    else:
                        best = max(best, float(sim or 0.0))
                except Exception:
                    continue
        dk = storyline_hyperedge_dedupe_key(domain_key, ids)
        ep = _normalize_endpoints(domain_key, storyline_ids=ids)
        evidence = {
            "member_count": len(ids),
            "max_pairwise_similarity": best,
        }
        if upsert_graph_connection_proposal(
            dedupe_key=dk,
            proposal_kind="hyperedge",
            domain_key=domain_key,
            confidence=float(best),
            source=source,
            endpoints=ep,
            evidence=evidence,
            subject_summary=f"mega_cluster n={len(ids)}",
        ):
            n += 1
    return n


def entity_pair_dedupe_key(domain_key: str, canonical_id_a: int, canonical_id_b: int) -> str:
    lo, hi = (
        (canonical_id_a, canonical_id_b)
        if canonical_id_a <= canonical_id_b
        else (canonical_id_b, canonical_id_a)
    )
    return f"merge|entity|{domain_key}|{lo}|{hi}"


def record_entity_pair_merge_proposal(
    domain_key: str,
    canonical_id_a: int,
    canonical_id_b: int,
    confidence: float,
    evidence: dict[str, Any] | None = None,
    *,
    source: str = "intelligence_cleanup",
) -> int | None:
    """
    Enqueue a canonical entity merge / unify signal (per-domain ``entity_canonical`` silo).
    Evidence should include ``keep_canonical_id`` and ``merge_canonical_id`` when direction matters.
    """
    lo, hi = (
        (canonical_id_a, canonical_id_b)
        if canonical_id_a <= canonical_id_b
        else (canonical_id_b, canonical_id_a)
    )
    dk = entity_pair_dedupe_key(domain_key, lo, hi)
    ep = _normalize_endpoints(domain_key, entity_ids=[lo, hi])
    return upsert_graph_connection_proposal(
        dedupe_key=dk,
        proposal_kind="merge",
        domain_key=domain_key,
        confidence=float(confidence),
        source=source,
        endpoints=ep,
        evidence=evidence or {},
        subject_summary=f"entities {canonical_id_a} <-> {canonical_id_b} ({domain_key})",
    )


def topic_pair_dedupe_key(domain_key: str, topic_id_a: int, topic_id_b: int) -> str:
    lo, hi = (topic_id_a, topic_id_b) if topic_id_a <= topic_id_b else (topic_id_b, topic_id_a)
    return f"associate|topic|{domain_key}|{lo}|{hi}"


def record_topic_pair_association_proposal(
    domain_key: str,
    topic_id_a: int,
    topic_id_b: int,
    confidence: float,
    evidence: dict[str, Any] | None = None,
    *,
    source: str = "topic_clustering",
    proposal_kind: str = "associate",
) -> int | None:
    """
    Enqueue soft link or future merge between two topics in a domain silo.
    proposal_kind 'associate' keeps many-to-many until an auto-merge policy applies.
    """
    dk = topic_pair_dedupe_key(domain_key, topic_id_a, topic_id_b)
    ep = _normalize_endpoints(domain_key, topic_ids=[topic_id_a, topic_id_b])
    return upsert_graph_connection_proposal(
        dedupe_key=dk,
        proposal_kind=proposal_kind,
        domain_key=domain_key,
        confidence=float(confidence),
        source=source,
        endpoints=ep,
        evidence=evidence or {},
        subject_summary=f"topics {topic_id_a} <-> {topic_id_b} ({domain_key})",
    )


def fetch_pending_proposals(
    *,
    limit: int = 50,
    min_confidence: float = 0.0,
    proposal_kind: str | None = None,
) -> list[dict[str, Any]]:
    """Return pending proposals for workers / review APIs."""
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return []
    out: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            q = """
                SELECT id, created_at, proposal_kind, domain_key, confidence,
                       min_confidence_for_auto, source, subject_summary, endpoints, evidence, dedupe_key
                FROM intelligence.graph_connection_proposals
                WHERE status = 'pending' AND confidence >= %s
            """
            args: list[Any] = [min_confidence]
            if proposal_kind:
                q += " AND proposal_kind = %s"
                args.append(proposal_kind)
            q += " ORDER BY confidence DESC, created_at ASC LIMIT %s"
            args.append(limit)
            cur.execute(q, tuple(args))
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                if isinstance(rec.get("endpoints"), str):
                    rec["endpoints"] = json.loads(rec["endpoints"])
                if isinstance(rec.get("evidence"), str):
                    rec["evidence"] = json.loads(rec["evidence"])
                out.append(rec)
        return out
    except Exception as e:
        logger.debug("fetch_pending_proposals: %s", e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_proposal_resolved(
    proposal_id: int,
    status: str,
    resolution_note: str | None = None,
) -> bool:
    """Set proposal status (auto_applied, applied_manual, rejected, superseded)."""
    if status not in ("auto_applied", "applied_manual", "rejected", "superseded", "pending"):
        status = "applied_manual"
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.graph_connection_proposals
                SET status = %s,
                    resolved_at = CASE WHEN %s = 'pending' THEN resolved_at ELSE NOW() END,
                    resolution_note = COALESCE(%s, resolution_note),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, status, resolution_note, proposal_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.debug("mark_proposal_resolved: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _ordered_link_tuple(
    left_kind: str, left_id: int, right_kind: str, right_id: int
) -> tuple[str, int, str, int]:
    if (left_kind, left_id) <= (right_kind, right_id):
        return left_kind, int(left_id), right_kind, int(right_id)
    return right_kind, int(right_id), left_kind, int(left_id)


def insert_graph_connection_link_pair(
    *,
    domain_key: str | None,
    source_proposal_id: int | None,
    left_kind: str,
    left_id: int,
    right_kind: str,
    right_id: int,
    link_role: str,
    confidence: float | None,
) -> bool:
    """Insert one undirected link (canonical endpoint order). Returns True if attempted OK."""
    lk, li, rk, ri = _ordered_link_tuple(left_kind, left_id, right_kind, right_id)
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.graph_connection_links (
                    domain_key, source_proposal_id,
                    left_kind, left_id, right_kind, right_id,
                    link_role, confidence
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (left_kind, left_id, right_kind, right_id, link_role) DO NOTHING
                """,
                (
                    domain_key,
                    source_proposal_id,
                    lk,
                    li,
                    rk,
                    ri,
                    link_role,
                    confidence,
                ),
            )
            conn.commit()
            return True
    except Exception as e:
        logger.debug("insert_graph_connection_link_pair: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def count_pending_graph_connection_proposals() -> int:
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.graph_connection_proposals
                    WHERE status = 'pending'
                    """
                )
                return int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except Exception:
        return 0


def finalize_entity_merges_in_queue(domain_key: str, pairs: list[tuple[int, int]]) -> None:
    """
    After duplicate canonicals are merged in DB, mark matching proposals auto_applied
    or insert a resolved audit row (so the graph queue reflects completed merges).
    """
    from shared.database.connection import get_db_connection

    if not pairs:
        return
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            for keep_id, merge_id in pairs:
                dk = entity_pair_dedupe_key(domain_key, keep_id, merge_id)
                cur.execute(
                    """
                    UPDATE intelligence.graph_connection_proposals
                    SET status = 'auto_applied',
                        resolved_at = NOW(),
                        resolution_note = COALESCE(resolution_note, %s),
                        updated_at = NOW()
                    WHERE dedupe_key = %s
                    """,
                    (f"entity_merged_into={keep_id}", dk),
                )
                if cur.rowcount:
                    continue
                ep = json.dumps(_normalize_endpoints(domain_key, entity_ids=[keep_id, merge_id]))
                ev = json.dumps(
                    {
                        "keep_canonical_id": keep_id,
                        "merge_canonical_id": merge_id,
                        "reason": "same_name_entity_type",
                    }
                )
                note = f"entity_merged_into={keep_id}"
                cur.execute(
                    """
                    INSERT INTO intelligence.graph_connection_proposals (
                        proposal_kind, domain_key, confidence, min_confidence_for_auto,
                        source, subject_summary, endpoints, evidence, dedupe_key, status, resolved_at,
                        resolution_note
                    ) VALUES (
                        'merge', %s, 0.92, %s, 'intelligence_cleanup', %s, %s::jsonb, %s::jsonb, %s,
                        'auto_applied', NOW(), %s
                    )
                    ON CONFLICT (dedupe_key) DO UPDATE SET
                        status = 'auto_applied',
                        resolved_at = NOW(),
                        resolution_note = COALESCE(
                            intelligence.graph_connection_proposals.resolution_note,
                            EXCLUDED.resolution_note
                        ),
                        updated_at = NOW()
                    """,
                    (
                        domain_key,
                        DEFAULT_MIN_CONFIDENCE_FOR_AUTO,
                        f"entities {keep_id} <- {merge_id}",
                        ep,
                        ev,
                        dk,
                        note,
                    ),
                )
        conn.commit()
    except Exception as e:
        logger.debug("finalize_entity_merges_in_queue: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
