"""
Quality Scorer for News Intelligence System
Provides content quality assessment and scoring
"""

import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    Content quality assessment and scoring system
    """

    def __init__(self):
        """Initialize the Quality Scorer"""
        self.weights = {
            "content_length": 0.15,
            "readability": 0.20,
            "structure": 0.15,
            "uniqueness": 0.15,
            "completeness": 0.15,
            "language_quality": 0.20,
        }

    def score_content(
        self, content: str, title: str = None, metadata: dict = None
    ) -> dict[str, any]:
        """
        Score content quality across multiple dimensions

        Args:
            content: The content to score
            title: Optional title for context
            metadata: Optional metadata from content analysis

        Returns:
            Dictionary containing quality scores and analysis
        """
        try:
            if not content:
                return self._create_empty_score("empty_content")

            # Calculate individual scores
            length_score = self._score_content_length(content)
            readability_score = self._score_readability(content)
            structure_score = self._score_structure(content)
            uniqueness_score = self._score_uniqueness(content)
            completeness_score = self._score_completeness(content, title)
            language_score = self._score_language_quality(content)

            # Calculate weighted overall score
            overall_score = (
                length_score * self.weights["content_length"]
                + readability_score * self.weights["readability"]
                + structure_score * self.weights["structure"]
                + uniqueness_score * self.weights["uniqueness"]
                + completeness_score * self.weights["completeness"]
                + language_score * self.weights["language_quality"]
            )

            # Determine quality grade
            grade = self._determine_grade(overall_score)

            return {
                "overall_score": round(overall_score, 3),
                "grade": grade,
                "dimensions": {
                    "content_length": {
                        "score": length_score,
                        "weight": self.weights["content_length"],
                        "details": self._get_length_details(content),
                    },
                    "readability": {
                        "score": readability_score,
                        "weight": self.weights["readability"],
                        "details": self._get_readability_details(content),
                    },
                    "structure": {
                        "score": structure_score,
                        "weight": self.weights["structure"],
                        "details": self._get_structure_details(content),
                    },
                    "uniqueness": {
                        "score": uniqueness_score,
                        "weight": self.weights["uniqueness"],
                        "details": self._get_uniqueness_details(content),
                    },
                    "completeness": {
                        "score": completeness_score,
                        "weight": self.weights["completeness"],
                        "details": self._get_completeness_details(content, title),
                    },
                    "language_quality": {
                        "score": language_score,
                        "weight": self.weights["language_quality"],
                        "details": self._get_language_details(content),
                    },
                },
                "recommendations": self._generate_recommendations(
                    overall_score,
                    {
                        "length": length_score,
                        "readability": readability_score,
                        "structure": structure_score,
                        "uniqueness": uniqueness_score,
                        "completeness": completeness_score,
                        "language": language_score,
                    },
                ),
                "scored_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error scoring content: {e}")
            return self._create_empty_score("scoring_error", str(e))

    def _score_content_length(self, content: str) -> float:
        """Score based on content length"""
        word_count = len(content.split())

        # Optimal range: 200-1000 words
        if 200 <= word_count <= 1000:
            return 1.0
        elif 100 <= word_count < 200:
            return 0.7
        elif 50 <= word_count < 100:
            return 0.4
        elif word_count > 1000:
            return max(0.3, 1.0 - (word_count - 1000) / 5000)  # Penalty for very long content
        else:
            return 0.1

    def _score_readability(self, content: str) -> float:
        """Score based on readability (simplified Flesch Reading Ease)"""
        try:
            sentences = re.split(r"[.!?]+", content)
            sentences = [s.strip() for s in sentences if s.strip()]

            if not sentences:
                return 0.0

            words = content.split()
            syllables = sum(self._count_syllables(word) for word in words)

            if len(sentences) == 0 or len(words) == 0:
                return 0.0

            # Simplified Flesch Reading Ease
            avg_sentence_length = len(words) / len(sentences)
            avg_syllables_per_word = syllables / len(words)

            # Simplified formula (not exact Flesch)
            score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)

            # Normalize to 0-1 scale
            if score >= 80:  # Very easy
                return 1.0
            elif score >= 60:  # Easy
                return 0.8
            elif score >= 40:  # Moderate
                return 0.6
            elif score >= 20:  # Difficult
                return 0.4
            else:  # Very difficult
                return 0.2

        except Exception as e:
            logger.error(f"Error calculating readability: {e}")
            return 0.5

    def _score_structure(self, content: str) -> float:
        """Score based on content structure"""
        score = 0.0

        # Check for paragraphs
        paragraphs = content.split("\n\n")
        if len(paragraphs) > 1:
            score += 0.3

        # Check for proper sentence structure
        sentences = re.split(r"[.!?]+", content)
        valid_sentences = [s for s in sentences if len(s.strip()) > 10]
        if len(valid_sentences) >= 3:
            score += 0.3

        # Check for variety in sentence length
        sentence_lengths = [len(s.split()) for s in valid_sentences]
        if len(sentence_lengths) > 1:
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((sl - avg_length) ** 2 for sl in sentence_lengths) / len(
                sentence_lengths
            )
            if variance > 10:  # Good variety
                score += 0.2

        # Check for proper capitalization
        if re.search(r"[A-Z]", content):
            score += 0.2

        return min(1.0, score)

    def _score_uniqueness(self, content: str) -> float:
        """Score based on content uniqueness"""
        words = content.lower().split()
        if not words:
            return 0.0

        # Remove common words
        common_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
        }

        unique_words = [w for w in words if w not in common_words and len(w) > 2]

        if not unique_words:
            return 0.0

        # Calculate uniqueness ratio
        unique_ratio = len(set(unique_words)) / len(unique_words)

        # Penalize repetitive content
        if unique_ratio < 0.3:
            return 0.2
        elif unique_ratio < 0.5:
            return 0.5
        elif unique_ratio < 0.7:
            return 0.8
        else:
            return 1.0

    def _score_completeness(self, content: str, title: str = None) -> float:
        """Score based on content completeness"""
        score = 0.0

        # Check for title
        if title and len(title.strip()) > 5:
            score += 0.2

        # Check for introduction (first sentence/paragraph)
        first_paragraph = content.split("\n\n")[0] if "\n\n" in content else content
        if len(first_paragraph) > 50:
            score += 0.2

        # Check for conclusion (last sentence/paragraph)
        last_paragraph = content.split("\n\n")[-1] if "\n\n" in content else content
        if len(last_paragraph) > 30:
            score += 0.2

        # Check for substantive content
        words = content.split()
        if len(words) > 100:
            score += 0.2

        # Check for multiple topics/points
        sentences = re.split(r"[.!?]+", content)
        if len(sentences) >= 5:
            score += 0.2

        return min(1.0, score)

    def _score_language_quality(self, content: str) -> float:
        """Score based on language quality"""
        score = 0.0

        # Check for proper punctuation
        if re.search(r"[.!?]", content):
            score += 0.2

        # Check for proper capitalization
        if re.search(r"[A-Z]", content):
            score += 0.2

        # Check for spelling (basic heuristic - no obvious typos)
        words = content.split()
        if words:
            # Simple check for repeated characters (likely typos)
            typo_count = sum(1 for word in words if re.search(r"(.)\1{2,}", word))
            if typo_count == 0:
                score += 0.2
            elif typo_count <= len(words) * 0.01:  # Less than 1% typos
                score += 0.1

        # Check for proper sentence structure
        sentences = re.split(r"[.!?]+", content)
        valid_sentences = [s for s in sentences if len(s.strip()) > 5]
        if len(valid_sentences) >= 3:
            score += 0.2

        # Check for variety in vocabulary
        unique_words = set(word.lower() for word in words if len(word) > 3)
        if len(unique_words) > 20:
            score += 0.2

        return min(1.0, score)

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (approximation)"""
        word = word.lower()
        vowels = "aeiouy"
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        # Handle silent 'e'
        if word.endswith("e") and syllable_count > 1:
            syllable_count -= 1

        return max(1, syllable_count)

    def _determine_grade(self, score: float) -> str:
        """Determine quality grade based on score"""
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B+"
        elif score >= 0.6:
            return "B"
        elif score >= 0.5:
            return "C+"
        elif score >= 0.4:
            return "C"
        elif score >= 0.3:
            return "D"
        else:
            return "F"

    def _get_length_details(self, content: str) -> dict:
        """Get details about content length"""
        word_count = len(content.split())
        char_count = len(content)

        return {
            "word_count": word_count,
            "character_count": char_count,
            "assessment": "optimal" if 200 <= word_count <= 1000 else "suboptimal",
        }

    def _get_readability_details(self, content: str) -> dict:
        """Get readability details"""
        sentences = re.split(r"[.!?]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = content.split()

        return {
            "sentence_count": len(sentences),
            "word_count": len(words),
            "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
            "assessment": "good"
            if sentences and 10 <= len(words) / len(sentences) <= 25
            else "needs_improvement",
        }

    def _get_structure_details(self, content: str) -> dict:
        """Get structure details"""
        paragraphs = content.split("\n\n")
        sentences = re.split(r"[.!?]+", content)

        return {
            "paragraph_count": len(paragraphs),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "has_proper_structure": len(paragraphs) > 1 and len(sentences) >= 3,
        }

    def _get_uniqueness_details(self, content: str) -> dict:
        """Get uniqueness details"""
        words = content.lower().split()
        unique_words = set(words)

        return {
            "total_words": len(words),
            "unique_words": len(unique_words),
            "uniqueness_ratio": len(unique_words) / len(words) if words else 0,
        }

    def _get_completeness_details(self, content: str, title: str = None) -> dict:
        """Get completeness details"""
        return {
            "has_title": bool(title and len(title.strip()) > 5),
            "has_introduction": len(content.split("\n\n")[0]) > 50
            if "\n\n" in content
            else len(content) > 50,
            "has_conclusion": len(content.split("\n\n")[-1]) > 30
            if "\n\n" in content
            else len(content) > 30,
            "word_count": len(content.split()),
        }

    def _get_language_details(self, content: str) -> dict:
        """Get language quality details"""
        sentences = re.split(r"[.!?]+", content)
        words = content.split()

        return {
            "has_proper_punctuation": bool(re.search(r"[.!?]", content)),
            "has_proper_capitalization": bool(re.search(r"[A-Z]", content)),
            "sentence_count": len([s for s in sentences if s.strip()]),
            "vocabulary_size": len(set(word.lower() for word in words if len(word) > 3)),
        }

    def _generate_recommendations(self, overall_score: float, dimension_scores: dict) -> list[str]:
        """Generate improvement recommendations"""
        recommendations = []

        if overall_score < 0.6:
            recommendations.append("Overall content quality needs improvement")

        if dimension_scores["length"] < 0.5:
            recommendations.append("Consider adjusting content length (optimal: 200-1000 words)")

        if dimension_scores["readability"] < 0.5:
            recommendations.append(
                "Improve readability by using shorter sentences and simpler words"
            )

        if dimension_scores["structure"] < 0.5:
            recommendations.append("Improve structure with clear paragraphs and proper formatting")

        if dimension_scores["uniqueness"] < 0.5:
            recommendations.append("Reduce repetitive content and increase vocabulary variety")

        if dimension_scores["completeness"] < 0.5:
            recommendations.append("Ensure content has proper introduction, body, and conclusion")

        if dimension_scores["language"] < 0.5:
            recommendations.append("Improve language quality with proper grammar and punctuation")

        if not recommendations:
            recommendations.append("Content quality is good - no major improvements needed")

        return recommendations

    def _create_empty_score(self, reason: str, error: str = None) -> dict:
        """Create empty score result"""
        return {
            "overall_score": 0.0,
            "grade": "F",
            "dimensions": {},
            "recommendations": [f"Cannot score content: {reason}"],
            "scored_at": datetime.now().isoformat(),
            "error": error,
        }
