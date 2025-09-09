"""
Early Quality Validation Service for News Intelligence System v3.0
Implements fail-fast quality gates before expensive ML processing
"""

import asyncio
import logging
import re
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

@dataclass
class QualityScore:
    """Quality score breakdown"""
    overall_score: float
    content_length_score: float
    source_reliability_score: float
    readability_score: float
    freshness_score: float
    language_score: float
    spam_score: float
    is_passing: bool
    rejection_reasons: List[str]

class EarlyQualityService:
    """Early quality validation service with fail-fast principles"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.quality_threshold = 0.3  # Base threshold
        self.source_reliability_scores = self._load_source_reliability()
        
    def _load_source_reliability(self) -> Dict[str, float]:
        """Load source reliability scores from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT source, AVG(quality_score) as avg_quality
                FROM articles 
                WHERE quality_score IS NOT NULL 
                AND created_at > NOW() - INTERVAL '30 days'
                GROUP BY source
                HAVING COUNT(*) > 10
            """)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            reliability_scores = {}
            for row in results:
                reliability_scores[row['source']] = float(row['avg_quality'])
            
            logger.info(f"Loaded reliability scores for {len(reliability_scores)} sources")
            return reliability_scores
            
        except Exception as e:
            logger.error(f"Error loading source reliability scores: {e}")
            return {}
    
    async def validate_article_quality(self, article: Dict[str, Any]) -> QualityScore:
        """Comprehensive early quality validation"""
        try:
            # Extract article data
            title = article.get('title', '')
            content = article.get('content', '')
            source = article.get('source', '')
            url = article.get('url', '')
            published_at = article.get('published_at')
            
            # Calculate individual quality scores
            content_length_score = self._calculate_content_length_score(content)
            source_reliability_score = self._calculate_source_reliability_score(source)
            readability_score = self._calculate_readability_score(content)
            freshness_score = self._calculate_freshness_score(published_at)
            language_score = self._calculate_language_score(content)
            spam_score = self._calculate_spam_score(title, content, url)
            
            # Calculate overall score (weighted average)
            overall_score = self._calculate_overall_score(
                content_length_score,
                source_reliability_score,
                readability_score,
                freshness_score,
                language_score,
                spam_score
            )
            
            # Determine if passing
            is_passing, rejection_reasons = self._evaluate_quality_threshold(
                overall_score,
                content_length_score,
                source_reliability_score,
                readability_score,
                freshness_score,
                language_score,
                spam_score
            )
            
            return QualityScore(
                overall_score=overall_score,
                content_length_score=content_length_score,
                source_reliability_score=source_reliability_score,
                readability_score=readability_score,
                freshness_score=freshness_score,
                language_score=language_score,
                spam_score=spam_score,
                is_passing=is_passing,
                rejection_reasons=rejection_reasons
            )
            
        except Exception as e:
            logger.error(f"Error validating article quality: {e}")
            return QualityScore(
                overall_score=0.0,
                content_length_score=0.0,
                source_reliability_score=0.0,
                readability_score=0.0,
                freshness_score=0.0,
                language_score=0.0,
                spam_score=1.0,  # Assume spam if error
                is_passing=False,
                rejection_reasons=[f"Validation error: {str(e)}"]
            )
    
    def _calculate_content_length_score(self, content: str) -> float:
        """Calculate content length quality score"""
        if not content:
            return 0.0
        
        word_count = len(content.split())
        
        # Optimal range: 200-2000 words
        if word_count < 50:
            return 0.1  # Too short
        elif word_count < 200:
            return 0.3 + (word_count - 50) / 150 * 0.4  # 0.3-0.7
        elif word_count <= 2000:
            return 0.7 + (word_count - 200) / 1800 * 0.3  # 0.7-1.0
        elif word_count <= 5000:
            return 1.0 - (word_count - 2000) / 3000 * 0.2  # 1.0-0.8
        else:
            return 0.8  # Very long but acceptable
    
    def _calculate_source_reliability_score(self, source: str) -> float:
        """Calculate source reliability score"""
        if not source:
            return 0.5  # Unknown source
        
        # Check cached reliability score
        if source in self.source_reliability_scores:
            return self.source_reliability_scores[source]
        
        # Default scores for known sources
        known_sources = {
            'Reuters': 0.95,
            'Associated Press': 0.95,
            'BBC': 0.90,
            'CNN': 0.85,
            'The New York Times': 0.90,
            'The Washington Post': 0.90,
            'The Guardian': 0.85,
            'NPR': 0.90,
            'PBS': 0.90,
            'ABC News': 0.80,
            'CBS News': 0.80,
            'NBC News': 0.80,
            'Fox News': 0.75,
            'MSNBC': 0.75,
            'Politico': 0.85,
            'Bloomberg': 0.90,
            'Wall Street Journal': 0.90,
            'Financial Times': 0.90,
            'The Economist': 0.90,
            'Time': 0.80,
            'Newsweek': 0.75,
            'USA Today': 0.70,
            'Los Angeles Times': 0.80,
            'Chicago Tribune': 0.75,
            'Boston Globe': 0.80,
            'Miami Herald': 0.70,
            'Denver Post': 0.70,
            'Seattle Times': 0.75,
            'Houston Chronicle': 0.70,
            'Dallas Morning News': 0.70
        }
        
        return known_sources.get(source, 0.5)  # Default for unknown sources
    
    def _calculate_readability_score(self, content: str) -> float:
        """Calculate readability quality score"""
        if not content:
            return 0.0
        
        # Simple readability metrics
        sentences = len(re.findall(r'[.!?]+', content))
        words = len(content.split())
        syllables = self._count_syllables(content)
        
        if sentences == 0 or words == 0:
            return 0.0
        
        # Flesch Reading Ease approximation
        avg_sentence_length = words / sentences
        avg_syllables_per_word = syllables / words
        
        # Simplified Flesch score
        flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        
        # Convert to 0-1 scale (higher is better)
        if flesch_score >= 80:
            return 1.0  # Very easy
        elif flesch_score >= 60:
            return 0.9  # Easy
        elif flesch_score >= 40:
            return 0.8  # Standard
        elif flesch_score >= 20:
            return 0.6  # Difficult
        else:
            return 0.3  # Very difficult
    
    def _count_syllables(self, text: str) -> int:
        """Count syllables in text (approximation)"""
        words = text.lower().split()
        syllable_count = 0
        
        for word in words:
            # Remove punctuation
            word = re.sub(r'[^a-z]', '', word)
            if not word:
                continue
            
            # Simple syllable counting
            vowels = 'aeiouy'
            syllable_count += 1
            
            for i in range(1, len(word)):
                if word[i] in vowels and word[i-1] not in vowels:
                    syllable_count += 1
            
            # Remove silent 'e'
            if word.endswith('e'):
                syllable_count -= 1
            
            # Ensure at least one syllable
            if syllable_count == 0:
                syllable_count = 1
        
        return syllable_count
    
    def _calculate_freshness_score(self, published_at) -> float:
        """Calculate content freshness score"""
        if not published_at:
            return 0.5  # Unknown age
        
        try:
            if isinstance(published_at, str):
                published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            else:
                published_date = published_at
            
            # Ensure timezone awareness
            if published_date.tzinfo is None:
                published_date = published_date.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            age_hours = (now - published_date).total_seconds() / 3600
            
            # Freshness scoring
            if age_hours <= 1:
                return 1.0  # Very fresh
            elif age_hours <= 6:
                return 0.9  # Fresh
            elif age_hours <= 24:
                return 0.8  # Recent
            elif age_hours <= 72:
                return 0.6  # Somewhat old
            elif age_hours <= 168:  # 1 week
                return 0.4  # Old
            else:
                return 0.2  # Very old
                
        except Exception as e:
            logger.warning(f"Error calculating freshness score: {e}")
            return 0.5  # Default for parsing errors
    
    def _calculate_language_score(self, content: str) -> float:
        """Calculate language quality score"""
        if not content:
            return 0.0
        
        # Check for English content
        english_words = re.findall(r'\b[a-zA-Z]+\b', content)
        total_words = len(content.split())
        
        if total_words == 0:
            return 0.0
        
        english_ratio = len(english_words) / total_words
        
        # Check for proper capitalization
        proper_caps = len(re.findall(r'\b[A-Z][a-z]+\b', content))
        proper_cap_ratio = proper_caps / max(len(english_words), 1)
        
        # Check for excessive repetition
        words = content.lower().split()
        word_counts = {}
        for word in words:
            if len(word) > 3:  # Only count meaningful words
                word_counts[word] = word_counts.get(word, 0) + 1
        
        max_repetition = max(word_counts.values()) if word_counts else 0
        repetition_penalty = min(max_repetition / len(words), 0.5) if words else 0
        
        # Combine metrics
        language_score = (english_ratio * 0.6 + proper_cap_ratio * 0.4) - repetition_penalty
        return max(0.0, min(1.0, language_score))
    
    def _calculate_spam_score(self, title: str, content: str, url: str) -> float:
        """Calculate spam/quality score (lower is better)"""
        spam_indicators = 0
        total_checks = 0
        
        # Check title for spam indicators
        if title:
            total_checks += 1
            title_lower = title.lower()
            
            # Excessive caps
            if len(title) > 10 and sum(1 for c in title if c.isupper()) / len(title) > 0.7:
                spam_indicators += 1
            
            # Spam keywords
            spam_keywords = ['click here', 'free', 'win', 'prize', 'urgent', 'act now', 'limited time']
            if any(keyword in title_lower for keyword in spam_keywords):
                spam_indicators += 1
            
            # Excessive punctuation
            if title.count('!') > 2 or title.count('?') > 2:
                spam_indicators += 1
        
        # Check content for spam indicators
        if content:
            total_checks += 1
            content_lower = content.lower()
            
            # Excessive repetition
            words = content.split()
            if len(words) > 100:
                word_counts = {}
                for word in words:
                    if len(word) > 3:
                        word_counts[word] = word_counts.get(word, 0) + 1
                
                max_repetition = max(word_counts.values()) if word_counts else 0
                if max_repetition > len(words) * 0.1:  # More than 10% repetition
                    spam_indicators += 1
            
            # Spam phrases
            spam_phrases = ['make money', 'work from home', 'get rich', 'lose weight', 'viagra', 'casino']
            if any(phrase in content_lower for phrase in spam_phrases):
                spam_indicators += 1
        
        # Check URL for spam indicators
        if url:
            total_checks += 1
            url_lower = url.lower()
            
            # Suspicious domains
            suspicious_domains = ['.tk', '.ml', '.ga', '.cf', 'bit.ly', 'tinyurl']
            if any(domain in url_lower for domain in suspicious_domains):
                spam_indicators += 1
            
            # Excessive parameters
            if url.count('?') > 0 and len(url.split('?')[1]) > 100:
                spam_indicators += 1
        
        if total_checks == 0:
            return 0.0
        
        # Convert to 0-1 scale (lower is better)
        spam_ratio = spam_indicators / total_checks
        return 1.0 - spam_ratio  # Invert so higher is better
    
    def _calculate_overall_score(self, content_length_score: float, source_reliability_score: float,
                               readability_score: float, freshness_score: float,
                               language_score: float, spam_score: float) -> float:
        """Calculate weighted overall quality score"""
        weights = {
            'content_length': 0.20,
            'source_reliability': 0.25,
            'readability': 0.15,
            'freshness': 0.15,
            'language': 0.10,
            'spam': 0.15
        }
        
        overall_score = (
            content_length_score * weights['content_length'] +
            source_reliability_score * weights['source_reliability'] +
            readability_score * weights['readability'] +
            freshness_score * weights['freshness'] +
            language_score * weights['language'] +
            spam_score * weights['spam']
        )
        
        return max(0.0, min(1.0, overall_score))
    
    def _evaluate_quality_threshold(self, overall_score: float, content_length_score: float,
                                  source_reliability_score: float, readability_score: float,
                                  freshness_score: float, language_score: float,
                                  spam_score: float) -> Tuple[bool, List[str]]:
        """Evaluate if article passes quality threshold"""
        rejection_reasons = []
        
        # Overall score threshold
        if overall_score < self.quality_threshold:
            rejection_reasons.append(f"Overall score {overall_score:.2f} below threshold {self.quality_threshold}")
        
        # Individual score thresholds
        if content_length_score < 0.2:
            rejection_reasons.append(f"Content too short (score: {content_length_score:.2f})")
        
        if source_reliability_score < 0.3:
            rejection_reasons.append(f"Source reliability too low (score: {source_reliability_score:.2f})")
        
        if readability_score < 0.3:
            rejection_reasons.append(f"Readability too low (score: {readability_score:.2f})")
        
        if freshness_score < 0.2:
            rejection_reasons.append(f"Content too old (score: {freshness_score:.2f})")
        
        if language_score < 0.4:
            rejection_reasons.append(f"Language quality too low (score: {language_score:.2f})")
        
        if spam_score < 0.5:
            rejection_reasons.append(f"Spam indicators detected (score: {spam_score:.2f})")
        
        is_passing = len(rejection_reasons) == 0
        return is_passing, rejection_reasons
    
    def adjust_quality_threshold(self, current_volume: int, system_load: float) -> None:
        """Adjust quality threshold based on system load and volume"""
        base_threshold = 0.3
        
        # Adjust for volume (stricter for high volume)
        volume_factor = min(current_volume / 1000, 0.1)
        
        # Adjust for system load (stricter for high load)
        load_factor = min(system_load, 0.1)
        
        self.quality_threshold = base_threshold + volume_factor + load_factor
        self.quality_threshold = max(0.1, min(0.8, self.quality_threshold))  # Clamp between 0.1 and 0.8
        
        logger.info(f"Adjusted quality threshold to {self.quality_threshold:.2f} (volume: {current_volume}, load: {system_load:.2f})")
    
    async def batch_validate_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of articles with parallel processing"""
        try:
            logger.info(f"Validating {len(articles)} articles for quality")
            
            validation_tasks = []
            for article in articles:
                task = self.validate_article_quality(article)
                validation_tasks.append(task)
            
            # Process in parallel
            quality_scores = await asyncio.gather(*validation_tasks)
            
            # Separate passing and failing articles
            passing_articles = []
            failing_articles = []
            
            for i, (article, quality_score) in enumerate(zip(articles, quality_scores)):
                if quality_score.is_passing:
                    article['quality_score'] = quality_score.overall_score
                    article['quality_breakdown'] = {
                        'content_length': quality_score.content_length_score,
                        'source_reliability': quality_score.source_reliability_score,
                        'readability': quality_score.readability_score,
                        'freshness': quality_score.freshness_score,
                        'language': quality_score.language_score,
                        'spam': quality_score.spam_score
                    }
                    passing_articles.append(article)
                else:
                    failing_articles.append({
                        'article': article,
                        'rejection_reasons': quality_score.rejection_reasons,
                        'quality_score': quality_score.overall_score
                    })
            
            logger.info(f"Quality validation complete: {len(passing_articles)} passing, {len(failing_articles)} failing")
            
            return {
                'success': True,
                'passing_articles': passing_articles,
                'failing_articles': failing_articles,
                'total_processed': len(articles),
                'pass_rate': len(passing_articles) / len(articles) if articles else 0,
                'quality_threshold': self.quality_threshold
            }
            
        except Exception as e:
            logger.error(f"Error in batch validation: {e}")
            return {
                'success': False,
                'error': str(e),
                'passing_articles': [],
                'failing_articles': articles,  # Fail safe - reject all on error
                'total_processed': len(articles),
                'pass_rate': 0.0
            }

# Global instance
_early_quality_service = None

def get_early_quality_service() -> EarlyQualityService:
    """Get global early quality service instance"""
    global _early_quality_service
    if _early_quality_service is None:
        from database.connection import get_db_config
        _early_quality_service = EarlyQualityService(get_db_config())
    return _early_quality_service


