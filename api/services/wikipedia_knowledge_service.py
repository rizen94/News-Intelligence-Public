"""
Local Wikipedia knowledge base service for entity background lookups.

Uses intelligence.wikipedia_knowledge (populated by load_wikipedia_dump.py).
Lookup order: exact title → alias match (redirects) → title prefix → full-text search,
with person/org preferred when page_type is set. For better mapping of redirects
(e.g. "GOP" → "Republican Party (United States)"), run scripts/populate_wikipedia_aliases.py
after loading the dump. Falls back to Wikipedia API when no local match is found.
"""

import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _get_wikipedia_api_service():
    """Lazy import to avoid circular deps."""
    from modules.ml.rag_external_services import WikipediaService
    return WikipediaService()


def lookup_entity(name: str) -> Optional[Dict[str, Any]]:
    """
    Look up an entity by name in the local Wikipedia knowledge base.
    Tries: exact title_lower → alias match (if aliases populated) → title prefix →
    full-text search (preferring person/org page_type when set).
    Returns None if not found (caller can fall back to API).
    """
    if not name or not name.strip():
        return None
    name_clean = name.strip()
    name_lower = name_clean.lower()
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # 1. Exact match on title_lower
            cur.execute(
                """
                SELECT page_id, title, title_lower, abstract, page_url, page_type
                FROM intelligence.wikipedia_knowledge
                WHERE title_lower = %s
                LIMIT 1
                """,
                (name_lower,),
            )
            row = cur.fetchone()
            if row:
                return _row_to_summary(row)
            # 2. Alias match (when aliases are populated, e.g. from redirects)
            cur.execute(
                """
                SELECT page_id, title, title_lower, abstract, page_url, page_type
                FROM intelligence.wikipedia_knowledge
                WHERE aliases IS NOT NULL AND array_length(aliases, 1) > 0
                  AND EXISTS (SELECT 1 FROM unnest(aliases) a WHERE lower(trim(a::text)) = %s)
                LIMIT 1
                """,
                (name_lower,),
            )
            row = cur.fetchone()
            if row:
                return _row_to_summary(row)
            # 3. Title prefix: title_lower LIKE name%
            cur.execute(
                """
                SELECT page_id, title, title_lower, abstract, page_url, page_type
                FROM intelligence.wikipedia_knowledge
                WHERE title_lower LIKE %s
                ORDER BY LENGTH(title_lower) ASC
                LIMIT 1
                """,
                (name_lower + "%",),
            )
            row = cur.fetchone()
            if row:
                return _row_to_summary(row)
            # 4. Full-text search; prefer person then organization when page_type is set
            cur.execute(
                """
                SELECT page_id, title, title_lower, abstract, page_url, page_type
                FROM intelligence.wikipedia_knowledge
                WHERE tsv @@ plainto_tsquery('english', %s)
                ORDER BY
                    CASE lower(coalesce(page_type, ''))
                        WHEN 'person' THEN 0
                        WHEN 'organization' THEN 1
                        ELSE 2
                    END NULLS LAST,
                    ts_rank(tsv, plainto_tsquery('english', %s)) DESC
                LIMIT 1
                """,
                (name_clean, name_clean),
            )
            row = cur.fetchone()
            if row:
                return _row_to_summary(row)
    except Exception as e:
        logger.debug("Wikipedia knowledge lookup for %s: %s", name, e)
    finally:
        conn.close()
    return None


def _row_to_summary(row: tuple) -> Dict[str, Any]:
    """Convert DB row to API-style summary dict."""
    page_id, title, title_lower, abstract, page_url, page_type = row
    return {
        "page_id": page_id,
        "title": title or "",
        "extract": (abstract or "")[:2000],
        "url": page_url or "",
        "type": page_type or "other",
    }


def search_entities(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Full-text search over local Wikipedia knowledge. Prefers person/org when page_type is set."""
    if not query or not query.strip():
        return []
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_id, title, title_lower, abstract, page_url, page_type
                FROM intelligence.wikipedia_knowledge
                WHERE tsv @@ plainto_tsquery('english', %s)
                ORDER BY
                    CASE lower(coalesce(page_type, ''))
                        WHEN 'person' THEN 0
                        WHEN 'organization' THEN 1
                        ELSE 2
                    END NULLS LAST,
                    ts_rank(tsv, plainto_tsquery('english', %s)) DESC
                LIMIT %s
                """,
                (query.strip(), query.strip(), limit),
            )
            return [_row_to_summary(row) for row in cur.fetchall()]
    except Exception as e:
        logger.debug("Wikipedia knowledge search for %s: %s", query, e)
        return []
    finally:
        conn.close()


def lookup_batch(names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Batch lookup by list of names. Returns dict mapping name (original) -> summary.
    Uses the same logic as lookup_entity for each name (exact → alias → prefix → FTS)
    so we get intelligent matching from the local dump, not just exact title match.
    Only includes names that were found locally; missing names are omitted.
    """
    if not names:
        return {}
    result = {}
    seen = set()
    for name in names:
        if not name or not name.strip():
            continue
        name_clean = name.strip()
        if name_clean in seen:
            continue
        seen.add(name_clean)
        summary = lookup_entity(name_clean)
        if summary:
            result[name_clean] = summary
    return result


def lookup_entity_with_fallback(name: str) -> Optional[Dict[str, Any]]:
    """
    Look up entity in local DB first; if not found, call Wikipedia API.
    Returns API-style summary (title, extract, url, etc.) for use by entity_enrichment and RAG.
    On API success, caches the result into intelligence.wikipedia_knowledge
    so subsequent lookups are local hits.
    """
    local = lookup_entity(name)
    if local:
        return local
    try:
        wiki = _get_wikipedia_api_service()
        summary = wiki.get_article_summary(name)
        if summary and summary.get("extract"):
            _cache_api_result(summary)
            return summary
        results = wiki.search_articles(name, limit=1)
        if results:
            summary = wiki.get_article_summary(results[0]["title"])
            if summary and summary.get("extract"):
                _cache_api_result(summary)
                return summary
    except Exception as e:
        logger.debug("Wikipedia API fallback for %s: %s", name, e)
    return None


def _cache_api_result(summary: Dict[str, Any]) -> None:
    """Upsert a Wikipedia API result into local intelligence.wikipedia_knowledge.

    The tsv tsvector column is maintained by a DB trigger, so we only need
    to supply the text columns.  Silently skips on any error so the caller
    always gets the result regardless of caching success.
    """
    title = (summary.get("title") or "").strip()
    extract = (summary.get("extract") or "").strip()
    if not title or not extract:
        return
    page_id = summary.get("pageid") or summary.get("page_id")
    if not page_id:
        import hashlib
        page_id = int(hashlib.md5(title.encode()).hexdigest()[:8], 16)
    page_url = summary.get("url") or ""
    try:
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.wikipedia_knowledge
                        (page_id, title, title_lower, abstract, page_url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (page_id) DO UPDATE
                        SET abstract = EXCLUDED.abstract,
                            page_url = EXCLUDED.page_url,
                            loaded_at = NOW()
                    """,
                    (page_id, title, title.lower(), extract, page_url),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("_cache_api_result for '%s': %s", title[:40], e)


def cache_knowledge_graph_result(name: str, result: Dict[str, Any]) -> None:
    """
    Store a Knowledge Graph API result in intelligence.wikipedia_knowledge so
    subsequent lookups hit local first. Uses synthetic negative page_id to avoid
    collisions with Wikipedia page IDs.
    """
    title = (result.get("title") or name or "").strip()
    description = (result.get("description") or "").strip()
    url = (result.get("url") or "").strip()
    if not title or not description:
        return
    import hashlib
    synthetic_page_id = -abs(int(hashlib.md5(title.encode()).hexdigest()[:8], 16))
    try:
        conn = get_db_connection()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.wikipedia_knowledge
                        (page_id, title, title_lower, abstract, page_url, page_type)
                    VALUES (%s, %s, %s, %s, %s, 'kg_cache')
                    ON CONFLICT (page_id) DO UPDATE
                        SET abstract = EXCLUDED.abstract,
                            page_url = EXCLUDED.page_url,
                            loaded_at = NOW()
                    """,
                    (synthetic_page_id, title, title.lower(), description[:50000], url),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("cache_knowledge_graph_result for '%s': %s", title[:40], e)
