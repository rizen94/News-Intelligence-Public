"""Pipeline-only helpers for stored storyline Wikipedia/GDELT RAG context.

Used by comprehensive_rag / narrative_finisher job runners — never by user-facing GET routes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

_PREFERRED_ENTITY_TYPES = frozenset(
    {
        "person",
        "organization",
        "org",
        "company",
        "location",
        "place",
        "country",
        "event",
        "gpe",
        "facility",
    }
)

_GENERIC_ENTITY_TOKENS = frozenset(
    {
        "app",
        "apps",
        "news",
        "report",
        "reports",
        "said",
        "year",
        "years",
        "today",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "government",
        "company",
        "officials",
        "people",
        "world",
        "state",
        "states",
        "united",
        "america",
    }
)


def render_rag_context_for_llm(rag_data: dict[str, Any] | None, *, max_chars: int = 4000) -> str:
    """Render stored wiki/GDELT rag_data into a compact prompt block."""
    if not rag_data or not isinstance(rag_data, dict):
        return ""
    parts: list[str] = []

    wiki = rag_data.get("wikipedia") if isinstance(rag_data.get("wikipedia"), dict) else {}
    summaries = wiki.get("summaries") if isinstance(wiki, dict) else None
    if isinstance(summaries, list) and summaries:
        parts.append("Wikipedia:")
        for item in summaries[:5]:
            if not isinstance(item, dict):
                continue
            term = (item.get("term") or item.get("title") or "").strip()
            summary = (item.get("summary") or "").strip()
            if summary:
                parts.append(f"- {term}: {summary[:500]}" if term else f"- {summary[:500]}")
    elif isinstance(wiki.get("articles"), list):
        parts.append("Wikipedia:")
        for art in wiki["articles"][:5]:
            if not isinstance(art, dict):
                continue
            title = (art.get("title") or "").strip()
            extract = (art.get("extract") or "").strip()
            if extract:
                parts.append(f"- {title}: {extract[:500]}" if title else f"- {extract[:500]}")

    gdelt = rag_data.get("gdelt") if isinstance(rag_data.get("gdelt"), dict) else {}
    events = gdelt.get("events") if isinstance(gdelt, dict) else None
    if isinstance(events, list) and events:
        parts.append("GDELT recent mentions:")
        for ev in events[:5]:
            if isinstance(ev, dict):
                title = (ev.get("title") or ev.get("seendate") or "").strip()
                url = (ev.get("url") or "").strip()
                line = title or url
                if line:
                    parts.append(f"- {line[:300]}")
            elif isinstance(ev, str) and ev.strip():
                parts.append(f"- {ev.strip()[:300]}")

    ents = rag_data.get("extracted_entities")
    if isinstance(ents, list) and ents:
        names = [str(e).strip() for e in ents[:12] if str(e).strip()]
        if names:
            parts.append(f"Key entities: {', '.join(names)}")

    topics = rag_data.get("extracted_topics")
    if isinstance(topics, list) and topics:
        labels = [str(t).strip() for t in topics[:10] if str(t).strip()]
        if labels:
            parts.append(f"Topics: {', '.join(labels)}")

    text = "\n".join(parts).strip()
    if not text:
        return ""
    if len(text) > max_chars:
        return text[: max_chars - 20].rstrip() + "\n…[truncated]"
    return text


def filter_entities_for_wikipedia(
    entities: list[dict[str, Any]] | list[str],
    *,
    limit: int = 5,
) -> list[str]:
    """Pick high-signal canonical entity names for Wikipedia lookup.

    Prefer person/org/location/event with known Wikipedia ids, then by mention_count.
    """
    names: list[str] = []
    seen: set[str] = set()

    # (type_rank, -mention_count, name) — lower type_rank wins, then higher mentions
    typed: list[tuple[int, int, str]] = []
    for e in entities:
        if isinstance(e, dict):
            name = (e.get("name") or "").strip()
            etype = (e.get("type") or e.get("entity_type") or "").strip().lower()
            type_rank = 0 if etype in _PREFERRED_ENTITY_TYPES else 1
            if e.get("wikipedia_page_id") or e.get("wikipedia_url"):
                type_rank = -1
            try:
                mentions = int(e.get("mention_count") or 0)
            except (TypeError, ValueError):
                mentions = 0
        else:
            name = str(e).strip()
            type_rank = 2
            mentions = 0
        if not name or len(name) < 3 or len(name) > 80:
            continue
        key = name.lower()
        if key in seen or key in _GENERIC_ENTITY_TOKENS:
            continue
        if " " not in name and key.isalpha() and len(name) < 4:
            continue
        seen.add(key)
        typed.append((type_rank, -mentions, name))

    typed.sort(key=lambda x: (x[0], x[1], x[2].lower()))
    for _, _, name in typed[:limit]:
        names.append(name)
    return names


async def ensure_storyline_rag_context(
    domain: str,
    storyline_id: int,
    *,
    force: bool = False,
    timeout_seconds: float = 45.0,
) -> dict[str, Any] | None:
    """Load stored RAG context; on miss (or force), enhance once and persist.

    Pipeline job runners only. Failures return None so callers can continue articles-only.
    """
    from services.rag import get_rag_service

    rag_service = get_rag_service()
    if not force:
        try:
            existing = await rag_service.get_rag_context(str(storyline_id), domain=domain)
            if existing and isinstance(existing, dict) and not existing.get("error"):
                wiki = existing.get("wikipedia") if isinstance(existing.get("wikipedia"), dict) else {}
                has_wiki = bool(
                    (isinstance(wiki.get("summaries"), list) and wiki.get("summaries"))
                    or (isinstance(wiki.get("articles"), list) and wiki.get("articles"))
                )
                if has_wiki or existing.get("extracted_entities"):
                    return existing
        except Exception as e:
            logger.debug("ensure_storyline_rag_context get: %s", e)

    schema = resolve_domain_schema(domain)
    title = ""
    summary_body = ""
    prefer_regen = False
    kitchen_sink_flag: bool | None = None
    articles: list[dict[str, Any]] = []
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title,
                       COALESCE(canonical_narrative, COALESCE(analysis_summary, '')),
                       COALESCE(narrative_finisher_meta, '{{}}'::jsonb),
                       COALESCE(quality_metrics, '{{}}'::jsonb)
                FROM {schema}.storylines WHERE id = %s
                """,
                (int(storyline_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            title = row[0] or ""
            summary_body = row[1] or ""
            try:
                import json as _json

                meta = (
                    _json.loads(row[2]) if isinstance(row[2], str) else row[2]
                )
                if isinstance(meta, dict):
                    prefer_regen = bool(meta.get("prefer_regenerate_from_keepers"))
                    prune_meta = meta.get("core_prune")
                    if isinstance(prune_meta, dict):
                        if prune_meta.get("prefer_regenerate_from_keepers"):
                            prefer_regen = True
                        if prune_meta.get("kitchen_sink"):
                            kitchen_sink_flag = True
                qm = _json.loads(row[3]) if isinstance(row[3], str) else row[3]
                if isinstance(qm, dict):
                    if qm.get("prefer_regenerate_from_keepers"):
                        prefer_regen = True
                    if qm.get("kitchen_sink"):
                        kitchen_sink_flag = True
            except Exception:
                pass
            cur.execute(
                f"""
                SELECT a.id, a.title, a.content, a.summary, a.source_domain,
                       COALESCE(sa.relationship_type, '')
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
                LIMIT 30
                """,
                (int(storyline_id),),
            )
            for r in cur.fetchall():
                articles.append(
                    {
                        "id": r[0],
                        "title": r[1],
                        "content": r[2] or "",
                        "summary": r[3],
                        "source": r[4],
                        "relationship_type": (r[5] or "").strip().lower(),
                        "entities": set(),
                    }
                )
            # Light entity enrichment for keeper scoring
            aids = [int(a["id"]) for a in articles if a.get("id")]
            if aids:
                try:
                    cur.execute(
                        f"""
                        SELECT ae.article_id, LOWER(ec.canonical_name)
                        FROM {schema}.article_entities ae
                        JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                        WHERE ae.article_id = ANY(%s)
                          AND ec.canonical_name IS NOT NULL
                        LIMIT 1500
                        """,
                        (aids,),
                    )
                    by_id = {int(a["id"]): a for a in articles}
                    for aid, name in cur.fetchall():
                        row_a = by_id.get(int(aid))
                        if row_a and name:
                            row_a["entities"].add(str(name).strip().lower())
                except Exception:
                    pass
            try:
                from services.storyline_core_prune_service import (
                    filter_articles_for_keeper_evidence,
                )

                before_n = len(articles)
                articles = filter_articles_for_keeper_evidence(
                    storyline_title=title,
                    storyline_summary=summary_body,
                    articles=articles,
                    prefer_regenerate_from_keepers=prefer_regen,
                    kitchen_sink=kitchen_sink_flag,
                )
                if before_n and len(articles) < before_n:
                    logger.info(
                        "rag_context keeper-only evidence %s/%s: %s → %s",
                        domain,
                        storyline_id,
                        before_n,
                        len(articles),
                    )
            except Exception as ke:
                logger.debug("rag_context keeper filter skipped: %s", ke)
            for a in articles:
                a.pop("entities", None)
                a.pop("relationship_type", None)
    except Exception as e:
        logger.warning("ensure_storyline_rag_context load articles: %s", e)
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    try:
        out = await asyncio.wait_for(
            rag_service.enhance_storyline_context(
                storyline_id=str(storyline_id),
                storyline_title=title,
                articles=articles,
                domain=domain,
            ),
            timeout=max(5.0, float(timeout_seconds)),
        )
        if isinstance(out, dict) and not out.get("error"):
            return out
    except asyncio.TimeoutError:
        logger.warning(
            "ensure_storyline_rag_context timeout domain=%s storyline_id=%s",
            domain,
            storyline_id,
        )
    except Exception as e:
        logger.warning("ensure_storyline_rag_context enhance: %s", e)
    return None
