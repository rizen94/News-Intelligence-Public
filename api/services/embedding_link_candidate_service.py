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
from shared.domain_processing_mode import filter_domains_for_phase
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
    return max(1, env_int("EMBEDDING_LINK_MAX_STORYLINES", 40))


# Persisted on storylines.metadata so re-scans only happen after material change.
_EMBEDDING_LINK_SCANNED_AT_KEY = "embedding_link_scanned_at"


def embedding_link_storyline_base_sql(alias: str = "s") -> str:
    """Active mega eligible for embedding-link consideration (drain + backlog)."""
    return f"""
                {alias}.status = 'active'
                  AND {alias}.merged_into_id IS NULL
                  AND COALESCE({alias}.article_count, 0) >= 3
""".rstrip()


def embedding_link_storyline_due_sql(alias: str = "s") -> str:
    """
    Due for a scan: never scanned, or storyline updated since last scan.

    Root fix for thrash — without this the drain re-walks the same updated_at head forever.
    """
    key = _EMBEDDING_LINK_SCANNED_AT_KEY
    return f"""
                (
                  {alias}.metadata->>'{key}' IS NULL
                  OR COALESCE({alias}.updated_at, {alias}.created_at)
                       > ({alias}.metadata->>'{key}')::timestamptz
                )
""".rstrip()


def count_embedding_link_candidates_due(*, domain_key: str | None = None) -> int:
    """Storylines the embedding-link drain will select (due SSOT)."""
    if not embedding_link_candidates_enabled():
        return 0
    domains = [domain_key] if domain_key else filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "embedding_link_candidates"
    )
    total = 0
    conn = get_db_connection()
    if not conn:
        return 0
    base = embedding_link_storyline_base_sql("s")
    due = embedding_link_storyline_due_sql("s")
    try:
        with conn.cursor() as cur:
            for dk in domains:
                if not dk:
                    continue
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.storylines s
                    WHERE {base}
                      AND {due}
                    """
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("count_embedding_link_candidates_due: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _mark_embedding_link_scanned(cur, schema: str, storyline_id: int) -> None:
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET metadata = COALESCE(metadata, '{{}}'::jsonb)
            || jsonb_build_object(%s, NOW())
        WHERE id = %s
        """,
        (_EMBEDDING_LINK_SCANNED_AT_KEY, int(storyline_id)),
    )


def _neighbors_per_query() -> int:
    return max(3, env_int("EMBEDDING_LINK_NEIGHBORS", 8))


# Re-export: canonical implementation lives in shared.link_scoring (v12).
from shared.link_scoring import (  # noqa: E402
    blend_link_score,
    causal_boost_for_storyline_pair,
)

_CAUSAL_BOOST_CAP = 0.06


def days_apart(a, b) -> float | None:
    """Absolute day gap between two date/datetime values; None if either missing."""
    if a is None or b is None:
        return None
    try:
        from datetime import date, datetime

        def _as_date(x):
            if isinstance(x, datetime):
                return x.date()
            if isinstance(x, date):
                return x
            return None

        da, db = _as_date(a), _as_date(b)
        if da is None or db is None:
            return None
        return abs((da - db).days)
    except Exception:
        return None


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


def _sei_canonical_ids(cur, schema: str, storyline_id: int, limit: int = 40) -> set[int]:
    """Canonical entity IDs from SEI when present, else article_entities via membership."""
    try:
        cur.execute(
            f"""
            SELECT DISTINCT canonical_entity_id
            FROM {schema}.story_entity_index
            WHERE storyline_id = %s AND canonical_entity_id IS NOT NULL
            LIMIT %s
            """,
            (storyline_id, limit),
        )
        ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
        if ids:
            return ids
    except Exception:
        pass
    try:
        cur.execute(
            f"""
            SELECT DISTINCT ae.canonical_entity_id
            FROM {schema}.article_entities ae
            JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
            WHERE sa.storyline_id = %s
              AND ae.canonical_entity_id IS NOT NULL
            LIMIT %s
            """,
            (storyline_id, limit),
        )
        return {int(r[0]) for r in cur.fetchall() if r[0] is not None}
    except Exception:
        return set()


def _storyline_anchor_date(cur, schema: str, storyline_id: int):
    """Best temporal anchor: last chrono event or material_updated_at / updated_at."""
    cur.execute(
        """
        SELECT MAX(actual_event_date)
        FROM public.chronological_events
        WHERE storyline_id = %s::text AND canonical_event_id IS NULL
        """,
        (f"{schema}:{storyline_id}" if schema and ":" not in str(storyline_id) else str(storyline_id),),
    )
    # Try both schema:id and bare id forms
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    cur.execute(
        """
        SELECT MAX(actual_event_date)
        FROM public.chronological_events
        WHERE storyline_id IN (%s, %s) AND canonical_event_id IS NULL
        """,
        (str(storyline_id), f"{schema}:{storyline_id}"),
    )
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    try:
        cur.execute(
            f"""
            SELECT COALESCE(material_updated_at, updated_at, created_at)
            FROM {schema}.storylines WHERE id = %s
            """,
            (storyline_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _sei_entities_bulk(
    cur, schema: str, storyline_ids: list[int], limit: int = 40
) -> dict[int, set[str]]:
    """Batch SEI entity names for many storylines (one query)."""
    if not storyline_ids:
        return {}
    cur.execute(
        f"""
        SELECT storyline_id, entity_name
        FROM {schema}.story_entity_index
        WHERE storyline_id = ANY(%s) AND entity_name IS NOT NULL
        ORDER BY storyline_id,
                 COALESCE(is_core_entity, false) DESC,
                 mention_count DESC NULLS LAST
        """,
        (list(storyline_ids),),
    )
    out: dict[int, set[str]] = {int(sid): set() for sid in storyline_ids}
    counts: dict[int, int] = {int(sid): 0 for sid in storyline_ids}
    for sid, name in cur.fetchall():
        sid_i = int(sid)
        if counts.get(sid_i, 0) >= limit:
            continue
        if name:
            out.setdefault(sid_i, set()).add(str(name))
            counts[sid_i] = counts.get(sid_i, 0) + 1
    return out


def _storylines_for_articles_bulk(
    cur, schema: str, article_ids: list[int], *, per_article: int = 5
) -> dict[int, list[int]]:
    if not article_ids:
        return {}
    cur.execute(
        f"""
        SELECT article_id, storyline_id
        FROM {schema}.storyline_articles
        WHERE article_id = ANY(%s)
        """,
        (list(article_ids),),
    )
    out: dict[int, list[int]] = {int(a): [] for a in article_ids}
    for art_id, sid in cur.fetchall():
        aid = int(art_id)
        bucket = out.setdefault(aid, [])
        if len(bucket) < per_article:
            bucket.append(int(sid))
    return out


def _storyline_query_texts_bulk(
    cur, schema: str, storyline_ids: list[int]
) -> dict[int, str]:
    if not storyline_ids:
        return {}
    cur.execute(
        f"""
        SELECT id, title,
               COALESCE(canonical_narrative, master_summary, summary, description, '')
        FROM {schema}.storylines
        WHERE id = ANY(%s) AND merged_into_id IS NULL
        """,
        (list(storyline_ids),),
    )
    out: dict[int, str] = {}
    for sid, title, body in cur.fetchall():
        text = f"{title or ''}\n{body or ''}".strip()
        if text:
            out[int(sid)] = text[:2500]
    return out


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
            base = embedding_link_storyline_base_sql("s")
            due = embedding_link_storyline_due_sql("s")
            cur.execute(
                f"""
                SELECT id FROM {schema}.storylines s
                WHERE {base}
                  AND {due}
                ORDER BY updated_at DESC NULLS LAST, article_count DESC NULLS LAST
                LIMIT %s
                """,
                (lim,),
            )
            storyline_ids = [int(r[0]) for r in cur.fetchall()]

        with conn.cursor() as cur:
            qtexts = _storyline_query_texts_bulk(cur, schema, storyline_ids)
            sei_by_sid = _sei_entities_bulk(cur, schema, storyline_ids)

        for sid in storyline_ids:
            stats["scanned"] += 1
            qtext = qtexts.get(sid)
            if not qtext:
                stats["skipped"] += 1
                try:
                    with conn.cursor() as cur:
                        _mark_embedding_link_scanned(cur, schema, sid)
                except Exception:
                    pass
                continue
            core_ents = sei_by_sid.get(sid) or set()

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

            arts_by_schema: dict[str, list[int]] = {}
            hit_meta: list[tuple] = []
            for hit in hits:
                sim = float(hit.get("similarity") or 0.0)
                if sim < min_cos:
                    continue
                peer_dk = str(hit.get("domain_key") or domain_key)
                peer_schema = resolve_domain_schema(peer_dk)
                art_id = _article_id_from_chunk(hit)
                if art_id is None:
                    continue
                arts_by_schema.setdefault(peer_schema, []).append(art_id)
                hit_meta.append((hit, sim, peer_dk, art_id))

            peers_by_schema_art: dict[str, dict[int, list[int]]] = {}
            peer_sei: dict[str, dict[int, set[str]]] = {}
            try:
                with conn.cursor() as cur:
                    peer_sids_by_schema: dict[str, list[int]] = {}
                    for pschema, aids in arts_by_schema.items():
                        peers_by_schema_art[pschema] = _storylines_for_articles_bulk(
                            cur, pschema, aids
                        )
                        for sids in peers_by_schema_art[pschema].values():
                            peer_sids_by_schema.setdefault(pschema, []).extend(sids)
                    for pschema, sids in peer_sids_by_schema.items():
                        uniq = list({int(x) for x in sids})
                        peer_sei[pschema] = _sei_entities_bulk(cur, pschema, uniq)
            except Exception as e:
                logger.debug("embedding_link peer prefetch: %s", e)

            seen_peers: set[tuple[str, int]] = set()
            for hit, sim, peer_dk, art_id in hit_meta:
                peer_schema = resolve_domain_schema(peer_dk)
                peers = (peers_by_schema_art.get(peer_schema) or {}).get(art_id) or []
                for peer_sid in peers:
                    if peer_dk == domain_key and peer_sid == sid:
                        continue
                    key = (peer_dk, peer_sid)
                    if key in seen_peers:
                        continue
                    seen_peers.add(key)

                    ent_j = 0.0
                    can_j = 0.0
                    temp_p = 1.0
                    peer_ents = (peer_sei.get(peer_schema) or {}).get(peer_sid) or set()
                    if core_ents and peer_ents:
                        inter = len(core_ents & peer_ents)
                        union = len(core_ents | peer_ents)
                        ent_j = float(inter) / float(union) if union else 0.0
                    try:
                        with conn.cursor() as cur:
                            if peer_dk == domain_key and _active_link_exists(
                                cur, domain_key=domain_key, a=sid, b=peer_sid
                            ):
                                stats["skipped"] += 1
                                continue
                            local_c = _sei_canonical_ids(cur, schema, sid)
                            peer_c = _sei_canonical_ids(cur, peer_schema, peer_sid)
                            if local_c and peer_c:
                                inter_c = len(local_c & peer_c)
                                union_c = len(local_c | peer_c)
                                can_j = float(inter_c) / float(union_c) if union_c else 0.0
                            try:
                                from services.domain_synthesis_config import (
                                    get_domain_synthesis_config,
                                    temporal_proximity_score,
                                )

                                d1 = _storyline_anchor_date(cur, schema, sid)
                                d2 = _storyline_anchor_date(cur, peer_schema, peer_sid)
                                gap = days_apart(d1, d2)
                                half = get_domain_synthesis_config(
                                    domain_key
                                ).link_score_profile.temporal_half_life_days
                                temp_p = temporal_proximity_score(gap, half_life_days=half)
                            except Exception:
                                temp_p = 1.0
                    except Exception:
                        pass

                    causal_b = causal_boost_for_storyline_pair(
                        domain_key, int(sid), int(peer_sid)
                    )
                    overall = blend_link_score(
                        semantic=sim,
                        entity_jaccard=ent_j,
                        canonical_jaccard=can_j,
                        temporal_proximity=temp_p,
                        domain_key=domain_key,
                        causal_boost=causal_b,
                    )
                    evidence = build_edge_evidence(
                        phase="embedding_link_candidates",
                        method="cosine_chunk",
                        score_parts={
                            "semantic": sim,
                            "entity": ent_j,
                            "canonical": can_j,
                            "temporal": temp_p,
                            "causal": causal_b,
                            "overall": overall,
                        },
                        anchors={
                            "article_ids": [art_id],
                            "chunk_ids": [
                                f"{hit.get('source_type')}:{hit.get('source_id')}:{hit.get('chunk_index')}"
                            ],
                        },
                        extra={
                            "link_role_intent": "associated_similarity",
                            "link_mode": "cosine_peer",
                            "membership_forbidden": True,
                        },
                    )

                    if peer_dk == domain_key and overall >= merge_band:
                        try:
                            from services.domain_synthesis_config import (
                                get_domain_synthesis_config,
                            )

                            if not get_domain_synthesis_config(
                                domain_key
                            ).link_score_profile.allow_storyline_merge:
                                # Chemistry / matter_docket: never enqueue merges from cosine
                                overall = min(overall, merge_band - 0.01)
                                stats.setdefault("merges_blocked_no_merge_domain", 0)
                                stats["merges_blocked_no_merge_domain"] += 1
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
                            stats.setdefault("proposal_only_cosine", 0)
                            stats["proposal_only_cosine"] += 1
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
                with conn.cursor() as cur:
                    _mark_embedding_link_scanned(cur, schema, sid)
            except Exception as mark_e:
                logger.debug("embedding_link mark scanned sid=%s: %s", sid, mark_e)

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
    for dk in filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "embedding_link_candidates"
    ):
        res = run_embedding_link_candidates_for_domain(dk, limit=limit_per_domain)
        by_domain[dk] = res
        for k in totals:
            totals[k] += int(res.get(k, 0) or 0)
    return {"by_domain": by_domain, "totals": totals}


def _collision_pair_prior(
    *,
    centroid_cos: float,
    entity_jaccard: float,
    temporal_proximity: float,
    chemistry_kind: bool = False,
) -> float:
    """Sampling weight for collision pairs.

    Linear narrative kinds: 0.5*centroid + 0.3*entity + 0.2*temporal.
    Chemistry kinds (evidence_thread / research_topic / matter_docket): boost
    entity overlap and de-emphasize temporal chapter proximity — these domains
    are not chronologically linear.
    """
    if chemistry_kind:
        return (
            0.35 * max(0.0, float(centroid_cos))
            + 0.55 * max(0.0, float(entity_jaccard))
            + 0.10 * max(0.0, float(temporal_proximity))
        )
    return (
        0.5 * max(0.0, float(centroid_cos))
        + 0.3 * max(0.0, float(entity_jaccard))
        + 0.2 * max(0.0, float(temporal_proximity))
    )


def collision_sampling_pool_sql(alias: str = "s") -> str:
    """Active storylines eligible for the collision sampler pool (drain + backlog)."""
    return f"""
                {alias}.status = 'active'
                  AND {alias}.merged_into_id IS NULL
""".rstrip()


def count_collision_sampling_actionable() -> int:
    """
    Domains with a samplable pool (≥2 active storylines).

    Collision is generative (not a depleting inventory). Hypothesized proposals
    belong to graph_connection_distillation — counting them here caused phantom
    backlog while the drain only samples pairs.
    """
    from shared.chemistry_beaker import collision_sampling_enabled

    if not collision_sampling_enabled():
        return 0
    domains = filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "collision_sampling"
    )
    actionable = 0
    conn = get_db_connection()
    if not conn:
        return 0
    pool = collision_sampling_pool_sql("s")
    try:
        with conn.cursor() as cur:
            for dk in domains:
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.storylines s
                    WHERE {pool}
                    """
                )
                n = int(cur.fetchone()[0] or 0)
                if n >= 2:
                    actionable += 1
        return actionable
    except Exception as e:
        logger.debug("count_collision_sampling_actionable: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_random_collision_sample(
    *,
    domain_key: str | None = None,
    pairs: int | None = None,
) -> dict[str, Any]:
    """
    Guided + epsilon collision sampling → hypothesized associates.

    Prior-biased pairs use centroid cosine, entity Jaccard, and temporal proximity.
    COLLISION_EPSILON_RANDOM (default 0.2) keeps pure random exploration.
    Never auto-establishes; always inference_stage=hypothesized.
    """
    from config.runtime import env_float, env_int
    from services.domain_synthesis_config import (
        get_domain_synthesis_config,
        temporal_proximity_score,
    )
    from services.graph_connection_queue_service import (
        build_edge_evidence,
        storyline_pair_dedupe_key,
        upsert_graph_connection_proposal,
    )
    from services.storyline_centroid import centroid_cosine, get_storyline_centroid
    from shared.connection_inference import INFERENCE_HYPOTHESIZED
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    n_pairs = max(1, min(50, pairs if pairs is not None else env_int("COLLISION_SAMPLING_PAIRS", 8)))
    try:
        epsilon = float(env_float("COLLISION_EPSILON_RANDOM", 0.2))
    except Exception:
        epsilon = 0.2
    epsilon = max(0.0, min(0.9, epsilon))

    domains = [domain_key] if domain_key else filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "collision_sampling"
    )
    stats: dict[str, Any] = {
        "proposals": 0,
        "guided": 0,
        "random": 0,
        "domains": {},
        "errors": 0,
    }
    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db"}
    try:
        import random

        with conn.cursor() as cur:
            for dk in domains:
                schema = resolve_domain_schema(dk)
                cfg = get_domain_synthesis_config(dk)
                half = float(cfg.link_score_profile.temporal_half_life_days)
                local_pairs = n_pairs if cfg.is_chemistry_kind() else max(1, n_pairs // 2)
                pool_n = max(8, local_pairs * 5)
                pool_where = collision_sampling_pool_sql("s")
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines s
                    WHERE {pool_where}
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (pool_n,),
                )
                ids = [int(r[0]) for r in cur.fetchall()]
                if len(ids) < 2:
                    stats["domains"][dk] = {"proposals": 0, "skipped": "too_few"}
                    continue

                # Build feature cache
                centroids: dict[int, list[float] | None] = {}
                ents: dict[int, set[str]] = {}
                dates: dict[int, Any] = {}
                for sid in ids:
                    centroids[sid] = get_storyline_centroid(schema, sid, conn=conn)
                    ents[sid] = _sei_entities(cur, schema, sid, limit=30)
                    dates[sid] = _storyline_anchor_date(cur, schema, sid)

                # All unordered pairs with priors
                weighted: list[tuple[float, int, int, dict[str, float]]] = []
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        a, b = ids[i], ids[j]
                        c_cos = centroid_cosine(centroids.get(a), centroids.get(b))
                        ea, eb = ents.get(a) or set(), ents.get(b) or set()
                        ent_j = 0.0
                        if ea and eb:
                            union = len(ea | eb)
                            ent_j = float(len(ea & eb)) / float(union) if union else 0.0
                        gap = days_apart(dates.get(a), dates.get(b))
                        temp_p = temporal_proximity_score(gap, half_life_days=half)
                        prior = _collision_pair_prior(
                            centroid_cos=c_cos,
                            entity_jaccard=ent_j,
                            temporal_proximity=temp_p,
                            chemistry_kind=cfg.is_chemistry_kind(),
                        )
                        parts = {
                            "centroid": c_cos,
                            "entity": ent_j,
                            "temporal": temp_p,
                            "prior": prior,
                        }
                        weighted.append((max(prior, 1e-6), a, b, parts))

                n_random = max(1, int(round(local_pairs * epsilon))) if local_pairs > 1 else 0
                n_guided = max(0, local_pairs - n_random)
                made = 0
                guided_n = 0
                random_n = 0

                def _emit(a: int, b: int, parts: dict[str, float], *, method: str) -> bool:
                    nonlocal made, guided_n, random_n
                    if a > b:
                        a, b = b, a
                    overall = blend_link_score(
                        semantic=float(parts.get("centroid") or 0.0),
                        entity_jaccard=float(parts.get("entity") or 0.0),
                        temporal_proximity=float(parts.get("temporal") or 1.0),
                        domain_key=dk,
                        causal_boost=causal_boost_for_storyline_pair(dk, int(a), int(b)),
                    )
                    # Keep exploratory confidence modest
                    conf = max(0.25, min(0.55, 0.30 + 0.25 * overall))
                    dedupe = storyline_pair_dedupe_key(dk, a, b).replace("merge|", "associate|", 1)
                    evidence = build_edge_evidence(
                        phase="collision_sampling",
                        method=method,
                        score_parts={
                            "semantic": parts.get("centroid", 0.0),
                            "entity": parts.get("entity", 0.0),
                            "temporal": parts.get("temporal", 1.0),
                            "prior": parts.get("prior", 0.0),
                            "overall": overall,
                        },
                        anchors={"storyline_ids": [a, b]},
                    )
                    pid = upsert_graph_connection_proposal(
                        dedupe_key=dedupe + "|explore",
                        proposal_kind="associate",
                        domain_key=dk,
                        confidence=conf,
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
                        if method == "guided_prior":
                            guided_n += 1
                            stats["guided"] += 1
                        else:
                            random_n += 1
                            stats["random"] += 1
                        return True
                    return False

                # Guided: weighted sample without replacement
                pool = list(weighted)
                for _ in range(n_guided):
                    if not pool:
                        break
                    weights = [w[0] for w in pool]
                    total_w = sum(weights)
                    if total_w <= 0:
                        break
                    pick = random.choices(range(len(pool)), weights=weights, k=1)[0]
                    _prior, a, b, parts = pool.pop(pick)
                    _emit(a, b, parts, method="guided_prior")

                # Epsilon random from id pool
                attempts = 0
                while random_n < n_random and attempts < n_random * 8:
                    attempts += 1
                    a, b = random.sample(ids, 2)
                    # Look up parts if available
                    parts = {"centroid": 0.0, "entity": 0.0, "temporal": 1.0, "prior": 0.0}
                    for w, x, y, p in weighted:
                        if {x, y} == {a, b}:
                            parts = p
                            break
                    _emit(a, b, parts, method="random_pair")

                # Fill remaining with guided if random undershot
                while made < local_pairs and pool:
                    _prior, a, b, parts = pool.pop(0)
                    if not _emit(a, b, parts, method="guided_prior"):
                        continue

                stats["domains"][dk] = {
                    "proposals": made,
                    "guided": guided_n,
                    "random": random_n,
                }
    except Exception as e:
        logger.warning("run_random_collision_sample: %s", e)
        stats["errors"] += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return stats

