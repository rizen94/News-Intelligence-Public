"""
Matter docket ledger — legal matter_docket proteins.

Procedural ruling timeline + running legal_status (not geopolitics arc chapters).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

_VALID_STATUS = frozenset({"legal", "not_legal", "contested", "unsettled"})
_DEFAULT_DOMAIN = "legal"


def get_matter_docket(
    storyline_id: int,
    *,
    domain_key: str = _DEFAULT_DOMAIN,
) -> dict[str, Any]:
    dk = (domain_key or _DEFAULT_DOMAIN).strip()
    schema = resolve_domain_schema(dk)
    protein = None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""
                    SELECT id, title, status, summary, updated_at,
                           COALESCE(total_articles, 0)
                    FROM {schema}.storylines WHERE id = %s
                    """,
                    (int(storyline_id),),
                )
                row = cur.fetchone()
                if row:
                    protein = {
                        "storyline_id": int(row[0]),
                        "title": row[1],
                        "status": row[2],
                        "summary": row[3],
                        "updated_at": row[4].isoformat() if row[4] else None,
                        "article_count": int(row[5] or 0),
                        "story_kind": "matter_docket",
                        "domain_key": dk,
                    }
            except Exception as e:
                logger.debug("matter docket protein: %s", e)
                return {"success": False, "error": str(e)[:200]}

    if not protein:
        return {"success": False, "error": "storyline_not_found", "storyline_id": storyline_id}

    status = _get_status(dk, int(storyline_id))
    rulings = _list_rulings(dk, int(storyline_id))
    return {
        "success": True,
        "protein": protein,
        "legal_status": status.get("legal_status", "unsettled"),
        "status_rationale": status.get("status_rationale"),
        "status_updated_at": status.get("updated_at"),
        "rulings": rulings,
    }


def record_ruling(
    *,
    storyline_id: int,
    domain_key: str = _DEFAULT_DOMAIN,
    decision_date: str | date | None = None,
    court: str | None = None,
    holding_summary: str | None = None,
    status_delta: str | None = None,
    article_id: int | None = None,
    apply_status: bool = True,
) -> dict[str, Any]:
    dk = (domain_key or _DEFAULT_DOMAIN).strip()
    delta = (status_delta or "").strip().lower() or None
    if delta and delta not in _VALID_STATUS:
        return {"success": False, "error": "invalid_status_delta", "status_delta": status_delta}

    d_date: date | None = None
    if isinstance(decision_date, date) and not isinstance(decision_date, datetime):
        d_date = decision_date
    elif decision_date:
        try:
            d_date = date.fromisoformat(str(decision_date)[:10])
        except ValueError:
            return {"success": False, "error": "invalid_decision_date"}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.matter_ruling_events (
                    domain_key, storyline_id, decision_date, court,
                    holding_summary, status_delta, article_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    dk,
                    int(storyline_id),
                    d_date,
                    court,
                    holding_summary,
                    delta,
                    article_id,
                ),
            )
            rid = int(cur.fetchone()[0])
            if apply_status and delta:
                cur.execute(
                    """
                    INSERT INTO intelligence.matter_docket_status (
                        domain_key, storyline_id, legal_status, status_rationale
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (domain_key, storyline_id) DO UPDATE SET
                        legal_status = EXCLUDED.legal_status,
                        status_rationale = EXCLUDED.status_rationale,
                        updated_at = NOW()
                    """,
                    (
                        dk,
                        int(storyline_id),
                        delta,
                        (holding_summary or "")[:500] or None,
                    ),
                )
        conn.commit()
    return {"success": True, "ruling_id": rid, "legal_status": delta}


def set_legal_status(
    *,
    storyline_id: int,
    legal_status: str,
    domain_key: str = _DEFAULT_DOMAIN,
    rationale: str | None = None,
) -> dict[str, Any]:
    dk = (domain_key or _DEFAULT_DOMAIN).strip()
    status = (legal_status or "").strip().lower()
    if status not in _VALID_STATUS:
        return {"success": False, "error": "invalid_legal_status"}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.matter_docket_status (
                    domain_key, storyline_id, legal_status, status_rationale
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (domain_key, storyline_id) DO UPDATE SET
                    legal_status = EXCLUDED.legal_status,
                    status_rationale = EXCLUDED.status_rationale,
                    updated_at = NOW()
                RETURNING legal_status, updated_at
                """,
                (dk, int(storyline_id), status, rationale),
            )
            row = cur.fetchone()
        conn.commit()
    return {
        "success": True,
        "legal_status": row[0],
        "updated_at": row[1].isoformat() if row and row[1] else None,
    }


def _get_status(domain_key: str, storyline_id: int) -> dict[str, Any]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT legal_status, status_rationale, updated_at
                    FROM intelligence.matter_docket_status
                    WHERE domain_key = %s AND storyline_id = %s
                    """,
                    (domain_key, storyline_id),
                )
                row = cur.fetchone()
                if not row:
                    return {"legal_status": "unsettled"}
                return {
                    "legal_status": row[0],
                    "status_rationale": row[1],
                    "updated_at": row[2].isoformat() if row[2] else None,
                }
            except Exception as e:
                logger.debug("matter_docket_status: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
                return {"legal_status": "unsettled"}


def _list_rulings(domain_key: str, storyline_id: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT id, decision_date, court, holding_summary, status_delta,
                           article_id, created_at
                    FROM intelligence.matter_ruling_events
                    WHERE domain_key = %s AND storyline_id = %s
                    ORDER BY decision_date DESC NULLS LAST, created_at DESC
                    LIMIT 100
                    """,
                    (domain_key, storyline_id),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    for k in ("decision_date", "created_at"):
                        if d.get(k) and hasattr(d[k], "isoformat"):
                            d[k] = d[k].isoformat()
                    out.append(d)
            except Exception as e:
                logger.debug("matter_ruling_events: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
    return out
