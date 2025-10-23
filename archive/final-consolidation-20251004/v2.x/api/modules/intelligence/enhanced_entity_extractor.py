#!/usr/bin/env python3
"""
Enhanced Entity Extractor for News Intelligence System v2.5.0
Provides comprehensive entity extraction, event detection, and relationship mapping
"""

import os
import sys
import json
import logging
import psycopg2
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict, Counter

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("Warning: spaCy not available. Using basic entity extraction.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ExtractedEntity:
    """Represents an extracted entity with metadata."""
    text: str
    label: str
    start_char: int
    end_char: int
    confidence: float
    metadata: Dict

@dataclass
class EventCandidate:
    """Represents a potential event detected from articles."""
    event_name: str
    event_type: str
    event_category: str
    confidence: float
    source_articles: List[int]
    entities: Dict[str, List[str]]
    keywords: List[str]
    temporal_indicators: List[str]
    geographic_indicators: List[str]

class EnhancedEntityExtractor:
    """
    Enhanced entity extractor with event detection capabilities.
    Uses spaCy for NLP and custom rules for event detection.
    """
    
    def __init__(self, db_config: Dict = None):
        """Initialize the enhanced entity extractor."""
        self.db_config = db_config or {
            'host': os.getenv('DB_HOST', 'postgres'),
            'database': os.getenv('DB_NAME', 'news_db'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
            'port': os.getenv('DB_PORT', '5432'),
            'connect_timeout': 10,
            'options': '-c statement_timeout=5000'
        }
        
        # Initialize spaCy if available
        self.nlp = None
        if SPACY_AVAILABLE:
            try:
                # Try to load English model, fall back to basic if not available
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy English model")
            except OSError:
                logger.warning("spaCy English model not found. Using basic extraction.")
                self.nlp = None
        
        # Event detection patterns
        self.event_patterns = {
            'breaking_news': [
                r'\b(breaking|urgent|alert|emergency|just in|developing)\b',
                r'\b(announced|revealed|disclosed|reported|confirmed)\b',
                r'\b(incident|accident|attack|disaster|crisis)\b'
            ],
            'ongoing_event': [
                r'\b(continues|ongoing|developing|unfolding|progressing)\b',
                r'\b(day \d+|week \d+|month \d+)\b',
                r'\b(update|latest|recent|current)\b'
            ],
            'announcement': [
                r'\b(announced|revealed|introduced|launched|unveiled)\b',
                r'\b(press release|statement|declaration|proposal)\b',
                r'\b(plan|initiative|policy|decision)\b'
            ],
            'investigation': [
                r'\b(investigation|probe|inquiry|examination|review)\b',
                r'\b(alleged|suspected|under investigation|scrutiny)\b',
                r'\b(evidence|witness|testimony|charges)\b'
            ]
        }
        
        # Event categories based on keywords
        self.category_keywords = {
            'politics': ['election', 'government', 'congress', 'senate', 'president', 'policy', 'vote'],
            'technology': ['tech', 'software', 'app', 'startup', 'innovation', 'digital', 'ai', 'cybersecurity'],
            'health': ['health', 'medical', 'hospital', 'doctor', 'patient', 'treatment', 'vaccine', 'pandemic'],
            'economy': ['economy', 'market', 'stock', 'trade', 'business', 'finance', 'inflation', 'recession'],
            'environment': ['climate', 'environment', 'pollution', 'sustainability', 'green', 'carbon', 'renewable'],
            'crime': ['crime', 'police', 'arrest', 'investigation', 'suspect', 'victim', 'charges', 'court']
        }
        
        # Temporal indicators
        self.temporal_indicators = [
            'today', 'yesterday', 'tomorrow', 'this week', 'this month', 'this year',
            'recently', 'earlier', 'later', 'soon', 'recent', 'latest', 'current'
        ]
        
        # Geographic indicators
        self.geographic_indicators = [
            'in', 'at', 'near', 'around', 'between', 'across', 'throughout',
            'city', 'state', 'country', 'region', 'area', 'zone'
        ]
    
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
    
    def extract_entities_spacy(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using spaCy NLP."""
        if not self.nlp or not text:
            return []
        
        entities = []
        doc = self.nlp(text)
        
        for ent in doc.ents:
            entity = ExtractedEntity(
                text=ent.text,
                label=ent.label_,
                start_char=ent.start_char,
                end_char=ent.end_char,
                confidence=0.8,  # spaCy doesn't provide confidence scores
                metadata={
                    'spacy_label': ent.label_,
                    'spacy_description': spacy.explain(ent.label_)
                }
            )
            entities.append(entity)
        
        return entities
    
    def extract_entities_basic(self, text: str) -> List[ExtractedEntity]:
        """Basic entity extraction using regex patterns when spaCy is not available."""
        if not text:
            return []
        
        entities = []
        
        # Person names (basic pattern)
        person_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b'
        for match in re.finditer(person_pattern, text):
            entity = ExtractedEntity(
                text=match.group(1),
                label='PERSON',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.6,
                metadata={'method': 'regex_pattern'}
            )
            entities.append(entity)
        
        # Organizations (basic pattern)
        org_pattern = r'\b([A-Z][a-z]+ (?:Corporation|Corp|Inc|LLC|Ltd|Company|Co))\b'
        for match in re.finditer(org_pattern, text):
            entity = ExtractedEntity(
                text=match.group(1),
                label='ORG',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.7,
                metadata={'method': 'regex_pattern'}
            )
            entities.append(entity)
        
        # Locations (basic pattern)
        location_pattern = r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*, [A-Z]{2}\b)'
        for match in re.finditer(location_pattern, text):
            entity = ExtractedEntity(
                text=match.group(1),
                label='GPE',
                start_char=match.start(),
                end_char=match.end(),
                confidence=0.7,
                metadata={'method': 'regex_pattern'}
            )
            entities.append(entity)
        
        return entities
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using the best available method."""
        if self.nlp:
            return self.extract_entities_spacy(text)
        else:
            return self.extract_entities_basic(text)
    
    def detect_event_type(self, text: str) -> Tuple[str, float]:
        """Detect the type of event from text content."""
        text_lower = text.lower()
        max_confidence = 0.0
        detected_type = 'general'
        
        for event_type, patterns in self.event_patterns.items():
            confidence = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                if matches > 0:
                    confidence += min(matches * 0.3, 0.9)  # Cap confidence per pattern
            
            if confidence > max_confidence:
                max_confidence = confidence
                detected_type = event_type
        
        return detected_type, max_confidence
    
    def detect_event_category(self, text: str, entities: List[ExtractedEntity]) -> Tuple[str, float]:
        """Detect the category of event from text and entities."""
        text_lower = text.lower()
        max_confidence = 0.0
        detected_category = 'general'
        
        for category, keywords in self.category_keywords.items():
            confidence = 0.0
            
            # Check keywords in text
            for keyword in keywords:
                if keyword in text_lower:
                    confidence += 0.2
            
            # Check entity types
            entity_types = [ent.label for ent in entities]
            if category == 'politics' and 'ORG' in entity_types:
                confidence += 0.3
            elif category == 'health' and 'PERSON' in entity_types:
                confidence += 0.2
            elif category == 'technology' and 'ORG' in entity_types:
                confidence += 0.2
            
            if confidence > max_confidence:
                max_confidence = confidence
                detected_category = category
        
        return detected_category, max_confidence
    
    def extract_temporal_indicators(self, text: str) -> List[str]:
        """Extract temporal indicators from text."""
        text_lower = text.lower()
        indicators = []
        
        for indicator in self.temporal_indicators:
            if indicator in text_lower:
                indicators.append(indicator)
        
        # Extract dates and times
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',  # MM/DD/YYYY
            r'\b\d{4}-\d{2}-\d{2}\b',      # YYYY-MM-DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'  # Month DD, YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            indicators.extend(matches)
        
        return indicators
    
    def extract_geographic_indicators(self, text: str, entities: List[ExtractedEntity]) -> List[str]:
        """Extract geographic indicators from text and entities."""
        indicators = []
        
        # Extract from entities
        for entity in entities:
            if entity.label in ['GPE', 'LOC']:
                indicators.append(entity.text)
        
        # Extract from text patterns
        text_lower = text.lower()
        for indicator in self.geographic_indicators:
            if indicator in text_lower:
                # Look for location names after geographic indicators
                location_pattern = rf'\b{indicator}\s+([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b'
                matches = re.findall(location_pattern, text)
                indicators.extend(matches)
        
        return indicators
    
    def group_entities_by_type(self, entities: List[ExtractedEntity]) -> Dict[str, List[str]]:
        """Group extracted entities by their type."""
        grouped = defaultdict(list)
        
        for entity in entities:
            grouped[entity.label].append(entity.text)
        
        # Remove duplicates while preserving order
        for label in grouped:
            seen = set()
            unique_entities = []
            for entity in grouped[label]:
                if entity not in seen:
                    seen.add(entity)
                    unique_entities.append(entity)
            grouped[label] = unique_entities
        
        return dict(grouped)
    
    def detect_event_candidates(self, articles: List[Dict]) -> List[EventCandidate]:
        """Detect potential events from a list of articles."""
        event_candidates = []
        
        for article in articles:
            # Extract entities
            entities = self.extract_entities(article.get('content', ''))
            
            # Detect event type and category
            event_type, type_confidence = self.detect_event_type(article.get('title', ''))
            event_category, category_confidence = self.detect_event_category(
                article.get('content', ''), entities
            )
            
            # Extract temporal and geographic indicators
            temporal_indicators = self.extract_temporal_indicators(article.get('content', ''))
            geographic_indicators = self.extract_geographic_indicators(
                article.get('content', ''), entities
            )
            
            # Group entities by type
            grouped_entities = self.group_entities_by_type(entities)
            
            # Extract keywords (simple approach - can be enhanced)
            content_words = article.get('content', '').lower().split()
            keywords = [word for word in content_words if len(word) > 4 and word.isalpha()]
            keyword_freq = Counter(keywords)
            top_keywords = [word for word, freq in keyword_freq.most_common(10)]
            
            # Calculate overall confidence
            overall_confidence = (type_confidence + category_confidence) / 2
            
            # Create event candidate
            candidate = EventCandidate(
                event_name=article.get('title', '')[:100],  # Truncate if too long
                event_type=event_type,
                event_category=event_category,
                confidence=overall_confidence,
                source_articles=[article.get('id')],
                entities=grouped_entities,
                keywords=top_keywords,
                temporal_indicators=temporal_indicators,
                geographic_indicators=geographic_indicators
            )
            
            event_candidates.append(candidate)
        
        return event_candidates
    
    def merge_similar_events(self, candidates: List[EventCandidate]) -> List[EventCandidate]:
        """Merge similar event candidates based on entity overlap and keywords."""
        if not candidates:
            return []
        
        merged = []
        processed = set()
        
        for i, candidate in enumerate(candidates):
            if i in processed:
                continue
            
            similar_group = [candidate]
            processed.add(i)
            
            # Find similar candidates
            for j, other_candidate in enumerate(candidates[i+1:], i+1):
                if j in processed:
                    continue
                
                # Calculate similarity score
                similarity = self._calculate_event_similarity(candidate, other_candidate)
                
                if similarity > 0.6:  # Threshold for merging
                    similar_group.append(other_candidate)
                    processed.add(j)
            
            # Merge the group
            if len(similar_group) > 1:
                merged_candidate = self._merge_event_candidates(similar_group)
                merged.append(merged_candidate)
            else:
                merged.append(candidate)
        
        return merged
    
    def _calculate_event_similarity(self, candidate1: EventCandidate, candidate2: EventCandidate) -> float:
        """Calculate similarity between two event candidates."""
        similarity_score = 0.0
        
        # Entity overlap
        entity_overlap = 0.0
        for entity_type in set(candidate1.entities.keys()) | set(candidate2.entities.keys()):
            entities1 = set(candidate1.entities.get(entity_type, []))
            entities2 = set(candidate2.entities.get(entity_type, []))
            
            if entities1 and entities2:
                intersection = len(entities1 & entities2)
                union = len(entities1 | entities2)
                if union > 0:
                    entity_overlap += intersection / union
        
        if entity_overlap > 0:
            similarity_score += entity_overlap * 0.4
        
        # Keyword overlap
        keyword_overlap = 0.0
        keywords1 = set(candidate1.keywords)
        keywords2 = set(candidate2.keywords)
        
        if keywords1 and keywords2:
            intersection = len(keywords1 & keywords2)
            union = len(keywords1 | keywords2)
            if union > 0:
                keyword_overlap = intersection / union
                similarity_score += keyword_overlap * 0.3
        
        # Category and type similarity
        if candidate1.event_category == candidate2.event_category:
            similarity_score += 0.2
        
        if candidate1.event_type == candidate2.event_type:
            similarity_score += 0.1
        
        return min(similarity_score, 1.0)
    
    def _merge_event_candidates(self, candidates: List[EventCandidate]) -> EventCandidate:
        """Merge multiple event candidates into one."""
        if not candidates:
            raise ValueError("Cannot merge empty list of candidates")
        
        if len(candidates) == 1:
            return candidates[0]
        
        # Merge basic fields
        merged = EventCandidate(
            event_name=candidates[0].event_name,  # Use first candidate's name
            event_type=candidates[0].event_type,
            event_category=candidates[0].event_category,
            confidence=sum(c.confidence for c in candidates) / len(candidates),
            source_articles=[],
            entities=defaultdict(list),
            keywords=[],
            temporal_indicators=[],
            geographic_indicators=[]
        )
        
        # Merge source articles
        for candidate in candidates:
            merged.source_articles.extend(candidate.source_articles)
        
        # Merge entities
        for candidate in candidates:
            for entity_type, entities in candidate.entities.items():
                merged.entities[entity_type].extend(entities)
        
        # Remove duplicate entities
        for entity_type in merged.entities:
            merged.entities[entity_type] = list(set(merged.entities[entity_type]))
        
        # Merge keywords
        all_keywords = []
        for candidate in candidates:
            all_keywords.extend(candidate.keywords)
        
        keyword_freq = Counter(all_keywords)
        merged.keywords = [word for word, freq in keyword_freq.most_common(15)]
        
        # Merge temporal and geographic indicators
        for candidate in candidates:
            merged.temporal_indicators.extend(candidate.temporal_indicators)
            merged.geographic_indicators.extend(candidate.geographic_indicators)
        
        # Remove duplicates
        merged.temporal_indicators = list(set(merged.temporal_indicators))
        merged.geographic_indicators = list(set(merged.geographic_indicators))
        
        return merged
    
    def process_articles_for_events(self, article_ids: List[int] = None) -> List[EventCandidate]:
        """Process articles to detect and extract events."""
        conn = self._get_db_connection()
        if not conn:
            logger.error("Failed to connect to database")
            return []
        
        try:
            # Get articles to process
            if article_ids:
                placeholders = ','.join(['%s'] * len(article_ids))
                query = f"""
                    SELECT id, title, content, published_date, created_at
                    FROM articles 
                    WHERE id IN ({placeholders})
                    AND processing_status = 'raw'
                    ORDER BY published_date DESC
                """
                cursor = conn.cursor()
                cursor.execute(query, article_ids)
            else:
                query = """
                    SELECT id, title, content, published_date, created_at
                    FROM articles 
                    WHERE processing_status = 'raw'
                    ORDER BY published_date DESC
                    LIMIT 100
                """
                cursor = conn.cursor()
                cursor.execute(query)
            
            articles = []
            for row in cursor.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'published_date': row[3],
                    'created_at': row[4]
                })
            
            cursor.close()
            
            if not articles:
                logger.info("No raw articles found for event detection")
                return []
            
            logger.info(f"Processing {len(articles)} articles for event detection")
            
            # Detect event candidates
            candidates = self.detect_event_candidates(articles)
            logger.info(f"Detected {len(candidates)} event candidates")
            
            # Merge similar events
            merged_candidates = self.merge_similar_events(candidates)
            logger.info(f"Merged into {len(merged_candidates)} unique events")
            
            return merged_candidates
            
        except psycopg2.Error as e:
            logger.error(f"Database error during event detection: {e}")
            return []
        finally:
            self._close_db_connection(conn)
    
    def save_events_to_database(self, events: List[EventCandidate]) -> bool:
        """Save detected events to the database."""
        conn = self._get_db_connection()
        if not conn:
            logger.error("Failed to connect to database")
            return False
        
        try:
            cursor = conn.cursor()
            
            for event in events:
                # Insert event
                event_query = """
                    INSERT INTO events (
                        event_name, event_type, event_category, event_description,
                        event_keywords, event_entities, event_importance_score,
                        event_start_date, is_ongoing, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING event_id
                """
                
                event_data = (
                    event.event_name,
                    event.event_type,
                    event.event_category,
                    f"Event detected from {len(event.source_articles)} articles",
                    event.keywords,
                    json.dumps(event.entities),
                    event.confidence,
                    datetime.now(),
                    True,
                    datetime.now(),
                    datetime.now()
                )
                
                cursor.execute(event_query, event_data)
                event_id = cursor.fetchone()[0]
                
                # Update articles with event_id
                if event.source_articles:
                    placeholders = ','.join(['%s'] * len(event.source_articles))
                    update_query = f"""
                        UPDATE articles 
                        SET event_id = %s, 
                            processing_status = 'processing',
                            processing_started_at = %s,
                            location_entities = %s,
                            person_entities = %s,
                            organization_entities = %s,
                            event_confidence = %s
                        WHERE id IN ({placeholders})
                    """
                    
                    update_data = (
                        event_id,
                        datetime.now(),
                        json.dumps(event.entities.get('GPE', [])),
                        json.dumps(event.entities.get('PERSON', [])),
                        json.dumps(event.entities.get('ORG', [])),
                        event.confidence,
                        *event.source_articles
                    )
                    
                    cursor.execute(update_query, update_data)
                
                # Create timeline entry
                timeline_query = """
                    INSERT INTO event_timeline_entries (
                        event_id, entry_type, entry_title, entry_description,
                        entry_timestamp, entry_order, source_article_ids,
                        entry_entities, entry_keywords, entry_impact_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                timeline_data = (
                    event_id,
                    'milestone',
                    f"Event detected: {event.event_name}",
                    f"Event detected from {len(event.source_articles)} articles with confidence {event.confidence:.2f}",
                    datetime.now(),
                    1,
                    event.source_articles,
                    json.dumps(event.entities),
                    event.keywords,
                    event.confidence
                )
                
                cursor.execute(timeline_query, timeline_data)
            
            conn.commit()
            logger.info(f"Successfully saved {len(events)} events to database")
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database error during event saving: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db_connection(conn)

def main():
    """Main function for testing the enhanced entity extractor."""
    extractor = EnhancedEntityExtractor()
    
    # Test with sample articles
    sample_articles = [
        {
            'id': 1,
            'title': 'Breaking: Major Tech Company Announces New AI Initiative',
            'content': 'A major technology corporation has announced a groundbreaking new artificial intelligence initiative today. The company, based in Silicon Valley, revealed plans to invest $1 billion in AI research and development.',
            'published_date': datetime.now(),
            'created_at': datetime.now()
        },
        {
            'id': 2,
            'title': 'Tech Giant Launches Revolutionary AI Platform',
            'content': 'The same technology company has launched its revolutionary AI platform, marking a significant milestone in artificial intelligence development. Industry experts are calling this a game-changer.',
            'published_date': datetime.now(),
            'created_at': datetime.now()
        }
    ]
    
    print("Testing Enhanced Entity Extractor...")
    
    # Extract entities
    for article in sample_articles:
        print(f"\nArticle: {article['title']}")
        entities = extractor.extract_entities(article['content'])
        print(f"Extracted {len(entities)} entities:")
        for entity in entities:
            print(f"  - {entity.text} ({entity.label}) - Confidence: {entity.confidence:.2f}")
    
    # Detect events
    print("\n\nDetecting events...")
    events = extractor.detect_event_candidates(sample_articles)
    print(f"Detected {len(events)} event candidates:")
    
    for event in events:
        print(f"\nEvent: {event.event_name}")
        print(f"  Type: {event.event_type}")
        print(f"  Category: {event.event_category}")
        print(f"  Confidence: {event.confidence:.2f}")
        print(f"  Source Articles: {len(event.source_articles)}")
        print(f"  Entities: {dict(event.entities)}")
        print(f"  Keywords: {event.keywords[:5]}...")

if __name__ == "__main__":
    main()
