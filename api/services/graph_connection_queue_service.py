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
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE_FOR_AUTO = float(
    env_str("GRAPH_CONNECTION_AUTO_MERGE_MIN", "0.72") or 0.72
)


def build_edge_evidence(
    *,
    phase: str,
    method: str,
    score_parts: dict[str, Any] | None = None,
    anchors: dict[str, Any] | None = None,
    refusal_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical evidence JSON for proposals/links (see docs/GRAPH_EDGE_PROVENANCE.md)."""
    out: dict[str, Any] = {
        "phase": phase,
        "method": method,
        "score_parts": score_parts or {},
        "anchors": anchors or {},
        "refusal_key": refusal_key,
    }
    if extra:
        for k, v in extra.items():
            if k not in out:
                out[k] = v
    return out


def persist_score_parts_outcome(
    *,
    domain_key: str | None,
    score_parts: dict[str, Any] | None,
    decision: str,
    source: str = "other",
    proposal_id: int | None = None,
    endpoints: dict[str, Any] | None = None,
) -> int | None:
    """
    Minimal persistence hook when callers already have score_parts
    (desk accept/reject, membership, review agents).
    """
    if not score_parts:
        return None
    try:
        from services.link_score_outcomes_service import record_link_score_outcome

        return record_link_score_outcome(
            domain_key=domain_key,
            score_parts=score_parts,
            decision=decision,
            source=source,
            proposal_id=proposal_id,
            endpoints=endpoints,
        )
    except Exception:
        return None



def merge_edge_evidence(
    base: dict[str, Any] | None,
    *,
    phase: str | None = None,
    method: str | None = None,
    score_parts: dict[str, Any] | None = None,
    anchors: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge proposal evidence into the link provenance contract."""
    src = dict(base or {})
    parts = dict(src.get("score_parts") or {})
    if score_parts:
        parts.update(score_parts)
    anch = dict(src.get("anchors") or {})
    if anchors:
        for k, v in anchors.items():
            if k in anch and isinstance(anch[k], list) and isinstance(v, list):
                anch[k] = list(dict.fromkeys([*anch[k], *v]))
            else:
                anch[k] = v
    # Lift common flat keys into score_parts / anchors when writers used legacy shape.
    for k in ("semantic", "entity", "article", "title", "overall", "cosine"):
        if k in src and k not in parts and isinstance(src[k], (int, float)):
            parts[k] = float(src[k])
    return build_edge_evidence(
        phase=str(phase or src.get("phase") or "unknown"),
        method=str(method or src.get("method") or "unknown"),
        score_parts=parts,
        anchors=anch,
        refusal_key=src.get("refusal_key"),
        extra={
            k: v
            for k, v in src.items()
            if k
            not in (
                "phase",
                "method",
                "score_parts",
                "anchors",
                "refusal_key",
                "semantic",
                "entity",
                "article",
                "title",
                "overall",
                "cosine",
            )
        },
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


def endpoint_key_from_endpoints(
    domain_key: str | None,
    endpoints: dict[str, Any] | None,
) -> str | None:
    """Source-agnostic key for refuse ledger (entity/storyline/topic pairs)."""
    if not isinstance(endpoints, dict):
        return None
    dk = (domain_key or endpoints.get("domain_key") or "global").strip() or "global"
    for kind, field in (
        ("entity", "entity_ids"),
        ("storyline", "storyline_ids"),
        ("topic", "topic_ids"),
    ):
        ids = endpoints.get(field)
        if isinstance(ids, list) and len(ids) >= 2:
            lo, hi = sorted(int(x) for x in ids[:2])
            return f"{kind}|{dk}|{lo}|{hi}"
    return None


def is_pattern_refused(endpoint_key: str) -> bool:
    """True when refuse/quarantine/supersede is active for this endpoint pair."""
    if not endpoint_key:
        return False
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM intelligence.graph_pattern_refusals
                WHERE endpoint_key = %s
                  AND status IN ('refuse', 'quarantine', 'supersede')
                LIMIT 1
                """,
                (endpoint_key,),
            )
            return cur.fetchone() is not None
    except Exception as e:
        # Table may not exist yet pre-migration — fail open for propose.
        logger.debug("is_pattern_refused: %s", e)
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _reopen_refusal_unlocked(cur, endpoint_key: str, *, source: str = "reopen") -> None:
    cur.execute(
        """
        UPDATE intelligence.graph_pattern_refusals
        SET status = 'reopened', updated_at = NOW(), source = %s
        WHERE endpoint_key = %s AND status IN ('refuse', 'quarantine', 'supersede')
        """,
        (source, endpoint_key),
    )


def record_pattern_refusal(
    *,
    endpoint_key: str,
    status: str = "refuse",
    reason: str | None = None,
    domain_key: str | None = None,
    endpoints: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    source: str = "operator",
    proposal_id: int | None = None,
    vault_path: str | None = None,
) -> bool:
    """Upsert refuse/quarantine/supersede for an endpoint pair."""
    if status not in ("refuse", "quarantine", "supersede", "reopened"):
        status = "refuse"
    if not endpoint_key:
        return False
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.graph_pattern_refusals (
                    endpoint_key, dedupe_key, status, reason, domain_key,
                    endpoints, source, proposal_id, vault_path
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (endpoint_key) DO UPDATE SET
                    status = EXCLUDED.status,
                    reason = COALESCE(EXCLUDED.reason, intelligence.graph_pattern_refusals.reason),
                    dedupe_key = COALESCE(EXCLUDED.dedupe_key, intelligence.graph_pattern_refusals.dedupe_key),
                    endpoints = COALESCE(EXCLUDED.endpoints, intelligence.graph_pattern_refusals.endpoints),
                    source = EXCLUDED.source,
                    proposal_id = COALESCE(EXCLUDED.proposal_id, intelligence.graph_pattern_refusals.proposal_id),
                    vault_path = COALESCE(EXCLUDED.vault_path, intelligence.graph_pattern_refusals.vault_path),
                    updated_at = NOW()
                """,
                (
                    endpoint_key,
                    dedupe_key,
                    status,
                    reason,
                    domain_key,
                    json.dumps(endpoints or {}),
                    source,
                    proposal_id,
                    vault_path,
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("record_pattern_refusal: %s", e)
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


def reopen_pattern_refusal(endpoint_key: str, *, source: str = "operator_reopen") -> bool:
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            _reopen_refusal_unlocked(cur, endpoint_key, source=source)
        conn.commit()
        return True
    except Exception as e:
        logger.debug("reopen_pattern_refusal: %s", e)
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


def break_graph_connection_link(
    *,
    left_kind: str,
    left_id: int,
    right_kind: str,
    right_id: int,
    link_role: str = "associated",
    reason: str | None = None,
    quarantine: bool = False,
    domain_key: str | None = None,
    evidence_extra: dict[str, Any] | None = None,
) -> bool:
    """Mark a materialized link broken (or quarantined) and record refuse ledger."""
    lk, li, rk, ri = _ordered_link_tuple(left_kind, left_id, right_kind, right_id)
    new_status = "quarantined" if quarantine else "broken"
    from shared.database.connection import get_db_connection

    if lk == rk:
        ek = f"{lk}|{domain_key or 'global'}|{min(li, ri)}|{max(li, ri)}"
    else:
        ek = f"{lk}:{li}|{rk}:{ri}|{link_role}"

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.graph_connection_links
                SET status = %s,
                    evidence = COALESCE(evidence, '{}'::jsonb) || %s::jsonb,
                    last_scored_at = NOW()
                WHERE left_kind = %s AND left_id = %s
                  AND right_kind = %s AND right_id = %s
                  AND link_role = %s
                  AND status = 'active'
                """,
                (
                    new_status,
                    json.dumps(
                        {
                            "refusal_key": ek,
                            "break_reason": reason or f"link_{new_status}",
                            **(evidence_extra or {}),
                        }
                    ),
                    lk,
                    li,
                    rk,
                    ri,
                    link_role,
                ),
            )
            updated = cur.rowcount > 0
        conn.commit()
    except Exception as e:
        logger.warning("break_graph_connection_link: %s", e)
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

    ep = {"domain_key": domain_key, f"{lk}_ids": [li, ri]} if lk == rk else {
        "domain_key": domain_key,
        "left": {"kind": lk, "id": li},
        "right": {"kind": rk, "id": ri},
    }
    record_pattern_refusal(
        endpoint_key=ek,
        status="quarantine" if quarantine else "refuse",
        reason=reason or f"link_{new_status}",
        domain_key=domain_key,
        endpoints=ep,
        source="break_connection",
    )
    return updated


def count_quarantined_patterns() -> int:
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.graph_pattern_refusals
                    WHERE status IN ('refuse', 'quarantine')
                    """
                )
                return int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except Exception:
        return 0


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
    reopen: bool = False,
    inference_stage: str | None = None,
    cur: Any | None = None,
) -> int | None:
    """
    Insert or update one proposal (confidence/evidence monotonic on conflict).

    Skips insert when the refuse ledger blocks the endpoint pair (unless reopen=True).
    Never reopens rejected/auto_applied rows to pending unless reopen=True.
    Returns proposal id, or None if DB unavailable / refused.

    When ``cur`` is provided, uses the caller's transaction (no checkout/commit).
    """
    from shared.database.connection import get_db_connection

    endpoint_key = endpoint_key_from_endpoints(domain_key, endpoints)
    if endpoint_key and is_pattern_refused(endpoint_key) and not reopen:
        logger.debug("graph_connection upsert skipped (refused): %s", endpoint_key)
        return None

    owns_conn = cur is None
    conn = None
    if owns_conn:
        conn = get_db_connection()
        if not conn:
            return None
    mca = (
        float(min_confidence_for_auto)
        if min_confidence_for_auto is not None
        else DEFAULT_MIN_CONFIDENCE_FOR_AUTO
    )
    try:
        if owns_conn:
            with conn.cursor() as work_cur:
                return _upsert_graph_connection_proposal_on_cur(
                    work_cur,
                    dedupe_key=dedupe_key,
                    proposal_kind=proposal_kind,
                    domain_key=domain_key,
                    confidence=confidence,
                    source=source,
                    endpoints=endpoints,
                    evidence=evidence,
                    subject_summary=subject_summary,
                    mca=mca,
                    reopen=reopen,
                    endpoint_key=endpoint_key,
                    inference_stage=inference_stage,
                    commit=True,
                    conn=conn,
                )
        return _upsert_graph_connection_proposal_on_cur(
            cur,
            dedupe_key=dedupe_key,
            proposal_kind=proposal_kind,
            domain_key=domain_key,
            confidence=confidence,
            source=source,
            endpoints=endpoints,
            evidence=evidence,
            subject_summary=subject_summary,
            mca=mca,
            reopen=reopen,
            endpoint_key=endpoint_key,
            inference_stage=inference_stage,
            commit=False,
            conn=None,
        )
    except Exception as e:
        logger.debug("graph_connection upsert failed: %s", e)
        if owns_conn and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        if owns_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _upsert_graph_connection_proposal_on_cur(
    work_cur: Any,
    *,
    dedupe_key: str,
    proposal_kind: str,
    domain_key: str | None,
    confidence: float,
    source: str,
    endpoints: dict[str, Any],
    evidence: dict[str, Any] | None,
    subject_summary: str | None,
    mca: float,
    reopen: bool,
    endpoint_key: str | None,
    commit: bool,
    conn: Any | None,
    inference_stage: str | None = None,
) -> int | None:
    if reopen and endpoint_key:
        _reopen_refusal_unlocked(work_cur, endpoint_key, source=source)
    if not reopen:
        work_cur.execute(
            """
            SELECT id, status FROM intelligence.graph_connection_proposals
            WHERE dedupe_key = %s
            """,
            (dedupe_key,),
        )
        existing = work_cur.fetchone()
        if existing and existing[1] in (
            "rejected",
            "auto_applied",
            "applied_manual",
            "superseded",
        ):
            if commit and conn is not None:
                conn.commit()
            return int(existing[0])

    reopen_clause = (
        ", resolved_at = NULL, resolution_note = NULL, status = 'pending'"
        if reopen
        else ""
    )
    from shared.connection_inference import (
        INFERENCE_CANDIDATE,
        normalize_inference_stage,
    )

    stage = normalize_inference_stage(inference_stage, default=INFERENCE_CANDIDATE)

    work_cur.execute(
        f"""
        INSERT INTO intelligence.graph_connection_proposals (
            proposal_kind, domain_key, confidence, min_confidence_for_auto,
            source, subject_summary, endpoints, evidence, dedupe_key, status,
            inference_stage
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, 'pending', %s
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
            inference_stage = CASE
                WHEN intelligence.graph_connection_proposals.inference_stage
                     = 'established' THEN 'established'
                WHEN EXCLUDED.inference_stage = 'established' THEN 'established'
                WHEN intelligence.graph_connection_proposals.inference_stage
                     = 'candidate'
                     AND EXCLUDED.inference_stage = 'hypothesized'
                THEN 'candidate'
                ELSE EXCLUDED.inference_stage
            END,
            updated_at = NOW()
            {reopen_clause}
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
            stage,
        ),
    )
    row = work_cur.fetchone()
    if commit and conn is not None:
        conn.commit()
    return int(row[0]) if row else None


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
    proposal_ids: list[int] | None = None,
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
                       min_confidence_for_auto, source, subject_summary, endpoints, evidence, dedupe_key,
                       status
                FROM intelligence.graph_connection_proposals
                WHERE status = 'pending' AND confidence >= %s
            """
            args: list[Any] = [min_confidence]
            if proposal_kind:
                q += " AND proposal_kind = %s"
                args.append(proposal_kind)
            if proposal_ids:
                q += " AND id = ANY(%s)"
                args.append(list(proposal_ids))
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


def get_proposal_by_id(proposal_id: int) -> dict[str, Any] | None:
    """Fetch one graph connection proposal by id (any status)."""
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, created_at, proposal_kind, domain_key, confidence,
                       min_confidence_for_auto, source, subject_summary, endpoints, evidence,
                       dedupe_key, status, resolution_note, resolved_at
                FROM intelligence.graph_connection_proposals
                WHERE id = %s
                """,
                (int(proposal_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            rec = dict(zip(cols, row))
            if isinstance(rec.get("endpoints"), str):
                rec["endpoints"] = json.loads(rec["endpoints"])
            if isinstance(rec.get("evidence"), str):
                rec["evidence"] = json.loads(rec["evidence"])
            return rec
    except Exception as e:
        logger.debug("get_proposal_by_id: %s", e)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def mark_proposal_resolved(
    proposal_id: int,
    status: str,
    resolution_note: str | None = None,
    *,
    inference_stage: str | None = None,
) -> bool:
    """Set proposal status (auto_applied, applied_manual, rejected, superseded).

    Chemistry model: successful apply → established; reject → quarantined
    (unless inference_stage is passed explicitly).
    """
    if status not in ("auto_applied", "applied_manual", "rejected", "superseded", "pending"):
        status = "applied_manual"
    from shared.connection_inference import (
        INFERENCE_ESTABLISHED,
        INFERENCE_QUARANTINED,
        normalize_inference_stage,
    )
    from shared.database.connection import get_db_connection

    if inference_stage is None:
        if status in ("auto_applied", "applied_manual"):
            inference_stage = INFERENCE_ESTABLISHED
        elif status == "rejected":
            inference_stage = INFERENCE_QUARANTINED
    stage = (
        normalize_inference_stage(inference_stage)
        if inference_stage is not None
        else None
    )

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            if stage is not None:
                cur.execute(
                    """
                    UPDATE intelligence.graph_connection_proposals
                    SET status = %s,
                        inference_stage = %s,
                        resolved_at = CASE WHEN %s = 'pending' THEN resolved_at ELSE NOW() END,
                        resolution_note = COALESCE(%s, resolution_note),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, stage, status, resolution_note, proposal_id),
                )
            else:
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
    evidence: dict[str, Any] | None = None,
    source: str | None = None,
    inference_stage: str | None = None,
    cur: Any | None = None,
) -> bool:
    """Insert one undirected link (canonical endpoint order). Returns True if attempted OK."""
    from shared.connection_inference import INFERENCE_ESTABLISHED, normalize_inference_stage

    lk, li, rk, ri = _ordered_link_tuple(left_kind, left_id, right_kind, right_id)
    ev = merge_edge_evidence(
        evidence,
        phase=(evidence or {}).get("phase") if isinstance(evidence, dict) else None,
        method=(evidence or {}).get("method") if isinstance(evidence, dict) else None,
    )
    src = source or (ev.get("phase") if isinstance(ev.get("phase"), str) else None) or "unknown"
    stage = normalize_inference_stage(
        inference_stage, default=INFERENCE_ESTABLISHED
    )

    def _do(cur_inner) -> bool:
        cur_inner.execute(
            """
            INSERT INTO intelligence.graph_connection_links (
                domain_key, source_proposal_id,
                left_kind, left_id, right_kind, right_id,
                link_role, confidence, status, evidence, source,
                inference_stage, last_scored_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s::jsonb, %s, %s, NOW())
            ON CONFLICT (left_kind, left_id, right_kind, right_id, link_role)
            DO UPDATE SET
                confidence = GREATEST(
                    COALESCE(intelligence.graph_connection_links.confidence, 0),
                    COALESCE(EXCLUDED.confidence, 0)
                ),
                evidence = EXCLUDED.evidence,
                source = COALESCE(EXCLUDED.source, intelligence.graph_connection_links.source),
                inference_stage = CASE
                    WHEN EXCLUDED.inference_stage = 'established' THEN 'established'
                    ELSE COALESCE(
                        intelligence.graph_connection_links.inference_stage,
                        EXCLUDED.inference_stage
                    )
                END,
                last_scored_at = NOW(),
                status = CASE
                    WHEN intelligence.graph_connection_links.status = 'active'
                    THEN 'active'
                    ELSE intelligence.graph_connection_links.status
                END
            WHERE intelligence.graph_connection_links.status = 'active'
               OR intelligence.graph_connection_links.status IS NULL
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
                json.dumps(ev),
                src,
                stage,
            ),
        )
        return True

    if cur is not None:
        try:
            return _do(cur)
        except Exception as e:
            logger.debug("insert_graph_connection_link_pair (cur): %s", e)
            return False

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            ok = _do(c)
        conn.commit()
        return ok
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


def count_pending_graph_connection_proposals(
    *,
    actionable_only: bool = False,
    domain_keys: list[str] | None = None,
) -> int:
    """Count pending proposals.

    When ``actionable_only`` is True, exclude entity-``merge`` rows below the
    auto-execute bar (``GRAPH_CONNECTION_ENTITY_MERGE_MIN``). The distillation
    drain intentionally leaves those pending for editorial disambiguation
    (``left_pending_editorial``), so counting them makes the backlog look
    permanently flat once drainable rows are gone — which falsely trips the
    phase stall detector into auto-silencing the drain (see
    ``phase_retry_silence_service``). The backlog/scheduler should treat the
    phase as idle in that state, not stalled.

    ``domain_keys`` restricts to those domains (corpus/research gate).
    """
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return 0
        try:
            with conn.cursor() as cur:
                domain_sql = ""
                params: list[Any] = []
                if domain_keys is not None:
                    if not domain_keys:
                        return 0
                    domain_sql = " AND domain_key = ANY(%s)"
                    params.append(list(domain_keys))
                if actionable_only:
                    entity_merge_min = float(
                        env_str("GRAPH_CONNECTION_ENTITY_MERGE_MIN", "0.88") or 0.88
                    )
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM intelligence.graph_connection_proposals
                        WHERE status = 'pending'
                          AND NOT (
                                proposal_kind = 'merge'
                                AND endpoints ? 'entity_ids'
                                AND COALESCE(confidence, 0) < %s
                          )
                          {domain_sql}
                        """,
                        tuple([entity_merge_min, *params]),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM intelligence.graph_connection_proposals
                        WHERE status = 'pending'
                          {domain_sql}
                        """,
                        tuple(params),
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


def bfs_graph_neighbors(
    *,
    seed_kind: str,
    seed_id: int,
    max_depth: int = 2,
    max_nodes: int = 50,
    domain_key: str | None = None,
) -> dict[str, Any]:
    """
    Bounded BFS over intelligence.graph_connection_links for Investigate shell expansion.
    """
    from collections import deque

    from shared.database.connection import get_db_connection_context

    seed_kind = (seed_kind or "").strip().lower()
    if not seed_kind or seed_id <= 0:
        return {"success": False, "error": "seed_kind and seed_id required"}
    max_depth = max(1, min(5, int(max_depth)))
    max_nodes = max(5, min(200, int(max_nodes)))

    visited: set[tuple[str, int]] = {(seed_kind, int(seed_id))}
    frontier: deque[tuple[str, int, int]] = deque([(seed_kind, int(seed_id), 0)])
    edges: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = [
        {"kind": seed_kind, "id": int(seed_id), "depth": 0}
    ]

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            while frontier and len(visited) < max_nodes:
                kind, obj_id, depth = frontier.popleft()
                if depth >= max_depth:
                    continue
                cur.execute(
                    """
                    SELECT id, left_kind, left_id, right_kind, right_id,
                           link_role, confidence, domain_key, source_proposal_id
                    FROM intelligence.graph_connection_links
                    WHERE ((left_kind = %s AND left_id = %s)
                       OR (right_kind = %s AND right_id = %s))
                      AND COALESCE(status, 'active') = 'active'
                    LIMIT 80
                    """,
                    (kind, obj_id, kind, obj_id),
                )
                for row in cur.fetchall():
                    (
                        link_id,
                        lk,
                        li,
                        rk,
                        ri,
                        role,
                        conf,
                        dk,
                        prop_id,
                    ) = row
                    edges.append(
                        {
                            "id": int(link_id),
                            "left_kind": lk,
                            "left_id": int(li),
                            "right_kind": rk,
                            "right_id": int(ri),
                            "link_role": role,
                            "confidence": conf,
                            "domain_key": dk,
                            "source_proposal_id": prop_id,
                        }
                    )
                    for nk, nid in ((lk, li), (rk, ri)):
                        key = (str(nk), int(nid))
                        if key in visited:
                            continue
                        if domain_key and dk and str(dk) != domain_key:
                            continue
                        visited.add(key)
                        nodes.append({"kind": key[0], "id": key[1], "depth": depth + 1})
                        frontier.append((key[0], key[1], depth + 1))
                        if len(visited) >= max_nodes:
                            break

    return {
        "success": True,
        "seed": {"kind": seed_kind, "id": int(seed_id)},
        "max_depth": max_depth,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
