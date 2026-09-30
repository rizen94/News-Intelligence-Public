"""
Registry for intelligence.vault_notes — structured pointers to Obsidian paths.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import entity_vault_rel_path

logger = logging.getLogger(__name__)


def upsert_vault_note(
    *,
    domain_key: str,
    note_type: str,
    object_id: int,
    vault_path: str,
    title: str | None = None,
    note_status: str = "note_pending",
    lifecycle: str = "stub",
    object_id_secondary: int | None = None,
    tags: list[str] | None = None,
    mention_count: int = 0,
    alias_ids: list[int] | None = None,
    last_article_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    geo_parent_entity_id: int | None = None,
    place_kind: str | None = None,
    tags_source: str = "ni_structural",
    body_md: str | None = None,
    summary_md: str | None = None,
) -> dict[str, Any]:
    """Insert or update registry row; returns the row dict.

    Tags: on conflict, Obsidian-mirrored tags are preserved unless this call
    explicitly uses tags_source='obsidian' (sync job). NI structural upserts
    only fill empty tag arrays.
    """
    now = datetime.now(timezone.utc)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.vault_notes (
                    domain_key, note_type, object_id, object_id_secondary,
                    vault_path, note_status, lifecycle, title, tags,
                    mention_count, alias_ids, last_article_id, metadata,
                    sources_last_scan_at, note_updated_at, updated_at,
                    tags_source, geo_parent_entity_id, place_kind,
                    body_md, summary_md
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s::jsonb,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (vault_path) DO UPDATE SET
                    note_type = EXCLUDED.note_type,
                    object_id = EXCLUDED.object_id,
                    note_status = EXCLUDED.note_status,
                    lifecycle = CASE
                        WHEN intelligence.vault_notes.lifecycle = 'frozen'
                            THEN intelligence.vault_notes.lifecycle
                        ELSE EXCLUDED.lifecycle
                    END,
                    title = COALESCE(EXCLUDED.title, intelligence.vault_notes.title),
                    tags = CASE
                        WHEN EXCLUDED.tags_source = 'obsidian'
                            THEN EXCLUDED.tags
                        WHEN cardinality(intelligence.vault_notes.tags) = 0
                             AND EXCLUDED.tags IS NOT NULL
                             AND cardinality(EXCLUDED.tags) > 0
                            THEN EXCLUDED.tags
                        ELSE intelligence.vault_notes.tags
                    END,
                    tags_source = CASE
                        WHEN EXCLUDED.tags_source = 'obsidian' THEN 'obsidian'
                        WHEN intelligence.vault_notes.tags_source = 'obsidian'
                            THEN 'obsidian'
                        ELSE EXCLUDED.tags_source
                    END,
                    mention_count = GREATEST(
                        intelligence.vault_notes.mention_count, EXCLUDED.mention_count
                    ),
                    alias_ids = CASE
                        WHEN EXCLUDED.alias_ids IS NOT NULL AND cardinality(EXCLUDED.alias_ids) > 0
                            THEN EXCLUDED.alias_ids
                        ELSE intelligence.vault_notes.alias_ids
                    END,
                    last_article_id = COALESCE(
                        EXCLUDED.last_article_id, intelligence.vault_notes.last_article_id
                    ),
                    metadata = intelligence.vault_notes.metadata || EXCLUDED.metadata,
                    geo_parent_entity_id = COALESCE(
                        EXCLUDED.geo_parent_entity_id,
                        intelligence.vault_notes.geo_parent_entity_id
                    ),
                    place_kind = COALESCE(
                        EXCLUDED.place_kind, intelligence.vault_notes.place_kind
                    ),
                    body_md = COALESCE(EXCLUDED.body_md, intelligence.vault_notes.body_md),
                    summary_md = COALESCE(
                        EXCLUDED.summary_md, intelligence.vault_notes.summary_md
                    ),
                    sources_last_scan_at = EXCLUDED.sources_last_scan_at,
                    note_updated_at = EXCLUDED.note_updated_at,
                    updated_at = EXCLUDED.updated_at
                RETURNING id, domain_key, note_type, object_id, vault_path,
                          note_status, lifecycle, title
                """,
                (
                    domain_key,
                    note_type,
                    int(object_id),
                    object_id_secondary,
                    vault_path,
                    note_status,
                    lifecycle,
                    title,
                    tags or [],
                    int(mention_count or 0),
                    alias_ids or [],
                    last_article_id,
                    json.dumps(metadata or {}),
                    now,
                    now,
                    now,
                    tags_source,
                    geo_parent_entity_id,
                    place_kind,
                    body_md,
                    summary_md,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return {"ok": False}
    return {
        "ok": True,
        "id": row[0],
        "domain_key": row[1],
        "note_type": row[2],
        "object_id": row[3],
        "vault_path": row[4],
        "note_status": row[5],
        "lifecycle": row[6],
        "title": row[7],
    }


def get_vault_note(
    *,
    domain_key: str,
    note_type: str,
    object_id: int,
    object_id_secondary: int | None = None,
) -> dict[str, Any] | None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, note_type, object_id, object_id_secondary,
                       vault_path, note_status, lifecycle, title, tags,
                       mention_count, alias_ids, last_article_id,
                       sources_last_scan_at, note_updated_at, rag_indexed_at,
                       metadata, created_at, updated_at, body_md, summary_md
                FROM intelligence.vault_notes
                WHERE domain_key = %s AND note_type = %s AND object_id = %s
                  AND COALESCE(object_id_secondary, 0) = COALESCE(%s, 0)
                LIMIT 1
                """,
                (domain_key, note_type, int(object_id), object_id_secondary),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "domain_key": row[1],
        "note_type": row[2],
        "object_id": row[3],
        "object_id_secondary": row[4],
        "vault_path": row[5],
        "note_status": row[6],
        "lifecycle": row[7],
        "title": row[8],
        "tags": list(row[9] or []),
        "mention_count": row[10],
        "alias_ids": list(row[11] or []),
        "last_article_id": row[12],
        "sources_last_scan_at": row[13].isoformat() if row[13] else None,
        "note_updated_at": row[14].isoformat() if row[14] else None,
        "rag_indexed_at": row[15].isoformat() if row[15] else None,
        "metadata": row[16] if isinstance(row[16], dict) else {},
        "created_at": row[17].isoformat() if row[17] else None,
        "updated_at": row[18].isoformat() if row[18] else None,
        "body_md": row[19],
        "summary_md": row[20],
    }


def get_vault_note_by_path(vault_path: str) -> dict[str, Any] | None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, note_type, object_id, vault_path,
                       note_status, lifecycle, title
                FROM intelligence.vault_notes
                WHERE vault_path = %s
                LIMIT 1
                """,
                (vault_path,),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "domain_key": row[1],
        "note_type": row[2],
        "object_id": row[3],
        "vault_path": row[4],
        "note_status": row[5],
        "lifecycle": row[6],
        "title": row[7],
    }


def mark_note_ready(
    vault_path: str,
    *,
    lifecycle: str | None = None,
    rag_fingerprint: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.vault_notes
                SET note_status = 'note_ready',
                    lifecycle = COALESCE(%s, lifecycle),
                    note_updated_at = %s,
                    rag_indexed_at = %s,
                    rag_fingerprint = COALESCE(%s, rag_fingerprint),
                    updated_at = %s
                WHERE vault_path = %s
                """,
                (lifecycle, now, now, rag_fingerprint, now, vault_path),
            )
        conn.commit()


def ensure_entity_registry(
    *,
    domain_key: str,
    entity_id: int,
    title: str,
    mention_count: int = 0,
    lifecycle: str = "stub",
    note_status: str = "note_pending",
    alias_ids: list[int] | None = None,
    entity_type: str | None = None,
) -> dict[str, Any]:
    path = entity_vault_rel_path(
        title, domain_key=domain_key, entity_type=entity_type
    )
    return upsert_vault_note(
        domain_key=domain_key,
        note_type="entity",
        object_id=entity_id,
        vault_path=path,
        title=title,
        note_status=note_status,
        lifecycle=lifecycle,
        mention_count=mention_count,
        alias_ids=alias_ids,
    )


def apply_obsidian_tag_mirror(
    vault_path: str,
    *,
    tags: list[str],
    domain_key: str | None = None,
    title: str | None = None,
) -> None:
    """Obsidian wins — overwrite mirrored tags from file."""
    now = datetime.now(timezone.utc)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.vault_notes
                SET tags = %s,
                    tags_source = 'obsidian',
                    tags_synced_at = %s,
                    title = COALESCE(%s, title),
                    domain_key = COALESCE(%s, domain_key),
                    updated_at = %s
                WHERE vault_path = %s
                """,
                (tags, now, title, domain_key, now, vault_path),
            )
            if cur.rowcount == 0 and domain_key:
                # Registry row missing — create stub pointer
                cur.execute(
                    """
                    INSERT INTO intelligence.vault_notes (
                        domain_key, note_type, object_id, vault_path, title,
                        tags, tags_source, tags_synced_at, note_status, lifecycle
                    ) VALUES (
                        %s, 'entity', 0, %s, %s, %s, 'obsidian', %s, 'note_ready', 'seeded'
                    )
                    ON CONFLICT (vault_path) DO UPDATE SET
                        tags = EXCLUDED.tags,
                        tags_source = 'obsidian',
                        tags_synced_at = EXCLUDED.tags_synced_at,
                        updated_at = NOW()
                    """,
                    (domain_key, vault_path, title, tags, now),
                )
        conn.commit()


def replace_vault_note_links(
    *,
    domain_key: str,
    src_vault_path: str,
    links: list[dict[str, Any]],
) -> int:
    """Replace all cached links for a source path (Obsidian sync)."""
    now = datetime.now(timezone.utc)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM intelligence.vault_note_links WHERE src_vault_path = %s",
                (src_vault_path,),
            )
            n = 0
            for link in links:
                cur.execute(
                    """
                    INSERT INTO intelligence.vault_note_links (
                        domain_key, src_vault_path, dst_vault_path, dst_title,
                        link_kind, synced_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (src_vault_path, dst_title, link_kind) DO UPDATE SET
                        dst_vault_path = EXCLUDED.dst_vault_path,
                        domain_key = EXCLUDED.domain_key,
                        synced_at = EXCLUDED.synced_at
                    """,
                    (
                        domain_key,
                        src_vault_path,
                        link.get("dst_vault_path"),
                        str(link.get("dst_title") or "")[:500],
                        link.get("link_kind") or "wikilink",
                        now,
                    ),
                )
                n += 1
            cur.execute(
                """
                UPDATE intelligence.vault_notes
                SET links_synced_at = %s, updated_at = %s
                WHERE vault_path = %s
                """,
                (now, now, src_vault_path),
            )
        conn.commit()
    return n


def set_geo_parent(
    vault_path: str,
    *,
    geo_parent_entity_id: int,
    place_kind: str | None = None,
) -> None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.vault_notes
                SET geo_parent_entity_id = %s,
                    place_kind = COALESCE(%s, place_kind),
                    updated_at = NOW()
                WHERE vault_path = %s
                """,
                (int(geo_parent_entity_id), place_kind, vault_path),
            )
        conn.commit()


def resolve_title_to_vault_path(title: str) -> str | None:
    """Match wikilink title to a registry path via title, slug, or common aliases."""
    from shared.vault_note_contract import (
        SCIENCE_TOPIC_DIR,
        entity_vault_rel_path,
        slugify_entity_name,
    )

    raw = (title or "").strip()
    if not raw or raw.startswith("#"):
        return None
    # Common short forms that should hit seeded living notes
    _ALIAS = {
        "donald trump": "Donald J. Trump",
        "trump": "Donald J. Trump",
        "trump administration": "Donald J. Trump",
        "joe biden": "Joe Biden",
        "joseph r. biden": "Joe Biden",
        "joseph biden": "Joe Biden",
        "us": "United States",
        "u.s.": "United States",
        "usa": "United States",
        "united states": "United States",
    }
    lookup = _ALIAS.get(raw.lower(), raw)
    slug = slugify_entity_name(lookup)
    slug_path = entity_vault_rel_path(lookup)
    science_path = f"{SCIENCE_TOPIC_DIR}/{slug}.md"
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path FROM intelligence.vault_notes
                WHERE lower(title) = lower(%s)
                   OR lower(title) = lower(%s)
                   OR vault_path = %s
                   OR vault_path = %s
                   OR vault_path ILIKE %s
                   OR vault_path ILIKE %s
                ORDER BY
                    CASE
                      WHEN lower(title) = lower(%s) THEN 0
                      WHEN vault_path = %s THEN 1
                      WHEN vault_path = %s THEN 2
                      ELSE 3
                    END
                LIMIT 1
                """,
                (
                    raw,
                    lookup,
                    slug_path,
                    science_path,
                    f"%/{slug}.md",
                    f"%/{slugify_entity_name(raw)}.md",
                    lookup,
                    slug_path,
                    science_path,
                ),
            )
            row = cur.fetchone()
    return row[0] if row else None


def get_expansion_for_storyline(
    domain_key: str, storyline_id: int
) -> dict[str, Any] | None:
    return get_vault_note(
        domain_key=domain_key, note_type="expansion", object_id=int(storyline_id)
    )


def get_expansion_for_article(
    domain_key: str, article_id: int
) -> dict[str, Any] | None:
    """Lookup expansion by metadata.source_article_id or object_id when article-anchored."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, note_type, object_id, vault_path,
                       title, body_md, summary_md, metadata, note_updated_at, updated_at
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type = 'expansion'
                  AND (
                    (metadata->>'source_article_id') = %s
                    OR object_id = %s
                  )
                ORDER BY note_updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (domain_key, str(int(article_id)), int(article_id)),
            )
            row = cur.fetchone()
    if not row:
        return None
    meta = row[8] if isinstance(row[8], dict) else {}
    return {
        "id": row[0],
        "domain_key": row[1],
        "note_type": row[2],
        "object_id": row[3],
        "vault_path": row[4],
        "title": row[5],
        "body_md": row[6],
        "summary_md": row[7],
        "metadata": meta,
        "note_updated_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


def get_latest_daily_briefing(
    *,
    domain_key: str = "global",
    branch: str | None = None,
) -> dict[str, Any] | None:
    """Most recent daily_briefing for domain (global news or science)."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, note_type, object_id, vault_path,
                       title, body_md, summary_md, metadata, note_updated_at, updated_at
                FROM intelligence.vault_notes
                WHERE note_type = 'daily_briefing'
                  AND domain_key = %s
                ORDER BY object_id DESC, note_updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (domain_key,),
            )
            row = cur.fetchone()
    if not row:
        return None
    meta = row[8] if isinstance(row[8], dict) else {}
    if branch and str(meta.get("branch") or "") != branch:
        return None
    return {
        "id": row[0],
        "domain_key": row[1],
        "note_type": row[2],
        "object_id": row[3],
        "vault_path": row[4],
        "title": row[5],
        "body_md": row[6],
        "summary_md": row[7],
        "metadata": meta,
        "note_updated_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
        "briefing_day": meta.get("briefing_day") or str(row[3]),
    }


def list_morning_expansions(
    *,
    briefing_day: str | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Recent expansion notes for home catalog (ongoing then new)."""
    day = (briefing_day or "").strip()[:10]
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if day:
                cur.execute(
                    """
                    SELECT id, domain_key, note_type, object_id, vault_path,
                           title, body_md, summary_md, metadata, note_updated_at
                    FROM intelligence.vault_notes
                    WHERE note_type = 'expansion'
                      AND COALESCE(body_md, summary_md, '') <> ''
                      AND (
                        (metadata->>'briefing_day') = %s
                        OR (metadata->>'window_end') = %s
                        OR note_updated_at::date = %s::date
                      )
                    ORDER BY
                      CASE WHEN metadata->>'briefing_lane' = 'ongoing' THEN 0 ELSE 1 END,
                      note_updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (day, day, day, int(limit)),
                )
            else:
                cur.execute(
                    """
                    SELECT id, domain_key, note_type, object_id, vault_path,
                           title, body_md, summary_md, metadata, note_updated_at
                    FROM intelligence.vault_notes
                    WHERE note_type = 'expansion'
                      AND COALESCE(body_md, summary_md, '') <> ''
                      AND note_updated_at >= NOW() - INTERVAL '2 days'
                    ORDER BY
                      CASE WHEN metadata->>'briefing_lane' = 'ongoing' THEN 0 ELSE 1 END,
                      note_updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (int(limit),),
                )
            rows = cur.fetchall() or []
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = row[8] if isinstance(row[8], dict) else {}
        out.append(
            {
                "id": row[0],
                "domain_key": row[1],
                "note_type": row[2],
                "object_id": row[3],
                "vault_path": row[4],
                "title": row[5],
                "body_md": row[6],
                "summary_md": row[7],
                "metadata": meta,
                "briefing_lane": meta.get("briefing_lane") or "new",
                "briefing_day": meta.get("briefing_day") or meta.get("window_end"),
                "note_updated_at": row[9].isoformat() if row[9] else None,
            }
        )
    return out


def list_priority_current_event_arcs(*, limit: int = 40) -> list[dict[str, Any]]:
    """Rank living event arcs by vault note bulk, recency, and longevity.

    Current Events should surface the biggest / most-updated / longest-running
    notes (storyline + expansion + event wiki), not morning-manager lane labels.
    File bytes on disk win when mirrored ``body_md`` is empty.
    """
    from pathlib import Path

    lim = max(1, min(int(limit), 80))
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH arc_notes AS (
                    SELECT
                        domain_key,
                        CASE
                            WHEN note_type = 'event'
                                AND (metadata->>'storyline_id') ~ '^[0-9]+$'
                            THEN (metadata->>'storyline_id')::bigint
                            ELSE object_id
                        END AS storyline_id,
                        note_type,
                        title,
                        vault_path,
                        body_md,
                        summary_md,
                        metadata,
                        COALESCE(note_updated_at, updated_at) AS note_updated_at,
                        created_at,
                        COALESCE(length(body_md), 0)
                          + COALESCE(length(summary_md), 0) AS pg_chars
                    FROM intelligence.vault_notes
                    WHERE note_type IN ('storyline', 'expansion', 'event')
                      AND object_id IS NOT NULL
                      AND (
                            note_type IN ('storyline', 'expansion')
                         OR (
                              note_type = 'event'
                              AND (metadata->>'storyline_id') ~ '^[0-9]+$'
                         )
                      )
                )
                SELECT
                    domain_key,
                    storyline_id,
                    MAX(title) FILTER (WHERE note_type = 'expansion') AS expansion_title,
                    MAX(title) FILTER (WHERE note_type = 'storyline') AS storyline_title,
                    MAX(title) FILTER (WHERE note_type = 'event') AS event_title,
                    MAX(summary_md) FILTER (WHERE note_type = 'expansion') AS expansion_summary,
                    MAX(body_md) FILTER (WHERE note_type = 'expansion') AS expansion_body,
                    MAX(vault_path) FILTER (WHERE note_type = 'expansion') AS expansion_path,
                    MAX(vault_path) FILTER (WHERE note_type = 'storyline') AS storyline_path,
                    MAX(vault_path) FILTER (WHERE note_type = 'event') AS event_path,
                    SUM(pg_chars)::bigint AS pg_chars,
                    MAX(note_updated_at) AS note_updated_at,
                    MIN(created_at) AS first_seen_at,
                    BOOL_OR(note_type = 'event') AS has_event_note,
                    BOOL_OR(note_type = 'expansion') AS has_expansion
                FROM arc_notes
                WHERE storyline_id IS NOT NULL AND storyline_id > 0
                GROUP BY domain_key, storyline_id
                ORDER BY
                    SUM(pg_chars) DESC,
                    MAX(note_updated_at) DESC NULLS LAST,
                    MIN(created_at) ASC NULLS LAST
                LIMIT %s
                """,
                (lim * 3,),  # headroom before disk-size re-rank
            )
            rows = cur.fetchall() or []

    vault_root: Path | None = None
    try:
        from services.vault_bridge_service import vault_root as _vault_root

        vault_root = _vault_root()
    except Exception:
        vault_root = None

    ranked: list[dict[str, Any]] = []
    for row in rows:
        paths = [p for p in (row[7], row[8], row[9]) if p]
        disk_chars = 0
        if vault_root is not None:
            for rel in paths:
                try:
                    fp = vault_root / str(rel)
                    if fp.is_file():
                        disk_chars = max(disk_chars, int(fp.stat().st_size))
                except OSError:
                    continue
        pg_chars = int(row[10] or 0)
        # Prefer the larger of mirrored prose vs on-disk note file.
        note_chars = max(pg_chars, disk_chars)
        title = (
            (row[2] or row[4] or row[3] or f"Storyline {row[1]}")
        )
        summary = (row[5] or "").strip()
        if not summary and row[6]:
            body = str(row[6]).strip()
            summary = (body[:320] + ("…" if len(body) > 320 else "")) if body else ""
        first_seen = row[12]
        age_days = 0
        if first_seen is not None:
            try:
                age_days = max(0, (datetime.now(timezone.utc) - first_seen).days)
            except Exception:
                age_days = 0
        ranked.append(
            {
                "domain_key": row[0],
                "object_id": int(row[1]),
                "storyline_id": int(row[1]),
                "title": title,
                "summary_md": summary,
                "body_md": row[6],
                "vault_path": row[7] or row[8] or row[9],
                "note_chars": note_chars,
                "pg_chars": pg_chars,
                "disk_chars": disk_chars,
                "note_updated_at": row[11].isoformat() if row[11] else None,
                "first_seen_at": first_seen.isoformat() if first_seen else None,
                "age_days": age_days,
                "has_event_note": bool(row[13]),
                "has_expansion": bool(row[14]),
                "briefing_lane": "ongoing",
            }
        )

    # Final priority: biggest notes, then most recently updated, then longest-running.
    ranked.sort(
        key=lambda r: (
            -int(r.get("note_chars") or 0),
            r.get("note_updated_at") or "",
            -int(r.get("age_days") or 0),
        )
    )
    return ranked[:lim]
