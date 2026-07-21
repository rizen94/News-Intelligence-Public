"""
Protein harden — chemistry stimulus: promote surviving candidate bonds and
enqueue storyline refinement from harden events (not heat census).
"""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_int, env_str
from shared.connection_inference import (
    INFERENCE_CANDIDATE,
    INFERENCE_ESTABLISHED,
    INFERENCE_HYPOTHESIZED,
)
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def protein_harden_enabled() -> bool:
    from shared.chemistry_beaker import protein_harden_enabled as _enabled

    return _enabled()


def run_protein_harden(*, limit: int | None = None) -> dict[str, Any]:
    """
    1) Promote high-confidence hypothesized → candidate (stimulus applied band).
    2) For recently established / auto_applied storyline links, enqueue refinement.
    """
    if not protein_harden_enabled():
        return {"enabled": False, "promoted": 0, "refined": 0}
    lim = limit if limit is not None else max(1, env_int("PROTEIN_HARDEN_BATCH", 40))
    promote_at = float(env_str("PROTEIN_HARDEN_PROMOTE_CONFIDENCE", "0.62") or 0.62)
    stats: dict[str, Any] = {
        "promoted": 0,
        "refined": 0,
        "skipped": 0,
        "errors": 0,
    }
    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.graph_connection_proposals
                SET inference_stage = %s, updated_at = NOW()
                WHERE id IN (
                    SELECT id FROM intelligence.graph_connection_proposals
                    WHERE status = 'pending'
                      AND COALESCE(inference_stage, 'candidate') = %s
                      AND COALESCE(confidence, 0) >= %s
                    ORDER BY confidence DESC NULLS LAST, id DESC
                    LIMIT %s
                )
                RETURNING id, domain_key
                """,
                (INFERENCE_CANDIDATE, INFERENCE_HYPOTHESIZED, promote_at, lim),
            )
            promoted_rows = cur.fetchall()
        conn.commit()
        stats["promoted"] = len(promoted_rows)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    l.domain_key,
                    CASE
                        WHEN l.left_kind = 'storyline' THEN l.left_id
                        WHEN l.right_kind = 'storyline' THEN l.right_id
                        ELSE NULL
                    END AS storyline_id
                FROM intelligence.graph_connection_links l
                WHERE COALESCE(l.inference_stage, 'established') = %s
                  AND l.status = 'active'
                  AND l.domain_key IS NOT NULL
                  AND (
                    l.left_kind = 'storyline' OR l.right_kind = 'storyline'
                  )
                  AND COALESCE(l.last_scored_at, l.created_at, NOW())
                      > NOW() - INTERVAL '7 days'
                ORDER BY 1, 2
                LIMIT %s
                """,
                (INFERENCE_ESTABLISHED, lim),
            )
            link_rows = [r for r in cur.fetchall() if r[0] and r[1]]
        from services.content_refinement_queue_service import (
            enqueue_refinement_for_stimulus,
        )

        for domain_key, storyline_id in link_rows:
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config

                cfg = get_domain_synthesis_config(str(domain_key))
                # Event-narrative domains still get census RAG elsewhere; chemistry
                # kinds harden only via stimulus.
                if not cfg.is_chemistry_kind() and not cfg.link_score_profile.allow_storyline_merge:
                    pass
                res = enqueue_refinement_for_stimulus(
                    domain_key=str(domain_key),
                    storyline_id=int(storyline_id),
                    reason="protein_harden",
                )
                stats["refined"] += int(res.get("enqueued") or 0)
            except Exception as e:
                stats["errors"] += 1
                logger.debug("protein_harden refine %s/%s: %s", domain_key, storyline_id, e)
        return stats
    except Exception as e:
        logger.warning("run_protein_harden: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {**stats, "error": str(e)[:200]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def count_protein_harden_pending() -> int:
    if not protein_harden_enabled():
        return 0
    promote_at = float(env_str("PROTEIN_HARDEN_PROMOTE_CONFIDENCE", "0.62") or 0.62)
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM intelligence.graph_connection_proposals
                WHERE status = 'pending'
                  AND COALESCE(inference_stage, 'candidate') = %s
                  AND COALESCE(confidence, 0) >= %s
                """,
                (INFERENCE_HYPOTHESIZED, promote_at),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
