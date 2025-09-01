#!/usr/bin/env python3
"""
News Intelligence System v2.5.0 - Intelligence Orchestrator
Coordinates all intelligence modules for ML-ready data processing
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Import our intelligence modules
from .article_processor import ArticleProcessor
from .content_clusterer import ContentClusterer
from .ml_data_preparer import MLDataPreparer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelligenceOrchestrator:
    """Main orchestrator for intelligence processing pipeline"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.article_processor = ArticleProcessor(db_config)
        self.content_clusterer = ContentClusterer(db_config)
        self.ml_data_preparer = MLDataPreparer(db_config)
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
    
    def run_full_intelligence_pipeline(self, batch_size: int = 100) -> Dict:
        """Run the complete intelligence processing pipeline"""
        try:
            logger.info("🚀 Starting full intelligence processing pipeline...")
            
            pipeline_results = {
                'started_at': datetime.now().isoformat(),
                'steps_completed': [],
                'articles_processed': 0,
                'clusters_created': 0,
                'datasets_created': 0,
                'errors': []
            }
            
            # Step 1: Process articles for ML
            logger.info("📝 Step 1: Processing articles for ML...")
            try:
                processed_articles = self.article_processor.batch_process_articles(batch_size)
                pipeline_results['articles_processed'] = len(processed_articles)
                pipeline_results['steps_completed'].append('article_processing')
                logger.info(f"✅ Processed {len(processed_articles)} articles for ML")
            except Exception as e:
                error_msg = f"Article processing failed: {e}"
                logger.error(error_msg)
                pipeline_results['errors'].append(error_msg)
            
            # Step 2: Create content clusters
            logger.info("🔗 Step 2: Creating content clusters...")
            try:
                clusters = self.content_clusterer.create_article_clusters()
                pipeline_results['clusters_created'] = len(clusters)
                pipeline_results['steps_completed'].append('content_clustering')
                logger.info(f"✅ Created {len(clusters)} content clusters")
            except Exception as e:
                error_msg = f"Content clustering failed: {e}"
                logger.error(error_msg)
                pipeline_results['errors'].append(error_msg)
            
            # Step 3: Create ML datasets
            logger.info("📊 Step 3: Creating ML datasets...")
            try:
                datasets = self._create_default_datasets()
                pipeline_results['datasets_created'] = len(datasets)
                pipeline_results['steps_completed'].append('dataset_creation')
                logger.info(f"✅ Created {len(datasets)} ML datasets")
            except Exception as e:
                error_msg = f"Dataset creation failed: {e}"
                logger.error(error_msg)
                pipeline_results['errors'].append(error_msg)
            
            # Step 4: Generate pipeline report
            pipeline_results['completed_at'] = datetime.now().isoformat()
            pipeline_results['duration_minutes'] = self._calculate_duration(
                pipeline_results['started_at'], 
                pipeline_results['completed_at']
            )
            
            # Store pipeline results
            self._store_pipeline_results(pipeline_results)
            
            logger.info("🎉 Intelligence pipeline completed!")
            logger.info(f"📊 Results: {pipeline_results['articles_processed']} articles, "
                       f"{pipeline_results['clusters_created']} clusters, "
                       f"{pipeline_results['datasets_created']} datasets")
            
            return pipeline_results
            
        except Exception as e:
            logger.error(f"Intelligence pipeline failed: {e}")
            return {
                'error': str(e),
                'started_at': datetime.now().isoformat(),
                'completed_at': datetime.now().isoformat()
            }
    
    def process_single_article(self, article_id: int) -> Dict:
        """Process a single article through the intelligence pipeline"""
        try:
            logger.info(f"🔍 Processing single article {article_id}...")
            
            # Process article for ML
            ml_data = self.article_processor.process_article_for_ml(article_id)
            if not ml_data:
                return {'error': 'Failed to process article for ML'}
            
            # Find similar articles
            similar_articles = self.content_clusterer.find_similar_articles(article_id)
            
            # Create mini-dataset for this article
            dataset_name = f"single_article_{article_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            dataset = self.ml_data_preparer.create_ml_dataset(dataset_name, {
                'article_ids': [article_id]
            })
            
            return {
                'article_id': article_id,
                'ml_data': ml_data,
                'similar_articles': len(similar_articles),
                'dataset_created': dataset.get('dataset_id', 0),
                'processing_status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Error processing single article {article_id}: {e}")
            return {'error': str(e)}
    
    def get_intelligence_status(self) -> Dict:
        """Get current status of intelligence processing"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return {}
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'database_connected': True,
                'processing_stats': {},
                'recent_activity': [],
                'system_health': 'healthy'
            }
            
            # Get processing statistics
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Total articles
                cursor.execute("SELECT COUNT(*) as total FROM articles")
                total_articles = cursor.fetchone()['total']
                
                # ML processed articles
                cursor.execute("""
                    SELECT COUNT(*) as processed 
                    FROM articles 
                    WHERE processing_status = 'ml_processed'
                """)
                processed_articles = cursor.fetchone()['processed']
                
                # Processing errors
                cursor.execute("""
                    SELECT COUNT(*) as errors 
                    FROM articles 
                    WHERE processing_status = 'processing_error'
                """)
                error_count = cursor.fetchone()['errors']
                
                # Recent processing activity
                cursor.execute("""
                    SELECT id, title, processing_status, updated_at
                    FROM articles 
                    WHERE updated_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY updated_at DESC 
                    LIMIT 10
                """)
                recent_activity = cursor.fetchall()
                
                # Cluster count
                cursor.execute("SELECT COUNT(*) as clusters FROM article_clusters")
                cluster_count = cursor.fetchone()['clusters']
                
                # Dataset count
                cursor.execute("SELECT COUNT(*) as datasets FROM ml_datasets")
                dataset_count = cursor.fetchone()['datasets']
            
            status['processing_stats'] = {
                'total_articles': total_articles,
                'ml_processed': processed_articles,
                'processing_errors': error_count,
                'processing_progress': round((processed_articles / total_articles * 100), 2) if total_articles > 0 else 0,
                'clusters_created': cluster_count,
                'datasets_created': dataset_count
            }
            
            status['recent_activity'] = [
                {
                    'article_id': row['id'],
                    'title': row['title'][:50] + '...' if len(row['title']) > 50 else row['title'],
                    'status': row['processing_status'],
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                }
                for row in recent_activity
            ]
            
            # Check system health
            if error_count > total_articles * 0.1:  # More than 10% errors
                status['system_health'] = 'warning'
            elif error_count > total_articles * 0.2:  # More than 20% errors
                status['system_health'] = 'critical'
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting intelligence status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'database_connected': False,
                'error': str(e),
                'system_health': 'error'
            }
    
    def create_custom_dataset(self, dataset_name: str, filters: Dict[str, Any]) -> Dict:
        """Create a custom ML dataset with specific filters"""
        try:
            logger.info(f"📊 Creating custom dataset '{dataset_name}' with filters: {filters}")
            
            dataset = self.ml_data_preparer.create_ml_dataset(dataset_name, filters)
            
            if dataset:
                logger.info(f"✅ Created custom dataset '{dataset_name}' with {dataset['article_count']} articles")
                
                # Get dataset statistics
                stats = self.ml_data_preparer.get_dataset_statistics(dataset['dataset_id'])
                dataset['statistics'] = stats
                
                return dataset
            else:
                return {'error': 'Failed to create dataset'}
                
        except Exception as e:
            logger.error(f"Error creating custom dataset: {e}")
            return {'error': str(e)}
    
    def export_dataset(self, dataset_id: int, format_type: str = 'csv', output_path: str = None) -> Dict:
        """Export a dataset in specified format"""
        try:
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"dataset_{dataset_id}_{timestamp}.{format_type}"
            
            if format_type.lower() == 'csv':
                success = self.ml_data_preparer.export_dataset_to_csv(dataset_id, output_path)
            else:
                return {'error': f'Unsupported format: {format_type}'}
            
            if success:
                return {
                    'dataset_id': dataset_id,
                    'format': format_type,
                    'output_path': output_path,
                    'export_status': 'success'
                }
            else:
                return {'error': 'Export failed'}
                
        except Exception as e:
            logger.error(f"Error exporting dataset: {e}")
            return {'error': str(e)}
    
    def _create_default_datasets(self) -> List[Dict]:
        """Create default ML datasets for common use cases"""
        try:
            datasets = []
            
            # High-quality recent articles
            high_quality_dataset = self.ml_data_preparer.create_ml_dataset(
                "high_quality_recent",
                {
                    'min_quality': 70,
                    'start_date': datetime.now() - timedelta(days=7)
                }
            )
            if high_quality_dataset:
                datasets.append(high_quality_dataset)
            
            # Long-form articles
            long_form_dataset = self.ml_data_preparer.create_ml_dataset(
                "long_form_articles",
                {
                    'min_words': 500,
                    'min_quality': 50
                }
            )
            if long_form_dataset:
                datasets.append(long_form_dataset)
            
            # Recent breaking news
            breaking_news_dataset = self.ml_data_preparer.create_ml_dataset(
                "breaking_news",
                {
                    'start_date': datetime.now() - timedelta(hours=24),
                    'min_quality': 60
                }
            )
            if breaking_news_dataset:
                datasets.append(breaking_news_dataset)
            
            return datasets
            
        except Exception as e:
            logger.error(f"Error creating default datasets: {e}")
            return []
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """Calculate duration between two timestamps in minutes"""
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            duration = end - start
            return round(duration.total_seconds() / 60, 2)
        except Exception:
            return 0.0
    
    def _store_pipeline_results(self, results: Dict):
        """Store pipeline results in database"""
        try:
            if not self.connection:
                return
            
            with self.connection.cursor() as cursor:
                # Create pipeline results table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS intelligence_pipeline_results (
                        result_id SERIAL PRIMARY KEY,
                        started_at TIMESTAMP NOT NULL,
                        completed_at TIMESTAMP NOT NULL,
                        duration_minutes DECIMAL(10,2),
                        articles_processed INTEGER,
                        clusters_created INTEGER,
                        datasets_created INTEGER,
                        steps_completed TEXT[],
                        errors TEXT[],
                        results_data JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Insert results
                cursor.execute("""
                    INSERT INTO intelligence_pipeline_results 
                    (started_at, completed_at, duration_minutes, articles_processed, 
                     clusters_created, datasets_created, steps_completed, errors, results_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    results['started_at'],
                    results['completed_at'],
                    results.get('duration_minutes', 0),
                    results.get('articles_processed', 0),
                    results.get('clusters_created', 0),
                    results.get('datasets_created', 0),
                    results.get('steps_completed', []),
                    results.get('errors', []),
                    json.dumps(results)
                ))
                
                self.connection.commit()
                
        except Exception as e:
            logger.error(f"Error storing pipeline results: {e}")
            if self.connection:
                self.connection.rollback()
    
    def close(self):
        """Close all connections"""
        try:
            self.article_processor.close()
            self.content_clusterer.close()
            self.ml_data_preparer.close()
            
            if self.connection:
                self.connection.close()
                self.connection = None
                
        except Exception as e:
            logger.error(f"Error closing connections: {e}")
