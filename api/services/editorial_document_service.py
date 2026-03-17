"""
Editorial Document Service — generates and refines editorial_document on storylines
and editorial_briefing on tracked_events.

This is the MISSING LINK in the intelligence cascade (see docs/DATA_FLOW_ARCHITECTURE.md).
It transforms accumulated article intelligence into user-facing editorial narratives.

Pipeline phase: should run after storyline_processing and event_tracking, before digest_generation.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

EDITORIAL_DOC_TEMPLATE = {
    "lede": "",
    "developments": [],
    "analysis": "",
    "outlook": "",
    "key_entities": [],
    "sources": [],
    "generated_at": None,
    "based_on_articles": [],
}

EDITORIAL_BRIEFING_TEMPLATE = {
    "headline": "",
    "summary": "",
    "chronology": [],
    "impact": "",
    "what_next": "",
    "key_participants": [],
}


async def _llm_generate(prompt: str) -> Optional[str]:
    """Call LLM; returns text or None on failure."""
    try:
        from shared.services.llm_service import llm_service, TaskType
        result = await llm_service.generate_summary(prompt[:3000], task_type=TaskType.QUICK_SUMMARY)
        if result.get("success"):
            return (result.get("summary") or "").strip() or None
    except Exception as e:
        logger.debug("LLM call failed: %s", e)
    return None


async def generate_storyline_editorial(domain: str, limit: int = 10) -> Dict[str, Any]:
    """
    Generate or refine editorial_document for active storylines that need it.
    Returns stats on how many were processed.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "No DB connection"}

    schema = domain.replace("-", "_")
    processed = 0
    skipped = 0
    errors = 0

    try:
        cursor = conn.cursor()

        # Find storylines that need editorial work:
        # - editorial_document is empty/null, OR
        # - storyline updated since last refinement
        cursor.execute(f"""
            SELECT s.id, s.title, s.description, s.analysis_summary,
                   s.editorial_document, s.document_version, s.last_refinement,
                   s.updated_at
            FROM {schema}.storylines s
            WHERE s.status IN ('active', 'developing', 'ongoing')
              AND (
                  s.editorial_document IS NULL
                  OR s.editorial_document = '{{}}'::jsonb
                  OR s.updated_at > COALESCE(s.last_refinement, '1970-01-01'::timestamptz)
              )
            ORDER BY s.updated_at DESC
            LIMIT %s
        """, (limit,))

        storylines = cursor.fetchall()
        if not storylines:
            conn.close()
            return {"success": True, "processed": 0, "skipped": 0, "message": "No storylines need editorial work"}

        for row in storylines:
            sid, title, description, analysis_summary, existing_doc, doc_version, last_refined, updated_at = row
            try:
                # Use content_synthesis_service to gather ALL intelligence for this storyline
                from services.content_synthesis_service import synthesize_storyline_context, render_synthesis_for_llm
                synthesis = synthesize_storyline_context(domain, sid)
                articles_synth = synthesis.get("articles", [])

                if len(articles_synth) < 1:
                    skipped += 1
                    continue

                article_ids = [a["id"] for a in articles_synth]
                sources = list({a.get("source", "") for a in articles_synth if a.get("source")})

                # Build rich context from the full synthesis (articles + entities + claims + positions + documents)
                context_text = render_synthesis_for_llm(synthesis, max_chars=3500)

                is_new = not existing_doc or existing_doc == {}

                if is_new:
                    prompt = (
                        f"You are writing an editorial document for a news storyline titled \"{title}\".\n"
                        f"Description: {description or 'N/A'}\n\n"
                        f"Intelligence gathered:\n{context_text}\n\n"
                        "Write a JSON object with these fields:\n"
                        '- "lede": one-sentence summary of the most important development\n'
                        '- "developments": array of 2-4 short bullet points on what happened\n'
                        '- "analysis": 1-2 sentences on why this matters (reference entity stances or document findings if relevant)\n'
                        '- "outlook": 1 sentence on what to watch next\n'
                        "Respond with ONLY the JSON object, no markdown."
                    )
                else:
                    existing_lede = existing_doc.get("lede", "") if isinstance(existing_doc, dict) else ""
                    prompt = (
                        f"You are refining an editorial document for the storyline \"{title}\".\n"
                        f"Current lede: {existing_lede}\n\n"
                        f"Updated intelligence:\n{context_text}\n\n"
                        "Update the editorial document. Write a JSON object with:\n"
                        '- "lede": updated one-sentence summary\n'
                        '- "developments": array of 2-4 updated bullet points\n'
                        '- "analysis": 1-2 sentences on current significance (incorporate entity positions, document findings, and cross-domain connections if present)\n'
                        '- "outlook": 1 sentence on what to watch\n'
                        "Respond with ONLY the JSON object, no markdown."
                    )

                llm_text = await _llm_generate(prompt)
                if not llm_text:
                    skipped += 1
                    continue

                editorial = _parse_editorial_json(llm_text, title, article_ids, sources)

                new_version = (doc_version or 0) + 1
                cursor.execute(f"""
                    UPDATE {schema}.storylines
                    SET editorial_document = %s,
                        document_version = %s,
                        document_status = %s,
                        last_refinement = NOW()
                    WHERE id = %s
                """, (json.dumps(editorial), new_version, "refined" if not is_new else "draft", sid))
                processed += 1

            except Exception as e:
                logger.warning("Editorial generation failed for storyline %s: %s", sid, e)
                errors += 1

        conn.commit()
        conn.close()
        return {"success": True, "processed": processed, "skipped": skipped, "errors": errors}

    except Exception as e:
        logger.error("generate_storyline_editorial failed: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


async def generate_event_editorial(limit: int = 10) -> Dict[str, Any]:
    """
    Generate or refine editorial_briefing for tracked events that need it.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "No DB connection"}

    processed = 0
    skipped = 0
    errors = 0

    try:
        cursor = conn.cursor()

        # Events without editorial briefing, or updated since last briefing
        cursor.execute("""
            SELECT e.id, e.event_name, e.event_type, e.start_date, e.end_date,
                   e.geographic_scope, e.editorial_briefing, e.briefing_version,
                   e.last_briefing_update, e.domain_keys
            FROM intelligence.tracked_events e
            WHERE e.editorial_briefing IS NULL
               OR e.updated_at > COALESCE(e.last_briefing_update, '1970-01-01'::timestamptz)
            ORDER BY e.updated_at DESC
            LIMIT %s
        """, (limit,))

        events = cursor.fetchall()
        if not events:
            conn.close()
            return {"success": True, "processed": 0, "skipped": 0, "message": "No events need editorial work"}

        for row in events:
            eid, event_name, event_type, start_date, end_date, geo, existing_briefing, bversion, last_update, domain_keys = row
            try:
                # Get chronicles for this event
                cursor.execute("""
                    SELECT developments, analysis, predictions, update_date
                    FROM intelligence.event_chronicles
                    WHERE event_id = %s
                    ORDER BY update_date DESC
                    LIMIT 5
                """, (eid,))
                chronicles = cursor.fetchall()

                if not chronicles:
                    skipped += 1
                    continue

                chronicle_context = []
                for c in chronicles:
                    dev, ana, pred, cdate = c
                    parts = []
                    if cdate:
                        parts.append(f"Date: {cdate}")
                    if dev:
                        parts.append(f"Developments: {dev[:200]}")
                    if ana:
                        parts.append(f"Analysis: {ana[:150]}")
                    chronicle_context.append(" | ".join(parts))

                context_text = "\n".join(chronicle_context[:4])
                is_new = not existing_briefing

                prompt = (
                    f"You are writing an editorial briefing for the event \"{event_name}\" (type: {event_type}).\n"
                    f"Time span: {start_date or '?'} to {end_date or 'ongoing'}\n"
                    f"Geography: {geo or 'N/A'}\n\n"
                    f"Chronicles:\n{context_text}\n\n"
                    "Write a JSON object with:\n"
                    '- "headline": short headline for the event\n'
                    '- "summary": 2-3 sentence overview\n'
                    '- "impact": 1 sentence on why this event matters\n'
                    '- "what_next": 1 sentence on what to watch\n'
                    "Respond with ONLY the JSON object, no markdown."
                )

                llm_text = await _llm_generate(prompt)
                if not llm_text:
                    skipped += 1
                    continue

                briefing_json = _parse_briefing_json(llm_text, event_name)
                briefing_text = briefing_json.get("summary") or briefing_json.get("headline") or llm_text[:500]

                new_version = (bversion or 0) + 1
                cursor.execute("""
                    UPDATE intelligence.tracked_events
                    SET editorial_briefing = %s,
                        editorial_briefing_json = %s,
                        briefing_version = %s,
                        briefing_status = %s,
                        last_briefing_update = NOW()
                    WHERE id = %s
                """, (briefing_text, json.dumps(briefing_json), new_version,
                      "refined" if not is_new else "draft", eid))
                processed += 1

            except Exception as e:
                logger.warning("Editorial generation failed for event %s: %s", eid, e)
                errors += 1

        conn.commit()
        conn.close()
        return {"success": True, "processed": processed, "skipped": skipped, "errors": errors}

    except Exception as e:
        logger.error("generate_event_editorial failed: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _parse_editorial_json(llm_text: str, title: str, article_ids: List[int], sources: List[str]) -> dict:
    """Try to parse LLM output as editorial JSON; fall back to template with raw text."""
    try:
        cleaned = llm_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            result = {**EDITORIAL_DOC_TEMPLATE}
            result.update({
                "lede": parsed.get("lede", ""),
                "developments": parsed.get("developments", []),
                "analysis": parsed.get("analysis", ""),
                "outlook": parsed.get("outlook", ""),
                "key_entities": parsed.get("key_entities", []),
                "sources": sources,
                "generated_at": datetime.now().isoformat(),
                "based_on_articles": article_ids,
            })
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    return {
        **EDITORIAL_DOC_TEMPLATE,
        "lede": llm_text[:300],
        "sources": sources,
        "generated_at": datetime.now().isoformat(),
        "based_on_articles": article_ids,
    }


def _parse_briefing_json(llm_text: str, event_name: str) -> dict:
    """Try to parse LLM output as briefing JSON; fall back to template."""
    try:
        cleaned = llm_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            result = {**EDITORIAL_BRIEFING_TEMPLATE}
            result.update({
                "headline": parsed.get("headline", event_name),
                "summary": parsed.get("summary", ""),
                "impact": parsed.get("impact", ""),
                "what_next": parsed.get("what_next", ""),
                "key_participants": parsed.get("key_participants", []),
            })
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    return {
        **EDITORIAL_BRIEFING_TEMPLATE,
        "headline": event_name,
        "summary": llm_text[:300],
    }
