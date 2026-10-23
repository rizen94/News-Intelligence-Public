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

Tune aggressiveness with ``EVENT_DEDUP_*`` env vars (see ``configs/env.example``).

Integration Point: Processes events from `chronological_events` table for deduplication
and updates metadata including `source_count` and `event_fingerprint` for downstream
processing by Story Continuation (Phase 5) phase.

Error Handling:
- Database connection issues trigger retry mechanisms
- LLM embedding failures are logged and skipped
- Invalid event data is logged and skipped
- Duplicate detection failures are logged and events proceed to next phase

Monitoring:
- Duplicate detection rate
- Semantic similarity scores
- Processing time per event
- Tier-1, Tier-2, Tier-3 match rates
"""

import difflib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _ollama_url() -> str:
    for key in ("OLLAMA_HOST", "OLLAMA_URL", "OLLAMA_POP_OS_HOST"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            return raw.rstrip("/")
    return "http://127.0.0.1:11434"


EMBED_MODEL = "nomic-embed-text"
# Back-compat alias; prefer _ollama_url() at call sites (env may load after import).
OLLAMA_URL = _ollama_url()


def _dedup_env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _dedup_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
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


def _dedup_tick_batch() -> int:
    """Default tick batch for deduplicate_recent when no limit argument is supplied."""
    v = _dedup_env_int("EVENT_DEDUP_TICK_BATCH", 50)
    return max(1, min(v, 2000))


async def _get_embedding(text: str) -> list[float] | None:
    """Get a 768-d embedding from Ollama's nomic-embed-text model via CB hub."""
    from shared.services.llm_service import is_ollama_pressure_error, ollama_embed_async

    try:
        return await ollama_embed_async(text, model=EMBED_MODEL)
    except Exception as e:
        if is_ollama_pressure_error(e):
            raise
        logger.error(f"Embedding request failed: {e}")
    return None


class EventDeduplicationService:
    """Cross-source event deduplication engine."""

    def __init__(self, conn):
        self.conn = conn
        self._chronological_has_embedding: bool | None = None
        self._hnsw_index_guaranteed: bool | None = None

    def _ensure_hnsw_index(self) -> None:
        """Create pgvector HNSW index on chronological_events(embedding) if missing.

        Idempotent — uses IF NOT EXISTS + CONCURRENTLY so it is safe to call
        repeatedly during startup/restarts.  Skips silently when the pg extension
        is not loaded (e.g. a small test DB without vector).
        """
        if self._hnsw_index_guaranteed is not None:
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE c.relname = 'idx_chronological_events_embedding_hnsw'
                          AND n.nspname = 'public'
                    ) THEN
                        CREATE INDEX CONCURRENTLY IF NOT EXISTS
                            idx_chronological_events_embedding_hnsw
                            ON public.chronological_events
                            USING hnsw (embedding vector_cosine_ops)
                            WITH (m = 16, ef_construction = 64);
                    END IF;
                END $$;
            """
            )
            self.conn.commit()
            logger.info("HNSW index on chronological_events(embedding) ready")
        except Exception as exc:
            # pgvector extension missing or unsupported — non-fatal
            logger.warning(
                "Could not create HNSW index (pgvector may be unavailable): %s", exc
            )
            self.conn.rollback()
        finally:
            cursor.close()
        self._hnsw_index_guaranteed = True

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

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def _match_and_collect(self, event_id: int) -> tuple[int, int] | None:
        """Find a canonical candidate for *event_id* without committing anything.

        Returns ``(duplicate_id, canonical_id)`` when a match is found, else ``None``.
        Used by both the per-event and batch entry points so they share identical
        matching logic with no double-commit side-effects.
        """
        # --- Tier 1: fingerprint match -----------------------------------------
        cursor = self.conn.cursor()
        try:
            await cursor.execute(
                "SELECT event_fingerprint FROM chronological_events WHERE id = %s",
                (event_id,),
            )
            r = await cursor.fetchone()
            fingerprint = r[0] if r and r[0] else None
        finally:
            cursor.close()

        if fingerprint:
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    "SELECT id FROM chronological_events WHERE event_fingerprint = %s AND id != %s AND canonical_event_id IS NULL ORDER BY extraction_timestamp ASC LIMIT 1",
                    (fingerprint, event_id),
                )
                match_row = cursor.fetchone()
                if match_row:
                    return (event_id, int(match_row[0]))
            finally:
                cursor.close()

        # --- Tier 2: semantic similarity -----------------------------------------
        embedding = None
        embed_col_exists = self._chronological_events_has_embedding()

        if embed_col_exists:
            cursor = self.conn.cursor()
            try:
                await cursor.execute(
                    "SELECT headline, summary FROM chronological_events WHERE id = %s",
                    (event_id,),
                )
                r = await cursor.fetchone()
                headline, summary = (r[0], r[1]) if r else (None, None)
            finally:
                cursor.close()

            parts = [f"Event #{event_id}"]
            if headline:
                parts.append(headline)
            if summary:
                parts.append(summary)
            text_for_embed = " ".join(parts)
            embedding = await _get_embedding(text_for_embed)

        if embedding is not None:
            cursor = self.conn.cursor()
            try:
                top_k = _dedup_embedding_top_k()
                sim_thr = _dedup_similarity_threshold()
                emb_margin = _dedup_embedding_margin()
                skip_margin_if_ge = _dedup_skip_margin_if_sim_ge()
                borderline_sim = _dedup_borderline_sim()
                borderline_sec = _dedup_borderline_max_seconds()

                cursor.execute(
                    "SELECT actual_event_date FROM chronological_events WHERE id = %s",
                    (event_id,),
                )
                r2 = cursor.fetchone()
                event_date: datetime | None = r2[0] if r2 else None

                vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
                cursor.execute(
                    "SELECT id, 1 - (embedding <=> %s::vector) AS similarity, actual_event_date, extraction_timestamp FROM chronological_events WHERE id != %s AND canonical_event_id IS NULL AND embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s",
                    (vec_literal, event_id, vec_literal, top_k),
                )
                candidates = cursor.fetchall() or []
                if not candidates:
                    return None

                best_id = candidates[0][0]
                best_sim = float(candidates[0][1] or 0.0)
                best_event_date = candidates[0][2]
                best_extraction_ts = candidates[0][3]

                if best_sim < sim_thr:
                    return None

                if len(candidates) > 1:
                    second_sim = float(candidates[1][1] or 0.0)
                    margin = best_sim - second_sim
                    if margin < emb_margin and best_sim < skip_margin_if_ge:
                        return None

                temporal_on = event_date is not None
                dt_sec = self._seconds_between_event_times(event_date, best_event_date)
                if temporal_on and (
                    best_sim < borderline_sim
                    and dt_sec is not None
                    and dt_sec > borderline_sec
                ):
                    return None

                return (event_id, int(best_id))
            except Exception as e:
                logger.error(f"pgvector similarity query failed: {e}")
                self.conn.rollback()
            finally:
                cursor.close()
            return None

        # --- Tier 3: entity + temporal overlap -----------------------------------
        cursor = self.conn.cursor()
        try:
            await cursor.execute(
                "SELECT key_actors, entities FROM chronological_events WHERE id = %s",
                (event_id,),
            )
            r = await cursor.fetchone()
            k_a, ents = (r[0], r[1]) if r else (None, None)

            actor_names: list[str] = []
            if isinstance(k_a, list):
                actor_names = [a.get("name", "") for a in k_a]
            if isinstance(ents, list):
                actor_names += [e.get("name", "") if isinstance(e, dict) else str(e) for e in ents]

            cursor.execute(
                "SELECT actual_event_date FROM chronological_events WHERE id = %s",
                (event_id,),
            )
            r2 = cursor.fetchone()
            event_date: datetime | None = r2[0] if r2 else None
        finally:
            cursor.close()

        canonical = self._match_by_entities(event_id, actor_names, event_date, "year")
        if canonical:
            return (event_id, int(canonical))

        return None

    async def deduplicate_event(self, event_id: int) -> int | None:
        """Check if *event_id* is a duplicate of an existing canonical event.

        Returns the canonical_event_id if a match is found, else None.
        Matching logic is fully delegated to ``_match_and_collect``; side-effects
        (canonical pointers, source counts, metadata merging) are applied via
        ``_merge`` so callers may batch multiple merges before committing.
        """
        match = await self._match_and_collect(event_id)
        if match is None:
            return None
        dup_id, canon_id = match
        await self._merge(dup_id, canon_id)
        return canon_id

    # ------------------------------------------------------------------
    # Batch entry point
    # ------------------------------------------------------------------

    async def deduplicate_recent(self, limit: int | None = None) -> dict[str, int]:
        """Deduplicate events that have not yet been checked.

        *limit* defaults to the ``EVENT_DEDUP_TICK_BATCH`` env var (see
        ``_dedup_tick_batch``); override for ad-hoc bulk runs.
        """
        # P0: env-driven tick batch size
        limit = limit if limit is not None else _dedup_tick_batch()

        # Ensure pgvector HNSW index exists for fast ANN lookups
        self._ensure_hnsw_index()

        # P1: bulk-fetch all candidates in a single query (one round-trip).
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id FROM chronological_events
            WHERE canonical_event_id IS NULL
            ORDER BY extraction_timestamp ASC
            LIMIT %s
        """,
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()

        if not rows:
            return {"checked": 0, "merged": 0}

        # P1: accumulate merges in memory before committing.
        pending_merges: list[tuple[int, int]] = []  # (duplicate_id, canonical_id)
        stats = {"checked": 0, "merged": 0}
        for (eid,) in rows:
            stats["checked"] += 1
            canonical = await self.deduplicate_event(eid)
            if canonical is not None:
                stats["merged"] += 1
                pending_merges.append((eid, canonical))

        # P1: batch-commit all merges in one transaction.
        if pending_merges:
            self._batch_apply_merges(pending_merges)

        return stats

    # ------------------------------------------------------------------
    # Matching tiers
    # ------------------------------------------------------------------

    def _match_by_fingerprint(self, event_id: int, fingerprint: str) -> int | None:
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
        return row[0] if row else None

    def _match_by_embedding(
        self, event_id: int, embedding: list, event_date: datetime | None
    ) -> int | None:
        cursor = self.conn.cursor()
        try:
            sim_thr = _dedup_similarity_threshold()
            top_k = _dedup_embedding_top_k()
            emb_margin = _dedup_embedding_margin()
            skip_margin_if_ge = _dedup_skip_margin_if_sim_ge()
            borderline_sim = _dedup_borderline_sim()
            borderline_sec = _dedup_borderline_max_seconds()
            temporal_on = os.environ.get("EVENT_DEDUP_DISABLE_TEMPORAL_BORDERLINE", "").lower() not in (
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
                return None

            best_id = candidates[0][0]
            best_sim = float(candidates[0][1] or 0.0)
            best_event_date = candidates[0][2]
            best_extraction_ts = candidates[0][3]

            if best_sim < sim_thr:
                return None

            if len(candidates) > 1:
                second_sim = float(candidates[1][1] or 0.0)
                margin = best_sim - second_sim
                if margin < emb_margin and best_sim < skip_margin_if_ge:
                    return None

            cand_time = best_event_date or best_extraction_ts
            dt_sec = self._seconds_between_event_times(event_date, cand_time)
            if temporal_on and (
                best_sim < borderline_sim
                and dt_sec is not None
                and dt_sec > borderline_sec
            ):
                return None

            return int(best_id)
        except Exception as e:
            logger.error(f"pgvector similarity query failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
        return None

    @staticmethod
    def _seconds_between_event_times(
        a: datetime | None, b: datetime | None
    ) -> float | None:
        """Absolute seconds between two event times; None if either side missing (skip temporal gate)."""
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

    def _match_by_entities(
        self,
        event_id: int,
        entity_names: list[str],
        event_date: datetime | None,
        precision: str,
    ) -> int | None:
        overlap_min = _dedup_entity_overlap_min()
        if len(entity_names) < overlap_min:
            return None

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

            for row in cursor.fetchall():
                cand_id, cand_actors_json, cand_entities_json = row
                cand_names_raw: list[str] = []
                for j in (cand_actors_json, cand_entities_json):
                    parsed = self._parse_json(j)
                    if isinstance(parsed, list):
                        for item in parsed:
                            name = item.get("name", "") if isinstance(item, dict) else str(item)
                            if name:
                                cand_names_raw.append(name.lower().strip())

                # Exact overlap first (fast path)
                if len(set(entity_names) & set(cand_names_raw)) >= overlap_min:
                    return cand_id

                # Fuzzy fallback: each query name must find ≥ threshold match
                fuzzy_threshold = 0.75
                matches = 0
                for qname in entity_names:
                    best_ratio = max(
                        difflib.SequenceMatcher(None, qname, cname).ratio()
                        for cname in cand_names_raw
                    ) if cand_names_raw else 0.0
                    if best_ratio >= fuzzy_threshold:
                        matches += 1
                if matches >= overlap_min:
                    return cand_id
        except Exception as e:
            logger.error(f"Entity-temporal match failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
        return None

    # ------------------------------------------------------------------
    # Merge logic
    # ------------------------------------------------------------------

    async def _merge(self, duplicate_id: int, canonical_id: int):
        """Apply a single dedup merge (delegates to batch helper)."""
        self._batch_apply_merges([(duplicate_id, canonical_id)])

    def _batch_apply_merges(self, pending_merges: list[tuple[int, int]]) -> None:
        """Apply all pending dedup merges in a single batch.

        Each tuple is ``(duplicate_id, canonical_id)``.  Updates are applied
        atomically; rows that already have ``canonical_event_id`` set (from prior
        _merge calls or earlier passes) are skipped gracefully.
        """
        if not pending_merges:
            return

        cursor = self.conn.cursor()
        try:
            # 1. Point duplicates → canonical
            for dup_id, canon_id in pending_merges:
                cursor.execute(
                    """
                    UPDATE chronological_events
                    SET canonical_event_id = %s
                    WHERE id = %s AND canonical_event_id IS NULL
                """,
                    (canon_id, dup_id),
                )

            # 2. Promote storyline_id from duplicates → canonical where needed
            for dup_id, canon_id in pending_merges:
                cursor.execute(
                    """
                    SELECT
                        (SELECT NULLIF(TRIM(COALESCE(storyline_id::text, '')), '')
                         FROM chronological_events WHERE id = %s) AS can_sl,
                        (SELECT NULLIF(TRIM(COALESCE(storyline_id::text, '')), '')
                         FROM chronological_events WHERE id = %s) AS dup_sl
                    """,
                    (canon_id, dup_id),
                )
                row = cursor.fetchone() or (None, None)
                can_sl, dup_sl = row[0], row[1]
                if not can_sl and dup_sl:
                    cursor.execute(
                        """
                        UPDATE chronological_events
                        SET storyline_id = %s
                        WHERE id = %s
                        """,
                        (dup_sl, canon_id),
                    )
                elif can_sl and dup_sl and str(can_sl) != str(dup_sl):
                    logger.warning(
                        "dedup merge storyline_id conflict dup=%s can=%s "
                        "dup_storyline=%s can_storyline=%s (keeping canonical)",
                        dup_id,
                        canon_id,
                        dup_sl,
                        can_sl,
                    )

            # 3. Merge key_actors from each duplicate into canonical
            for dup_id, canon_id in pending_merges:
                cursor.execute(
                    """
                    SELECT key_actors FROM chronological_events WHERE id = %s
                """,
                    (dup_id,),
                )
                dup_actors_raw = self._parse_json((cursor.fetchone() or (None,))[0])

                cursor.execute(
                    """
                    SELECT key_actors FROM chronological_events WHERE id = %s
                """,
                    (canon_id,),
                )
                can_actors_raw = self._parse_json((cursor.fetchone() or (None,))[0])

                if isinstance(dup_actors_raw, list) and isinstance(can_actors_raw, list):
                    existing_names: set[str] = {
                        a.get("name", "").lower()
                        for a in can_actors_raw
                        if isinstance(a, dict)
                    }
                    for actor in dup_actors_raw:
                        if (
                            isinstance(actor, dict)
                            and actor.get("name", "").lower() not in existing_names
                        ):
                            can_actors_raw.append(actor)
                    cursor.execute(
                        """
                        UPDATE chronological_events
                        SET key_actors = %s
                        WHERE id = %s
                        """,
                        (json.dumps(can_actors_raw), canon_id),
                    )

            # 4. Bump source_count on each unique canonical only once
            canon_ids_set = {cid for _, cid in pending_merges}
            if canon_ids_set:
                canon_list = list(canon_ids_set)
                placeholders = ",".join(f"%s" for _ in canon_list)
                cursor.execute(
                    f"""
                    UPDATE chronological_events
                    SET source_count = GREATEST(source_count, 1) + 1,
                        last_corroborated_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s::int[])
                      AND canonical_event_id IS NULL
                    """,
                    (canon_list,),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Batch dedup merge failed: {e}", exc_info=True)
            self.conn.rollback()
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
