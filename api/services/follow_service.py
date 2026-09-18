"""
Follow registry — quiet track vs living story tiers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.runtime import follow_living_cap
from shared.database.connection import get_ui_db_connection_context

logger = logging.getLogger(__name__)


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _count_living(user_key: str, cur) -> int:
    cur.execute(
        """
        SELECT COUNT(*)::int FROM intelligence.followed_items
        WHERE user_key = %s AND tier = 'living' AND status = 'active'
        """,
        (user_key,),
    )
    return int((cur.fetchone() or [0])[0] or 0)


def _validate_target(cur, object_kind: str, domain_key: str | None, object_id: int) -> None:
    kind = (object_kind or "").strip().lower()
    if kind not in ("episode", "container", "package"):
        raise ValueError("object_kind must be episode|container|package")
    if kind == "container":
        cur.execute(
            """
            SELECT 1 FROM intelligence.tracked_events
            WHERE id = %s AND container_kind IS NOT NULL
            LIMIT 1
            """,
            (int(object_id),),
        )
        if not cur.fetchone():
            raise ValueError("container follow requires tracked_events.container_kind")
    if kind == "episode" and not (domain_key or "").strip():
        raise ValueError("domain_key required for episode follows")


def follow(
    object_kind: str,
    domain_key: str | None,
    object_id: int,
    *,
    tier: str = "quiet",
    user_key: str = "operator",
    notify_on: str = "any_movement",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tier = (tier or "quiet").strip().lower()
    if tier == "living" and object_kind != "episode":
        raise ValueError("tier=living is only valid for object_kind=episode")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            _validate_target(cur, object_kind, domain_key, object_id)
            if tier == "living" and _count_living(user_key, cur) >= follow_living_cap():
                raise ValueError(f"living follow cap ({follow_living_cap()}) reached")
            cur.execute(
                """
                INSERT INTO intelligence.followed_items
                    (object_kind, domain_key, object_id, tier, user_key,
                     notify_on, status, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, 'active', %s::jsonb)
                ON CONFLICT (user_key, object_kind, domain_key, object_id)
                DO UPDATE SET
                    tier = EXCLUDED.tier,
                    notify_on = EXCLUDED.notify_on,
                    status = 'active',
                    metadata = intelligence.followed_items.metadata || EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    object_kind,
                    domain_key,
                    int(object_id),
                    tier,
                    user_key,
                    notify_on,
                    json.dumps(metadata or {}),
                ),
            )
            row = _row(cur)
        conn.commit()
    return dict(row or {})


def unfollow(follow_id: int, *, user_key: str = "operator") -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.followed_items
                SET status = 'archived', updated_at = NOW()
                WHERE id = %s AND user_key = %s
                RETURNING *
                """,
                (int(follow_id), user_key),
            )
            row = _row(cur)
        conn.commit()
    if not row:
        raise LookupError(f"follow {follow_id} not found")
    return row


def list_followed(
    user_key: str = "operator",
    *,
    include_archived: bool = False,
    tier: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["user_key = %s"]
    params: list[Any] = [user_key]
    if not include_archived:
        clauses.append("status <> 'archived'")
    if tier:
        clauses.append("tier = %s")
        params.append(tier)
    sql = f"""
        SELECT * FROM intelligence.followed_items
        WHERE {' AND '.join(clauses)}
        ORDER BY tier DESC, COALESCE(last_surfaced_at, updated_at) DESC NULLS LAST, id DESC
    """
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = _rows(cur)
    return enrich_follow_rows(rows)


def mark_read(follow_id: int, *, user_key: str = "operator") -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.followed_items
                SET last_read_at = NOW(), updated_at = NOW()
                WHERE id = %s AND user_key = %s
                RETURNING *
                """,
                (int(follow_id), user_key),
            )
            row = _row(cur)
        conn.commit()
    if not row:
        raise LookupError(f"follow {follow_id} not found")
    return row


def set_tier(follow_id: int, tier: str, *, user_key: str = "operator") -> dict[str, Any]:
    tier = (tier or "").strip().lower()
    if tier not in ("quiet", "living"):
        raise ValueError("tier must be quiet|living")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.followed_items WHERE id = %s AND user_key = %s",
                (int(follow_id), user_key),
            )
            existing = _row(cur)
            if not existing:
                raise LookupError(f"follow {follow_id} not found")
            if tier == "living" and existing.get("object_kind") != "episode":
                raise ValueError("tier=living requires episode follow")
            if tier == "living" and existing.get("tier") != "living":
                if _count_living(user_key, cur) >= follow_living_cap():
                    raise ValueError(f"living follow cap ({follow_living_cap()}) reached")
            cur.execute(
                """
                UPDATE intelligence.followed_items
                SET tier = %s, updated_at = NOW()
                WHERE id = %s AND user_key = %s
                RETURNING *
                """,
                (tier, int(follow_id), user_key),
            )
            row = _row(cur)
        conn.commit()
    return dict(row or {})


def patch_follow(
    follow_id: int,
    *,
    user_key: str = "operator",
    tier: str | None = None,
    notify_on: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields: list[str] = []
    params: list[Any] = []
    if tier is not None:
        fields.append("tier = %s")
        params.append(tier)
    if notify_on is not None:
        fields.append("notify_on = %s")
        params.append(notify_on)
    if status is not None:
        fields.append("status = %s")
        params.append(status)
    if metadata is not None:
        fields.append("metadata = metadata || %s::jsonb")
        params.append(json.dumps(metadata))
    if not fields:
        raise ValueError("no fields to patch")
    fields.append("updated_at = NOW()")
    params.extend([int(follow_id), user_key])
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if tier == "living":
                cur.execute(
                    "SELECT object_kind, tier FROM intelligence.followed_items WHERE id = %s",
                    (int(follow_id),),
                )
                r = cur.fetchone()
                if r and r[0] != "episode":
                    raise ValueError("tier=living requires episode follow")
                if r and r[1] != "living" and _count_living(user_key, cur) >= follow_living_cap():
                    raise ValueError(f"living follow cap ({follow_living_cap()}) reached")
            cur.execute(
                f"""
                UPDATE intelligence.followed_items
                SET {', '.join(fields)}
                WHERE id = %s AND user_key = %s
                RETURNING *
                """,
                tuple(params),
            )
            row = _row(cur)
        conn.commit()
    if not row:
        raise LookupError(f"follow {follow_id} not found")
    return row


def get_follow_by_id(follow_id: int, *, user_key: str = "operator") -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM intelligence.followed_items WHERE id = %s AND user_key = %s",
                (int(follow_id), user_key),
            )
            row = _row(cur)
    if not row:
        return None
    enriched = enrich_follow_rows([row])
    return enriched[0] if enriched else row


def enrich_follow_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach display title (and optional story_kind) for episode/container follows."""
    if not rows:
        return rows
    from shared.domain_registry import resolve_domain_schema

    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for row in rows:
                r = dict(row)
                kind = str(r.get("object_kind") or "")
                dk = str(r.get("domain_key") or "").strip()
                oid = int(r.get("object_id") or 0)
                title = None
                story_kind = None
                if kind == "episode" and dk and oid > 0:
                    schema = resolve_domain_schema(dk)
                    try:
                        cur.execute(
                            f"SELECT title, story_kind FROM {schema}.storylines WHERE id = %s LIMIT 1",
                            (oid,),
                        )
                        ep = cur.fetchone()
                        if ep:
                            title, story_kind = ep[0], ep[1]
                    except Exception:
                        pass
                elif kind == "container" and oid > 0:
                    cur.execute(
                        "SELECT event_name, container_kind FROM intelligence.tracked_events WHERE id = %s LIMIT 1",
                        (oid,),
                    )
                    te = cur.fetchone()
                    if te:
                        title, story_kind = te[0], te[1]
                if title:
                    r["title"] = str(title)[:500]
                if story_kind:
                    r["story_kind"] = story_kind
                out.append(r)
    return out
