"""
Politics — EU/UK relationship tracking.

Paths: ``/api/politics/eu_uk/...`` — EU/UK relationship data and tracking.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.shared.database import get_db_connection_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/politics/eu_uk",
    tags=["Politics — EU/UK Relationships"],
    responses={404: {"description": "Not found"}},
)


def _format_date(date_obj: Any) -> str | None:
    if date_obj is None:
        return None
    if hasattr(date_obj, "isoformat"):
        return date_obj.isoformat()
    return str(date_obj)


def _row_dict(cur, row) -> dict[str, Any]:
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row, strict=False))


def _format_relationship_row(rel: dict[str, Any]) -> None:
    rel["date"] = _format_date(rel.get("date"))
    rel["created_at"] = _format_date(rel.get("created_at"))
    rel["updated_at"] = _format_date(rel.get("updated_at"))


@router.get("/relationships")
async def get_eu_uk_relationships(
    country: str | None = Query(None, description="Filter by country (UK or EU)"),
    relationship_type: str | None = Query(None, description="Filter by relationship type"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []

    if country:
        conditions.append("country ILIKE %s")
        params.append(f"%{country}%")
    if relationship_type:
        conditions.append("relationship_type ILIKE %s")
        params.append(f"%{relationship_type}%")
    if start_date:
        conditions.append("date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("date <= %s")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
                """,
                params,
            )
            total = cur.fetchone()[0]

            page_params = list(params) + [limit, offset]
            cur.execute(
                f"""
                SELECT id, country, relationship_type, date, description,
                       source_url, created_at, updated_at
                FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
                ORDER BY date DESC, created_at DESC
                LIMIT %s OFFSET %s
                """,
                page_params,
            )
            relationships = [_row_dict(cur, row) for row in cur.fetchall()]
            for rel in relationships:
                _format_relationship_row(rel)

    return {
        "success": True,
        "data": relationships,
        "total": total,
        "limit": limit,
        "offset": offset,
        "message": "EU/UK relationship data retrieved successfully",
    }


@router.get("/relationships/{id}")
async def get_eu_uk_relationship(id: int) -> dict[str, Any]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, country, relationship_type, date, description,
                       source_url, created_at, updated_at
                FROM intelligence.eu_uk_relationships
                WHERE id = %s
                """,
                (id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="EU/UK relationship record not found")
            relationship = _row_dict(cur, row)
            _format_relationship_row(relationship)

    return {
        "success": True,
        "data": relationship,
        "message": "EU/UK relationship record retrieved successfully",
    }


@router.get("/types")
async def get_relationship_types() -> dict[str, Any]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT relationship_type
                FROM intelligence.eu_uk_relationships
                ORDER BY relationship_type
                """
            )
            types = [row[0] for row in cur.fetchall()]

    return {
        "success": True,
        "data": types,
        "message": "Relationship types retrieved successfully",
    }


@router.get("/countries")
async def get_countries() -> dict[str, Any]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT country
                FROM intelligence.eu_uk_relationships
                ORDER BY country
                """
            )
            countries = [row[0] for row in cur.fetchall()]

    return {
        "success": True,
        "data": countries,
        "message": "Countries retrieved successfully",
    }


@router.get("/summary")
async def get_eu_uk_relationship_summary(
    country: str | None = Query(None),
    relationship_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> dict[str, Any]:
    conditions: list[str] = []
    params: list[Any] = []

    if country:
        conditions.append("country ILIKE %s")
        params.append(f"%{country}%")
    if relationship_type:
        conditions.append("relationship_type ILIKE %s")
        params.append(f"%{relationship_type}%")
    if start_date:
        conditions.append("date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("date <= %s")
        params.append(end_date)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) as total_records,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date,
                    COUNT(DISTINCT country) as unique_countries,
                    COUNT(DISTINCT relationship_type) as unique_types
                FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
                """,
                params,
            )
            row = cur.fetchone()
            if not row:
                summary_dict = {
                    "total_records": 0,
                    "earliest_date": None,
                    "latest_date": None,
                    "unique_countries": 0,
                    "unique_types": 0,
                }
            else:
                summary_dict = _row_dict(cur, row)
                summary_dict["earliest_date"] = _format_date(summary_dict.get("earliest_date"))
                summary_dict["latest_date"] = _format_date(summary_dict.get("latest_date"))

    return {
        "success": True,
        "data": summary_dict,
        "message": "EU/UK relationship summary retrieved successfully",
    }