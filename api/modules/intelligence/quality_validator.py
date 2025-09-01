#!/usr/bin/env python3
"""
Quality Validator for News Intelligence System v2.5.0
Assesses content quality, completeness, and readability
"""
import os
import sys
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False
    print("Warning: textstat not available. Using basic readability metrics.")

try:
    from readability import Document
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False
    print("Warning: readability not available. Using basic content analysis.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QualityMetrics:
    """Quality metrics for content validation."""
    content_length: int
    word_count: int
    sentence_count: int
    paragraph_count: int
    average_sentence_length: float
    average_word_length: float
    unique_words: int
    vocabulary_diversity: float
    readability_score: float
    content_completeness: float
    quality_score: float
    validation_passed: bool
    issues: List[str]
    recommendations: List[str]

@dataclass
class ValidationResult:
    """Result of quality validation operation."""
    article_id: Optional[int]
    url: str
    quality_metrics: QualityMetrics
    validation_status: str  # 'passed', 'warning', 'failed'
    processing_recommendation: str  # 'process', 'review', 'skip'
    timestamp: datetime

class QualityValidator:
    """
    Comprehensive quality validation system that:
    - Assesses content length and completeness
    - Calculates readability metrics
    - Identifies content quality issues
    - Provides processing recommendations
    """
    
    def __init__(self, config: Dict = None):
        """Initialize the quality validator."""
        self.config = config or {
            'length_thresholds': {
                'min_content_length': 100,
                'max_content_length': 50000,
                'min_word_count': 20,
                'max_word_count': 10000,
                'min_sentence_count': 3,
                'max_sentence_count': 1000,
                'min_paragraph_count': 1,
                'max_paragraph_count': 200
            },
            'quality_thresholds': {
                'min_readability_score': 0.0,
                'max_readability_score': 100.0,
                'min_completeness_score': 0.6,
                'min_quality_score': 0.5
            },
            'scoring_weights': {
                'length': 0.25,
                'readability': 0.25,
                'completeness': 0.25,
                'diversity': 0.25
            }
        }
        
        # Common content issues patterns
        self.issue_patterns = {
            'incomplete_content': [
                r'\b(continued|more|read more|click here|full story)\b',
                r'\.\.\.$',
                r'\[advertisement\]',
                r'\[sponsored\]'
            ],
            'low_quality_indicators': [
                r'\b(clickbait|fake news|conspiracy|rumor)\b',
                r'[A-Z]{5,}',  # Excessive caps
                r'!{3,}',      # Multiple exclamation marks
                r'\?{3,}'      # Multiple question marks
            ],
            'technical_issues': [
                r'\[error\]',
                r'\[loading\]',
                r'\[javascript required\]',
                r'\[image\]',
                r'\[video\]'
            ]
        }
    
    def validate_content(self, content: str, url: str = None, article_id: int = None) -> ValidationResult:
        """
        Validate content quality and completeness.
        
        Args:
            content: Article content to validate
            url: Article URL for context
            article_id: Article ID for tracking
            
        Returns:
            ValidationResult with quality assessment
        """
        if not content or not content.strip():
            return self._create_empty_result(url, article_id)
        
        try:
            # Calculate basic metrics
            metrics = self._calculate_metrics(content)
            
            # Assess quality
            quality_score = self._calculate_quality_score(metrics)
            metrics.quality_score = quality_score
            
            # Check for issues
            issues = self._identify_issues(content, metrics)
            metrics.issues = issues
            
            # Generate recommendations
            recommendations = self._generate_recommendations(metrics, issues)
            metrics.recommendations = recommendations
            
            # Determine validation status
            validation_status = self._determine_validation_status(metrics, issues)
            
            # Determine processing recommendation
            processing_recommendation = self._determine_processing_recommendation(
                validation_status, metrics, issues
            )
            
            # Check if validation passed
            metrics.validation_passed = validation_status == 'passed'
            
            return ValidationResult(
                article_id=article_id,
                url=url or 'unknown',
                quality_metrics=metrics,
                validation_status=validation_status,
                processing_recommendation=processing_recommendation,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return self._create_error_result(url, article_id, str(e))
    
    def _calculate_metrics(self, content: str) -> QualityMetrics:
        """Calculate comprehensive content metrics."""
        # Basic counts
        content_length = len(content)
        word_count = len(content.split())
        sentence_count = len(re.split(r'[.!?]+', content))
        paragraph_count = len([p for p in content.split('\n\n') if p.strip()])
        
        # Averages
        average_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        average_word_length = sum(len(word) for word in content.split()) / word_count if word_count > 0 else 0
        
        # Vocabulary analysis
        words = re.findall(r'\b\w+\b', content.lower())
        unique_words = len(set(words))
        vocabulary_diversity = unique_words / word_count if word_count > 0 else 0
        
        # Readability score
        readability_score = self._calculate_readability(content)
        
        # Content completeness
        content_completeness = self._calculate_completeness(content, word_count)
        
        # Initialize with calculated values
        metrics = QualityMetrics(
            content_length=content_length,
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            average_sentence_length=round(average_sentence_length, 2),
            average_word_length=round(average_word_length, 2),
            unique_words=unique_words,
            vocabulary_diversity=round(vocabulary_diversity, 3),
            readability_score=round(readability_score, 2),
            content_completeness=round(content_completeness, 3),
            quality_score=0.0,  # Will be calculated later
            validation_passed=False,  # Will be set later
            issues=[],  # Will be populated later
            recommendations=[]  # Will be populated later
        )
        
        return metrics
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate readability score using available libraries."""
        if TEXTSTAT_AVAILABLE:
            try:
                # Use textstat for comprehensive readability
                flesch_reading_ease = textstat.flesch_reading_ease(content)
                # Normalize to 0-100 scale
                return max(0, min(100, flesch_reading_ease))
            except Exception as e:
                logger.warning(f"Textstat readability calculation failed: {e}")
        
        # Fallback to basic readability calculation
        try:
            sentences = re.split(r'[.!?]+', content)
            words = content.split()
            syllables = self._count_syllables(content)
            
            if sentences and words and syllables:
                # Simplified Flesch Reading Ease
                avg_sentence_length = words / len(sentences)
                avg_syllables_per_word = syllables / words
                
                # Flesch formula: 206.835 - (1.015 × avg_sentence_length) - (84.6 × avg_syllables_per_word)
                flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
                return max(0, min(100, flesch_score))
        except Exception as e:
            logger.warning(f"Basic readability calculation failed: {e}")
        
        return 50.0  # Default middle score
    
    def _count_syllables(self, text: str) -> int:
        """Count syllables in text (simplified method)."""
        text = text.lower()
        count = 0
        vowels = "aeiouy"
        on_vowel = False
        
        for char in text:
            is_vowel = char in vowels
            if is_vowel and not on_vowel:
                count += 1
            on_vowel = is_vowel
        
        # Adjust for common patterns
        if text.endswith('e'):
            count -= 1
        if count == 0:
            count = 1
        
        return count
    
    def _calculate_completeness(self, content: str, word_count: int) -> float:
        """Calculate content completeness score."""
        # Check for common incomplete content indicators
        incomplete_indicators = 0
        total_indicators = 0
        
        for pattern in self.issue_patterns['incomplete_content']:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            incomplete_indicators += matches
            total_indicators += 1
        
        # Check for balanced content structure
        paragraphs = content.split('\n\n')
        balanced_structure = len(paragraphs) >= 2
        
        # Check for meaningful conclusion
        has_conclusion = not content.strip().endswith(('...', 'continued', 'more'))
        
        # Calculate completeness score
        length_score = min(1.0, word_count / self.config['length_thresholds']['min_word_count'])
        structure_score = 1.0 if balanced_structure else 0.5
        conclusion_score = 1.0 if has_conclusion else 0.7
        indicator_score = max(0.0, 1.0 - (incomplete_indicators / max(1, total_indicators)))
        
        completeness = (length_score + structure_score + conclusion_score + indicator_score) / 4
        return completeness
    
    def _calculate_quality_score(self, metrics: QualityMetrics) -> float:
        """Calculate overall quality score."""
        weights = self.config['scoring_weights']
        
        # Length score (0-1)
        length_score = self._normalize_length_score(metrics)
        
        # Readability score (0-1)
        readability_score = metrics.readability_score / 100.0
        
        # Completeness score (0-1)
        completeness_score = metrics.content_completeness
        
        # Diversity score (0-1)
        diversity_score = min(1.0, metrics.vocabulary_diversity * 10)
        
        # Calculate weighted quality score
        quality_score = (
            length_score * weights['length'] +
            readability_score * weights['readability'] +
            completeness_score * weights['completeness'] +
            diversity_score * weights['diversity']
        )
        
        return round(quality_score, 3)
    
    def _normalize_length_score(self, metrics: QualityMetrics) -> float:
        """Normalize length metrics to 0-1 score."""
        word_count = metrics.word_count
        min_words = self.config['length_thresholds']['min_word_count']
        max_words = self.config['length_thresholds']['max_word_count']
        
        if word_count < min_words:
            return word_count / min_words
        elif word_count > max_words:
            return 1.0 - ((word_count - max_words) / max_words)
        else:
            return 1.0
    
    def _identify_issues(self, content: str, metrics: QualityMetrics) -> List[str]:
        """Identify content quality issues."""
        issues = []
        
        # Check length thresholds
        thresholds = self.config['length_thresholds']
        
        if metrics.word_count < thresholds['min_word_count']:
            issues.append(f"Content too short: {metrics.word_count} words (minimum: {thresholds['min_word_count']})")
        
        if metrics.word_count > thresholds['max_word_count']:
            issues.append(f"Content too long: {metrics.word_count} words (maximum: {thresholds['max_word_count']})")
        
        if metrics.sentence_count < thresholds['min_sentence_count']:
            issues.append(f"Too few sentences: {metrics.sentence_count} (minimum: {thresholds['min_sentence_count']})")
        
        # Check quality thresholds
        quality_thresholds = self.config['quality_thresholds']
        
        if metrics.readability_score < quality_thresholds['min_readability_score']:
            issues.append(f"Readability too low: {metrics.readability_score}")
        
        if metrics.content_completeness < quality_thresholds['min_completeness_score']:
            issues.append(f"Content completeness too low: {metrics.content_completeness:.3f}")
        
        if metrics.quality_score < quality_thresholds['min_quality_score']:
            issues.append(f"Overall quality too low: {metrics.quality_score:.3f}")
        
        # Check for content issues
        for issue_type, patterns in self.issue_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    issues.append(f"Detected {issue_type}: {len(matches)} instances")
                    break
        
        # Check for technical issues
        if metrics.average_sentence_length > 25:
            issues.append(f"Sentences too long: average {metrics.average_sentence_length:.1f} words")
        
        if metrics.average_word_length > 8:
            issues.append(f"Words too long: average {metrics.average_word_length:.1f} characters")
        
        return issues
    
    def _generate_recommendations(self, metrics: QualityMetrics, issues: List[str]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        if metrics.word_count < self.config['length_thresholds']['min_word_count']:
            recommendations.append("Expand content to meet minimum word count requirements")
        
        if metrics.readability_score < 50:
            recommendations.append("Simplify language and sentence structure for better readability")
        
        if metrics.content_completeness < 0.7:
            recommendations.append("Ensure content has proper introduction, body, and conclusion")
        
        if metrics.vocabulary_diversity < 0.3:
            recommendations.append("Increase vocabulary diversity for better content quality")
        
        if metrics.average_sentence_length > 20:
            recommendations.append("Break long sentences into shorter, more readable ones")
        
        if not recommendations:
            recommendations.append("Content meets quality standards")
        
        return recommendations
    
    def _determine_validation_status(self, metrics: QualityMetrics, issues: List[str]) -> str:
        """Determine overall validation status."""
        if not issues:
            return 'passed'
        
        # Count critical issues
        critical_issues = len([issue for issue in issues if 'too short' in issue or 'too long' in issue])
        
        if critical_issues > 0:
            return 'failed'
        elif len(issues) <= 2:
            return 'warning'
        else:
            return 'failed'
    
    def _determine_processing_recommendation(self, validation_status: str, metrics: QualityMetrics, issues: List[str]) -> str:
        """Determine processing recommendation."""
        if validation_status == 'passed':
            return 'process'
        elif validation_status == 'warning':
            return 'review'
        else:
            return 'skip'
    
    def _create_empty_result(self, url: str, article_id: int) -> ValidationResult:
        """Create result for empty content."""
        empty_metrics = QualityMetrics(
            content_length=0,
            word_count=0,
            sentence_count=0,
            paragraph_count=0,
            average_sentence_length=0.0,
            average_word_length=0.0,
            unique_words=0,
            vocabulary_diversity=0.0,
            readability_score=0.0,
            content_completeness=0.0,
            quality_score=0.0,
            validation_passed=False,
            issues=['No content provided'],
            recommendations=['Provide article content for validation']
        )
        
        return ValidationResult(
            article_id=article_id,
            url=url or 'unknown',
            quality_metrics=empty_metrics,
            validation_status='failed',
            processing_recommendation='skip',
            timestamp=datetime.now()
        )
    
    def _create_error_result(self, url: str, article_id: int, error_message: str) -> ValidationResult:
        """Create result for validation errors."""
        error_metrics = QualityMetrics(
            content_length=0,
            word_count=0,
            sentence_count=0,
            paragraph_count=0,
            average_sentence_length=0.0,
            average_word_length=0.0,
            unique_words=0,
            vocabulary_diversity=0.0,
            readability_score=0.0,
            content_completeness=0.0,
            quality_score=0.0,
            validation_passed=False,
            issues=[f'Validation error: {error_message}'],
            recommendations=['Check content format and retry validation']
        )
        
        return ValidationResult(
            article_id=article_id,
            url=url or 'unknown',
            quality_metrics=error_metrics,
            validation_status='failed',
            processing_recommendation='skip',
            timestamp=datetime.now()
        )
    
    def batch_validate(self, articles: List[Dict]) -> List[ValidationResult]:
        """Validate multiple articles."""
        results = []
        
        for article in articles:
            try:
                content = article.get('content', '') or article.get('text', '')
                url = article.get('url', '')
                article_id = article.get('id')
                
                result = self.validate_content(content, url, article_id)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Batch validation failed for article: {e}")
                error_result = self._create_error_result(
                    article.get('url', ''), 
                    article.get('id'), 
                    str(e)
                )
                results.append(error_result)
        
        return results
    
    def get_validation_statistics(self, results: List[ValidationResult]) -> Dict:
        """Get statistics from validation results."""
        if not results:
            return {}
        
        total_articles = len(results)
        passed_articles = sum(1 for r in results if r.validation_status == 'passed')
        warning_articles = sum(1 for r in results if r.validation_status == 'warning')
        failed_articles = sum(1 for r in results if r.validation_status == 'failed')
        
        # Quality score statistics
        quality_scores = [r.quality_metrics.quality_score for r in results if r.quality_metrics.quality_score > 0]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        # Readability statistics
        readability_scores = [r.quality_metrics.readability_score for r in results if r.quality_metrics.readability_score > 0]
        avg_readability = sum(readability_scores) / len(readability_scores) if readability_scores else 0
        
        # Processing recommendations
        process_count = sum(1 for r in results if r.processing_recommendation == 'process')
        review_count = sum(1 for r in results if r.processing_recommendation == 'review')
        skip_count = sum(1 for r in results if r.processing_recommendation == 'skip')
        
        return {
            'total_articles': total_articles,
            'validation_results': {
                'passed': passed_articles,
                'warning': warning_articles,
                'failed': failed_articles
            },
            'validation_percentages': {
                'passed': (passed_articles / total_articles) * 100 if total_articles > 0 else 0,
                'warning': (warning_articles / total_articles) * 100 if total_articles > 0 else 0,
                'failed': (failed_articles / total_articles) * 100 if total_articles > 0 else 0
            },
            'quality_metrics': {
                'average_quality_score': round(avg_quality, 3),
                'average_readability_score': round(avg_readability, 2)
            },
            'processing_recommendations': {
                'process': process_count,
                'review': review_count,
                'skip': skip_count
            }
        }

def main():
    """Test the quality validator."""
    validator = QualityValidator()
    
    # Test content
    test_content = [
        "This is a short test article.",
        "This is a comprehensive article about artificial intelligence and machine learning. It covers various topics including neural networks, deep learning, and natural language processing. The article provides detailed explanations and examples to help readers understand these complex concepts.",
        "This is an incomplete article that ends with...",
        "1234567890 !@#$%^&*()",  # Numbers and symbols
        "",  # Empty content
    ]
    
    print("Quality Validation Test Results:")
    print("=" * 60)
    
    for i, content in enumerate(test_content):
        result = validator.validate_content(content, f"test_url_{i}", i)
        print(f"\nArticle {i+1}: {content[:50]}...")
        print(f"  Validation Status: {result.validation_status}")
        print(f"  Quality Score: {result.quality_metrics.quality_score:.3f}")
        print(f"  Readability: {result.quality_metrics.readability_score:.1f}")
        print(f"  Word Count: {result.quality_metrics.word_count}")
        print(f"  Recommendation: {result.processing_recommendation}")
        
        if result.quality_metrics.issues:
            print(f"  Issues: {', '.join(result.quality_metrics.issues[:2])}")
    
    # Test batch validation
    print("\n" + "=" * 60)
    print("Batch Validation Statistics:")
    
    test_articles = [
        {'id': 1, 'content': test_content[1], 'url': 'test1.com'},
        {'id': 2, 'content': test_content[2], 'url': 'test2.com'},
        {'id': 3, 'content': test_content[0], 'url': 'test3.com'},
    ]
    
    batch_results = validator.batch_validate(test_articles)
    stats = validator.get_validation_statistics(batch_results)
    
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for sub_key, sub_value in value.items():
                print(f"    {sub_key}: {sub_value}")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
