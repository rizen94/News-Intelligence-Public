"""
External Services Integration for Enhanced RAG
Integrates Wikipedia, NewsAPI, Knowledge Graph, and other services for rich context
"""

import logging
import requests
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import re
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)

class WikipediaService:
    """Wikipedia API integration for historical context and background information"""
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1"
        self.search_url = "https://en.wikipedia.org/w/api.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsIntelligenceSystem/1.0 (https://newsintelligence.com)'
        })
    
    def search_articles(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Wikipedia for relevant articles"""
        try:
            params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srlimit': limit,
                'srprop': 'snippet|timestamp'
            }
            
            response = self.session.get(self.search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for item in data.get('query', {}).get('search', []):
                articles.append({
                    'title': item.get('title', ''),
                    'snippet': item.get('snippet', ''),
                    'timestamp': item.get('timestamp', ''),
                    'pageid': item.get('pageid', ''),
                    'url': f"https://en.wikipedia.org/wiki/{quote(item.get('title', ''))}"
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"Error searching Wikipedia: {e}")
            return []
    
    def get_article_summary(self, title: str) -> Optional[Dict[str, Any]]:
        """Get article summary from Wikipedia"""
        try:
            url = f"{self.base_url}/page/summary/{quote(title)}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'title': data.get('title', ''),
                'extract': data.get('extract', ''),
                'description': data.get('description', ''),
                'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                'thumbnail': data.get('thumbnail', {}).get('source', '') if data.get('thumbnail') else '',
                'coordinates': data.get('coordinates', {}),
                'type': data.get('type', '')
            }
            
        except Exception as e:
            logger.error(f"Error getting Wikipedia article: {e}")
            return None
    
    def get_related_articles(self, title: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get related articles from Wikipedia"""
        try:
            params = {
                'action': 'query',
                'format': 'json',
                'prop': 'links',
                'titles': title,
                'pllimit': limit,
                'plnamespace': 0
            }
            
            response = self.session.get(self.search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            pages = data.get('query', {}).get('pages', {})
            links = []
            
            for page_id, page_data in pages.items():
                for link in page_data.get('links', []):
                    links.append({
                        'title': link.get('title', ''),
                        'url': f"https://en.wikipedia.org/wiki/{quote(link.get('title', ''))}"
                    })
            
            return links[:limit]
            
        except Exception as e:
            logger.error(f"Error getting related Wikipedia articles: {e}")
            return []

class NewsAPIService:
    """NewsAPI integration for recent related articles and trending topics"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "your_newsapi_key_here"  # Replace with actual key
        self.base_url = "https://newsapi.org/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': self.api_key,
            'User-Agent': 'NewsIntelligenceSystem/1.0'
        })
    
    def search_articles(self, query: str, days: int = 7, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for recent articles related to query"""
        try:
            if not self.api_key or self.api_key == "your_newsapi_key_here":
                logger.warning("NewsAPI key not configured")
                return []
            
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(days=days)
            
            params = {
                'q': query,
                'from': from_date.strftime('%Y-%m-%d'),
                'to': to_date.strftime('%Y-%m-%d'),
                'sortBy': 'relevancy',
                'pageSize': min(limit, 100),
                'language': 'en'
            }
            
            response = self.session.get(f"{self.base_url}/everything", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for item in data.get('articles', []):
                articles.append({
                    'title': item.get('title', ''),
                    'description': item.get('description', ''),
                    'content': item.get('content', ''),
                    'url': item.get('url', ''),
                    'source': item.get('source', {}).get('name', ''),
                    'published_at': item.get('publishedAt', ''),
                    'url_to_image': item.get('urlToImage', ''),
                    'author': item.get('author', '')
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"Error searching NewsAPI: {e}")
            return []
    
    def get_trending_topics(self, category: str = 'general', limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending topics from NewsAPI"""
        try:
            if not self.api_key or self.api_key == "your_newsapi_key_here":
                logger.warning("NewsAPI key not configured")
                return []
            
            params = {
                'category': category,
                'country': 'us',
                'pageSize': min(limit, 100)
            }
            
            response = self.session.get(f"{self.base_url}/top-headlines", params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            topics = []
            for article in data.get('articles', []):
                topics.append({
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', ''),
                    'published_at': article.get('publishedAt', ''),
                    'url': article.get('url', '')
                })
            
            return topics
            
        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return []

class KnowledgeGraphService:
    """Google Knowledge Graph API integration for entity relationships"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "your_kg_api_key_here"  # Replace with actual key
        self.base_url = "https://kgsearch.googleapis.com/v1/entities:search"
        self.session = requests.Session()
    
    def search_entities(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for entities in Knowledge Graph"""
        try:
            if not self.api_key or self.api_key == "your_kg_api_key_here":
                logger.warning("Knowledge Graph API key not configured")
                return []
            
            params = {
                'query': query,
                'limit': min(limit, 20),
                'indent': True,
                'key': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            entities = []
            for item in data.get('itemListElement', []):
                entity = item.get('result', {})
                entities.append({
                    'name': entity.get('name', ''),
                    'description': entity.get('description', ''),
                    'detailed_description': entity.get('detailedDescription', {}).get('articleBody', ''),
                    'url': entity.get('detailedDescription', {}).get('url', ''),
                    'type': entity.get('@type', []),
                    'image': entity.get('image', {}).get('contentUrl', '') if entity.get('image') else '',
                    'score': item.get('resultScore', 0)
                })
            
            return entities
            
        except Exception as e:
            logger.error(f"Error searching Knowledge Graph: {e}")
            return []

class SemanticSearchService:
    """Semantic search using sentence transformers for better article matching"""
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load sentence transformer model"""
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight model for better performance
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not available. Install with: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"Error loading sentence transformer model: {e}")
    
    def compute_similarity(self, query: str, articles: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        """Compute semantic similarity between query and articles"""
        try:
            if not self.model:
                # Fallback to simple keyword matching
                return self._fallback_similarity(query, articles)
            
            # Prepare texts for encoding
            query_text = query.lower()
            article_texts = []
            
            for article in articles:
                text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}"
                article_texts.append(text.lower())
            
            # Encode query and articles
            query_embedding = self.model.encode([query_text])
            article_embeddings = self.model.encode(article_texts)
            
            # Compute similarities
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(query_embedding, article_embeddings)[0]
            
            # Pair articles with similarities
            results = list(zip(articles, similarities))
            results.sort(key=lambda x: x[1], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Error computing semantic similarity: {e}")
            return self._fallback_similarity(query, articles)
    
    def _fallback_similarity(self, query: str, articles: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        """Fallback similarity using keyword matching"""
        query_words = set(query.lower().split())
        results = []
        
        for article in articles:
            text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}"
            article_words = set(text.lower().split())
            
            # Simple Jaccard similarity
            intersection = len(query_words.intersection(article_words))
            union = len(query_words.union(article_words))
            similarity = intersection / union if union > 0 else 0
            
            results.append((article, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results

class TimelineAnalysisService:
    """Timeline analysis for story evolution tracking"""
    
    def __init__(self):
        self.date_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
            r'\b\w+ \d{1,2}, \d{4}\b',  # Month DD, YYYY
            r'\b\d{1,2} \w+ \d{4}\b'  # DD Month YYYY
        ]
    
    def extract_timeline_events(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract timeline events from articles"""
        try:
            events = []
            
            for article in articles:
                # Extract dates from content
                content = f"{article.get('title', '')} {article.get('content', '')}"
                dates = self._extract_dates(content)
                
                # Create timeline event
                event = {
                    'article_id': article.get('id'),
                    'title': article.get('title', ''),
                    'published_date': article.get('published_date'),
                    'extracted_dates': dates,
                    'source': article.get('source', ''),
                    'url': article.get('url', ''),
                    'summary': article.get('summary', '')[:200] + '...' if len(article.get('summary', '')) > 200 else article.get('summary', '')
                }
                
                events.append(event)
            
            # Sort by published date
            events.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            return events
            
        except Exception as e:
            logger.error(f"Error extracting timeline events: {e}")
            return []
    
    def _extract_dates(self, text: str) -> List[str]:
        """Extract dates from text using regex patterns"""
        dates = []
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)
        return list(set(dates))  # Remove duplicates
    
    def build_story_timeline(self, articles: List[Dict[str, Any]], story_keywords: List[str]) -> Dict[str, Any]:
        """Build comprehensive timeline for a story"""
        try:
            events = self.extract_timeline_events(articles)
            
            # Group events by time periods
            timeline = {
                'total_events': len(events),
                'time_periods': self._group_by_time_periods(events),
                'key_milestones': self._identify_milestones(events, story_keywords),
                'evolution_phases': self._identify_evolution_phases(events),
                'events': events
            }
            
            return timeline
            
        except Exception as e:
            logger.error(f"Error building story timeline: {e}")
            return {}
    
    def _group_by_time_periods(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group events by time periods"""
        periods = {
            'last_24h': [],
            'last_week': [],
            'last_month': [],
            'older': []
        }
        
        now = datetime.now()
        
        for event in events:
            pub_date = event.get('published_date')
            if not pub_date:
                periods['older'].append(event)
                continue
            
            try:
                event_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                time_diff = now - event_date
                
                if time_diff.days == 0:
                    periods['last_24h'].append(event)
                elif time_diff.days <= 7:
                    periods['last_week'].append(event)
                elif time_diff.days <= 30:
                    periods['last_month'].append(event)
                else:
                    periods['older'].append(event)
            except:
                periods['older'].append(event)
        
        return periods
    
    def _identify_milestones(self, events: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """Identify key milestones in the story"""
        milestones = []
        
        milestone_keywords = [
            'breakthrough', 'announcement', 'launch', 'release', 'agreement',
            'deal', 'merger', 'acquisition', 'crisis', 'scandal', 'investigation'
        ]
        
        for event in events:
            title_lower = event.get('title', '').lower()
            if any(keyword in title_lower for keyword in milestone_keywords + keywords):
                milestones.append(event)
        
        return milestones[:10]  # Limit to 10 milestones
    
    def _identify_evolution_phases(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify evolution phases of the story"""
        phases = []
        
        if len(events) >= 10:
            phases = [
                {'name': 'Initial Development', 'events': events[-10:-7]},
                {'name': 'Growth Phase', 'events': events[-7:-3]},
                {'name': 'Current Phase', 'events': events[-3:]}
            ]
        elif len(events) >= 5:
            phases = [
                {'name': 'Early Phase', 'events': events[-5:-2]},
                {'name': 'Current Phase', 'events': events[-2:]}
            ]
        else:
            phases = [
                {'name': 'Current Phase', 'events': events}
            ]
        
        return phases

class EntityRelationshipService:
    """Entity relationship mapping for connected stories"""
    
    def __init__(self):
        self.entity_cache = {}
    
    def extract_entities(self, articles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract entities from articles and find relationships"""
        try:
            entities = {
                'people': [],
                'organizations': [],
                'locations': [],
                'topics': []
            }
            
            for article in articles:
                # Simple entity extraction (can be enhanced with NER)
                text = f"{article.get('title', '')} {article.get('content', '')}"
                
                # Extract capitalized words (potential entities)
                words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
                
                for word in words:
                    if len(word) > 2:
                        # Categorize entities (simplified)
                        if any(org_word in word.lower() for org_word in ['inc', 'corp', 'ltd', 'company', 'group']):
                            entities['organizations'].append({
                                'name': word,
                                'article_id': article.get('id'),
                                'context': text[:200] + '...'
                            })
                        elif any(loc_word in word.lower() for loc_word in ['city', 'state', 'country', 'united', 'america']):
                            entities['locations'].append({
                                'name': word,
                                'article_id': article.get('id'),
                                'context': text[:200] + '...'
                            })
                        else:
                            entities['people'].append({
                                'name': word,
                                'article_id': article.get('id'),
                                'context': text[:200] + '...'
                            })
            
            # Remove duplicates and count occurrences
            for category in entities:
                entity_counts = {}
                for entity in entities[category]:
                    name = entity['name']
                    if name in entity_counts:
                        entity_counts[name]['count'] += 1
                        entity_counts[name]['articles'].append(entity['article_id'])
                    else:
                        entity_counts[name] = {
                            'name': name,
                            'count': 1,
                            'articles': [entity['article_id']],
                            'context': entity['context']
                        }
                
                entities[category] = list(entity_counts.values())
                entities[category].sort(key=lambda x: x['count'], reverse=True)
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {'people': [], 'organizations': [], 'locations': [], 'topics': []}
    
    def find_related_stories(self, entities: Dict[str, List[Dict[str, Any]]], 
                           existing_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find stories related through shared entities"""
        try:
            related_stories = []
            
            # Find articles that share entities
            for category, entity_list in entities.items():
                for entity in entity_list[:5]:  # Top 5 entities per category
                    entity_name = entity['name']
                    
                    # Find articles mentioning this entity
                    related_articles = []
                    for article in existing_articles:
                        text = f"{article.get('title', '')} {article.get('content', '')}"
                        if entity_name.lower() in text.lower():
                            related_articles.append(article)
                    
                    if len(related_articles) > 1:  # Multiple articles mention this entity
                        related_stories.append({
                            'entity': entity_name,
                            'category': category,
                            'article_count': len(related_articles),
                            'articles': related_articles[:5],  # Limit to 5 articles
                            'connection_strength': min(len(related_articles) / 10, 1.0)
                        })
            
            # Sort by connection strength
            related_stories.sort(key=lambda x: x['connection_strength'], reverse=True)
            return related_stories[:10]  # Top 10 related stories
            
        except Exception as e:
            logger.error(f"Error finding related stories: {e}")
            return []

class RAGExternalServicesManager:
    """Manager for all external RAG services"""
    
    def __init__(self, config: Dict[str, str] = None):
        self.config = config or {}
        
        # Initialize services
        self.wikipedia = WikipediaService()
        self.newsapi = NewsAPIService(self.config.get('newsapi_key'))
        self.knowledge_graph = KnowledgeGraphService(self.config.get('kg_api_key'))
        self.semantic_search = SemanticSearchService()
        self.timeline_analysis = TimelineAnalysisService()
        self.entity_relationships = EntityRelationshipService()
        
        # Rate limiting
        self.last_request_times = {}
        self.rate_limits = {
            'wikipedia': 1.0,  # 1 second between requests
            'newsapi': 2.0,    # 2 seconds between requests
            'knowledge_graph': 1.5  # 1.5 seconds between requests
        }
    
    def _rate_limit(self, service: str) -> None:
        """Apply rate limiting for external services"""
        if service in self.last_request_times:
            time_since_last = time.time() - self.last_request_times[service]
            if time_since_last < self.rate_limits.get(service, 1.0):
                time.sleep(self.rate_limits[service] - time_since_last)
        
        self.last_request_times[service] = time.time()
    
    def gather_comprehensive_context(self, query: str, story_keywords: List[str] = None,
                                   max_results: int = 20) -> Dict[str, Any]:
        """Gather comprehensive context from all external services"""
        try:
            logger.info(f"Gathering comprehensive context for query: {query}")
            
            context = {
                'query': query,
                'generated_at': datetime.now().isoformat(),
                'sources': {}
            }
            
            # Wikipedia context
            try:
                self._rate_limit('wikipedia')
                wiki_articles = self.wikipedia.search_articles(query, limit=5)
                if wiki_articles:
                    context['sources']['wikipedia'] = {
                        'articles': wiki_articles,
                        'count': len(wiki_articles)
                    }
                    
                    # Get detailed summary for top article
                    if wiki_articles:
                        top_article = self.wikipedia.get_article_summary(wiki_articles[0]['title'])
                        if top_article:
                            context['sources']['wikipedia']['detailed_summary'] = top_article
            except Exception as e:
                logger.warning(f"Wikipedia service error: {e}")
            
            # NewsAPI context
            try:
                self._rate_limit('newsapi')
                news_articles = self.newsapi.search_articles(query, days=30, limit=10)
                if news_articles:
                    context['sources']['newsapi'] = {
                        'articles': news_articles,
                        'count': len(news_articles)
                    }
            except Exception as e:
                logger.warning(f"NewsAPI service error: {e}")
            
            # Knowledge Graph context
            try:
                self._rate_limit('knowledge_graph')
                kg_entities = self.knowledge_graph.search_entities(query, limit=5)
                if kg_entities:
                    context['sources']['knowledge_graph'] = {
                        'entities': kg_entities,
                        'count': len(kg_entities)
                    }
            except Exception as e:
                logger.warning(f"Knowledge Graph service error: {e}")
            
            # Timeline analysis
            if story_keywords:
                try:
                    all_articles = []
                    if 'wikipedia' in context['sources']:
                        all_articles.extend(context['sources']['wikipedia']['articles'])
                    if 'newsapi' in context['sources']:
                        all_articles.extend(context['sources']['newsapi']['articles'])
                    
                    if all_articles:
                        timeline = self.timeline_analysis.build_story_timeline(all_articles, story_keywords)
                        context['timeline_analysis'] = timeline
                except Exception as e:
                    logger.warning(f"Timeline analysis error: {e}")
            
            # Entity relationships
            try:
                all_articles = []
                if 'wikipedia' in context['sources']:
                    all_articles.extend(context['sources']['wikipedia']['articles'])
                if 'newsapi' in context['sources']:
                    all_articles.extend(context['sources']['newsapi']['articles'])
                
                if all_articles:
                    entities = self.entity_relationships.extract_entities(all_articles)
                    related_stories = self.entity_relationships.find_related_stories(entities, all_articles)
                    
                    context['entity_analysis'] = {
                        'entities': entities,
                        'related_stories': related_stories
                    }
            except Exception as e:
                logger.warning(f"Entity analysis error: {e}")
            
            # Summary
            context['summary'] = self._generate_context_summary(context)
            
            return context
            
        except Exception as e:
            logger.error(f"Error gathering comprehensive context: {e}")
            return {'error': str(e)}
    
    def _generate_context_summary(self, context: Dict[str, Any]) -> str:
        """Generate a summary of the gathered context"""
        try:
            sources = context.get('sources', {})
            summary_parts = []
            
            if 'wikipedia' in sources:
                wiki_count = sources['wikipedia']['count']
                summary_parts.append(f"Found {wiki_count} Wikipedia articles")
            
            if 'newsapi' in sources:
                news_count = sources['newsapi']['count']
                summary_parts.append(f"Found {news_count} recent news articles")
            
            if 'knowledge_graph' in sources:
                kg_count = sources['knowledge_graph']['count']
                summary_parts.append(f"Found {kg_count} Knowledge Graph entities")
            
            if 'timeline_analysis' in context:
                timeline = context['timeline_analysis']
                summary_parts.append(f"Timeline analysis: {timeline.get('total_events', 0)} events across {len(timeline.get('time_periods', {}))} time periods")
            
            if 'entity_analysis' in context:
                entities = context['entity_analysis']['entities']
                total_entities = sum(len(entities[cat]) for cat in entities)
                summary_parts.append(f"Entity analysis: {total_entities} entities identified")
            
            return ". ".join(summary_parts) + "." if summary_parts else "No external context found."
            
        except Exception as e:
            logger.error(f"Error generating context summary: {e}")
            return "Context summary generation failed."
