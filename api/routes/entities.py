"""
Entities API Routes for News Intelligence System v3.0
Provides entity extraction, management, and analytics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Enums
class EntityType(str, Enum):
    """Entity types"""
    PERSON = "PERSON"
    ORGANIZATION = "ORG"
    LOCATION = "GPE"
    MISC = "MISC"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    DATE = "DATE"
    TIME = "TIME"

# Pydantic models
class EntityBase(BaseModel):
    """Base entity model"""
    text: str = Field(..., description="Entity text")
    type: EntityType = Field(..., description="Entity type")
    confidence: float = Field(0.0, description="Confidence score")

class EntityCreate(EntityBase):
    """Entity creation model"""
    pass

class EntityUpdate(BaseModel):
    """Entity update model"""
    text: Optional[str] = None
    type: Optional[EntityType] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class Entity(EntityBase):
    """Complete entity model"""
    id: int = Field(..., description="Entity ID")
    frequency: int = Field(1, description="Frequency count")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Entity metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

class EntityList(BaseModel):
    """Entity list response"""
    entities: List[Entity] = Field(..., description="List of entities")
    total: int = Field(..., description="Total number of entities")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class EntityStats(BaseModel):
    """Entity statistics model"""
    total_entities: int = Field(..., description="Total entities")
    entities_by_type: Dict[str, int] = Field(..., description="Entities by type")
    most_frequent: List[Dict[str, Any]] = Field(..., description="Most frequent entities")
    recent_entities: List[Dict[str, Any]] = Field(..., description="Recently discovered entities")
    confidence_distribution: Dict[str, int] = Field(..., description="Confidence distribution")

# API Endpoints

@router.get("/", response_model=EntityList)
async def get_entities(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    search: Optional[str] = Query(None, description="Search query"),
    min_confidence: Optional[float] = Query(None, description="Minimum confidence score"),
    sort_by: str = Query("frequency", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order")
):
    """Get list of entities with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if entity_type:
            where_conditions.append("type = %s")
            params.append(entity_type.value)
        
        if search:
            where_conditions.append("text ILIKE %s")
            params.append(f"%{search}%")
        
        if min_confidence is not None:
            where_conditions.append("confidence >= %s")
            params.append(min_confidence)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM entities {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get entities
        order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"
        entities_query = f"""
            SELECT 
                id, text, type, frequency, confidence, first_seen, last_seen, metadata, created_at
            FROM entities 
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(entities_query, params)
        
        entities = []
        for row in cursor.fetchall():
            entity = Entity(
                id=row[0],
                text=row[1],
                type=row[2],
                frequency=row[3],
                confidence=row[4],
                first_seen=row[5],
                last_seen=row[6],
                metadata=row[7] or {},
                created_at=row[8]
            )
            entities.append(entity)
        
        cursor.close()
        conn.close()
        
        return EntityList(
            entities=entities,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch entities: {str(e)}"
        )

@router.get("/{entity_id}", response_model=Entity)
async def get_entity(entity_id: int = Path(..., description="Entity ID")):
    """Get specific entity by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, text, type, frequency, confidence, first_seen, last_seen, metadata, created_at
            FROM entities 
            WHERE id = %s
        """, (entity_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity = Entity(
            id=row[0],
            text=row[1],
            type=row[2],
            frequency=row[3],
            confidence=row[4],
            first_seen=row[5],
            last_seen=row[6],
            metadata=row[7] or {},
            created_at=row[8]
        )
        
        cursor.close()
        conn.close()
        
        return entity
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch entity: {str(e)}"
        )

@router.post("/", response_model=Entity)
async def create_entity(entity_data: EntityCreate):
    """Create new entity"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if entity already exists
        cursor.execute("SELECT id FROM entities WHERE text = %s AND type = %s", (entity_data.text, entity_data.type.value))
        existing = cursor.fetchone()
        
        if existing:
            # Update frequency and last_seen
            cursor.execute("""
                UPDATE entities 
                SET frequency = frequency + 1, last_seen = %s
                WHERE id = %s
            """, (datetime.utcnow(), existing[0]))
            conn.commit()
            cursor.close()
            conn.close()
            return await get_entity(existing[0])
        
        # Insert new entity
        cursor.execute("""
            INSERT INTO entities (
                text, type, confidence, frequency, first_seen, last_seen, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            entity_data.text,
            entity_data.type.value,
            entity_data.confidence,
            1,
            datetime.utcnow(),
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        entity_id = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return created entity
        return await get_entity(entity_id)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create entity: {str(e)}"
        )

@router.put("/{entity_id}", response_model=Entity)
async def update_entity(
    entity_id: int = Path(..., description="Entity ID"),
    entity_data: EntityUpdate = Body(..., description="Entity update data")
):
    """Update entity"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if entity exists
        cursor.execute("SELECT id FROM entities WHERE id = %s", (entity_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if entity_data.text is not None:
            update_fields.append("text = %s")
            params.append(entity_data.text)
        
        if entity_data.type is not None:
            update_fields.append("type = %s")
            params.append(entity_data.type.value)
        
        if entity_data.confidence is not None:
            update_fields.append("confidence = %s")
            params.append(entity_data.confidence)
        
        if entity_data.metadata is not None:
            update_fields.append("metadata = %s")
            params.append(entity_data.metadata)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        params.append(entity_id)
        
        update_query = f"""
            UPDATE entities 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated entity
        return await get_entity(entity_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update entity: {str(e)}"
        )

@router.delete("/{entity_id}")
async def delete_entity(entity_id: int = Path(..., description="Entity ID")):
    """Delete entity"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if entity exists
        cursor.execute("SELECT id FROM entities WHERE id = %s", (entity_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Entity not found")
        
        # Delete entity
        cursor.execute("DELETE FROM entities WHERE id = %s", (entity_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Entity deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete entity: {str(e)}"
        )

@router.get("/stats/overview", response_model=EntityStats)
async def get_entity_stats():
    """Get entity statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get total entities
        cursor.execute("SELECT COUNT(*) FROM entities")
        total_entities = cursor.fetchone()[0]
        
        # Get entities by type
        cursor.execute("""
            SELECT type, COUNT(*) 
            FROM entities 
            GROUP BY type 
            ORDER BY COUNT(*) DESC
        """)
        entities_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get most frequent entities
        cursor.execute("""
            SELECT text, type, frequency, confidence
            FROM entities 
            ORDER BY frequency DESC 
            LIMIT 10
        """)
        most_frequent = [
            {
                "text": row[0],
                "type": row[1],
                "frequency": row[2],
                "confidence": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get recent entities
        cursor.execute("""
            SELECT text, type, first_seen, confidence
            FROM entities 
            ORDER BY first_seen DESC 
            LIMIT 10
        """)
        recent_entities = [
            {
                "text": row[0],
                "type": row[1],
                "first_seen": row[2],
                "confidence": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get confidence distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN confidence >= 0.9 THEN 'high'
                    WHEN confidence >= 0.7 THEN 'medium'
                    ELSE 'low'
                END as confidence_level,
                COUNT(*)
            FROM entities 
            GROUP BY confidence_level
        """)
        confidence_distribution = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        return EntityStats(
            total_entities=total_entities,
            entities_by_type=entities_by_type,
            most_frequent=most_frequent,
            recent_entities=recent_entities,
            confidence_distribution=confidence_distribution
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch entity statistics: {str(e)}"
        )
