"""
Event Deduplication Service for News Intelligence v5.0 (Phase 2)

Recognises when multiple articles from different sources describe the same
real-world event using a three-tier matching strategy:

1. Fingerprint matching  (fast, exact)
2. Semantic similarity    (medium, fuzzy -- pgvector cosine distance)
3. Entity-temporal overlap (slow, precise)

When duplicates are found the system designates the earliest-reported version
as canonical and merges metadata from subsequent sources. ``source_count`` and
``last_corroborated_at`` on the canonical row preserve multi-source tracking.

Narrative Phase 1 extends this with an explicit coreference cluster layer:
``event_cluster_id``, ``intelligence.event_coreference_links`` (hard + soft),
and union-find chain collapse after each batch.

Tune aggressiveness with ``EVENT_DEDUP_*`` env vars (see ``configs/env.example``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from config.runtime import env_str

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def _dedup_env_float(name: str, default: float) -> float:
    try:
        return float(env_str(name, str(default)))
    except (TypeError, ValueError):
        return default


def _dedup_env_int(name: str, default: int) -> int:
    raw = env_str(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _dedup_similarity_threshold() -> float:
    """Lower → more aggressive tier-2 merges (cosine). Canonical still accumulates source_count."""
    v = _dedup_env_float("EVENT_DEDUP_SIMILARITY_THRESHOLD", 0.85)
    return max(0.5, min(v, 0.999))


def _dedup_soft_min() -> float:
    """Lower bound of soft band for tier-2 (below hard threshold)."""
    hard = _dedup_similarity_threshold()
    v = _dedup_env_float("EVENT_DEDUP_SOFT_MIN", max(0.70, hard - 0.12))
    return max(0.5, min(v, hard - 0.001))


def _dedup_entity_overlap_min() -> int:
    """Lower → more aggressive tier-3 (entity overlap)."""
    v = _dedup_env_int("EVENT_DEDUP_ENTITY_OVERLAP_MIN", 2)
    return max(1, min(v, 20))


def _dedup_embedding_top_k() -> int:
    v = _dedup_env_int("EVENT_DEDUP_EMBEDDING_TOP_K", 10)
    return max(2, min(v, 50))


def _dedup_embedding_margin() -> float:
    v = _dedup_env_float("EVENT_DEDUP_EMBEDDING_MARGIN", 0.1)
    return max(0.0, min(v, 0.5))


def _dedup_skip_margin_if_sim_ge() -> float:
    v = _dedup_env_float("EVENT_DEDUP_EMBEDDING_SKIP_MARGIN_IF_SIM_GE", 0.95)
    return max(0.8, min(v, 1.0))


def _dedup_borderline_sim() -> float:
    v = _dedup_env_float("EVENT_DEDUP_BORDERLINE_SIM", 0.9)
    return max(0.5, min(v, 0.999))


def _dedup_borderline_max_seconds() -> float:
    v = _dedup_env_float("EVENT_DEDUP_BORDERLINE_MAX_SECONDS_APART", 86400.0)
    return max(60.0, min(v, 86400.0 * 30))


async def _get_embedding(text: str) -> list[float] | None:
    """Get a 768-d embedding from Ollama's nomic-embed-text model."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, dict):
                    return None
                return data.get("embedding")
        except Exception as e:
            logger.error(f"Embedding request failed: {e}")
    return None


class EventDeduplicationService:
    """Cross-source event deduplication + coreference engine."""

    def __init__(self, conn):
        self.conn = conn
        self._chronological_has_embedding: bool | None = None
        self._has_cluster_col: bool | None = None
        self._has_coref_table: bool | None = None

    def _chronological_events_has_embedding(self) -> bool:
        if self._chronological_has_embedding is not None:
            return self._chronological_has_embedding
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns c
                    WHERE c.table_schema = 'public'
                      AND c.table_name = 'chronological_events'
                      AND c.column_name = 'embedding'
                )
                """
            )
            row = cursor.fetchone()
            self._chronological_has_embedding = bool(row and row[0])
        finally:
            cursor.close()
        return self._chronological_has_embedding

    def _has_event_cluster_id(self) -> bool:
        if self._has_cluster_col is not None:
            return self._has_cluster_col
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns c
                    WHERE c.table_schema = 'public'
                      AND c.table_name = 'chronological_events'
                      AND c.column_name = 'event_cluster_id'
                )
                """
            )
            row = cursor.fetchone()
            self._has_cluster_col = bool(row and row[0])
        finally:
            cursor.close()
        return self._has_cluster_col

    def _has_coreference_links_table(self) -> bool:
        if self._has_coref_table is not None:
            return self._has_coref_table
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT to_regclass('intelligence.event_coreference_links')")
            row = cursor.fetchone()
            self._has_coref_table = bool(row and row[0])
        finally:
            cursor.close()
        return self._has_coref_table

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def deduplicate_event(self, event_id: int) -> int | None:
        """
        Check if *event_id* is a duplicate of an existing canonical event.

        Returns the canonical_event_id if a hard match is found, else None.
        Soft-band matches write coreference links without setting canonical_event_id.
        """
        result = await self._coreference_event(event_id)
        if result and result.get("hard"):
            return int(result["canonical_id"])
        return None

    async def _coreference_event(self, event_id: int) -> dict[str, Any] | None:
        """Run tiers 1→3; return match dict or None."""
        has_emb = self._chronological_events_has_embedding()
        cursor = self.conn.cursor()
        if has_emb:
            cursor.execute(
                """
                SELECT id, event_fingerprint, title, description, event_type,
                       actual_event_date, date_precision, location, key_actors,
                       entities, embedding, storyline_id
                FROM chronological_events
                WHERE id = %s
            """,
                (event_id,),
            )
        else:
            cursor.execute(
                """
                SELECT id, event_fingerprint, title, description, event_type,
                       actual_event_date, date_precision, location, key_actors,
                       entities, storyline_id
                FROM chronological_events
                WHERE id = %s
            """,
                (event_id,),
            )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None

        if has_emb:
            (
                eid,
                fingerprint,
                title,
                desc,
                etype,
                edate,
                precision,
                loc,
                actors_json,
                entities_json,
                embedding,
                storyline_id,
            ) = row
        else:
            (
                eid,
                fingerprint,
                title,
                desc,
                etype,
                edate,
                precision,
                loc,
                actors_json,
                entities_json,
                storyline_id,
            ) = row
            embedding = None

        key_actors = self._parse_json(actors_json)
        entities = self._parse_json(entities_json)

        # --- Tier 1: fingerprint ----------------------------------------
        hit = self._score_fingerprint(eid, fingerprint)
        if hit:
            await self._merge(
                eid,
                hit["candidate_id"],
                match_tier=hit["match_tier"],
                score=hit.get("score"),
                evidence=hit.get("evidence"),
            )
            return {
                "hard": True,
                "canonical_id": hit["candidate_id"],
                "match_tier": hit["match_tier"],
            }

        # --- Tier 2: semantic similarity (pgvector) ----------------------
        soft_hit: dict[str, Any] | None = None
        if has_emb:
            if embedding is None:
                embed_text = f"{title}. {desc or ''}"
                vec = await _get_embedding(embed_text)
                if vec:
                    self._store_embedding(eid, vec)
                    embedding = vec

            if embedding is not None:
                hard, soft = self._score_embedding(eid, embedding, edate)
                if hard:
                    await self._merge(
                        eid,
                        hard["candidate_id"],
                        match_tier=hard["match_tier"],
                        score=hard.get("score"),
                        evidence=hard.get("evidence"),
                    )
                    return {
                        "hard": True,
                        "canonical_id": hard["candidate_id"],
                        "match_tier": hard["match_tier"],
                    }
                soft_hit = soft

        # --- Tier 3: entity + temporal overlap ---------------------------
        actor_names = (
            [a.get("name", "") for a in key_actors] if isinstance(key_actors, list) else []
        )
        entity_names = []
        if isinstance(entities, list):
            entity_names = [e.get("name", "") if isinstance(e, dict) else str(e) for e in entities]
        all_names = list(set(n.lower().strip() for n in actor_names + entity_names if n))

        hard, soft_ent = self._score_entities(eid, all_names, edate, precision)
        if hard:
            await self._merge(
                eid,
                hard["candidate_id"],
                match_tier=hard["match_tier"],
                score=hard.get("score"),
                evidence=hard.get("evidence"),
            )
            return {
                "hard": True,
                "canonical_id": hard["candidate_id"],
                "match_tier": hard["match_tier"],
            }

        # Prefer embedding soft over entity soft when both present
        soft = soft_hit or soft_ent
        if soft:
            await self._link_soft(
                eid,
                soft["candidate_id"],
                score=soft.get("score"),
                evidence=soft.get("evidence"),
            )
            return {
                "hard": False,
                "canonical_id": soft["candidate_id"],
                "match_tier": "soft",
            }

        return None

    # ------------------------------------------------------------------
    # Batch entry point
    # ------------------------------------------------------------------

    async def deduplicate_recent(self, limit: int = 50) -> dict[str, int]:
        """Deduplicate / coreference events that have not yet been hard-merged."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id FROM chronological_events
            WHERE canonical_event_id IS NULL
            ORDER BY extraction_timestamp DESC
            LIMIT %s
        """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()

        stats = {
            "checked": 0,
            "merged": 0,
            "hard_merges": 0,
            "soft_links": 0,
            "chains_collapsed": 0,
            "soft_pruned": 0,
        }
        for (eid,) in rows:
            stats["checked"] += 1
            result = await self._coreference_event(eid)
            if not result:
                continue
            if result.get("hard"):
                stats["merged"] += 1
                stats["hard_merges"] += 1
            else:
                stats["soft_links"] += 1

        collapsed = self._collapse_coref_chains()
        stats["chains_collapsed"] = collapsed
        pruned = self._prune_weak_soft_links()
        stats["soft_pruned"] = pruned
        return stats

    # ------------------------------------------------------------------
    # Scoring tiers (extracted for tests / soft band)
    # ------------------------------------------------------------------

    def _score_fingerprint(self, event_id: int, fingerprint: str) -> dict[str, Any] | None:
        if not fingerprint:
            return None
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id FROM chronological_events
            WHERE event_fingerprint = %s
              AND id != %s
              AND canonical_event_id IS NULL
            ORDER BY extraction_timestamp ASC
            LIMIT 1
        """,
            (fingerprint, event_id),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {
            "candidate_id": int(row[0]),
            "match_tier": "fingerprint",
            "score": 1.0,
            "evidence": {"tier": "fingerprint"},
        }

    def _score_embedding(
        self, event_id: int, embedding: list, event_date: datetime | None
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return (hard_hit, soft_hit)."""
        cursor = self.conn.cursor()
        try:
            sim_thr = _dedup_similarity_threshold()
            soft_min = _dedup_soft_min()
            top_k = _dedup_embedding_top_k()
            emb_margin = _dedup_embedding_margin()
            skip_margin_if_ge = _dedup_skip_margin_if_sim_ge()
            borderline_sim = _dedup_borderline_sim()
            borderline_sec = _dedup_borderline_max_seconds()
            temporal_on = env_str("EVENT_DEDUP_DISABLE_TEMPORAL_BORDERLINE", "").lower() not in (
                "1",
                "true",
                "yes",
            )

            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            cursor.execute(
                """
                SELECT id,
                       1 - (embedding <=> %s::vector) AS similarity,
                       actual_event_date,
                       extraction_timestamp
                FROM chronological_events
                WHERE id != %s
                  AND canonical_event_id IS NULL
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """,
                (vec_literal, event_id, vec_literal, top_k),
            )
            candidates = cursor.fetchall() or []
            if not candidates:
                return None, None

            best_id = int(candidates[0][0])
            best_sim = float(candidates[0][1] or 0.0)
            best_event_date = candidates[0][2]
            best_extraction_ts = candidates[0][3]

            if len(candidates) > 1:
                second_sim = float(candidates[1][1] or 0.0)
                margin = best_sim - second_sim
                if margin < emb_margin and best_sim < skip_margin_if_ge:
                    return None, None

            cand_time = best_event_date or best_extraction_ts
            dt_sec = self._seconds_between_event_times(event_date, cand_time)
            if temporal_on and (
                best_sim < borderline_sim
                and dt_sec is not None
                and dt_sec > borderline_sec
            ):
                return None, None

            evidence = {
                "tier": "embedding",
                "similarity": best_sim,
                "dt_seconds": dt_sec,
            }
            if best_sim >= sim_thr:
                return (
                    {
                        "candidate_id": best_id,
                        "match_tier": "embedding",
                        "score": best_sim,
                        "evidence": evidence,
                    },
                    None,
                )
            if soft_min <= best_sim < sim_thr:
                return (
                    None,
                    {
                        "candidate_id": best_id,
                        "match_tier": "soft",
                        "score": best_sim,
                        "evidence": evidence,
                    },
                )
            return None, None
        except Exception as e:
            logger.error(f"pgvector similarity query failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
        return None, None

    def _score_entities(
        self,
        event_id: int,
        entity_names: list[str],
        event_date: datetime | None,
        precision: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return (hard_hit, soft_hit) for entity-temporal overlap."""
        overlap_min = _dedup_entity_overlap_min()
        soft_overlap = max(1, overlap_min - 1)
        if len(entity_names) < soft_overlap:
            return None, None

        window = self._precision_window(precision)
        cursor = self.conn.cursor()
        try:
            if event_date and window:
                cursor.execute(
                    """
                    SELECT id, key_actors, entities
                    FROM chronological_events
                    WHERE id != %s
                      AND canonical_event_id IS NULL
                      AND actual_event_date BETWEEN %s AND %s
                """,
                    (event_id, event_date - window, event_date + window),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, key_actors, entities
                    FROM chronological_events
                    WHERE id != %s
                      AND canonical_event_id IS NULL
                """,
                    (event_id,),
                )

            best_hard: dict[str, Any] | None = None
            best_soft: dict[str, Any] | None = None
            best_hard_overlap = -1
            best_soft_overlap = -1

            for row in cursor.fetchall():
                cand_id, cand_actors_json, cand_entities_json = row
                cand_names = set()
                for j in (cand_actors_json, cand_entities_json):
                    parsed = self._parse_json(j)
                    if isinstance(parsed, list):
                        for item in parsed:
                            name = item.get("name", "") if isinstance(item, dict) else str(item)
                            if name:
                                cand_names.add(name.lower().strip())
                overlap = len(set(entity_names) & cand_names)
                evidence = {
                    "tier": "entity_temporal",
                    "overlap": overlap,
                    "overlap_min": overlap_min,
                }
                if overlap >= overlap_min and overlap > best_hard_overlap:
                    best_hard_overlap = overlap
                    best_hard = {
                        "candidate_id": int(cand_id),
                        "match_tier": "entity_temporal",
                        "score": float(overlap) / float(max(len(entity_names), 1)),
                        "evidence": evidence,
                    }
                elif (
                    overlap == soft_overlap
                    and overlap < overlap_min
                    and event_date
                    and window
                    and overlap > best_soft_overlap
                ):
                    best_soft_overlap = overlap
                    best_soft = {
                        "candidate_id": int(cand_id),
                        "match_tier": "soft",
                        "score": float(overlap) / float(max(len(entity_names), 1)),
                        "evidence": evidence,
                    }
            return best_hard, best_soft
        except Exception as e:
            logger.error(f"Entity-temporal match failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
        return None, None

    # ------------------------------------------------------------------
    # Legacy match wrappers (tests / callers)
    # ------------------------------------------------------------------

    def _match_by_fingerprint(self, event_id: int, fingerprint: str) -> int | None:
        hit = self._score_fingerprint(event_id, fingerprint)
        return int(hit["candidate_id"]) if hit else None

    def _match_by_embedding(
        self, event_id: int, embedding: list, event_date: datetime | None
    ) -> int | None:
        hard, _soft = self._score_embedding(event_id, embedding, event_date)
        return int(hard["candidate_id"]) if hard else None

    def _match_by_entities(
        self,
        event_id: int,
        entity_names: list[str],
        event_date: datetime | None,
        precision: str,
    ) -> int | None:
        hard, _soft = self._score_entities(event_id, entity_names, event_date, precision)
        return int(hard["candidate_id"]) if hard else None

    @staticmethod
    def _seconds_between_event_times(
        a: datetime | None, b: datetime | None
    ) -> float | None:
        """Absolute seconds between two event times; None if either side missing."""
        if a is None or b is None:
            return None
        if a.tzinfo is not None and b.tzinfo is None:
            b = b.replace(tzinfo=a.tzinfo)
        elif a.tzinfo is None and b.tzinfo is not None:
            a = a.replace(tzinfo=b.tzinfo)
        try:
            return abs((a - b).total_seconds())
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Merge / soft link / chain collapse
    # ------------------------------------------------------------------

    def resolve_cluster_root(self, event_id: int) -> int:
        """Follow canonical_event_id pointers to the root (union-find find)."""
        cursor = self.conn.cursor()
        seen: set[int] = set()
        current = int(event_id)
        try:
            for _ in range(32):
                if current in seen:
                    break
                seen.add(current)
                if self._has_event_cluster_id():
                    cursor.execute(
                        """
                        SELECT canonical_event_id, event_cluster_id
                        FROM chronological_events WHERE id = %s
                        """,
                        (current,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT canonical_event_id, NULL::bigint
                        FROM chronological_events WHERE id = %s
                        """,
                        (current,),
                    )
                row = cursor.fetchone()
                if not row:
                    break
                canon, cluster = row[0], row[1]
                if canon is not None:
                    current = int(canon)
                    continue
                if cluster is not None and int(cluster) != current:
                    current = int(cluster)
                    continue
                break
        finally:
            cursor.close()
        return current

    def _upsert_coref_link(
        self,
        *,
        member_id: int,
        canonical_id: int,
        match_tier: str,
        score: float | None,
        evidence: dict[str, Any] | None,
    ) -> None:
        if not self._has_coreference_links_table():
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO intelligence.event_coreference_links (
                    member_event_id, canonical_event_id, match_tier, score, evidence, updated_at
                ) VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (member_event_id) DO UPDATE SET
                    canonical_event_id = EXCLUDED.canonical_event_id,
                    match_tier = EXCLUDED.match_tier,
                    score = EXCLUDED.score,
                    evidence = EXCLUDED.evidence,
                    updated_at = NOW()
                """,
                (
                    int(member_id),
                    int(canonical_id),
                    match_tier,
                    float(score) if score is not None else None,
                    json.dumps(evidence or {}),
                ),
            )
        except Exception as e:
            logger.debug("coref link upsert failed: %s", e)
            raise
        finally:
            cursor.close()

    async def _merge(
        self,
        duplicate_id: int,
        canonical_id: int,
        *,
        match_tier: str = "hard",
        score: float | None = None,
        evidence: dict[str, Any] | None = None,
    ):
        """Point duplicate at canonical, set cluster root, merge metadata, write link."""
        root = self.resolve_cluster_root(canonical_id)
        cursor = self.conn.cursor()
        try:
            if self._has_event_cluster_id():
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET canonical_event_id = %s,
                        event_cluster_id = %s
                    WHERE id = %s
                """,
                    (root, root, duplicate_id),
                )
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET event_cluster_id = COALESCE(event_cluster_id, %s)
                    WHERE id = %s
                """,
                    (root, root),
                )
            else:
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET canonical_event_id = %s
                    WHERE id = %s
                """,
                    (root, duplicate_id),
                )

            cursor.execute(
                """
                UPDATE chronological_events
                SET source_count = source_count + 1,
                    last_corroborated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (root,),
            )

            cursor.execute(
                """
                SELECT key_actors FROM chronological_events WHERE id = %s
            """,
                (duplicate_id,),
            )
            dup_actors = self._parse_json((cursor.fetchone() or (None,))[0])

            cursor.execute(
                """
                SELECT key_actors FROM chronological_events WHERE id = %s
            """,
                (root,),
            )
            can_actors = self._parse_json((cursor.fetchone() or (None,))[0])

            if isinstance(dup_actors, list) and isinstance(can_actors, list):
                existing_names = {
                    a.get("name", "").lower() for a in can_actors if isinstance(a, dict)
                }
                for actor in dup_actors:
                    if (
                        isinstance(actor, dict)
                        and actor.get("name", "").lower() not in existing_names
                    ):
                        can_actors.append(actor)
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET key_actors = %s
                    WHERE id = %s
                """,
                    (json.dumps(can_actors), root),
                )

            tier = match_tier if match_tier != "soft" else "hard"
            if tier == "hard" and match_tier not in (
                "fingerprint",
                "embedding",
                "entity_temporal",
            ):
                tier = "hard"
            self._upsert_coref_link(
                member_id=duplicate_id,
                canonical_id=root,
                match_tier=tier if tier != "hard" else (
                    match_tier if match_tier in (
                        "fingerprint", "embedding", "entity_temporal", "hard"
                    ) else "hard"
                ),
                score=score if score is not None else 1.0,
                evidence=evidence,
            )

            # Causal harvest hook (Phase 3b) — best-effort, never fail merge
            try:
                self._maybe_harvest_causal_edge(duplicate_id, root, score=score)
            except Exception as ce:
                logger.debug("causal harvest after merge: %s", ce)

            self.conn.commit()
            logger.info(f"Merged event {duplicate_id} -> canonical {root}")
        except Exception as e:
            logger.error(f"Merge failed ({duplicate_id} -> {canonical_id}): {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    async def _link_soft(
        self,
        member_id: int,
        candidate_id: int,
        *,
        score: float | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Soft band: write coreference link + cluster id; do NOT set canonical_event_id."""
        # Zero / missing similarity must not stick as a provisional link.
        soft_floor = _dedup_soft_min()
        if score is None or float(score) < soft_floor:
            logger.debug(
                "Skip soft link %s -> %s: score=%s below soft_min=%s",
                member_id,
                candidate_id,
                score,
                soft_floor,
            )
            return
        root = self.resolve_cluster_root(candidate_id)
        cursor = self.conn.cursor()
        try:
            if self._has_event_cluster_id():
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET event_cluster_id = %s
                    WHERE id = %s AND canonical_event_id IS NULL
                """,
                    (root, member_id),
                )
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET event_cluster_id = COALESCE(event_cluster_id, %s)
                    WHERE id = %s
                """,
                    (root, root),
                )
            self._upsert_coref_link(
                member_id=member_id,
                canonical_id=root,
                match_tier="soft",
                score=score,
                evidence=evidence,
            )
            self.conn.commit()
            logger.info(
                "Soft-linked event %s -> cluster root %s (score=%s)",
                member_id,
                root,
                score,
            )
        except Exception as e:
            logger.error(f"Soft link failed ({member_id} -> {candidate_id}): {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def _prune_weak_soft_links(self) -> int:
        """Drop soft coreference links whose score fell below the soft band (or is null/0).

        Hard merges (canonical_event_id set) are left alone. Soft links with score below
        ``EVENT_DEDUP_SOFT_MIN`` are deleted and their cluster pointer cleared when it
        only came from a soft link.
        """
        if not self._has_coreference_links_table():
            return 0
        soft_floor = _dedup_soft_min()
        cursor = self.conn.cursor()
        pruned = 0
        try:
            cursor.execute(
                """
                SELECT member_event_id, canonical_event_id, score
                FROM intelligence.event_coreference_links
                WHERE match_tier = 'soft'
                  AND (score IS NULL OR score < %s)
                """,
                (soft_floor,),
            )
            rows = cursor.fetchall() or []
            for member_id, canon_id, _score in rows:
                cursor.execute(
                    """
                    DELETE FROM intelligence.event_coreference_links
                    WHERE member_event_id = %s AND match_tier = 'soft'
                    """,
                    (int(member_id),),
                )
                # Clear cluster id only when the member was never hard-merged.
                if self._has_event_cluster_id():
                    cursor.execute(
                        """
                        UPDATE public.chronological_events
                        SET event_cluster_id = NULL
                        WHERE id = %s
                          AND canonical_event_id IS NULL
                          AND event_cluster_id IS NOT DISTINCT FROM %s
                        """,
                        (int(member_id), int(canon_id) if canon_id is not None else None),
                    )
                pruned += 1
            if pruned:
                self.conn.commit()
                logger.info(
                    "Pruned %s weak soft coreference links (score < %s)",
                    pruned,
                    soft_floor,
                )
        except Exception as e:
            logger.warning("prune weak soft links failed: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass
            return 0
        finally:
            cursor.close()
        return pruned

    def _collapse_coref_chains(self) -> int:
        """Rewrite A→B→C chains so members point at the ultimate root."""
        if not self._has_event_cluster_id() and not self._has_coreference_links_table():
            return 0
        cursor = self.conn.cursor()
        collapsed = 0
        try:
            # chronological_events canonical chains
            cursor.execute(
                """
                SELECT id, canonical_event_id
                FROM chronological_events
                WHERE canonical_event_id IS NOT NULL
                """
            )
            pairs = cursor.fetchall() or []
            for eid, canon in pairs:
                root = self.resolve_cluster_root(int(canon))
                if root != int(canon):
                    if self._has_event_cluster_id():
                        cursor.execute(
                            """
                            UPDATE chronological_events
                            SET canonical_event_id = %s, event_cluster_id = %s
                            WHERE id = %s
                            """,
                            (root, root, int(eid)),
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE chronological_events
                            SET canonical_event_id = %s
                            WHERE id = %s
                            """,
                            (root, int(eid)),
                        )
                    collapsed += 1

            if self._has_coreference_links_table():
                cursor.execute(
                    """
                    SELECT member_event_id, canonical_event_id
                    FROM intelligence.event_coreference_links
                    """
                )
                for member_id, canon in cursor.fetchall() or []:
                    root = self.resolve_cluster_root(int(canon))
                    if root != int(canon):
                        cursor.execute(
                            """
                            UPDATE intelligence.event_coreference_links
                            SET canonical_event_id = %s, updated_at = NOW()
                            WHERE member_event_id = %s
                            """,
                            (root, int(member_id)),
                        )
                        collapsed += 1

            self.conn.commit()
        except Exception as e:
            logger.error("coref chain collapse failed: %s", e)
            self.conn.rollback()
        finally:
            cursor.close()
        return collapsed

    def _maybe_harvest_causal_edge(
        self, duplicate_id: int, root_id: int, *, score: float | None = None
    ) -> None:
        """
        Phase 3b: when hard-merging into a root that already has a distinct prior
        cluster on a shared storyline, upsert a chronological_event causal edge.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT storyline_id, actual_event_date
                FROM chronological_events WHERE id = %s
                """,
                (duplicate_id,),
            )
            dup = cursor.fetchone()
            cursor.execute(
                """
                SELECT storyline_id, actual_event_date
                FROM chronological_events WHERE id = %s
                """,
                (root_id,),
            )
            root = cursor.fetchone()
            if not dup or not root:
                return
            # Prefer edges between distinct cluster roots already on a storyline
            sl = (root[0] or dup[0] or "").strip()
            if not sl:
                return
            # Find another leaf event on same storyline with different cluster
            if self._has_event_cluster_id():
                cursor.execute(
                    """
                    SELECT id FROM chronological_events
                    WHERE storyline_id = %s
                      AND id NOT IN (%s, %s)
                      AND canonical_event_id IS NULL
                      AND (
                        event_cluster_id IS DISTINCT FROM %s
                        OR event_cluster_id IS NULL
                      )
                    ORDER BY actual_event_date ASC NULLS LAST
                    LIMIT 1
                    """,
                    (sl, duplicate_id, root_id, root_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id FROM chronological_events
                    WHERE storyline_id = %s
                      AND id NOT IN (%s, %s)
                      AND canonical_event_id IS NULL
                    ORDER BY actual_event_date ASC NULLS LAST
                    LIMIT 1
                    """,
                    (sl, duplicate_id, root_id),
                )
            prior = cursor.fetchone()
            if not prior:
                return
            prior_id = int(prior[0])
            conf = float(score) if score is not None else 0.7
            conf = max(0.4, min(0.95, conf))
            grade = (
                "strong" if conf >= 0.85 else "moderate" if conf >= 0.7 else "weak"
            )
            domain_key = None
            if ":" in sl:
                domain_key = sl.split(":", 1)[0]
            from services.causal_edges_service import upsert_causal_edge

            upsert_causal_edge(
                cause_kind="chronological_event",
                cause_id=prior_id,
                effect_kind="chronological_event",
                effect_id=root_id,
                relation="precedes",
                confidence=conf,
                evidence_grade=grade,
                domain_key=domain_key,
                source="event_coreference",
                reasoning_steps=[
                    {
                        "action": "hard_merge_corroboration",
                        "member": duplicate_id,
                        "root": root_id,
                        "prior_cluster_event": prior_id,
                    }
                ],
            )
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _store_embedding(self, event_id: int, embedding: list):
        cursor = self.conn.cursor()
        try:
            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            cursor.execute(
                """
                UPDATE chronological_events
                SET embedding = %s::vector
                WHERE id = %s
            """,
                (vec_literal, event_id),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to store embedding for event {event_id}: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    @staticmethod
    def _precision_window(precision: str) -> timedelta | None:
        return {
            "exact": timedelta(days=1),
            "week": timedelta(weeks=1),
            "month": timedelta(days=31),
            "quarter": timedelta(days=93),
            "year": timedelta(days=366),
        }.get(precision)

    @staticmethod
    def _parse_json(val) -> Any:
        if val is None:
            return []
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
