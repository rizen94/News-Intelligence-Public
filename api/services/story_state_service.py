"""
Story state service — Phase 2 RAG. Tracks storyline state over time: maturity score,
knowledge gaps, change detection. Writes to intelligence.storyline_states.
See docs/RAG_ENHANCEMENT_ROADMAP.md.
"""

import json
import logging
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def compute_maturity_score(conn, domain_key: str, storyline_id: int) -> float:
    """
    Compute maturity score 0.0–1.0 from article count, entity index count, and recency.
    Uses domain schema for storylines and story_entity_index (and public fallback).
    """
    schema = _schema_for_domain(domain_key)
    score = 0.0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.article_count, s.updated_at,
                       (SELECT COUNT(*) FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id) AS sa_count
                FROM {schema}.storylines s
                WHERE s.id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
        if not row:
            return 0.0
        article_count, updated_at, sa_count = row[0], row[1], row[2]
        count = article_count if article_count is not None else (sa_count or 0)
        # 0.4 from article count (cap at ~10 articles)
        score += min(0.4, (count or 0) * 0.04)
        # 0.3 from entity index (try domain then public)
        for try_schema in (schema, "public"):
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {try_schema}.story_entity_index WHERE storyline_id = %s",
                        (storyline_id,),
                    )
                    ent_row = cur.fetchone()
                if ent_row and ent_row[0]:
                    score += min(0.3, ent_row[0] * 0.06)
                    break
            except Exception:
                continue
        # 0.3 from recency (updated_at in last 30 days)
        if updated_at:
            from datetime import datetime, timezone

            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            delta = (datetime.now(timezone.utc) - updated_at).days
            if delta <= 7:
                score += 0.3
            elif delta <= 30:
                score += 0.2
            elif delta <= 90:
                score += 0.1
    except Exception as e:
        logger.debug("compute_maturity_score %s/%s: %s", domain_key, storyline_id, e)
    return min(1.0, round(score, 2))


def detect_knowledge_gaps(conn, domain_key: str, storyline_id: int) -> list[str]:
    """
    Return knowledge gap descriptions from rules: few articles, no articles, or no recent coverage.
    Can be extended with LLM or more rules (e.g. missing entities).
    """
    gaps: list[str] = []
    try:
        with conn.cursor() as cur:
            schema = _schema_for_domain(domain_key)
            cur.execute(
                f"SELECT article_count FROM {schema}.storylines WHERE id = %s",
                (storyline_id,),
            )
            row = cur.fetchone()
        count = (row[0] or 0) if row else 0
        if count == 0:
            gaps.append("No articles linked yet; add articles to build the storyline.")
        elif count < 3:
            gaps.append("Few articles linked; add more coverage to improve understanding.")
        else:
            # Optional: no recent articles in last 7 days
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT MAX(a.created_at) FROM {schema}.articles a
                        INNER JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                        WHERE sa.storyline_id = %s
                        """,
                        (storyline_id,),
                    )
                    rec = cur.fetchone()
                if rec and rec[0]:
                    from datetime import datetime, timedelta, timezone

                    now = datetime.now(timezone.utc)
                    last_at = rec[0]
                    if getattr(last_at, "tzinfo", None) is None:
                        last_at = last_at.replace(tzinfo=timezone.utc)
                    if (now - last_at) > timedelta(days=7):
                        gaps.append(
                            "No new articles in the last 7 days; consider adding recent coverage."
                        )
            except Exception:
                pass
    except Exception:
        pass
    return gaps


def get_previous_state(conn, domain_key: str, storyline_id: int) -> dict[str, Any] | None:
    """Load latest storyline_states row for (domain_key, storyline_id)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, version, state_summary, maturity_score, knowledge_gaps, created_at
                FROM intelligence.storyline_states
                WHERE domain_key = %s AND storyline_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (domain_key, storyline_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "version": row[1],
            "state_summary": row[2],
            "maturity_score": float(row[3]) if row[3] is not None else None,
            "knowledge_gaps": row[4]
            if isinstance(row[4], list)
            else (json.loads(row[4]) if row[4] else []),
            "created_at": row[5],
        }
    except Exception as e:
        logger.debug("get_previous_state: %s", e)
        return None


def update_story_state(
    domain_key: str,
    storyline_id: int,
    state_summary: str | None = None,
    significant_change: bool = False,
    change_summary: str | None = None,
) -> bool:
    """
    Compute maturity and knowledge gaps, optionally detect change vs previous state,
    and insert a new row into intelligence.storyline_states.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        maturity = compute_maturity_score(conn, domain_key, storyline_id)
        gaps = detect_knowledge_gaps(conn, domain_key, storyline_id)
        prev = get_previous_state(conn, domain_key, storyline_id)
        version = (prev["version"] + 1) if prev else 1
        is_significant = significant_change
        change_text = change_summary
        if prev and not change_text:
            if maturity != (prev.get("maturity_score") or 0):
                is_significant = True
                change_text = f"Maturity {prev.get('maturity_score') or 0:.2f} → {maturity:.2f}"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.storyline_states
                (domain_key, storyline_id, version, state_summary, maturity_score, knowledge_gaps, significant_change, change_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    domain_key,
                    storyline_id,
                    version,
                    state_summary or "",
                    maturity,
                    json.dumps(gaps),
                    is_significant,
                    change_text or "",
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        logger.warning("update_story_state %s/%s: %s", domain_key, storyline_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()
