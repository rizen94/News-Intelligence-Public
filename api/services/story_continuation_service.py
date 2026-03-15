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
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

EVENT_TYPE_COMPATIBILITY = {
    'legal_action':    {'court_ruling', 'arrest', 'investigation', 'legal_action', 'legislation'},
    'court_ruling':    {'legal_action', 'arrest', 'investigation', 'court_ruling'},
    'arrest':          {'legal_action', 'court_ruling', 'investigation', 'arrest'},
    'investigation':   {'legal_action', 'court_ruling', 'arrest', 'investigation', 'report_release'},
    'policy_decision': {'legislation', 'policy_decision', 'public_statement', 'meeting'},
    'legislation':     {'policy_decision', 'legislation', 'public_statement', 'meeting'},
    'election':        {'election', 'appointment', 'resignation', 'public_statement'},
    'conflict':        {'conflict', 'agreement', 'protest', 'public_statement', 'death'},
    'protest':         {'protest', 'conflict', 'public_statement', 'arrest'},
    'agreement':       {'agreement', 'conflict', 'meeting', 'policy_decision'},
    'economic_event':  {'economic_event', 'policy_decision', 'report_release'},
    'appointment':     {'appointment', 'resignation', 'election'},
    'resignation':     {'resignation', 'appointment', 'investigation'},
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


class StoryContinuationService:
    """Matches new events to existing storylines across unbounded time windows."""

    def __init__(self, conn, llm: Optional[LLMService] = None, schema: Optional[str] = None):
        self.conn = conn
        self.llm = llm or LLMService()
        # When set (e.g. 'politics', 'finance', 'science_tech'), search_path is set and storyline_id stored as "schema:id"
        self.schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def match_event_to_storyline(
        self, event_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to match a single event to an existing storyline.

        Returns a dict with match info if found, else None.
        """
        event = self._load_event(event_id)
        if not event:
            return None

        actor_names = self._extract_names(event['key_actors'])
        entity_names = self._extract_names(event['entities'])
        all_names = list(set(actor_names + entity_names))

        # Step 1: entity lookup (no time constraint)
        candidates = self._find_candidates_by_entities(all_names, event['id'])

        if not candidates:
            return None

        # Step 2: event type compatibility
        candidates = self._filter_by_event_type(candidates, event['event_type'])
        if not candidates:
            return None

        # Step 3: LLM verification (top 3)
        best_match = await self._verify_candidates(candidates[:3], event)
        if best_match:
            self._link_event(event, best_match)
            return best_match

        return None

    async def process_recent_events(self, limit: int = 30) -> Dict[str, int]:
        """Batch-match unlinked events to storylines. Uses story_entity_index and storylines in current search_path."""
        cursor = self.conn.cursor()
        try:
            if self.schema:
                cursor.execute("SET search_path TO %s, public", (self.schema,))
            cursor.execute("""
                SELECT id FROM chronological_events
                WHERE storyline_id = '' OR storyline_id IS NULL
                ORDER BY extraction_timestamp DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning("Story continuation: failed to list unlinked events (check search_path / schema): %s", e)
            cursor.close()
            return {"checked": 0, "linked": 0, "flagged": 0}
        finally:
            cursor.close()

        stats = {"checked": 0, "linked": 0, "flagged": 0}
        for (eid,) in rows:
            stats["checked"] += 1
            result = await self.match_event_to_storyline(eid)
            if result:
                if result.get('auto_linked'):
                    stats["linked"] += 1
                else:
                    stats["flagged"] += 1
        return stats

    def update_entity_index(self, storyline_id: int):
        """
        Rebuild the entity index for a storyline from its linked events.
        Called after a new event is linked.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT key_actors, entities
                FROM chronological_events
                WHERE storyline_id = %s::text
                  AND canonical_event_id IS NULL
            """, (storyline_id,))
            rows = cursor.fetchall()

            entity_counts: Dict[Tuple[str, str], Dict] = {}
            for actors_json, entities_json in rows:
                for item_json, default_type in [(actors_json, 'person'), (entities_json, 'other')]:
                    items = self._parse_json(item_json)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get('name', '').strip()
                            etype = item.get('entity_type', item.get('role', default_type))
                        else:
                            name = str(item).strip()
                            etype = default_type
                        if not name:
                            continue
                        key = (name.lower(), etype)
                        if key not in entity_counts:
                            entity_counts[key] = {
                                'name': name, 'type': etype,
                                'role': item.get('role', '') if isinstance(item, dict) else '',
                                'count': 0,
                            }
                        entity_counts[key]['count'] += 1

            for (norm_name, etype), info in entity_counts.items():
                is_core = info['count'] >= 3
                cursor.execute("""
                    INSERT INTO story_entity_index
                        (storyline_id, entity_name, entity_role, entity_type,
                         mention_count, is_core_entity, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (storyline_id, entity_name, entity_type)
                    DO UPDATE SET
                        mention_count = EXCLUDED.mention_count,
                        is_core_entity = EXCLUDED.is_core_entity,
                        last_seen_at = CURRENT_TIMESTAMP
                """, (storyline_id, info['name'], info['role'], etype,
                      info['count'], is_core))

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
            logger.warning("Story continuation: failed to set search_path for lifecycle update: %s", e)
            cursor.close()
            return
        now = datetime.now(timezone.utc)
        try:
            cursor.execute("""
                UPDATE storylines
                SET status = 'dormant',
                    dormant_since = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'active'
                  AND last_event_at < %s
                  AND last_event_at IS NOT NULL
            """, (now - timedelta(days=DORMANT_DAYS),))
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

    def _load_event(self, event_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, title, description, event_type, actual_event_date,
                   location, key_actors, entities, continuation_signals
            FROM chronological_events
            WHERE id = %s
        """, (event_id,))
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {
            'id': row[0], 'title': row[1], 'description': row[2],
            'event_type': row[3], 'actual_event_date': row[4],
            'location': row[5], 'key_actors': self._parse_json(row[6]),
            'entities': self._parse_json(row[7]),
            'continuation_signals': self._parse_json(row[8]),
        }

    def _find_candidates_by_entities(
        self, entity_names: List[str], event_id: int
    ) -> List[Dict]:
        if not entity_names:
            return []

        cursor = self.conn.cursor()
        placeholders = ','.join(['%s'] * len(entity_names))
        lower_names = [n.lower() for n in entity_names]

        try:
            cursor.execute(f"""
                SELECT sei.storyline_id, s.title, s.summary, s.status,
                       COUNT(DISTINCT sei.entity_name) AS overlap,
                       ARRAY_AGG(DISTINCT sei.entity_name) AS matched_entities
                FROM story_entity_index sei
                JOIN storylines s ON s.id = sei.storyline_id
                WHERE LOWER(sei.entity_name) IN ({placeholders})
                  AND s.status NOT IN ('archived', 'concluded')
                GROUP BY sei.storyline_id, s.title, s.summary, s.status
                HAVING COUNT(DISTINCT sei.entity_name) >= 2
                ORDER BY overlap DESC
                LIMIT 10
            """, lower_names)

            results = []
            for row in cursor.fetchall():
                results.append({
                    'storyline_id': row[0], 'title': row[1],
                    'summary': row[2], 'status': row[3],
                    'entity_overlap': row[4],
                    'matched_entities': row[5],
                })
            return results
        except Exception as e:
            logger.error(f"Entity candidate lookup failed: {e}")
            return []
        finally:
            cursor.close()

    def _filter_by_event_type(
        self, candidates: List[Dict], event_type: str
    ) -> List[Dict]:
        compatible = EVENT_TYPE_COMPATIBILITY.get(event_type, {event_type, 'other'})
        filtered = []
        cursor = self.conn.cursor()
        for cand in candidates:
            cursor.execute("""
                SELECT DISTINCT event_type FROM chronological_events
                WHERE storyline_id = %s::text AND event_type IS NOT NULL
            """, (cand['storyline_id'],))
            story_types = {r[0] for r in cursor.fetchall()}
            if story_types & compatible:
                cand['type_compatible'] = True
                filtered.append(cand)
            elif not story_types:
                cand['type_compatible'] = False
                filtered.append(cand)
        cursor.close()
        return filtered

    async def _verify_candidates(
        self, candidates: List[Dict], event: Dict
    ) -> Optional[Dict]:
        for cand in candidates:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT title, actual_event_date
                FROM chronological_events
                WHERE storyline_id = %s::text
                ORDER BY actual_event_date DESC NULLS LAST
                LIMIT 5
            """, (cand['storyline_id'],))
            recent = cursor.fetchall()
            cursor.close()

            events_text = "\n".join(
                f"- {r[0]} ({r[1] or 'date unknown'})" for r in recent
            ) or "(no prior events)"

            actor_names = [
                a.get('name', '') if isinstance(a, dict) else str(a)
                for a in (event.get('key_actors') or [])
            ]

            prompt = STORY_VERIFICATION_PROMPT.format(
                storyline_title=cand['title'],
                storyline_summary=cand.get('summary') or '(no summary)',
                recent_events=events_text,
                core_entities=', '.join(cand.get('matched_entities') or []),
                event_title=event['title'],
                event_date=event.get('actual_event_date') or 'unknown',
                event_actors=', '.join(actor_names),
                event_description=event.get('description') or '',
            )

            try:
                raw = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
                verdict = self._parse_verdict(raw)
                if not verdict:
                    continue

                confidence = verdict.get('confidence', 0)
                if verdict['verdict'] == 'YES' and confidence >= AUTO_LINK_THRESHOLD:
                    cand['confidence'] = confidence
                    cand['auto_linked'] = True
                    cand['reasoning'] = verdict.get('reasoning', '')
                    return cand
                elif verdict['verdict'] in ('YES', 'MAYBE') and confidence >= REVIEW_THRESHOLD:
                    cand['confidence'] = confidence
                    cand['auto_linked'] = False
                    cand['reasoning'] = verdict.get('reasoning', '')
                    return cand
            except Exception as e:
                logger.warning(f"LLM verification failed for storyline {cand['storyline_id']}: {e}")

        return None

    def _link_event(self, event: Dict, match: Dict):
        cursor = self.conn.cursor()
        try:
            storyline_id = match['storyline_id']
            cursor.execute("""
                UPDATE chronological_events
                SET storyline_id = %s::text
                WHERE id = %s
            """, (storyline_id, event['id']))

            # Reactivate dormant storylines
            cursor.execute("""
                UPDATE storylines
                SET status = 'active',
                    last_event_at = CURRENT_TIMESTAMP,
                    reactivation_count = COALESCE(reactivation_count, 0) + 1,
                    dormant_since = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'dormant'
            """, (storyline_id,))

            cursor.execute("""
                UPDATE storylines
                SET last_event_at = CURRENT_TIMESTAMP,
                    total_events = COALESCE(total_events, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (storyline_id,))

            self.conn.commit()
            self.update_entity_index(storyline_id)
            logger.info(
                f"Linked event {event['id']} to storyline {storyline_id} "
                f"(confidence={match.get('confidence', 0):.2f}, auto={match.get('auto_linked')})"
            )
        except Exception as e:
            logger.error(f"Event linking failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def _parse_verdict(self, raw: str) -> Optional[Dict]:
        text = raw.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[-1]
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0]
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(text[start:end + 1])
            if 'verdict' in data:
                return data
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _extract_names(val) -> List[str]:
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
                name = item.get('name', '').strip()
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
