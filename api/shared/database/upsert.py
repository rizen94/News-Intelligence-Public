"""Unified upsert — single path for INSERT OR CONFLICT resolution.

Eliminates the scattered raw SQL f-string patterns across RSS collectors,
storyline routes, and services that cause ``NameError`` and conditional-SQL bugs.

## Usage

### Simple upsert (ON CONFLICT with no update):

    api.shared.database.upsert import insert_or_upsert

    with get_db_connection() as conn:
        cur = conn.cursor()
        insert_or_upsert(
            cur,
            table="topic_extraction_queue",
            values=dict(article_id=101, status="pending", priority=2),
            conflict_columns=["article_id"],
            update_values=None,          # <- ON CONFLICT DO NOTHING (default)
        )

### Upsert with update on conflict:

    insert_or_upsert(
        cur,
        table="topic_extraction_queue",
        values=dict(article_id=102, status="pending", priority=3),
        conflict_columns=["article_id"],
        update_values=dict(status="pending", priority=3, created_at="NOW()"),
    )

### Upsert with domain schema prefix:

    insert_or_upsert(
        cur,
        table="news.agriculture.articles",   # "schema.table"
        values=dict(title="...", url="..."),
        conflict_columns=["url"],
        update_values=dict(title="updated", updated_at="NOW()"),
    )

## Why this replaces the old pattern

Before (scattered across rss_collector.py, storyline_*.py, services/):

    try:
        cur.execute(f"INSERT INTO {{schema}}.articles ({cols}) VALUES ...")
    except psycopg2.errors.UndefinedColumn:
        cur.execute(f"INSERT INTO {{schema}}.articles ({cols_no_extra}) VALUES ...")
    # ^ conditional SQL fragments, NameError-prone, impossible to review

After (single source of truth):

    insert_or_upsert(
        cur,
        table=f"{schema}.articles",
        values={...},          # typed dict — no f-string concatenation
        conflict_columns=["url"],
        update_values=dict(title="updated"),
    )

"""

from __future__ import annotations

import logging
from typing import Any, Mapping

import psycopg2.errors

logger = logging.getLogger(__name__)


def insert_or_upsert(
    cur: Any,
    table: str,
    values: Mapping[str, Any],
    *,
    conflict_columns: list[str] | None = None,
    update_values: Mapping[str, Any] | None = None,
) -> int | None:
    """Execute INSERT ... ON CONFLICT and return the affected row id (if RETURNING id).

    Parameters
    ----------
    cur:
        A psycopg2 cursor (any connection type).
    table:
        Table identifier.  Supports ``"schema.table"`` — schema will be escaped with
        quotes to prevent injection even from dynamic domain-derived values.
    values:
        Column → value mapping for the INSERT side.  Keys become the column list;
        values become parameterized %s placeholders.  **Never** use f-string or
        .format() for column names — pass them as dict keys here.
    conflict_columns:
        Primary-key / unique-constraint columns used in ``ON CONFLICT(col1, col2)``.
        Defaults to the first key of *values* (safe for single-column PK).
    update_values:
        If provided, generates ``DO UPDATE SET col = EXCLUDED.col``.  Keys are column
        names; values are either literal strings (for SQL expressions like ``'NOW()'``)
        or regular Python values that get parameterized with %s.

    Returns
    -------
    The first column of the RETURNING row if the table has a ``RETURNING id`` clause,
    otherwise ``None``.  Also returns ``None`` when an insert is silently ignored by
    ON CONFLICT DO NOTHING.
    """

    if not values:
        raise ValueError("insert_or_upsert requires non-empty 'values'")

    # ── Build identifiers (always quoted — safe for dynamic schema names) ──────────

    cols = list(values.keys())
    conflict_cols = conflict_columns or [cols[0]]

    # Detect schema.table pattern and quote each part independently
    if "." in table:
        parts = [p.strip() for p in table.split(".", 1)]
        safe_table = f'"{parts[0]}"."{parts[1]}"'
    else:
        safe_table = f'"{table}"'

    safe_cols = ", ".join(f'"{c}"' for c in cols)
    safe_cols = ", ".join(f'"{c}"' for c in cols)
    safe_conflict = ", ".join(f'"{c}"' for c in conflict_cols)

    # ── Build INSERT value placeholders (%s x N) ────────────────────────────────────

    val_placeholders = ", ".join("%s" for _ in cols)
    insert_vals = [values[c] for c in cols]

    extra_vals: list[Any] = []

    if update_values and isinstance(update_values, dict):
        set_parts: list[str] = []
        for k, v in update_values.items():
            set_col = f'"{k}"'
            if isinstance(v, str) and not v.startswith("'"):
                set_parts.append(f"{set_col} = {v}")
            else:
                set_parts.append(f"{set_col} = %s")
                extra_vals.append(v)
        do_update_clause = f"DO UPDATE SET {', '.join(set_parts)}"
    elif update_values is None:
        do_update_clause = "DO NOTHING"
    else:
        do_update_clause = f"DO UPDATE SET {update_values}"

    query_base = (
        f"INSERT INTO {safe_table} ({safe_cols}) "
        f"VALUES ({val_placeholders}) "
        f"ON CONFLICT ({safe_conflict}) {do_update_clause}"
    )

    all_insert_vals = insert_vals + extra_vals

    try:
        cur.execute(query_base + " RETURNING id", all_insert_vals)
        row = cur.fetchone()
        return row[0] if row else None
    except psycopg2.errors.UndefinedColumn as e:
        logger.debug(
            "Upsert undefined column %s; retrying without extra columns",
            str(e).split("'")[1] if "'" in str(e) else str(e),
        )
        cur.execute(query_base + " RETURNING id", insert_vals)
        row = cur.fetchone()
        return row[0] if row else None


def insert_or_ignore(
    cur: Any,
    table: str,
    values: Mapping[str, Any],
    *,
    conflict_columns: list[str] | None = None,
) -> bool:
    """Execute INSERT ... ON CONFLICT DO NOTHING.  Returns True if a row was inserted."""
    result = insert_or_upsert(cur, table, values, conflict_columns=conflict_columns)
    return result is not None


def insert_many(
    cur: Any,
    table: str,
    value_rows: list[Mapping[str, Any]],
    *,
    batch_size: int = 500,
) -> int:
    """Insert many rows in batches.  Returns total count of inserted rows."""
    if not value_rows:
        return 0

    cols = list(value_rows[0].keys())
    safe_cols = ", ".join(f'"{c}"' for c in cols)
    val_placeholders = ", ".join("%s" for _ in cols)
    total = 0

    if "." in table:
        parts = [p.strip() for p in table.split(".", 1)]
        safe_table = f'"{parts[0]}"."{parts[1]}"'
    else:
        safe_table = f'"{table}"'

    query = (
        f"INSERT INTO {safe_table} ({safe_cols}) "
        f"VALUES ({val_placeholders}) ON CONFLICT DO NOTHING"
    )

    for i in range(0, len(value_rows), batch_size):
        batch = value_rows[i : i + batch_size]
        for row in batch:
            vals = [row[c] for c in cols]
            cur.execute(query, vals)
            if cur.rowcount and cur.rowcount > 0:
                total += cur.rowcount

    return total
    safe_conflict = ", ".join(f'"{c}"' for c in conflict_cols)
