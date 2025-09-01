#!/usr/bin/env python3
"""
Content Cleaner for News Intelligence System v2.5.0
Provides comprehensive content cleaning and normalization before processing
"""

import os
import re
import logging
import unicodedata
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import html
import chardet

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CleaningResult:
    """Result of content cleaning operation."""
    cleaned_content: str
    original_length: int
    cleaned_length: int
    cleaning_actions: List[str]
    quality_score: float
    encoding_fixed: bool
    html_removed: bool
    normalized: bool

class ContentCleaner:
    """
    Comprehensive content cleaner that handles:
    - HTML tag removal
    - Text encoding normalization
    - Special character handling
    - Whitespace normalization
    - Content validation
    """
    
    def __init__(self):
        """Initialize the content cleaner."""
        # HTML tag patterns to remove
        self.html_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'<style[^>]*>.*?</style>',    # Style tags
            r'<[^>]+>',                     # All other HTML tags
        ]
        
        # Special character patterns
        self.special_char_patterns = [
            (r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\']', ''),  # Remove most special chars
            (r'[\u2018\u2019]', "'"),  # Smart quotes to simple
            (r'[\u201C\u201D]', '"'),  # Smart quotes to simple
            (r'[\u2013\u2014]', '-'),  # Em dashes to simple
            (r'[\u2026]', '...'),      # Ellipsis to dots
        ]
        
        # Whitespace patterns
        self.whitespace_patterns = [
            (r'\s+', ' '),              # Multiple spaces to single
            (r'\n\s*\n', '\n\n'),       # Multiple newlines to double
            (r'^\s+', ''),              # Leading whitespace
            (r'\s+$', ''),              # Trailing whitespace
        ]
        
        # Content quality thresholds
        self.quality_thresholds = {
            'min_length': 50,           # Minimum content length
            'max_length': 50000,        # Maximum content length
            'min_words': 10,            # Minimum word count
            'max_words': 10000,         # Maximum word count
        }
    
    def clean_content(self, content: str, url: str = None) -> CleaningResult:
        """
        Clean and normalize article content.
        
        Args:
            content: Raw article content
            url: Article URL for context
            
        Returns:
            CleaningResult with cleaned content and metadata
        """
        if not content:
            return CleaningResult(
                cleaned_content="",
                original_length=0,
                cleaned_length=0,
                cleaning_actions=["No content provided"],
                quality_score=0.0,
                encoding_fixed=False,
                html_removed=False,
                normalized=False
            )
        
        original_length = len(content)
        cleaning_actions = []
        
        # Step 1: Fix encoding issues
        content, encoding_fixed = self._fix_encoding(content)
        if encoding_fixed:
            cleaning_actions.append("Encoding normalized")
        
        # Step 2: Remove HTML tags
        content, html_removed = self._remove_html(content)
        if html_removed:
            cleaning_actions.append("HTML tags removed")
        
        # Step 3: Normalize special characters
        content, normalized = self._normalize_special_chars(content)
        if normalized:
            cleaning_actions.append("Special characters normalized")
        
        # Step 4: Normalize whitespace
        content = self._normalize_whitespace(content)
        cleaning_actions.append("Whitespace normalized")
        
        # Step 5: Clean up common issues
        content = self._cleanup_common_issues(content)
        cleaning_actions.append("Common issues cleaned")
        
        # Step 6: Validate content
        content, validation_actions = self._validate_content(content)
        cleaning_actions.extend(validation_actions)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(content, original_length)
        
        cleaned_length = len(content)
        
        return CleaningResult(
            cleaned_content=content,
            original_length=original_length,
            cleaned_length=cleaned_length,
            cleaning_actions=cleaning_actions,
            quality_score=quality_score,
            encoding_fixed=encoding_fixed,
            html_removed=html_removed,
            normalized=normalized
        )
    
    def _fix_encoding(self, content: str) -> Tuple[str, bool]:
        """Fix text encoding issues."""
        try:
            # Try to detect encoding
            if isinstance(content, bytes):
                detected = chardet.detect(content)
                if detected['encoding']:
                    content = content.decode(detected['encoding'], errors='replace')
                    return content, True
            
            # Handle common encoding issues
            if '\\u' in content or '\\x' in content:
                # Fix escaped unicode
                content = content.encode('utf-8').decode('unicode_escape')
                return content, True
            
            # Normalize unicode
            content = unicodedata.normalize('NFKC', content)
            
            return content, False
            
        except Exception as e:
            logger.warning(f"Encoding fix failed: {e}")
            return content, False
    
    def _remove_html(self, content: str) -> Tuple[str, bool]:
        """Remove HTML tags from content."""
        original_content = content
        
        try:
            # Remove script and style content first
            for pattern in self.html_patterns[:2]:
                content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove remaining HTML tags
            content = re.sub(self.html_patterns[2], '', content)
            
            # Decode HTML entities
            content = html.unescape(content)
            
            # Check if any HTML was removed
            html_removed = content != original_content
            
            return content, html_removed
            
        except Exception as e:
            logger.warning(f"HTML removal failed: {e}")
            return content, False
    
    def _normalize_special_chars(self, content: str) -> Tuple[str, bool]:
        """Normalize special characters."""
        original_content = content
        
        try:
            for pattern, replacement in self.special_char_patterns:
                content = re.sub(pattern, replacement, content)
            
            # Check if any changes were made
            normalized = content != original_content
            
            return content, normalized
            
        except Exception as e:
            logger.warning(f"Special character normalization failed: {e}")
            return content, False
    
    def _normalize_whitespace(self, content: str) -> str:
        """Normalize whitespace in content."""
        try:
            for pattern, replacement in self.whitespace_patterns:
                content = re.sub(pattern, replacement, content)
            
            return content.strip()
            
        except Exception as e:
            logger.warning(f"Whitespace normalization failed: {e}")
            return content
    
    def _cleanup_common_issues(self, content: str) -> str:
        """Clean up common content issues."""
        try:
            # Remove multiple periods
            content = re.sub(r'\.{3,}', '...', content)
            
            # Fix spacing around punctuation
            content = re.sub(r'\s+([.,!?;:])', r'\1', content)
            content = re.sub(r'([.,!?;:])\s*([A-Z])', r'\1 \2', content)
            
            # Fix spacing around quotes
            content = re.sub(r'\s+["\']', r'"', content)
            content = re.sub(r'["\']\s+', r'"', content)
            
            # Remove excessive whitespace
            content = re.sub(r' {2,}', ' ', content)
            
            return content
            
        except Exception as e:
            logger.warning(f"Common issue cleanup failed: {e}")
            return content
    
    def _validate_content(self, content: str) -> Tuple[str, List[str]]:
        """Validate content quality and make adjustments."""
        validation_actions = []
        
        try:
            # Check content length
            if len(content) < self.quality_thresholds['min_length']:
                validation_actions.append("Content too short - marked for review")
                content = f"[SHORT_CONTENT: {len(content)} chars] {content}"
            
            elif len(content) > self.quality_thresholds['max_length']:
                validation_actions.append("Content truncated - too long")
                content = content[:self.quality_thresholds['max_length']] + "..."
            
            # Check word count
            word_count = len(content.split())
            if word_count < self.quality_thresholds['min_words']:
                validation_actions.append("Word count too low - marked for review")
                content = f"[LOW_WORD_COUNT: {word_count} words] {content}"
            
            elif word_count > self.quality_thresholds['max_words']:
                validation_actions.append("Word count too high - truncated")
                # Truncate to reasonable length
                words = content.split()[:self.quality_thresholds['max_words']]
                content = ' '.join(words) + "..."
            
            # Check for common quality issues
            if content.count('...') > 10:
                validation_actions.append("Excessive ellipsis detected")
            
            if content.count('  ') > 0:
                validation_actions.append("Multiple spaces detected")
            
            return content, validation_actions
            
        except Exception as e:
            logger.warning(f"Content validation failed: {e}")
            return content, ["Validation failed"]
    
    def _calculate_quality_score(self, content: str, original_length: int) -> float:
        """Calculate content quality score (0.0 to 1.0)."""
        try:
            score = 0.0
            
            # Length score (0-30 points)
            if len(content) >= self.quality_thresholds['min_length']:
                score += 30
            elif len(content) > 0:
                score += (len(content) / self.quality_thresholds['min_length']) * 30
            
            # Word count score (0-25 points)
            word_count = len(content.split())
            if word_count >= self.quality_thresholds['min_words']:
                score += 25
            elif word_count > 0:
                score += (word_count / self.quality_thresholds['min_words']) * 25
            
            # Readability score (0-25 points)
            readability = self._calculate_readability(content)
            score += readability * 25
            
            # Cleanliness score (0-20 points)
            cleanliness = self._calculate_cleanliness(content)
            score += cleanliness * 20
            
            return min(score / 100.0, 1.0)
            
        except Exception as e:
            logger.warning(f"Quality score calculation failed: {e}")
            return 0.0
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate basic readability score (0.0 to 1.0)."""
        try:
            if not content:
                return 0.0
            
            sentences = re.split(r'[.!?]+', content)
            words = content.split()
            
            if not sentences or not words:
                return 0.0
            
            # Average sentence length (lower is better for readability)
            avg_sentence_length = len(words) / len(sentences)
            
            # Simple readability scoring
            if avg_sentence_length <= 15:
                return 1.0
            elif avg_sentence_length <= 20:
                return 0.8
            elif avg_sentence_length <= 25:
                return 0.6
            elif avg_sentence_length <= 30:
                return 0.4
            else:
                return 0.2
                
        except Exception as e:
            logger.warning(f"Readability calculation failed: {e}")
            return 0.5
    
    def _calculate_cleanliness(self, content: str) -> float:
        """Calculate content cleanliness score (0.0 to 1.0)."""
        try:
            if not content:
                return 0.0
            
            # Check for common quality issues
            issues = 0
            total_checks = 0
            
            # Check for excessive punctuation
            if content.count('...') > 5:
                issues += 1
            total_checks += 1
            
            # Check for multiple spaces
            if '  ' in content:
                issues += 1
            total_checks += 1
            
            # Check for excessive newlines
            if content.count('\n') > len(content) / 100:
                issues += 1
            total_checks += 1
            
            # Check for excessive special characters
            special_char_ratio = len(re.findall(r'[^\w\s]', content)) / len(content)
            if special_char_ratio > 0.3:
                issues += 1
            total_checks += 1
            
            # Calculate cleanliness score
            cleanliness = 1.0 - (issues / total_checks)
            return max(0.0, cleanliness)
            
        except Exception as e:
            logger.warning(f"Cleanliness calculation failed: {e}")
            return 0.5
    
    def batch_clean_articles(self, articles: List[Dict]) -> List[CleaningResult]:
        """Clean multiple articles in batch."""
        results = []
        
        for article in articles:
            try:
                content = article.get('content', '')
                url = article.get('url', '')
                
                result = self.clean_content(content, url)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error cleaning article: {e}")
                # Create error result
                error_result = CleaningResult(
                    cleaned_content=content,
                    original_length=len(content),
                    cleaned_length=0,
                    cleaning_actions=[f"Error: {str(e)}"],
                    quality_score=0.0,
                    encoding_fixed=False,
                    html_removed=False,
                    normalized=False
                )
                results.append(error_result)
        
        return results
    
    def get_cleaning_statistics(self, results: List[CleaningResult]) -> Dict:
        """Get statistics from batch cleaning results."""
        try:
            total_articles = len(results)
            if total_articles == 0:
                return {}
            
            # Calculate statistics
            total_original_length = sum(r.original_length for r in results)
            total_cleaned_length = sum(r.cleaned_length for r in results)
            avg_quality_score = sum(r.quality_score for r in results) / total_articles
            
            encoding_fixed_count = sum(1 for r in results if r.encoding_fixed)
            html_removed_count = sum(1 for r in results if r.html_removed)
            normalized_count = sum(1 for r in results if r.normalized)
            
            # Quality distribution
            high_quality = sum(1 for r in results if r.quality_score >= 0.8)
            medium_quality = sum(1 for r in results if 0.5 <= r.quality_score < 0.8)
            low_quality = sum(1 for r in results if r.quality_score < 0.5)
            
            return {
                'total_articles': total_articles,
                'total_original_length': total_original_length,
                'total_cleaned_length': total_cleaned_length,
                'compression_ratio': total_cleaned_length / total_original_length if total_original_length > 0 else 0,
                'avg_quality_score': avg_quality_score,
                'encoding_fixed_count': encoding_fixed_count,
                'html_removed_count': html_removed_count,
                'normalized_count': normalized_count,
                'quality_distribution': {
                    'high': high_quality,
                    'medium': medium_quality,
                    'low': low_quality
                }
            }
            
        except Exception as e:
            logger.error(f"Statistics calculation failed: {e}")
            return {}

def main():
    """Test the content cleaner."""
    print("Testing Content Cleaner...")
    
    cleaner = ContentCleaner()
    
    # Test content
    test_content = """
    <html>
    <head><title>Test Article</title></head>
    <body>
        <h1>Breaking News!</h1>
        <p>This is a <strong>test article</strong> with some HTML tags.</p>
        <p>It has multiple paragraphs and some special characters: "smart quotes" and – em dashes.</p>
        <script>alert('test');</script>
    </body>
    </html>
    """
    
    print(f"Original content length: {len(test_content)}")
    print(f"Original content preview: {test_content[:100]}...")
    
    # Clean content
    result = cleaner.clean_content(test_content, "https://example.com/test")
    
    print(f"\nCleaning Results:")
    print(f"  Cleaned length: {result.cleaned_length}")
    print(f"  Quality score: {result.quality_score:.2f}")
    print(f"  Encoding fixed: {result.encoding_fixed}")
    print(f"  HTML removed: {result.html_removed}")
    print(f"  Normalized: {result.normalized}")
    print(f"  Actions: {', '.join(result.cleaning_actions)}")
    
    print(f"\nCleaned content preview: {result.cleaned_content[:200]}...")

if __name__ == "__main__":
    main()
