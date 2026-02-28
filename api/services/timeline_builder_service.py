"""
Timeline Builder Service for News Intelligence v5.0 (Phase 4)

Takes a storyline's linked events and produces a structured chronological
timeline with gap detection, milestone identification, and source attribution.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ACTIVE_GAP_DAYS = 7
SLOW_GAP_DAYS = 30


class TimelineBuilderService:
    """Constructs structured timelines from storyline events."""

    def __init__(self, conn):
        self.conn = conn

    def build_timeline(self, storyline_id: int) -> Dict[str, Any]:
        """
        Build a full timeline for a storyline.

        Returns a dict with ordered events, gaps, milestones, and metadata.
        """
        events = self._load_events(storyline_id)
        if not events:
            return {"storyline_id": storyline_id, "events": [], "gaps": [], "milestones": []}

        events = self._order_events(events)
        gaps = self._detect_gaps(events, storyline_id)
        milestones = self._identify_milestones(events)
        events_with_sources = self._attach_sources(events)

        return {
            "storyline_id": storyline_id,
            "events": events_with_sources,
            "gaps": gaps,
            "milestones": milestones,
            "event_count": len(events),
            "time_span": self._compute_span(events),
            "source_count": self._count_distinct_sources(events),
            "built_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Event loading and ordering
    # ------------------------------------------------------------------

    def _load_events(self, storyline_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT ce.id, ce.title, ce.description, ce.event_type,
                   ce.actual_event_date, ce.date_precision,
                   ce.location, ce.key_actors, ce.entities,
                   ce.importance_score, ce.source_article_id,
                   ce.source_count, ce.is_ongoing, ce.outcome,
                   ce.canonical_event_id
            FROM chronological_events ce
            WHERE ce.storyline_id = %s::text
              AND ce.canonical_event_id IS NULL
            ORDER BY ce.actual_event_date ASC NULLS LAST
        """, (storyline_id,))
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id": r[0], "title": r[1], "description": r[2],
                "event_type": r[3], "event_date": r[4],
                "date_precision": r[5], "location": r[6],
                "key_actors": self._pj(r[7]), "entities": self._pj(r[8]),
                "importance": float(r[9] or 0),
                "source_article_id": r[10], "source_count": r[11] or 1,
                "is_ongoing": r[12], "outcome": r[13],
            }
            for r in rows
        ]

    @staticmethod
    def _order_events(events: List[Dict]) -> List[Dict]:
        dated = [e for e in events if e.get('event_date')]
        undated = [e for e in events if not e.get('event_date')]
        dated.sort(key=lambda e: e['event_date'])
        return dated + undated

    # ------------------------------------------------------------------
    # Gap detection
    # ------------------------------------------------------------------

    def _detect_gaps(self, events: List[Dict], storyline_id: int) -> List[Dict]:
        dated = [e for e in events if e.get('event_date')]
        if len(dated) < 2:
            return []

        gap_threshold = self._gap_threshold(storyline_id)
        gaps = []
        for i in range(len(dated) - 1):
            d1 = dated[i]['event_date']
            d2 = dated[i + 1]['event_date']
            if isinstance(d1, datetime):
                d1 = d1.date()
            if isinstance(d2, datetime):
                d2 = d2.date()
            delta = (d2 - d1).days
            if delta > gap_threshold:
                gaps.append({
                    "after_event_id": dated[i]['id'],
                    "before_event_id": dated[i + 1]['id'],
                    "gap_days": delta,
                    "from_date": d1.isoformat(),
                    "to_date": d2.isoformat(),
                })
        return gaps

    def _gap_threshold(self, storyline_id: int) -> int:
        """Use a shorter threshold for active stories, longer for slow-moving ones."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT status FROM storylines WHERE id = %s", (storyline_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        status = row[0] if row else 'active'
        if status in ('dormant', 'watching'):
            return SLOW_GAP_DAYS
        return ACTIVE_GAP_DAYS

    # ------------------------------------------------------------------
    # Milestone identification
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_milestones(events: List[Dict]) -> List[Dict]:
        if not events:
            return []

        milestones = []
        dated = [e for e in events if e.get('event_date')]

        if dated:
            milestones.append({
                "type": "first_event",
                "event_id": dated[0]['id'],
                "label": "Story begins",
            })

        high_importance = [e for e in events if e.get('importance', 0) >= 0.8]
        for e in high_importance:
            milestones.append({
                "type": "escalation",
                "event_id": e['id'],
                "label": f"Key development: {e['title'][:60]}",
            })

        resolution_types = {'court_ruling', 'agreement', 'resignation', 'death'}
        for e in events:
            if e.get('event_type') in resolution_types and not e.get('is_ongoing'):
                milestones.append({
                    "type": "resolution",
                    "event_id": e['id'],
                    "label": f"Resolution: {e['title'][:60]}",
                })

        return milestones

    # ------------------------------------------------------------------
    # Source attribution
    # ------------------------------------------------------------------

    def _attach_sources(self, events: List[Dict]) -> List[Dict]:
        cursor = self.conn.cursor()
        for evt in events:
            aid = evt.get('source_article_id')
            if aid:
                cursor.execute("""
                    SELECT title, source_domain, published_at
                    FROM articles WHERE id = %s
                """, (aid,))
                row = cursor.fetchone()
                if row:
                    evt['source'] = {
                        'article_title': row[0],
                        'domain': row[1],
                        'published_at': row[2].isoformat() if row[2] else None,
                    }
        cursor.close()
        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_span(events: List[Dict]) -> Optional[Dict]:
        dated = [e for e in events if e.get('event_date')]
        if len(dated) < 2:
            return None
        first = dated[0]['event_date']
        last = dated[-1]['event_date']
        if isinstance(first, datetime):
            first = first.date()
        if isinstance(last, datetime):
            last = last.date()
        return {
            "start": first.isoformat(),
            "end": last.isoformat(),
            "days": (last - first).days,
        }

    @staticmethod
    def _count_distinct_sources(events: List[Dict]) -> int:
        return len({
            e.get('source', {}).get('domain')
            for e in events if e.get('source', {}).get('domain')
        })

    @staticmethod
    def _pj(val):
        if val is None:
            return []
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
