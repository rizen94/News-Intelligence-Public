"""
Enhanced Timeline Service for Chronological Event Extraction
Integrates temporal NLP with ML to create comprehensive timelines
"""

import logging
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import text
from config.database import get_db

from services.temporal_nlp_service import temporal_nlp_service, ChronologicalEvent
from services.ml_summarization_service import MLSummarizationService

logger = logging.getLogger(__name__)

@dataclass
class TimelineReconstruction:
    """Represents a reconstructed timeline narrative"""
    reconstruction_id: str
    storyline_id: str
    narrative_text: str
    event_sequence: List[str]
    coherence_score: float
    completeness_score: float
    accuracy_score: float
    reconstruction_type: str

class EnhancedTimelineService:
    """Service for creating comprehensive chronological timelines"""
    
    def __init__(self):
        self.ml_service = MLSummarizationService()
        self.temporal_nlp = temporal_nlp_service
    
    def extract_chronological_events_from_storyline(self, storyline_id: str) -> List[ChronologicalEvent]:
        """Extract chronological events from all articles in a storyline"""
        try:
            # Get storyline articles
            articles = self._get_storyline_articles(storyline_id)
            
            if not articles:
                logger.warning(f"No articles found for storyline {storyline_id}")
                return []
            
            all_events = []
            
            for article in articles:
                # Extract events from each article
                article_events = self._extract_events_from_article(article)
                all_events.extend(article_events)
            
            # Store events in database
            stored_events = self._store_chronological_events(storyline_id, all_events)
            
            # Find relationships between events
            self._find_event_relationships(storyline_id, stored_events)
            
            return stored_events
            
        except Exception as e:
            logger.error(f"Error extracting chronological events: {e}")
            return []
    
    def _get_storyline_articles(self, storyline_id: str) -> List[Dict[str, Any]]:
        """Get articles for a storyline"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text("""
                    SELECT a.id, a.title, a.content, a.summary, a.source, a.url, 
                           a.published_at, a.author, a.entities, a.sentiment_score
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = :storyline_id
                    ORDER BY a.published_at ASC
                """)
                
                result = db.execute(query, {"storyline_id": storyline_id}).fetchall()
                return [dict(row._mapping) for row in result]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            return []
    
    def _extract_events_from_article(self, article: Dict[str, Any]) -> List[ChronologicalEvent]:
        """Extract chronological events from a single article"""
        try:
            content = article.get('content', '') or article.get('summary', '')
            if not content:
                return []
            
            # Use temporal NLP service to extract events
            events = self.temporal_nlp.extract_chronological_events(
                content, 
                article.get('title', ''), 
                article.get('source', '')
            )
            
            # Enhance events with article context
            enhanced_events = []
            for event in events:
                enhanced_event = self._enhance_event_with_context(event, article)
                enhanced_events.append(enhanced_event)
            
            return enhanced_events
            
        except Exception as e:
            logger.error(f"Error extracting events from article {article.get('id')}: {e}")
            return []
    
    def _enhance_event_with_context(self, event: ChronologicalEvent, article: Dict[str, Any]) -> ChronologicalEvent:
        """Enhance event with additional context from article"""
        # Add article metadata
        event.source_article_id = article['id']
        event.source_publication = article.get('source', '')
        event.article_published_at = article.get('published_at')
        
        # Enhance importance score based on article quality
        article_quality = self._calculate_article_quality(article)
        event.importance_score = min(event.importance_score + article_quality * 0.1, 1.0)
        
        # Add article entities to event entities
        article_entities = article.get('entities', [])
        if isinstance(article_entities, str):
            try:
                article_entities = json.loads(article_entities)
            except:
                article_entities = []
        
        event.entities.extend(article_entities[:3])  # Add top 3 article entities
        event.entities = list(set(event.entities))  # Remove duplicates
        
        return event
    
    def _calculate_article_quality(self, article: Dict[str, Any]) -> float:
        """Calculate article quality score"""
        score = 0.5  # Base score
        
        # Boost for engagement metrics
        engagement_score = article.get('engagement_score', 0)
        if engagement_score:
            score += engagement_score * 0.3
        
        # Boost for sentiment score (neutral to positive)
        sentiment_score = article.get('sentiment_score', 0)
        if sentiment_score is not None:
            score += abs(sentiment_score) * 0.2
        
        # Boost for content length
        content_length = len(article.get('content', ''))
        if content_length > 1000:
            score += 0.1
        elif content_length > 500:
            score += 0.05
        
        # Boost for reputable sources
        source = article.get('source', '').lower()
        if any(reputable in source for reputable in ['reuters', 'ap', 'bbc', 'cnn', 'fox', 'nbc']):
            score += 0.1
        
        return min(score, 1.0)
    
    def _store_chronological_events(self, storyline_id: str, events: List[ChronologicalEvent]) -> List[ChronologicalEvent]:
        """Store chronological events in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                stored_events = []
                
                for i, event in enumerate(events):
                    # Generate unique event ID
                    event_id = f"{storyline_id}_event_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Insert chronological event
                    insert_query = text("""
                        INSERT INTO chronological_events (
                            event_id, storyline_id, title, description, actual_event_date,
                            relative_temporal_expression, temporal_confidence, source_article_id,
                            source_text, source_paragraph, source_sentence_start, source_sentence_end,
                            extraction_method, extraction_confidence, importance_score,
                            event_type, location, entities, tags, verified, created_at, updated_at
                        ) VALUES (
                            :event_id, :storyline_id, :title, :description, :actual_event_date,
                            :relative_expression, :temporal_confidence, :source_article_id,
                            :source_text, :source_paragraph, :source_sentence_start, :source_sentence_end,
                            :extraction_method, :extraction_confidence, :importance_score,
                            :event_type, :location, :entities, :tags, :verified, :created_at, :updated_at
                        ) ON CONFLICT (event_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            actual_event_date = EXCLUDED.actual_event_date,
                            importance_score = EXCLUDED.importance_score,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id, event_id
                    """)
                    
                    now = datetime.now()
                    event_data = {
                        'event_id': event_id,
                        'storyline_id': storyline_id,
                        'title': event.title,
                        'description': event.description,
                        'actual_event_date': event.actual_event_date,
                        'relative_expression': event.relative_expression,
                        'temporal_confidence': event.confidence,
                        'source_article_id': getattr(event, 'source_article_id', None),
                        'source_text': event.source_text,
                        'source_paragraph': event.source_paragraph,
                        'source_sentence_start': event.source_sentence_start,
                        'source_sentence_end': event.source_sentence_end,
                        'extraction_method': 'ml_nlp',
                        'extraction_confidence': event.confidence,
                        'importance_score': event.importance_score,
                        'event_type': event.event_type,
                        'location': None,  # Could be extracted from content
                        'entities': json.dumps(event.entities),
                        'tags': [],  # Could be generated based on content
                        'verified': False,
                        'created_at': now,
                        'updated_at': now
                    }
                    
                    result = db.execute(insert_query, event_data).fetchone()
                    
                    if result:
                        event.db_id = result[0]
                        event.db_event_id = result[1]
                        stored_events.append(event)
                
                db.commit()
                logger.info(f"Stored {len(stored_events)} chronological events for storyline {storyline_id}")
                return stored_events
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing chronological events: {e}")
            return events
    
    def _find_event_relationships(self, storyline_id: str, events: List[ChronologicalEvent]):
        """Find relationships between chronological events"""
        try:
            # Sort events by date
            sorted_events = sorted([e for e in events if e.actual_event_date], 
                                 key=lambda x: x.actual_event_date)
            
            relationships = []
            
            for i, event1 in enumerate(sorted_events):
                for j, event2 in enumerate(sorted_events[i+1:], i+1):
                    # Calculate relationship
                    relationship = self._calculate_event_relationship(event1, event2)
                    if relationship:
                        relationships.append(relationship)
            
            # Store relationships
            self._store_event_relationships(relationships)
            
        except Exception as e:
            logger.error(f"Error finding event relationships: {e}")
    
    def _calculate_event_relationship(self, event1: ChronologicalEvent, event2: ChronologicalEvent) -> Optional[Dict[str, Any]]:
        """Calculate relationship between two events"""
        if not event1.actual_event_date or not event2.actual_event_date:
            return None
        
        # Calculate time gap
        time_gap = (event2.actual_event_date - event1.actual_event_date).days
        
        # Determine relationship type
        relationship_type = None
        temporal_relationship = None
        
        if time_gap < 0:
            temporal_relationship = 'before'
            if abs(time_gap) <= 7:
                relationship_type = 'follows'
        elif time_gap == 0:
            temporal_relationship = 'simultaneous'
            relationship_type = 'parallel'
        else:
            temporal_relationship = 'after'
            if time_gap <= 7:
                relationship_type = 'causes'
        
        # Calculate relationship strength
        strength = self._calculate_relationship_strength(event1, event2, time_gap)
        
        if strength > 0.3:  # Only store significant relationships
            return {
                'source_event_id': getattr(event1, 'db_id', None),
                'target_event_id': getattr(event2, 'db_id', None),
                'relationship_type': relationship_type,
                'relationship_strength': strength,
                'temporal_relationship': temporal_relationship,
                'time_gap_days': abs(time_gap),
                'confidence_score': strength
            }
        
        return None
    
    def _calculate_relationship_strength(self, event1: ChronologicalEvent, event2: ChronologicalEvent, time_gap: int) -> float:
        """Calculate strength of relationship between events"""
        strength = 0.0
        
        # Time proximity factor
        if abs(time_gap) <= 1:
            strength += 0.4
        elif abs(time_gap) <= 7:
            strength += 0.3
        elif abs(time_gap) <= 30:
            strength += 0.2
        else:
            strength += 0.1
        
        # Entity overlap
        entities1 = set(event1.entities)
        entities2 = set(event2.entities)
        if entities1 and entities2:
            overlap = len(entities1 & entities2) / len(entities1 | entities2)
            strength += overlap * 0.3
        
        # Event type similarity
        if event1.event_type == event2.event_type:
            strength += 0.2
        
        # Importance factor
        avg_importance = (event1.importance_score + event2.importance_score) / 2
        strength += avg_importance * 0.1
        
        return min(strength, 1.0)
    
    def _store_event_relationships(self, relationships: List[Dict[str, Any]]):
        """Store event relationships in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                for rel in relationships:
                    if rel.get('source_event_id') and rel.get('target_event_id'):
                        insert_query = text("""
                            INSERT INTO event_relationships (
                                relationship_id, source_event_id, target_event_id,
                                relationship_type, relationship_strength, temporal_relationship,
                                time_gap_days, confidence_score, created_at
                            ) VALUES (
                                :relationship_id, :source_event_id, :target_event_id,
                                :relationship_type, :relationship_strength, :temporal_relationship,
                                :time_gap_days, :confidence_score, :created_at
                            ) ON CONFLICT (source_event_id, target_event_id, relationship_type) DO UPDATE SET
                                relationship_strength = EXCLUDED.relationship_strength,
                                confidence_score = EXCLUDED.confidence_score
                        """)
                        
                        relationship_id = f"rel_{rel['source_event_id']}_{rel['target_event_id']}_{rel['relationship_type']}"
                        
                        db.execute(insert_query, {
                            'relationship_id': relationship_id,
                            'source_event_id': rel['source_event_id'],
                            'target_event_id': rel['target_event_id'],
                            'relationship_type': rel['relationship_type'],
                            'relationship_strength': rel['relationship_strength'],
                            'temporal_relationship': rel['temporal_relationship'],
                            'time_gap_days': rel['time_gap_days'],
                            'confidence_score': rel['confidence_score'],
                            'created_at': datetime.now()
                        })
                
                db.commit()
                logger.info(f"Stored {len(relationships)} event relationships")
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing event relationships: {e}")
    
    def reconstruct_timeline_narrative(self, storyline_id: str) -> TimelineReconstruction:
        """Reconstruct a cohesive timeline narrative from chronological events"""
        try:
            # Get chronological events
            events = self._get_chronological_events(storyline_id)
            
            if not events:
                return self._create_empty_timeline(storyline_id)
            
            # Sort events chronologically
            sorted_events = sorted(events, key=lambda x: (x['actual_event_date'], x.get('actual_event_time', '00:00:00')))
            
            # Generate narrative using ML
            narrative = self._generate_timeline_narrative(sorted_events, storyline_id)
            
            # Calculate quality scores
            coherence_score = self._calculate_coherence_score(narrative)
            completeness_score = self._calculate_completeness_score(events)
            accuracy_score = self._calculate_accuracy_score(events)
            
            # Create reconstruction
            reconstruction = TimelineReconstruction(
                reconstruction_id=f"timeline_{storyline_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                storyline_id=storyline_id,
                narrative_text=narrative,
                event_sequence=[str(e['id']) for e in sorted_events],
                coherence_score=coherence_score,
                completeness_score=completeness_score,
                accuracy_score=accuracy_score,
                reconstruction_type='chronological'
            )
            
            # Store reconstruction
            self._store_timeline_reconstruction(reconstruction)
            
            return reconstruction
            
        except Exception as e:
            logger.error(f"Error reconstructing timeline narrative: {e}")
            return self._create_empty_timeline(storyline_id)
    
    def _get_chronological_events(self, storyline_id: str) -> List[Dict[str, Any]]:
        """Get chronological events from database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                query = text("""
                    SELECT id, event_id, title, description, actual_event_date, actual_event_time,
                           event_type, importance_score, entities, temporal_confidence
                    FROM chronological_events
                    WHERE storyline_id = :storyline_id
                    ORDER BY actual_event_date, actual_event_time
                """)
                
                result = db.execute(query, {"storyline_id": storyline_id}).fetchall()
                return [dict(row._mapping) for row in result]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting chronological events: {e}")
            return []
    
    def _generate_timeline_narrative(self, events: List[Dict[str, Any]], storyline_id: str) -> str:
        """Generate timeline narrative using ML"""
        try:
            # Prepare context for ML
            context = self._prepare_timeline_context(events, storyline_id)
            
            # Generate narrative using ML service
            result = self.ml_service.generate_summary(context)
            
            if result and result.get('success'):
                return result.get('summary', 'Timeline narrative generation failed.')
            else:
                return self._generate_fallback_narrative(events)
                
        except Exception as e:
            logger.error(f"Error generating timeline narrative: {e}")
            return self._generate_fallback_narrative(events)
    
    def _prepare_timeline_context(self, events: List[Dict[str, Any]], storyline_id: str) -> str:
        """Prepare context for timeline narrative generation"""
        context = f"""
TIMELINE NARRATIVE GENERATION REQUEST

Storyline ID: {storyline_id}
Total Events: {len(events)}

Create a cohesive chronological narrative that tells the complete story of these events.
Focus on how events connect and build upon each other over time.

CHRONOLOGICAL EVENTS:
"""
        
        for i, event in enumerate(events, 1):
            event_date = event['actual_event_date'].strftime('%B %d, %Y') if event['actual_event_date'] else 'Unknown Date'
            context += f"""
Event {i} - {event_date}:
Title: {event['title']}
Description: {event['description']}
Type: {event['event_type']}
Importance: {event['importance_score']}
Confidence: {event['temporal_confidence']}
"""
        
        context += """
INSTRUCTIONS:
1. Create a flowing narrative that connects these events chronologically
2. Explain how each event relates to the overall story
3. Highlight key turning points and developments
4. Show cause-and-effect relationships where evident
5. Use clear, engaging language that tells a complete story
6. Aim for 500-800 words that provide comprehensive coverage

Write as a journalist creating a comprehensive timeline report.
"""
        
        return context
    
    def _generate_fallback_narrative(self, events: List[Dict[str, Any]]) -> str:
        """Generate fallback narrative without ML"""
        if not events:
            return "No chronological events available for this storyline."
        
        narrative = f"# Timeline Narrative\n\nThis storyline contains {len(events)} chronological events:\n\n"
        
        for i, event in enumerate(events, 1):
            event_date = event['actual_event_date'].strftime('%B %d, %Y') if event['actual_event_date'] else 'Unknown Date'
            narrative += f"**{i}. {event_date}** - {event['title']}\n"
            narrative += f"{event['description']}\n\n"
        
        return narrative
    
    def _calculate_coherence_score(self, narrative: str) -> float:
        """Calculate coherence score for narrative"""
        # Simple heuristic - could be more sophisticated
        if len(narrative) < 100:
            return 0.3
        
        # Check for temporal indicators
        temporal_indicators = ['then', 'next', 'following', 'after', 'before', 'during', 'meanwhile']
        indicator_count = sum(1 for indicator in temporal_indicators if indicator in narrative.lower())
        
        # Check for transition words
        transition_words = ['however', 'furthermore', 'additionally', 'consequently', 'therefore']
        transition_count = sum(1 for word in transition_words if word in narrative.lower())
        
        # Calculate score
        score = 0.5  # Base score
        score += min(indicator_count * 0.1, 0.3)  # Temporal indicators
        score += min(transition_count * 0.05, 0.2)  # Transition words
        
        return min(score, 1.0)
    
    def _calculate_completeness_score(self, events: List[Dict[str, Any]]) -> float:
        """Calculate completeness score based on event coverage"""
        if not events:
            return 0.0
        
        # Check for date coverage
        events_with_dates = sum(1 for e in events if e['actual_event_date'])
        date_coverage = events_with_dates / len(events)
        
        # Check for importance distribution
        high_importance_events = sum(1 for e in events if e['importance_score'] > 0.7)
        importance_distribution = high_importance_events / len(events)
        
        # Calculate score
        score = date_coverage * 0.6 + importance_distribution * 0.4
        return min(score, 1.0)
    
    def _calculate_accuracy_score(self, events: List[Dict[str, Any]]) -> float:
        """Calculate accuracy score based on confidence levels"""
        if not events:
            return 0.0
        
        # Average confidence score
        avg_confidence = sum(e['temporal_confidence'] for e in events) / len(events)
        
        # Check for verified events
        verified_events = sum(1 for e in events if e.get('verified', False))
        verification_rate = verified_events / len(events)
        
        # Calculate score
        score = avg_confidence * 0.7 + verification_rate * 0.3
        return min(score, 1.0)
    
    def _create_empty_timeline(self, storyline_id: str) -> TimelineReconstruction:
        """Create empty timeline when no events are available"""
        return TimelineReconstruction(
            reconstruction_id=f"empty_timeline_{storyline_id}",
            storyline_id=storyline_id,
            narrative_text="No chronological events available for this storyline.",
            event_sequence=[],
            coherence_score=0.0,
            completeness_score=0.0,
            accuracy_score=0.0,
            reconstruction_type='empty'
        )
    
    def _store_timeline_reconstruction(self, reconstruction: TimelineReconstruction):
        """Store timeline reconstruction in database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                insert_query = text("""
                    INSERT INTO timeline_reconstructions (
                        reconstruction_id, storyline_id, reconstruction_type, narrative_text,
                        event_sequence, coherence_score, completeness_score, accuracy_score,
                        generation_method, generation_timestamp, created_at, updated_at
                    ) VALUES (
                        :reconstruction_id, :storyline_id, :reconstruction_type, :narrative_text,
                        :event_sequence, :coherence_score, :completeness_score, :accuracy_score,
                        :generation_method, :generation_timestamp, :created_at, :updated_at
                    ) ON CONFLICT (reconstruction_id) DO UPDATE SET
                        narrative_text = EXCLUDED.narrative_text,
                        event_sequence = EXCLUDED.event_sequence,
                        coherence_score = EXCLUDED.coherence_score,
                        completeness_score = EXCLUDED.completeness_score,
                        accuracy_score = EXCLUDED.accuracy_score,
                        updated_at = EXCLUDED.updated_at
                """)
                
                now = datetime.now()
                db.execute(insert_query, {
                    'reconstruction_id': reconstruction.reconstruction_id,
                    'storyline_id': reconstruction.storyline_id,
                    'reconstruction_type': reconstruction.reconstruction_type,
                    'narrative_text': reconstruction.narrative_text,
                    'event_sequence': json.dumps(reconstruction.event_sequence),
                    'coherence_score': reconstruction.coherence_score,
                    'completeness_score': reconstruction.completeness_score,
                    'accuracy_score': reconstruction.accuracy_score,
                    'generation_method': 'ml_enhanced',
                    'generation_timestamp': now,
                    'created_at': now,
                    'updated_at': now
                })
                
                db.commit()
                logger.info(f"Stored timeline reconstruction for storyline {reconstruction.storyline_id}")
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error storing timeline reconstruction: {e}")

# Global instance
enhanced_timeline_service = EnhancedTimelineService()
