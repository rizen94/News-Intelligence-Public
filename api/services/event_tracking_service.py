"""
Event tracking service — groups contexts into tracked events using LLM analysis.
Populates intelligence.tracked_events and intelligence.event_chronicles.
"""

import json
import logging
import asyncio
from datetime import date
from typing import List, Dict, Any, Optional, TypedDict

from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

EVENT_GROUPING_PROMPT = """You are a news intelligence analyst. Given these article headlines and summaries, identify the distinct real-world EVENTS they describe.

An "event" is a specific, trackable happening — not a vague topic. Examples:
- GOOD: "US-Israel military strikes on Iran (March 2026)"
- GOOD: "California congressional redistricting and retirements"
- BAD: "politics" (too vague)
- BAD: "news" (not an event)

Group related articles by the event they cover. Each event needs:
- event_name: Clear, specific name (max 200 chars)
- event_type: One of: conflict, election, legislation, investigation, diplomatic, economic, disaster, protest, policy, appointment, market_shift, government_bond, regulatory, other
- geographic_scope: Where it's happening (e.g. "Iran, Israel", "California, USA", "India", "US", "EU")
- article_ids: List of article context IDs that belong to this event
- summary: 1-2 sentence description of what's happening

Articles may belong to zero events (if unrelated noise) or exactly one event.
Only create an event if at least 2 articles are about the same happening.

ARTICLES:
{articles}
{domain_hint}

Respond with valid JSON only — an array of event objects:
[
  {{
    "event_name": "...",
    "event_type": "...",
    "geographic_scope": "...",
    "article_ids": [1, 2, 3],
    "summary": "..."
  }}
]
"""

VALID_EVENT_TYPES = {
    "conflict", "election", "legislation", "investigation", "diplomatic",
    "economic", "disaster", "protest", "policy", "appointment", "other",
    "market_shift", "government_bond", "regulatory",
}


class DiscoverEventsResult(TypedDict, total=False):
    """Result schema for discover_events_from_contexts."""

    error: str
    events_created: int
    events: List[Dict[str, Any]]
    message: str


def _strip_html(text: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', text).strip()


async def discover_events_from_contexts(
    domain_key: Optional[str] = None, limit: int = 100
) -> DiscoverEventsResult:
    """
    Analyze recent contexts and create tracked events from clusters.
    Returns summary of events created.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return {"error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            # Fetch existing event names so we can tell the LLM to find NEW events only
            cur.execute("SELECT event_name FROM intelligence.tracked_events")
            existing_events = [r[0] for r in cur.fetchall()]

            # Only analyze contexts not already linked to an event chronicle
            if domain_key:
                cur.execute("""
                    SELECT c.id, c.title, c.content, c.domain_key, c.metadata, c.created_at
                    FROM intelligence.contexts c
                    WHERE c.domain_key = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                      )
                    ORDER BY c.created_at DESC
                    LIMIT %s
                """, (domain_key, limit))
            else:
                cur.execute("""
                    SELECT c.id, c.title, c.content, c.domain_key, c.metadata, c.created_at
                    FROM intelligence.contexts c
                    WHERE NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                    )
                    ORDER BY c.created_at DESC
                    LIMIT %s
                """, (limit,))
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"discover_events: DB query failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return {"error": str(e)}

    if not rows:
        return {"events_created": 0, "message": "No unlinked contexts to analyze"}

    articles_text = "\n".join(
        f"ID={r[0]} | {r[1] or '(no title)'} | {_strip_html((r[2] or '')[:200])}"
        for r in rows
    )

    existing_note = ""
    if existing_events:
        existing_note = (
            "\n\nEVENTS ALREADY TRACKED (do NOT re-create these, find NEW events only):\n"
            + "\n".join(f"- {e}" for e in existing_events)
            + "\n"
        )

    domain_hint = ""
    if domain_key == "finance":
        domain_hint = (
            "\n\nThis batch is FINANCE content. Prefer event_type: market_shift (major indices, volatility, rate moves), "
            "government_bond (treasury, sovereign debt, yield moves), regulatory (SEC, Fed, enforcement), or investigation "
            "(corporate probes, fraud, DOJ). Name events specifically (e.g. 'Fed rate decision March 2026', 'SEC investigation into X')."
        )

    prompt = EVENT_GROUPING_PROMPT.format(articles=articles_text, domain_hint=domain_hint) + existing_note

    llm = LLMService()
    try:
        raw_response = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
    except Exception as e:
        logger.error(f"discover_events: LLM call failed: {e}")
        return {"error": f"LLM failed: {e}"}

    events = _parse_llm_events(raw_response)
    logger.info("discover_events: LLM proposed %d events from %d contexts", len(events), len(rows))
    for ev in events:
        logger.info("  proposed: %s (%s)", ev.get("event_name", "?")[:60], ev.get("event_type", "?"))
    if not events:
        return {"events_created": 0, "message": "LLM returned no valid events"}

    context_ids_set = {r[0] for r in rows}
    context_dates = {r[0]: r[5] for r in rows}
    context_id_to_domain = {r[0]: r[3] for r in rows if r[3]}

    created_events = []
    conn = get_db_connection()
    if not conn:
        return {"error": "no_db_connection for insert"}

    try:
        with conn.cursor() as cur:
            for ev in events:
                valid_ids = [aid for aid in ev.get("article_ids", []) if aid in context_ids_set]
                if len(valid_ids) < 2:
                    continue

                event_name = ev.get("event_name", "Unnamed Event")[:300]
                event_type = ev.get("event_type", "other")
                if event_type not in VALID_EVENT_TYPES:
                    event_type = "other"
                geo = ev.get("geographic_scope", "")[:100]
                summary = ev.get("summary", "")

                dates = [context_dates[cid] for cid in valid_ids if cid in context_dates and context_dates[cid]]
                start = min(dates).date() if dates else date.today()

                cur.execute("""
                    SELECT id FROM intelligence.tracked_events
                    WHERE (event_name = %s OR event_name ILIKE %s) AND event_type = %s
                """, (event_name, f'%{event_name[:40]}%', event_type))
                if cur.fetchone():
                    continue

                if domain_key:
                    domains = [domain_key]
                else:
                    domains = list({context_id_to_domain[cid] for cid in valid_ids if cid in context_id_to_domain})
                cur.execute("""
                    INSERT INTO intelligence.tracked_events
                    (event_type, event_name, start_date, geographic_scope, key_participant_entity_ids, milestones, domain_keys)
                    VALUES (%s, %s, %s, %s, '[]', '[]', %s)
                    RETURNING id
                """, (event_type, event_name, start, geo, domains))
                event_id = cur.fetchone()[0]

                developments = [{"context_id": cid, "type": "initial"} for cid in valid_ids]
                analysis = {"summary": summary, "context_count": len(valid_ids)}

                cur.execute("""
                    INSERT INTO intelligence.event_chronicles
                    (event_id, update_date, developments, analysis, predictions, momentum_score)
                    VALUES (%s, %s, %s, %s, '[]', %s)
                """, (
                    event_id,
                    date.today(),
                    json.dumps(developments),
                    json.dumps(analysis),
                    min(1.0, len(valid_ids) * 0.15),
                ))

                created_events.append({
                    "event_id": event_id,
                    "event_name": event_name,
                    "event_type": event_type,
                    "context_count": len(valid_ids),
                })

        conn.commit()
        conn.close()
        logger.info(f"discover_events: created {len(created_events)} events")
        return {"events_created": len(created_events), "events": created_events}
    except Exception as e:
        logger.error(f"discover_events: insert failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"error": str(e)}


# Domains that have contexts and should get event discovery batches.
EVENT_DISCOVERY_DOMAINS = ("politics", "finance", "science_tech")


async def run_event_tracking_batch(limit: int = 50) -> int:
    """
    Batch wrapper called by the automation manager.
    Discovers new events per domain (so finance/politics/science_tech get correct domain_keys),
    then updates chronicles for existing ones.
    Returns total number of chronicle entries added.
    """
    batch_size = 30  # small enough for 8B model to return valid JSON
    created_total = 0
    for domain in EVENT_DISCOVERY_DOMAINS:
        for offset in range(0, limit, batch_size):
            result = await discover_events_from_contexts(domain_key=domain, limit=batch_size)
            created_total += result.get("events_created", 0)
            if result.get("error"):
                logger.warning("run_event_tracking_batch(%s): %s", domain, result["error"])
                break
            if result.get("message", "").startswith("No unlinked"):
                break

    updated = await _update_existing_event_chronicles(limit=limit)
    total = created_total + updated
    if total > 0:
        logger.info("run_event_tracking_batch: %d new events, %d chronicle updates", created_total, updated)
    return total


async def _update_existing_event_chronicles(limit: int = 20) -> int:
    """
    For existing tracked_events, check for new contexts that match
    and append chronicle entries.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT te.id, te.event_name, te.event_type,
                       COALESCE(te.domain_keys, '{}') as domain_keys,
                       (SELECT MAX(ec.update_date) FROM intelligence.event_chronicles ec WHERE ec.event_id = te.id) as last_update
                FROM intelligence.tracked_events te
                ORDER BY te.id DESC
                LIMIT %s
            """, (limit,))
            events = cur.fetchall()

        if not events:
            conn.close()
            return 0

        updates = 0
        for event_id, event_name, event_type, domain_keys, last_update in events:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.id, c.title
                    FROM intelligence.contexts c
                    WHERE c.created_at > COALESCE(%s, '2020-01-01'::date)
                      AND (c.title ILIKE %s OR c.content ILIKE %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.event_id = %s
                            AND ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                      )
                    LIMIT 10
                """, (last_update, f'%{event_name[:30]}%', f'%{event_name[:30]}%', event_id))
                new_contexts = cur.fetchall()

            if new_contexts:
                developments = [{"context_id": c[0], "type": "update", "title": c[1]} for c in new_contexts]
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO intelligence.event_chronicles
                        (event_id, update_date, developments, analysis, predictions, momentum_score)
                        VALUES (%s, CURRENT_DATE, %s, '{}', '[]', %s)
                    """, (event_id, json.dumps(developments), min(1.0, len(new_contexts) * 0.1)))
                updates += 1

        conn.commit()
        conn.close()
        return updates

    except Exception as e:
        logger.warning("_update_existing_event_chronicles: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return 0


def _parse_llm_events(raw: str) -> List[Dict[str, Any]]:
    """Extract JSON array of events from LLM response, tolerant of markdown fences and truncation."""
    import re
    text = raw.strip()

    # Strip markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break

    start = text.find("[")
    if start == -1:
        logger.warning("discover_events: no JSON array found in LLM response")
        return []

    end = text.rfind("]")
    candidate = text[start:end + 1] if end > start else text[start:]

    # First try: parse the full array
    try:
        data = json.loads(candidate)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Second try: the response may be truncated — try to recover individual objects
    recovered = []
    for m in re.finditer(r'\{[^{}]*\}', candidate):
        try:
            obj = json.loads(m.group())
            if "event_name" in obj:
                recovered.append(obj)
        except json.JSONDecodeError:
            continue

    if recovered:
        logger.info("discover_events: recovered %d events from malformed JSON", len(recovered))
        return recovered

    logger.warning("discover_events: could not parse LLM response (%d chars)", len(raw))
    return []
