"""Resolve domain_key for rows in public.chronological_events.

Widow stores articles per domain schema ({schema}.articles), not public.articles.
Public-data collectors use storyline_id ``public_data:{domain_key}``.
"""

from __future__ import annotations

from collectors.public_event_upsert import PUBLIC_STORYLINE_PREFIX, public_storyline_id
from shared.domain_registry import (
    get_pipeline_active_domain_keys,
    is_valid_domain_key,
    resolve_domain_schema,
)


def _schema_has_table(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = %s AND table_name = %s
            )
            """,
            (schema, table),
        )
        row = cur.fetchone()
        return bool(row and row[0])


def domain_from_storyline_id(storyline_id: str | None) -> str | None:
    sl = (storyline_id or "").strip()
    if not sl:
        return None
    if sl.startswith(PUBLIC_STORYLINE_PREFIX):
        dk = sl[len(PUBLIC_STORYLINE_PREFIX) :].strip().lower().replace("-", "_")
        return dk if is_valid_domain_key(dk) else None
    if sl.isdigit():
        return None
    if ":" in sl:
        head = sl.split(":", 1)[0].strip().lower()
        if is_valid_domain_key(head):
            return head
    return None


def resolve_chronological_event_domain_key(conn, event_id: int) -> str | None:
    """Best-effort domain_key for a chronological_events row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ce.source_article_id, ce.storyline_id, ce.title
            FROM public.chronological_events ce
            WHERE ce.id = %s
            LIMIT 1
            """,
            (int(event_id),),
        )
        row = cur.fetchone()
    if not row:
        return None

    source_article_id, storyline_id, title = row
    sl_dk = domain_from_storyline_id(str(storyline_id or ""))
    if sl_dk:
        return sl_dk

    article_id = int(source_article_id) if source_article_id is not None else None
    if article_id:
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
            if not _schema_has_table(conn, schema, "articles"):
                continue
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM {schema}.articles WHERE id = %s LIMIT 1",
                    (article_id,),
                )
                if cur.fetchone():
                    return dk

    sl = str(storyline_id or "").strip()
    if sl.isdigit():
        for dk in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(dk)
            if not _schema_has_table(conn, schema, "storylines"):
                continue
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT 1 FROM {schema}.storylines WHERE id = %s LIMIT 1",
                    (int(sl),),
                )
                if cur.fetchone():
                    return dk

    try:
        from services.event_chronicle_hygiene_service import infer_domain_from_event_name

        inferred = infer_domain_from_event_name(str(title or ""))
        if inferred and is_valid_domain_key(inferred):
            return inferred
    except Exception:
        pass
    return None


def unlinked_event_domain_predicate(
    conn, schema: str, domain_key: str
) -> tuple[str, tuple]:
    """SQL fragment + params matching unlinked CE rows likely belonging to domain_key."""
    public_sl = public_storyline_id(domain_key)
    parts: list[str] = [f"ce.storyline_id = %s"]
    params: list = [public_sl]

    if _schema_has_table(conn, schema, "articles"):
        parts.insert(
            0,
            f"""EXISTS (
            SELECT 1 FROM {schema}.articles a
            WHERE a.id = ce.source_article_id
        )""",
        )
    if _schema_has_table(conn, schema, "storylines"):
        parts.append(
            f"""(
            ce.storyline_id ~ '^[0-9]+$'
            AND EXISTS (
                SELECT 1 FROM {schema}.storylines s
                WHERE s.id::text = ce.storyline_id
            )
        )"""
        )

    sql = f"({' OR '.join(parts)})"
    return sql, tuple(params)
