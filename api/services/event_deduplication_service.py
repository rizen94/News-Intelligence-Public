"""
Event Deduplication Service for News Intelligence v5.0 (Phase 2)

Recognises when multiple articles from different sources describe the same
real-world event using a three-tier matching strategy:

1. Fingerprint matching  (fast, exact)
2. Semantic similarity    (medium, fuzzy -- pgvector cosine distance)
3. Entity-temporal overlap (slow, precise)

When duplicates are found the system designates the earliest-reported version
as canonical and merges metadata from subsequent sources.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
ENTITY_OVERLAP_MIN = 2
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


async def _get_embedding(text: str) -> list[float] | None:
    """Get a 768-d embedding from Ollama's nomic-embed-text model."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            if resp.status_code == 200:
                return resp.json().get("embedding")
        except Exception as e:
            logger.error(f"Embedding request failed: {e}")
    return None


class EventDeduplicationService:
    """Cross-source event deduplication engine."""

    def __init__(self, conn):
        self.conn = conn
        self._chronological_has_embedding: bool | None = None

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

    async def deduplicate_event(self, event_id: int) -> int | None:
        """
        Check if *event_id* is a duplicate of an existing canonical event.

        Returns the canonical_event_id if a match is found, else None.
        Side-effects: updates canonical pointers, source counts, and merges
        metadata when a match is confirmed.
        """
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
        canonical = self._match_by_fingerprint(eid, fingerprint)
        if canonical:
            await self._merge(eid, canonical)
            return canonical

        # --- Tier 2: semantic similarity (pgvector) ----------------------
        if has_emb:
            if embedding is None:
                embed_text = f"{title}. {desc or ''}"
                vec = await _get_embedding(embed_text)
                if vec:
                    self._store_embedding(eid, vec)
                    embedding = vec

            if embedding is not None:
                canonical = self._match_by_embedding(eid, embedding)
                if canonical:
                    await self._merge(eid, canonical)
                    return canonical

        # --- Tier 3: entity + temporal overlap ---------------------------
        actor_names = (
            [a.get("name", "") for a in key_actors] if isinstance(key_actors, list) else []
        )
        entity_names = []
        if isinstance(entities, list):
            entity_names = [e.get("name", "") if isinstance(e, dict) else str(e) for e in entities]
        all_names = list(set(n.lower().strip() for n in actor_names + entity_names if n))

        canonical = self._match_by_entities(eid, all_names, edate, precision)
        if canonical:
            await self._merge(eid, canonical)
            return canonical

        return None

    # ------------------------------------------------------------------
    # Batch entry point
    # ------------------------------------------------------------------

    async def deduplicate_recent(self, limit: int = 50) -> dict[str, int]:
        """Deduplicate events that have not yet been checked."""
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

        stats = {"checked": 0, "merged": 0}
        for (eid,) in rows:
            stats["checked"] += 1
            canonical = await self.deduplicate_event(eid)
            if canonical:
                stats["merged"] += 1
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

    def _match_by_embedding(self, event_id: int, embedding: list) -> int | None:
        cursor = self.conn.cursor()
        try:
            vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
            cursor.execute(
                """
                SELECT id, 1 - (embedding <=> %s::vector) AS similarity
                FROM chronological_events
                WHERE id != %s
                  AND canonical_event_id IS NULL
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT 1
            """,
                (vec_literal, event_id, vec_literal),
            )
            row = cursor.fetchone()
            if row and row[1] >= SIMILARITY_THRESHOLD:
                return row[0]
        except Exception as e:
            logger.error(f"pgvector similarity query failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()
        return None

    def _match_by_entities(
        self,
        event_id: int,
        entity_names: list[str],
        event_date: datetime | None,
        precision: str,
    ) -> int | None:
        if len(entity_names) < ENTITY_OVERLAP_MIN:
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
                cand_names = set()
                for j in (cand_actors_json, cand_entities_json):
                    parsed = self._parse_json(j)
                    if isinstance(parsed, list):
                        for item in parsed:
                            name = item.get("name", "") if isinstance(item, dict) else str(item)
                            if name:
                                cand_names.add(name.lower().strip())
                overlap = len(set(entity_names) & cand_names)
                if overlap >= ENTITY_OVERLAP_MIN:
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
        """Point duplicate at canonical and merge metadata."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE chronological_events
                SET canonical_event_id = %s
                WHERE id = %s
            """,
                (canonical_id, duplicate_id),
            )

            cursor.execute(
                """
                UPDATE chronological_events
                SET source_count = source_count + 1,
                    last_corroborated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (canonical_id,),
            )

            # Merge key_actors from duplicate into canonical
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
                (canonical_id,),
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
                    (json.dumps(can_actors), canonical_id),
                )

            self.conn.commit()
            logger.info(f"Merged event {duplicate_id} -> canonical {canonical_id}")
        except Exception as e:
            logger.error(f"Merge failed ({duplicate_id} -> {canonical_id}): {e}")
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
