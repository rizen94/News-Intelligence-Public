"""
Timeline Builder Service for News Intelligence v5.0 (Phase 4)

Takes a storyline's linked events and produces a structured chronological
timeline with gap detection, milestone identification, and source attribution.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

ACTIVE_GAP_DAYS = 7
SLOW_GAP_DAYS = 30

# Per-domain storylines/articles live in these schemas (not public).
_DOMAIN_SCHEMAS = ("politics", "finance", "science_tech")
# Extracted timeline rows live in public (migrations 060, 133).
_CHRONO_EVENTS = "public.chronological_events"


class TimelineBuilderService:
    """Constructs structured timelines from storyline events."""

    def __init__(self, conn, schema_name: str | None = None):
        """
        Args:
            conn: Open DB connection (psycopg2).
            schema_name: Domain schema for storylines/articles lookups (e.g. politics, science_tech).
                chronological_events is read from public.chronological_events; articles are domain-scoped.
        """
        self.conn = conn
        self.schema_name = schema_name.replace("-", "_") if schema_name else None

    def build_timeline(self, storyline_id: int) -> dict[str, Any]:
        """
        Build a full timeline for a storyline.

        Returns a dict with ordered events, gaps, milestones, and metadata.
        """
        events = self._load_events(storyline_id)
        merged_duplicate_events_count = self._count_merged_duplicate_events(storyline_id)
        if not events:
            return {
                "storyline_id": storyline_id,
                "events": [],
                "gaps": [],
                "milestones": [],
                "merged_duplicate_events_count": merged_duplicate_events_count,
            }

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
            "merged_duplicate_events_count": merged_duplicate_events_count,
        }

    # ------------------------------------------------------------------
    # Event loading and ordering
    # ------------------------------------------------------------------

    def _count_merged_duplicate_events(self, storyline_id: int) -> int:
        """Rows merged into a canonical event (hidden from primary timeline)."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM {_CHRONO_EVENTS}
                WHERE storyline_id = %s::text AND canonical_event_id IS NOT NULL
                """,
                (storyline_id,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            logger.debug("TimelineBuilderService: merged duplicate count failed", exc_info=True)
            return 0
        finally:
            cursor.close()

    def _load_events(self, storyline_id: int) -> list[dict]:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'chronological_events'
                      AND column_name = 'temporal_status'
                )
                """
            )
            has_temporal = bool(cursor.fetchone()[0])
        except Exception:
            has_temporal = False

        temporal_sql = (
            ", COALESCE(ce.temporal_status, 'unknown') AS temporal_status"
            if has_temporal
            else ""
        )
        cursor.execute(
            f"""
            SELECT ce.id, ce.title, ce.description, ce.event_type,
                   ce.actual_event_date, ce.date_precision,
                   ce.location, ce.key_actors, ce.entities,
                   ce.importance_score, ce.source_article_id,
                   ce.source_count, ce.is_ongoing, ce.outcome,
                   ce.canonical_event_id, ce.extraction_method,
                   ce.extraction_confidence
                   {temporal_sql}
            FROM {_CHRONO_EVENTS} ce
            WHERE ce.storyline_id = %s::text
              AND ce.canonical_event_id IS NULL
            ORDER BY ce.actual_event_date ASC NULLS LAST
        """,
            (storyline_id,),
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                "id": r[0],
                "title": r[1],
                "description": r[2],
                "event_type": r[3],
                "event_date": r[4],
                "date_precision": r[5],
                "location": r[6],
                "key_actors": self._pj(r[7]),
                "entities": self._pj(r[8]),
                "importance": float(r[9] or 0),
                "source_article_id": r[10],
                "source_count": r[11] or 1,
                "is_ongoing": r[12],
                "outcome": r[13],
                "canonical_event_id": r[14] if len(r) > 14 else None,
                "extraction_method": r[15] if len(r) > 15 else None,
                "extraction_confidence": float(r[16])
                if len(r) > 16 and r[16] is not None
                else None,
                "temporal_status": r[17] if has_temporal and len(r) > 17 else "unknown",
                "timeline_row_role": "primary",
            }
            for r in rows
        ]

    @staticmethod
    def _order_events(events: list[dict]) -> list[dict]:
        dated = [e for e in events if e.get("event_date")]
        undated = [e for e in events if not e.get("event_date")]
        dated.sort(key=lambda e: e["event_date"])
        return dated + undated

    # ------------------------------------------------------------------
    # Gap detection
    # ------------------------------------------------------------------

    def _detect_gaps(self, events: list[dict], storyline_id: int) -> list[dict]:
        dated = [e for e in events if e.get("event_date")]
        if len(dated) < 2:
            return []

        gap_threshold = self._gap_threshold(storyline_id)
        gaps = []
        for i in range(len(dated) - 1):
            d1 = dated[i]["event_date"]
            d2 = dated[i + 1]["event_date"]
            if isinstance(d1, datetime):
                d1 = d1.date()
            if isinstance(d2, datetime):
                d2 = d2.date()
            delta = (d2 - d1).days
            if delta > gap_threshold:
                gaps.append(
                    {
                        "after_event_id": dated[i]["id"],
                        "before_event_id": dated[i + 1]["id"],
                        "gap_days": delta,
                        "from_date": d1.isoformat(),
                        "to_date": d2.isoformat(),
                    }
                )
        return gaps

    def _gap_threshold(self, storyline_id: int) -> int:
        """Use a shorter threshold for active stories, longer for slow-moving ones."""
        schemas = [self.schema_name] if self.schema_name else list(_DOMAIN_SCHEMAS)
        cursor = self.conn.cursor()
        try:
            status = "active"
            for sch in schemas:
                if not sch:
                    continue
                cursor.execute(
                    f"SELECT status FROM {sch}.storylines WHERE id = %s",
                    (storyline_id,),
                )
                row = cursor.fetchone()
                if row:
                    status = row[0] or "active"
                    break
        finally:
            cursor.close()
        if status in ("dormant", "watching"):
            return SLOW_GAP_DAYS
        return ACTIVE_GAP_DAYS

    # ------------------------------------------------------------------
    # Milestone identification
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_milestones(events: list[dict]) -> list[dict]:
        if not events:
            return []

        milestones = []
        dated = [e for e in events if e.get("event_date")]

        if dated:
            milestones.append(
                {
                    "type": "first_event",
                    "event_id": dated[0]["id"],
                    "label": "Story begins",
                }
            )

        high_importance = [e for e in events if e.get("importance", 0) >= 0.8]
        for e in high_importance:
            milestones.append(
                {
                    "type": "escalation",
                    "event_id": e["id"],
                    "label": f"Key development: {e['title'][:60]}",
                }
            )

        resolution_types = {"court_ruling", "agreement", "resignation", "death"}
        for e in events:
            if e.get("event_type") in resolution_types and not e.get("is_ongoing"):
                milestones.append(
                    {
                        "type": "resolution",
                        "event_id": e["id"],
                        "label": f"Resolution: {e['title'][:60]}",
                    }
                )

        return milestones

    # ------------------------------------------------------------------
    # Source attribution
    # ------------------------------------------------------------------

    def _attach_sources(self, events: list[dict]) -> list[dict]:
        if not self.schema_name:
            logger.debug(
                "TimelineBuilderService: no schema_name; skipping article source enrichment"
            )
            return events
        sch = self.schema_name
        cursor = self.conn.cursor()
        try:
            for evt in events:
                aid = evt.get("source_article_id")
                if not aid:
                    continue
                cursor.execute(
                    f"""
                    SELECT title, source_domain, published_at
                    FROM {sch}.articles WHERE id = %s
                """,
                    (aid,),
                )
                row = cursor.fetchone()
                if row:
                    evt["source"] = {
                        "article_title": row[0],
                        "domain": row[1],
                        "published_at": row[2].isoformat() if row[2] else None,
                    }
        finally:
            cursor.close()
        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_span(events: list[dict]) -> dict | None:
        dated = [e for e in events if e.get("event_date")]
        if len(dated) < 2:
            return None
        first = dated[0]["event_date"]
        last = dated[-1]["event_date"]
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
    def _count_distinct_sources(events: list[dict]) -> int:
        return len(
            {e.get("source", {}).get("domain") for e in events if e.get("source", {}).get("domain")}
        )

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
