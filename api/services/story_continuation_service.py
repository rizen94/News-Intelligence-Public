"""
Story Continuation Service for News Intelligence v5.0 (Phase 3)

When new events are extracted, this service matches them to existing
long-running storylines -- even if the last related article was months ago.

Matching strategy:
1. Entity lookup in story_entity_index (no time window)
2. Event type compatibility filter
3. LLM context verification for top candidates
4. Automatic or flagged linking based on confidence

Also manages storyline lifecycle transitions:
  active -> dormant -> watching -> concluded -> archived

Integration Point: Processes events from `chronological_events` table and links them
to existing storylines in the database. Updates `storyline_id` field for downstream
processing by other phases.

Error Handling:
- Database connection issues trigger retry mechanisms
- LLM context verification failures are logged and skipped
- Invalid storyline data is logged and skipped
- Entity lookup failures are logged and events proceed to next phase

Monitoring:
- Storyline linking accuracy
- LLM verification confidence scores
- Processing time per event
- Storyline transition rates
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.runtime import env_int
from shared.pg_savepoint import execute_with_savepoint
from shared.services.llm_service import LLMService, ModelType
from shared.story_entity_index import map_entity_type_for_sei

logger = logging.getLogger(__name__)

EVENT_TYPE_COMPATIBILITY = {
    "legal_action": {"court_ruling", "arrest", "investigation", "legal_action", "legislation"},
    "court_ruling": {"legal_action", "arrest", "investigation", "court_ruling"},
    "arrest": {"legal_action", "court_ruling", "investigation", "arrest"},
    "investigation": {"legal_action", "court_ruling", "arrest", "investigation", "report_release"},
    "policy_decision": {"legislation", "policy_decision", "public_statement", "meeting"},
    "legislation": {"policy_decision", "legislation", "public_statement", "meeting"},
    "election": {"election", "appointment", "resignation", "public_statement"},
        "conflict": {
            "conflict",
            "military_action",
            "agreement",
            "protest",
            "public_statement",
            "death",
            "diplomatic",
        },
        "military_action": {"conflict", "military_action", "diplomatic", "protest"},
        "diplomatic": {"diplomatic", "conflict", "agreement", "meeting", "policy_decision"},
    "protest": {"protest", "conflict", "public_statement", "arrest"},
    "agreement": {"agreement", "conflict", "meeting", "policy_decision"},
    "economic_event": {"economic_event", "policy_decision", "report_release"},
    "appointment": {"appointment", "resignation", "election"},
    "resignation": {"resignation", "appointment", "investigation"},
}

STORY_VERIFICATION_PROMPT = """You are a senior news analyst. Determine whether a new event belongs to an existing storyline.

Existing storyline: "{storyline_title}"
Summary: {storyline_summary}

Recent events in this storyline (chronological):
{recent_events}

Core entities: {core_entities}

---

New event: "{event_title}" on {event_date}
Key actors: {event_actors}
Description: {event_description}

---

Question: Is this new event part of the same ongoing story?
Answer with ONLY a JSON object:
{{
    "verdict": "YES" or "NO" or "MAYBE",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<one sentence>"
}}"""

DORMANT_DAYS = 30
AUTO_LINK_THRESHOLD = 0.8
REVIEW_THRESHOLD = 0.5

# Cap on how many of the source article's entities feed candidate lookup.
ARTICLE_ENTITY_SIGNAL_LIMIT = 60


def _min_entity_overlap() -> int:
    return max(1, min(5, env_int("CONTINUATION_MIN_ENTITY_OVERLAP", 2)))


def _rare_entity_max_storylines() -> int:
    """A matched entity in <= this many storylines is distinctive enough to admit alone."""
    return max(0, min(10, env_int("CONTINUATION_RARE_ENTITY_MAX_STORYLINES", 2)))


def _candidate_limit() -> int:
    return max(1, min(50, env_int("CONTINUATION_CANDIDATE_LIMIT", 10)))


def _hub_entity_count() -> int:
    """Storylines indexing more entities than this are 'hubs' and match almost anything.

    Overbroad storylines (catch-all clusters) otherwise absorb every new event, so
    they must clear a higher bar than a focused storyline.
    """
    return max(10, env_int("CONTINUATION_HUB_ENTITY_COUNT", 150))


class StoryContinuationService:
    """Matches new events to existing storylines across unbounded time windows."""

    def __init__(self, conn, llm: LLMService | None = None, schema: str | None = None):
        self.conn = conn
        self.llm = llm or LLMService()
        # When set (e.g. 'politics', 'finance', 'science_tech'), search_path is set and storyline_id stored as "schema:id"
        self.schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def match_event_to_storyline(self, event_id: int) -> dict[str, Any] | None:
        """
        Attempt to match a single event to an existing storyline.

        Returns a dict with match info if found, else None.
        Prefers cluster-root events when resolving temporal/entity features.
        """
        event = self._load_event(event_id)
        if not event:
            return None

        # Prefer cluster root for scoring dates / continuity
        try:
            from services.event_coreference_service import resolve_cluster_root

            root_id = resolve_cluster_root(self.conn, int(event_id))
            if root_id != int(event_id):
                root_event = self._load_event(root_id)
                if root_event:
                    # Keep member id for linking; borrow root date/source_count cues
                    event["cluster_root_id"] = root_id
                    event["actual_event_date"] = (
                        root_event.get("actual_event_date") or event.get("actual_event_date")
                    )
        except Exception:
            pass

        actor_names = self._extract_names(event["key_actors"])
        entity_names = self._extract_names(event["entities"])
        # LLM actors are often descriptive prose ("city authorities"); the source
        # article's extracted entities are the same vocabulary story_entity_index
        # was built from, so they carry the real matching signal.
        article_names, canonical_ids = self._article_entity_signals(event.get("source_article_id"))
        all_names = list({*actor_names, *entity_names, *article_names})

        # Step 1: entity lookup (no time constraint)
        candidates = self._find_candidates_by_entities(
            all_names, event["id"], canonical_ids=canonical_ids
        )

        if not candidates:
            return None

        # Step 2: event type compatibility
        candidates = self._filter_by_event_type(candidates, event["event_type"])
        if not candidates:
            return None

        # Step 2b: pre-LLM rank with blend_link_score (temporal + entity)
        candidates = self._rank_candidates_with_blend(candidates, event)

        # Step 3: LLM verification (top 3)
        best_match = await self._verify_candidates(candidates[:3], event)
        if best_match:
            self._link_event(event, best_match)
            try:
                self._maybe_causal_from_continuation(event, best_match)
            except Exception:
                pass
            return best_match

        return None

    def _rank_candidates_with_blend(self, candidates: list[dict], event: dict) -> list[dict]:
        """Re-order candidates by blend_link_score before LLM gate."""
        try:
            from services.domain_synthesis_config import (
                get_domain_synthesis_config,
                temporal_proximity_score,
            )
            from services.embedding_link_candidate_service import blend_link_score, days_apart
        except Exception:
            return candidates

        domain_key = self.schema or "politics"
        try:
            half = get_domain_synthesis_config(domain_key).link_score_profile.temporal_half_life_days
        except Exception:
            half = 14.0

        event_date = event.get("actual_event_date")
        ranked: list[tuple[float, dict]] = []
        cursor = self.conn.cursor()
        try:
            for cand in candidates:
                sid = cand["storyline_id"]
                # Entity overlap as Jaccard proxy
                matched = cand.get("matched_entities") or []
                overlap_n = int(cand.get("entity_overlap") or len(matched) or 0)
                canonical_n = int(cand.get("canonical_overlap") or 0)
                # Identity-resolved matches are worth more than raw name hits.
                effective_n = overlap_n + canonical_n
                # Approximate: overlap / (overlap + 2) as soft jaccard
                ent_j = float(effective_n) / float(effective_n + 2) if effective_n else 0.0
                # Damp broad storylines: a hit inside a 400-entity index is weak evidence.
                index_size = int(cand.get("index_size") or 0)
                hub_cut = _hub_entity_count()
                if index_size > hub_cut:
                    ent_j *= (float(hub_cut) / float(index_size)) ** 0.5
                # Storyline last event date
                cursor.execute(
                    """
                    SELECT MAX(actual_event_date)
                    FROM chronological_events
                    WHERE storyline_id = %s::text AND canonical_event_id IS NULL
                    """,
                    (sid,),
                )
                row = cursor.fetchone()
                sl_date = row[0] if row else None
                gap = days_apart(event_date, sl_date)
                temp_p = temporal_proximity_score(gap, half_life_days=half)
                # Semantic proxy from entity overlap strength
                sem = min(1.0, 0.45 + 0.15 * effective_n)
                causal_b = 0.0
                try:
                    from services.causal_edges_service import has_causal_edge_between

                    # Prefer cluster-root event id when available for continuity cues.
                    _eid = int(event.get("cluster_root_id") or event.get("id") or 0)
                    if _eid and sid is not None:
                        if has_causal_edge_between(
                            "chronological_event",
                            _eid,
                            "storyline",
                            int(sid),
                            domain_key=domain_key,
                        ) or has_causal_edge_between(
                            "storyline",
                            int(sid),
                            "chronological_event",
                            _eid,
                            domain_key=domain_key,
                        ):
                            causal_b = 1.0
                except Exception:
                    causal_b = 0.0
                score = blend_link_score(
                    semantic=sem,
                    entity_jaccard=ent_j,
                    temporal_proximity=temp_p,
                    domain_key=domain_key,
                    causal_boost=causal_b,
                )
                cand["blend_score"] = score
                cand["temporal_proximity"] = temp_p
                cand["causal_boost"] = causal_b
                ranked.append((score, cand))
        finally:
            cursor.close()
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in ranked]

    def _maybe_causal_from_continuation(self, event: dict, match: dict) -> None:
        """Phase 3b: upsert causal edge when continuation links event to storyline with prior events."""
        from services.causal_edges_service import upsert_causal_edge

        sid = match.get("storyline_id")
        eid = int(event["id"])
        if sid is None:
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id FROM chronological_events
                WHERE storyline_id = %s::text
                  AND id != %s
                  AND canonical_event_id IS NULL
                ORDER BY actual_event_date ASC NULLS LAST
                LIMIT 1
                """,
                (sid, eid),
            )
            prior = cursor.fetchone()
            if not prior:
                return
            conf = float(match.get("confidence") or match.get("blend_score") or 0.65)
            grade = "moderate" if conf >= 0.7 else "weak"
            domain_key = self.schema
            upsert_causal_edge(
                cause_kind="chronological_event",
                cause_id=int(prior[0]),
                effect_kind="chronological_event",
                effect_id=eid,
                relation="contributes_to",
                confidence=max(0.4, min(0.95, conf)),
                evidence_grade=grade,
                domain_key=domain_key,
                source="story_continuation",
                reasoning_steps=[
                    {
                        "action": "story_continuation_link",
                        "storyline_id": sid,
                        "event_id": eid,
                    }
                ],
            )
        finally:
            cursor.close()

    async def process_recent_events(self, limit: int = 30) -> dict[str, int]:
        """Batch-match unlinked events to storylines. Uses story_entity_index and storylines in current search_path."""
        cursor = self.conn.cursor()
        try:
            if self.schema:
                cursor.execute("SET search_path TO %s, public", (self.schema,))
            cursor.execute(
                """
                SELECT id FROM chronological_events
                WHERE storyline_id = '' OR storyline_id IS NULL
                ORDER BY extraction_timestamp DESC
                LIMIT %s
            """,
                (limit,),
            )
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning(
                "Story continuation: failed to list unlinked events (check search_path / schema): %s",
                e,
            )
            cursor.close()
            return {"checked": 0, "linked": 0, "flagged": 0}
        finally:
            cursor.close()

        stats = {"checked": 0, "linked": 0, "flagged": 0}
        for (eid,) in rows:
            stats["checked"] += 1
            result = await self.match_event_to_storyline(eid)
            if result:
                if result.get("auto_linked"):
                    stats["linked"] += 1
                else:
                    stats["flagged"] += 1
        return stats

    def update_entity_index(self, storyline_id: int):
        """
        Rebuild the entity index for a storyline from its linked events.
        Called after a new event is linked.
        """
        schema = self.schema or "public"
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT key_actors, entities
                FROM public.chronological_events
                WHERE storyline_id = %s::text
                  AND canonical_event_id IS NULL
            """,
                (storyline_id,),
            )
            rows = cursor.fetchall()

            entity_counts: dict[tuple[str, str], dict] = {}
            # Both lists default to `other`: event payloads carry no entity types, and
            # guessing `person` both mistypes organisations and splits one entity across
            # two rows (the unique key includes entity_type).
            for actors_json, entities_json in rows:
                for item_json, default_type in [(actors_json, "other"), (entities_json, "other")]:
                    items = self._parse_json(item_json)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get("name", "").strip()
                            # `role` is free-text prose ("Investigating body") and is not a
                            # type — only entity_type may seed the CHECK-constrained column.
                            etype = map_entity_type_for_sei(
                                item.get("entity_type") or default_type
                            )
                        else:
                            name = str(item).strip()
                            etype = map_entity_type_for_sei(default_type)
                        if not name:
                            continue
                        key = (name.lower(), etype)
                        if key not in entity_counts:
                            entity_counts[key] = {
                                "name": name,
                                "type": etype,
                                "role": item.get("role", "") if isinstance(item, dict) else "",
                                "count": 0,
                            }
                        entity_counts[key]["count"] += 1

            skipped = 0
            for idx, ((norm_name, etype), info) in enumerate(entity_counts.items()):
                is_core = info["count"] >= 3
                ok = execute_with_savepoint(
                    cursor,
                    self.conn,
                    f"sei_upsert_{storyline_id}_{idx}",
                    f"""
                    INSERT INTO {schema}.story_entity_index
                        (storyline_id, entity_name, entity_role, entity_type,
                         mention_count, is_core_entity, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (storyline_id, entity_name, entity_type)
                    DO UPDATE SET
                        mention_count = EXCLUDED.mention_count,
                        is_core_entity = EXCLUDED.is_core_entity,
                        last_seen_at = CURRENT_TIMESTAMP
                """,
                    (storyline_id, info["name"], info["role"], etype, info["count"], is_core),
                )
                if not ok:
                    skipped += 1
            if skipped:
                logger.warning(
                    "Entity index storyline %s: %s/%s rows rejected",
                    storyline_id,
                    skipped,
                    len(entity_counts),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Entity index update for storyline {storyline_id} failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def update_lifecycle_states(self):
        """Transition storylines between lifecycle states based on activity. Uses storylines in current search_path."""
        cursor = self.conn.cursor()
        try:
            if self.schema:
                cursor.execute("SET search_path TO %s, public", (self.schema,))
        except Exception as e:
            logger.warning(
                "Story continuation: failed to set search_path for lifecycle update: %s", e
            )
            cursor.close()
            return
        now = datetime.now(timezone.utc)
        try:
            cursor.execute(
                """
                UPDATE storylines
                SET status = 'dormant',
                    dormant_since = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'active'
                  AND last_event_at < %s
                  AND last_event_at IS NOT NULL
            """,
                (now - timedelta(days=DORMANT_DAYS),),
            )
            dormant_count = cursor.rowcount

            self.conn.commit()
            if dormant_count:
                logger.info(f"Transitioned {dormant_count} storylines to dormant")
        except Exception as e:
            logger.error(f"Lifecycle update failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_event(self, event_id: int) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, event_type, actual_event_date,
                   location, key_actors, entities, continuation_signals,
                   source_article_id
            FROM chronological_events
            WHERE id = %s
        """,
            (event_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "event_type": row[3],
            "actual_event_date": row[4],
            "location": row[5],
            "key_actors": self._parse_json(row[6]),
            "entities": self._parse_json(row[7]),
            "continuation_signals": self._parse_json(row[8]),
            "source_article_id": row[9],
        }

    def _article_entity_signals(self, article_id: Any) -> tuple[list[str], list[int]]:
        """Entity names + canonical ids extracted from the event's source article."""
        if article_id is None or not self.schema:
            return [], []
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT DISTINCT entity_name, canonical_entity_id
                FROM {self.schema}.article_entities
                WHERE article_id = %s AND entity_name IS NOT NULL
                LIMIT %s
                """,
                (int(article_id), ARTICLE_ENTITY_SIGNAL_LIMIT),
            )
            names: list[str] = []
            canonical_ids: list[int] = []
            for name, cid in cursor.fetchall():
                if name and name.strip():
                    names.append(name.strip())
                if cid is not None:
                    canonical_ids.append(int(cid))
            return names, sorted(set(canonical_ids))
        except Exception as e:
            logger.debug("article entity signals article=%s: %s", article_id, e)
            return [], []
        finally:
            cursor.close()

    def _find_candidates_by_entities(
        self,
        entity_names: list[str],
        event_id: int,
        *,
        canonical_ids: list[int] | None = None,
    ) -> list[dict]:
        """Candidate storylines by shared entities.

        Admits a storyline when any of these hold:
          - ``min_overlap`` distinct entity names match (original rule);
          - at least one canonical entity id matches (identity-resolved, high trust);
          - one name matches and that entity is rare across storylines (distinctive).
        Recall is deliberately wide — the LLM verification gate downstream decides.
        """
        cids = [int(c) for c in (canonical_ids or [])]
        if not entity_names and not cids:
            return []

        lower_names = sorted({n.lower().strip() for n in entity_names if n and n.strip()})
        schema = self.schema or "public"
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                WITH sig_names AS (
                    SELECT UNNEST(%(names)s::text[]) AS nm
                ),
                sig_ids AS (
                    SELECT UNNEST(%(ids)s::int[]) AS cid
                ),
                matches AS (
                    SELECT sei.storyline_id,
                           sei.entity_name,
                           sei.canonical_entity_id,
                           COALESCE(sei.is_core_entity, FALSE) AS is_core,
                           (sei.canonical_entity_id IS NOT NULL
                            AND sei.canonical_entity_id IN (SELECT cid FROM sig_ids)) AS by_canonical
                    FROM {schema}.story_entity_index sei
                    WHERE LOWER(sei.entity_name) IN (SELECT nm FROM sig_names)
                       OR (sei.canonical_entity_id IS NOT NULL
                           AND sei.canonical_entity_id IN (SELECT cid FROM sig_ids))
                ),
                rarity AS (
                    SELECT LOWER(entity_name) AS nm, COUNT(DISTINCT storyline_id) AS story_count
                    FROM {schema}.story_entity_index
                    WHERE LOWER(entity_name) IN (SELECT nm FROM sig_names)
                    GROUP BY 1
                ),
                sizes AS (
                    SELECT storyline_id, COUNT(*) AS sei_size
                    FROM {schema}.story_entity_index
                    GROUP BY 1
                )
                SELECT m.storyline_id, s.title, s.summary, s.status,
                       COUNT(DISTINCT m.entity_name) AS overlap,
                       COUNT(DISTINCT m.canonical_entity_id)
                           FILTER (WHERE m.by_canonical) AS canonical_overlap,
                       BOOL_OR(m.is_core) AS core_hit,
                       MIN(COALESCE(r.story_count, 9999)) AS min_story_count,
                       COALESCE(MAX(z.sei_size), 0) AS sei_size,
                       ARRAY_AGG(DISTINCT m.entity_name) AS matched_entities
                FROM matches m
                JOIN {schema}.storylines s ON s.id = m.storyline_id
                LEFT JOIN rarity r ON r.nm = LOWER(m.entity_name)
                LEFT JOIN sizes z ON z.storyline_id = m.storyline_id
                WHERE s.status NOT IN ('archived', 'concluded')
                GROUP BY m.storyline_id, s.title, s.summary, s.status
                HAVING
                    CASE WHEN COALESCE(MAX(z.sei_size), 0) > %(hub)s THEN
                        -- Hub storyline: only strong, identity-resolved evidence admits it.
                        COUNT(DISTINCT m.canonical_entity_id) FILTER (WHERE m.by_canonical) >= 2
                        OR COUNT(DISTINCT m.entity_name) >= %(hub_min_overlap)s
                    ELSE
                        COUNT(DISTINCT m.entity_name) >= %(min_overlap)s
                        OR COUNT(DISTINCT m.canonical_entity_id) FILTER (WHERE m.by_canonical) >= 1
                        OR (
                            COUNT(DISTINCT m.entity_name) >= 1
                            AND MIN(COALESCE(r.story_count, 9999)) <= %(rare)s
                        )
                    END
                ORDER BY canonical_overlap DESC, overlap DESC
                LIMIT %(limit)s
                """,
                {
                    "names": lower_names,
                    "ids": cids,
                    "hub": _hub_entity_count(),
                    "hub_min_overlap": max(4, _min_entity_overlap() * 2),
                    "min_overlap": _min_entity_overlap(),
                    "rare": _rare_entity_max_storylines(),
                    "limit": _candidate_limit(),
                },
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "storyline_id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "status": row[3],
                        "entity_overlap": row[4],
                        "canonical_overlap": row[5],
                        "core_entity_hit": bool(row[6]),
                        "entity_rarity": row[7],
                        "index_size": row[8],
                        "matched_entities": row[9],
                    }
                )
            return results
        except Exception as e:
            logger.error(f"Entity candidate lookup failed: {e}")
            return []
        finally:
            cursor.close()

    def _filter_by_event_type(self, candidates: list[dict], event_type: str) -> list[dict]:
        compatible = EVENT_TYPE_COMPATIBILITY.get(event_type, {event_type, "other"})
        filtered = []
        cursor = self.conn.cursor()
        for cand in candidates:
            cursor.execute(
                """
                SELECT DISTINCT event_type FROM chronological_events
                WHERE storyline_id = %s::text AND event_type IS NOT NULL
            """,
                (cand["storyline_id"],),
            )
            story_types = {r[0] for r in cursor.fetchall()}
            if story_types & compatible:
                cand["type_compatible"] = True
                filtered.append(cand)
            elif not story_types:
                cand["type_compatible"] = False
                filtered.append(cand)
        cursor.close()
        return filtered

    async def _verify_candidates(self, candidates: list[dict], event: dict) -> dict | None:
        for cand in candidates:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT title, actual_event_date
                FROM chronological_events
                WHERE storyline_id = %s::text
                ORDER BY actual_event_date DESC NULLS LAST
                LIMIT 5
            """,
                (cand["storyline_id"],),
            )
            recent = cursor.fetchall()
            cursor.close()

            events_text = (
                "\n".join(f"- {r[0]} ({r[1] or 'date unknown'})" for r in recent)
                or "(no prior events)"
            )

            actor_names = [
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in (event.get("key_actors") or [])
            ]

            prompt = STORY_VERIFICATION_PROMPT.format(
                storyline_title=cand["title"],
                storyline_summary=cand.get("summary") or "(no summary)",
                recent_events=events_text,
                core_entities=", ".join(cand.get("matched_entities") or []),
                event_title=event["title"],
                event_date=event.get("actual_event_date") or "unknown",
                event_actors=", ".join(actor_names),
                event_description=event.get("description") or "",
            )

            try:
                raw = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
                verdict = self._parse_verdict(raw)
                if not verdict:
                    continue

                confidence = verdict.get("confidence", 0)
                if verdict["verdict"] == "YES" and confidence >= AUTO_LINK_THRESHOLD:
                    cand["confidence"] = confidence
                    cand["auto_linked"] = True
                    cand["reasoning"] = verdict.get("reasoning", "")
                    return cand
                elif verdict["verdict"] in ("YES", "MAYBE") and confidence >= REVIEW_THRESHOLD:
                    cand["confidence"] = confidence
                    cand["auto_linked"] = False
                    cand["reasoning"] = verdict.get("reasoning", "")
                    return cand
            except Exception as e:
                logger.warning(f"LLM verification failed for storyline {cand['storyline_id']}: {e}")

        return None

    def _link_event(self, event: dict, match: dict):
        cursor = self.conn.cursor()
        schema = self.schema or "public"
        try:
            storyline_id = match["storyline_id"]
            cursor.execute(
                """
                UPDATE chronological_events
                SET storyline_id = %s::text
                WHERE id = %s
            """,
                (storyline_id, event["id"]),
            )

            # Attach source article to the storyline when present (membership only).
            aid = event.get("source_article_id")
            if aid is not None:
                try:
                    conf = float(match.get("confidence") or 0.7)
                except (TypeError, ValueError):
                    conf = 0.7
                conf = max(0.0, min(1.0, conf))
                # Savepoint: a rejected attach must not abort the storyline updates below.
                attached = execute_with_savepoint(
                    cursor,
                    self.conn,
                    f"continuation_attach_{event['id']}",
                    f"""
                    INSERT INTO {schema}.storyline_articles
                    (storyline_id, article_id, relevance_score, confidence_score,
                     relationship_type, added_at, added_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'related', NOW(), 'story_continuation',
                            NOW(), NOW())
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                    """,
                    (int(storyline_id), int(aid), conf, conf),
                )
                if not attached:
                    logger.warning(
                        "continuation storyline_articles attach failed storyline=%s article=%s",
                        storyline_id,
                        aid,
                    )

            # Reactivate dormant storylines
            cursor.execute(
                f"""
                UPDATE {schema}.storylines
                SET status = 'active',
                    last_event_at = CURRENT_TIMESTAMP,
                    reactivation_count = COALESCE(reactivation_count, 0) + 1,
                    dormant_since = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'dormant'
            """,
                (storyline_id,),
            )

            cursor.execute(
                f"""
                UPDATE {schema}.storylines
                SET last_event_at = CURRENT_TIMESTAMP,
                    total_events = COALESCE(total_events, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (storyline_id,),
            )

            self.conn.commit()
            self.update_entity_index(storyline_id)
            # Admit / refresh editorial package so Research modal can pick it up.
            try:
                from shared.domain_registry import schema_to_primary_domain_key
                from services.editorial_package_service import ensure_package_from_storyline

                dk = schema_to_primary_domain_key(schema)
                ensure_package_from_storyline(
                    domain_key=dk,
                    storyline_id=int(storyline_id),
                    actor="story_continuation",
                    refresh_members=True,
                )
            except Exception as e:
                logger.debug(
                    "continuation editorial seed storyline=%s: %s", storyline_id, e
                )
            logger.info(
                f"Linked event {event['id']} to storyline {storyline_id} "
                f"(confidence={match.get('confidence', 0):.2f}, auto={match.get('auto_linked')})"
            )
        except Exception as e:
            logger.error(f"Event linking failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def _parse_verdict(self, raw: str) -> dict | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(text[start : end + 1])
            if "verdict" in data:
                return data
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _extract_names(val) -> list[str]:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        if not isinstance(val, list):
            return []
        names = []
        for item in val:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
            else:
                name = str(item).strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _parse_json(val):
        if val is None:
            return []
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
