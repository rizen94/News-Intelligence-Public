"""
Event tracking service — groups contexts into tracked events using LLM analysis.
Populates intelligence.tracked_events and intelligence.event_chronicles.
"""

import json
import logging
import re
from datetime import date
from typing import Any, TypedDict

from shared.services.llm_service import LLMService, ModelType

from services.commodity_event_bridge import maybe_append_finance_domain_key

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
    "conflict",
    "election",
    "legislation",
    "investigation",
    "diplomatic",
    "economic",
    "disaster",
    "protest",
    "policy",
    "appointment",
    "other",
    "market_shift",
    "government_bond",
    "regulatory",
}

_MAX_KEY_PARTICIPANTS = 20


def _domain_key_to_schema(domain_key: str) -> str:
    from shared.domain_registry import domain_key_to_schema

    try:
        return domain_key_to_schema(domain_key)
    except KeyError:
        return (domain_key or "").replace("-", "_")


def _active_schema_set() -> frozenset[str]:
    from shared.domain_registry import get_pipeline_schema_names_active

    return frozenset(get_pipeline_schema_names_active())


def _resolve_context_ids_to_entity_profile_ids(conn, context_ids: list[int]) -> list[int]:
    """
    Resolve context IDs to up to _MAX_KEY_PARTICIPANTS unique entity_profile IDs.
    Uses article_to_context -> domain article_entities -> entity_profiles.
    """
    if not context_ids:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT article_id, domain_key FROM intelligence.article_to_context WHERE context_id = ANY(%s)",
                (context_ids,),
            )
            article_domain_pairs = cur.fetchall()
        if not article_domain_pairs:
            return []

        # Group article_ids by domain_key so we can query each schema once
        by_domain: dict[str, list[int]] = {}
        for article_id, dk in article_domain_pairs:
            if dk not in by_domain:
                by_domain[dk] = []
            by_domain[dk].append(article_id)

        canonical_pairs: set = set()
        for domain_key, article_ids in by_domain.items():
            schema = _domain_key_to_schema(domain_key)
            if schema not in _active_schema_set():
                continue
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT article_id, canonical_entity_id FROM {schema}.article_entities WHERE article_id = ANY(%s)",
                    (list(set(article_ids)),),
                )
                for _aid, cid in cur.fetchall():
                    canonical_pairs.add((domain_key, cid))

        if not canonical_pairs:
            return []
        pairs = list(canonical_pairs)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM intelligence.entity_profiles WHERE (domain_key, canonical_entity_id) IN %s",
                (tuple(pairs),),
            )
            profile_ids = [r[0] for r in cur.fetchall()]
        return list(dict.fromkeys(profile_ids))[:_MAX_KEY_PARTICIPANTS]
    except Exception as e:
        logger.debug("_resolve_context_ids_to_entity_profile_ids: %s", e)
        return []


class DiscoverEventsResult(TypedDict, total=False):
    """Result schema for discover_events_from_contexts."""

    error: str
    events_created: int
    events: list[dict[str, Any]]
    message: str


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


async def discover_events_from_contexts(
    domain_key: str | None = None, limit: int = 100
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
                cur.execute(
                    """
                    SELECT c.id, c.title, c.content, c.domain_key, c.metadata, c.created_at
                    FROM intelligence.contexts c
                    WHERE c.domain_key = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                      )
                    ORDER BY c.created_at DESC
                    LIMIT %s
                """,
                    (domain_key, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.content, c.domain_key, c.metadata, c.created_at
                    FROM intelligence.contexts c
                    WHERE NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                    )
                    ORDER BY c.created_at DESC
                    LIMIT %s
                """,
                    (limit,),
                )
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
        f"ID={r[0]} | {r[1] or '(no title)'} | {_strip_html((r[2] or '')[:600])}" for r in rows
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
    elif domain_key and domain_key != "finance":
        domain_hint = (
            "\n\nIf the story materially affects global commodities, energy, shipping chokepoints, critical minerals, "
            "sanctions, or major macro markets, state that clearly in geographic_scope or summary "
            "(e.g. oil/LNG, straits, OPEC, gold mining, tariffs) so cross-domain finance maps can surface it."
        )

    prompt = (
        EVENT_GROUPING_PROMPT.format(articles=articles_text, domain_hint=domain_hint)
        + existing_note
    )

    llm = LLMService()
    try:
        raw_response = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
    except Exception as e:
        logger.error(f"discover_events: LLM call failed: {e}")
        return {"error": f"LLM failed: {e}"}

    events = _parse_llm_events(raw_response)
    logger.info("discover_events: LLM proposed %d events from %d contexts", len(events), len(rows))
    for ev in events:
        logger.info(
            "  proposed: %s (%s)", ev.get("event_name", "?")[:60], ev.get("event_type", "?")
        )
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

                dates = [
                    context_dates[cid]
                    for cid in valid_ids
                    if cid in context_dates and context_dates[cid]
                ]
                start = min(dates).date() if dates else date.today()

                cur.execute(
                    """
                    SELECT id FROM intelligence.tracked_events
                    WHERE event_type = %s
                      AND (
                        lower(trim(event_name)) = lower(trim(%s))
                        OR (
                          length(trim(%s)) >= 8
                          AND (
                            lower(trim(event_name)) LIKE %s
                            OR lower(trim(%s)) LIKE '%%' || lower(trim(event_name)) || '%%'
                          )
                        )
                      )
                      AND (
                        start_date IS NULL
                        OR start_date BETWEEN (%s::date - INTERVAL '7 days') AND (%s::date + INTERVAL '7 days')
                      )
                    LIMIT 1
                """,
                    (
                        event_type,
                        event_name,
                        event_name,
                        f"%{event_name[:80].strip().lower()}%",
                        event_name[:80],
                        start,
                        start,
                    ),
                )
                if cur.fetchone():
                    continue

                if domain_key:
                    domains = [domain_key]
                else:
                    domains = list(
                        {
                            context_id_to_domain[cid]
                            for cid in valid_ids
                            if cid in context_id_to_domain
                        }
                    )

                # Build initial editorial briefing from LLM summary
                initial_briefing = summary[:500] if summary else None
                initial_briefing_json = (
                    json.dumps(
                        {
                            "headline": event_name,
                            "summary": summary or "",
                            "impact": "",
                            "what_next": "",
                            "key_participants": [],
                        }
                    )
                    if summary
                    else None
                )

                cur.execute(
                    """
                    INSERT INTO intelligence.tracked_events
                    (event_type, event_name, start_date, geographic_scope,
                     key_participant_entity_ids, milestones, domain_keys,
                     editorial_briefing, editorial_briefing_json,
                     briefing_version, briefing_status)
                    VALUES (%s, %s, %s, %s, '[]', '[]', %s, %s, %s, 1, 'draft')
                    RETURNING id
                """,
                    (
                        event_type,
                        event_name,
                        start,
                        geo,
                        domains,
                        initial_briefing,
                        initial_briefing_json,
                    ),
                )
                event_id = cur.fetchone()[0]

                developments = [{"context_id": cid, "type": "initial"} for cid in valid_ids]
                analysis = {"summary": summary, "context_count": len(valid_ids)}

                cur.execute(
                    """
                    INSERT INTO intelligence.event_chronicles
                    (event_id, update_date, developments, analysis, predictions, momentum_score)
                    VALUES (%s, %s, %s, %s, '[]', %s)
                """,
                    (
                        event_id,
                        date.today(),
                        json.dumps(developments),
                        json.dumps(analysis),
                        min(1.0, len(valid_ids) * 0.15),
                    ),
                )

                # Auto-populate key_participant_entity_ids from contexts linked to this event
                profile_ids = _resolve_context_ids_to_entity_profile_ids(conn, valid_ids)
                if profile_ids:
                    cur.execute(
                        "UPDATE intelligence.tracked_events SET key_participant_entity_ids = %s WHERE id = %s",
                        (json.dumps(profile_ids), event_id),
                    )

                maybe_append_finance_domain_key(
                    conn, event_id, event_name, geo, summary or "", domains
                )

                created_events.append(
                    {
                        "event_id": event_id,
                        "event_name": event_name,
                        "event_type": event_type,
                        "context_count": len(valid_ids),
                    }
                )

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


def _backfill_key_participants_for_event(conn, event_id: int) -> bool:
    """
    Populate key_participant_entity_ids for an existing event from its chronicle developments.
    Returns True if updated.
    """
    context_ids: list[int] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT developments FROM intelligence.event_chronicles WHERE event_id = %s",
                (event_id,),
            )
            for (dev_json,) in cur.fetchall() or []:
                if not dev_json:
                    continue
                try:
                    devs = dev_json if isinstance(dev_json, list) else json.loads(dev_json)
                    for d in devs:
                        cid = d.get("context_id") if isinstance(d, dict) else None
                        if cid is not None:
                            context_ids.append(int(cid))
                except (TypeError, ValueError, KeyError):
                    pass
        context_ids = list(dict.fromkeys(context_ids))
        if not context_ids:
            return False
        profile_ids = _resolve_context_ids_to_entity_profile_ids(conn, context_ids)
        if not profile_ids:
            return False
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE intelligence.tracked_events SET key_participant_entity_ids = %s WHERE id = %s",
                (json.dumps(profile_ids), event_id),
            )
        return True
    except Exception as e:
        logger.debug("_backfill_key_participants_for_event(%s): %s", event_id, e)
        return False


def backfill_key_participants_for_tracked_events(limit: int = 30) -> int:
    """
    Backfill key_participant_entity_ids for events that have none.
    Call from automation after event_tracking batch. Returns number of events updated.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.tracked_events
                WHERE key_participant_entity_ids IS NULL
                   OR key_participant_entity_ids = '[]'
                   OR key_participant_entity_ids = 'null'
                ORDER BY id DESC
                LIMIT %s
            """,
                (limit,),
            )
            event_ids = [r[0] for r in cur.fetchall()]
        for eid in event_ids:
            if _backfill_key_participants_for_event(conn, eid):
                updated += 1
        if updated:
            conn.commit()
            logger.info("backfill_key_participants: %d events updated", updated)
    except Exception as e:
        logger.debug("backfill_key_participants_for_tracked_events: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return updated


def link_tracked_events_to_storylines(limit: int = 50) -> int:
    """
    Set tracked_events.storyline_id by entity overlap: for each event with
    key_participant_entity_ids but no storyline_id, find a storyline in the same
    domain whose articles mention the same entities; set storyline_id = 'schema:id'.
    Returns number of events linked.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0
    linked = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(key_participant_entity_ids, '[]'::jsonb) as profile_ids
                FROM intelligence.tracked_events
                WHERE storyline_id IS NULL
                  AND key_participant_entity_ids IS NOT NULL
                  AND jsonb_array_length(COALESCE(key_participant_entity_ids, '[]'::jsonb)) > 0
                ORDER BY id DESC
                LIMIT %s
            """,
                (limit,),
            )
            rows = cur.fetchall()
        if not rows:
            conn.close()
            return 0

        for event_id, profile_ids_json in rows:
            try:
                profile_ids = (
                    json.loads(profile_ids_json)
                    if isinstance(profile_ids_json, str)
                    else (profile_ids_json or [])
                )
                profile_ids = [int(x) for x in profile_ids if isinstance(x, (int, float))]
                if not profile_ids:
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT domain_key, canonical_entity_id FROM intelligence.entity_profiles WHERE id = ANY(%s)",
                        (profile_ids,),
                    )
                    domain_canonicals = cur.fetchall()
                if not domain_canonicals:
                    continue
                # Group by domain: domain_key -> set of canonical_entity_id
                by_domain: dict[str, list[int]] = {}
                for dk, cid in domain_canonicals:
                    if dk not in by_domain:
                        by_domain[dk] = []
                    by_domain[dk].append(cid)
                best_schema = None
                best_storyline_id = None
                best_overlap = 0
                for domain_key, canonical_ids in by_domain.items():
                    schema = _domain_key_to_schema(domain_key)
                    if schema not in _active_schema_set():
                        continue
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT s.id, COUNT(DISTINCT ae.canonical_entity_id) AS overlap
                            FROM {schema}.storylines s
                            JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
                            JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                            WHERE ae.canonical_entity_id = ANY(%s)
                            GROUP BY s.id
                            ORDER BY overlap DESC
                            LIMIT 1
                            """,
                            (list(set(canonical_ids)),),
                        )
                        row = cur.fetchone()
                    if row and row[1] and row[1] > best_overlap:
                        best_overlap = row[1]
                        best_schema = schema
                        best_storyline_id = row[0]
                if best_schema and best_storyline_id is not None:
                    storyline_id_val = f"{best_schema}:{best_storyline_id}"
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE intelligence.tracked_events SET storyline_id = %s WHERE id = %s",
                            (storyline_id_val, event_id),
                        )
                    linked += 1
                    logger.debug(
                        "link_tracked_events_to_storylines: event %s -> %s",
                        event_id,
                        storyline_id_val,
                    )
            except Exception as e:
                logger.debug("link_tracked_events_to_storylines event %s: %s", event_id, e)
                continue
        conn.commit()
    except Exception as e:
        logger.debug("link_tracked_events_to_storylines: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return linked


async def run_event_tracking_batch(limit: int = 300) -> int:
    """
    Batch wrapper called by the automation manager.
    Discovers new events per domain (unlinked contexts in batches of 30), then updates
    chronicles for existing events. Run every 15 min with limit=300 to drain backlog.
    Returns total number of chronicle entries added.
    """
    batch_size = 30  # small enough for 8B model to return valid JSON
    created_total = 0
    from shared.domain_registry import get_active_domain_keys

    for domain in get_active_domain_keys():
        for offset in range(0, limit, batch_size):
            result = await discover_events_from_contexts(domain_key=domain, limit=batch_size)
            created_total += result.get("events_created", 0)
            if result.get("error"):
                logger.warning("run_event_tracking_batch(%s): %s", domain, result["error"])
                break
            if result.get("message", "").startswith("No unlinked"):
                break

    updated = await _update_existing_event_chronicles(limit=limit)
    # Backfill key_participant_entity_ids for existing events that have none
    backfilled = backfill_key_participants_for_tracked_events(limit=30)
    # Bridge tracked_events to storylines via entity overlap (Phase 2B)
    linked = link_tracked_events_to_storylines(limit=50)
    total = created_total + updated
    if total > 0 or backfilled > 0 or linked > 0:
        logger.info(
            "run_event_tracking_batch: %d new events, %d chronicle updates, %d participant backfills, %d storyline links",
            created_total,
            updated,
            backfilled,
            linked,
        )
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
            cur.execute(
                """
                SELECT te.id, te.event_name, te.event_type,
                       COALESCE(te.domain_keys, '{}') as domain_keys,
                       COALESCE(te.key_participant_entity_ids, '[]'::jsonb) as key_participant_entity_ids,
                       (SELECT MAX(ec.update_date) FROM intelligence.event_chronicles ec WHERE ec.event_id = te.id) as last_update
                FROM intelligence.tracked_events te
                ORDER BY te.id DESC
                LIMIT %s
            """,
                (limit,),
            )
            events = cur.fetchall()

        if not events:
            conn.close()
            return 0

        updates = 0
        for (
            event_id,
            event_name,
            event_type,
            domain_keys,
            participant_ids_json,
            last_update,
        ) in events:
            # Build search terms: significant words (len >= 4) from event name, up to 3
            words = [w for w in re.split(r"\W+", (event_name or "")) if len(w) >= 4][:3]
            if not words:
                words = [(event_name or "")[:50].strip() or " "]
            # Match contexts that contain any of these terms in title or content, or that mention key participants
            ilike_conditions = " OR ".join(
                ["(c.title ILIKE %s OR c.content ILIKE %s)"] * len(words)
            )
            params: list = [last_update]
            for w in words:
                params.append(f"%{w}%")
                params.append(f"%{w}%")
            participant_ids: list = []
            if participant_ids_json and isinstance(participant_ids_json, list):
                participant_ids = [
                    int(x) for x in participant_ids_json if isinstance(x, (int, float))
                ]
            elif isinstance(participant_ids_json, str):
                try:
                    participant_ids = json.loads(participant_ids_json)
                    participant_ids = [
                        int(x) for x in participant_ids if isinstance(x, (int, float))
                    ]
                except Exception:
                    pass
            if participant_ids:
                ilike_conditions += " OR c.id IN (SELECT context_id FROM intelligence.context_entity_mentions WHERE entity_profile_id = ANY(%s))"
                params.append(participant_ids)
            params.append(event_id)

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.id, c.title, LEFT(c.content, 400)
                    FROM intelligence.contexts c
                    WHERE c.created_at > COALESCE(%s, '2020-01-01'::date)
                      AND ({ilike_conditions})
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.event_id = %s
                            AND ec.developments::text LIKE '%%"context_id": ' || c.id || '%%'
                      )
                    LIMIT 10
                    """,
                    tuple(params),
                )
                new_contexts = cur.fetchall()

            if new_contexts:
                developments = [
                    {
                        "context_id": c[0],
                        "type": "update",
                        "title": c[1],
                        "excerpt": (c[2] or "")[:200],
                    }
                    for c in new_contexts
                ]

                # Build on prior analysis instead of starting empty
                prior_analysis = {}
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT analysis FROM intelligence.event_chronicles
                        WHERE event_id = %s ORDER BY update_date DESC LIMIT 1
                    """,
                        (event_id,),
                    )
                    prev = cur.fetchone()
                    if prev and prev[0] and isinstance(prev[0], dict):
                        prior_analysis = prev[0]

                new_titles = [c[1] for c in new_contexts if c[1]]
                analysis = {
                    "summary": prior_analysis.get("summary", ""),
                    "context_count": prior_analysis.get("context_count", 0) + len(new_contexts),
                    "latest_developments": "; ".join(new_titles[:5]),
                    "prior_analysis_carried_forward": True,
                }

                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO intelligence.event_chronicles
                        (event_id, update_date, developments, analysis, predictions, momentum_score)
                        VALUES (%s, CURRENT_DATE, %s, %s, '[]', %s)
                    """,
                        (
                            event_id,
                            json.dumps(developments),
                            json.dumps(analysis),
                            min(1.0, len(new_contexts) * 0.1),
                        ),
                    )
                updates += 1
                try:
                    from services.tracked_event_narrative_service import (
                        refresh_domain_keys_for_tracked_event,
                    )

                    refresh_domain_keys_for_tracked_event(conn, event_id)
                    with conn.cursor() as ucur:
                        ucur.execute(
                            """
                            UPDATE intelligence.tracked_events
                            SET updated_at = NOW()
                            WHERE id = %s
                            """,
                            (event_id,),
                        )
                except Exception as ex:
                    logger.debug("refresh_domain_keys after chronicle: %s", ex)

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


def _parse_llm_events(raw: str) -> list[dict[str, Any]]:
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
    candidate = text[start : end + 1] if end > start else text[start:]

    # First try: parse the full array
    try:
        data = json.loads(candidate)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Second try: the response may be truncated — try to recover individual objects
    recovered = []
    for m in re.finditer(r"\{[^{}]*\}", candidate):
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
