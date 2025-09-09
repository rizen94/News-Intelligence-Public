"""
Readability & Quality Metrics Module for News Intelligence System v3.0
Uses local LLM models via Ollama for comprehensive content analysis
"""

import logging
import json
import time
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ReadabilityMetrics:
    """Structured readability analysis result"""
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    smog_index: float
    automated_readability_index: float
    coleman_liau_index: float
    average_grade_level: float
    reading_time_minutes: float
    word_count: int
    sentence_count: int
    syllable_count: int
    character_count: int
    local_processing: bool = True

@dataclass
class QualityMetrics:
    """Structured content quality analysis result"""
    overall_quality_score: float
    clarity_score: float
    coherence_score: float
    completeness_score: float
    accuracy_score: float
    engagement_score: float
    bias_score: float
    factual_consistency: float
    source_reliability: float
    writing_style: str
    content_type: str
    target_audience: str
    recommendations: List[str]
    model_used: str
    processing_time: float
    local_processing: bool = True

@dataclass
class ContentAnalysisResult:
    """Complete content analysis result"""
    readability: ReadabilityMetrics
    quality: QualityMetrics
    text: str
    model_used: str
    total_processing_time: float
    local_processing: bool = True

class LocalReadabilityAnalyzer:
    """
    Local readability and quality analyzer using Ollama models
    No training required - uses mathematical formulas and LLM analysis
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.available_models = ["llama3.1:8b", "llama3.1:70b"]
        self.default_model = "llama3.1:8b"
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Reading speed constants (words per minute)
        self.READING_SPEEDS = {
            'slow': 150,
            'average': 200,
            'fast': 250
        }
    
    def analyze_content(self, 
                       text: str, 
                       model: Optional[str] = None,
                       use_cache: bool = True) -> ContentAnalysisResult:
        """
        Analyze content for readability and quality metrics
        
        Args:
            text: Text to analyze
            model: Specific model to use (optional)
            use_cache: Whether to use cached results
            
        Returns:
            ContentAnalysisResult with comprehensive analysis
        """
        try:
            start_time = time.time()
            
            # Check cache first
            if use_cache:
                cache_key = f"{hash(text)}_{model or self.default_model}"
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        logger.info(f"Using cached readability analysis for text: {text[:50]}...")
                        return ContentAnalysisResult(**cached_result['data'])
            
            # Select model
            selected_model = model or self.default_model
            if selected_model not in self.available_models:
                logger.warning(f"Model {selected_model} not available, using {self.default_model}")
                selected_model = self.default_model
            
            # Calculate readability metrics (mathematical)
            readability = self._calculate_readability_metrics(text)
            
            # Analyze quality using LLM
            quality = self._analyze_quality_with_llm(text, selected_model)
            
            # Create result
            total_processing_time = time.time() - start_time
            
            result = ContentAnalysisResult(
                readability=readability,
                quality=quality,
                text=text,
                model_used=selected_model,
                total_processing_time=total_processing_time
            )
            
            # Cache result
            if use_cache:
                self.cache[cache_key] = {
                    'data': {
                        'readability': {
                            'flesch_reading_ease': readability.flesch_reading_ease,
                            'flesch_kincaid_grade': readability.flesch_kincaid_grade,
                            'gunning_fog': readability.gunning_fog,
                            'smog_index': readability.smog_index,
                            'automated_readability_index': readability.automated_readability_index,
                            'coleman_liau_index': readability.coleman_liau_index,
                            'average_grade_level': readability.average_grade_level,
                            'reading_time_minutes': readability.reading_time_minutes,
                            'word_count': readability.word_count,
                            'sentence_count': readability.sentence_count,
                            'syllable_count': readability.syllable_count,
                            'character_count': readability.character_count,
                            'local_processing': readability.local_processing
                        },
                        'quality': {
                            'overall_quality_score': quality.overall_quality_score,
                            'clarity_score': quality.clarity_score,
                            'coherence_score': quality.coherence_score,
                            'completeness_score': quality.completeness_score,
                            'accuracy_score': quality.accuracy_score,
                            'engagement_score': quality.engagement_score,
                            'bias_score': quality.bias_score,
                            'factual_consistency': quality.factual_consistency,
                            'source_reliability': quality.source_reliability,
                            'writing_style': quality.writing_style,
                            'content_type': quality.content_type,
                            'target_audience': quality.target_audience,
                            'recommendations': quality.recommendations,
                            'model_used': quality.model_used,
                            'processing_time': quality.processing_time,
                            'local_processing': quality.local_processing
                        },
                        'text': text,
                        'model_used': selected_model,
                        'total_processing_time': total_processing_time,
                        'local_processing': True
                    },
                    'timestamp': time.time()
                }
            
            logger.info(f"Content analysis completed in {total_processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            # Return basic result on error
            readability = self._calculate_readability_metrics(text)
            quality = QualityMetrics(
                overall_quality_score=0.5,
                clarity_score=0.5,
                coherence_score=0.5,
                completeness_score=0.5,
                accuracy_score=0.5,
                engagement_score=0.5,
                bias_score=0.5,
                factual_consistency=0.5,
                source_reliability=0.5,
                writing_style="unknown",
                content_type="unknown",
                target_audience="general",
                recommendations=["Analysis failed"],
                model_used=selected_model,
                processing_time=0.0
            )
            
            return ContentAnalysisResult(
                readability=readability,
                quality=quality,
                text=text,
                model_used=selected_model,
                total_processing_time=time.time() - start_time
            )
    
    def _calculate_readability_metrics(self, text: str) -> ReadabilityMetrics:
        """Calculate readability metrics using mathematical formulas"""
        try:
            # Basic text statistics
            words = self._count_words(text)
            sentences = self._count_sentences(text)
            syllables = self._count_syllables(text)
            characters = len(text)
            
            # Calculate reading time (average speed)
            reading_time = words / self.READING_SPEEDS['average']
            
            # Flesch Reading Ease
            if sentences > 0 and words > 0:
                flesch_ease = 206.835 - (1.015 * (words / sentences)) - (84.6 * (syllables / words))
            else:
                flesch_ease = 0
            
            # Flesch-Kincaid Grade Level
            if sentences > 0 and words > 0:
                flesch_grade = (0.39 * (words / sentences)) + (11.8 * (syllables / words)) - 15.59
            else:
                flesch_grade = 0
            
            # Gunning Fog Index
            if sentences > 0 and words > 0:
                complex_words = self._count_complex_words(text)
                gunning_fog = 0.4 * ((words / sentences) + (100 * (complex_words / words)))
            else:
                gunning_fog = 0
            
            # SMOG Index
            if sentences > 0:
                complex_words_smog = self._count_complex_words_smog(text)
                smog = 1.043 * (complex_words_smog ** 0.5) + 3.1291
            else:
                smog = 0
            
            # Automated Readability Index
            if sentences > 0 and words > 0:
                ari = (4.71 * (characters / words)) + (0.5 * (words / sentences)) - 21.43
            else:
                ari = 0
            
            # Coleman-Liau Index
            if words > 0:
                cli = (0.0588 * (characters / words * 100)) - (0.296 * (sentences / words * 100)) - 15.8
            else:
                cli = 0
            
            # Average grade level
            grade_levels = [flesch_grade, gunning_fog, smog, ari, cli]
            valid_grades = [g for g in grade_levels if g > 0]
            avg_grade = sum(valid_grades) / len(valid_grades) if valid_grades else 0
            
            return ReadabilityMetrics(
                flesch_reading_ease=flesch_ease,
                flesch_kincaid_grade=flesch_grade,
                gunning_fog=gunning_fog,
                smog_index=smog,
                automated_readability_index=ari,
                coleman_liau_index=cli,
                average_grade_level=avg_grade,
                reading_time_minutes=reading_time,
                word_count=words,
                sentence_count=sentences,
                syllable_count=syllables,
                character_count=characters
            )
            
        except Exception as e:
            logger.error(f"Error calculating readability metrics: {e}")
            return ReadabilityMetrics(
                flesch_reading_ease=0,
                flesch_kincaid_grade=0,
                gunning_fog=0,
                smog_index=0,
                automated_readability_index=0,
                coleman_liau_index=0,
                average_grade_level=0,
                reading_time_minutes=0,
                word_count=0,
                sentence_count=0,
                syllable_count=0,
                character_count=0
            )
    
    def _analyze_quality_with_llm(self, text: str, model: str) -> QualityMetrics:
        """Analyze content quality using local LLM"""
        try:
            start_time = time.time()
            
            # Create quality analysis prompt
            prompt = self._create_quality_prompt(text)
            
            # Call Ollama
            response = self._call_ollama(prompt, model)
            
            # Parse response
            quality_data = self._parse_quality_response(response)
            
            processing_time = time.time() - start_time
            
            return QualityMetrics(
                overall_quality_score=quality_data['overall_quality_score'],
                clarity_score=quality_data['clarity_score'],
                coherence_score=quality_data['coherence_score'],
                completeness_score=quality_data['completeness_score'],
                accuracy_score=quality_data['accuracy_score'],
                engagement_score=quality_data['engagement_score'],
                bias_score=quality_data['bias_score'],
                factual_consistency=quality_data['factual_consistency'],
                source_reliability=quality_data['source_reliability'],
                writing_style=quality_data['writing_style'],
                content_type=quality_data['content_type'],
                target_audience=quality_data['target_audience'],
                recommendations=quality_data['recommendations'],
                model_used=model,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error in LLM quality analysis: {e}")
            return QualityMetrics(
                overall_quality_score=0.5,
                clarity_score=0.5,
                coherence_score=0.5,
                completeness_score=0.5,
                accuracy_score=0.5,
                engagement_score=0.5,
                bias_score=0.5,
                factual_consistency=0.5,
                source_reliability=0.5,
                writing_style="unknown",
                content_type="unknown",
                target_audience="general",
                recommendations=["Quality analysis failed"],
                model_used=model,
                processing_time=0.0
            )
    
    def _count_words(self, text: str) -> int:
        """Count words in text"""
        words = re.findall(r'\b\w+\b', text.lower())
        return len(words)
    
    def _count_sentences(self, text: str) -> int:
        """Count sentences in text"""
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])
    
    def _count_syllables(self, text: str) -> int:
        """Count syllables in text"""
        words = re.findall(r'\b\w+\b', text.lower())
        total_syllables = 0
        
        for word in words:
            syllables = self._count_word_syllables(word)
            total_syllables += syllables
        
        return total_syllables
    
    def _count_word_syllables(self, word: str) -> int:
        """Count syllables in a single word"""
        if not word:
            return 0
        
        # Remove common suffixes
        word = re.sub(r'[^a-z]', '', word.lower())
        if not word:
            return 0
        
        # Count vowel groups
        vowels = 'aeiouy'
        syllable_count = 0
        prev_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel
        
        # Handle silent 'e'
        if word.endswith('e') and syllable_count > 1:
            syllable_count -= 1
        
        # Minimum 1 syllable per word
        return max(1, syllable_count)
    
    def _count_complex_words(self, text: str) -> int:
        """Count complex words (3+ syllables)"""
        words = re.findall(r'\b\w+\b', text.lower())
        complex_count = 0
        
        for word in words:
            if self._count_word_syllables(word) >= 3:
                complex_count += 1
        
        return complex_count
    
    def _count_complex_words_smog(self, text: str) -> int:
        """Count complex words for SMOG index (3+ syllables)"""
        # Take first 30 sentences for SMOG calculation
        sentences = re.split(r'[.!?]+', text)
        first_30_sentences = sentences[:30]
        text_sample = '. '.join(first_30_sentences)
        
        words = re.findall(r'\b\w+\b', text_sample.lower())
        complex_count = 0
        
        for word in words:
            if self._count_word_syllables(word) >= 3:
                complex_count += 1
        
        return complex_count
    
    def _create_quality_prompt(self, text: str) -> str:
        """Create structured prompt for quality analysis"""
        return f"""
Analyze the quality of the following text and provide detailed metrics.

Text: "{text}"

Please provide your analysis in the following JSON format:
{{
    "overall_quality_score": 0.85,
    "clarity_score": 0.90,
    "coherence_score": 0.80,
    "completeness_score": 0.75,
    "accuracy_score": 0.85,
    "engagement_score": 0.70,
    "bias_score": 0.20,
    "factual_consistency": 0.90,
    "source_reliability": 0.80,
    "writing_style": "professional",
    "content_type": "news_article",
    "target_audience": "general_public",
    "recommendations": [
        "Improve paragraph structure",
        "Add more specific examples"
    ]
}}

Guidelines:
- Score each metric from 0.0 (poor) to 1.0 (excellent)
- bias_score: 0.0 = no bias, 1.0 = highly biased
- writing_style: professional, casual, academic, technical, creative
- content_type: news_article, blog_post, report, analysis, opinion
- target_audience: general_public, professionals, academics, students, experts
- Be objective and analytical
- Provide specific, actionable recommendations
"""
    
    def _call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama API for quality analysis"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "temperature": 0.2,  # Low temperature for consistent analysis
                        "num_predict": 800,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            # Parse streaming response
            result = ""
            for line in response.text.split('\n'):
                if line.strip():
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            result += data['response']
                    except json.JSONDecodeError:
                        continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise
    
    def _parse_quality_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama response and extract quality data"""
        try:
            # Try to find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Validate and normalize data
                return {
                    'overall_quality_score': max(0.0, min(1.0, float(data.get('overall_quality_score', 0.5)))),
                    'clarity_score': max(0.0, min(1.0, float(data.get('clarity_score', 0.5)))),
                    'coherence_score': max(0.0, min(1.0, float(data.get('coherence_score', 0.5)))),
                    'completeness_score': max(0.0, min(1.0, float(data.get('completeness_score', 0.5)))),
                    'accuracy_score': max(0.0, min(1.0, float(data.get('accuracy_score', 0.5)))),
                    'engagement_score': max(0.0, min(1.0, float(data.get('engagement_score', 0.5)))),
                    'bias_score': max(0.0, min(1.0, float(data.get('bias_score', 0.5)))),
                    'factual_consistency': max(0.0, min(1.0, float(data.get('factual_consistency', 0.5)))),
                    'source_reliability': max(0.0, min(1.0, float(data.get('source_reliability', 0.5)))),
                    'writing_style': data.get('writing_style', 'unknown'),
                    'content_type': data.get('content_type', 'unknown'),
                    'target_audience': data.get('target_audience', 'general'),
                    'recommendations': data.get('recommendations', [])
                }
            else:
                # Fallback parsing if JSON not found
                return self._fallback_quality_parse(response)
                
        except Exception as e:
            logger.error(f"Error parsing quality response: {e}")
            return self._fallback_quality_parse(response)
    
    def _fallback_quality_parse(self, response: str) -> Dict[str, Any]:
        """Fallback parsing when JSON parsing fails"""
        return {
            'overall_quality_score': 0.5,
            'clarity_score': 0.5,
            'coherence_score': 0.5,
            'completeness_score': 0.5,
            'accuracy_score': 0.5,
            'engagement_score': 0.5,
            'bias_score': 0.5,
            'factual_consistency': 0.5,
            'source_reliability': 0.5,
            'writing_style': 'unknown',
            'content_type': 'unknown',
            'target_audience': 'general',
            'recommendations': ['Quality analysis failed']
        }
    
    def clear_cache(self):
        """Clear the analysis cache"""
        self.cache.clear()
        logger.info("Readability analysis cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_ttl": self.cache_ttl,
            "available_models": self.available_models,
            "default_model": self.default_model,
            "reading_speeds": self.READING_SPEEDS
        }

# Global instance
readability_analyzer = LocalReadabilityAnalyzer()


