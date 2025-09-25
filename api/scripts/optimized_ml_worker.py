#!/usr/bin/env python3
"""
Optimized ML Processing Worker
Processes articles in parallel with multiple threads for maximum efficiency
"""

import os
import sys
import time
import logging
import psycopg2
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class OptimizedMLWorker:
    def __init__(self, worker_id=1, max_workers=4, batch_size=20):
        self.worker_id = worker_id
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.db_config = {
            'host': 'postgres',
            'database': 'news_intelligence',
            'user': 'newsapp',
            'password': 'Database@NEWSINT2025'
        }
        self.is_running = False
        self.processed_count = 0
        self.failed_count = 0
        
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def process_article_batch(self, articles):
        """Process a batch of articles in parallel"""
        logger.info(f"Worker {self.worker_id}: Processing batch of {len(articles)} articles")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all articles for processing
            future_to_article = {
                executor.submit(self.process_single_article, article): article 
                for article in articles
            }
            
            # Process completed articles
            for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    success = future.result()
                    if success:
                        self.processed_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e:
                    logger.error(f"Worker {self.worker_id}: Error processing article {article['id']}: {e}")
                    self.failed_count += 1
    
    def process_single_article(self, article):
        """Process a single article with enhanced ML operations"""
        article_id = article['id']
        title = article['title']
        content = article['content']
        source = article['source']
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Enhanced quality scoring
            quality_score = self.calculate_enhanced_quality_score(title, content, source)
            
            # Enhanced entity extraction
            entities = self.extract_enhanced_entities(title, content)
            
            # Enhanced topic extraction
            topics = self.extract_enhanced_topics(title, content)
            
            # Calculate readability score
            readability_score = self.calculate_readability_score(content)
            
            # Calculate engagement score
            engagement_score = self.calculate_engagement_score(title, content, source)
            
            # Extract key points
            key_points = self.extract_key_points(content)
            
            # Update article with enhanced processing results
            cursor.execute("""
                UPDATE articles 
                SET processing_status = 'processed',
                    quality_score = %s,
                    entities_extracted = %s,
                    topics_extracted = %s,
                    readability_score = %s,
                    engagement_score = %s,
                    key_points = %s,
                    processing_completed_at = %s,
                    updated_at = %s
                WHERE id = %s
            """, (
                quality_score,
                entities,
                topics,
                readability_score,
                engagement_score,
                key_points,
                datetime.utcnow(),
                datetime.utcnow(),
                article_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Worker {self.worker_id}: Processed article {article_id} (quality: {quality_score:.2f})")
            return True
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error processing article {article_id}: {str(e)}")
            return False
    
    def calculate_enhanced_quality_score(self, title, content, source):
        """Calculate enhanced quality score"""
        score = 0.3  # Base score
        
        # Content length scoring
        if content:
            if len(content) > 200:
                score += 0.2
            if len(content) > 500:
                score += 0.2
            if len(content) > 1000:
                score += 0.1
        
        # Title quality
        if title and len(title) > 20:
            score += 0.1
        
        # Source reputation
        source_scores = {
            'BBC News': 0.2,
            'Reuters': 0.2,
            'NPR News': 0.15,
            'TechCrunch': 0.1,
            'The Verge': 0.1
        }
        score += source_scores.get(source, 0.05)
        
        # Content quality indicators
        if content:
            quality_indicators = ['analysis', 'report', 'investigation', 'study', 'research']
            if any(indicator in content.lower() for indicator in quality_indicators):
                score += 0.1
        
        return min(score, 1.0)
    
    def extract_enhanced_entities(self, title, content):
        """Extract enhanced entities from title and content"""
        entities = []
        text = f"{title} {content or ''}".lower()
        
        # Technology entities
        tech_entities = ['ai', 'artificial intelligence', 'machine learning', 'technology', 'software', 'hardware', 'data', 'algorithm']
        for entity in tech_entities:
            if entity in text:
                entities.append(entity)
        
        # Business entities
        business_entities = ['business', 'economy', 'market', 'finance', 'investment', 'company', 'startup']
        for entity in business_entities:
            if entity in text:
                entities.append(entity)
        
        # News entities
        news_entities = ['government', 'politics', 'policy', 'election', 'law', 'regulation']
        for entity in news_entities:
            if entity in text:
                entities.append(entity)
        
        return list(set(entities))  # Remove duplicates
    
    def extract_enhanced_topics(self, title, content):
        """Extract enhanced topics from title and content"""
        topics = []
        text = f"{title} {content or ''}".lower()
        
        # Topic categories
        topic_categories = {
            'Technology': ['tech', 'ai', 'software', 'hardware', 'digital', 'internet', 'computer'],
            'Business': ['business', 'economy', 'market', 'finance', 'money', 'investment'],
            'Politics': ['government', 'politics', 'policy', 'election', 'law', 'regulation'],
            'Science': ['science', 'research', 'study', 'discovery', 'medical', 'health'],
            'Entertainment': ['entertainment', 'movie', 'music', 'sports', 'celebrity', 'culture']
        }
        
        for category, keywords in topic_categories.items():
            if any(keyword in text for keyword in keywords):
                topics.append(category)
        
        return topics
    
    def calculate_readability_score(self, content):
        """Calculate readability score based on content complexity"""
        if not content:
            return 0.0
        
        # Simple readability calculation
        words = content.split()
        sentences = content.split('.')
        
        if len(sentences) == 0 or len(words) == 0:
            return 0.0
        
        avg_words_per_sentence = len(words) / len(sentences)
        
        # Score based on sentence length (shorter = more readable)
        if avg_words_per_sentence < 15:
            return 0.9
        elif avg_words_per_sentence < 20:
            return 0.7
        elif avg_words_per_sentence < 25:
            return 0.5
        else:
            return 0.3
    
    def calculate_engagement_score(self, title, content, source):
        """Calculate engagement score based on content appeal"""
        score = 0.5  # Base score
        
        # Title engagement
        if title:
            engaging_words = ['breaking', 'exclusive', 'shocking', 'amazing', 'incredible', 'new', 'first']
            if any(word in title.lower() for word in engaging_words):
                score += 0.2
        
        # Content length (longer articles often more engaging)
        if content and len(content) > 500:
            score += 0.2
        
        # Source engagement
        engaging_sources = ['BBC News', 'TechCrunch', 'The Verge']
        if source in engaging_sources:
            score += 0.1
        
        return min(score, 1.0)
    
    def extract_key_points(self, content):
        """Extract key points from content"""
        if not content:
            return []
        
        # Simple key point extraction (first few sentences)
        sentences = content.split('.')[:3]
        key_points = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        return key_points
    
    def get_pending_articles(self):
        """Get pending articles for processing"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, source, created_at
                FROM articles 
                WHERE processing_status = 'processing'
                ORDER BY created_at ASC
                LIMIT %s
            """, (self.batch_size,))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'source': row[3],
                    'created_at': row[4]
                })
            
            conn.close()
            return articles
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error getting pending articles: {str(e)}")
            return []
    
    def run_worker_loop(self):
        """Run the optimized worker in a continuous loop"""
        logger.info(f"Starting optimized ML worker {self.worker_id} with {self.max_workers} threads")
        self.is_running = True
        
        while self.is_running:
            try:
                articles = self.get_pending_articles()
                
                if articles:
                    logger.info(f"Worker {self.worker_id}: Found {len(articles)} articles to process")
                    self.process_article_batch(articles)
                    logger.info(f"Worker {self.worker_id}: Batch completed. Processed: {self.processed_count}, Failed: {self.failed_count}")
                else:
                    logger.info(f"Worker {self.worker_id}: No articles to process, waiting...")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                logger.info(f"Worker {self.worker_id} stopped by user")
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error in worker loop: {str(e)}")
                time.sleep(5)
        
        logger.info(f"Worker {self.worker_id} stopped. Total processed: {self.processed_count}, Failed: {self.failed_count}")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimized ML Worker')
    parser.add_argument('--worker-id', type=int, default=1, help='Worker ID')
    parser.add_argument('--max-workers', type=int, default=4, help='Max parallel threads')
    parser.add_argument('--batch-size', type=int, default=20, help='Batch size')
    
    args = parser.parse_args()
    
    worker = OptimizedMLWorker(
        worker_id=args.worker_id,
        max_workers=args.max_workers,
        batch_size=args.batch_size
    )
    
    try:
        worker.run_worker_loop()
    except KeyboardInterrupt:
        logger.info("Worker stopped")
    except Exception as e:
        logger.error(f"Worker failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
