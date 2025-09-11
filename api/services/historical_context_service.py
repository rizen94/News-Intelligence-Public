"""
Historical Context Service for News Intelligence System v3.0
Provides comprehensive historical context and pattern recognition
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from database.connection import get_db
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PatternType(Enum):
    """Available historical pattern types"""
    POLITICAL_CYCLE = "political_cycle"
    ECONOMIC_CYCLE = "economic_cycle"
    SOCIAL_MOVEMENT = "social_movement"
    TECHNOLOGICAL_ADOPTION = "technological_adoption"
    DIPLOMATIC_CRISIS = "diplomatic_crisis"
    ENVIRONMENTAL_EVENT = "environmental_event"

@dataclass
class HistoricalEvent:
    """Historical event data structure"""
    event_id: str
    title: str
    description: str
    date: str
    category: str
    significance_score: float
    similarity_score: float
    source: str
    metadata: Dict[str, Any]

@dataclass
class HistoricalPattern:
    """Historical pattern data structure"""
    pattern_id: str
    pattern_type: str
    description: str
    historical_events: List[HistoricalEvent]
    similarity_score: float
    confidence_level: float
    precedent_analysis: str
    lessons_learned: List[str]
    metadata: Dict[str, Any]

@dataclass
class HistoricalContextResult:
    """Result of historical context analysis"""
    storyline_id: str
    historical_timeline: List[HistoricalEvent]
    identified_patterns: List[HistoricalPattern]
    similar_events: List[HistoricalEvent]
    precedent_analysis: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    context_quality_score: float

class HistoricalContextService:
    """
    Historical context service that provides historical analysis and pattern recognition
    """
    
    def __init__(self, ml_service=None, rag_service=None):
        """
        Initialize the Historical Context Service
        
        Args:
            ml_service: ML summarization service instance
            rag_service: RAG service instance
        """
        self.ml_service = ml_service
        self.rag_service = rag_service
        
        # Historical data sources configuration
        self.historical_sources = {
            'gdelt_historical': {
                'name': 'GDELT Historical Events',
                'description': 'Historical events from GDELT database',
                'time_range': 365,  # days
                'categories': ['political', 'economic', 'social', 'environmental', 'technological']
            },
            'wikipedia_timeline': {
                'name': 'Wikipedia Historical Timeline',
                'description': 'Historical timeline from Wikipedia',
                'time_range': 730,  # days
                'categories': ['general', 'political', 'economic', 'social', 'cultural']
            },
            'news_archives': {
                'name': 'News Archives',
                'description': 'Historical news articles and reports',
                'time_range': 1095,  # days
                'categories': ['news', 'analysis', 'opinion', 'investigation']
            }
        }
        
        # Pattern recognition templates
        self.pattern_templates = {
            PatternType.POLITICAL_CYCLE: {
                'name': 'Political Cycle Pattern',
                'description': 'Recurring political patterns and cycles',
                'keywords': ['election', 'government', 'policy', 'political', 'administration', 'campaign'],
                'time_frames': ['short_term', 'medium_term', 'long_term'],
                'significance_threshold': 0.7
            },
            PatternType.ECONOMIC_CYCLE: {
                'name': 'Economic Cycle Pattern',
                'description': 'Economic patterns and business cycles',
                'keywords': ['economic', 'market', 'recession', 'growth', 'inflation', 'employment'],
                'time_frames': ['medium_term', 'long_term'],
                'significance_threshold': 0.6
            },
            PatternType.SOCIAL_MOVEMENT: {
                'name': 'Social Movement Pattern',
                'description': 'Social movements and cultural shifts',
                'keywords': ['social', 'movement', 'protest', 'activism', 'cultural', 'demographic'],
                'time_frames': ['medium_term', 'long_term'],
                'significance_threshold': 0.5
            },
            PatternType.TECHNOLOGICAL_ADOPTION: {
                'name': 'Technological Adoption Pattern',
                'description': 'Technology adoption and innovation patterns',
                'keywords': ['technology', 'innovation', 'digital', 'adoption', 'disruption', 'automation'],
                'time_frames': ['short_term', 'medium_term', 'long_term'],
                'significance_threshold': 0.6
            },
            PatternType.DIPLOMATIC_CRISIS: {
                'name': 'Diplomatic Crisis Pattern',
                'description': 'International diplomatic patterns and crises',
                'keywords': ['diplomatic', 'international', 'crisis', 'conflict', 'treaty', 'negotiation'],
                'time_frames': ['short_term', 'medium_term'],
                'significance_threshold': 0.8
            },
            PatternType.ENVIRONMENTAL_EVENT: {
                'name': 'Environmental Event Pattern',
                'description': 'Environmental events and climate patterns',
                'keywords': ['environmental', 'climate', 'disaster', 'sustainability', 'conservation', 'pollution'],
                'time_frames': ['short_term', 'medium_term', 'long_term'],
                'significance_threshold': 0.5
            }
        }
    
    async def generate_historical_context(self, storyline_id: str, storyline_title: str, 
                                       articles: List[Dict], rag_context: Dict[str, Any] = None) -> HistoricalContextResult:
        """
        Generate comprehensive historical context for a storyline
        
        Args:
            storyline_id: ID of the storyline
            storyline_title: Title of the storyline
            articles: List of articles in the storyline
            rag_context: Optional RAG context for enhanced analysis
            
        Returns:
            HistoricalContextResult with comprehensive historical analysis
        """
        try:
            logger.info(f"Generating historical context for storyline: {storyline_id}")
            
            # Build historical timeline
            historical_timeline = await self._build_historical_timeline(storyline_title, articles, rag_context)
            
            # Identify historical patterns
            identified_patterns = await self._identify_historical_patterns(storyline_title, historical_timeline)
            
            # Find similar historical events
            similar_events = await self._find_similar_events(storyline_title, historical_timeline, articles)
            
            # Analyze historical precedents
            precedent_analysis = await self._analyze_precedents(similar_events, identified_patterns)
            
            # Generate trend analysis
            trend_analysis = await self._analyze_trends(historical_timeline, identified_patterns)
            
            # Calculate context quality score
            context_quality_score = self._calculate_context_quality_score(
                historical_timeline, identified_patterns, similar_events
            )
            
            # Create result
            result = HistoricalContextResult(
                storyline_id=storyline_id,
                historical_timeline=historical_timeline,
                identified_patterns=identified_patterns,
                similar_events=similar_events,
                precedent_analysis=precedent_analysis,
                trend_analysis=trend_analysis,
                context_quality_score=context_quality_score
            )
            
            # Store historical context
            await self._store_historical_context(result)
            
            logger.info(f"Historical context generated for storyline: {storyline_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating historical context: {e}")
            raise
    
    async def _build_historical_timeline(self, storyline_title: str, articles: List[Dict], 
                                       rag_context: Dict[str, Any]) -> List[HistoricalEvent]:
        """Build historical timeline for the storyline"""
        try:
            timeline_events = []
            
            # Extract key entities and topics for historical search
            key_entities = self._extract_key_entities(articles, rag_context)
            key_topics = self._extract_key_topics(articles, rag_context)
            
            # Search for historical events using different sources
            for source_name, source_config in self.historical_sources.items():
                try:
                    events = await self._search_historical_events(
                        storyline_title, key_entities, key_topics, source_name, source_config
                    )
                    timeline_events.extend(events)
                except Exception as e:
                    logger.warning(f"Error searching {source_name}: {e}")
                    continue
            
            # Sort events by date and significance
            timeline_events.sort(key=lambda x: (x.date, -x.significance_score))
            
            # Remove duplicates and limit to most relevant events
            unique_events = self._deduplicate_events(timeline_events)
            return unique_events[:50]  # Limit to 50 most relevant events
            
        except Exception as e:
            logger.error(f"Error building historical timeline: {e}")
            return []
    
    async def _search_historical_events(self, storyline_title: str, key_entities: List[str], 
                                      key_topics: List[str], source_name: str, 
                                      source_config: Dict[str, Any]) -> List[HistoricalEvent]:
        """Search for historical events from a specific source"""
        try:
            # This is a simplified implementation - in production, you would integrate with actual APIs
            events = []
            
            # Generate mock historical events based on storyline title and entities
            for i, entity in enumerate(key_entities[:5]):  # Limit to 5 entities
                event = HistoricalEvent(
                    event_id=f"{source_name}_{i}",
                    title=f"Historical event related to {entity}",
                    description=f"This is a historical event that relates to {entity} and the storyline '{storyline_title}'",
                    date=self._generate_historical_date(),
                    category=source_config['categories'][i % len(source_config['categories'])],
                    significance_score=0.5 + (i * 0.1),
                    similarity_score=0.6 + (i * 0.05),
                    source=source_name,
                    metadata={
                        'search_entity': entity,
                        'search_topic': key_topics[i % len(key_topics)] if key_topics else 'general',
                        'generated_at': datetime.now(timezone.utc).isoformat()
                    }
                )
                events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"Error searching historical events from {source_name}: {e}")
            return []
    
    async def _identify_historical_patterns(self, storyline_title: str, 
                                         historical_events: List[HistoricalEvent]) -> List[HistoricalPattern]:
        """Identify historical patterns in the events"""
        try:
            patterns = []
            
            for pattern_type, pattern_config in self.pattern_templates.items():
                # Check if events match this pattern type
                matching_events = self._find_matching_events(historical_events, pattern_config)
                
                if matching_events:
                    # Calculate pattern similarity and confidence
                    similarity_score = self._calculate_pattern_similarity(matching_events, pattern_config)
                    confidence_level = self._calculate_pattern_confidence(matching_events, similarity_score)
                    
                    if similarity_score >= pattern_config['significance_threshold']:
                        # Generate pattern analysis
                        precedent_analysis = await self._generate_precedent_analysis(
                            pattern_type, matching_events, storyline_title
                        )
                        
                        lessons_learned = self._extract_lessons_learned(matching_events, pattern_type)
                        
                        pattern = HistoricalPattern(
                            pattern_id=f"pattern_{pattern_type.value}_{len(patterns)}",
                            pattern_type=pattern_type.value,
                            description=f"{pattern_config['name']} identified in historical context",
                            historical_events=matching_events,
                            similarity_score=similarity_score,
                            confidence_level=confidence_level,
                            precedent_analysis=precedent_analysis,
                            lessons_learned=lessons_learned,
                            metadata={
                                'pattern_name': pattern_config['name'],
                                'keywords_used': pattern_config['keywords'],
                                'events_count': len(matching_events),
                                'generated_at': datetime.now(timezone.utc).isoformat()
                            }
                        )
                        patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error identifying historical patterns: {e}")
            return []
    
    async def _find_similar_events(self, storyline_title: str, historical_events: List[HistoricalEvent], 
                                 articles: List[Dict]) -> List[HistoricalEvent]:
        """Find similar historical events to current storyline"""
        try:
            similar_events = []
            
            # Extract current storyline characteristics
            current_characteristics = self._extract_storyline_characteristics(articles)
            
            # Find events with high similarity to current storyline
            for event in historical_events:
                similarity = self._calculate_event_similarity(event, current_characteristics)
                if similarity > 0.6:  # Threshold for similarity
                    event.similarity_score = similarity
                    similar_events.append(event)
            
            # Sort by similarity score
            similar_events.sort(key=lambda x: x.similarity_score, reverse=True)
            
            return similar_events[:20]  # Limit to 20 most similar events
            
        except Exception as e:
            logger.error(f"Error finding similar events: {e}")
            return []
    
    async def _analyze_precedents(self, similar_events: List[HistoricalEvent], 
                                patterns: List[HistoricalPattern]) -> Dict[str, Any]:
        """Analyze historical precedents and their implications"""
        try:
            precedent_analysis = {
                'similar_events_count': len(similar_events),
                'patterns_identified': len(patterns),
                'precedent_lessons': [],
                'historical_outcomes': [],
                'risk_factors': [],
                'success_factors': []
            }
            
            # Analyze similar events
            if similar_events:
                outcomes = [event.metadata.get('outcome', 'unknown') for event in similar_events]
                precedent_analysis['historical_outcomes'] = list(set(outcomes))
                
                # Extract lessons from similar events
                for event in similar_events[:5]:  # Top 5 most similar
                    lesson = f"Historical precedent: {event.title} - {event.description[:100]}..."
                    precedent_analysis['precedent_lessons'].append(lesson)
            
            # Analyze patterns
            for pattern in patterns:
                if pattern.lessons_learned:
                    precedent_analysis['precedent_lessons'].extend(pattern.lessons_learned)
                
                # Extract risk and success factors
                if pattern.confidence_level > 0.7:
                    if 'crisis' in pattern.pattern_type or 'conflict' in pattern.pattern_type:
                        precedent_analysis['risk_factors'].append(f"High confidence pattern: {pattern.description}")
                    else:
                        precedent_analysis['success_factors'].append(f"Positive pattern: {pattern.description}")
            
            return precedent_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing precedents: {e}")
            return {'error': str(e)}
    
    async def _analyze_trends(self, historical_events: List[HistoricalEvent], 
                            patterns: List[HistoricalPattern]) -> Dict[str, Any]:
        """Analyze historical trends and their implications"""
        try:
            trend_analysis = {
                'temporal_distribution': {},
                'category_distribution': {},
                'significance_trends': {},
                'emerging_patterns': [],
                'declining_patterns': [],
                'stable_patterns': []
            }
            
            # Analyze temporal distribution
            if historical_events:
                dates = [event.date for event in historical_events if event.date]
                if dates:
                    # Group by decade or year
                    decade_counts = {}
                    for date in dates:
                        try:
                            year = int(date.split('-')[0])
                            decade = (year // 10) * 10
                            decade_counts[decade] = decade_counts.get(decade, 0) + 1
                        except:
                            continue
                    trend_analysis['temporal_distribution'] = decade_counts
            
            # Analyze category distribution
            category_counts = {}
            for event in historical_events:
                category = event.category
                category_counts[category] = category_counts.get(category, 0) + 1
            trend_analysis['category_distribution'] = category_counts
            
            # Analyze significance trends
            if historical_events:
                significance_scores = [event.significance_score for event in historical_events]
                trend_analysis['significance_trends'] = {
                    'average_significance': sum(significance_scores) / len(significance_scores),
                    'max_significance': max(significance_scores),
                    'min_significance': min(significance_scores)
                }
            
            # Analyze pattern trends
            for pattern in patterns:
                if pattern.confidence_level > 0.8:
                    trend_analysis['emerging_patterns'].append(pattern.description)
                elif pattern.confidence_level < 0.4:
                    trend_analysis['declining_patterns'].append(pattern.description)
                else:
                    trend_analysis['stable_patterns'].append(pattern.description)
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {'error': str(e)}
    
    def _extract_key_entities(self, articles: List[Dict], rag_context: Dict[str, Any]) -> List[str]:
        """Extract key entities from articles and RAG context"""
        entities = []
        
        # Extract from RAG context
        if rag_context and 'extracted_entities' in rag_context:
            entities.extend(rag_context['extracted_entities'])
        
        # Extract from article titles and content
        for article in articles[:10]:  # Limit to first 10 articles
            title = article.get('title', '')
            content = article.get('content', '')[:500]  # First 500 chars
            
            # Simple entity extraction (in production, use NLP libraries)
            words = (title + ' ' + content).split()
            # Look for capitalized words (simple heuristic)
            for word in words:
                if word[0].isupper() and len(word) > 3:
                    entities.append(word)
        
        # Remove duplicates and return top entities
        unique_entities = list(set(entities))
        return unique_entities[:20]  # Limit to 20 entities
    
    def _extract_key_topics(self, articles: List[Dict], rag_context: Dict[str, Any]) -> List[str]:
        """Extract key topics from articles and RAG context"""
        topics = []
        
        # Extract from RAG context
        if rag_context and 'extracted_topics' in rag_context:
            topics.extend(rag_context['extracted_topics'])
        
        # Extract from article content
        for article in articles[:10]:  # Limit to first 10 articles
            content = article.get('content', '')[:500]  # First 500 chars
            
            # Simple topic extraction (in production, use NLP libraries)
            # Look for common topic keywords
            topic_keywords = ['policy', 'economic', 'social', 'political', 'environmental', 
                            'technology', 'international', 'security', 'health', 'education']
            
            for keyword in topic_keywords:
                if keyword.lower() in content.lower():
                    topics.append(keyword)
        
        # Remove duplicates and return top topics
        unique_topics = list(set(topics))
        return unique_topics[:15]  # Limit to 15 topics
    
    def _generate_historical_date(self) -> str:
        """Generate a random historical date"""
        import random
        from datetime import datetime, timedelta
        
        # Generate date between 1 year ago and 10 years ago
        end_date = datetime.now() - timedelta(days=365)
        start_date = end_date - timedelta(days=3650)  # 10 years ago
        
        random_days = random.randint(0, (end_date - start_date).days)
        random_date = start_date + timedelta(days=random_days)
        
        return random_date.strftime('%Y-%m-%d')
    
    def _find_matching_events(self, events: List[HistoricalEvent], pattern_config: Dict[str, Any]) -> List[HistoricalEvent]:
        """Find events that match a specific pattern"""
        matching_events = []
        keywords = pattern_config['keywords']
        
        for event in events:
            # Check if event title or description contains pattern keywords
            event_text = (event.title + ' ' + event.description).lower()
            keyword_matches = sum(1 for keyword in keywords if keyword.lower() in event_text)
            
            if keyword_matches >= 2:  # At least 2 keyword matches
                matching_events.append(event)
        
        return matching_events
    
    def _calculate_pattern_similarity(self, events: List[HistoricalEvent], pattern_config: Dict[str, Any]) -> float:
        """Calculate similarity score for a pattern"""
        if not events:
            return 0.0
        
        # Calculate based on keyword matches and event significance
        total_score = 0.0
        for event in events:
            event_text = (event.title + ' ' + event.description).lower()
            keyword_matches = sum(1 for keyword in pattern_config['keywords'] if keyword.lower() in event_text)
            keyword_score = keyword_matches / len(pattern_config['keywords'])
            significance_score = event.significance_score
            total_score += (keyword_score * 0.6) + (significance_score * 0.4)
        
        return total_score / len(events)
    
    def _calculate_pattern_confidence(self, events: List[HistoricalEvent], similarity_score: float) -> float:
        """Calculate confidence level for a pattern"""
        if not events:
            return 0.0
        
        # Base confidence on similarity score and number of matching events
        event_count_factor = min(len(events) / 5, 1.0)  # More events = higher confidence
        return (similarity_score * 0.7) + (event_count_factor * 0.3)
    
    async def _generate_precedent_analysis(self, pattern_type: PatternType, 
                                         events: List[HistoricalEvent], 
                                         storyline_title: str) -> str:
        """Generate precedent analysis for a pattern"""
        try:
            if self.ml_service:
                # Use ML service for analysis
                prompt = f"""
                Analyze the historical precedent for this pattern: {pattern_type.value}
                
                Storyline: {storyline_title}
                Historical Events: {[event.title for event in events]}
                
                Provide analysis of:
                1. Historical outcomes and consequences
                2. Key factors that influenced outcomes
                3. Lessons learned from historical precedents
                4. Implications for current situation
                """
                
                result = await self._call_ml_service(
                    "You are a senior historical analyst specializing in precedent analysis.",
                    prompt
                )
                return result.get('summary', 'Precedent analysis not available')
            else:
                # Fallback analysis
                return f"Historical precedent analysis for {pattern_type.value}: {len(events)} related events identified. Key factors include historical context, stakeholder involvement, and outcome patterns."
                
        except Exception as e:
            logger.error(f"Error generating precedent analysis: {e}")
            return f"Precedent analysis error: {str(e)}"
    
    def _extract_lessons_learned(self, events: List[HistoricalEvent], pattern_type: PatternType) -> List[str]:
        """Extract lessons learned from historical events"""
        lessons = []
        
        # Generic lessons based on pattern type
        pattern_lessons = {
            PatternType.POLITICAL_CYCLE: [
                "Political cycles often follow predictable patterns",
                "Public opinion shifts can significantly impact outcomes",
                "Institutional factors play a crucial role in political stability"
            ],
            PatternType.ECONOMIC_CYCLE: [
                "Economic cycles are influenced by multiple factors",
                "Market sentiment can drive economic outcomes",
                "Policy responses need to be timely and appropriate"
            ],
            PatternType.SOCIAL_MOVEMENT: [
                "Social movements require sustained momentum",
                "Cultural factors significantly influence social change",
                "Leadership and organization are critical for success"
            ],
            PatternType.TECHNOLOGICAL_ADOPTION: [
                "Technology adoption follows predictable patterns",
                "User acceptance is crucial for successful implementation",
                "Infrastructure and support systems are essential"
            ],
            PatternType.DIPLOMATIC_CRISIS: [
                "Diplomatic crises require careful management",
                "International cooperation is often necessary",
                "Communication and transparency are key factors"
            ],
            PatternType.ENVIRONMENTAL_EVENT: [
                "Environmental events have long-term implications",
                "Prevention and mitigation strategies are crucial",
                "International cooperation is often required"
            ]
        }
        
        lessons.extend(pattern_lessons.get(pattern_type, []))
        
        # Add specific lessons based on events
        for event in events[:3]:  # Top 3 events
            lesson = f"From {event.title}: {event.description[:100]}..."
            lessons.append(lesson)
        
        return lessons[:10]  # Limit to 10 lessons
    
    def _extract_storyline_characteristics(self, articles: List[Dict]) -> Dict[str, Any]:
        """Extract characteristics of current storyline for similarity matching"""
        characteristics = {
            'topics': [],
            'entities': [],
            'sources': [],
            'time_period': 'recent',
            'significance': 'medium'
        }
        
        # Extract topics and entities from articles
        for article in articles[:5]:  # Limit to first 5 articles
            title = article.get('title', '')
            content = article.get('content', '')[:200]
            source = article.get('source', '')
            
            # Simple extraction (in production, use NLP)
            words = (title + ' ' + content).split()
            for word in words:
                if word[0].isupper() and len(word) > 3:
                    characteristics['entities'].append(word)
            
            if source:
                characteristics['sources'].append(source)
        
        # Remove duplicates
        characteristics['entities'] = list(set(characteristics['entities']))
        characteristics['sources'] = list(set(characteristics['sources']))
        
        return characteristics
    
    def _calculate_event_similarity(self, event: HistoricalEvent, characteristics: Dict[str, Any]) -> float:
        """Calculate similarity between historical event and current storyline"""
        similarity_score = 0.0
        
        # Check entity overlap
        event_entities = set(event.title.split() + event.description.split())
        current_entities = set(characteristics['entities'])
        
        if event_entities and current_entities:
            entity_overlap = len(event_entities.intersection(current_entities)) / len(event_entities.union(current_entities))
            similarity_score += entity_overlap * 0.4
        
        # Check category relevance
        if event.category in ['political', 'economic', 'social']:
            similarity_score += 0.3
        
        # Check significance
        similarity_score += event.significance_score * 0.3
        
        return min(similarity_score, 1.0)
    
    def _deduplicate_events(self, events: List[HistoricalEvent]) -> List[HistoricalEvent]:
        """Remove duplicate events from timeline"""
        unique_events = []
        seen_titles = set()
        
        for event in events:
            if event.title not in seen_titles:
                unique_events.append(event)
                seen_titles.add(event.title)
        
        return unique_events
    
    def _calculate_context_quality_score(self, timeline: List[HistoricalEvent], 
                                       patterns: List[HistoricalPattern], 
                                       similar_events: List[HistoricalEvent]) -> float:
        """Calculate overall quality score for historical context"""
        try:
            quality_factors = []
            
            # Timeline quality
            if timeline:
                timeline_quality = min(len(timeline) / 20, 1.0)  # More events = better
                quality_factors.append(timeline_quality)
            
            # Pattern quality
            if patterns:
                pattern_quality = min(len(patterns) / 5, 1.0)  # More patterns = better
                avg_confidence = sum(p.confidence_level for p in patterns) / len(patterns)
                quality_factors.append(pattern_quality * avg_confidence)
            
            # Similar events quality
            if similar_events:
                similar_quality = min(len(similar_events) / 10, 1.0)  # More similar events = better
                avg_similarity = sum(e.similarity_score for e in similar_events) / len(similar_events)
                quality_factors.append(similar_quality * avg_similarity)
            
            return sum(quality_factors) / len(quality_factors) if quality_factors else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating context quality score: {e}")
            return 0.0
    
    async def _call_ml_service(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Call ML service for historical analysis generation"""
        try:
            if hasattr(self.ml_service, 'generate_summary'):
                result = self.ml_service.generate_summary(user_prompt, system_prompt)
                return result
            else:
                return {'summary': 'ML service not available', 'confidence_score': 0.0}
        except Exception as e:
            logger.error(f"Error calling ML service: {e}")
            return {'summary': 'ML service error', 'confidence_score': 0.0}
    
    async def _store_historical_context(self, result: HistoricalContextResult):
        """Store historical context result in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Store historical patterns
                for pattern in result.identified_patterns:
                    insert_query = text("""
                        INSERT INTO historical_patterns (
                            storyline_id, pattern_type, pattern_description,
                            historical_events, similarity_score, precedent_analysis,
                            lessons_learned, pattern_confidence
                        ) VALUES (
                            :storyline_id, :pattern_type, :pattern_description,
                            :historical_events, :similarity_score, :precedent_analysis,
                            :lessons_learned, :pattern_confidence
                        )
                    """)
                    
                    db.execute(insert_query, {
                        'storyline_id': result.storyline_id,
                        'pattern_type': pattern.pattern_type,
                        'pattern_description': pattern.description,
                        'historical_events': json.dumps([{
                            'event_id': e.event_id,
                            'title': e.title,
                            'date': e.date,
                            'significance_score': e.significance_score
                        } for e in pattern.historical_events]),
                        'similarity_score': pattern.similarity_score,
                        'precedent_analysis': pattern.precedent_analysis,
                        'lessons_learned': json.dumps(pattern.lessons_learned),
                        'pattern_confidence': pattern.confidence_level
                    })
                
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing historical context: {e}")

# Global instance
_historical_context_service = None

def get_historical_context_service(ml_service=None, rag_service=None) -> HistoricalContextService:
    """Get global historical context service instance"""
    global _historical_context_service
    if _historical_context_service is None:
        _historical_context_service = HistoricalContextService(ml_service, rag_service)
    return _historical_context_service

