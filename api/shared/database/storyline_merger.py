"""
Storyline merger utilities for the News Intelligence system.

This module provides functions to merge and update existing storylines
instead of creating new ones for the same topic.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .connection import get_db_connection
from .db_availability import is_database_ready

logger = logging.getLogger(__name__)

class StorylineMerger:
    """
    A class to handle merging and updating storylines in the database.
    """
    
    def __init__(self):
        """Initialize the StorylineMerger."""
        self.db_ready = is_database_ready()
    
    def find_existing_storyline(self, topic: str, source: str = None) -> Optional[Dict[str, Any]]:
        """
        Find an existing storyline for a given topic.
        
        Args:
            topic (str): The topic to search for
            source (str, optional): Specific source to filter by
            
        Returns:
            Dict containing existing storyline data or None if not found
        """
        if not self.db_ready:
            logger.warning("Database not ready, cannot find existing storyline")
            return None
            
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Search for existing storyline by topic
                    query = """
                        SELECT id, topic, content, updated_at, source, status
                        FROM storylines 
                        WHERE topic ILIKE %s 
                        AND status != 'archived'
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """
                    cur.execute(query, (f"%{topic}%",))
                    result = cur.fetchone()
                    
                    if result:
                        return {
                            'id': result[0],
                            'topic': result[1],
                            'content': result[2],
                            'updated_at': result[3],
                            'source': result[4],
                            'status': result[5]
                        }
                    return None
        except Exception as e:
            logger.error(f"Error finding existing storyline: {e}")
            return None
    
    def update_existing_storyline(self, storyline_id: int, new_content: str, 
                                new_source: str, update_time: datetime = None) -> bool:
        """
        Update an existing storyline with new content.
        
        Args:
            storyline_id (int): ID of the storyline to update
            new_content (str): New content to add to the storyline
            new_source (str): Source of the new content
            update_time (datetime, optional): Time of update
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if not self.db_ready:
            logger.warning("Database not ready, cannot update storyline")
            return False
            
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Update the storyline content
                    query = """
                        UPDATE storylines 
                        SET content = content || %s,
                            updated_at = %s,
                            source = %s
                        WHERE id = %s
                        RETURNING id
                    """
                    update_time = update_time or datetime.utcnow()
                    cur.execute(query, (new_content, update_time, new_source, storyline_id))
                    result = cur.fetchone()
                    
                    return result is not None
        except Exception as e:
            logger.error(f"Error updating storyline: {e}")
            return False
    
    def create_new_storyline(self, topic: str, content: str, source: str, 
                           created_time: datetime = None) -> Optional[int]:
        """
        Create a new storyline for a topic.
        
        Args:
            topic (str): The topic for the storyline
            content (str): Initial content for the storyline
            source (str): Source of the content
            created_time (datetime, optional): Time of creation
            
        Returns:
            int: ID of the created storyline or None if failed
        """
        if not self.db_ready:
            logger.warning("Database not ready, cannot create new storyline")
            return None
            
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Create new storyline
                    query = """
                        INSERT INTO storylines (topic, content, source, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """
                    created_time = created_time or datetime.utcnow()
                    cur.execute(query, (topic, content, source, created_time, created_time))
                    result = cur.fetchone()
                    
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating new storyline: {e}")
            return None
    
    def merge_storylines(self, topic: str, new_content: str, new_source: str) -> Dict[str, Any]:
        """
        Merge new content into existing storyline or create a new one if none exists.
        
        Args:
            topic (str): The topic to merge/update
            new_content (str): New content to add
            new_source (str): Source of the new content
            
        Returns:
            Dict containing merge result information
        """
        try:
            # Find existing storyline
            existing_storyline = self.find_existing_storyline(topic)
            
            if existing_storyline:
                # Update existing storyline
                success = self.update_existing_storyline(
                    existing_storyline['id'], 
                    f"\\n\\n---\\n\\n{new_content}", 
                    new_source
                )
                
                if success:
                    logger.info(f"Updated existing storyline for topic: {topic}")
                    return {
                        'success': True,
                        'action': 'updated',
                        'storyline_id': existing_storyline['id'],
                        'message': 'Storyline updated with new content'
                    }
                else:
                    logger.error(f"Failed to update storyline for topic: {topic}")
                    return {
                        'success': False,
                        'action': 'failed_update',
                        'message': 'Failed to update storyline'
                    }
            else:
                # Create new storyline
                storyline_id = self.create_new_storyline(topic, new_content, new_source)
                
                if storyline_id:
                    logger.info(f"Created new storyline for topic: {topic}")
                    return {
                        'success': True,
                        'action': 'created',
                        'storyline_id': storyline_id,
                        'message': 'New storyline created'
                    }
                else:
                    logger.error(f"Failed to create storyline for topic: {topic}")
                    return {
                        'success': False,
                        'action': 'failed_create',
                        'message': 'Failed to create storyline'
                    }
        except Exception as e:
            logger.error(f"Error in merge_storylines: {e}")
            return {
                'success': False,
                'action': 'error',
                'message': f'Error merging storylines: {str(e)}'
            }
    
    def get_storyline_status(self, storyline_id: int) -> Optional[Dict[str, Any]]:
        """
        Get status information for a specific storyline.
        
        Args:
            storyline_id (int): ID of the storyline
            
        Returns:
            Dict containing storyline status or None if not found
        """
        if not self.db_ready:
            logger.warning("Database not ready, cannot get storyline status")
            return None
            
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, topic, content, created_at, updated_at, source, status
                        FROM storylines 
                        WHERE id = %s
                    """
                    cur.execute(query, (storyline_id,))
                    result = cur.fetchone()
                    
                    if result:
                        return {
                            'id': result[0],
                            'topic': result[1],
                            'content': result[2],
                            'created_at': result[3],
                            'updated_at': result[4],
                            'source': result[5],
                            'status': result[6]
                        }
                    return None
        except Exception as e:
            logger.error(f"Error getting storyline status: {e}")
            return None

    def get_recent_storylines(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a list of recent storylines.
        
        Args:
            limit (int): Maximum number of storylines to return
            
        Returns:
            List of recent storyline dictionaries
        """
        if not self.db_ready:
            logger.warning("Database not ready, cannot get recent storylines")
            return []
            
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, topic, content, created_at, updated_at, source, status
                        FROM storylines 
                        WHERE status != 'archived'
                        ORDER BY updated_at DESC
                        LIMIT %s
                    """
                    cur.execute(query, (limit,))
                    results = cur.fetchall()
                    
                    return [
                        {
                            'id': row[0],
                            'topic': row[1],
                            'content': row[2],
                            'created_at': row[3],
                            'updated_at': row[4],
                            'source': row[5],
                            'status': row[6]
                        }
                        for row in results
                    ]
        except Exception as e:
            logger.error(f"Error getting recent storylines: {e}")
            return []