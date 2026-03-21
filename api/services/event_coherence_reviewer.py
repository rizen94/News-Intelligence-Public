"""
Event coherence reviewer — periodically reviews tracked events to ensure
each linked context actually belongs. Uses LLM to compare each context
against the event's core topic and removes mismatches.

Designed to be called by the automation_manager or newsroom orchestrator.
As events gain more contexts, the reviewer gets better signal for what
belongs and what doesn't.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

COHERENCE_PROMPT = """You are an intelligence analyst reviewing whether articles belong to a specific tracked event.

EVENT: {event_name}
EVENT TYPE: {event_type}
GEOGRAPHIC SCOPE: {event_scope}
EVENT SUMMARY: {event_summary}

For each article below, decide if it is DIRECTLY about this specific event.
A match means the article covers the SAME specific real-world happening, not just a loosely related topic.

Examples of what should NOT match:
- An article about a different country's legislature when the event is about a specific US congressman
- An article about general economic trends when the event is a specific trade deal
- An article mentioning similar keywords but covering a completely different story

ARTICLES:
{articles}

For each article, respond with a JSON array. Each entry has:
- "context_id": the article ID
- "relevant": true if it directly covers this event, false if it doesn't belong
- "confidence": 0.0 to 1.0 how confident you are
- "reason": brief explanation (max 30 words)

Respond with ONLY the JSON array, no other text:
[{{"context_id": 1, "relevant": true, "confidence": 0.95, "reason": "directly covers the event"}}]
"""


async def review_event_coherence(
    event_id: int,
    relevance_threshold: float = 0.5,
    auto_remove: bool = True,
) -> dict[str, Any]:
    """
    Review a single tracked event: ask the LLM whether each linked context
    actually belongs. Returns review results and optionally removes mismatches.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, geographic_scope
                FROM intelligence.tracked_events WHERE id = %s
            """,
                (event_id,),
            )
            ev_row = cur.fetchone()
            if not ev_row:
                conn.close()
                return {"error": "event_not_found"}

            event_name = ev_row[2]
            event_type = ev_row[1]
            event_scope = ev_row[3] or ""

            cur.execute(
                """
                SELECT ec.id, ec.developments, ec.analysis
                FROM intelligence.event_chronicles ec
                WHERE ec.event_id = %s
                ORDER BY ec.update_date DESC LIMIT 1
            """,
                (event_id,),
            )
            chron_row = cur.fetchone()
            if not chron_row:
                conn.close()
                return {"error": "no_chronicles", "event_id": event_id}

            chronicle_id = chron_row[0]
            developments = chron_row[1] or []
            analysis = chron_row[2] or {}
            event_summary = analysis.get("summary", "") if isinstance(analysis, dict) else ""

            context_ids = [
                d["context_id"] for d in developments if isinstance(d, dict) and d.get("context_id")
            ]
            if not context_ids:
                conn.close()
                return {"event_id": event_id, "reviewed": 0, "removed": 0}

            placeholders = ",".join(["%s"] * len(context_ids))
            cur.execute(
                f"""
                SELECT id, title, LEFT(content, 300) as snippet
                FROM intelligence.contexts
                WHERE id IN ({placeholders})
            """,
                tuple(context_ids),
            )
            ctx_rows = cur.fetchall()

        conn.close()
    except Exception as e:
        logger.error(f"review_event_coherence db read: {e}")
        _safe_close(conn)
        return {"error": str(e)}

    if len(ctx_rows) < 2:
        return {
            "event_id": event_id,
            "reviewed": len(ctx_rows),
            "removed": 0,
            "message": "Too few contexts to review",
        }

    articles_text = "\n".join(
        f"ID={r[0]} | {r[1] or '(no title)'} | {_strip_html(r[2] or '')}" for r in ctx_rows
    )

    prompt = COHERENCE_PROMPT.format(
        event_name=event_name,
        event_type=event_type,
        event_scope=event_scope,
        event_summary=event_summary,
        articles=articles_text,
    )

    llm = LLMService()
    try:
        raw = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
    except Exception as e:
        logger.error(f"review_event_coherence LLM: {e}")
        return {"error": f"LLM failed: {e}"}

    reviews = _parse_reviews(raw)
    if not reviews:
        return {
            "event_id": event_id,
            "reviewed": 0,
            "removed": 0,
            "message": "LLM returned no parseable reviews",
        }

    irrelevant_ids = []
    review_details = []
    for rev in reviews:
        cid = rev.get("context_id")
        relevant = rev.get("relevant", True)
        confidence = rev.get("confidence", 1.0)
        reason = rev.get("reason", "")

        if cid not in context_ids:
            continue

        is_match = relevant and confidence >= relevance_threshold
        review_details.append(
            {
                "context_id": cid,
                "relevant": relevant,
                "confidence": confidence,
                "reason": reason,
                "kept": is_match,
            }
        )
        if not is_match:
            irrelevant_ids.append(cid)

    removed = 0
    if auto_remove and irrelevant_ids:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    new_devs = [
                        d
                        for d in developments
                        if not (isinstance(d, dict) and d.get("context_id") in irrelevant_ids)
                    ]

                    kept_count = len(new_devs)
                    new_analysis = dict(analysis) if isinstance(analysis, dict) else {}
                    new_analysis["context_count"] = kept_count
                    new_analysis["last_coherence_review"] = datetime.now(timezone.utc).isoformat()
                    new_analysis["contexts_removed"] = irrelevant_ids

                    cur.execute(
                        """
                        UPDATE intelligence.event_chronicles
                        SET developments = %s, analysis = %s
                        WHERE id = %s
                    """,
                        (json.dumps(new_devs), json.dumps(new_analysis), chronicle_id),
                    )
                    removed = len(irrelevant_ids)

                    if kept_count < 2:
                        cur.execute(
                            """
                            UPDATE intelligence.tracked_events
                            SET end_date = CURRENT_DATE, updated_at = NOW()
                            WHERE id = %s AND end_date IS NULL
                        """,
                            (event_id,),
                        )
                        logger.info(f"Event {event_id} closed — too few contexts after review")

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"review_event_coherence update: {e}")
                _safe_close(conn)

    logger.info(
        f"Event coherence review #{event_id} '{event_name}': "
        f"reviewed {len(review_details)}, removed {removed}"
    )

    return {
        "event_id": event_id,
        "event_name": event_name,
        "reviewed": len(review_details),
        "removed": removed,
        "details": review_details,
    }


async def review_all_open_events(
    relevance_threshold: float = 0.5,
    auto_remove: bool = True,
) -> dict[str, Any]:
    """Review all open (no end_date) tracked events."""
    conn = get_db_connection()
    if not conn:
        return {"error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM intelligence.tracked_events
                WHERE end_date IS NULL
                ORDER BY id
            """)
            event_ids = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        _safe_close(conn)
        return {"error": str(e)}

    results = []
    total_removed = 0
    for eid in event_ids:
        r = await review_event_coherence(
            eid, relevance_threshold=relevance_threshold, auto_remove=auto_remove
        )
        results.append(r)
        total_removed += r.get("removed", 0)

    return {
        "events_reviewed": len(results),
        "total_contexts_removed": total_removed,
        "events": results,
    }


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_reviews(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _safe_close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
