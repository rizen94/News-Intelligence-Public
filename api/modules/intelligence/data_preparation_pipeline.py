#!/usr/bin/env python3
"""
Data Preparation Pipeline for News Intelligence System v2.5.0
Integrates entity extraction, event detection, and data preparation for ML summarization
"""

import os
import sys
import json
import logging
import psycopg2
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from enhanced_entity_extractor import EnhancedEntityExtractor, EventCandidate
except ImportError:
    print("Warning: EnhancedEntityExtractor not available. Using basic functionality.")
    EnhancedEntityExtractor = None
    EventCandidate = None

try:
    from article_processor import ArticleProcessor
except ImportError:
    print("Warning: ArticleProcessor not available. Using basic functionality.")
    ArticleProcessor = None

try:
    from article_deduplicator import ArticleDeduplicator
except ImportError:
    print("Warning: ArticleDeduplicator not available. Using basic functionality.")
    ArticleDeduplicator = None

try:
    from content_cleaner import ContentCleaner
except ImportError:
    print("Warning: ContentCleaner not available. Using basic functionality.")
    ContentCleaner = None

try:
    from language_detector import LanguageDetector
except ImportError:
    print("Warning: LanguageDetector not available. Using basic functionality.")
    LanguageDetector = None

try:
    from quality_validator import QualityValidator
except ImportError:
    print("Warning: QualityValidator not available. Using basic functionality.")
    QualityValidator = None

try:
    from article_stager import ArticleStager
except ImportError:
    print("Warning: ArticleStager not available. Using basic functionality.")
    ArticleStager = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/data_preparation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PipelineStep:
    """Represents a step in the data preparation pipeline."""
    name: str
    description: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    articles_processed: int = 0
    articles_successful: int = 0
    articles_failed: int = 0
    errors: List[str] = None
    warnings: List[str] = None
    results: Dict = None

class DataPreparationPipeline:
    """
    Comprehensive data preparation pipeline that processes raw articles
    through entity extraction, event detection, and ML preparation.
    """
    
    def __init__(self, db_config: Dict = None):
        """Initialize the data preparation pipeline."""
        self.db_config = db_config or {
            'host': os.getenv('DB_HOST', 'postgres'),
            'database': os.getenv('DB_NAME', 'news_db'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
            'port': os.getenv('DB_PORT', '5432'),
            'connect_timeout': 10,
            'options': '-c statement_timeout=5000'
        }
        
        # Initialize components
        self.entity_extractor = None
        if EnhancedEntityExtractor:
            self.entity_extractor = EnhancedEntityExtractor(db_config)
        
        self.article_processor = None
        if ArticleProcessor:
            self.article_processor = ArticleProcessor(db_config)
        
        self.deduplicator = None
        if ArticleDeduplicator:
            self.deduplicator = ArticleDeduplicator(db_config)
        
        # Initialize new intelligence components
        self.content_cleaner = None
        if ContentCleaner:
            self.content_cleaner = ContentCleaner()
        
        self.language_detector = None
        if LanguageDetector:
            self.language_detector = LanguageDetector()
        
        self.quality_validator = None
        if QualityValidator:
            self.quality_validator = QualityValidator()
        
        self.article_stager = None
        if ArticleStager:
            self.article_stager = ArticleStager(db_config)
        
        # Pipeline configuration
        self.pipeline_config = {
            'max_articles_per_batch': 100,
            'max_workers': 4,
            'timeout_seconds': 300,
            'enable_staging': True,
            'enable_content_cleaning': True,
            'enable_language_detection': True,
            'enable_quality_validation': True,
            'enable_deduplication': True,
            'enable_event_detection': True,
            'enable_entity_extraction': True,
            'enable_ml_preparation': True,
            'min_confidence_threshold': 0.5
        }
        
        # Pipeline steps
        self.pipeline_steps = []
        self.current_step = None
        
        # Statistics
        self.total_articles_processed = 0
        self.total_articles_staged = 0
        self.total_articles_cleaned = 0
        self.total_articles_language_detected = 0
        self.total_articles_validated = 0
        self.total_events_detected = 0
        self.total_entities_extracted = 0
        self.total_duplicates_removed = 0
        self.pipeline_start_time = None
        self.pipeline_end_time = None
    
    def _get_db_connection(self) -> Optional[psycopg2.extensions.connection]:
        """Get database connection with error handling."""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            return None
    
    def _close_db_connection(self, conn: psycopg2.extensions.connection):
        """Close database connection safely."""
        if conn and not conn.closed:
            conn.close()
    
    def _create_pipeline_step(self, name: str, description: str) -> PipelineStep:
        """Create a new pipeline step."""
        step = PipelineStep(
            name=name,
            description=description,
            status='pending',
            errors=[],
            warnings=[],
            results={}
        )
        self.pipeline_steps.append(step)
        return step
    
    def _start_step(self, step: PipelineStep):
        """Start a pipeline step."""
        step.status = 'running'
        step.start_time = datetime.now()
        self.current_step = step
        logger.info(f"Starting pipeline step: {step.name}")
    
    def _complete_step(self, step: PipelineStep, success: bool = True):
        """Complete a pipeline step."""
        step.status = 'completed' if success else 'failed'
        step.end_time = datetime.now()
        if step.start_time:
            step.duration_seconds = (step.end_time - step.start_time).total_seconds()
        
        self.current_step = None
        status_msg = "completed successfully" if success else "failed"
        logger.info(f"Pipeline step '{step.name}' {status_msg} in {step.duration_seconds:.2f}s")
    
    def _get_raw_articles(self, limit: int = None) -> List[Dict]:
        """Get raw articles from the database."""
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            limit_clause = f"LIMIT {limit}" if limit else ""
            query = f"""
                SELECT id, title, content, url, published_date, created_at, source
                FROM articles 
                WHERE processing_status = 'raw'
                ORDER BY published_date DESC
                {limit_clause}
            """
            
            cursor = conn.cursor()
            cursor.execute(query)
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'url': row[3],
                    'published_date': row[4],
                    'created_at': row[5],
                    'source': row[6]
                })
            
            cursor.close()
            return articles
            
        except psycopg2.Error as e:
            logger.error(f"Database error getting raw articles: {e}")
            return []
        finally:
            self._close_db_connection(conn)
    
    def _update_article_status(self, article_id: int, status: str, **kwargs):
        """Update article processing status and metadata."""
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            # Build dynamic update query
            update_fields = ['processing_status = %s']
            update_values = [status]
            
            for key, value in kwargs.items():
                if value is not None:
                    update_fields.append(f"{key} = %s")
                    update_values.append(value)
            
            update_fields.append('updated_at = %s')
            update_values.append(datetime.now())
            update_values.append(article_id)
            
            query = f"""
                UPDATE articles 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            
            cursor = conn.cursor()
            cursor.execute(query, update_values)
            cursor.close()
            
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database error updating article status: {e}")
            return False
        finally:
            self._close_db_connection(conn)
    
    def _extract_entities_batch(self, articles: List[Dict]) -> Dict[int, Dict]:
        """Extract entities from a batch of articles."""
        if not self.entity_extractor:
            logger.warning("Entity extractor not available, skipping entity extraction")
            return {}
        
        entity_results = {}
        
        for article in articles:
            try:
                # Extract entities
                entities = self.entity_extractor.extract_entities(article.get('content', ''))
                
                # Group entities by type
                grouped_entities = self.entity_extractor.group_entities_by_type(entities)
                
                # Store results
                entity_results[article['id']] = {
                    'entities': grouped_entities,
                    'entity_count': len(entities),
                    'extraction_success': True
                }
                
                # Update article with entity information
                self._update_article_status(
                    article['id'],
                    'entity_extracted',
                    person_entities=json.dumps(grouped_entities.get('PERSON', [])),
                    organization_entities=json.dumps(grouped_entities.get('ORG', [])),
                    location_entities=json.dumps(grouped_entities.get('GPE', [])),
                    ml_data=json.dumps({
                        'entity_extraction': {
                            'timestamp': datetime.now().isoformat(),
                            'entities_found': len(entities),
                            'entity_types': list(grouped_entities.keys())
                        }
                    })
                )
                
            except Exception as e:
                logger.error(f"Error extracting entities from article {article['id']}: {e}")
                entity_results[article['id']] = {
                    'entities': {},
                    'entity_count': 0,
                    'extraction_success': False,
                    'error': str(e)
                }
                
                # Mark article as failed
                self._update_article_status(
                    article['id'],
                    'processing_error',
                    ml_data=json.dumps({
                        'entity_extraction_error': {
                            'timestamp': datetime.now().isoformat(),
                            'error': str(e)
                        }
                    })
                )
        
        return entity_results
    
    def _detect_events_batch(self, articles: List[Dict]) -> List[EventCandidate]:
        """Detect events from a batch of articles."""
        if not self.entity_extractor:
            logger.warning("Entity extractor not available, skipping event detection")
            return []
        
        try:
            # Detect event candidates
            candidates = self.entity_extractor.detect_event_candidates(articles)
            logger.info(f"Detected {len(candidates)} event candidates")
            
            # Merge similar events
            merged_events = self.entity_extractor.merge_similar_events(candidates)
            logger.info(f"Merged into {len(merged_events)} unique events")
            
            return merged_events
            
        except Exception as e:
            logger.error(f"Error during event detection: {e}")
            return []
    
    def _process_articles_ml(self, articles: List[Dict]) -> Dict[int, Dict]:
        """Process articles for ML preparation."""
        if not self.article_processor:
            logger.warning("Article processor not available, skipping ML preparation")
            return {}
        
        ml_results = {}
        
        for article in articles:
            try:
                # Process article for ML
                ml_data = self.article_processor.process_article_for_ml(article['id'])
                
                if ml_data:
                    ml_results[article['id']] = {
                        'ml_processing_success': True,
                        'ml_data': ml_data
                    }
                    
                    # Update article status
                    self._update_article_status(
                        article['id'],
                        'ml_processed',
                        processing_completed_at=datetime.now(),
                        ml_data=json.dumps(ml_data)
                    )
                else:
                    ml_results[article['id']] = {
                        'ml_processing_success': False,
                        'error': 'No ML data returned'
                    }
                    
                    # Mark as failed
                    self._update_article_status(
                        article['id'],
                        'processing_error',
                        ml_data=json.dumps({
                            'ml_processing_error': {
                                'timestamp': datetime.now().isoformat(),
                                'error': 'No ML data returned'
                            }
                        })
                    )
                
            except Exception as e:
                logger.error(f"Error processing article {article['id']} for ML: {e}")
                ml_results[article['id']] = {
                    'ml_processing_success': False,
                    'error': str(e)
                }
                
                # Mark as failed
                self._update_article_status(
                    article['id'],
                    'processing_error',
                    ml_data=json.dumps({
                        'ml_processing_error': {
                            'timestamp': datetime.now().isoformat(),
                            'error': str(e)
                        }
                    })
                )
        
        return ml_results
    
    def _save_pipeline_results(self, step: PipelineStep, events: List[EventCandidate] = None):
        """Save pipeline execution results to the database."""
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            # Save pipeline execution results
            pipeline_query = """
                INSERT INTO intelligence_pipeline_results (
                    pipeline_version, pipeline_type, started_at, completed_at,
                    duration_minutes, articles_processed, articles_successful,
                    articles_failed, clusters_created, datasets_created,
                    steps_completed, errors, warnings, results_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            duration_minutes = step.duration_seconds / 60 if step.duration_seconds else 0
            
            pipeline_data = (
                '2.1.1',
                'full_pipeline',
                step.start_time,
                step.end_time,
                duration_minutes,
                step.articles_processed,
                step.articles_successful,
                step.articles_failed,
                len(events) if events else 0,
                0,  # datasets_created
                [s.name for s in self.pipeline_steps if s.status == 'completed'],
                step.errors,
                step.warnings,
                json.dumps(step.results)
            )
            
            cursor = conn.cursor()
            cursor.execute(pipeline_query, pipeline_data)
            cursor.close()
            
            # Save events if any were detected
            if events and self.entity_extractor:
                self.entity_extractor.save_events_to_database(events)
            
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database error saving pipeline results: {e}")
            return False
        finally:
            self._close_db_connection(conn)
    
    def run_full_pipeline(self, max_articles: int = None) -> bool:
        """Run the complete data preparation pipeline with enhanced intelligence."""
        self.pipeline_start_time = datetime.now()
        logger.info("Starting enhanced data preparation pipeline with intelligence components")
        
        try:
            # Step 1: Article Collection and Staging
            step1 = self._create_pipeline_step(
                "article_collection_staging",
                "Collect and stage raw articles for processing"
            )
            self._start_step(step1)
            
            articles = self._get_raw_articles(max_articles or self.pipeline_config['max_articles_per_batch'])
            if not articles:
                logger.info("No raw articles found for processing")
                self._complete_step(step1, True)
                return True
            
            # Stage articles if staging is enabled
            if self.pipeline_config['enable_staging'] and self.article_stager:
                staged_articles = []
                for article in articles:
                    staging_result = self.article_stager.stage_article(article)
                    if staging_result.success:
                        staged_articles.append(article)
                        self.total_articles_staged += 1
                    else:
                        logger.warning(f"Failed to stage article {article['id']}: {staging_result.message}")
                
                articles = staged_articles
                logger.info(f"Staged {len(staged_articles)} articles for processing")
            
            step1.articles_processed = len(articles)
            step1.results['articles_found'] = len(articles)
            step1.results['articles_staged'] = self.total_articles_staged
            self._complete_step(step1, True)
            
            # Step 2: Content Cleaning
            if self.pipeline_config['enable_content_cleaning'] and self.content_cleaner:
                step2 = self._create_pipeline_step(
                    "content_cleaning",
                    "Clean and normalize article content"
                )
                self._start_step(step2)
                
                cleaned_articles = []
                for article in articles:
                    try:
                        cleaning_result = self.content_cleaner.clean_content(
                            article.get('content', ''), 
                            article.get('url', '')
                        )
                        
                        if cleaning_result.quality_score > 0.3:  # Minimum quality threshold
                            article['cleaned_content'] = cleaning_result.cleaned_content
                            article['cleaning_metadata'] = {
                                'quality_score': cleaning_result.quality_score,
                                'cleaning_actions': cleaning_result.cleaning_actions,
                                'original_length': cleaning_result.original_length,
                                'cleaned_length': cleaning_result.cleaned_length
                            }
                            cleaned_articles.append(article)
                            self.total_articles_cleaned += 1
                        else:
                            logger.warning(f"Article {article['id']} failed quality threshold after cleaning")
                    except Exception as e:
                        logger.error(f"Content cleaning failed for article {article['id']}: {e}")
                
                articles = cleaned_articles
                step2.articles_processed = len(articles)
                step2.results['articles_cleaned'] = self.total_articles_cleaned
                step2.results['cleaning_success_rate'] = (len(cleaned_articles) / len(articles) * 100) if articles else 0
                self._complete_step(step2, True)
                logger.info(f"Content cleaning completed: {self.total_articles_cleaned} articles cleaned")
            
            # Step 3: Language Detection
            if self.pipeline_config['enable_language_detection'] and self.language_detector:
                step3 = self._create_pipeline_step(
                    "language_detection",
                    "Detect article language and filter content"
                )
                self._start_step(step3)
                
                english_articles = []
                for article in articles:
                    try:
                        lang_result = self.language_detector.detect_language(
                            article.get('cleaned_content', article.get('content', '')),
                            article.get('url', '')
                        )
                        
                        if lang_result.is_english and lang_result.is_reliable:
                            article['language_detection'] = {
                                'detected_language': lang_result.detected_language,
                                'confidence_score': lang_result.confidence_score,
                                'detection_method': lang_result.detection_method
                            }
                            english_articles.append(article)
                            self.total_articles_language_detected += 1
                        else:
                            logger.info(f"Article {article['id']} filtered out: language {lang_result.detected_language} (confidence: {lang_result.confidence_score})")
                    except Exception as e:
                        logger.error(f"Language detection failed for article {article['id']}: {e}")
                
                articles = english_articles
                step3.articles_processed = len(articles)
                step3.results['articles_language_detected'] = self.total_articles_language_detected
                step3.results['language_filtering_rate'] = (len(english_articles) / len(articles) * 100) if articles else 0
                self._complete_step(step3, True)
                logger.info(f"Language detection completed: {self.total_articles_language_detected} English articles identified")
            
            # Step 4: Quality Validation
            if self.pipeline_config['enable_quality_validation'] and self.quality_validator:
                step4 = self._create_pipeline_step(
                    "quality_validation",
                    "Validate content quality and completeness"
                )
                self._start_step(step4)
                
                validated_articles = []
                for article in articles:
                    try:
                        validation_result = self.quality_validator.validate_content(
                            article.get('cleaned_content', article.get('content', '')),
                            article.get('url', ''),
                            article.get('id')
                        )
                        
                        if validation_result.validation_status in ['passed', 'warning']:
                            article['quality_validation'] = {
                                'validation_status': validation_result.validation_status,
                                'quality_score': validation_result.quality_metrics.quality_score,
                                'readability_score': validation_result.quality_metrics.readability_score,
                                'issues': validation_result.quality_metrics.issues,
                                'recommendations': validation_result.quality_metrics.recommendations
                            }
                            validated_articles.append(article)
                            self.total_articles_validated += 1
                        else:
                            logger.warning(f"Article {article['id']} failed quality validation: {validation_result.quality_metrics.issues}")
                    except Exception as e:
                        logger.error(f"Quality validation failed for article {article['id']}: {e}")
                
                articles = validated_articles
                step4.articles_processed = len(articles)
                step4.results['articles_validated'] = self.total_articles_validated
                step4.results['validation_success_rate'] = (len(validated_articles) / len(articles) * 100) if articles else 0
                self._complete_step(step4, True)
                logger.info(f"Quality validation completed: {self.total_articles_validated} articles validated")
            
            # Step 5: Deduplication
            if self.pipeline_config['enable_deduplication'] and self.deduplicator:
                step5 = self._create_pipeline_step(
                    "deduplication",
                    "Remove duplicate articles to ensure data quality"
                )
                self._start_step(step5)
                
                dedup_results = self.deduplicator.run_deduplication(len(articles))
                if dedup_results['status'] == 'success':
                    step5.articles_processed = dedup_results['articles_processed']
                    step5.results['duplicate_groups_found'] = dedup_results['duplicate_groups_found']
                    step5.results['total_duplicates'] = dedup_results['total_duplicates']
                    step5.results['duplicate_rate'] = dedup_results['duplicate_rate']
                    step5.results['processing_time'] = dedup_results['processing_time_seconds']
                    self._complete_step(step5, True)
                    
                    # Update article count after deduplication
                    remaining_articles = dedup_results['articles_processed'] - dedup_results['total_duplicates']
                    self.total_duplicates_removed += dedup_results['total_duplicates']
                    logger.info(f"Deduplication completed: {dedup_results['total_duplicates']} duplicates removed, {remaining_articles} articles remaining")
                else:
                    step5.errors.append(f"Deduplication failed: {dedup_results.get('error', 'Unknown error')}")
                    self._complete_step(step5, False)
                    logger.error("Deduplication step failed, continuing with pipeline")
            
            # Step 6: Entity Extraction
            if self.pipeline_config['enable_entity_extraction']:
                step6 = self._create_pipeline_step(
                    "entity_extraction",
                    "Extract entities from article content"
                )
                self._start_step(step6)
                
                entity_results = self._extract_entities_batch(articles)
                successful_extractions = sum(1 for r in entity_results.values() if r.get('extraction_success', False))
                
                step6.articles_processed = len(articles)
                step6.articles_successful = successful_extractions
                step6.articles_failed = len(articles) - successful_extractions
                step6.results['entities_extracted'] = sum(r.get('entity_count', 0) for r in entity_results.values())
                self._complete_step(step6, True)
                
                self.total_entities_extracted += step6.results['entities_extracted']
            
            # Step 7: Event Detection
            events = []
            if self.pipeline_config['enable_event_detection']:
                step7 = self._create_pipeline_step(
                    "event_detection",
                    "Detect and group events from articles"
                )
                self._start_step(step7)
                
                events = self._detect_events_batch(articles)
                
                step7.articles_processed = len(articles)
                step7.results['events_detected'] = len(events)
                self._complete_step(step7, True)
                
                self.total_events_detected += len(events)
            
            # Step 8: ML Preparation
            if self.pipeline_config['enable_ml_preparation']:
                step8 = self._create_pipeline_step(
                    "ml_preparation",
                    "Prepare articles for ML processing"
                )
                self._start_step(step8)
                
                ml_results = self._process_articles_ml(articles)
                successful_ml = sum(1 for r in ml_results.values() if r.get('ml_processing_success', False))
                
                step8.articles_processed = len(articles)
                step8.articles_successful = successful_ml
                step8.articles_failed = len(articles) - successful_ml
                self._complete_step(step8, True)
            
            # Update final statistics
            self.total_articles_processed += len(articles)
            
            # Save pipeline results
            final_step = self.pipeline_steps[-1] if self.pipeline_steps else None
            if final_step:
                self._save_pipeline_results(final_step, events)
            
            self.pipeline_end_time = datetime.now()
            total_duration = (self.pipeline_end_time - self.pipeline_start_time).total_seconds()
            
            logger.info(f"Pipeline completed successfully in {total_duration:.2f}s")
            logger.info(f"Processed {self.total_articles_processed} articles")
            logger.info(f"Removed {self.total_duplicates_removed} duplicates")
            logger.info(f"Detected {self.total_events_detected} events")
            logger.info(f"Extracted {self.total_entities_extracted} entities")
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            if self.current_step:
                self.current_step.errors.append(str(e))
                self._complete_step(self.current_step, False)
            return False
    
    def run_incremental_pipeline(self, hours_back: int = 24) -> bool:
        """Run incremental pipeline for recent articles."""
        logger.info(f"Starting incremental pipeline for articles from last {hours_back} hours")
        
        # Get articles from the last N hours
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            query = """
                SELECT id FROM articles 
                WHERE created_at >= %s AND processing_status = 'raw'
                ORDER BY created_at DESC
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_time,))
            
            recent_article_ids = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            if not recent_article_ids:
                logger.info("No recent articles found for incremental processing")
                return True
            
            logger.info(f"Found {len(recent_article_ids)} recent articles for processing")
            
            # Run pipeline on recent articles
            return self.run_full_pipeline(len(recent_article_ids))
            
        except psycopg2.Error as e:
            logger.error(f"Database error during incremental pipeline: {e}")
            return False
        finally:
            self._close_db_connection(conn)
    
    def get_pipeline_status(self) -> Dict:
        """Get current pipeline status and statistics."""
        return {
            'pipeline_status': 'running' if self.current_step else 'idle',
            'current_step': self.current_step.name if self.current_step else None,
            'total_steps': len(self.pipeline_steps),
            'completed_steps': len([s for s in self.pipeline_steps if s.status == 'completed']),
            'failed_steps': len([s for s in self.pipeline_steps if s.status == 'failed']),
            'total_articles_processed': self.total_articles_processed,
            'total_articles_staged': self.total_articles_staged,
            'total_articles_cleaned': self.total_articles_cleaned,
            'total_articles_language_detected': self.total_articles_language_detected,
            'total_articles_validated': self.total_articles_validated,
            'total_duplicates_removed': self.total_duplicates_removed,
            'total_events_detected': self.total_events_detected,
            'total_entities_extracted': self.total_entities_extracted,
            'pipeline_start_time': self.pipeline_start_time.isoformat() if self.pipeline_start_time else None,
            'pipeline_end_time': self.pipeline_end_time.isoformat() if self.pipeline_end_time else None,
            'step_details': [
                {
                    'name': step.name,
                    'status': step.status,
                    'duration_seconds': step.duration_seconds,
                    'articles_processed': step.articles_processed,
                    'articles_successful': step.articles_successful,
                    'articles_failed': step.articles_failed
                }
                for step in self.pipeline_steps
            ]
        }
    
    def reset_pipeline(self):
        """Reset pipeline state for a new run."""
        self.pipeline_steps = []
        self.current_step = None
        self.pipeline_start_time = None
        self.pipeline_end_time = None
        logger.info("Pipeline reset for new run")

def main():
    """Main function for testing the data preparation pipeline."""
    print("Testing Data Preparation Pipeline...")
    
    # Initialize pipeline
    pipeline = DataPreparationPipeline()
    
    # Check component availability
    print(f"Entity Extractor Available: {pipeline.entity_extractor is not None}")
    print(f"Article Processor Available: {pipeline.article_processor is not None}")
    
    # Run pipeline
    print("\nRunning full pipeline...")
    success = pipeline.run_full_pipeline(max_articles=10)
    
    if success:
        print("Pipeline completed successfully!")
        
        # Show status
        status = pipeline.get_pipeline_status()
        print(f"\nPipeline Status:")
        print(f"  Total Articles Processed: {status['total_articles_processed']}")
        print(f"  Total Events Detected: {status['total_events_detected']}")
        print(f"  Total Entities Extracted: {status['total_entities_extracted']}")
        
        print(f"\nStep Details:")
        for step in status['step_details']:
            print(f"  {step['name']}: {step['status']} ({step['duration_seconds']:.2f}s)")
            print(f"    Articles: {step['articles_successful']}/{step['articles_processed']} successful")
    else:
        print("Pipeline failed!")

if __name__ == "__main__":
    main()
