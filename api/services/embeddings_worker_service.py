"""
Embeddings worker — chunk articles and reference events into intelligence.embedding_chunks.

Runs in nightly window; yields when ingest backlog is high.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)


def _chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            break_at = text.rfind(". ", start, end)
            if break_at > start + 200:
                end = break_at + 1
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


def _get_embedding(text: str) -> list[float] | None:
    try:
        from services.ai_storyline_discovery import get_embedding_single

        vec = get_embedding_single(text[:4000])
        if vec is None:
            return None
        if isinstance(vec, str):
            parsed = json.loads(vec)
            return parsed if isinstance(parsed, list) else None
        return list(vec) if vec else None
    except Exception as e:
        logger.debug("embedding skip: %s", e)
        return None


def _format_vector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


def _embeddings_should_yield() -> bool:
    """Skip embedding when claim extraction backlog is high (pipeline priority)."""
    threshold = int(os.environ.get("EMBEDDINGS_YIELD_CLAIM_BACKLOG", "5000"))
    try:
        from services.claim_extraction_service import get_context_claim_backlog_stats

        stats = get_context_claim_backlog_stats()
        backlog = int(stats.get("actionable_no_claims") or 0)
        if backlog > threshold:
            logger.info(
                "embeddings worker yielding: claim backlog %s > %s",
                backlog,
                threshold,
            )
            return True
    except Exception as e:
        logger.debug("embeddings yield check skipped: %s", e)
    return False


def _embed_reference_events(cur, *, limit: int) -> tuple[int, int]:
    embedded = 0
    skipped = 0
    cur.execute(
        """
        SELECT re.id, re.title, re.summary, re.event_date
        FROM intelligence.reference_events re
        WHERE re.superseded_by_id IS NULL
          AND COALESCE(re.summary, re.title, '') <> ''
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.embedding_chunks ec
              WHERE ec.source_type = 'reference_event'
                AND ec.source_id = re.id::text
          )
        ORDER BY re.event_date DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )
    for rid, title, summary, event_date in cur.fetchall():
        body = f"{title or ''}\n\n{summary or ''}".strip()
        chunks = _chunk_text(body)
        if not chunks:
            skipped += 1
            continue
        source_id = str(rid)
        any_ok = False
        for idx, chunk in enumerate(chunks):
            vec = _get_embedding(chunk)
            if not vec:
                continue
            cur.execute(
                """
                INSERT INTO intelligence.embedding_chunks (
                    source_type, source_id, domain_key, chunk_index, chunk_text,
                    embedding, event_date, ingestion_date, metadata
                ) VALUES (
                    'reference_event', %s, NULL, %s, %s, %s::vector, %s, NOW(), %s::jsonb
                )
                ON CONFLICT (source_type, source_id, chunk_index) DO NOTHING
                """,
                (
                    source_id,
                    idx,
                    chunk[:8000],
                    _format_vector(vec),
                    event_date,
                    json.dumps({"reference_event_id": rid}),
                ),
            )
            any_ok = True
        if any_ok:
            embedded += 1
        else:
            skipped += 1
    return embedded, skipped


def _fetch_wikipedia_summary(title: str) -> dict[str, Any] | None:
    import os
    from urllib.parse import quote

    import requests

    base = (os.environ.get("KIWIX_WIKIPEDIA_REST_URL") or "").strip().rstrip("/")
    api_base = base or "https://en.wikipedia.org/api/rest_v1"
    url = f"{api_base}/page/summary/{quote(title.replace(' ', '_'))}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "NewsIntelligence/1.0 embeddings"})
        if r.status_code != 200:
            return None
        data = r.json()
        extract = (data.get("extract") or "").strip()
        if not extract:
            return None
        return {
            "title": data.get("title") or title,
            "extract": extract,
            "url": (data.get("content_urls") or {}).get("desktop", {}).get("page", ""),
        }
    except Exception as e:
        logger.debug("wikipedia fetch %s: %s", title, e)
        return None


def _embed_wikipedia_topics(cur, *, limit: int) -> tuple[int, int]:
    """Embed Wikipedia summaries for reference-event titles not yet chunked."""
    import os

    vintage_raw = (os.environ.get("KIWIX_ZIM_VINTAGE_DATE") or "").strip()
    vintage_date = None
    if vintage_raw:
        try:
            vintage_date = datetime.fromisoformat(vintage_raw[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            vintage_date = None

    cur.execute(
        """
        SELECT re.id, re.title, re.event_date
        FROM intelligence.reference_events re
        WHERE re.superseded_by_id IS NULL
          AND COALESCE(re.title, '') <> ''
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.embedding_chunks ec
              WHERE ec.source_type = 'wikipedia'
                AND ec.source_id = 'ref:' || re.id::text
          )
        ORDER BY re.event_date DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )
    embedded = 0
    skipped = 0
    for rid, title, event_date in cur.fetchall():
        wiki = _fetch_wikipedia_summary(title)
        if not wiki:
            skipped += 1
            continue
        body = f"{wiki['title']}\n\n{wiki['extract']}"
        chunks = _chunk_text(body)
        source_id = f"ref:{rid}"
        any_ok = False
        meta = {
            "reference_event_id": rid,
            "wikipedia_url": wiki.get("url"),
            "vintage_date": vintage_raw or None,
        }
        for idx, chunk in enumerate(chunks):
            vec = _get_embedding(chunk)
            if not vec:
                continue
            cur.execute(
                """
                INSERT INTO intelligence.embedding_chunks (
                    source_type, source_id, domain_key, chunk_index, chunk_text,
                    embedding, event_date, ingestion_date, vintage_date, metadata
                ) VALUES (
                    'wikipedia', %s, NULL, %s, %s, %s::vector, %s, NOW(), %s, %s::jsonb
                )
                ON CONFLICT (source_type, source_id, chunk_index) DO NOTHING
                """,
                (
                    source_id,
                    idx,
                    chunk[:8000],
                    _format_vector(vec),
                    event_date,
                    vintage_date,
                    json.dumps(meta),
                ),
            )
            any_ok = True
        if any_ok:
            embedded += 1
        else:
            skipped += 1
    return embedded, skipped


def _embed_contexts(cur, *, limit: int) -> tuple[int, int]:
    """Chunk intelligence.contexts rows into embedding_chunks (source_type=context)."""
    embedded = 0
    skipped = 0
    cur.execute(
        """
        SELECT c.id, c.title, c.content, c.domain_key, c.event_date, c.metadata,
               atc.article_id
        FROM intelligence.contexts c
        LEFT JOIN intelligence.article_to_context atc ON atc.context_id = c.id
        WHERE COALESCE(c.content, c.title, '') <> ''
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.embedding_chunks ec
              WHERE ec.source_type = 'context'
                AND ec.source_id = c.id::text
          )
        ORDER BY c.created_at DESC NULLS LAST
        LIMIT %s
        """,
        (limit,),
    )
    for cid, title, content, domain_key, event_date, metadata, article_id in cur.fetchall():
        body = f"{title or ''}\n\n{content or ''}".strip()
        chunks = _chunk_text(body)
        if not chunks:
            skipped += 1
            continue
        meta: dict[str, Any] = {"context_id": cid}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        if isinstance(metadata, dict):
            meta.update({k: v for k, v in metadata.items() if k not in meta})
        if article_id is not None:
            meta["article_id"] = article_id
        storyline_id = meta.get("storyline_id")
        if storyline_id is None and article_id is not None and domain_key:
            try:
                schema = resolve_domain_schema(domain_key)
                cur.execute(
                    f"""
                    SELECT sa.storyline_id
                    FROM {schema}.storyline_articles sa
                    WHERE sa.article_id = %s
                    ORDER BY sa.added_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (article_id,),
                )
                srow = cur.fetchone()
                if srow and srow[0]:
                    meta["storyline_id"] = srow[0]
            except Exception as e:
                logger.debug("context storyline lookup %s: %s", cid, e)

        source_id = str(cid)
        any_ok = False
        for idx, chunk in enumerate(chunks):
            vec = _get_embedding(chunk)
            if not vec:
                continue
            cur.execute(
                """
                INSERT INTO intelligence.embedding_chunks (
                    source_type, source_id, domain_key, chunk_index, chunk_text,
                    embedding, event_date, ingestion_date, metadata
                ) VALUES (
                    'context', %s, %s, %s, %s, %s::vector, %s, NOW(), %s::jsonb
                )
                ON CONFLICT (source_type, source_id, chunk_index) DO NOTHING
                """,
                (
                    source_id,
                    domain_key,
                    idx,
                    chunk[:8000],
                    _format_vector(vec),
                    event_date,
                    json.dumps(meta),
                ),
            )
            any_ok = True
        if any_ok:
            embedded += 1
        else:
            skipped += 1
    return embedded, skipped


def run_embeddings_worker_batch(
    *,
    batch_limit: int | None = None,
    domain_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Embed unchunked articles and reference events across pipeline domains."""
    if _embeddings_should_yield():
        return {
            "success": True,
            "yielded": True,
            "embedded_articles": 0,
            "embedded_reference_events": 0,
            "embedded_wikipedia": 0,
            "embedded_contexts": 0,
            "skipped": 0,
        }

    limit = batch_limit or int(os.environ.get("EMBEDDINGS_WORKER_BATCH_LIMIT", "50"))
    ref_limit = int(os.environ.get("EMBEDDINGS_REFERENCE_EVENT_BATCH_LIMIT", "20"))
    wiki_limit = int(os.environ.get("EMBEDDINGS_WIKIPEDIA_BATCH_LIMIT", "10"))
    ctx_limit = int(os.environ.get("EMBEDDINGS_CONTEXT_BATCH_LIMIT", "30"))
    domains = domain_keys or list(get_pipeline_active_domain_keys())
    embedded = 0
    ref_embedded = 0
    wiki_embedded = 0
    ctx_embedded = 0
    skipped = 0

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            ref_embedded, ref_skipped = _embed_reference_events(cur, limit=ref_limit)
            skipped += ref_skipped
            wiki_embedded, wiki_skipped = _embed_wikipedia_topics(cur, limit=wiki_limit)
            skipped += wiki_skipped
            ctx_embedded, ctx_skipped = _embed_contexts(cur, limit=ctx_limit)
            skipped += ctx_skipped

        for dk in domains:
            schema = resolve_domain_schema(dk)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = 'articles' AND column_name = 'event_date'
                    LIMIT 1
                    """,
                    (schema,),
                )
                has_event_date = cur.fetchone() is not None
                event_date_col = "a.event_date" if has_event_date else "a.published_at"
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.content, a.published_at, {event_date_col} AS event_date
                    FROM {schema}.articles a
                    WHERE COALESCE(a.content, a.title, '') <> ''
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.embedding_chunks ec
                          WHERE ec.source_type = 'article'
                            AND ec.source_id = %s || ':' || a.id::text
                      )
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (dk, limit),
                )
                rows = cur.fetchall()
                for aid, title, content, published_at, event_date in rows:
                    body = f"{title or ''}\n\n{content or ''}".strip()
                    chunks = _chunk_text(body)
                    if not chunks:
                        skipped += 1
                        continue
                    ev_dt = event_date or published_at
                    source_id = f"{dk}:{aid}"
                    any_ok = False
                    for idx, chunk in enumerate(chunks):
                        vec = _get_embedding(chunk)
                        if not vec:
                            continue
                        cur.execute(
                            """
                            INSERT INTO intelligence.embedding_chunks (
                                source_type, source_id, domain_key, chunk_index, chunk_text,
                                embedding, event_date, ingestion_date, metadata
                            ) VALUES (
                                'article', %s, %s, %s, %s, %s::vector, %s, NOW(), %s::jsonb
                            )
                            ON CONFLICT (source_type, source_id, chunk_index) DO NOTHING
                            """,
                            (
                                source_id,
                                dk,
                                idx,
                                chunk[:8000],
                                _format_vector(vec),
                                ev_dt,
                                json.dumps({"article_id": aid, "domain_key": dk}),
                            ),
                        )
                        any_ok = True
                    if any_ok:
                        embedded += 1
                    else:
                        skipped += 1
        conn.commit()

    return {
        "success": True,
        "yielded": False,
        "embedded_articles": embedded,
        "embedded_reference_events": ref_embedded,
        "embedded_wikipedia": wiki_embedded,
        "embedded_contexts": ctx_embedded,
        "skipped": skipped,
    }


# Backward-compatible alias for automation/docs referencing run_embeddings_worker
run_embeddings_worker = run_embeddings_worker_batch


def search_embedding_chunks(
    query: str,
    *,
    limit: int = 12,
    source_types: list[str] | None = None,
    domain_key: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    source_ids: list[str] | None = None,
    storyline_article_ids: list[int] | None = None,
    keyword_hint: str | None = None,
) -> list[dict[str, Any]]:
    """Cosine similarity search over embedding_chunks with optional structured filters."""
    vec = _get_embedding(query)
    if not vec:
        return []
    vec_str = _format_vector(vec)
    types = source_types or ["article", "reference_event", "wikipedia"]
    conditions: list[str] = [
        "source_type = ANY(%s)",
        "embedding IS NOT NULL",
    ]
    params: list[Any] = [types]

    if domain_key:
        conditions.append("domain_key = %s")
        params.append(domain_key)

    if date_from is not None:
        conditions.append("event_date >= %s")
        params.append(date_from)

    if date_to is not None:
        conditions.append("event_date <= %s")
        params.append(date_to)

    if source_ids:
        conditions.append("source_id = ANY(%s)")
        params.append(list(source_ids))

    if storyline_article_ids:
        id_list = [int(x) for x in storyline_article_ids]
        conditions.append(
            """(
                (metadata->>'article_id')::bigint = ANY(%s)
                OR (
                    source_type = 'article'
                    AND NULLIF(split_part(source_id, ':', 2), '')::bigint = ANY(%s)
                )
            )"""
        )
        params.extend([id_list, id_list])

    if keyword_hint and keyword_hint.strip():
        conditions.append(
            "to_tsvector('english', COALESCE(chunk_text, '')) @@ plainto_tsquery('english', %s)"
        )
        params.append(keyword_hint.strip())

    where_sql = " AND ".join(conditions)
    params.extend([vec_str, vec_str, limit])

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT source_type, source_id, domain_key, chunk_index, chunk_text,
                       event_date, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM intelligence.embedding_chunks
                WHERE {where_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                tuple(params),
            )
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("event_date") and hasattr(d["event_date"], "isoformat"):
                    d["event_date"] = d["event_date"].isoformat()
                meta = d.get("metadata")
                if isinstance(meta, str):
                    try:
                        d["metadata"] = json.loads(meta)
                    except Exception:
                        d["metadata"] = {}
                out.append(d)
            return out
