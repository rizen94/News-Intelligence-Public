#!/usr/bin/env python3
"""
Language Detector for News Intelligence System v2.5.0
Identifies article language and filters content for processing
"""
import os
import sys
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from langdetect import detect, detect_langs, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("Warning: langdetect not available. Using basic language detection.")

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False
    print("Warning: chardet not available. Using basic encoding detection.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LanguageResult:
    """Result of language detection operation."""
    detected_language: str
    confidence_score: float
    alternative_languages: List[Tuple[str, float]]
    is_english: bool
    is_reliable: bool
    detection_method: str
    processing_recommendation: str
    timestamp: datetime

class LanguageDetector:
    """
    Advanced language detection system that:
    - Detects article language with confidence scoring
    - Filters content for English articles
    - Provides fallback detection methods
    - Supports multi-language content analysis
    """
    
    def __init__(self, config: Dict = None):
        """Initialize the language detector."""
        self.config = config or {
            'primary_language': 'en',
            'min_confidence': 0.6,
            'supported_languages': ['en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'ru', 'ja', 'zh'],
            'english_variants': ['en', 'en-US', 'en-GB', 'en-CA', 'en-AU'],
            'fallback_patterns': {
                'en': [
                    r'\b(the|and|or|but|in|on|at|to|for|of|with|by)\b',
                    r'\b(is|are|was|were|be|been|being|have|has|had|do|does|did)\b',
                    r'\b(this|that|these|those|it|they|them|their|we|us|our)\b'
                ],
                'es': [
                    r'\b(el|la|los|las|de|del|en|con|por|para|sin|sobre|entre)\b',
                    r'\b(es|son|era|eran|está|están|tiene|tienen|hay|hace|hacen)\b'
                ],
                'fr': [
                    r'\b(le|la|les|de|du|des|en|avec|par|pour|sans|sur|entre)\b',
                    r'\b(est|sont|était|étaient|a|ont|il y a|fait|font)\b'
                ],
                'de': [
                    r'\b(der|die|das|den|dem|des|in|mit|von|für|ohne|auf|zwischen)\b',
                    r'\b(ist|sind|war|waren|hat|haben|es gibt|macht|machen)\b'
                ]
            }
        }
        
        # Language-specific word patterns for fallback detection
        self.language_patterns = self.config['fallback_patterns']
        
        # Common language indicators
        self.language_indicators = {
            'en': ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'],
            'es': ['el', 'la', 'los', 'las', 'de', 'del', 'en', 'con', 'por', 'para'],
            'fr': ['le', 'la', 'les', 'de', 'du', 'des', 'en', 'avec', 'par', 'pour'],
            'de': ['der', 'die', 'das', 'den', 'dem', 'des', 'in', 'mit', 'von', 'für']
        }
    
    def detect_language(self, text: str, url: str = None) -> LanguageResult:
        """
        Detect the language of the given text.
        
        Args:
            text: Text content to analyze
            url: URL for additional context (optional)
            
        Returns:
            LanguageResult with detection details
        """
        if not text or len(text.strip()) < 10:
            return LanguageResult(
                detected_language='unknown',
                confidence_score=0.0,
                alternative_languages=[],
                is_english=False,
                is_reliable=False,
                detection_method='insufficient_text',
                processing_recommendation='skip',
                timestamp=datetime.now()
            )
        
        # Clean and prepare text for detection
        cleaned_text = self._prepare_text_for_detection(text)
        
        # Try primary detection method
        if LANGDETECT_AVAILABLE:
            try:
                primary_result = self._detect_with_langdetect(cleaned_text)
                if primary_result.is_reliable:
                    return primary_result
            except Exception as e:
                logger.warning(f"Primary language detection failed: {e}")
        
        # Fallback to pattern-based detection
        fallback_result = self._detect_with_patterns(cleaned_text)
        
        # Combine results if possible
        if LANGDETECT_AVAILABLE:
            try:
                combined_result = self._combine_detection_results(
                    primary_result, fallback_result
                )
                return combined_result
            except Exception as e:
                logger.warning(f"Combined detection failed: {e}")
        
        return fallback_result
    
    def _prepare_text_for_detection(self, text: str) -> str:
        """Prepare text for language detection."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might interfere
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\']', ' ', text)
        
        # Extract meaningful text (first 1000 characters)
        words = text.split()
        if len(words) > 200:
            text = ' '.join(words[:200])
        
        return text.strip()
    
    def _detect_with_langdetect(self, text: str) -> LanguageResult:
        """Detect language using langdetect library."""
        try:
            # Detect primary language
            primary_lang = detect(text)
            
            # Get confidence scores for all detected languages
            detected_langs = detect_langs(text)
            
            # Find confidence for primary language
            primary_confidence = 0.0
            alternative_languages = []
            
            for lang, confidence in detected_langs:
                if lang == primary_lang:
                    primary_confidence = confidence
                else:
                    alternative_languages.append((lang, confidence))
            
            # Sort alternatives by confidence
            alternative_languages.sort(key=lambda x: x[1], reverse=True)
            
            # Determine if result is reliable
            is_reliable = primary_confidence >= self.config['min_confidence']
            
            # Check if it's English
            is_english = primary_lang in self.config['english_variants']
            
            # Determine processing recommendation
            if is_english and is_reliable:
                recommendation = 'process'
            elif is_english and not is_reliable:
                recommendation = 'review'
            elif not is_english:
                recommendation = 'skip'
            else:
                recommendation = 'review'
            
            return LanguageResult(
                detected_language=primary_lang,
                confidence_score=primary_confidence,
                alternative_languages=alternative_languages,
                is_english=is_english,
                is_reliable=is_reliable,
                detection_method='langdetect',
                processing_recommendation=recommendation,
                timestamp=datetime.now()
            )
            
        except LangDetectException as e:
            logger.warning(f"LangDetect exception: {e}")
            return LanguageResult(
                detected_language='unknown',
                confidence_score=0.0,
                alternative_languages=[],
                is_english=False,
                is_reliable=False,
                detection_method='langdetect_failed',
                processing_recommendation='fallback',
                timestamp=datetime.now()
            )
    
    def _detect_with_patterns(self, text: str) -> LanguageResult:
        """Detect language using pattern matching."""
        text_lower = text.lower()
        words = text_lower.split()
        
        # Count language-specific patterns
        language_scores = {}
        
        for lang, patterns in self.language_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            
            # Normalize score by text length
            if len(words) > 0:
                language_scores[lang] = score / len(words)
            else:
                language_scores[lang] = 0.0
        
        # Find best matching language
        if language_scores:
            best_lang = max(language_scores.items(), key=lambda x: x[1])
            detected_lang = best_lang[0]
            confidence = min(best_lang[1] * 10, 1.0)  # Scale confidence
        else:
            detected_lang = 'unknown'
            confidence = 0.0
        
        # Check if it's English
        is_english = detected_lang in self.config['english_variants']
        
        # Determine reliability
        is_reliable = confidence >= self.config['min_confidence']
        
        # Determine processing recommendation
        if is_english and is_reliable:
            recommendation = 'process'
        elif is_english and not is_reliable:
            recommendation = 'review'
        elif not is_english:
            recommendation = 'skip'
        else:
            recommendation = 'review'
        
        return LanguageResult(
            detected_language=detected_lang,
            confidence_score=confidence,
            alternative_languages=[(lang, score) for lang, score in language_scores.items() if lang != detected_lang],
            is_english=is_english,
            is_reliable=is_reliable,
            detection_method='pattern_matching',
            processing_recommendation=recommendation,
            timestamp=datetime.now()
        )
    
    def _combine_detection_results(self, primary: LanguageResult, fallback: LanguageResult) -> LanguageResult:
        """Combine results from multiple detection methods."""
        # If primary detection is reliable, use it
        if primary.is_reliable:
            return primary
        
        # If fallback is more confident, use it
        if fallback.confidence_score > primary.confidence_score:
            return fallback
        
        # Otherwise, use primary but mark as less reliable
        return LanguageResult(
            detected_language=primary.detected_language,
            confidence_score=primary.confidence_score * 0.8,  # Reduce confidence
            alternative_languages=primary.alternative_languages,
            is_english=primary.is_english,
            is_reliable=False,
            detection_method='combined',
            processing_recommendation='review',
            timestamp=datetime.now()
        )
    
    def batch_detect_languages(self, texts: List[str], urls: List[str] = None) -> List[LanguageResult]:
        """Detect languages for multiple texts."""
        if urls is None:
            urls = [None] * len(texts)
        
        results = []
        for text, url in zip(texts, urls):
            try:
                result = self.detect_language(text, url)
                results.append(result)
            except Exception as e:
                logger.error(f"Language detection failed for text: {e}")
                # Create fallback result
                fallback_result = LanguageResult(
                    detected_language='unknown',
                    confidence_score=0.0,
                    alternative_languages=[],
                    is_english=False,
                    is_reliable=False,
                    detection_method='error',
                    processing_recommendation='skip',
                    timestamp=datetime.now()
                )
                results.append(fallback_result)
        
        return results
    
    def get_language_statistics(self, results: List[LanguageResult]) -> Dict:
        """Get statistics from language detection results."""
        if not results:
            return {}
        
        total_articles = len(results)
        english_articles = sum(1 for r in results if r.is_english)
        reliable_detections = sum(1 for r in results if r.is_reliable)
        
        language_counts = {}
        confidence_scores = []
        
        for result in results:
            lang = result.detected_language
            language_counts[lang] = language_counts.get(lang, 0) + 1
            confidence_scores.append(result.confidence_score)
        
        # Sort languages by frequency
        sorted_languages = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_articles': total_articles,
            'english_articles': english_articles,
            'english_percentage': (english_articles / total_articles) * 100 if total_articles > 0 else 0,
            'reliable_detections': reliable_detections,
            'reliability_percentage': (reliable_detections / total_articles) * 100 if total_articles > 0 else 0,
            'language_distribution': sorted_languages,
            'average_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            'detection_methods': {
                'langdetect': sum(1 for r in results if 'langdetect' in r.detection_method),
                'pattern_matching': sum(1 for r in results if 'pattern_matching' in r.detection_method),
                'combined': sum(1 for r in results if 'combined' in r.detection_method),
                'fallback': sum(1 for r in results if 'fallback' in r.detection_method)
            }
        }
    
    def filter_articles_by_language(self, articles: List[Dict], target_language: str = 'en') -> Tuple[List[Dict], List[Dict]]:
        """
        Filter articles by target language.
        
        Args:
            articles: List of article dictionaries
            target_language: Target language code (default: 'en')
            
        Returns:
            Tuple of (matching_articles, non_matching_articles)
        """
        matching_articles = []
        non_matching_articles = []
        
        for article in articles:
            content = article.get('content', '') or article.get('text', '')
            if not content:
                non_matching_articles.append(article)
                continue
            
            try:
                lang_result = self.detect_language(content, article.get('url'))
                
                if lang_result.detected_language == target_language and lang_result.is_reliable:
                    # Add language detection metadata
                    article['language_detection'] = {
                        'detected_language': lang_result.detected_language,
                        'confidence_score': lang_result.confidence_score,
                        'is_reliable': lang_result.is_reliable,
                        'detection_method': lang_result.detection_method
                    }
                    matching_articles.append(article)
                else:
                    article['language_detection'] = {
                        'detected_language': lang_result.detected_language,
                        'confidence_score': lang_result.confidence_score,
                        'is_reliable': lang_result.is_reliable,
                        'detection_method': lang_result.detection_method,
                        'filtered_out': True,
                        'reason': f'Language {lang_result.detected_language} != {target_language}'
                    }
                    non_matching_articles.append(article)
                    
            except Exception as e:
                logger.error(f"Language detection failed for article: {e}")
                article['language_detection'] = {
                    'detected_language': 'unknown',
                    'confidence_score': 0.0,
                    'is_reliable': False,
                    'detection_method': 'error',
                    'filtered_out': True,
                    'reason': 'Detection error'
                }
                non_matching_articles.append(article)
        
        return matching_articles, non_matching_articles

def main():
    """Test the language detector."""
    detector = LanguageDetector()
    
    # Test texts
    test_texts = [
        "This is an English article about technology and innovation.",
        "Este es un artículo en español sobre tecnología e innovación.",
        "Ceci est un article en français sur la technologie et l'innovation.",
        "Dies ist ein deutscher Artikel über Technologie und Innovation.",
        "This is a mixed language text with some English words.",
        "1234567890 !@#$%^&*()",  # Numbers and symbols
        "",  # Empty text
    ]
    
    print("Language Detection Test Results:")
    print("=" * 50)
    
    for i, text in enumerate(test_texts):
        result = detector.detect_language(text)
        print(f"\nText {i+1}: {text[:50]}...")
        print(f"  Language: {result.detected_language}")
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Is English: {result.is_english}")
        print(f"  Is Reliable: {result.is_reliable}")
        print(f"  Method: {result.detection_method}")
        print(f"  Recommendation: {result.processing_recommendation}")
    
    # Test batch detection
    print("\n" + "=" * 50)
    print("Batch Detection Statistics:")
    
    batch_results = detector.batch_detect_languages(test_texts)
    stats = detector.get_language_statistics(batch_results)
    
    for key, value in stats.items():
        if key == 'language_distribution':
            print(f"  {key}:")
            for lang, count in value:
                print(f"    {lang}: {count}")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
