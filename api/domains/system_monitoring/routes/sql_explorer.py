"""
Read-only SQL explorer for local / trusted networks.

Enable with NEWS_INTEL_SQL_EXPLORER=true. Uses a dedicated short-lived connection
with default_transaction_read_only=on, statement timeout, and row cap.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg2
from config.settings import SQL_EXPLORER_ENABLED
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from shared.database.connection import get_db_connect_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system_monitoring/sql_explorer", tags=["System Monitoring"])

_MAX_SQL_CHARS = 20_000
_MAX_ROWS_CAP = 2000
_DEFAULT_MAX_ROWS = 500
_STATEMENT_TIMEOUT_MS = 45_000


def _semicolon_outside_strings(sql: str) -> bool:
    """True if there is a semicolon not inside a single-quoted literal (SQL standard '' escape)."""
    s = sql.rstrip().rstrip(";").strip()
    in_quote = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "'":
            if in_quote and i + 1 < len(s) and s[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
            i += 1
            continue
        if c == ";" and not in_quote:
            return True
        i += 1
    return False


class SqlExplorerQueryBody(BaseModel):
    sql: str = Field(..., max_length=_MAX_SQL_CHARS)
    max_rows: int = Field(_DEFAULT_MAX_ROWS, ge=1, le=_MAX_ROWS_CAP)


def _reject_if_disabled() -> None:
    if not SQL_EXPLORER_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="SQL explorer is disabled. Set NEWS_INTEL_SQL_EXPLORER=true on the API process.",
        )


def _validate_sql(sql: str) -> str:
    s = (sql or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="Empty SQL")
    if _semicolon_outside_strings(s):
        raise HTTPException(
            status_code=400,
            detail="Only one statement per request; remove extra semicolons or run one query at a time.",
        )
    core = s.rstrip().rstrip(";").strip()
    low = core.lower()
    if not (
        low.startswith("select")
        or low.startswith("with")
        or low.startswith("explain")
        or low.startswith("table ")
    ):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT, WITH … SELECT, TABLE, or EXPLAIN … are allowed.",
        )
    return core


@router.get("/enabled")
def sql_explorer_enabled() -> dict[str, Any]:
    """Always 200 — lets the UI show setup instructions when disabled."""
    return {"success": True, "enabled": SQL_EXPLORER_ENABLED}


@router.get("/schema")
def sql_explorer_schema() -> dict[str, Any]:
    """Columns for user schemas (excludes pg_catalog / information_schema)."""
    _reject_if_disabled()
    kwargs = get_db_connect_kwargs()
    kwargs["options"] = (
        f"-c statement_timeout={_STATEMENT_TIMEOUT_MS} -c default_transaction_read_only=on"
    )
    conn = psycopg2.connect(**kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_schema NOT LIKE 'pg\\_%%' ESCAPE '\\'
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    tables: dict[str, dict[str, Any]] = {}
    for table_schema, table_name, column_name, data_type, is_nullable in rows:
        key = f"{table_schema}.{table_name}"
        if key not in tables:
            tables[key] = {"schema": table_schema, "table": table_name, "columns": []}
        tables[key]["columns"].append(
            {
                "name": column_name,
                "data_type": data_type,
                "nullable": (is_nullable == "YES"),
            }
        )
    return {
        "success": True,
        "tables": sorted(tables.values(), key=lambda t: (t["schema"], t["table"])),
    }


@router.post("/query")
def sql_explorer_query(body: SqlExplorerQueryBody) -> dict[str, Any]:
    _reject_if_disabled()
    sql = _validate_sql(body.sql)
    kwargs = get_db_connect_kwargs()
    kwargs["options"] = (
        f"-c statement_timeout={_STATEMENT_TIMEOUT_MS} -c default_transaction_read_only=on"
    )
    conn = psycopg2.connect(**kwargs)
    columns: list[str] = []
    rows: list[list[Any]] = []
    truncated = False
    rowcount: int | None = None
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                columns = [d[0] for d in cur.description]
            rowcount = cur.rowcount
            limit = min(body.max_rows, _MAX_ROWS_CAP)
            batch = cur.fetchmany(limit + 1)
            if len(batch) > limit:
                truncated = True
                batch = batch[:limit]
            rows = [list(r) for r in batch]
        conn.rollback()
    except HTTPException:
        raise
    except Exception as e:
        logger.info("sql_explorer query error: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        conn.close()

    return {
        "success": True,
        "columns": columns,
        "rows": rows,
        "row_count_returned": len(rows),
        "truncated": truncated,
        "cursor_rowcount": rowcount,
    }
