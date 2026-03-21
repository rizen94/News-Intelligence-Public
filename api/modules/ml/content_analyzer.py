"""
Content Analyzer for News Intelligence System
Provides content analysis, deduplication, and quality assessment
"""

import hashlib
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    Content analysis and processing utilities
    """

    def __init__(self):
        """Initialize the Content Analyzer"""
        self.min_content_length = 100  # Minimum content length for processing
        self.max_content_length = 50000  # Maximum content length for processing

    def generate_content_hash(self, content: str) -> str:
        """
        Generate a hash for content deduplication

        Args:
            content: The content to hash

        Returns:
            SHA256 hash of the normalized content
        """
        try:
            # Normalize content for consistent hashing
            normalized = self._normalize_content(content)

            # Generate hash
            content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

            logger.debug(f"Generated content hash: {content_hash[:16]}...")
            return content_hash

        except Exception as e:
            logger.error(f"Error generating content hash: {e}")
            return ""

    def _normalize_content(self, content: str) -> str:
        """
        Normalize content for consistent processing

        Args:
            content: Raw content

        Returns:
            Normalized content
        """
        if not content:
            return ""

        # Convert to lowercase
        normalized = content.lower()

        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Remove common punctuation variations
        normalized = re.sub(r'[""' "`]", '"', normalized)
        normalized = re.sub(r"[–—]", "-", normalized)

        # Remove extra spaces around punctuation
        normalized = re.sub(r"\s+([.,!?;:])", r"\1", normalized)

        return normalized.strip()

    def is_duplicate_content(self, content1: str, content2: str, threshold: float = 0.8) -> bool:
        """
        Check if two pieces of content are duplicates using simple similarity

        Args:
            content1: First content piece
            content2: Second content piece
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            True if content is considered duplicate
        """
        try:
            if not content1 or not content2:
                return False

            # Normalize both contents
            norm1 = self._normalize_content(content1)
            norm2 = self._normalize_content(content2)

            # Check exact match first
            if norm1 == norm2:
                return True

            # Simple similarity check using word overlap
            words1 = set(norm1.split())
            words2 = set(norm2.split())

            if len(words1) == 0 or len(words2) == 0:
                return False

            # Calculate Jaccard similarity
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))

            similarity = intersection / union if union > 0 else 0

            return similarity >= threshold

        except Exception as e:
            logger.error(f"Error checking content duplication: {e}")
            return False

    def extract_metadata(self, content: str, title: str = None) -> dict[str, any]:
        """
        Extract metadata from content

        Args:
            content: The content to analyze
            title: Optional title for context

        Returns:
            Dictionary containing extracted metadata
        """
        try:
            metadata = {
                "word_count": 0,
                "sentence_count": 0,
                "paragraph_count": 0,
                "reading_time_minutes": 0,
                "has_numbers": False,
                "has_urls": False,
                "has_emails": False,
                "language_indicators": [],
                "extracted_at": datetime.now().isoformat(),
            }

            if not content:
                return metadata

            # Word count
            words = content.split()
            metadata["word_count"] = len(words)

            # Sentence count (simple heuristic)
            sentences = re.split(r"[.!?]+", content)
            metadata["sentence_count"] = len([s for s in sentences if s.strip()])

            # Paragraph count
            paragraphs = content.split("\n\n")
            metadata["paragraph_count"] = len([p for p in paragraphs if p.strip()])

            # Reading time (average 200 words per minute)
            metadata["reading_time_minutes"] = max(1, metadata["word_count"] // 200)

            # Check for numbers
            metadata["has_numbers"] = bool(re.search(r"\d+", content))

            # Check for URLs
            url_pattern = (
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
            )
            metadata["has_urls"] = bool(re.search(url_pattern, content))

            # Check for emails
            email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            metadata["has_emails"] = bool(re.search(email_pattern, content))

            # Language indicators (simple heuristics)
            language_indicators = []
            if re.search(r"\b(the|and|or|but|in|on|at|to|for|of|with|by)\b", content.lower()):
                language_indicators.append("english")
            if re.search(
                r"\b(der|die|das|und|oder|aber|in|auf|zu|für|von|mit|bei)\b", content.lower()
            ):
                language_indicators.append("german")
            if re.search(
                r"\b(le|la|les|et|ou|mais|dans|sur|à|pour|de|avec|par)\b", content.lower()
            ):
                language_indicators.append("french")

            metadata["language_indicators"] = language_indicators

            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {
                "word_count": 0,
                "sentence_count": 0,
                "paragraph_count": 0,
                "reading_time_minutes": 0,
                "has_numbers": False,
                "has_urls": False,
                "has_emails": False,
                "language_indicators": [],
                "extracted_at": datetime.now().isoformat(),
                "error": str(e),
            }

    def clean_content(self, content: str) -> dict[str, any]:
        """
        Clean and normalize content

        Args:
            content: Raw content to clean

        Returns:
            Dictionary containing cleaned content and cleaning metadata
        """
        try:
            if not content:
                return {
                    "cleaned_content": "",
                    "original_length": 0,
                    "cleaned_length": 0,
                    "changes_made": [],
                    "cleaned_at": datetime.now().isoformat(),
                }

            original_length = len(content)
            cleaned = content
            changes = []

            # Remove HTML tags
            if "<" in cleaned and ">" in cleaned:
                cleaned = re.sub(r"<[^>]+>", "", cleaned)
                changes.append("removed_html_tags")

            # Remove extra whitespace
            if re.search(r"\s{3,}", cleaned):
                cleaned = re.sub(r"\s{3,}", " ", cleaned)
                changes.append("normalized_whitespace")

            # Remove common artifacts
            if "\xa0" in cleaned:  # Non-breaking spaces
                cleaned = cleaned.replace("\xa0", " ")
                changes.append("removed_nbsp")

            if "\u2019" in cleaned:  # Smart quotes
                cleaned = cleaned.replace("\u2019", "'")
                changes.append("normalized_quotes")

            # Remove leading/trailing whitespace
            cleaned = cleaned.strip()

            cleaned_length = len(cleaned)

            return {
                "cleaned_content": cleaned,
                "original_length": original_length,
                "cleaned_length": cleaned_length,
                "changes_made": changes,
                "cleaned_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error cleaning content: {e}")
            return {
                "cleaned_content": content if content else "",
                "original_length": len(content) if content else 0,
                "cleaned_length": 0,
                "changes_made": [],
                "cleaned_at": datetime.now().isoformat(),
                "error": str(e),
            }

    def validate_content_quality(self, content: str, title: str = None) -> dict[str, any]:
        """
        Validate content quality and provide recommendations

        Args:
            content: Content to validate
            title: Optional title for context

        Returns:
            Dictionary containing quality assessment
        """
        try:
            quality_assessment = {
                "is_valid": False,
                "quality_score": 0.0,
                "issues": [],
                "recommendations": [],
                "assessed_at": datetime.now().isoformat(),
            }

            if not content:
                quality_assessment["issues"].append("empty_content")
                quality_assessment["recommendations"].append("Content is empty")
                return quality_assessment

            # Check minimum length
            if len(content) < self.min_content_length:
                quality_assessment["issues"].append("too_short")
                quality_assessment["recommendations"].append(
                    f"Content too short (minimum {self.min_content_length} characters)"
                )

            # Check maximum length
            if len(content) > self.max_content_length:
                quality_assessment["issues"].append("too_long")
                quality_assessment["recommendations"].append(
                    f"Content too long (maximum {self.max_content_length} characters)"
                )

            # Check for meaningful content
            words = content.split()
            if len(words) < 20:
                quality_assessment["issues"].append("insufficient_words")
                quality_assessment["recommendations"].append(
                    "Content has too few words for meaningful analysis"
                )

            # Check for repetitive content
            if len(set(words)) < len(words) * 0.3:  # Less than 30% unique words
                quality_assessment["issues"].append("repetitive_content")
                quality_assessment["recommendations"].append("Content appears repetitive")

            # Check for proper sentence structure
            sentences = re.split(r"[.!?]+", content)
            valid_sentences = [s for s in sentences if len(s.strip()) > 10]
            if len(valid_sentences) < 2:
                quality_assessment["issues"].append("poor_sentence_structure")
                quality_assessment["recommendations"].append(
                    "Content lacks proper sentence structure"
                )

            # Calculate quality score
            quality_score = 1.0
            for issue in quality_assessment["issues"]:
                if issue in ["too_short", "too_long", "insufficient_words"]:
                    quality_score -= 0.3
                elif issue in ["repetitive_content", "poor_sentence_structure"]:
                    quality_score -= 0.2
                else:
                    quality_score -= 0.1

            quality_assessment["quality_score"] = max(0.0, quality_score)
            quality_assessment["is_valid"] = (
                quality_score >= 0.5 and len(quality_assessment["issues"]) == 0
            )

            return quality_assessment

        except Exception as e:
            logger.error(f"Error validating content quality: {e}")
            return {
                "is_valid": False,
                "quality_score": 0.0,
                "issues": ["validation_error"],
                "recommendations": [f"Error during validation: {str(e)}"],
                "assessed_at": datetime.now().isoformat(),
                "error": str(e),
            }
