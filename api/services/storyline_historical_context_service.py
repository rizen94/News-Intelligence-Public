"""
Storyline historical memory — durable context for long-arc narratives.

Separates **memory** (query on demand from versioned_facts, chronological_events,
story_entity_index, articles) from the **hot queue** (fact_change_log / story_update_queue).

Consumers: content_synthesis, narrative finisher, narrative_synthesis, story_state snapshots.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

_CHRONO_EVENTS = "public.chronological_events"


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(env_str(name, str(default)))))
    except (TypeError, ValueError):
        return default


def _schema(domain_key: str) -> str:
    return resolve_domain_schema(domain_key)


def _load_storyline_entities(cur, schema: str, storyline_id: int) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        cur.execute(
            f"""
            SELECT entity_name, entity_type, mention_count
            FROM {schema}.story_entity_index
            WHERE storyline_id = %s
            ORDER BY mention_count DESC NULLS LAST, entity_name ASC
            """,
            (storyline_id,),
        )
        for name, etype, mc in cur.fetchall():
            n = (name or "").strip()
            if not n:
                continue
            key = n.lower()
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                {
                    "name": n,
                    "entity_type": etype or "subject",
                    "mention_count": int(mc or 0),
                    "source": "story_entity_index",
                }
            )
    except Exception as e:
        logger.debug("historical_context story_entity_index %s: %s", schema, e)

    if len(entities) < 20:
        try:
            cur.execute(
                f"""
                SELECT ec.canonical_name, ec.entity_type, COUNT(*) AS cnt
                FROM {schema}.storyline_articles sa
                JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE sa.storyline_id = %s
                GROUP BY ec.id, ec.canonical_name, ec.entity_type
                ORDER BY cnt DESC
                LIMIT 40
                """,
                (storyline_id,),
            )
            for name, etype, cnt in cur.fetchall():
                n = (name or "").strip()
                if not n:
                    continue
                key = n.lower()
                if key in seen:
                    continue
                seen.add(key)
                entities.append(
                    {
                        "name": n,
                        "entity_type": etype or "subject",
                        "mention_count": int(cnt or 0),
                        "source": "article_entities",
                    }
                )
        except Exception as e:
            logger.debug("historical_context article_entities %s: %s", schema, e)
    return entities


def _load_versioned_facts_for_entities(
    cur,
    domain_key: str,
    entities: list[dict[str, Any]],
    *,
    max_facts: int,
    include_superseded: bool,
) -> list[dict[str, Any]]:
    if not entities:
        return []
    names = [e["name"] for e in entities if e.get("name")][:60]
    if not names:
        return []

    superseded_clause = "" if include_superseded else "AND vf.superseded_by_id IS NULL"
    try:
        cur.execute(
            f"""
            SELECT
                vf.id,
                vf.entity_profile_id,
                vf.fact_type,
                vf.fact_text,
                vf.confidence,
                vf.valid_from,
                vf.valid_to,
                vf.superseded_by_id,
                COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name', '') AS entity_name
            FROM intelligence.versioned_facts vf
            JOIN intelligence.entity_profiles ep ON ep.id = vf.entity_profile_id
            WHERE ep.domain_key = %s
              AND (
                LOWER(COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name', '')) = ANY(%s)
              )
              {superseded_clause}
            ORDER BY vf.valid_from DESC NULLS LAST, vf.confidence DESC NULLS LAST
            LIMIT %s
            """,
            (
                domain_key,
                [n.lower() for n in names],
                max_facts,
            ),
        )
        out: list[dict[str, Any]] = []
        for row in cur.fetchall():
            out.append(
                {
                    "id": row[0],
                    "entity_profile_id": row[1],
                    "fact_type": row[2] or "",
                    "fact_text": (row[3] or "")[:2000],
                    "confidence": float(row[4]) if row[4] is not None else None,
                    "valid_from": row[5].isoformat() if row[5] else None,
                    "valid_to": row[6].isoformat() if row[6] else None,
                    "superseded": row[7] is not None,
                    "entity_name": (row[8] or "").strip() or "Unknown",
                }
            )
        return out
    except Exception as e:
        logger.debug("historical_context versioned_facts: %s", e)
        return []


def _load_storyline_articles(
    cur, schema: str, storyline_id: int, *, max_articles: int
) -> list[dict[str, Any]]:
    try:
        cur.execute(
            f"""
            SELECT a.id, a.title, a.source_domain, a.published_at,
                   LEFT(a.content, 800), COALESCE(a.summary, ''),
                   COALESCE(a.quality_score, 0)
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = %s
            ORDER BY COALESCE(a.quality_score, 0) DESC, a.published_at DESC NULLS LAST
            LIMIT %s
            """,
            (storyline_id, max_articles),
        )
        articles = []
        for row in cur.fetchall():
            articles.append(
                {
                    "id": row[0],
                    "title": row[1] or "",
                    "source": row[2] or "",
                    "published_at": row[3].isoformat() if row[3] else None,
                    "content_excerpt": (row[4] or "")[:800],
                    "summary": (row[5] or "")[:500],
                    "quality_score": float(row[6] or 0),
                }
            )
        return articles
    except Exception as e:
        logger.debug("historical_context articles %s: %s", schema, e)
        return []


def build_storyline_historical_context(
    domain_key: str,
    storyline_id: int,
    *,
    max_facts: int | None = None,
    max_events: int | None = None,
    max_articles: int | None = None,
    include_superseded_facts: bool = True,
    conn=None,
) -> dict[str, Any]:
    """
    Assemble durable historical memory for one storyline (no age cutoff on facts/events).
    """
    max_facts = max_facts if max_facts is not None else _int_env("STORYLINE_HISTORICAL_MAX_FACTS", 40, 5, 200)
    max_articles = max_articles if max_articles is not None else _int_env(
        "STORYLINE_HISTORICAL_MAX_ARTICLES", 30, 5, 100
    )

    schema = _schema(domain_key)
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection", "domain_key": domain_key, "storyline_id": storyline_id}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, title FROM {schema}.storylines WHERE id = %s",
                (storyline_id,),
            )
            srow = cur.fetchone()
            if not srow:
                return {
                    "success": False,
                    "error": "storyline_not_found",
                    "domain_key": domain_key,
                    "storyline_id": storyline_id,
                }

            entities = _load_storyline_entities(cur, schema, storyline_id)
            facts = _load_versioned_facts_for_entities(
                cur,
                domain_key,
                entities,
                max_facts=max_facts,
                include_superseded=include_superseded_facts,
            )
            articles = _load_storyline_articles(cur, schema, storyline_id, max_articles=max_articles)

        from services.timeline_builder_service import build_storyline_spine

        spine = build_storyline_spine(domain_key, storyline_id, conn=conn)
        events = list(spine.get("events") or [])
        if max_events is not None and max_events > 0:
            events = events[-max_events:] if len(events) > max_events else events
            spine = {**spine, "events": events, "event_count": len(events)}

        fact_dates = [f["valid_from"] for f in facts if f.get("valid_from")]
        spine_summary = {
            "entity_count": len(entities),
            "fact_count": len(facts),
            "event_count": spine.get("event_count", 0),
            "gap_count": len(spine.get("gaps") or []),
            "milestone_count": len(spine.get("milestones") or []),
            "article_count": len(articles),
            "fact_date_min": min(fact_dates) if fact_dates else None,
            "fact_date_max": max(fact_dates) if fact_dates else None,
            "built_at": datetime.now(timezone.utc).isoformat(),
        }

        ctx = {
            "success": True,
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "storyline_title": srow[1] or "",
            "entities": entities,
            "versioned_facts": facts,
            "chronological_spine": spine,
            "articles": articles,
            "spine_summary": spine_summary,
            "token_budget": {
                "max_facts": max_facts,
                "max_articles": max_articles,
                "facts_returned": len(facts),
                "articles_returned": len(articles),
            },
        }
        ctx["rendered"] = render_historical_context_for_llm(ctx)
        return ctx
    except Exception as e:
        logger.warning("build_storyline_historical_context failed: %s", e)
        return {"success": False, "error": str(e), "domain_key": domain_key, "storyline_id": storyline_id}
    finally:
        if own_conn and conn:
            try:
                conn.close()
            except Exception:
                pass


def render_historical_context_for_llm(
    ctx: dict[str, Any],
    max_chars: int | None = None,
) -> str:
    """Render historical context block for LLM prompts."""
    if not ctx.get("success"):
        return ""
    max_chars = max_chars if max_chars is not None else _int_env(
        "STORYLINE_HISTORICAL_CONTEXT_MAX_CHARS", 6000, 500, 50000
    )

    parts: list[str] = []
    summary = ctx.get("spine_summary") or {}
    parts.append(
        f"## Historical memory (entities={summary.get('entity_count', 0)}, "
        f"facts={summary.get('fact_count', 0)}, events={summary.get('event_count', 0)})"
    )
    if summary.get("fact_date_min"):
        parts.append(
            f"Fact timeline span: {summary.get('fact_date_min')} .. {summary.get('fact_date_max')}"
        )

    facts = ctx.get("versioned_facts") or []
    if facts:
        parts.append("\n## Established facts (entity timeline, no age cutoff)")
        for f in facts[:50]:
            line = f"- [{f.get('valid_from', '?')}] {f.get('entity_name', '?')}: {f.get('fact_text', '')[:400]}"
            if f.get("superseded"):
                line += " (superseded)"
            parts.append(line)

    spine = ctx.get("chronological_spine") or {}
    events = spine.get("events") or []
    if events:
        parts.append("\n## Chronological spine (extracted events)")
        for ev in events[:60]:
            d = ev.get("event_date")
            dstr = d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "?")
            parts.append(
                f"- [{dstr}] {ev.get('title', '')} ({ev.get('event_type', '')})"
                f" importance={ev.get('importance', 0)}"
            )
    gaps = spine.get("gaps") or []
    if gaps:
        parts.append("\n## Timeline gaps")
        for g in gaps[:8]:
            parts.append(f"- {g.get('gap_days', 0)} days between events ({g.get('from_date')} .. {g.get('to_date')})")
    milestones = spine.get("milestones") or []
    if milestones:
        parts.append("\n## Milestones")
        for m in milestones[:10]:
            parts.append(f"- {m.get('title', m.get('type', 'milestone'))}")

    articles = ctx.get("articles") or []
    if articles:
        parts.append("\n## Linked articles (excerpts)")
        for a in articles[:25]:
            parts.append(
                f"- [{a.get('published_at', '?')}] {a.get('title', '')} ({a.get('source', '')})"
            )

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 40] + "\n\n[... historical context truncated ...]"
    return text
