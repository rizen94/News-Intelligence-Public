"""
Enhanced RAG Service for News Intelligence System
Integrates with ML summarizer for intelligent context retrieval and generation
"""

import logging
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import psycopg2
from collections import defaultdict, Counter
import re

from .summarization_service import MLSummarizationService
from .background_processor import BackgroundMLProcessor
from .rag_external_services import RAGExternalServicesManager
from .gdelt_rag_service import GDELTRAGService

logger = logging.getLogger(__name__)

class RAGEnhancedService:
    """
    Enhanced RAG service that integrates with ML summarizer for intelligent context retrieval
    """
    
    def __init__(self, db_config: Dict[str, str], ml_service: MLSummarizationService = None, 
                 external_config: Dict[str, str] = None):
        """
        Initialize the Enhanced RAG Service
        
        Args:
            db_config: Database configuration dictionary
            ml_service: ML summarization service instance
            external_config: Configuration for external services (API keys, etc.)
        """
        self.db_config = db_config
        self.ml_service = ml_service or MLSummarizationService()
        
        # Initialize external services
        self.external_services = RAGExternalServicesManager(external_config)
        
        # Initialize GDELT service for timeline and context enhancement
        self.gdelt_service = GDELTRAGService()
        
        # RAG Configuration
        self.config = {
            'max_context_articles': 25,
            'max_context_length': 8000,
            'similarity_threshold': 0.7,
            'max_historical_days': 365,
            'context_types': ['historical', 'related', 'background', 'timeline', 'expert_analysis'],
            'rag_processing_timeout': 300,  # 5 minutes
            'enable_ml_enhancement': True,
            'enable_external_services': True
        }
        
        # Performance tracking
        self.stats = {
            'rag_requests': 0,
            'ml_enhanced_requests': 0,
            'external_service_requests': 0,
            'avg_processing_time': 0.0,
            'success_rate': 0.0
        }
    
    def build_enhanced_context(self, query: str, context_type: str = 'comprehensive',
                              max_articles: int = None, include_ml_analysis: bool = True) -> Dict[str, Any]:
        """
        Build enhanced RAG context with ML-powered analysis
        
        Args:
            query: Search query or topic
            context_type: Type of context to build
            max_articles: Maximum number of articles to include
            include_ml_analysis: Whether to include ML-powered analysis
            
        Returns:
            Dictionary with enhanced context information
        """
        start_time = time.time()
        self.stats['rag_requests'] += 1
        
        try:
            if max_articles is None:
                max_articles = self.config['max_context_articles']
            
            logger.info(f"Building enhanced RAG context for query: {query}")
            
            # Step 1: Retrieve relevant articles
            relevant_articles = self._retrieve_relevant_articles(query, max_articles)
            
            if not relevant_articles:
                return {
                    'query': query,
                    'context_type': context_type,
                    'articles_found': 0,
                    'context_summary': f"No relevant articles found for query: {query}",
                    'ml_enhanced': False,
                    'processing_time': time.time() - start_time,
                    'generated_at': datetime.now().isoformat()
                }
            
            # Step 2: Build base context
            base_context = self._build_base_context(query, relevant_articles, context_type)
            
            # Step 3: ML Enhancement (if enabled)
            if include_ml_analysis and self.config['enable_ml_enhancement']:
                enhanced_context = self._enhance_with_ml(base_context, relevant_articles)
                self.stats['ml_enhanced_requests'] += 1
            else:
                enhanced_context = base_context
            
            # Step 4: Add metadata and statistics
            processing_time = time.time() - start_time
            enhanced_context.update({
                'ml_enhanced': include_ml_analysis and self.config['enable_ml_enhancement'],
                'processing_time': processing_time,
                'generated_at': datetime.now().isoformat(),
                'config_used': self.config
            })
            
            # Update statistics
            self._update_stats(processing_time, True)
            
            # Log the RAG request
            self._log_rag_request(query, context_type, enhanced_context, processing_time)
            
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Error building enhanced RAG context: {e}")
            processing_time = time.time() - start_time
            self._update_stats(processing_time, False)
            return {
                'query': query,
                'context_type': context_type,
                'error': str(e),
                'ml_enhanced': False,
                'processing_time': processing_time,
                'generated_at': datetime.now().isoformat()
            }
    
    def build_comprehensive_research_context(self, query: str, story_keywords: List[str] = None,
                                           include_external: bool = True,
                                           include_internal: bool = True) -> Dict[str, Any]:
        """
        Build comprehensive research context using both internal and external sources
        
        Args:
            query: Research query or topic
            story_keywords: Keywords related to the story
            include_external: Whether to include external services (Wikipedia, NewsAPI, etc.)
            include_internal: Whether to include internal database articles
            
        Returns:
            Dictionary with comprehensive research context
        """
        start_time = time.time()
        self.stats['rag_requests'] += 1
        
        try:
            logger.info(f"Building comprehensive research context for query: {query}")
            
            context = {
                'query': query,
                'story_keywords': story_keywords or [],
                'generated_at': datetime.now().isoformat(),
                'sources': {}
            }
            
            # Internal database context
            if include_internal:
                try:
                    internal_articles = self._retrieve_relevant_articles(query, 20)
                    if internal_articles:
                        context['sources']['internal_database'] = {
                            'articles': internal_articles,
                            'count': len(internal_articles),
                            'summary': self._generate_base_summary(internal_articles, query)
                        }
                except Exception as e:
                    logger.warning(f"Error retrieving internal articles: {e}")
            
            # External services context
            if include_external and self.config['enable_external_services']:
                try:
                    self.stats['external_service_requests'] += 1
                    external_context = self.external_services.gather_comprehensive_context(
                        query, story_keywords, max_results=20
                    )
                    
                    if 'error' not in external_context:
                        context['sources']['external_services'] = external_context
                    else:
                        logger.warning(f"External services error: {external_context['error']}")
                        
                except Exception as e:
                    logger.warning(f"Error gathering external context: {e}")
            
            # ML-enhanced analysis
            if self.config['enable_ml_enhancement']:
                try:
                    # Combine all articles for ML analysis
                    all_articles = []
                    if 'internal_database' in context['sources']:
                        all_articles.extend(context['sources']['internal_database']['articles'])
                    
                    if all_articles:
                        ml_analysis = self._enhance_with_ml({
                            'query': query,
                            'articles': all_articles
                        }, all_articles)
                        
                        if 'ml_analysis' in ml_analysis:
                            context['ml_analysis'] = ml_analysis['ml_analysis']
                        
                        if 'argument_analysis' in ml_analysis:
                            context['argument_analysis'] = ml_analysis['argument_analysis']
                        
                        if 'key_insights' in ml_analysis:
                            context['key_insights'] = ml_analysis['key_insights']
                        
                        self.stats['ml_enhanced_requests'] += 1
                        
                except Exception as e:
                    logger.warning(f"Error in ML enhancement: {e}")
            
            # Generate comprehensive summary
            context['comprehensive_summary'] = self._generate_comprehensive_summary(context)
            
            # Add metadata
            processing_time = time.time() - start_time
            context.update({
                'processing_time': processing_time,
                'sources_used': list(context['sources'].keys()),
                'total_sources': len(context['sources'])
            })
            
            # Update statistics
            self._update_stats(processing_time, True)
            
            return context
            
        except Exception as e:
            logger.error(f"Error building comprehensive research context: {e}")
            processing_time = time.time() - start_time
            self._update_stats(processing_time, False)
            return {
                'query': query,
                'error': str(e),
                'processing_time': processing_time,
                'generated_at': datetime.now().isoformat()
            }
    
    def build_story_dossier_with_rag(self, story_id: str, story_title: str = None,
                                   include_historical: bool = True,
                                   include_related: bool = True,
                                   include_analysis: bool = True) -> Dict[str, Any]:
        """
        Build a comprehensive story dossier with RAG-enhanced context
        
        Args:
            story_id: Story identifier
            story_title: Story title (optional)
            include_historical: Include historical context
            include_related: Include related stories
            include_analysis: Include ML analysis
            
        Returns:
            Dictionary with comprehensive story dossier
        """
        start_time = time.time()
        
        try:
            logger.info(f"Building story dossier with RAG for story: {story_id}")
            
            # Build comprehensive query
            query = f"{story_title or story_id} {story_id}"
            
            # Get story articles
            story_articles = self._get_story_articles(story_id)
            
            dossier = {
                'story_id': story_id,
                'story_title': story_title,
                'generated_at': datetime.now().isoformat(),
                'sections': {}
            }
            
            # Historical Context
            if include_historical:
                historical_context = self.build_enhanced_context(
                    f"historical context {query}",
                    'historical',
                    max_articles=15,
                    include_ml_analysis=include_analysis
                )
                dossier['sections']['historical_context'] = historical_context
            
            # Related Stories
            if include_related:
                related_context = self.build_enhanced_context(
                    f"related stories {query}",
                    'related',
                    max_articles=10,
                    include_ml_analysis=include_analysis
                )
                dossier['sections']['related_stories'] = related_context
            
            # Current Story Analysis
            if story_articles and include_analysis:
                current_analysis = self._analyze_current_story(story_articles, story_title)
                dossier['sections']['current_analysis'] = current_analysis
            
            # Expert Analysis (ML-powered)
            if include_analysis and story_articles:
                expert_analysis = self._generate_expert_analysis(story_articles, story_title)
                dossier['sections']['expert_analysis'] = expert_analysis
            
            # Timeline
            timeline = self._build_story_timeline(story_articles)
            dossier['sections']['timeline'] = timeline
            
            # Key Insights
            insights = self._extract_key_insights(dossier['sections'])
            dossier['key_insights'] = insights
            
            # Summary
            summary = self._generate_dossier_summary(dossier)
            dossier['summary'] = summary
            
            dossier['processing_time'] = time.time() - start_time
            
            return dossier
            
        except Exception as e:
            logger.error(f"Error building story dossier with RAG: {e}")
            return {
                'story_id': story_id,
                'error': str(e),
                'processing_time': time.time() - start_time,
                'generated_at': datetime.now().isoformat()
            }
    
    def _retrieve_relevant_articles(self, query: str, max_articles: int) -> List[Dict[str, Any]]:
        """Retrieve relevant articles using enhanced RAG retrieval"""
        try:
            # Use enhanced retrieval service if available
            try:
                from services.enhanced_rag_retrieval import EnhancedRAGRetrieval
                retrieval_service = EnhancedRAGRetrieval(self.db_config)
                
                # Use async retrieval (wrap in sync if needed)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                articles = loop.run_until_complete(
                    retrieval_service.retrieve_relevant_articles(
                        query=query,
                        max_results=max_articles,
                        use_semantic=True,
                        use_hybrid=True,
                        expand_query=True,
                        rerank=True
                    )
                )
                
                if articles:
                    logger.info(f"Enhanced RAG retrieval found {len(articles)} articles")
                    return articles
            except ImportError:
                logger.warning("Enhanced RAG retrieval not available, falling back to basic search")
            except Exception as e:
                logger.warning(f"Enhanced RAG retrieval failed: {e}, falling back to basic search")
            
            # Fallback to basic keyword search
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Extract keywords from query
            keywords = self._extract_keywords(query)
            logger.info(f"Extracted keywords: {keywords}")
            
            # Simple query first to test
            if not keywords:
                # If no keywords, get recent articles
                query_sql = """
                    SELECT id, title, content, excerpt, summary, source_domain, published_at, url,
                           quality_score, processing_status
                    FROM articles 
                    WHERE quality_score >= 0.3
                    ORDER BY published_at DESC
                    LIMIT %s
                """
                cursor.execute(query_sql, (max_articles,))
            else:
                # Build search query
                keyword_conditions = []
                params = []
                for keyword in keywords:
                    keyword_conditions.append(
                        "(LOWER(title) LIKE %s OR LOWER(content) LIKE %s OR LOWER(excerpt) LIKE %s OR LOWER(summary) LIKE %s)"
                    )
                    pattern = f'%{keyword.lower()}%'
                    params.extend([pattern, pattern, pattern, pattern])
                
                keyword_query = " OR ".join(keyword_conditions)
                
                query_sql = f"""
                    SELECT id, title, content, excerpt, summary, source_domain, published_at, url,
                           quality_score, processing_status
                    FROM articles 
                    WHERE ({keyword_query})
                    AND quality_score >= 0.3
                    ORDER BY 
                        quality_score DESC,
                        published_at DESC
                    LIMIT %s
                """
                
                params.append(max_articles)
                logger.info(f"Executing query with {len(keywords)} keywords")
                cursor.execute(query_sql, params)
            
            articles = []
            rows = cursor.fetchall()
            logger.info(f"Found {len(rows)} rows")
            
            if not rows:
                logger.info("No rows returned from query")
                conn.close()
                return articles
            
            for i, row in enumerate(rows):
                try:
                    if len(row) < 10:
                        logger.warning(f"Row {i} has only {len(row)} columns, expected 10")
                        continue
                        
                    articles.append({
                        'id': row[0],
                        'title': row[1] or "",
                        'content': row[2] or "",
                        'excerpt': row[3] or "",
                        'summary': row[4] or "",
                        'source': row[5] or "",
                        'published_at': row[6].isoformat() if row[6] else None,
                        'url': row[7] or "",
                        'quality_score': float(row[8]) if row[8] else 0.0,
                        'ml_processed': row[9] == 'completed' if row[9] else False,
                        'relevance_score': 0.5,
                        'retrieval_method': 'keyword'
                    })
                except Exception as e:
                    logger.warning(f"Error processing article row {i}: {e}")
                    continue
            
            conn.close()
            logger.info(f"Successfully retrieved {len(articles)} articles")
            return articles
            
        except Exception as e:
            logger.error(f"Error retrieving relevant articles: {e}")
            return []
    
    def _build_base_context(self, query: str, articles: List[Dict[str, Any]], 
                          context_type: str) -> Dict[str, Any]:
        """Build base context from articles"""
        try:
            # Extract key information
            key_entities = self._extract_entities(articles)
            key_themes = self._extract_themes(articles)
            timeline = self._build_timeline(articles)
            sources = self._analyze_sources(articles)
            
            # Generate base summary
            base_summary = self._generate_base_summary(articles, query)
            
            return {
                'query': query,
                'context_type': context_type,
                'articles_found': len(articles),
                'base_summary': base_summary,
                'key_entities': key_entities,
                'key_themes': key_themes,
                'timeline': timeline,
                'sources': sources,
                'articles': articles[:10]  # Limit for response size
            }
            
        except Exception as e:
            logger.error(f"Error building base context: {e}")
            return {'error': str(e)}
    
    def _enhance_with_ml(self, base_context: Dict[str, Any], 
                        articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance context with ML analysis"""
        try:
            # Prepare content for ML analysis
            ml_articles = [a for a in articles if a.get('ml_processed', False)]
            non_ml_articles = [a for a in articles if not a.get('ml_processed', False)]
            
            enhanced_context = base_context.copy()
            
            # Use existing ML data for processed articles
            if ml_articles:
                ml_insights = self._aggregate_ml_insights(ml_articles)
                enhanced_context['ml_insights'] = ml_insights
            
            # Process non-ML articles if needed
            if non_ml_articles and len(non_ml_articles) <= 5:  # Limit to avoid timeout
                try:
                    # Create combined content for analysis
                    combined_content = self._combine_article_content(non_ml_articles)
                    
                    # Generate ML analysis
                    ml_analysis = self.ml_service.generate_summary(
                        combined_content, 
                        f"Context Analysis: {base_context['query']}"
                    )
                    
                    if ml_analysis.get('status') == 'success':
                        enhanced_context['ml_analysis'] = {
                            'summary': ml_analysis.get('summary', ''),
                            'model_used': ml_analysis.get('model_used', ''),
                            'generated_at': ml_analysis.get('generated_at', ''),
                            'content_length': ml_analysis.get('content_length', 0)
                        }
                except Exception as e:
                    logger.warning(f"ML analysis failed for non-processed articles: {e}")
            
            # Generate argument analysis if controversial
            if self._is_controversial_topic(base_context['query'], articles):
                try:
                    controversial_content = self._combine_article_content(articles[:3])
                    argument_analysis = self.ml_service.analyze_arguments(
                        controversial_content,
                        f"Argument Analysis: {base_context['query']}"
                    )
                    
                    if argument_analysis.get('status') == 'success':
                        enhanced_context['argument_analysis'] = argument_analysis
                except Exception as e:
                    logger.warning(f"Argument analysis failed: {e}")
            
            # Generate key insights
            insights = self._generate_ml_insights(enhanced_context, articles)
            enhanced_context['key_insights'] = insights
            
            return enhanced_context
            
        except Exception as e:
            logger.error(f"Error enhancing with ML: {e}")
            return base_context  # Return base context if ML enhancement fails
    
    def _aggregate_ml_insights(self, ml_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate insights from ML-processed articles"""
        try:
            insights = {
                'total_processed': len(ml_articles),
                'models_used': set(),
                'key_points': [],
                'sentiments': [],
                'argument_analyses': []
            }
            
            for article in ml_articles:
                ml_data = article.get('ml_data', {})
                
                # Collect model information
                if article.get('ml_model_used'):
                    insights['models_used'].add(article['ml_model_used'])
                
                # Aggregate key points
                if 'key_points' in ml_data:
                    insights['key_points'].extend(ml_data['key_points'])
                
                # Aggregate sentiments
                if 'sentiment' in ml_data:
                    insights['sentiments'].append(ml_data['sentiment'])
                
                # Aggregate argument analyses
                if 'argument_analysis' in ml_data:
                    insights['argument_analyses'].append(ml_data['argument_analysis'])
            
            # Convert set to list for JSON serialization
            insights['models_used'] = list(insights['models_used'])
            
            # Limit aggregated data
            insights['key_points'] = insights['key_points'][:20]
            insights['argument_analyses'] = insights['argument_analyses'][:5]
            
            return insights
            
        except Exception as e:
            logger.error(f"Error aggregating ML insights: {e}")
            return {}
    
    def _generate_expert_analysis(self, articles: List[Dict[str, Any]], 
                                story_title: str = None) -> Dict[str, Any]:
        """Generate expert analysis using ML"""
        try:
            if not articles:
                return {'error': 'No articles provided for analysis'}
            
            # Combine content from top articles
            top_articles = sorted(articles, key=lambda x: x.get('quality_score', 0), reverse=True)[:3]
            combined_content = self._combine_article_content(top_articles)
            
            # Generate comprehensive analysis
            analysis_prompt = f"""
            Provide a comprehensive expert analysis of the following news story: {story_title or 'Current Story'}
            
            Consider:
            1. Key developments and their significance
            2. Historical context and precedents
            3. Stakeholder perspectives and implications
            4. Future outlook and potential outcomes
            5. Expert opinions and analysis
            
            Content to analyze:
            {combined_content}
            """
            
            expert_analysis = self.ml_service.generate_summary(
                analysis_prompt,
                "Expert Analysis Request"
            )
            
            return {
                'analysis': expert_analysis.get('summary', ''),
                'model_used': expert_analysis.get('model_used', ''),
                'articles_analyzed': len(top_articles),
                'generated_at': expert_analysis.get('generated_at', ''),
                'status': expert_analysis.get('status', 'failed')
            }
            
        except Exception as e:
            logger.error(f"Error generating expert analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_current_story(self, articles: List[Dict[str, Any]], 
                             story_title: str = None) -> Dict[str, Any]:
        """Analyze current story developments"""
        try:
            if not articles:
                return {'error': 'No articles provided'}
            
            # Sort by recency and quality
            sorted_articles = sorted(
                articles, 
                key=lambda x: (x.get('published_at', ''), x.get('quality_score', 0)), 
                reverse=True
            )
            
            # Extract key developments
            developments = []
            for article in sorted_articles[:5]:
                if article.get('title'):
                    developments.append({
                        'title': article['title'],
                        'date': article.get('published_at'),
                        'source': article.get('source'),
                        'quality_score': article.get('quality_score', 0)
                    })
            
            # Analyze trends
            trends = self._analyze_trends(sorted_articles)
            
            return {
                'total_articles': len(articles),
                'recent_developments': developments,
                'trends': trends,
                'story_title': story_title,
                'analysis_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing current story: {e}")
            return {'error': str(e)}
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query"""
        try:
            # Simple keyword extraction
            words = re.findall(r'\b\w+\b', query.lower())
            # Filter out common words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            keywords = [word for word in words if word not in stop_words and len(word) > 2]
            return keywords[:10]  # Limit to 10 keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    def _extract_entities(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key entities from articles using enhanced extraction"""
        try:
            # Use enhanced entity extractor if available
            try:
                from services.enhanced_entity_extractor import EnhancedEntityExtractor
                extractor = EnhancedEntityExtractor()
                
                all_entities = {
                    'people': [],
                    'organizations': [],
                    'locations': [],
                    'topics': []
                }
                
                # Extract from all articles
                for article in articles[:10]:  # Limit to 10 articles for performance
                    text = f"{article.get('title', '')} {article.get('excerpt', '')} {article.get('summary', '')}"
                    entities = extractor.extract_entities(text)
                    
                    for entity_type in all_entities:
                        all_entities[entity_type].extend(entities.get(entity_type, []))
                
                # Get top entities by frequency
                entity_list = []
                for entity_type, entity_list_type in all_entities.items():
                    entity_counter = Counter(entity_list_type)
                    top_entities = [entity for entity, count in entity_counter.most_common(5)]
                    entity_list.extend(top_entities)
                
                return entity_list[:20]  # Limit to 20 total entities
                
            except ImportError:
                logger.warning("Enhanced entity extractor not available, using basic extraction")
            except Exception as e:
                logger.warning(f"Enhanced entity extraction failed: {e}, using basic extraction")
            
            # Fallback to basic extraction
            entities = set()
            for article in articles:
                title = article.get('title', '')
                # Simple entity extraction based on capitalization
                words = re.findall(r'\b[A-Z][a-z]+\b', title)
                entities.update(words)
            
            return list(entities)[:20]  # Limit to 20 entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return []
    
    def _extract_themes(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract key themes from articles"""
        try:
            word_freq = Counter()
            for article in articles:
                title = article.get('title', '').lower()
                content = article.get('content', '').lower()
                
                # Extract meaningful words
                words = re.findall(r'\b\w{4,}\b', title + ' ' + content)
                for word in words:
                    if word not in {'this', 'that', 'with', 'from', 'they', 'have', 'been', 'will', 'were', 'said', 'news', 'report'}:
                        word_freq[word] += 1
            
            return [word for word, count in word_freq.most_common(15)]
            
        except Exception as e:
            logger.error(f"Error extracting themes: {e}")
            return []
    
    def _build_timeline(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build timeline from articles"""
        try:
            timeline = []
            for article in articles:
                if article.get('published_at'):
                    timeline.append({
                        'date': article['published_at'],
                        'title': article.get('title', ''),
                        'source': article.get('source', ''),
                        'url': article.get('url', '')
                    })
            
            # Sort by date
            timeline.sort(key=lambda x: x['date'], reverse=True)
            return timeline[:20]  # Limit to 20 timeline entries
            
        except Exception as e:
            logger.error(f"Error building timeline: {e}")
            return []
    
    def _analyze_sources(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze source distribution"""
        try:
            source_count = Counter()
            for article in articles:
                source = article.get('source', 'Unknown')
                source_count[source] += 1
            
            return {
                'total_sources': len(source_count),
                'top_sources': dict(source_count.most_common(10)),
                'source_diversity': len(source_count) / len(articles) if articles else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sources: {e}")
            return {}
    
    def _generate_base_summary(self, articles: List[Dict[str, Any]], query: str) -> str:
        """Generate base summary without ML"""
        try:
            if not articles:
                return f"No articles found for query: {query}"
            
            # Use existing summaries if available
            summaries = []
            for article in articles:
                if article.get('summary'):
                    summaries.append(article['summary'])
                elif article.get('title'):
                    summaries.append(article['title'])
            
            if summaries:
                return f"Found {len(articles)} articles. Key topics include: {', '.join(summaries[:3])}"
            else:
                return f"Found {len(articles)} articles related to: {query}"
                
        except Exception as e:
            logger.error(f"Error generating base summary: {e}")
            return f"Summary generation failed for query: {query}"
    
    def _combine_article_content(self, articles: List[Dict[str, Any]]) -> str:
        """Combine article content for ML processing"""
        try:
            combined = []
            for article in articles[:3]:  # Limit to 3 articles to avoid token limits
                title = article.get('title', '')
                content = article.get('content', '')
                summary = article.get('summary', '')
                
                if title:
                    combined.append(f"Title: {title}")
                if summary:
                    combined.append(f"Summary: {summary}")
                elif content:
                    # Truncate content to avoid token limits
                    truncated_content = content[:1000] + '...' if len(content) > 1000 else content
                    combined.append(f"Content: {truncated_content}")
            
            return '\n\n'.join(combined)
            
        except Exception as e:
            logger.error(f"Error combining article content: {e}")
            return ""
    
    def _is_controversial_topic(self, query: str, articles: List[Dict[str, Any]]) -> bool:
        """Determine if topic is controversial"""
        try:
            controversial_keywords = [
                'controversy', 'debate', 'dispute', 'conflict', 'crisis',
                'scandal', 'protest', 'strike', 'lawsuit', 'investigation'
            ]
            
            query_lower = query.lower()
            if any(keyword in query_lower for keyword in controversial_keywords):
                return True
            
            # Check article titles for controversial keywords
            for article in articles[:5]:
                title = article.get('title', '').lower()
                if any(keyword in title for keyword in controversial_keywords):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if topic is controversial: {e}")
            return False
    
    def _generate_ml_insights(self, enhanced_context: Dict[str, Any], 
                            articles: List[Dict[str, Any]]) -> List[str]:
        """Generate key insights from ML analysis"""
        try:
            insights = []
            
            # Article count insight
            insights.append(f"Analyzed {len(articles)} articles with {enhanced_context.get('articles_found', 0)} total matches")
            
            # ML processing insight
            ml_processed = sum(1 for a in articles if a.get('ml_processed', False))
            if ml_processed > 0:
                insights.append(f"{ml_processed} articles have been ML-processed for enhanced analysis")
            
            # Source diversity insight
            sources = enhanced_context.get('sources', {})
            if sources.get('source_diversity', 0) > 0.5:
                insights.append(f"High source diversity with {sources.get('total_sources', 0)} different sources")
            
            # Timeline insight
            timeline = enhanced_context.get('timeline', [])
            if len(timeline) > 1:
                insights.append(f"Story spans {len(timeline)} articles over time")
            
            # Controversy insight
            if 'argument_analysis' in enhanced_context:
                insights.append("Controversial topic with multiple perspectives identified")
            
            return insights[:5]  # Limit to 5 insights
            
        except Exception as e:
            logger.error(f"Error generating ML insights: {e}")
            return []
    
    def _get_story_articles(self, story_id: str) -> List[Dict[str, Any]]:
        """Get articles for a specific story"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Search for articles related to story
            cursor.execute("""
                SELECT id, title, content, summary, source, published_at, category, url,
                       quality_score, processing_status
                FROM articles 
                WHERE (LOWER(title) LIKE %s OR LOWER(content) LIKE %s)
                ORDER BY published_at DESC
                LIMIT 20
            """, (f'%{story_id.lower()}%', f'%{story_id.lower()}%'))
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1] or "",
                    'content': row[2] or "",
                    'summary': row[3] or "",
                    'source': row[4] or "",
                    'published_at': row[5].isoformat() if row[5] else None,
                    'category': row[6] or "",
                    'url': row[7] or "",
                    'ml_data': {},  # Empty for now
                    'quality_score': float(row[8]) if row[8] else 0.0,
                    'ml_processed': row[9] == 'completed' if row[9] else False
                })
            
            conn.close()
            return articles
            
        except Exception as e:
            logger.error(f"Error getting story articles: {e}")
            return []
    
    def _build_story_timeline(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build timeline for story articles"""
        try:
            timeline = []
            for article in articles:
                if article.get('published_at'):
                    timeline.append({
                        'date': article['published_at'],
                        'title': article.get('title', ''),
                        'source': article.get('source', ''),
                        'summary': article.get('summary', '')[:200] + '...' if len(article.get('summary', '')) > 200 else article.get('summary', ''),
                        'url': article.get('url', '')
                    })
            
            # Sort by date
            timeline.sort(key=lambda x: x['date'])
            return timeline
            
        except Exception as e:
            logger.error(f"Error building story timeline: {e}")
            return []
    
    def _extract_key_insights(self, sections: Dict[str, Any]) -> List[str]:
        """Extract key insights from dossier sections"""
        try:
            insights = []
            
            # Historical insights
            if 'historical_context' in sections:
                hist = sections['historical_context']
                if hist.get('articles_found', 0) > 0:
                    insights.append(f"Historical context: {hist.get('articles_found', 0)} related articles found")
            
            # Related story insights
            if 'related_stories' in sections:
                related = sections['related_stories']
                if related.get('articles_found', 0) > 0:
                    insights.append(f"Related stories: {related.get('articles_found', 0)} connected articles identified")
            
            # Current analysis insights
            if 'current_analysis' in sections:
                current = sections['current_analysis']
                if current.get('total_articles', 0) > 0:
                    insights.append(f"Current developments: {current.get('total_articles', 0)} recent articles analyzed")
            
            # Expert analysis insights
            if 'expert_analysis' in sections:
                expert = sections['expert_analysis']
                if expert.get('status') == 'success':
                    insights.append("Expert analysis: Comprehensive ML-powered analysis completed")
            
            return insights[:5]  # Limit to 5 insights
            
        except Exception as e:
            logger.error(f"Error extracting key insights: {e}")
            return []
    
    def _generate_dossier_summary(self, dossier: Dict[str, Any]) -> str:
        """Generate summary of the dossier"""
        try:
            story_title = dossier.get('story_title', dossier.get('story_id', 'Unknown Story'))
            sections = dossier.get('sections', {})
            
            summary_parts = [f"Comprehensive dossier for: {story_title}"]
            
            # Add section summaries
            if 'historical_context' in sections:
                hist = sections['historical_context']
                summary_parts.append(f"Historical context: {hist.get('articles_found', 0)} articles")
            
            if 'related_stories' in sections:
                related = sections['related_stories']
                summary_parts.append(f"Related stories: {related.get('articles_found', 0)} articles")
            
            if 'expert_analysis' in sections:
                summary_parts.append("Expert analysis: ML-enhanced analysis included")
            
            summary_parts.append(f"Generated: {dossier.get('generated_at', 'Unknown time')}")
            
            return '. '.join(summary_parts) + '.'
            
        except Exception as e:
            logger.error(f"Error generating dossier summary: {e}")
            return f"Dossier generated for {dossier.get('story_id', 'Unknown Story')}"
    
    def _analyze_trends(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends in articles"""
        try:
            if not articles:
                return {}
            
            # Analyze by date
            dates = [a.get('published_at') for a in articles if a.get('published_at')]
            if dates:
                dates.sort()
                trend_period = f"{dates[0]} to {dates[-1]}"
            else:
                trend_period = "Unknown period"
            
            # Analyze by source
            sources = Counter(a.get('source', 'Unknown') for a in articles)
            
            # Analyze by quality
            quality_scores = [a.get('quality_score', 0) for a in articles if a.get('quality_score')]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            return {
                'period': trend_period,
                'article_count': len(articles),
                'top_sources': dict(sources.most_common(5)),
                'average_quality': round(avg_quality, 2),
                'quality_trend': 'high' if avg_quality > 0.7 else 'medium' if avg_quality > 0.4 else 'low'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {}
    
    def _log_rag_request(self, query: str, context_type: str, 
                        context: Dict[str, Any], processing_time: float) -> None:
        """Log RAG request for analytics"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO rag_context_requests 
                (article_id, context_type, context_description, priority, status, 
                 context_data, sources_used, confidence_score, requested_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                None,  # article_id
                context_type,
                f"RAG request: {query}",
                1,  # priority
                'completed',
                json.dumps(context),  # context_data
                [],  # sources_used
                0.9,  # confidence_score
                datetime.now() - timedelta(seconds=processing_time),
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging RAG request: {e}")
    
    def _update_stats(self, processing_time: float, success: bool) -> None:
        """Update performance statistics"""
        try:
            if success:
                # Update average processing time
                total_requests = self.stats['rag_requests']
                current_avg = self.stats['avg_processing_time']
                self.stats['avg_processing_time'] = ((current_avg * (total_requests - 1)) + processing_time) / total_requests
                
                # Update success rate
                successful_requests = self.stats.get('successful_requests', 0) + 1
                self.stats['successful_requests'] = successful_requests
                self.stats['success_rate'] = successful_requests / total_requests
            
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def _generate_comprehensive_summary(self, context: Dict[str, Any]) -> str:
        """Generate comprehensive summary of all gathered context"""
        try:
            query = context.get('query', 'Unknown query')
            sources = context.get('sources', {})
            
            summary_parts = [f"Comprehensive research context for: {query}"]
            
            # Internal database summary
            if 'internal_database' in sources:
                internal = sources['internal_database']
                summary_parts.append(f"Internal database: {internal['count']} articles found")
            
            # External services summary
            if 'external_services' in sources:
                external = sources['external_services']
                external_sources = external.get('sources', {})
                
                if 'wikipedia' in external_sources:
                    wiki_count = external_sources['wikipedia']['count']
                    summary_parts.append(f"Wikipedia: {wiki_count} articles")
                
                if 'newsapi' in external_sources:
                    news_count = external_sources['newsapi']['count']
                    summary_parts.append(f"Recent news: {news_count} articles")
                
                if 'knowledge_graph' in external_sources:
                    kg_count = external_sources['knowledge_graph']['count']
                    summary_parts.append(f"Knowledge Graph: {kg_count} entities")
            
            # Timeline analysis summary
            if 'external_services' in sources:
                external = sources['external_services']
                if 'timeline_analysis' in external:
                    timeline = external['timeline_analysis']
                    summary_parts.append(f"Timeline: {timeline.get('total_events', 0)} events analyzed")
            
            # Entity analysis summary
            if 'external_services' in sources:
                external = sources['external_services']
                if 'entity_analysis' in external:
                    entities = external['entity_analysis']['entities']
                    total_entities = sum(len(entities[cat]) for cat in entities)
                    summary_parts.append(f"Entities: {total_entities} identified")
            
            # ML analysis summary
            if 'ml_analysis' in context:
                summary_parts.append("ML-enhanced analysis completed")
            
            # Processing time
            processing_time = context.get('processing_time', 0)
            summary_parts.append(f"Processing time: {processing_time:.2f} seconds")
            
            return ". ".join(summary_parts) + "."
            
        except Exception as e:
            logger.error(f"Error generating comprehensive summary: {e}")
            return f"Comprehensive research context generated for: {context.get('query', 'Unknown query')}"
    
    def get_rag_statistics(self) -> Dict[str, Any]:
        """Get RAG service statistics"""
        return {
            'total_requests': self.stats['rag_requests'],
            'ml_enhanced_requests': self.stats['ml_enhanced_requests'],
            'external_service_requests': self.stats['external_service_requests'],
            'avg_processing_time': self.stats['avg_processing_time'],
            'success_rate': self.stats['success_rate'],
            'config': self.config
        }
    
    def enhance_article_with_gdelt_timeline(self, article_id: int, keywords: List[str] = None) -> Dict[str, Any]:
        """
        Enhance an article with GDELT timeline and context data
        
        Args:
            article_id: ID of the article to enhance
            keywords: Optional keywords to use for GDELT search
            
        Returns:
            Dict containing enhanced article data with GDELT context
        """
        try:
            start_time = time.time()
            
            # Get article data
            article_data = self._get_article_data(article_id)
            if not article_data:
                return {"error": f"Article {article_id} not found"}
            
            # Extract keywords if not provided
            if not keywords:
                keywords = self._extract_article_keywords(article_data)
            
            # Get GDELT timeline data
            gdelt_timeline = self.gdelt_service.get_event_timeline(
                query=" ".join(keywords[:5]), 
                days_back=30
            )
            
            # Get background context
            background_context = self.gdelt_service.get_background_context(
                keywords=keywords,
                article_date=article_data.get('published_at', '')
            )
            
            # Extract entities and get entity context
            entities = self._extract_entities_from_article(article_data)
            entity_contexts = {}
            
            for entity in entities[:3]:  # Limit to top 3 entities
                entity_context = self.gdelt_service.get_entity_context(
                    entity=entity,
                    entity_type="person"  # Default to person, could be enhanced
                )
                entity_contexts[entity] = entity_context
            
            # Combine all GDELT data
            gdelt_enhancement = {
                "article_id": article_id,
                "keywords": keywords,
                "timeline": gdelt_timeline,
                "background_context": background_context,
                "entity_contexts": entity_contexts,
                "enhancement_timestamp": datetime.now().isoformat(),
                "processing_time": time.time() - start_time
            }
            
            # Store enhancement in database
            self._store_gdelt_enhancement(article_id, gdelt_enhancement)
            
            # Update article with RAG enhancement flag
            self._update_article_rag_status(article_id, "gdelt_enhanced")
            
            logger.info(f"Enhanced article {article_id} with GDELT timeline data in {gdelt_enhancement['processing_time']:.2f}s")
            
            return gdelt_enhancement
            
        except Exception as e:
            logger.error(f"Error enhancing article {article_id} with GDELT: {e}")
            return {"error": f"Error enhancing article with GDELT: {str(e)}"}
    
    def _get_article_data(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article data from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, content, summary, url, source, published_at, 
                       category, language, quality_score, processing_status, ml_data
                FROM articles 
                WHERE id = %s
            """, (article_id,))
            
            result = cursor.fetchone()
            if result:
                columns = [desc[0] for desc in cursor.description]
                article_data = dict(zip(columns, result))
                return article_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting article data: {e}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _extract_article_keywords(self, article_data: Dict[str, Any]) -> List[str]:
        """Extract keywords from article data"""
        # Simple keyword extraction - could be enhanced with NLP
        text = f"{article_data.get('title', '')} {article_data.get('content', '')}"
        
        # Remove common words and extract meaningful terms
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them'}
        
        # Extract words (simple approach)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        keywords = [word for word in words if word not in common_words]
        
        # Count frequency and return top keywords
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]
    
    def _extract_entities_from_article(self, article_data: Dict[str, Any]) -> List[str]:
        """Extract entities from article data"""
        # Simple entity extraction - could be enhanced with NER
        text = f"{article_data.get('title', '')} {article_data.get('content', '')}"
        
        # Look for capitalized words (simple approach)
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        
        # Remove common words and return unique entities
        common_words = {'The', 'This', 'That', 'These', 'Those', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For', 'Of', 'With', 'By'}
        entities = [entity for entity in entities if entity not in common_words]
        
        return list(set(entities))[:5]  # Return top 5 unique entities
    
    def _store_gdelt_enhancement(self, article_id: int, enhancement_data: Dict[str, Any]) -> bool:
        """Store GDELT enhancement data in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Update article with GDELT enhancement data
            cursor.execute("""
                UPDATE articles 
                SET ml_data = COALESCE(ml_data, '{}'::jsonb) || %s::jsonb,
                    rag_keep_longer = TRUE,
                    rag_context_needed = FALSE,
                    updated_at = NOW()
                WHERE id = %s
            """, (json.dumps({"gdelt_enhancement": enhancement_data}), article_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing GDELT enhancement: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _update_article_rag_status(self, article_id: int, status: str) -> bool:
        """Update article RAG processing status"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE articles 
                SET processing_status = %s,
                    rag_keep_longer = TRUE,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, article_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating article RAG status: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
