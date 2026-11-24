"""Resolve retired storyline ids to canonical episode ids (merge + lineage table)."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def record_storyline_lineage(
    conn,
    *,
    domain_key: str,
    old_storyline_id: int,
    canonical_storyline_id: int,
    reason: str = "merged",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Upsert one old→canonical mapping."""
    oid = int(old_storyline_id)
    cid = int(canonical_storyline_id)
    if oid <= 0 or cid <= 0 or oid == cid:
        return
    meta = metadata or {}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO intelligence.storyline_id_lineage
                (domain_key, old_storyline_id, canonical_storyline_id, reason, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (domain_key, old_storyline_id)
            DO UPDATE SET
                canonical_storyline_id = EXCLUDED.canonical_storyline_id,
                reason = EXCLUDED.reason,
                merged_at = NOW(),
                metadata = intelligence.storyline_id_lineage.metadata || EXCLUDED.metadata
            """,
            (domain_key, oid, cid, reason[:120], json.dumps(meta)),
        )


def resolve_canonical_storyline_id(domain_key: str, storyline_id: int) -> int:
    """Return active canonical id; 0 if unresolvable."""
    sid = int(storyline_id or 0)
    if sid <= 0:
        return 0
    try:
        from api.shared.database import get_db_connection_context
        from api.shared.domain_registry import resolve_domain_schema
    except Exception:
        return sid

    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            return _resolve_with_cursor(cur, domain_key, schema, sid)


def _resolve_with_cursor(cur, domain_key: str, schema: str, storyline_id: int) -> int:
    visited: set[int] = set()
    current = int(storyline_id)
    for _ in range(32):
        if current in visited:
            break
        visited.add(current)
        cur.execute(
            f"""
            SELECT id, merged_into_id, COALESCE(status, 'active')
            FROM {schema}.storylines
            WHERE id = %s
            """,
            (current,),
        )
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """
                SELECT canonical_storyline_id
                FROM intelligence.storyline_id_lineage
                WHERE domain_key = %s AND old_storyline_id = %s
                """,
                (domain_key, current),
            )
            lr = cur.fetchone()
            if lr and lr[0]:
                current = int(lr[0])
                continue
            return 0
        sl_id, merged_into, status = int(row[0]), row[1], str(row[2] or "active").lower()
        if merged_into is None:
            if status in ("merged", "deleted", "archived"):
                return 0
            return sl_id
        current = int(merged_into)
    return current if current > 0 else 0


def reader_storyline_href(domain_key: str, storyline_id: int) -> str | None:
    """Href target for reader; None when id does not resolve."""
    canonical = resolve_canonical_storyline_id(domain_key, storyline_id)
    if canonical <= 0:
        return None
    return f"/storylines/{domain_key}/{canonical}"


def batch_resolve_canonical_ids(
    domain_key: str, storyline_ids: list[int]
) -> dict[int, int]:
    """Map requested ids → canonical ids (omit unresolvable)."""
    out: dict[int, int] = {}
    for raw in storyline_ids:
        sid = int(raw or 0)
        if sid <= 0:
            continue
        canonical = resolve_canonical_storyline_id(domain_key, sid)
        if canonical > 0:
            out[sid] = canonical
    return out


def _resolve_active_from_prefetch(
    raw_id: int,
    *,
    lineage: dict[int, int],
    rows: dict[int, tuple[int | None, str]],
) -> int:
    visited: set[int] = set()
    current = int(raw_id)
    for _ in range(32):
        if current in visited:
            return 0
        visited.add(current)
        while current in lineage:
            nxt = lineage[current]
            if nxt in visited:
                return 0
            current = nxt
        if current not in rows:
            return 0
        merged_into, status = rows[current]
        if merged_into is not None:
            current = int(merged_into)
            continue
        if status in ("merged", "deleted", "archived"):
            return 0
        if status == "active":
            return current
        return 0
    return 0


def _prefetch_storyline_rows(
    cur, schema: str, seed_ids: set[int]
) -> dict[int, tuple[int | None, str]]:
    """Load storyline id rows plus merge-chain targets for hub member resolution."""
    rows: dict[int, tuple[int | None, str]] = {}
    pending = {int(x) for x in seed_ids if int(x) > 0}
    for _ in range(32):
        missing = pending - set(rows.keys())
        if not missing:
            break
        cur.execute(
            f"""
            SELECT id, merged_into_id, COALESCE(status, 'active')
            FROM {schema}.storylines
            WHERE id = ANY(%s)
            """,
            (list(missing),),
        )
        for r in cur.fetchall() or []:
            sid = int(r[0])
            merged = int(r[1]) if r[1] is not None else None
            status = str(r[2] or "active").lower()
            rows[sid] = (merged, status)
            if merged is not None:
                pending.add(int(merged))
    return rows


def batch_resolve_active_storyline_ids_with_cursor(
    cur,
    domain_key: str,
    schema: str,
    storyline_ids: list[int],
) -> dict[int, int]:
    """Map each registry id → active canonical storyline id (unresolved omitted)."""
    requested = sorted({int(x) for x in storyline_ids if int(x) > 0})
    if not requested:
        return {}

    lineage: dict[int, int] = {}
    to_fetch = set(requested)
    for _ in range(4):
        if not to_fetch:
            break
        cur.execute(
            """
            SELECT old_storyline_id, canonical_storyline_id
            FROM intelligence.storyline_id_lineage
            WHERE domain_key = %s AND old_storyline_id = ANY(%s)
            """,
            (domain_key, list(to_fetch)),
        )
        new_targets: set[int] = set()
        for old_id, canon_id in cur.fetchall() or []:
            if not old_id or not canon_id:
                continue
            oid, cid = int(old_id), int(canon_id)
            lineage[oid] = cid
            new_targets.add(cid)
        to_fetch = new_targets - set(lineage.keys()) - set(requested)

    rows = _prefetch_storyline_rows(
        cur, schema, set(requested) | set(lineage.values())
    )
    out: dict[int, int] = {}
    for raw in requested:
        active = _resolve_active_from_prefetch(raw, lineage=lineage, rows=rows)
        if active > 0:
            out[raw] = active
    return out


def ordered_active_hub_member_ids(
    storyline_ids: list[int], resolved: dict[int, int]
) -> list[int]:
    """Preserve registry order; dedupe to unique active member ids."""
    out: list[int] = []
    seen: set[int] = set()
    for raw in storyline_ids:
        try:
            rid = int(raw)
        except (TypeError, ValueError):
            continue
        if rid <= 0:
            continue
        active = resolved.get(rid, 0)
        if active > 0 and active not in seen:
            seen.add(active)
            out.append(active)
    return out