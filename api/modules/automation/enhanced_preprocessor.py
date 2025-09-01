#!/usr/bin/env python3
"""
Enhanced Preprocessing System
Intelligent deduplication, story consolidation, and smart tagging
"""

import os
import logging
import hashlib
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from collections import defaultdict, Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN

# Import ML services
from ..ml.summarization_service import MLSummarizationService
from ..ml.content_analyzer import ContentAnalyzer

logger = logging.getLogger(__name__)

class EnhancedPreprocessor:
    """Enhanced preprocessing system for intelligent article consolidation"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.ml_service = MLSummarizationService()
        self.content_analyzer = ContentAnalyzer()
        
        # Configuration
        self.config = {
            'similarity_threshold': 0.75,  # Articles with >75% similarity are considered duplicates
            'min_sources_for_consolidation': 2,  # Minimum sources to create master article
            'max_tags_per_article': 10,  # Maximum tags to extract
            'top_tags_display': 5,  # Top tags to display in UI
            'consolidation_time_window_hours': 24,  # Articles within 24h can be consolidated
            'min_article_length': 100,  # Minimum article length for processing
            'max_consolidation_articles': 20  # Maximum articles to consolidate into one master
        }
        
        # Initialize TF-IDF vectorizer for similarity
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.8
        )
        
        # Statistics
        self.stats = {
            'articles_processed': 0,
            'duplicates_found': 0,
            'master_articles_created': 0,
            'tags_extracted': 0,
            'consolidation_groups': 0
        }
    
    def process_new_articles(self, batch_size: int = 100) -> Dict[str, Any]:
        """
        Process new articles through enhanced preprocessing pipeline
        
        Args:
            batch_size: Number of articles to process in this batch
            
        Returns:
            Dictionary with processing results
        """
        try:
            logger.info(f"🔄 Starting enhanced preprocessing for {batch_size} articles...")
            
            # Get unprocessed articles
            unprocessed_articles = self._get_unprocessed_articles(batch_size)
            
            if not unprocessed_articles:
                logger.info("ℹ️ No unprocessed articles found")
                return {
                    'success': True,
                    'articles_processed': 0,
                    'message': 'No articles to process'
                }
            
            logger.info(f"📝 Found {len(unprocessed_articles)} unprocessed articles")
            
            # Step 1: Intelligent deduplication and grouping
            logger.info("🔍 Step 1: Intelligent deduplication and grouping...")
            article_groups = self._group_similar_articles(unprocessed_articles)
            
            # Step 2: Create master articles from groups
            logger.info("📰 Step 2: Creating master articles...")
            master_articles = self._create_master_articles(article_groups)
            
            # Step 3: Extract and rank tags
            logger.info("🏷️ Step 3: Extracting and ranking tags...")
            tagged_articles = self._extract_smart_tags(master_articles)
            
            # Step 4: Store processed articles
            logger.info("💾 Step 4: Storing processed articles...")
            stored_count = self._store_processed_articles(tagged_articles)
            
            # Update statistics
            self.stats['articles_processed'] += len(unprocessed_articles)
            self.stats['duplicates_found'] += sum(len(group) - 1 for group in article_groups if len(group) > 1)
            self.stats['master_articles_created'] += len(master_articles)
            self.stats['consolidation_groups'] += len(article_groups)
            
            logger.info(f"✅ Enhanced preprocessing completed: {stored_count} master articles created")
            
            return {
                'success': True,
                'articles_processed': len(unprocessed_articles),
                'master_articles_created': len(master_articles),
                'duplicates_consolidated': self.stats['duplicates_found'],
                'consolidation_groups': len(article_groups),
                'statistics': self.stats
            }
            
        except Exception as e:
            logger.error(f"Enhanced preprocessing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_unprocessed_articles(self, limit: int) -> List[Dict]:
        """Get articles that need preprocessing"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get articles that haven't been preprocessed yet
            cursor.execute("""
                SELECT id, title, content, summary, source, category, published_date, url
                FROM articles 
                WHERE (preprocessing_status IS NULL OR preprocessing_status = 'pending' OR processing_status = 'pending')
                AND LENGTH(COALESCE(content, '')) >= %s
                ORDER BY published_date DESC
                LIMIT %s
            """, (self.config['min_article_length'], limit))
            
            articles = cursor.fetchall()
            conn.close()
            
            return [dict(article) for article in articles]
            
        except Exception as e:
            logger.error(f"Error getting unprocessed articles: {e}")
            return []
    
    def _group_similar_articles(self, articles: List[Dict]) -> List[List[Dict]]:
        """Group similar articles using content similarity"""
        try:
            if len(articles) < 2:
                return [[article] for article in articles]
            
            # Prepare text for similarity analysis
            article_texts = []
            for article in articles:
                # Combine title and content for similarity analysis
                text = f"{article['title']} {article.get('content', '') or article.get('summary', '')}"
                article_texts.append(text)
            
            # Calculate TF-IDF vectors
            tfidf_matrix = self.vectorizer.fit_transform(article_texts)
            
            # Calculate cosine similarity
            # Handle case where all documents are identical (would cause division by zero)
            if tfidf_matrix.nnz == 0:
                # All documents are empty, treat as all different
                similarity_matrix = np.eye(len(story_texts))
            else:
                similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Group articles using DBSCAN clustering
            # Convert similarity to distance (1 - similarity)
            distance_matrix = 1 - similarity_matrix
            
            # Use DBSCAN for clustering
            clustering = DBSCAN(
                eps=1 - self.config['similarity_threshold'],
                min_samples=1,
                metric='precomputed'
            )
            
            cluster_labels = clustering.fit_predict(distance_matrix)
            
            # Group articles by cluster
            groups = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                groups[label].append(articles[i])
            
            # Convert to list and filter out noise (label -1)
            article_groups = [group for label, group in groups.items() if label != -1]
            
            logger.info(f"📊 Grouped {len(articles)} articles into {len(article_groups)} similarity groups")
            
            return article_groups
            
        except Exception as e:
            logger.error(f"Error grouping similar articles: {e}")
            # Fallback: return each article as its own group
            return [[article] for article in articles]
    
    def _create_master_articles(self, article_groups: List[List[Dict]]) -> List[Dict]:
        """Create master articles from groups of similar articles"""
        master_articles = []
        
        for group in article_groups:
            try:
                if len(group) == 1:
                    # Single article - just enhance it
                    master_article = self._enhance_single_article(group[0])
                else:
                    # Multiple articles - create consolidated master article
                    master_article = self._consolidate_articles(group)
                
                if master_article:
                    master_articles.append(master_article)
                    
            except Exception as e:
                logger.warning(f"Error creating master article for group: {e}")
                # Fallback: use the first article in the group
                if group:
                    master_articles.append(self._enhance_single_article(group[0]))
        
        return master_articles
    
    def _enhance_single_article(self, article: Dict) -> Dict:
        """Enhance a single article with additional metadata"""
        try:
            # Calculate source priority (single source = lower priority)
            source_priority = 1.0
            
            # Extract basic tags from title and content
            basic_tags = self._extract_basic_tags(article)
            
            enhanced_article = {
                'original_articles': [article['id']],
                'title': article['title'],
                'content': article.get('content') or article.get('summary', ''),
                'summary': article.get('summary', ''),
                'source': article['source'],
                'sources': [article['source']],
                'source_count': 1,
                'source_priority': source_priority,
                'category': article.get('category', 'General'),
                'published_at': article['published_date'],
                'url': article.get('url', ''),
                'tags': basic_tags,
                'preprocessing_status': 'enhanced_single',
                'created_at': datetime.now()
            }
            
            return enhanced_article
            
        except Exception as e:
            logger.error(f"Error enhancing single article: {e}")
            return None
    
    def _consolidate_articles(self, articles: List[Dict]) -> Dict:
        """Consolidate multiple similar articles into a master article"""
        try:
            if not articles:
                return None
            
            # Sort articles by source priority and recency
            articles.sort(key=lambda x: (x.get('published_date', datetime.min), x['source']))
            
            # Use the most recent article as the base
            base_article = articles[0]
            
            # Collect all sources
            sources = list(set([article['source'] for article in articles]))
            source_count = len(sources)
            
            # Calculate source priority (more sources = higher priority)
            source_priority = min(2.0, 1.0 + (source_count - 1) * 0.2)
            
            # Combine content from all articles
            combined_content = self._combine_article_content(articles)
            
            # Generate consolidated summary using ML
            consolidated_summary = self._generate_consolidated_summary(articles)
            
            # Extract comprehensive tags
            comprehensive_tags = self._extract_comprehensive_tags(articles)
            
            # Determine the best category
            category = self._determine_best_category(articles)
            
            # Create master article
            master_article = {
                'original_articles': [article['id'] for article in articles],
                'title': self._create_consolidated_title(articles),
                'content': combined_content,
                'summary': consolidated_summary,
                'source': f"Consolidated ({source_count} sources)",
                'sources': sources,
                'source_count': source_count,
                'source_priority': source_priority,
                'category': category,
                'published_at': base_article['published_date'],
                'url': base_article.get('url', ''),
                'tags': comprehensive_tags,
                'preprocessing_status': 'consolidated',
                'consolidation_metadata': {
                    'original_count': len(articles),
                    'sources': sources,
                    'consolidation_date': datetime.now().isoformat()
                },
                'created_at': datetime.now()
            }
            
            logger.info(f"📰 Created master article from {len(articles)} sources: {master_article['title'][:50]}...")
            
            return master_article
            
        except Exception as e:
            logger.error(f"Error consolidating articles: {e}")
            return None
    
    def _combine_article_content(self, articles: List[Dict]) -> str:
        """Combine content from multiple articles intelligently"""
        try:
            # Extract unique content from each article
            content_parts = []
            
            for article in articles:
                content = article.get('content') or article.get('summary', '')
                if content and len(content.strip()) > 50:  # Only include substantial content
                    content_parts.append(content.strip())
            
            # Remove duplicates and combine
            unique_content = []
            seen_content = set()
            
            for content in content_parts:
                # Simple deduplication based on content hash
                content_hash = hashlib.md5(content.encode()).hexdigest()
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    unique_content.append(content)
            
            # Combine with separators
            combined = "\n\n---\n\n".join(unique_content)
            
            # Limit total length
            max_length = 10000
            if len(combined) > max_length:
                combined = combined[:max_length] + "..."
            
            return combined
            
        except Exception as e:
            logger.error(f"Error combining article content: {e}")
            return articles[0].get('content', '') if articles else ''
    
    def _generate_consolidated_summary(self, articles: List[Dict]) -> str:
        """Generate a consolidated summary using ML"""
        try:
            # Prepare content for ML summarization
            combined_text = ""
            
            for article in articles:
                title = article.get('title', '')
                content = article.get('content') or article.get('summary', '')
                
                if content:
                    combined_text += f"Title: {title}\nContent: {content}\n\n"
            
            if not combined_text.strip():
                return "No content available for summarization."
            
            # Use ML service to generate consolidated summary
            summary_result = self.ml_service.generate_summary(
                article_content=combined_text,
                article_title=f"Consolidated story from {len(articles)} sources"
            )
            
            if summary_result and 'summary' in summary_result:
                return summary_result['summary']
            else:
                # Fallback: create simple summary
                return f"Consolidated story from {len(articles)} sources covering: {articles[0].get('title', 'Unknown topic')}"
                
        except Exception as e:
            logger.error(f"Error generating consolidated summary: {e}")
            return f"Consolidated story from {len(articles)} sources"
    
    def _extract_comprehensive_tags(self, articles: List[Dict]) -> List[Dict]:
        """Extract comprehensive tags from multiple articles"""
        try:
            all_tags = []
            
            # Extract tags from each article
            for article in articles:
                tags = self._extract_basic_tags(article)
                all_tags.extend(tags)
            
            # Count tag frequency and calculate scores
            tag_counts = Counter([tag['text'] for tag in all_tags])
            
            # Create ranked tags
            ranked_tags = []
            for tag_text, count in tag_counts.most_common():
                # Calculate score based on frequency and source count
                score = min(1.0, count / len(articles) + 0.1)
                
                ranked_tags.append({
                    'text': tag_text,
                    'type': 'consolidated',
                    'score': score,
                    'frequency': count,
                    'source_count': len(articles)
                })
            
            # Return top tags
            return ranked_tags[:self.config['max_tags_per_article']]
            
        except Exception as e:
            logger.error(f"Error extracting comprehensive tags: {e}")
            return []
    
    def _extract_basic_tags(self, article: Dict) -> List[Dict]:
        """Extract basic tags from a single article"""
        try:
            tags = []
            
            # Extract from title
            title = article.get('title', '')
            title_words = self._extract_meaningful_words(title)
            
            for word in title_words:
                tags.append({
                    'text': word,
                    'type': 'title',
                    'score': 0.8,
                    'frequency': 1
                })
            
            # Extract from content
            content = article.get('content', '') or article.get('summary', '')
            if content:
                content_words = self._extract_meaningful_words(content)
                
                for word in content_words[:10]:  # Limit content tags
                    tags.append({
                        'text': word,
                        'type': 'content',
                        'score': 0.6,
                        'frequency': 1
                    })
            
            return tags
            
        except Exception as e:
            logger.error(f"Error extracting basic tags: {e}")
            return []
    
    def _extract_meaningful_words(self, text: str) -> List[str]:
        """Extract meaningful words from text"""
        try:
            if not text:
                return []
            
            # Clean and tokenize
            text = re.sub(r'[^\w\s]', ' ', text.lower())
            words = text.split()
            
            # Filter out common words and short words
            stop_words = {
                'the', 'and', 'for', 'with', 'this', 'that', 'have', 'been', 'will', 'from',
                'are', 'was', 'were', 'said', 'says', 'new', 'news', 'report', 'reports',
                'according', 'sources', 'source', 'told', 'tells', 'could', 'would', 'should'
            }
            
            meaningful_words = []
            for word in words:
                if (len(word) > 3 and 
                    word not in stop_words and 
                    not word.isdigit() and
                    word not in meaningful_words):
                    meaningful_words.append(word)
            
            return meaningful_words[:20]  # Limit to 20 words
            
        except Exception as e:
            logger.error(f"Error extracting meaningful words: {e}")
            return []
    
    def _determine_best_category(self, articles: List[Dict]) -> str:
        """Determine the best category from multiple articles"""
        try:
            categories = [article.get('category', 'General') for article in articles]
            
            # Use the most common category
            category_counts = Counter(categories)
            best_category = category_counts.most_common(1)[0][0]
            
            return best_category
            
        except Exception as e:
            logger.error(f"Error determining best category: {e}")
            return 'General'
    
    def _create_consolidated_title(self, articles: List[Dict]) -> str:
        """Create a consolidated title from multiple articles"""
        try:
            # Use the most recent article's title as base
            base_title = articles[0].get('title', '')
            
            # If multiple sources, indicate consolidation
            if len(articles) > 1:
                source_count = len(set([article['source'] for article in articles]))
                if source_count > 1:
                    return f"{base_title} (from {source_count} sources)"
            
            return base_title
            
        except Exception as e:
            logger.error(f"Error creating consolidated title: {e}")
            return "Consolidated Story"
    
    def _extract_smart_tags(self, master_articles: List[Dict]) -> List[Dict]:
        """Extract and rank smart tags for master articles"""
        try:
            for article in master_articles:
                # Ensure tags are properly ranked
                if 'tags' in article and article['tags']:
                    # Sort by score and limit to top tags
                    article['tags'] = sorted(
                        article['tags'], 
                        key=lambda x: x.get('score', 0), 
                        reverse=True
                    )[:self.config['top_tags_display']]
                    
                    # Update tag count
                    self.stats['tags_extracted'] += len(article['tags'])
            
            return master_articles
            
        except Exception as e:
            logger.error(f"Error extracting smart tags: {e}")
            return master_articles
    
    def _store_processed_articles(self, master_articles: List[Dict]) -> int:
        """Store processed master articles in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            stored_count = 0
            
            for article in master_articles:
                try:
                    # Insert master article
                    cursor.execute("""
                        INSERT INTO master_articles (
                            title, content, summary, source, sources, source_count,
                            source_priority, category, published_at, url, tags,
                            preprocessing_status, consolidation_metadata, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        article['title'],
                        article['content'],
                        article['summary'],
                        article['source'],
                        json.dumps(article['sources']),
                        article['source_count'],
                        article['source_priority'],
                        article['category'],
                        article['published_at'],
                        article['url'],
                        json.dumps(article['tags']),
                        article['preprocessing_status'],
                        json.dumps(article.get('consolidation_metadata', {})),
                        article['created_at']
                    ))
                    
                    master_article_id = cursor.fetchone()[0]
                    
                    # Update original articles to link to master article
                    for original_id in article['original_articles']:
                        cursor.execute("""
                            UPDATE articles 
                            SET master_article_id = %s, preprocessing_status = 'consolidated'
                            WHERE id = %s
                        """, (master_article_id, original_id))
                    
                    stored_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error storing master article: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            return stored_count
            
        except Exception as e:
            logger.error(f"Error storing processed articles: {e}")
            return 0
    
    def get_preprocessing_statistics(self) -> Dict[str, Any]:
        """Get preprocessing statistics"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get master articles count
            cursor.execute("SELECT COUNT(*) as count FROM master_articles")
            master_count = cursor.fetchone()['count']
            
            # Get consolidated articles count
            cursor.execute("SELECT COUNT(*) as count FROM master_articles WHERE preprocessing_status = 'consolidated'")
            consolidated_count = cursor.fetchone()['count']
            
            # Get source distribution
            cursor.execute("""
                SELECT source_count, COUNT(*) as count
                FROM master_articles
                GROUP BY source_count
                ORDER BY source_count DESC
            """)
            source_distribution = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_master_articles': master_count,
                'consolidated_articles': consolidated_count,
                'single_source_articles': master_count - consolidated_count,
                'source_distribution': [dict(row) for row in source_distribution],
                'processing_statistics': self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting preprocessing statistics: {e}")
            return {}
