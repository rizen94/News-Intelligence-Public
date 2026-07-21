"""
Embedding-ranked graph link candidates → intelligence.graph_connection_proposals.

Uses pgvector cosine over embedding_chunks (article/context) to propose storyline
associates and optional cross-domain entity associates. No Neo4j / GNN.
"""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_float, env_int, env_str
from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)


def embedding_link_candidates_enabled() -> bool:
    from shared.chemistry_beaker import embedding_link_candidates_enabled as _enabled

    return _enabled()


def _min_cosine() -> float:
    try:
        return float(env_str("EMBEDDING_LINK_MIN_COSINE", "0.62"))
    except ValueError:
        return 0.62


def _merge_band() -> float:
    try:
        return float(env_str("EMBEDDING_LINK_MERGE_BAND", "0.78"))
    except ValueError:
        return 0.78


def _max_storylines() -> int:
    return max(1, env_int("EMBEDDING_LINK_MAX_STORYLINES", 12))


def _neighbors_per_query() -> int:
    return max(3, env_int("EMBEDDING_LINK_NEIGHBORS", 8))


def blend_link_score(*, semantic: float, entity_jaccard: float = 0.0) -> float:
    """Primary semantic + light entity bonus → overall confidence in [0,1]."""
    s = max(0.0, min(1.0, float(semantic)))
    e = max(0.0, min(1.0, float(entity_jaccard)))
    return max(0.0, min(1.0, 0.80 * s + 0.20 * e))


def _sei_entities(cur, schema: str, storyline_id: int, limit: int = 25) -> set[str]:
    cur.execute(
        f"""
        SELECT lower(entity_name)
        FROM {schema}.story_entity_index
        WHERE storyline_id = %s AND entity_name IS NOT NULL
        ORDER BY COALESCE(is_core_entity, false) DESC, mention_count DESC NULLS LAST
        LIMIT %s
        """,
        (storyline_id, limit),
    )
    return {str(r[0]) for r in cur.fetchall() if r[0]}


def _storyline_query_text(cur, schema: str, storyline_id: int) -> str | None:
    cur.execute(
        f"""
        SELECT title,
               COALESCE(canonical_narrative, master_summary, summary, description, '')
        FROM {schema}.storylines
        WHERE id = %s AND merged_into_id IS NULL
        """,
        (storyline_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    title, body = row[0] or "", row[1] or ""
    text = f"{title}\n{body}".strip()
    return text[:2500] if text else None


def _article_id_from_chunk(hit: dict[str, Any]) -> int | None:
    meta = hit.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("article_id") is not None:
        try:
            return int(meta["article_id"])
        except (TypeError, ValueError):
            pass
    sid = str(hit.get("source_id") or "")
    if ":" in sid:
        try:
            return int(sid.split(":", 1)[1])
        except ValueError:
            return None
    return None


def _storylines_for_article(cur, schema: str, article_id: int) -> list[int]:
    cur.execute(
        f"""
        SELECT storyline_id FROM {schema}.storyline_articles
        WHERE article_id = %s
        LIMIT 5
        """,
        (article_id,),
    )
    return [int(r[0]) for r in cur.fetchall()]


def _active_link_exists(
    cur, *, domain_key: str, a: int, b: int, link_role: str = "associated_similarity"
) -> bool:
    lo, hi = (a, b) if a <= b else (b, a)
    cur.execute(
        """
        SELECT 1 FROM intelligence.graph_connection_links
        WHERE left_kind = 'storyline' AND right_kind = 'storyline'
          AND left_id = %s AND right_id = %s
          AND link_role = %s
          AND status IN ('active', 'quarantined')
          AND (domain_key IS NULL OR domain_key = %s)
        LIMIT 1
        """,
        (lo, hi, link_role, domain_key),
    )
    return cur.fetchone() is not None


def run_embedding_link_candidates_for_domain(
    domain_key: str,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Propose storyline associates (and merge-band proposals) from chunk cosine."""
    from services.embeddings_worker_service import search_embedding_chunks
    from services.graph_connection_queue_service import (
        build_edge_evidence,
        record_storyline_merge_candidates,
        storyline_pair_dedupe_key,
        upsert_graph_connection_proposal,
    )
    from shared.connection_inference import stage_for_embedding_source

    _candidate_stage = stage_for_embedding_source(exploratory=False)
    lim = limit if limit is not None else _max_storylines()
    min_cos = _min_cosine()
    merge_band = _merge_band()
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, Any] = {
        "domain_key": domain_key,
        "scanned": 0,
        "proposals": 0,
        "merges_enqueued": 0,
        "skipped": 0,
        "errors": 0,
    }

    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id FROM {schema}.storylines
                WHERE status = 'active' AND merged_into_id IS NULL
                  AND COALESCE(article_count, 0) >= 3
                ORDER BY updated_at DESC NULLS LAST, article_count DESC NULLS LAST
                LIMIT %s
                """,
                (lim,),
            )
            storyline_ids = [int(r[0]) for r in cur.fetchall()]

        for sid in storyline_ids:
            stats["scanned"] += 1
            try:
                with conn.cursor() as cur:
                    qtext = _storyline_query_text(cur, schema, sid)
                    if not qtext:
                        stats["skipped"] += 1
                        continue
                    core_ents = _sei_entities(cur, schema, sid)
            except Exception as e:
                logger.debug("embedding_link seed %s/%s: %s", domain_key, sid, e)
                stats["errors"] += 1
                continue

            try:
                hits = search_embedding_chunks(
                    qtext,
                    limit=_neighbors_per_query(),
                    source_types=["article", "context"],
                    domain_key=None,  # allow cross-domain hits
                )
            except Exception as e:
                logger.debug("search_embedding_chunks: %s", e)
                stats["errors"] += 1
                continue

            seen_peers: set[tuple[str, int]] = set()
            for hit in hits:
                sim = float(hit.get("similarity") or 0.0)
                if sim < min_cos:
                    continue
                peer_dk = str(hit.get("domain_key") or domain_key)
                peer_schema = resolve_domain_schema(peer_dk)
                art_id = _article_id_from_chunk(hit)
                if art_id is None:
                    continue
                try:
                    with conn.cursor() as cur:
                        peers = _storylines_for_article(cur, peer_schema, art_id)
                except Exception:
                    peers = []
                for peer_sid in peers:
                    if peer_dk == domain_key and peer_sid == sid:
                        continue
                    key = (peer_dk, peer_sid)
                    if key in seen_peers:
                        continue
                    seen_peers.add(key)

                    ent_j = 0.0
                    try:
                        with conn.cursor() as cur:
                            peer_ents = _sei_entities(cur, peer_schema, peer_sid)
                            if core_ents and peer_ents:
                                inter = len(core_ents & peer_ents)
                                union = len(core_ents | peer_ents)
                                ent_j = float(inter) / float(union) if union else 0.0
                            if peer_dk == domain_key and _active_link_exists(
                                cur, domain_key=domain_key, a=sid, b=peer_sid
                            ):
                                stats["skipped"] += 1
                                continue
                    except Exception:
                        pass

                    overall = blend_link_score(semantic=sim, entity_jaccard=ent_j)
                    evidence = build_edge_evidence(
                        phase="embedding_link_candidates",
                        method="cosine_chunk",
                        score_parts={
                            "semantic": sim,
                            "entity": ent_j,
                            "overall": overall,
                        },
                        anchors={
                            "article_ids": [art_id],
                            "chunk_ids": [
                                f"{hit.get('source_type')}:{hit.get('source_id')}:{hit.get('chunk_index')}"
                            ],
                        },
                        extra={"link_role_intent": "associated_similarity"},
                    )

                    if peer_dk == domain_key and overall >= merge_band:
                        try:
                            from services.domain_synthesis_config import (
                                get_domain_synthesis_config,
                            )

                            if not get_domain_synthesis_config(
                                domain_key
                            ).link_score_profile.allow_storyline_merge:
                                overall = min(overall, merge_band - 0.01)
                        except Exception:
                            pass
                    if peer_dk == domain_key and overall >= merge_band:
                        # Lightweight StorylineInfo stand-ins for record helper
                        class _S:
                            def __init__(self, i: int):
                                self.id = i

                        n = record_storyline_merge_candidates(
                            domain_key,
                            [
                                (
                                    _S(sid),
                                    _S(peer_sid),
                                    {
                                        "semantic": sim,
                                        "entity": ent_j,
                                        "overall": overall,
                                    },
                                )
                            ],
                            source="embedding_link_ranker",
                        )
                        stats["merges_enqueued"] += int(n or 0)
                        continue

                    if peer_dk == domain_key:
                        dedupe = storyline_pair_dedupe_key(domain_key, sid, peer_sid).replace(
                            "merge|", "associate|", 1
                        )
                        pid = upsert_graph_connection_proposal(
                            dedupe_key=dedupe,
                            proposal_kind="associate",
                            domain_key=domain_key,
                            confidence=overall,
                            source="embedding_link_ranker",
                            endpoints={
                                "domain_key": domain_key,
                                "storyline_ids": [sid, peer_sid],
                            },
                            evidence=evidence,
                            subject_summary=f"embedding associate storylines {sid}<->{peer_sid}",
                            inference_stage=_candidate_stage,
                        )
                        if pid:
                            stats["proposals"] += 1
                    else:
                        # Cross-domain: associate via shared article entities if any
                        try:
                            with conn.cursor() as cur:
                                cur.execute(
                                    f"""
                                    SELECT DISTINCT ae.canonical_entity_id
                                    FROM {schema}.article_entities ae
                                    JOIN {schema}.storyline_articles sa
                                      ON sa.article_id = ae.article_id
                                    WHERE sa.storyline_id = %s
                                      AND ae.canonical_entity_id IS NOT NULL
                                    LIMIT 30
                                    """,
                                    (sid,),
                                )
                                local_c = {int(r[0]) for r in cur.fetchall()}
                                cur.execute(
                                    f"""
                                    SELECT DISTINCT ae.canonical_entity_id
                                    FROM {peer_schema}.article_entities ae
                                    JOIN {peer_schema}.storyline_articles sa
                                      ON sa.article_id = ae.article_id
                                    WHERE sa.storyline_id = %s
                                      AND ae.canonical_entity_id IS NOT NULL
                                    LIMIT 30
                                    """,
                                    (peer_sid,),
                                )
                                peer_c = {int(r[0]) for r in cur.fetchall()}
                            shared = sorted(local_c & peer_c)[:3]
                        except Exception:
                            shared = []
                        if not shared:
                            # Still propose storyline-level cross associate via left/right
                            lo_dk, hi_dk = (
                                (domain_key, peer_dk)
                                if domain_key <= peer_dk
                                else (peer_dk, domain_key)
                            )
                            dedupe = (
                                f"associate|storyline_xd|{lo_dk}|{hi_dk}|"
                                f"{min(sid, peer_sid)}|{max(sid, peer_sid)}"
                            )
                            xd_ev = build_edge_evidence(
                                phase="embedding_link_candidates",
                                method="cosine_chunk",
                                score_parts={
                                    "semantic": sim,
                                    "entity": ent_j,
                                    "overall": overall,
                                },
                                anchors={"article_ids": [art_id]},
                            )
                            pid = upsert_graph_connection_proposal(
                                dedupe_key=dedupe,
                                proposal_kind="associate",
                                domain_key=domain_key,
                                confidence=overall,
                                source="embedding_link_ranker",
                                endpoints={
                                    "left": {
                                        "domain_key": domain_key,
                                        "kind": "storyline",
                                        "id": sid,
                                    },
                                    "right": {
                                        "domain_key": peer_dk,
                                        "kind": "storyline",
                                        "id": peer_sid,
                                    },
                                },
                                evidence=xd_ev,
                                subject_summary=(
                                    f"cross-domain storyline {domain_key}:{sid}"
                                    f"↔{peer_dk}:{peer_sid}"
                                ),
                                inference_stage=_candidate_stage,
                            )
                            if pid:
                                stats["proposals"] += 1
                            continue
                        for cid in shared:
                            lo_dk, hi_dk = (
                                (domain_key, peer_dk)
                                if domain_key <= peer_dk
                                else (peer_dk, domain_key)
                            )
                            dedupe = f"cross_domain|{lo_dk}|{hi_dk}|canonical|{cid}"
                            conf = max(0.58, overall)
                            xd_ev = build_edge_evidence(
                                phase="embedding_link_candidates",
                                method="cosine_chunk",
                                score_parts={
                                    "semantic": sim,
                                    "entity": ent_j,
                                    "overall": conf,
                                },
                                anchors={
                                    "article_ids": [art_id],
                                    "canonical_ids": [cid],
                                },
                            )
                            pid = upsert_graph_connection_proposal(
                                dedupe_key=dedupe,
                                proposal_kind="associate",
                                domain_key=domain_key,
                                confidence=conf,
                                source="embedding_link_ranker",
                                endpoints={
                                    "left": {
                                        "domain_key": domain_key,
                                        "kind": "entity",
                                        "id": cid,
                                    },
                                    "right": {
                                        "domain_key": peer_dk,
                                        "kind": "entity",
                                        "id": cid,
                                    },
                                    "canonical_ids": [cid],
                                },
                                evidence=xd_ev,
                                subject_summary=(
                                    f"embedding cross-domain {domain_key}↔{peer_dk} "
                                    f"canon={cid}"
                                ),
                                inference_stage=_candidate_stage,
                            )
                            if pid:
                                stats["proposals"] += 1

        try:
            conn.commit()
        except Exception:
            pass
    except Exception as e:
        logger.exception("run_embedding_link_candidates_for_domain: %s", e)
        stats["errors"] += 1
        stats["error"] = str(e)[:300]
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


def run_embedding_link_candidates_all_domains(
    *, limit_per_domain: int | None = None
) -> dict[str, Any]:
    by_domain = {}
    totals = {"proposals": 0, "merges_enqueued": 0, "scanned": 0, "errors": 0}
    for dk in get_pipeline_active_domain_keys():
        res = run_embedding_link_candidates_for_domain(dk, limit=limit_per_domain)
        by_domain[dk] = res
        for k in totals:
            totals[k] += int(res.get(k, 0) or 0)
    return {"by_domain": by_domain, "totals": totals}


def run_random_collision_sample(
    *,
    domain_key: str | None = None,
    pairs: int | None = None,
) -> dict[str, Any]:
    """
    Epsilon-style exploratory collisions: random active storyline pairs → hypothesized associates.
    Never auto-establishes; always inference_stage=hypothesized.
    """
    from config.runtime import env_int
    from services.domain_synthesis_config import get_domain_synthesis_config
    from services.graph_connection_queue_service import (
        storyline_pair_dedupe_key,
        upsert_graph_connection_proposal,
    )
    from shared.connection_inference import INFERENCE_HYPOTHESIZED
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from shared.graph_edge_evidence import build_edge_evidence

    n_pairs = max(1, min(50, pairs if pairs is not None else env_int("COLLISION_SAMPLING_PAIRS", 8)))
    domains = [domain_key] if domain_key else list(get_pipeline_active_domain_keys())
    stats: dict[str, Any] = {"proposals": 0, "domains": {}, "errors": 0}
    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db"}
    try:
        import random

        with conn.cursor() as cur:
            for dk in domains:
                schema = resolve_domain_schema(dk)
                cfg = get_domain_synthesis_config(dk)
                # Chemistry kinds get more random stirs
                local_pairs = n_pairs if cfg.is_chemistry_kind() else max(1, n_pairs // 2)
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE status = 'active' AND merged_into_id IS NULL
                    ORDER BY random()
                    LIMIT %s
                    """,
                    (max(4, local_pairs * 3),),
                )
                ids = [int(r[0]) for r in cur.fetchall()]
                if len(ids) < 2:
                    stats["domains"][dk] = {"proposals": 0, "skipped": "too_few"}
                    continue
                made = 0
                attempts = 0
                while made < local_pairs and attempts < local_pairs * 5:
                    attempts += 1
                    a, b = random.sample(ids, 2)
                    if a > b:
                        a, b = b, a
                    dedupe = storyline_pair_dedupe_key(dk, a, b).replace("merge|", "associate|", 1)
                    evidence = build_edge_evidence(
                        phase="collision_sampling",
                        method="random_pair",
                        score_parts={"overall": 0.35},
                        anchors={"storyline_ids": [a, b]},
                    )
                    pid = upsert_graph_connection_proposal(
                        dedupe_key=dedupe + "|explore",
                        proposal_kind="associate",
                        domain_key=dk,
                        confidence=0.35,
                        source="collision_sampling",
                        endpoints={"domain_key": dk, "storyline_ids": [a, b]},
                        evidence=evidence,
                        subject_summary=f"exploratory collision {a}<->{b}",
                        inference_stage=INFERENCE_HYPOTHESIZED,
                        min_confidence_for_auto=0.99,
                    )
                    if pid:
                        made += 1
                        stats["proposals"] += 1
                stats["domains"][dk] = {"proposals": made}
    except Exception as e:
        logger.warning("run_random_collision_sample: %s", e)
        stats["errors"] += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return stats

