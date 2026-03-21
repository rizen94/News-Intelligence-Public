#!/usr/bin/env python3
"""
Content Prioritization Engine
Manages story threads, content priority, and user interest rules
"""

import logging
import psycopg2
from shared.database.connection import get_db_connection
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import re

logger = logging.getLogger(__name__)

class ContentPrioritizationEngine:
    """Engine for managing content priority and story threads"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize content prioritization engine
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # Cache for priority levels and rules
        self.priority_levels = {}
        self.user_rules = {}
        self.collection_rules = []
        
        # Load configuration
        self._load_priority_levels()
        self._load_user_rules()
        self._load_collection_rules()
    
    def _load_priority_levels(self):
        """Load priority levels from database"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, description, priority_score, color_hex, is_active
                FROM content_priority_levels
                WHERE is_active = TRUE
                ORDER BY priority_score DESC
            """)
            
            for row in cursor.fetchall():
                self.priority_levels[row[0]] = {
                    'id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'priority_score': row[3],
                    'color_hex': row[4],
                    'is_active': row[5]
                }
            
            self.logger.info(f"Loaded {len(self.priority_levels)} priority levels")
            
        except Exception as e:
            self.logger.error(f"Error loading priority levels: {e}")
        finally:
            if conn:
                conn.close()
    
    def _load_user_rules(self):
        """Load user interest rules from database"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT uir.id, uir.rule_type, uir.rule_value, uir.priority_level_id,
                       uir.action, uir.weight, uir.is_active, uip.profile_name
                FROM user_interest_rules uir
                JOIN user_interest_profiles uip ON uir.profile_id = uip.id
                WHERE uir.is_active = TRUE AND uip.is_active = TRUE
            """)
            
            for row in cursor.fetchall():
                rule = {
                    'id': row[0],
                    'rule_type': row[1],
                    'rule_value': row[2],
                    'priority_level_id': row[3],
                    'action': row[4],
                    'weight': float(row[5]),
                    'is_active': row[6],
                    'profile_name': row[7]
                }
                
                if rule['profile_name'] not in self.user_rules:
                    self.user_rules[rule['profile_name']] = []
                
                self.user_rules[rule['profile_name']].append(rule)
            
            self.logger.info(f"Loaded user rules for {len(self.user_rules)} profiles")
            
        except Exception as e:
            self.logger.error(f"Error loading user rules: {e}")
        finally:
            if conn:
                conn.close()
    
    def _load_collection_rules(self):
        """Load content collection rules from database"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, rule_name, rule_type, rule_conditions, priority_level_id,
                       action, is_active
                FROM content_collection_rules
                WHERE is_active = TRUE
            """)
            
            for row in cursor.fetchall():
                rule = {
                    'id': row[0],
                    'rule_name': row[1],
                    'rule_type': row[2],
                    'rule_conditions': row[3],
                    'priority_level_id': row[4],
                    'action': row[5],
                    'is_active': row[6]
                }
                
                self.collection_rules.append(rule)
            
            self.logger.info(f"Loaded {len(self.collection_rules)} collection rules")
            
        except Exception as e:
            self.logger.error(f"Error loading collection rules: {e}")
            self.collection_rules = []
        finally:
            if conn:
                conn.close()
    
    def calculate_article_priority(self, article_data: Dict[str, Any], 
                                 profile_name: str = 'default') -> Dict[str, Any]:
        """
        Calculate priority for an article based on content and user rules
        
        Args:
            article_data: Article data including title, content, source, category
            profile_name: User profile name to apply rules from
            
        Returns:
            Dictionary with priority information
        """
        try:
            title = article_data.get('title', '')
            content = article_data.get('content', '')
            source = article_data.get('source', '')
            category = article_data.get('category', '')
            
            # Start with base priority
            base_priority = 50
            priority_score = base_priority
            priority_level_id = None
            reasoning = []
            
            # Apply user interest rules
            if profile_name in self.user_rules:
                for rule in self.user_rules[profile_name]:
                    if self._rule_matches(rule, title, content, source, category):
                        rule_priority = self.priority_levels.get(rule['priority_level_id'], {})
                        rule_score = rule_priority.get('priority_score', 50)
                        
                        if rule['action'] == 'boost':
                            priority_score += (rule_score * rule['weight'])
                            reasoning.append(f"Boosted by {rule['rule_type']}: {rule['rule_value']}")
                        elif rule['action'] == 'suppress':
                            priority_score -= (rule_score * rule['weight'])
                            reasoning.append(f"Suppressed by {rule['rule_type']}: {rule['rule_value']}")
                        elif rule['action'] == 'track':
                            priority_score += (rule_score * rule['weight'] * 0.5)
                            reasoning.append(f"Tracked by {rule['rule_type']}: {rule['rule_value']}")
            
            # Apply collection rules
            for rule in self.collection_rules:
                if self._collection_rule_matches(rule, title, content, source, category):
                    rule_priority = self.priority_levels.get(rule['priority_level_id'], {})
                    rule_score = rule_priority.get('priority_score', 50)
                    
                    if rule['action'] == 'boost':
                        priority_score += (rule_score * 0.3)
                        reasoning.append(f"Collection rule boost: {rule['rule_name']}")
                    elif rule['action'] == 'avoid':
                        priority_score = 0
                        reasoning.append(f"Collection rule avoid: {rule['rule_name']}")
            
            # Ensure priority is within bounds
            priority_score = max(0, min(100, priority_score))
            
            # Find matching priority level
            for level_id, level_data in self.priority_levels.items():
                if priority_score >= level_data['priority_score']:
                    priority_level_id = level_id
                    break
            
            # Check for story thread matches
            thread_matches = self._find_story_thread_matches(title, content, category)
            
            result = {
                'priority_score': priority_score,
                'priority_level_id': priority_level_id,
                'priority_level_name': self.priority_levels.get(priority_level_id, {}).get('name', 'unknown'),
                'reasoning': reasoning,
                'thread_matches': thread_matches,
                'should_collect': priority_score > 0,
                'collection_priority': 'high' if priority_score >= 75 else 'medium' if priority_score >= 50 else 'low'
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating article priority: {e}")
            return {
                'priority_score': 50,
                'priority_level_id': None,
                'priority_level_name': 'medium',
                'reasoning': [f'Error: {str(e)}'],
                'thread_matches': [],
                'should_collect': True,
                'collection_priority': 'medium'
            }
    
    def _rule_matches(self, rule: Dict[str, Any], title: str, content: str, 
                      source: str, category: str) -> bool:
        """Check if a rule matches the article content"""
        try:
            rule_type = rule['rule_type']
            rule_value = rule['rule_value'].lower()
            
            if rule_type == 'keyword':
                return (rule_value in title.lower() or 
                       rule_value in content.lower())
            elif rule_type == 'source':
                return rule_value in source.lower()
            elif rule_type == 'category':
                return rule_value in category.lower()
            elif rule_type == 'topic':
                # More sophisticated topic matching could be implemented here
                return rule_value in title.lower() or rule_value in content.lower()
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking rule match: {e}")
            return False
    
    def _collection_rule_matches(self, rule: Dict[str, Any], title: str, content: str,
                                source: str, category: str) -> bool:
        """Check if a collection rule matches the article content"""
        try:
            rule_type = rule['rule_type']
            conditions = rule['rule_conditions']
            
            if rule_type == 'content_filter':
                keywords = conditions.get('keywords', [])
                for keyword in keywords:
                    if keyword.lower() in title.lower() or keyword.lower() in content.lower():
                        return True
                        
            elif rule_type == 'source_filter':
                sources = conditions.get('sources', [])
                for source_pattern in sources:
                    if source_pattern.lower() in source.lower():
                        return True
                        
            elif rule_type == 'category_filter':
                categories = conditions.get('categories', [])
                for cat in categories:
                    if cat.lower() in category.lower():
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking collection rule match: {e}")
            return False
    
    def _find_story_thread_matches(self, title: str, content: str, category: str) -> List[Dict[str, Any]]:
        """Find matching story threads for an article"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT st.id, st.title, st.description, st.category,
                       stk.keyword, stk.weight, st.priority_level_id
                FROM story_threads st
                JOIN story_thread_keywords stk ON st.id = stk.thread_id
                WHERE st.status = 'active' AND stk.is_active = TRUE
            """)
            
            matches = []
            for row in cursor.fetchall():
                thread_id, thread_title, thread_desc, thread_cat, keyword, weight, priority_id = row
                
                # Check if keyword matches
                if (keyword.lower() in title.lower() or 
                    keyword.lower() in content.lower() or
                    keyword.lower() in category.lower()):
                    
                    matches.append({
                        'thread_id': thread_id,
                        'thread_title': thread_title,
                        'thread_description': thread_desc,
                        'thread_category': thread_cat,
                        'matching_keyword': keyword,
                        'match_weight': float(weight),
                        'priority_level_id': priority_id
                    })
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error finding story thread matches: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def create_story_thread(self, title: str, description: str, category: str,
                           priority_level_name: str = 'medium', 
                           keywords: List[str] = None,
                           user_created: bool = False) -> Dict[str, Any]:
        """
        Create a new story thread
        
        Args:
            title: Thread title
            description: Thread description
            category: Thread category
            priority_level_name: Priority level name
            keywords: List of keywords for automatic detection
            user_created: Whether created by user or system
            
        Returns:
            Dictionary with thread information
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            priority_level_id = None
            for level_id, level_data in self.priority_levels.items():
                if level_data['name'] == priority_level_name:
                    priority_level_id = level_id
                    break
            
            if not priority_level_id:
                priority_level_id = 2
            
            cursor.execute("""
                INSERT INTO story_threads (title, description, category, priority_level_id, user_created)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (title, description, category, priority_level_id, user_created))
            
            thread_id = cursor.fetchone()[0]
            
            if keywords:
                for keyword in keywords:
                    cursor.execute("""
                        INSERT INTO story_thread_keywords (thread_id, keyword, weight)
                        VALUES (%s, %s, %s)
                    """, (thread_id, keyword, 1.0))
            
            conn.commit()
            
            self.logger.info(f"Created story thread: {title} (ID: {thread_id})")
            
            return {
                'id': thread_id,
                'title': title,
                'description': description,
                'category': category,
                'priority_level_id': priority_level_id,
                'keywords': keywords or [],
                'user_created': user_created
            }
            
        except Exception as e:
            self.logger.error(f"Error creating story thread: {e}")
            return {'error': str(e)}
        finally:
            if conn:
                conn.close()
    
    def add_user_interest_rule(self, profile_name: str, rule_type: str, rule_value: str,
                               priority_level_name: str, action: str = 'track',
                               weight: float = 1.0) -> Dict[str, Any]:
        """
        Add a user interest rule
        
        Args:
            profile_name: User profile name
            rule_type: Type of rule (keyword, source, category, topic)
            rule_value: Rule value to match
            priority_level_name: Priority level name
            action: Action to take (track, avoid, boost, suppress)
            weight: Rule weight (0.0 to 1.0)
            
        Returns:
            Dictionary with rule information
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM user_interest_profiles 
                WHERE profile_name = %s AND is_active = TRUE
            """, (profile_name,))
            
            profile_result = cursor.fetchone()
            if profile_result:
                profile_id = profile_result[0]
            else:
                cursor.execute("""
                    INSERT INTO user_interest_profiles (user_id, profile_name)
                    VALUES (%s, %s)
                    RETURNING id
                """, ('default', profile_name))
                profile_id = cursor.fetchone()[0]
            
            priority_level_id = None
            for level_id, level_data in self.priority_levels.items():
                if level_data['name'] == priority_level_name:
                    priority_level_id = level_id
                    break
            
            if not priority_level_id:
                priority_level_id = 2
            
            cursor.execute("""
                INSERT INTO user_interest_rules 
                (profile_id, rule_type, rule_value, priority_level_id, action, weight)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (profile_id, rule_type, rule_value, priority_level_id, action, weight))
            
            rule_id = cursor.fetchone()[0]
            
            conn.commit()
            
            self._load_user_rules()
            
            self.logger.info(f"Added user interest rule: {rule_type}={rule_value} -> {action}")
            
            return {
                'id': rule_id,
                'profile_id': profile_id,
                'rule_type': rule_type,
                'rule_value': rule_value,
                'priority_level_id': priority_level_id,
                'action': action,
                'weight': weight
            }
            
        except Exception as e:
            self.logger.error(f"Error adding user interest rule: {e}")
            return {'error': str(e)}
        finally:
            if conn:
                conn.close()
    
    def get_story_threads(self, status: str = 'active', 
                          priority_level_name: str = None) -> List[Dict[str, Any]]:
        """
        Get story threads with optional filtering
        
        Args:
            status: Thread status filter
            priority_level_name: Priority level filter
            
        Returns:
            List of story threads
        """
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT st.id, st.title, st.description, st.category, st.status,
                       st.user_created, st.auto_generated, st.created_at, st.last_activity,
                       cpl.name as priority_level, cpl.color_hex,
                       COUNT(stk.id) as keyword_count
                FROM story_threads st
                JOIN content_priority_levels cpl ON st.priority_level_id = cpl.id
                LEFT JOIN story_thread_keywords stk ON st.id = stk.thread_id AND stk.is_active = TRUE
                WHERE st.status = %s
            """
            
            params = [status]
            
            if priority_level_name:
                query += " AND cpl.name = %s"
                params.append(priority_level_name)
            
            query += " GROUP BY st.id, st.title, st.description, st.category, st.status, st.user_created, st.auto_generated, st.created_at, st.last_activity, cpl.name, cpl.color_hex ORDER BY st.last_activity DESC"
            
            cursor.execute(query, params)
            
            threads = []
            for row in cursor.fetchall():
                threads.append({
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'category': row[3],
                    'status': row[4],
                    'user_created': row[5],
                    'auto_generated': row[6],
                    'created_at': row[7].isoformat() if row[7] else None,
                    'last_activity': row[8].isoformat() if row[8] else None,
                    'priority_level': row[9],
                    'color_hex': row[10],
                    'keyword_count': row[11]
                })
            
            return threads
            
        except Exception as e:
            self.logger.error(f"Error getting story threads: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_priority_statistics(self) -> Dict[str, Any]:
        """Get statistics about content priority distribution"""
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get priority level counts
            cursor.execute("""
                SELECT cpl.name, cpl.color_hex, COUNT(cpa.id) as article_count
                FROM content_priority_levels cpl
                LEFT JOIN content_priority_assignments cpa ON cpl.id = cpa.priority_level_id
                WHERE cpl.is_active = TRUE
                GROUP BY cpl.id, cpl.name, cpl.color_hex
                ORDER BY cpl.priority_score DESC
            """)
            
            priority_stats = []
            for row in cursor.fetchall():
                priority_stats.append({
                    'name': row[0],
                    'color_hex': row[1],
                    'article_count': row[2]
                })
            
            # Get story thread counts
            cursor.execute("""
                SELECT status, COUNT(*) as thread_count
                FROM story_threads
                GROUP BY status
            """)
            
            thread_stats = dict(cursor.fetchall())
            
            # Get recent activity
            cursor.execute("""
                SELECT COUNT(*) as recent_articles
                FROM content_priority_assignments
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            
            recent_articles = cursor.fetchone()[0]
            
            return {
                'priority_levels': priority_stats,
                'story_threads': thread_stats,
                'recent_articles': recent_articles,
                'total_priority_levels': len(priority_stats),
                'total_story_threads': sum(thread_stats.values())
            }
            
        except Exception as e:
            self.logger.error(f"Error getting priority statistics: {e}")
            return {'error': str(e)}
        finally:
            if conn:
                conn.close()
