"""
News Intelligence System v3.1.0 - Digest Automation Service
Automated daily digest generation and management
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
logger = logging.getLogger(__name__)

class DigestAutomationService:
    """Automated digest generation and management service"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.last_digest_time = None
        self.digest_interval = 3600  # Generate digest every hour
        self.is_running = False
        
    async def start_automation(self):
        """Start the automated digest generation process"""
        self.is_running = True
        logger.info("Starting digest automation service...")
        
        # Generate initial digest
        await self.generate_digest_if_needed()
        
        # Start background task
        asyncio.create_task(self._background_loop())
        
    async def _background_loop(self):
        """Background loop for automated digest generation"""
        while self.is_running:
            try:
                await self.generate_digest_if_needed()
                await asyncio.sleep(self.digest_interval)
            except Exception as e:
                logger.error(f"Error in digest automation loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                
    async def generate_digest_if_needed(self):
        """Generate digest if enough time has passed or no recent digest exists"""
        try:
            # Check if we need to generate a new digest
            if await self._should_generate_digest():
                logger.info("Generating automated digest...")
                await self._generate_digest()
                self.last_digest_time = datetime.now()
                logger.info("Automated digest generated successfully")
            else:
                logger.debug("No need to generate digest at this time")
                
        except Exception as e:
            logger.error(f"Error generating automated digest: {e}")
            
    async def _should_generate_digest(self) -> bool:
        """Check if a new digest should be generated"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            # Check for recent digest
            cursor.execute("""
                SELECT created_at FROM story_consolidations 
                WHERE headline LIKE 'Daily News Digest%'
                ORDER BY created_at DESC LIMIT 1
            """)
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return True  # No digest exists
                
            last_digest = result[0]
            time_since_digest = datetime.now() - last_digest
            
            # Generate new digest if:
            # - More than 1 hour has passed, OR
            # - More than 10 new articles since last digest
            if time_since_digest.total_seconds() > 3600:  # 1 hour
                return True
                
            # Check for new articles
            new_articles_count = await self._count_new_articles_since(last_digest)
            return new_articles_count >= 10
            
        except Exception as e:
            logger.error(f"Error checking if digest should be generated: {e}")
            return False
            
    async def _count_new_articles_since(self, since_time: datetime) -> int:
        """Count new articles since the given time"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE published_at > %s
            """, (since_time,))
            
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return count
            
        except Exception as e:
            logger.error(f"Error counting new articles: {e}")
            return 0
            
    async def _generate_digest(self):
        """Generate a new automated digest"""
        try:
            # Get recent articles (last 24 hours)
            recent_articles = await self._get_recent_articles()
            
            # Get active storylines
            active_storylines = await self._get_active_storylines()
            
            # Create digest content
            digest_title = f"Daily News Digest - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            digest_content = await self._create_digest_content(recent_articles, active_storylines)
            
            # Save to database
            await self._save_digest(digest_title, digest_content, recent_articles)
            
        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            raise
            
    async def _get_recent_articles(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent articles from the last N hours"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT id, title, summary, content, source, published_at, 
                       sentiment_score, quality_score, topics_extracted, entities_extracted
                FROM articles 
                WHERE published_at > %s
                ORDER BY published_at DESC
                LIMIT 50
            """, (cutoff_time,))
            
            articles = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(article) for article in articles]
            
        except Exception as e:
            logger.error(f"Error getting recent articles: {e}")
            return []
            
    async def _get_active_storylines(self) -> List[Dict[str, Any]]:
        """Get active storylines with recent updates"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT id, story_id, title, summary, status, sentiment, impact_level, created_at
                FROM story_timelines 
                WHERE status IN ('developing', 'breaking', 'monitoring')
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            storylines = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(storyline) for storyline in storylines]
            
        except Exception as e:
            logger.error(f"Error getting active storylines: {e}")
            return []
            
    async def _create_digest_content(self, articles: List[Dict], storylines: List[Dict]) -> Dict[str, Any]:
        """Create digest content structure"""
        return {
            "generated_at": datetime.now().isoformat(),
            "articles_count": len(articles),
            "storylines_count": len(storylines),
            "summary": {
                "total_articles": len(articles),
                "breaking_news": len([a for a in articles if a.get('quality_score', 0) > 0.8]),
                "active_storylines": len(storylines),
                "sources": list(set(a.get('source', '') for a in articles)),
                "top_topics": self._extract_top_topics(articles)
            },
            "articles": articles[:10],  # Top 10 articles
            "storylines": storylines[:5],  # Top 5 storylines
            "metadata": {
                "generation_method": "automated",
                "interval_hours": 1,
                "next_generation": (datetime.now() + timedelta(hours=1)).isoformat()
            }
        }
        
    def _extract_top_topics(self, articles: List[Dict]) -> List[str]:
        """Extract top topics from articles"""
        topic_counts = {}
        for article in articles:
            topics = article.get('topics_extracted', [])
            if isinstance(topics, str):
                try:
                    topics = json.loads(topics)
                except:
                    topics = []
            
            for topic in topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
                
        # Return top 5 topics
        return sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
    async def _save_digest(self, title: str, content: Dict, articles: List[Dict]):
        """Save digest to database"""
        try:
            conn = await self._get_db_connection()
            cursor = conn.cursor()
            
            # Insert digest record
            cursor.execute("""
                INSERT INTO story_consolidations 
                (headline, consolidated_summary, ai_analysis, sources, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                title,
                content.get('summary', {}).get('summary', 'Automated daily news digest'),
                json.dumps(content),
                json.dumps(content.get('summary', {}).get('sources', [])),
                datetime.now(),
                datetime.now()
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving digest: {e}")
            raise
            
    async def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
        
    async def stop_automation(self):
        """Stop the automated digest generation"""
        self.is_running = False
        logger.info("Digest automation service stopped")

# Global instance
digest_service = None

def get_digest_service() -> DigestAutomationService:
    """Get the global digest service instance"""
    global digest_service
    if digest_service is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        digest_service = DigestAutomationService(db_config)
    return digest_service
