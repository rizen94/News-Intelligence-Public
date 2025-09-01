#!/usr/bin/env python3
"""
News Intelligence System v2.5.0 - ML Data Preparer
Prepares processed articles into ML-ready datasets for summarization
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLDataPreparer:
    """Prepares ML-ready datasets from processed articles"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.connection = None
        
    def connect_db(self) -> bool:
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config.get('host', 'postgres'),
                database=self.db_config.get('database', 'news_system'),
                user=self.db_config.get('user', 'newsapp'),
                password=self.db_config.get('password', ''),
                connect_timeout=10,
                options='-c statement_timeout=30000'
            )
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def create_ml_dataset(self, dataset_name: str, filters: Dict[str, Any] = None) -> Dict:
        """Create a new ML dataset with specified filters"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return {}
            
            # Build query based on filters
            query, params = self._build_dataset_query(filters)
            
            # Execute query to get articles
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                articles = cursor.fetchall()
            
            if not articles:
                logger.warning(f"No articles found for dataset '{dataset_name}' with given filters")
                return {}
            
            # Process articles into ML format
            ml_dataset = self._process_articles_for_ml(articles)
            
            # Store dataset metadata
            dataset_id = self._store_dataset_metadata(dataset_name, filters, len(articles))
            
            # Store dataset content
            self._store_dataset_content(dataset_id, ml_dataset)
            
            logger.info(f"Created ML dataset '{dataset_name}' with {len(articles)} articles")
            
            return {
                'dataset_id': dataset_id,
                'dataset_name': dataset_name,
                'article_count': len(articles),
                'created_at': datetime.now().isoformat(),
                'filters': filters,
                'ml_format': 'ready'
            }
            
        except Exception as e:
            logger.error(f"Error creating ML dataset: {e}")
            return {}
    
    def get_dataset_for_summarization(self, dataset_id: int, max_length: int = 4000) -> List[Dict]:
        """Get dataset formatted for ML summarization"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return []
            
            # Get dataset content
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT content FROM ml_datasets WHERE dataset_id = %s
                """, (dataset_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"Dataset {dataset_id} not found")
                    return []
                
                dataset_content = json.loads(result['content'])
            
            # Format for summarization
            summarization_data = []
            
            for article in dataset_content:
                # Prepare text for summarization
                text = self._prepare_text_for_summarization(article, max_length)
                
                if text:
                    summarization_data.append({
                        'article_id': article['article_id'],
                        'title': article.get('title', ''),
                        'text': text,
                        'metadata': {
                            'source': article.get('domain', ''),
                            'date': article.get('published_date', ''),
                            'word_count': article.get('word_count', 0),
                            'quality_score': article.get('quality_score', 0)
                        }
                    })
            
            logger.info(f"Prepared {len(summarization_data)} articles for summarization")
            return summarization_data
            
        except Exception as e:
            logger.error(f"Error preparing dataset for summarization: {e}")
            return []
    
    def export_dataset_to_csv(self, dataset_id: int, output_path: str) -> bool:
        """Export dataset to CSV format"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return False
            
            # Get dataset content
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT content FROM ml_datasets WHERE dataset_id = %s
                """, (dataset_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"Dataset {dataset_id} not found")
                    return False
                
                dataset_content = json.loads(result['content'])
            
            # Write to CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['article_id', 'title', 'content', 'domain', 'published_date', 
                             'word_count', 'quality_score', 'key_phrases']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for article in dataset_content:
                    writer.writerow({
                        'article_id': article.get('article_id', ''),
                        'title': article.get('title', ''),
                        'content': article.get('cleaned_content', ''),
                        'domain': article.get('domain', ''),
                        'published_date': article.get('published_date', ''),
                        'word_count': article.get('word_count', 0),
                        'quality_score': article.get('quality_score', 0),
                        'key_phrases': ', '.join(article.get('key_phrases', []))
                    })
            
            logger.info(f"Exported dataset {dataset_id} to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting dataset to CSV: {e}")
            return False
    
    def get_dataset_statistics(self, dataset_id: int) -> Dict:
        """Get comprehensive statistics for a dataset"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return {}
            
            # Get dataset content
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT content FROM ml_datasets WHERE dataset_id = %s
                """, (dataset_id,))
                
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"Dataset {dataset_id} not found")
                    return {}
                
                dataset_content = json.loads(result['content'])
            
            if not dataset_content:
                return {}
            
            # Calculate statistics
            total_words = sum(article.get('word_count', 0) for article in dataset_content)
            total_chars = sum(article.get('char_count', 0) for article in dataset_content)
            avg_quality = sum(article.get('quality_score', 0) for article in dataset_content) / len(dataset_content)
            
            # Get date range
            dates = [article.get('published_date') for article in dataset_content if article.get('published_date')]
            date_range = {
                'earliest': min(dates) if dates else None,
                'latest': max(dates) if dates else None
            }
            
            # Get domain distribution
            domains = {}
            for article in dataset_content:
                domain = article.get('domain', '')
                if domain:
                    domains[domain] = domains.get(domain, 0) + 1
            
            # Get quality distribution
            quality_distribution = {
                'excellent': len([a for a in dataset_content if a.get('quality_score', 0) >= 80]),
                'good': len([a for a in dataset_content if 60 <= a.get('quality_score', 0) < 80]),
                'fair': len([a for a in dataset_content if 40 <= a.get('quality_score', 0) < 60]),
                'poor': len([a for a in dataset_content if a.get('quality_score', 0) < 40])
            }
            
            # Get content length distribution
            length_distribution = {
                'short': len([a for a in dataset_content if a.get('word_count', 0) < 200]),
                'medium': len([a for a in dataset_content if 200 <= a.get('word_count', 0) < 500]),
                'long': len([a for a in dataset_content if a.get('word_count', 0) >= 500])
            }
            
            statistics = {
                'dataset_id': dataset_id,
                'article_count': len(dataset_content),
                'total_words': total_words,
                'total_characters': total_chars,
                'average_quality': round(avg_quality, 2),
                'date_range': date_range,
                'domain_distribution': domains,
                'quality_distribution': quality_distribution,
                'length_distribution': length_distribution,
                'average_words_per_article': round(total_words / len(dataset_content), 2),
                'average_chars_per_article': round(total_chars / len(dataset_content), 2)
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error getting dataset statistics: {e}")
            return {}
    
    def _build_dataset_query(self, filters: Dict[str, Any]) -> Tuple[str, List]:
        """Build SQL query based on filters"""
        try:
            base_query = """
                SELECT a.*, 
                       COALESCE(a.ml_data->>'quality_score', '0')::float as quality_score,
                       COALESCE(a.ml_data->>'word_count', '0')::int as word_count,
                       COALESCE(a.ml_data->>'char_count', '0')::int as char_count
                FROM articles a
                WHERE a.processing_status = 'ml_processed'
            """
            
            params = []
            conditions = []
            
            if filters:
                # Quality score filter
                if 'min_quality' in filters:
                    conditions.append("COALESCE(a.ml_data->>'quality_score', '0')::float >= %s")
                    params.append(filters['min_quality'])
                
                # Word count filter
                if 'min_words' in filters:
                    conditions.append("COALESCE(a.ml_data->>'word_count', '0')::int >= %s")
                    params.append(filters['min_words'])
                
                # Date range filter
                if 'start_date' in filters:
                    conditions.append("a.published_date >= %s")
                    params.append(filters['start_date'])
                
                if 'end_date' in filters:
                    conditions.append("a.published_date <= %s")
                    params.append(filters['end_date'])
                
                # Domain filter
                if 'domains' in filters and filters['domains']:
                    domain_conditions = []
                    for domain in filters['domains']:
                        domain_conditions.append("a.url LIKE %s")
                        params.append(f"%{domain}%")
                    
                    if domain_conditions:
                        conditions.append(f"({' OR '.join(domain_conditions)})")
                
                # Source filter
                if 'sources' in filters and filters['sources']:
                    source_conditions = []
                    for source in filters['sources']:
                        source_conditions.append("a.url LIKE %s")
                        params.append(f"%{source}%")
                    
                    if source_conditions:
                        conditions.append(f"({' OR '.join(source_conditions)})")
            
            # Add conditions to query
            if conditions:
                base_query += " AND " + " AND ".join(conditions)
            
            # Add ordering
            base_query += " ORDER BY a.published_date DESC"
            
            return base_query, params
            
        except Exception as e:
            logger.error(f"Error building dataset query: {e}")
            return "SELECT * FROM articles WHERE 1=0", []
    
    def _process_articles_for_ml(self, articles: List[Dict]) -> List[Dict]:
        """Process articles into ML-ready format"""
        try:
            ml_articles = []
            
            for article in articles:
                # Extract ML data
                ml_data = article.get('ml_data', {})
                if isinstance(ml_data, str):
                    try:
                        ml_data = json.loads(ml_data)
                    except:
                        ml_data = {}
                
                # Prepare ML article
                ml_article = {
                    'article_id': article.get('id'),
                    'title': article.get('title', ''),
                    'url': article.get('url', ''),
                    'domain': self._extract_domain(article.get('url', '')),
                    'published_date': article.get('published_date'),
                    'cleaned_content': ml_data.get('cleaned_content', article.get('content', '')),
                    'segments': ml_data.get('segments', []),
                    'key_phrases': ml_data.get('key_phrases', []),
                    'word_count': ml_data.get('word_count', len(article.get('content', '').split())),
                    'char_count': ml_data.get('char_count', len(article.get('content', ''))),
                    'quality_score': ml_data.get('quality_score', 0.0),
                    'reading_time': ml_data.get('reading_time', 1),
                    'content_hash': ml_data.get('content_hash', ''),
                    'processing_timestamp': ml_data.get('processing_timestamp', '')
                }
                
                ml_articles.append(ml_article)
            
            return ml_articles
            
        except Exception as e:
            logger.error(f"Error processing articles for ML: {e}")
            return []
    
    def _prepare_text_for_summarization(self, article: Dict, max_length: int) -> str:
        """Prepare text for ML summarization"""
        try:
            # Get the main content
            content = article.get('cleaned_content', '')
            if not content:
                return ""
            
            # If content is too long, truncate intelligently
            if len(content) > max_length:
                # Try to truncate at sentence boundary
                sentences = content.split('. ')
                truncated_content = ""
                
                for sentence in sentences:
                    if len(truncated_content + sentence + '. ') <= max_length:
                        truncated_content += sentence + '. '
                    else:
                        break
                
                if truncated_content:
                    content = truncated_content.rstrip()
                else:
                    # Fallback to simple truncation
                    content = content[:max_length].rsplit(' ', 1)[0] + '...'
            
            return content
            
        except Exception as e:
            logger.error(f"Error preparing text for summarization: {e}")
            return article.get('cleaned_content', '')
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            if not url:
                return ""
            
            if '://' in url:
                domain = url.split('://')[1]
            else:
                domain = url
            
            if '/' in domain:
                domain = domain.split('/')[0]
            
            return domain.lower()
        except Exception:
            return ""
    
    def _store_dataset_metadata(self, dataset_name: str, filters: Dict, article_count: int) -> int:
        """Store dataset metadata and return dataset ID"""
        try:
            with self.connection.cursor() as cursor:
                # Create datasets table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ml_datasets (
                        dataset_id SERIAL PRIMARY KEY,
                        dataset_name VARCHAR(255) NOT NULL,
                        filters JSONB,
                        article_count INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Insert dataset metadata
                cursor.execute("""
                    INSERT INTO ml_datasets (dataset_name, filters, article_count)
                    VALUES (%s, %s, %s)
                    RETURNING dataset_id
                """, (dataset_name, json.dumps(filters), article_count))
                
                dataset_id = cursor.fetchone()[0]
                self.connection.commit()
                
                return dataset_id
                
        except Exception as e:
            logger.error(f"Error storing dataset metadata: {e}")
            if self.connection:
                self.connection.rollback()
            return 0
    
    def _store_dataset_content(self, dataset_id: int, content: List[Dict]):
        """Store dataset content"""
        try:
            with self.connection.cursor() as cursor:
                # Create dataset content table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ml_dataset_content (
                        content_id SERIAL PRIMARY KEY,
                        dataset_id INTEGER REFERENCES ml_datasets(dataset_id),
                        content JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Insert content
                cursor.execute("""
                    INSERT INTO ml_dataset_content (dataset_id, content)
                    VALUES (%s, %s)
                """, (dataset_id, json.dumps(content)))
                
                self.connection.commit()
                
        except Exception as e:
            logger.error(f"Error storing dataset content: {e}")
            if self.connection:
                self.connection.rollback()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
