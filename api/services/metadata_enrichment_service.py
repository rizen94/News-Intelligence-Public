"""
Metadata Enrichment Service for News Intelligence System v3.0
Language detection, translation, categorization, and geography tagging
"""

import asyncio
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# Try to import language detection and translation libraries
try:
    import langdetect
    from langdetect import detect, DetectorFactory
    LANGDETECT_AVAILABLE = True
    # Set seed for consistent results
    DetectorFactory.seed = 0
except ImportError:
    LANGDETECT_AVAILABLE = False
    logging.warning("langdetect not available - using basic language detection")

try:
    from googletrans import Translator
    GOOGLETRANS_AVAILABLE = True
except ImportError:
    GOOGLETRANS_AVAILABLE = False
    logging.warning("googletrans not available - translation disabled")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logging.warning("spacy not available - using basic entity extraction")

from database.connection import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class EnrichmentResult:
    """Result of metadata enrichment"""
    language: str
    detected_language: str
    is_translated: bool
    categories: List[str]
    geography: List[str]
    entities: List[Dict[str, Any]]
    sentiment_score: float
    quality_score: float
    enrichment_status: str

class MetadataEnrichmentService:
    """Service for enriching article metadata with language, categories, geography, and entities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.translator = None
        self.nlp_model = None
        
        # Initialize language detection
        if LANGDETECT_AVAILABLE:
            self.logger.info("Language detection initialized")
        else:
            self.logger.warning("Language detection not available - using basic detection")
        
        # Initialize translation
        if GOOGLETRANS_AVAILABLE:
            try:
                self.translator = Translator()
                self.logger.info("Translation service initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize translator: {e}")
                self.translator = None
        
        # Initialize spaCy for entity extraction
        if SPACY_AVAILABLE:
            try:
                self.nlp_model = spacy.load("en_core_web_sm")
                self.logger.info("spaCy model loaded successfully")
            except OSError:
                self.logger.warning("spaCy English model not found - using basic entity extraction")
                self.nlp_model = None
            except Exception as e:
                self.logger.error(f"Failed to load spaCy model: {e}")
                self.nlp_model = None
        
        # Category keywords for classification
        self.category_keywords = {
            "politics": [
                "election", "government", "policy", "legislation", "congress", "senate",
                "parliament", "democracy", "voting", "president", "prime minister",
                "political", "campaign", "candidate", "vote", "ballot", "election",
                "political party", "cabinet", "minister", "mayor", "governor"
            ],
            "economy": [
                "economy", "economic", "financial", "market", "business", "trade",
                "inflation", "gdp", "unemployment", "recession", "growth", "fiscal",
                "monetary", "bank", "investment", "stock", "currency", "dollar",
                "euro", "yen", "bitcoin", "cryptocurrency", "banking", "finance"
            ],
            "technology": [
                "tech", "technology", "innovation", "ai", "artificial intelligence",
                "cybersecurity", "digital", "software", "hardware", "computer",
                "internet", "data", "algorithm", "machine learning", "blockchain",
                "startup", "app", "platform", "cloud", "database", "programming"
            ],
            "climate": [
                "climate", "environment", "carbon", "renewable", "sustainability",
                "green", "emissions", "global warming", "climate change", "pollution",
                "energy", "solar", "wind", "fossil fuel", "carbon footprint",
                "renewable energy", "clean energy", "environmental", "ecosystem"
            ],
            "world": [
                "international", "global", "world", "foreign", "diplomacy", "conflict",
                "peace", "treaty", "summit", "united nations", "international",
                "global", "worldwide", "overseas", "international relations",
                "embassy", "consulate", "diplomatic", "multilateral"
            ],
            "business": [
                "business", "corporate", "company", "industry", "market", "finance",
                "investment", "merger", "acquisition", "revenue", "profit", "earnings",
                "ceo", "executive", "board", "shareholder", "ipo", "venture capital"
            ],
            "health": [
                "health", "medical", "healthcare", "medicine", "doctor", "hospital",
                "patient", "disease", "virus", "pandemic", "vaccine", "treatment",
                "pharmaceutical", "drug", "clinical", "research", "study"
            ],
            "science": [
                "science", "research", "study", "discovery", "experiment", "laboratory",
                "scientist", "research", "innovation", "breakthrough", "findings",
                "peer review", "journal", "publication", "academic"
            ]
        }
        
        # Geography patterns
        self.geography_patterns = {
            "countries": [
                "united states", "usa", "america", "canada", "mexico", "brazil",
                "united kingdom", "uk", "britain", "france", "germany", "italy",
                "spain", "russia", "china", "japan", "india", "australia",
                "south korea", "north korea", "iran", "israel", "saudi arabia",
                "egypt", "south africa", "nigeria", "kenya", "ethiopia"
            ],
            "regions": [
                "europe", "asia", "africa", "americas", "middle east", "southeast asia",
                "eastern europe", "western europe", "north america", "south america",
                "central america", "caribbean", "pacific", "atlantic", "arctic"
            ],
            "cities": [
                "new york", "london", "paris", "berlin", "tokyo", "beijing",
                "moscow", "mumbai", "delhi", "sydney", "melbourne", "toronto",
                "vancouver", "mexico city", "sao paulo", "buenos aires"
            ]
        }
    
    async def enrich_article(self, article_id: int) -> EnrichmentResult:
        """Enrich a single article with metadata"""
        try:
            # Get article data
            article = await self._get_article(article_id)
            if not article:
                return EnrichmentResult(
                    language="en", detected_language="en", is_translated=False,
                    categories=[], geography=[], entities=[], sentiment_score=0.0,
                    quality_score=0.0, enrichment_status="error"
                )
            
            # Detect language
            detected_language = await self._detect_language(article["content"])
            
            # Translate if necessary
            translated_content = article["content"]
            is_translated = False
            if detected_language != "en" and self.translator:
                translated_content = await self._translate_text(article["content"], detected_language, "en")
                is_translated = True
            
            # Extract categories
            categories = await self._extract_categories(translated_content)
            
            # Extract geography
            geography = await self._extract_geography(translated_content)
            
            # Extract entities
            entities = await self._extract_entities(translated_content)
            
            # Calculate sentiment
            sentiment_score = await self._calculate_sentiment(translated_content)
            
            # Calculate quality score
            quality_score = await self._calculate_quality_score(article, translated_content)
            
            # Update article in database
            await self._update_article_metadata(
                article_id, detected_language, is_translated, categories,
                geography, entities, sentiment_score, quality_score
            )
            
            return EnrichmentResult(
                language=article["language"],
                detected_language=detected_language,
                is_translated=is_translated,
                categories=categories,
                geography=geography,
                entities=entities,
                sentiment_score=sentiment_score,
                quality_score=quality_score,
                enrichment_status="completed"
            )
            
        except Exception as e:
            self.logger.error(f"Error enriching article {article_id}: {e}")
            return EnrichmentResult(
                language="en", detected_language="en", is_translated=False,
                categories=[], geography=[], entities=[], sentiment_score=0.0,
                quality_score=0.0, enrichment_status="error"
            )
    
    async def batch_enrich_articles(self, article_ids: List[int]) -> List[EnrichmentResult]:
        """Enrich multiple articles in batch"""
        try:
            tasks = []
            for article_id in article_ids:
                task = asyncio.create_task(self.enrich_article(article_id))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error enriching article {article_ids[i]}: {result}")
                    processed_results.append(EnrichmentResult(
                        language="en", detected_language="en", is_translated=False,
                        categories=[], geography=[], entities=[], sentiment_score=0.0,
                        quality_score=0.0, enrichment_status="error"
                    ))
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            self.logger.error(f"Error in batch enrichment: {e}")
            return []
    
    async def _get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article data from database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                result = db.execute(text("""
                    SELECT id, title, content, language, source, created_at
                    FROM articles 
                    WHERE id = :article_id
                """), {"article_id": article_id}).fetchone()
                
                if result:
                    return {
                        "id": result[0],
                        "title": result[1],
                        "content": result[2],
                        "language": result[3],
                        "source": result[4],
                        "created_at": result[5]
                    }
                return None
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting article {article_id}: {e}")
            return None
    
    async def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            if not text or len(text.strip()) < 10:
                return "en"  # Default to English for very short text
            
            if LANGDETECT_AVAILABLE:
                try:
                    detected = detect(text)
                    return detected
                except Exception as e:
                    self.logger.warning(f"Language detection failed: {e}")
                    return "en"
            else:
                # Basic language detection based on common words
                return self._basic_language_detection(text)
                
        except Exception as e:
            self.logger.error(f"Error detecting language: {e}")
            return "en"
    
    def _basic_language_detection(self, text: str) -> str:
        """Basic language detection using common words"""
        text_lower = text.lower()
        
        # English common words
        english_words = ["the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"]
        # Spanish common words
        spanish_words = ["el", "la", "de", "que", "y", "a", "en", "un", "es", "se", "no", "te", "lo", "le"]
        # French common words
        french_words = ["le", "la", "de", "et", "à", "un", "il", "être", "et", "en", "avoir", "que", "pour"]
        
        english_count = sum(1 for word in english_words if word in text_lower)
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        french_count = sum(1 for word in french_words if word in text_lower)
        
        if spanish_count > english_count and spanish_count > french_count:
            return "es"
        elif french_count > english_count and french_count > spanish_count:
            return "fr"
        else:
            return "en"
    
    async def _translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source language to target language"""
        try:
            if not self.translator or source_lang == target_lang:
                return text
            
            # Translate in chunks to avoid API limits
            max_chunk_size = 4000
            if len(text) <= max_chunk_size:
                result = self.translator.translate(text, src=source_lang, dest=target_lang)
                return result.text
            else:
                # Split into chunks and translate
                chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
                translated_chunks = []
                
                for chunk in chunks:
                    result = self.translator.translate(chunk, src=source_lang, dest=target_lang)
                    translated_chunks.append(result.text)
                
                return " ".join(translated_chunks)
                
        except Exception as e:
            self.logger.warning(f"Translation failed: {e}")
            return text
    
    async def _extract_categories(self, text: str) -> List[str]:
        """Extract categories from text"""
        try:
            text_lower = text.lower()
            categories = []
            
            for category, keywords in self.category_keywords.items():
                # Check if any keywords match
                matches = sum(1 for keyword in keywords if keyword in text_lower)
                if matches >= 2:  # Require at least 2 keyword matches
                    categories.append(category)
            
            return categories
            
        except Exception as e:
            self.logger.error(f"Error extracting categories: {e}")
            return []
    
    async def _extract_geography(self, text: str) -> List[str]:
        """Extract geographical entities from text"""
        try:
            text_lower = text.lower()
            geography = []
            
            # Check for countries
            for country in self.geography_patterns["countries"]:
                if country in text_lower:
                    geography.append(country.title())
            
            # Check for regions
            for region in self.geography_patterns["regions"]:
                if region in text_lower:
                    geography.append(region.title())
            
            # Check for cities
            for city in self.geography_patterns["cities"]:
                if city in text_lower:
                    geography.append(city.title())
            
            # Remove duplicates and return
            return list(set(geography))
            
        except Exception as e:
            self.logger.error(f"Error extracting geography: {e}")
            return []
    
    async def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract named entities from text"""
        try:
            if self.nlp_model:
                return await self._extract_entities_spacy(text)
            else:
                return await self._extract_entities_basic(text)
                
        except Exception as e:
            self.logger.error(f"Error extracting entities: {e}")
            return []
    
    async def _extract_entities_spacy(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using spaCy"""
        try:
            doc = self.nlp_model(text)
            entities = []
            
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "confidence": 1.0  # spaCy doesn't provide confidence scores
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"Error in spaCy entity extraction: {e}")
            return []
    
    async def _extract_entities_basic(self, text: str) -> List[Dict[str, Any]]:
        """Basic entity extraction using regex patterns"""
        try:
            entities = []
            
            # Person names (capitalized words)
            person_pattern = r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'
            persons = re.findall(person_pattern, text)
            for person in persons:
                entities.append({
                    "text": person,
                    "label": "PERSON",
                    "confidence": 0.7
                })
            
            # Organizations (words ending in Corp, Inc, Ltd, etc.)
            org_pattern = r'\b[A-Z][a-zA-Z\s]+(?:Corp|Inc|Ltd|LLC|Company|Organization)\b'
            orgs = re.findall(org_pattern, text)
            for org in orgs:
                entities.append({
                    "text": org,
                    "label": "ORG",
                    "confidence": 0.8
                })
            
            # Locations (already extracted in geography)
            for location in await self._extract_geography(text):
                entities.append({
                    "text": location,
                    "label": "GPE",
                    "confidence": 0.9
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"Error in basic entity extraction: {e}")
            return []
    
    async def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score for text"""
        try:
            # Basic sentiment analysis using word lists
            positive_words = [
                "good", "great", "excellent", "amazing", "wonderful", "fantastic",
                "positive", "success", "win", "victory", "achievement", "progress",
                "improvement", "growth", "increase", "rise", "gain", "benefit"
            ]
            
            negative_words = [
                "bad", "terrible", "awful", "horrible", "disaster", "crisis",
                "negative", "failure", "loss", "defeat", "decline", "decrease",
                "fall", "drop", "problem", "issue", "concern", "worry", "threat"
            ]
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            total_words = len(text.split())
            if total_words == 0:
                return 0.0
            
            # Calculate sentiment score (-1 to 1)
            sentiment = (positive_count - negative_count) / total_words
            return max(-1.0, min(1.0, sentiment * 10))  # Scale and clamp
            
        except Exception as e:
            self.logger.error(f"Error calculating sentiment: {e}")
            return 0.0
    
    async def _calculate_quality_score(self, article: Dict[str, Any], content: str) -> float:
        """Calculate quality score for article"""
        try:
            score = 0.0
            
            # Length score (0-0.3)
            content_length = len(content)
            if content_length > 1000:
                score += 0.3
            elif content_length > 500:
                score += 0.2
            elif content_length > 200:
                score += 0.1
            
            # Source tier score (0-0.3)
            source_tier = article.get("source_tier", 2)
            if source_tier == 1:  # Wire services
                score += 0.3
            elif source_tier == 2:  # Institutions
                score += 0.2
            else:  # Specialized
                score += 0.1
            
            # Content quality indicators (0-0.4)
            quality_indicators = [
                "according to", "reported", "sources say", "officials", "experts",
                "research", "study", "data", "statistics", "analysis"
            ]
            
            content_lower = content.lower()
            indicator_count = sum(1 for indicator in quality_indicators if indicator in content_lower)
            score += min(0.4, indicator_count * 0.05)
            
            return min(1.0, score)
            
        except Exception as e:
            self.logger.error(f"Error calculating quality score: {e}")
            return 0.5
    
    async def _update_article_metadata(self, article_id: int, detected_language: str,
                                     is_translated: bool, categories: List[str],
                                     geography: List[str], entities: List[Dict[str, Any]],
                                     sentiment_score: float, quality_score: float):
        """Update article with enriched metadata"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                db.execute(text("""
                    UPDATE articles 
                    SET detected_language = :detected_language,
                        is_translated = :is_translated,
                        categories = :categories,
                        geography = :geography,
                        entities = :entities,
                        sentiment_score = :sentiment_score,
                        quality_score = :quality_score,
                        enrichment_status = 'completed'
                    WHERE id = :article_id
                """), {
                    "article_id": article_id,
                    "detected_language": detected_language,
                    "is_translated": is_translated,
                    "categories": json.dumps(categories),
                    "geography": json.dumps(geography),
                    "entities": json.dumps(entities),
                    "sentiment_score": sentiment_score,
                    "quality_score": quality_score
                })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating article metadata: {e}")

# Global enrichment service instance
_enrichment_service = None

async def get_enrichment_service() -> MetadataEnrichmentService:
    """Get or create global enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = MetadataEnrichmentService()
    return _enrichment_service


