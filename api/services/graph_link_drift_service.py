"""
Sliding re-score of weak / stale graph_connection_links (drift review).

Updates confidence + evidence + last_scored_at; quarantines when score falls
below floor. Feature-flagged default off.

Enable path (ops):
  - Set ``GRAPH_LINK_DRIFT_REVIEW_ENABLED=true`` in Widow API ``.env`` and restart
    ``news-intelligence-api-public`` so AutomationManager runs ``graph_link_drift_review``.
  - Or dry-run / force-apply without the flag:
    ``PYTHONPATH=api python3 api/scripts/run_graph_link_drift_dry_run.py``
    ``PYTHONPATH=api python3 api/scripts/run_graph_link_drift_dry_run.py --apply --limit 40``
  - Tunables: ``GRAPH_LINK_DRIFT_DAYS`` (stale window), ``GRAPH_LINK_DRIFT_CONF_MAX``,
    ``GRAPH_LINK_DRIFT_QUARANTINE_FLOOR``, ``GRAPH_LINK_DRIFT_BATCH``,
    ``GRAPH_LINK_DRIFT_TEMPORAL_HALF_LIFE_DAYS`` (confidence decay vs age).
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from config.runtime import env_float, env_int, env_str
from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)


def graph_link_drift_enabled() -> bool:
    return env_str("GRAPH_LINK_DRIFT_REVIEW_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _drift_days() -> int:
    return max(1, env_int("GRAPH_LINK_DRIFT_DAYS", 14))


def _conf_max() -> float:
    try:
        return float(env_str("GRAPH_LINK_DRIFT_CONF_MAX", "0.70"))
    except ValueError:
        return 0.70


def _quarantine_floor() -> float:
    try:
        return float(env_str("GRAPH_LINK_DRIFT_QUARANTINE_FLOOR", "0.40"))
    except ValueError:
        return 0.40


def _batch_limit() -> int:
    return max(1, env_int("GRAPH_LINK_DRIFT_BATCH", 40))


def _temporal_half_life_days() -> float:
    try:
        return max(1.0, float(env_str("GRAPH_LINK_DRIFT_TEMPORAL_HALF_LIFE_DAYS", "21")))
    except ValueError:
        return 21.0


def temporal_confidence_decay(
    prior_confidence: float,
    *,
    age_days: float | None,
    half_life_days: float | None = None,
) -> float:
    """
    Exponential decay of prior confidence by link age (days since last score).

    age_days=None → mild 0.95 keep factor (legacy non-storyline path).
    """
    prior = max(0.0, min(1.0, float(prior_confidence or 0.0)))
    if age_days is None:
        return max(0.0, min(1.0, prior * 0.95))
    half = float(half_life_days if half_life_days is not None else _temporal_half_life_days())
    age = max(0.0, float(age_days))
    factor = math.pow(0.5, age / half) if half > 0 else 1.0
    return max(0.0, min(1.0, prior * factor))

def _storyline_text(cur, schema: str, storyline_id: int) -> str:
    cur.execute(
        f"""
        SELECT COALESCE(title, '') || ' ' ||
               COALESCE(canonical_narrative, master_summary, summary, '')
        FROM {schema}.storylines WHERE id = %s
        """,
        (storyline_id,),
    )
    row = cur.fetchone()
    return (row[0] or "")[:2000] if row else ""


def _sei_set(cur, schema: str, storyline_id: int) -> set[str]:
    cur.execute(
        f"""
        SELECT lower(entity_name) FROM {schema}.story_entity_index
        WHERE storyline_id = %s AND entity_name IS NOT NULL
        LIMIT 40
        """,
        (storyline_id,),
    )
    return {str(r[0]) for r in cur.fetchall() if r[0]}


def _rescore_storyline_pair(
    cur, domain_key: str, a: int, b: int
) -> tuple[float, dict[str, float]]:
    from services.embedding_link_candidate_service import blend_link_score
    from services.embeddings_worker_service import search_embedding_chunks

    schema = resolve_domain_schema(domain_key)
    text_a = _storyline_text(cur, schema, a)
    if not text_a.strip():
        return 0.0, {"semantic": 0.0, "entity": 0.0, "overall": 0.0}
    ents_a = _sei_set(cur, schema, a)
    ents_b = _sei_set(cur, schema, b)
    ent_j = 0.0
    if ents_a and ents_b:
        inter = len(ents_a & ents_b)
        union = len(ents_a | ents_b)
        ent_j = float(inter) / float(union) if union else 0.0
    # Cosine: query A, look for articles in B's membership
    cur.execute(
        f"SELECT article_id FROM {schema}.storyline_articles WHERE storyline_id = %s LIMIT 80",
        (b,),
    )
    b_arts = [int(r[0]) for r in cur.fetchall()]
    semantic = 0.0
    if b_arts:
        try:
            hits = search_embedding_chunks(
                text_a,
                limit=5,
                source_types=["article"],
                domain_key=domain_key,
                storyline_article_ids=b_arts,
            )
            if hits:
                semantic = max(float(h.get("similarity") or 0.0) for h in hits)
        except Exception as e:
            logger.debug("drift search: %s", e)
            semantic = ent_j * 0.5
    else:
        semantic = ent_j * 0.5
    overall = blend_link_score(
        semantic=semantic,
        entity_jaccard=ent_j,
        domain_key=domain_key,
    )
    return overall, {"semantic": semantic, "entity": ent_j, "overall": overall}


def rescore_active_graph_links(*, limit: int | None = None) -> dict[str, Any]:
    """Re-score stale/weak active links; quarantine when below floor."""
    from services.graph_connection_queue_service import (
        break_graph_connection_link,
        build_edge_evidence,
    )

    lim = limit if limit is not None else _batch_limit()
    days = _drift_days()
    conf_max = _conf_max()
    floor = _quarantine_floor()
    stats = {
        "examined": 0,
        "updated": 0,
        "quarantined": 0,
        "skipped": 0,
        "errors": 0,
    }
    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db_connection"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, left_kind, left_id, right_kind, right_id,
                       link_role, confidence, evidence, source,
                       EXTRACT(EPOCH FROM (NOW() - COALESCE(last_scored_at, created_at)))
                           / 86400.0 AS age_days
                FROM intelligence.graph_connection_links
                WHERE status = 'active'
                  AND (
                    COALESCE(confidence, 0) < %s
                    OR last_scored_at IS NULL
                    OR last_scored_at < NOW() - (%s || ' days')::interval
                  )
                ORDER BY COALESCE(last_scored_at, '1970-01-01'::timestamptz) ASC
                LIMIT %s
                """,
                (conf_max, days, lim),
            )
            rows = cur.fetchall()

        half_life = _temporal_half_life_days()
        for row in rows:
            stats["examined"] += 1
            (
                _lid,
                domain_key,
                left_kind,
                left_id,
                right_kind,
                right_id,
                link_role,
                old_conf,
                old_ev,
                source,
                age_days,
            ) = row
            try:
                if (
                    left_kind == "storyline"
                    and right_kind == "storyline"
                    and domain_key
                ):
                    with conn.cursor() as cur:
                        overall, parts = _rescore_storyline_pair(
                            cur, str(domain_key), int(left_id), int(right_id)
                        )
                    # Blend fresh score with age-decayed prior so stale links drift down.
                    decayed_prior = temporal_confidence_decay(
                        float(old_conf or 0.0),
                        age_days=float(age_days) if age_days is not None else None,
                        half_life_days=half_life,
                    )
                    overall = max(0.0, min(1.0, 0.70 * overall + 0.30 * decayed_prior))
                    parts = dict(parts)
                    parts["decayed_prior"] = decayed_prior
                    parts["age_days"] = float(age_days) if age_days is not None else None
                    parts["overall"] = overall
                else:
                    overall = temporal_confidence_decay(
                        float(old_conf or 0.5),
                        age_days=float(age_days) if age_days is not None else None,
                        half_life_days=half_life,
                    )
                    parts = {
                        "overall": overall,
                        "semantic": overall,
                        "entity": 0.0,
                        "age_days": float(age_days) if age_days is not None else None,
                    }

                if isinstance(old_ev, str):
                    try:
                        old_ev = json.loads(old_ev)
                    except Exception:
                        old_ev = {}
                evidence = build_edge_evidence(
                    phase="graph_link_drift_review",
                    method="cosine_chunk",
                    score_parts=parts,
                    anchors=(old_ev or {}).get("anchors")
                    if isinstance(old_ev, dict)
                    else {},
                    extra={
                        "prior_confidence": float(old_conf) if old_conf is not None else None
                    },
                )

                if overall < floor:
                    ok = break_graph_connection_link(
                        left_kind=str(left_kind),
                        left_id=int(left_id),
                        right_kind=str(right_kind),
                        right_id=int(right_id),
                        link_role=str(link_role or "associated"),
                        reason="drift_rescore",
                        quarantine=True,
                        domain_key=str(domain_key) if domain_key else None,
                        evidence_extra={"score_parts": parts},
                    )
                    if ok:
                        stats["quarantined"] += 1
                    else:
                        stats["skipped"] += 1
                    continue

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.graph_connection_links
                        SET confidence = %s,
                            evidence = %s::jsonb,
                            last_scored_at = NOW(),
                            source = COALESCE(source, %s)
                        WHERE id = %s AND status = 'active'
                        """,
                        (
                            overall,
                            json.dumps(evidence),
                            source or "graph_link_drift_review",
                            int(_lid),
                        ),
                    )
                    if cur.rowcount:
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                conn.commit()
            except Exception as e:
                logger.debug("drift row: %s", e)
                stats["errors"] += 1
                try:
                    conn.rollback()
                except Exception:
                    pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return stats
