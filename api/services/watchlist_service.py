"""
Watchlist Service for News Intelligence v5.0 (Phase 5)

Allows users to mark storylines for long-term tracking, generates alerts
when dormant stories reactivate, and produces weekly digests.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WatchlistService:
    """Manages the watchlist and alert lifecycle."""

    def __init__(self, conn):
        self.conn = conn

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_to_watchlist(
        self,
        storyline_id: int,
        user_label: Optional[str] = None,
        notes: Optional[str] = None,
        alert_on_reactivation: bool = True,
        weekly_digest: bool = True,
    ) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO watchlist (storyline_id, user_label, notes,
                                      alert_on_reactivation, weekly_digest)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (storyline_id) DO UPDATE SET
                    user_label = EXCLUDED.user_label,
                    notes = EXCLUDED.notes,
                    alert_on_reactivation = EXCLUDED.alert_on_reactivation,
                    weekly_digest = EXCLUDED.weekly_digest,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (storyline_id, user_label, notes,
                  alert_on_reactivation, weekly_digest))
            row = cursor.fetchone()

            cursor.execute("""
                UPDATE storylines
                SET status = 'watching', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status IN ('active', 'dormant')
            """, (storyline_id,))

            self.conn.commit()
            return {"success": True, "watchlist_id": row[0]}
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to add storyline {storyline_id} to watchlist: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()

    def remove_from_watchlist(self, storyline_id: int) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM watchlist WHERE storyline_id = %s", (storyline_id,))
            cursor.execute("""
                UPDATE storylines
                SET status = 'active', updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'watching'
            """, (storyline_id,))
            self.conn.commit()
            return {"success": True}
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to remove storyline {storyline_id} from watchlist: {e}")
            return {"success": False, "error": str(e)}
        finally:
            cursor.close()

    def get_watchlist(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT w.id, w.storyline_id, w.user_label, w.notes,
                       w.alert_on_reactivation, w.weekly_digest,
                       w.created_at, s.title, s.status, s.total_events,
                       s.last_event_at,
                       (SELECT COUNT(*) FROM watchlist_alerts wa
                        WHERE wa.watchlist_id = w.id AND wa.is_read = FALSE) AS unread
                FROM watchlist w
                JOIN storylines s ON s.id = w.storyline_id
                ORDER BY w.created_at DESC
            """)
            items = []
            for r in cursor.fetchall():
                items.append({
                    "watchlist_id": r[0],
                    "storyline_id": r[1],
                    "user_label": r[2],
                    "notes": r[3],
                    "alert_on_reactivation": r[4],
                    "weekly_digest": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                    "storyline_title": r[7],
                    "storyline_status": r[8],
                    "total_events": r[9] or 0,
                    "last_event_at": r[10].isoformat() if r[10] else None,
                    "unread_alerts": r[11],
                })
            return items
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def get_alerts(self, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        try:
            where = "WHERE wa.is_read = FALSE" if unread_only else ""
            cursor.execute(f"""
                SELECT wa.id, wa.storyline_id, wa.event_id, wa.alert_type,
                       wa.title, wa.body, wa.is_read, wa.created_at,
                       s.title AS storyline_title
                FROM watchlist_alerts wa
                JOIN storylines s ON s.id = wa.storyline_id
                {where}
                ORDER BY wa.created_at DESC
                LIMIT %s
            """, (limit,))
            alerts = []
            for r in cursor.fetchall():
                alerts.append({
                    "id": r[0], "storyline_id": r[1], "event_id": r[2],
                    "alert_type": r[3], "title": r[4], "body": r[5],
                    "is_read": r[6],
                    "created_at": r[7].isoformat() if r[7] else None,
                    "storyline_title": r[8],
                })
            return alerts
        finally:
            cursor.close()

    def mark_alert_read(self, alert_id: int) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE watchlist_alerts SET is_read = TRUE WHERE id = %s",
                (alert_id,),
            )
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to mark alert {alert_id} as read: {e}")
            return False
        finally:
            cursor.close()

    def mark_all_read(self) -> int:
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE watchlist_alerts SET is_read = TRUE WHERE is_read = FALSE")
            self.conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Alert generation (called by automation)
    # ------------------------------------------------------------------

    def generate_reactivation_alerts(self) -> int:
        """Create alerts for watched storylines that were recently reactivated."""
        cursor = self.conn.cursor()
        generated = 0
        try:
            cursor.execute("""
                SELECT w.id, w.storyline_id, s.title, s.reactivation_count
                FROM watchlist w
                JOIN storylines s ON s.id = w.storyline_id
                WHERE w.alert_on_reactivation = TRUE
                  AND s.status = 'active'
                  AND s.dormant_since IS NULL
                  AND s.reactivation_count > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM watchlist_alerts wa
                      WHERE wa.watchlist_id = w.id
                        AND wa.alert_type = 'reactivation'
                        AND wa.created_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
                  )
            """)
            for wid, sid, title, react_count in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO watchlist_alerts (watchlist_id, storyline_id, alert_type, title, body)
                    VALUES (%s, %s, 'reactivation', %s, %s)
                """, (wid, sid,
                      f"Storyline reactivated: {title}",
                      f"This storyline was dormant but new events were found (reactivation #{react_count})."))
                generated += 1

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Reactivation alert generation failed: {e}")
        finally:
            cursor.close()
        return generated

    def generate_new_event_alerts(self) -> int:
        """Create alerts for new events on watched storylines."""
        cursor = self.conn.cursor()
        generated = 0
        try:
            cursor.execute("""
                SELECT w.id, w.storyline_id, ce.id, ce.title, ce.event_type
                FROM watchlist w
                JOIN chronological_events ce ON ce.storyline_id = w.storyline_id::text
                WHERE ce.extraction_timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                  AND ce.canonical_event_id IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM watchlist_alerts wa
                      WHERE wa.event_id = ce.id AND wa.alert_type = 'new_event'
                  )
            """)
            for wid, sid, eid, etitle, etype in cursor.fetchall():
                cursor.execute("""
                    INSERT INTO watchlist_alerts (watchlist_id, storyline_id, event_id,
                                                 alert_type, title, body)
                    VALUES (%s, %s, %s, 'new_event', %s, %s)
                """, (wid, sid, eid,
                      f"New event: {etitle}",
                      f"A new {etype.replace('_', ' ')} event was detected for this storyline."))
                generated += 1

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"New event alert generation failed: {e}")
        finally:
            cursor.close()
        return generated

    # ------------------------------------------------------------------
    # Dashboard helpers
    # ------------------------------------------------------------------

    def get_story_activity_feed(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Recent storyline activity across all watched storylines."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT ce.id, ce.title, ce.event_type, ce.actual_event_date,
                       ce.storyline_id, s.title AS storyline_title,
                       ce.source_count, ce.extraction_timestamp
                FROM chronological_events ce
                JOIN storylines s ON s.id::text = ce.storyline_id
                WHERE ce.canonical_event_id IS NULL
                ORDER BY ce.extraction_timestamp DESC
                LIMIT %s
            """, (limit,))
            feed = []
            for r in cursor.fetchall():
                feed.append({
                    "event_id": r[0], "event_title": r[1], "event_type": r[2],
                    "event_date": r[3].isoformat() if r[3] else None,
                    "storyline_id": r[4], "storyline_title": r[5],
                    "source_count": r[6],
                    "detected_at": r[7].isoformat() if r[7] else None,
                })
            return feed
        finally:
            cursor.close()

    def get_dormant_story_alerts(self, days: int = 30) -> List[Dict[str, Any]]:
        """Watched storylines that have been dormant for N+ days."""
        cursor = self.conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cursor.execute("""
                SELECT s.id, s.title, s.dormant_since, s.total_events
                FROM storylines s
                JOIN watchlist w ON w.storyline_id = s.id
                WHERE s.status = 'dormant'
                  AND s.dormant_since < %s
                ORDER BY s.dormant_since ASC
            """, (cutoff,))
            return [
                {
                    "storyline_id": r[0], "title": r[1],
                    "dormant_since": r[2].isoformat() if r[2] else None,
                    "total_events": r[3] or 0,
                }
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()

    def get_coverage_gaps(self, days: int = 7) -> List[Dict[str, Any]]:
        """Active storylines that haven't had new sources recently."""
        cursor = self.conn.cursor()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cursor.execute("""
                SELECT s.id, s.title, s.last_event_at, s.total_events
                FROM storylines s
                WHERE s.status = 'active'
                  AND (s.last_event_at IS NULL OR s.last_event_at < %s)
                ORDER BY s.last_event_at ASC NULLS FIRST
                LIMIT 20
            """, (cutoff,))
            return [
                {
                    "storyline_id": r[0], "title": r[1],
                    "last_event_at": r[2].isoformat() if r[2] else None,
                    "total_events": r[3] or 0,
                }
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()

    def get_cross_domain_connections(self) -> List[Dict[str, Any]]:
        """Find storylines that share entities across different domains."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT a.storyline_id AS sid_a, b.storyline_id AS sid_b,
                       sa.title AS title_a, sb.title AS title_b,
                       ARRAY_AGG(DISTINCT a.entity_name) AS shared_entities
                FROM story_entity_index a
                JOIN story_entity_index b
                    ON LOWER(a.entity_name) = LOWER(b.entity_name)
                    AND a.storyline_id < b.storyline_id
                    AND a.is_core_entity = TRUE
                    AND b.is_core_entity = TRUE
                JOIN storylines sa ON sa.id = a.storyline_id
                JOIN storylines sb ON sb.id = b.storyline_id
                WHERE sa.status NOT IN ('archived', 'concluded')
                  AND sb.status NOT IN ('archived', 'concluded')
                GROUP BY a.storyline_id, b.storyline_id, sa.title, sb.title
                HAVING COUNT(DISTINCT a.entity_name) >= 2
                ORDER BY COUNT(DISTINCT a.entity_name) DESC
                LIMIT 20
            """)
            return [
                {
                    "storyline_a": {"id": r[0], "title": r[2]},
                    "storyline_b": {"id": r[1], "title": r[3]},
                    "shared_entities": r[4],
                }
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()
