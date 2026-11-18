"""
Politics — EU/UK relationship tracking.

Paths: ``/api/politics/eu_uk/...`` — EU/UK relationship data and tracking.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.shared.database import get_db_connection_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/politics/eu_uk",
    tags=["Politics — EU/UK Relationships"],
    responses={404: {"description": "Not found"}},
)


def _format_date(date_obj: Any) -> str:
    """Format date objects to ISO format string."""
    if date_obj:
        return date_obj.isoformat() if hasattr(date_obj, 'isoformat') else str(date_obj)
    return None


@router.get("/relationships")
async def get_eu_uk_relationships(
    country: Optional[str] = Query(None, description="Filter by country (UK or EU)"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
) -> Dict[str, Any]:
    """
    Get EU/UK relationship tracking data.
    
    This endpoint provides information about the evolving relationship between 
    the European Union and the United Kingdom, including trade agreements, 
    political developments, and diplomatic relations.
    """
    
    conditions = []
    params = []
    
    # Build dynamic WHERE clause based on provided filters
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
            # Get total count
            cur.execute(f"""
                SELECT COUNT(*) FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
            """, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            params.extend([limit, offset])
            cur.execute(f"""
                SELECT id, country, relationship_type, date, description, 
                       source_url, created_at, updated_at
                FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
                ORDER BY date DESC, created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            
            cols = [desc[0] for desc in cur.description]
            relationships = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Format dates in results
            for rel in relationships:
                if rel.get('date'):
                    rel['date'] = _format_date(rel['date'])
                if rel.get('created_at'):
                    rel['created_at'] = _format_date(rel['created_at'])
                if rel.get('updated_at'):
                    rel['updated_at'] = _format_date(rel['updated_at'])
    
    return {
        "success": True,
        "data": relationships,
        "total": total,
        "limit": limit,
        "offset": offset,
        "message": "EU/UK relationship data retrieved successfully"
    }
    return {
        "success": True,
        "data": relationships,
        "total": total,
        "limit": limit,
        "offset": offset,
        "message": "EU/UK relationship data retrieved successfully"
    }


@router.get("/relationships/{id}")
async def get_eu_uk_relationship(
    id: int
) -> Dict[str, Any]:
    """
    Get a specific EU/UK relationship record by ID.
    
    Args:
        id: The database ID of the relationship record
        
    Returns:
        The relationship record with all fields
    """
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
    return {
        "success": True,
        "data": relationship,
        "message": "EU/UK relationship record retrieved successfully"
    }


@router.get("/types")
async def get_relationship_types() -> Dict[str, Any]:
    """
    Get all available EU/UK relationship types.
    
    Returns:
        List of distinct relationship types
    """
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT relationship_type 
                FROM intelligence.eu_uk_relationships
                ORDER BY relationship_type
            """)
    return {
        "success": True,
        "data": types,
        "message": "Relationship types retrieved successfully"
    }


@router.get("/countries")
async def get_countries() -> Dict[str, Any]:
    """
    Get all countries represented in the EU/UK relationship tracking.
    
    Returns:
        List of distinct countries
    """
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT country 
                FROM intelligence.eu_uk_relationships
                ORDER BY country
    return {
        "success": True,
        "data": countries,
        "message": "Countries retrieved successfully"
    }


@router.get("/summary")
async def get_eu_uk_relationship_summary(
    country: Optional[str] = Query(None, description="Filter by country (UK or EU)"),
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Get summary statistics for EU/UK relationships.
    
    Returns:
        Summary of relationship data including counts and time periods
    """
    
    conditions = []
    params = []
    
    # Build dynamic WHERE clause based on provided filters
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
            # Get summary statistics
            cur.execute(f"""
                SELECT 
                    COUNT(*) as total_records,
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date,
                    COUNT(DISTINCT country) as unique_countries,
                    COUNT(DISTINCT relationship_type) as unique_types
                FROM intelligence.eu_uk_relationships
                WHERE {where_clause}
            """, params)
            
            summary = cur.fetchone()
            if not summary:
                return {
                    "success": True,
                    "data": {
                        "total_records": 0,
                        "earliest_date": None,
                        "latest_date": None,
                        "unique_countries": 0,
                        "unique_types": 0
                    },
                    "message": "No data available"
                }
            
            cols = [desc[0] for desc in cur.description]
            summary_dict = dict(zip(cols, summary))
            
            # Format dates
            if summary_dict.get('earliest_date'):
                summary_dict['earliest_date'] = _format_date(summary_dict['earliest_date'])
            if summary_dict.get('latest_date'):
                summary_dict['latest_date'] = _format_date(summary_dict['latest_date'])
    
    return {
        "success": True,
        "data": summary_dict,
        "message": "EU/UK relationship summary retrieved successfully"
    }
            """)
            
            countries = [row[0] for row in cur.fetchall()]
    
    return {
        "success": True,
        "data": countries,
        "message": "Countries retrieved successfully"
    }
            
            types = [row[0] for row in cur.fetchall()]
    
    return {
        "success": True,
        "data": types,
        "message": "Relationship types retrieved successfully"
    }
            cur.execute("""
                SELECT id, country, relationship_type, date, description, 
                       source_url, created_at, updated_at
                FROM intelligence.eu_uk_relationships
                WHERE id = %s
            """, (id,))
            
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="EU/UK relationship record not found")
            
            cols = [desc[0] for desc in cur.description]
            relationship = dict(zip(cols, row))
            
            # Format dates
            if relationship.get('date'):
                relationship['date'] = _format_date(relationship['date'])
            if relationship.get('created_at'):
                relationship['created_at'] = _format_date(relationship['created_at'])
            if relationship.get('updated_at'):
                relationship['updated_at'] = _format_date(relationship['updated_at'])
    
    return {
        "success": True,
        "data": relationship,
        "message": "EU/UK relationship record retrieved successfully"
    }