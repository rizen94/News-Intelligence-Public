"""
Modal handoffs + Editor alerts (v11).

Handoffs always carry package_id as the primary object.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database.connection import get_ui_db_connection_context

logger = logging.getLogger(__name__)

EDITOR_ALERT_REASON_CODES = frozenset(
    {
        "package_ready",
        "reduction_cleared",
        "reduction_blocked",
        "citation_gap",
        "rework",
        "manual",
    }
)

# Packages in these statuses are out of the Editor inbox until sent back.
_EDITOR_ALERT_EXCLUDED_PKG_STATUSES = frozenset(
    {"in_research", "in_narrative", "in_reduction"}
)


def _jsonb(val: Any) -> str:
    return json.dumps(val if val is not None else {})


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def create_handoff(
    *,
    package_id: int | None,
    source_modal: str,
    target_modal: str,
    reason_code: str = "manual",
    note: str | None = None,
    focus_member_id: int | None = None,
    domain_keys: list[str] | None = None,
    created_by: str = "operator",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.modal_handoffs
                    (package_id, source_modal, target_modal, object_type, object_id,
                     focus_member_id, domain_keys, reason_code, note, status,
                     created_by, metadata)
                VALUES (%s, %s, %s, 'editorial_package', %s, %s, %s::text[],
                        %s, %s, 'open', %s, %s::jsonb)
                RETURNING *
                """,
                (
                    package_id,
                    source_modal,
                    target_modal,
                    package_id,
                    focus_member_id,
                    domain_keys or [],
                    reason_code or "manual",
                    note,
                    created_by,
                    _jsonb(metadata or {}),
                ),
            )
            row = _row(cur)
            conn.commit()
            assert row is not None
            return row


def find_open_handoff(
    *,
    package_id: int,
    target_modal: str,
    reason_code: str,
) -> dict[str, Any] | None:
    """Return newest open handoff matching package + target + reason, if any."""
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intelligence.modal_handoffs
                WHERE package_id = %s
                  AND target_modal = %s
                  AND reason_code = %s
                  AND status = 'open'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (package_id, target_modal, reason_code),
            )
            return _row(cur)


def dismiss_open_editor_handoffs(
    package_id: int,
    *,
    rationale: str | None = None,
) -> int:
    """Dismiss all open Editor-inbox handoffs for a package. Returns rows updated."""
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.modal_handoffs
                SET status = 'dismissed',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb)
                        || jsonb_build_object(
                            'dismissed_reason',
                            COALESCE(%s, 'package_sent_for_rework')
                        )
                WHERE package_id = %s
                  AND target_modal = 'editor'
                  AND status = 'open'
                """,
                (rationale or "package_sent_for_rework", package_id),
            )
            n = cur.rowcount or 0
            conn.commit()
            return int(n)


def dismiss_open_process_handoffs(
    package_id: int,
    *,
    rationale: str | None = None,
) -> int:
    """Dismiss open Research/Narrative/Reduction handoffs (package left those queues)."""
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.modal_handoffs
                SET status = 'dismissed',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb)
                        || jsonb_build_object(
                            'dismissed_reason',
                            COALESCE(%s, 'package_ready_for_editor')
                        )
                WHERE package_id = %s
                  AND target_modal IN ('research', 'narrative', 'reduction')
                  AND status = 'open'
                """,
                (rationale or "package_ready_for_editor", package_id),
            )
            n = cur.rowcount or 0
            conn.commit()
            return int(n)


def dismiss_stale_process_handoffs(*, limit: int = 5000) -> int:
    """Dismiss process-modal handoffs whose package is no longer in that modal status."""
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.modal_handoffs h
                SET status = 'dismissed',
                    updated_at = NOW(),
                    metadata = COALESCE(h.metadata, '{}'::jsonb)
                        || jsonb_build_object(
                            'dismissed_reason',
                            'stale_vs_package_status'
                        )
                WHERE h.id IN (
                    SELECT h2.id
                    FROM intelligence.modal_handoffs h2
                    JOIN intelligence.editorial_packages p ON p.id = h2.package_id
                    WHERE h2.status = 'open'
                      AND (
                        (h2.target_modal = 'research' AND p.status IS DISTINCT FROM 'in_research')
                        OR (h2.target_modal = 'narrative' AND p.status IS DISTINCT FROM 'in_narrative')
                        OR (h2.target_modal = 'reduction' AND p.status IS DISTINCT FROM 'in_reduction')
                      )
                    ORDER BY h2.id
                    LIMIT %s
                )
                """,
                (max(1, int(limit)),),
            )
            n = cur.rowcount or 0
            conn.commit()
            return int(n)


def list_handoffs(
    *,
    target_modal: str | None = None,
    status: str | None = "open",
    package_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = ["1=1"]
    args: list[Any] = []
    if target_modal:
        filters.append("h.target_modal = %s")
        args.append(target_modal)
    if status:
        filters.append("h.status = %s")
        args.append(status)
    if package_id is not None:
        filters.append("h.package_id = %s")
        args.append(package_id)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT h.*, p.working_title, p.status AS package_status,
                       p.presentation_kind
                FROM intelligence.modal_handoffs h
                LEFT JOIN intelligence.editorial_packages p ON p.id = h.package_id
                WHERE {" AND ".join(filters)}
                ORDER BY h.created_at DESC, h.id DESC
                LIMIT %s
                """,
                [*args, int(limit)],
            )
            return _rows(cur)


def update_handoff_status(
    handoff_id: int,
    *,
    status: str,
) -> dict[str, Any] | None:
    if status not in ("open", "accepted", "done", "dismissed"):
        raise ValueError(f"Invalid handoff status: {status}")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.modal_handoffs
                SET status = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (status, handoff_id),
            )
            row = _row(cur)
            conn.commit()
            return row


def editor_alerts(*, limit: int = 50) -> list[dict[str, Any]]:
    """Open handoffs targeting Editor — hide packages out for rework."""
    rows = list_handoffs(target_modal="editor", status="open", limit=max(limit * 3, 50))
    out: list[dict[str, Any]] = []
    for row in rows:
        pkg_status = (row.get("package_status") or "").strip()
        if pkg_status in _EDITOR_ALERT_EXCLUDED_PKG_STATUSES:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def request_rework(
    package_id: int,
    *,
    target_modal: str,
    note: str | None = None,
    actor: str = "operator",
    source_modal: str = "editor",
) -> dict[str, Any]:
    if target_modal not in ("research", "narrative", "reduction"):
        raise ValueError("rework target must be research|narrative|reduction")
    src = (source_modal or "editor").strip().lower()
    if src not in ("editor", "reduction", "research", "narrative", "system"):
        raise ValueError("source_modal must be editor|reduction|research|narrative|system")
    from services.editorial_package_service import _append_decision, update_package
    from shared.database.connection import get_ui_db_connection_context

    # Drop off Editor Alerts until Reduction/ready sends the package back.
    dismissed = dismiss_open_editor_handoffs(
        package_id,
        rationale=f"rework_requested→{target_modal}",
    )
    logger.info(
        "rework package_id=%s dismissed_editor_handoffs=%s → %s (from %s)",
        package_id,
        dismissed,
        target_modal,
        src,
    )

    status_map = {
        "research": "in_research",
        "narrative": "in_narrative",
        "reduction": "in_reduction",
    }
    update_package(
        package_id,
        status=status_map[target_modal],
        primary_modal=src if src != "system" else "editor",
        actor=actor,
        modal=src,
        rationale=note or f"rework_requested → {target_modal}",
    )
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            _append_decision(
                cur,
                package_id=package_id,
                action="rework_requested",
                actor=actor,
                modal=src,
                rationale=note or f"rework_requested → {target_modal}",
                metadata={
                    "target_modal": target_modal,
                    "source_modal": src,
                    "dismissed_editor_handoffs": dismissed,
                },
            )
            conn.commit()
    return create_handoff(
        package_id=package_id,
        source_modal=src,
        target_modal=target_modal,
        reason_code="rework",
        note=note,
        created_by=actor,
        metadata={"action": "rework_requested"},
    )
