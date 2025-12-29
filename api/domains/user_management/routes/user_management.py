"""
Domain 5: User Management Routes
Handles user profiles, preferences, and authentication
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import hashlib
import secrets

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v4/user_management",
    tags=["User Management"],
    responses={404: {"description": "Not found"}}
)

@router.get("/health")
async def health_check():
    """Health check for User Management domain"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "domain": "user_management",
                "status": "unhealthy",
                "error": "Database connection failed"
            }
        
        conn.close()
        
        return {
            "success": True,
            "domain": "user_management",
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "domain": "user_management",
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/users")
async def get_users(limit: int = 20, active_only: bool = True):
    """Get all users"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            where_clause = "WHERE is_active = true" if active_only else ""
            
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, username, email, full_name, created_at, updated_at, last_login
                    FROM user_profiles 
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                
                users = []
                for row in cur.fetchall():
                    users.append({
                        "id": row[0],
                        "username": row[1],
                        "email": row[2],
                        "full_name": row[3],
                        "created_at": row[4].isoformat() if row[4] else None,
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "last_login": row[6].isoformat() if row[6] else None
                    })
                
                return {
                    "success": True,
                    "data": {"users": users},
                    "count": len(users),
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}")
async def get_user(user_id: int):
    """Get a specific user"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, username, email, full_name, created_at, updated_at, last_login
                    FROM user_profiles 
                    WHERE id = %s
                """, (user_id,))
                
                user = cur.fetchone()
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                return {
                    "success": True,
                    "data": {
                        "id": user[0],
                        "username": user[1],
                        "email": user[2],
                        "full_name": user[3],
                        "created_at": user[4].isoformat() if user[4] else None,
                        "updated_at": user[5].isoformat() if user[5] else None,
                        "last_login": user[6].isoformat() if user[6] else None
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
async def create_user(request: Dict[str, Any]):
    """Create a new user"""
    try:
        username = request.get("username")
        email = request.get("email")
        password = request.get("password")
        full_name = request.get("full_name")
        
        if not username or not email or not password:
            raise HTTPException(status_code=400, detail="Username, email, and password are required")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if username or email already exists
                cur.execute("""
                    SELECT COUNT(*) FROM user_profiles 
                    WHERE username = %s OR email = %s
                """, (username, email))
                
                if cur.fetchone()[0] > 0:
                    raise HTTPException(status_code=409, detail="Username or email already exists")
                
                # Hash password
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                
                # Create user
                cur.execute("""
                    INSERT INTO user_profiles (username, email, password_hash, full_name, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, username, email, full_name, created_at
                """, (username, email, password_hash, full_name, datetime.now(), datetime.now()))
                
                new_user = cur.fetchone()
                conn.commit()
                
                return {
                    "success": True,
                    "data": {
                        "id": new_user[0],
                        "username": new_user[1],
                        "email": new_user[2],
                        "full_name": new_user[3],
                        "created_at": new_user[4].isoformat()
                    },
                    "message": "User created successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/{user_id}")
async def update_user(user_id: int, request: Dict[str, Any]):
    """Update a user"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM user_profiles WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")
                
                # Build update query
                update_fields = []
                params = []
                
                if "username" in request:
                    update_fields.append("username = %s")
                    params.append(request["username"])
                
                if "email" in request:
                    update_fields.append("email = %s")
                    params.append(request["email"])
                
                if "full_name" in request:
                    update_fields.append("full_name = %s")
                    params.append(request["full_name"])
                
                if "password" in request:
                    password_hash = hashlib.sha256(request["password"].encode()).hexdigest()
                    update_fields.append("password_hash = %s")
                    params.append(password_hash)
                
                if not update_fields:
                    raise HTTPException(status_code=400, detail="No fields to update")
                
                update_fields.append("updated_at = %s")
                params.append(datetime.now())
                params.append(user_id)
                
                cur.execute(f"""
                    UPDATE user_profiles 
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                """, params)
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "User updated successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}/preferences")
async def get_user_preferences(user_id: int):
    """Get user preferences"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT preference_type, preference_value, created_at, updated_at
                    FROM user_preferences 
                    WHERE user_id = %s
                    ORDER BY preference_type
                """, (user_id,))
                
                preferences = {}
                for row in cur.fetchall():
                    preferences[row[0]] = {
                        "value": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "updated_at": row[3].isoformat() if row[3] else None
                    }
                
                return {
                    "success": True,
                    "data": {"preferences": preferences},
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}/preferences")
async def set_user_preferences(user_id: int, request: Dict[str, Any]):
    """Set user preferences"""
    try:
        preferences = request.get("preferences", {})
        
        if not preferences:
            raise HTTPException(status_code=400, detail="No preferences provided")
        
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Check if user exists
                cur.execute("SELECT id FROM user_profiles WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")
                
                # Insert or update preferences
                for pref_type, pref_value in preferences.items():
                    cur.execute("""
                        INSERT INTO user_preferences (user_id, preference_type, preference_value, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, preference_type)
                        DO UPDATE SET 
                            preference_value = EXCLUDED.preference_value,
                            updated_at = EXCLUDED.updated_at
                    """, (user_id, pref_type, pref_value, datetime.now(), datetime.now()))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Preferences updated successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error setting preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}/login")
async def user_login(user_id: int, request: Dict[str, Any]):
    """Update user last login time"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Update last login time
                cur.execute("""
                    UPDATE user_profiles 
                    SET last_login = %s, updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), datetime.now(), user_id))
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "Login recorded successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error recording login: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    """Delete a user (soft delete)"""
    try:
        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        try:
            with conn.cursor() as cur:
                # Soft delete by setting is_active to false
                cur.execute("""
                    UPDATE user_profiles 
                    SET is_active = false, updated_at = %s
                    WHERE id = %s
                """, (datetime.now(), user_id))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found")
                
                conn.commit()
                
                return {
                    "success": True,
                    "message": "User deleted successfully",
                    "timestamp": datetime.now().isoformat()
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
