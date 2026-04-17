"""
Bias Detection Service
Analyzes political bias in articles and sources, similar to Ground News
Domain-aware: Only applies political bias detection to politics domain
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def calculate_domain_bias_score(
    domain: str, title: str, content: str, source: str = ""
) -> float | None:
    """
    Calculate bias score for an article based on domain.

    Args:
        domain: Domain name ('politics', 'finance', 'artificial-intelligence', …)
        title: Article title
        content: Article content
        source: Source name/domain

    Returns:
        bias_score: Float between -1.0 and 1.0, or None if bias detection not applicable
    """
    # Only apply bias detection to politics domain
    if domain not in ["politics"]:
        # Non-politics domains skip political bias detection
        return None

    # For politics domain, use simplified political bias detection
    try:
        text_lower = f"{title} {content}".lower()

        # Political bias keywords
        left_keywords = [
            "progressive",
            "liberal",
            "democratic",
            "socialist",
            "equality",
            "diversity",
            "climate change",
            "environmental",
            "healthcare",
            "union",
            "minimum wage",
            "social justice",
            "civil rights",
            "immigration reform",
            "gun control",
            "abortion rights",
            "lgbtq",
            "feminist",
            "woke",
            "systemic racism",
        ]

        right_keywords = [
            "conservative",
            "republican",
            "libertarian",
            "traditional",
            "patriot",
            "free market",
            "capitalism",
            "tax cuts",
            "small government",
            "states rights",
            "constitutional",
            "law and order",
            "border security",
            "immigration control",
            "gun rights",
            "pro-life",
            "family values",
            "religious",
            "america first",
        ]

        # Count keyword matches
        left_count = sum(1 for kw in left_keywords if kw in text_lower)
        right_count = sum(1 for kw in right_keywords if kw in text_lower)

        # Calculate bias score (-1.0 to 1.0)
        total_keywords = left_count + right_count
        if total_keywords == 0:
            return 0.0  # No political keywords found, neutral

        # Normalize to -1.0 to 1.0 range
        bias_score = (right_count - left_count) / max(total_keywords, 1)

        # Apply source bias if known
        known_left_sources = ["cnn", "msnbc", "new york times", "washington post", "guardian"]
        known_right_sources = ["fox news", "breitbart", "daily wire", "newsmax"]

        source_lower = source.lower()
        source_bias = 0.0
        if any(s in source_lower for s in known_left_sources):
            source_bias = -0.3
        elif any(s in source_lower for s in known_right_sources):
            source_bias = 0.3

        # Combine content bias (70%) and source bias (30%)
        final_score = (bias_score * 0.7) + (source_bias * 0.3)

        return max(-1.0, min(1.0, final_score))

    except Exception as e:
        logger.warning(f"Error calculating bias score: {e}")
        return 0.0  # Default to neutral on error


class BiasDetectionService:
    def __init__(self, db: Session):
        self.db = db

        # Political bias keywords and their weights
        self.left_keywords = {
            "progressive": 0.8,
            "liberal": 0.9,
            "democratic": 0.6,
            "socialist": 0.9,
            "equality": 0.7,
            "diversity": 0.6,
            "inclusion": 0.7,
            "climate change": 0.8,
            "environmental": 0.7,
            "healthcare": 0.6,
            "education": 0.5,
            "workers": 0.7,
            "union": 0.8,
            "minimum wage": 0.8,
            "social justice": 0.9,
            "civil rights": 0.8,
            "immigration reform": 0.7,
            "gun control": 0.8,
            "abortion rights": 0.9,
            "LGBTQ": 0.8,
            "feminist": 0.9,
            "woke": 0.8,
            "systemic racism": 0.9,
        }

        self.right_keywords = {
            "conservative": 0.8,
            "republican": 0.6,
            "libertarian": 0.7,
            "traditional": 0.6,
            "patriot": 0.7,
            "freedom": 0.6,
            "liberty": 0.7,
            "free market": 0.8,
            "capitalism": 0.8,
            "business": 0.5,
            "entrepreneur": 0.6,
            "tax cuts": 0.8,
            "small government": 0.9,
            "states rights": 0.8,
            "constitutional": 0.7,
            "law and order": 0.8,
            "border security": 0.8,
            "immigration control": 0.8,
            "gun rights": 0.8,
            "pro-life": 0.9,
            "family values": 0.8,
            "religious": 0.7,
            "patriotic": 0.7,
            "America first": 0.9,
            "drain the swamp": 0.8,
        }

        # Neutral/center indicators
        self.neutral_keywords = {
            "bipartisan": 0.8,
            "compromise": 0.7,
            "moderate": 0.8,
            "centrist": 0.8,
            "balanced": 0.7,
            "objective": 0.8,
            "factual": 0.9,
            "unbiased": 0.9,
            "nonpartisan": 0.8,
            "independent": 0.7,
        }

        # Bias indicators in language
        self.bias_indicators = {
            "emotional_language": [
                "outrageous",
                "shocking",
                "devastating",
                "incredible",
                "amazing",
            ],
            "loaded_terms": ["radical", "extreme", "dangerous", "threat", "crisis"],
            "subjective_adjectives": ["clearly", "obviously", "undoubtedly", "certainly"],
            "opinion_markers": ["I believe", "in my opinion", "it seems", "appears to be"],
        }

    def analyze_article_bias(self, article_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze political bias in an article"""
        try:
            title = article_data.get("title", "")
            content = article_data.get("content", "")
            source = article_data.get("source", "")

            # Get source bias rating
            source_bias = self._get_source_bias(source)

            # Analyze content bias
            content_analysis = self._analyze_content_bias(title, content)

            # Calculate overall bias score
            overall_bias_score = self._calculate_overall_bias(source_bias, content_analysis)

            # Determine political bias category
            political_bias = self._categorize_bias(overall_bias_score)

            # Extract bias keywords and indicators
            bias_keywords = self._extract_bias_keywords(title, content)
            bias_indicators = self._identify_bias_indicators(title, content)

            return {
                "political_bias": political_bias,
                "bias_score": overall_bias_score,
                "sentiment_score": content_analysis["sentiment"],
                "language_bias_score": content_analysis["language_bias"],
                "topic_bias_score": content_analysis["topic_bias"],
                "overall_bias_score": overall_bias_score,
                "bias_keywords": bias_keywords,
                "bias_indicators": bias_indicators,
                "source_bias": source_bias,
            }
        except Exception as e:
            logger.error(f"Error analyzing article bias: {e}")
            return self._get_neutral_bias()

    def _get_source_bias(self, source_name: str) -> dict[str, Any]:
        """Get bias rating for a source"""
        try:
            query = text("""
                SELECT political_bias, bias_score, credibility_score, factuality_score
                FROM source_bias_ratings
                WHERE source_name = :source_name
            """)

            result = self.db.execute(query, {"source_name": source_name}).fetchone()

            if result:
                return {
                    "political_bias": result[0],
                    "bias_score": float(result[1]),
                    "credibility_score": float(result[2]),
                    "factuality_score": float(result[3]),
                }
            else:
                # Default to center if source not found
                return {
                    "political_bias": "center",
                    "bias_score": 0.0,
                    "credibility_score": 0.5,
                    "factuality_score": 0.5,
                }
        except Exception as e:
            logger.error(f"Error getting source bias: {e}")
            return {
                "political_bias": "center",
                "bias_score": 0.0,
                "credibility_score": 0.5,
                "factuality_score": 0.5,
            }

    def _analyze_content_bias(self, title: str, content: str) -> dict[str, float]:
        """Analyze bias in article content"""
        text = f"{title} {content}".lower()

        # Analyze keyword bias
        left_score = self._calculate_keyword_score(text, self.left_keywords)
        right_score = self._calculate_keyword_score(text, self.right_keywords)
        neutral_score = self._calculate_keyword_score(text, self.neutral_keywords)

        # Calculate topic bias (difference between left and right scores)
        topic_bias = (right_score - left_score) / max(left_score + right_score, 1)

        # Analyze language bias
        language_bias = self._analyze_language_bias(text)

        # Calculate sentiment (positive/negative)
        sentiment = self._calculate_sentiment(text)

        return {
            "left_score": left_score,
            "right_score": right_score,
            "neutral_score": neutral_score,
            "topic_bias": topic_bias,
            "language_bias": language_bias,
            "sentiment": sentiment,
        }

    def _calculate_keyword_score(self, text: str, keywords: dict[str, float]) -> float:
        """Calculate bias score based on keywords"""
        total_score = 0.0
        keyword_count = 0

        for keyword, weight in keywords.items():
            count = text.count(keyword.lower())
            if count > 0:
                total_score += count * weight
                keyword_count += count

        return total_score / max(keyword_count, 1)

    def _analyze_language_bias(self, text: str) -> float:
        """Analyze language bias indicators"""
        bias_score = 0.0
        total_indicators = 0

        # Check for emotional language
        for word in self.bias_indicators["emotional_language"]:
            if word in text:
                bias_score += 0.1
                total_indicators += 1

        # Check for loaded terms
        for word in self.bias_indicators["loaded_terms"]:
            if word in text:
                bias_score += 0.2
                total_indicators += 1

        # Check for subjective adjectives
        for word in self.bias_indicators["subjective_adjectives"]:
            if word in text:
                bias_score += 0.1
                total_indicators += 1

        # Check for opinion markers
        for phrase in self.bias_indicators["opinion_markers"]:
            if phrase in text:
                bias_score += 0.3
                total_indicators += 1

        return min(bias_score, 1.0)  # Cap at 1.0

    def _calculate_sentiment(self, text: str) -> float:
        """Calculate basic sentiment score"""
        positive_words = ["good", "great", "excellent", "positive", "success", "win", "achievement"]
        negative_words = ["bad", "terrible", "awful", "negative", "failure", "lose", "problem"]

        positive_count = sum(text.count(word) for word in positive_words)
        negative_count = sum(text.count(word) for word in negative_words)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        return (positive_count - negative_count) / total

    def _calculate_overall_bias(
        self, source_bias: dict[str, Any], content_analysis: dict[str, float]
    ) -> float:
        """Calculate overall bias score combining source and content"""
        # Weight source bias 40% and content bias 60%
        source_weight = 0.4
        content_weight = 0.6

        source_score = source_bias["bias_score"]
        content_score = content_analysis["topic_bias"]

        overall = (source_score * source_weight) + (content_score * content_weight)

        # Normalize to -1 to 1 range
        return max(-1.0, min(1.0, overall))

    def _categorize_bias(self, bias_score: float) -> str:
        """Categorize bias score into political categories"""
        if bias_score <= -0.6:
            return "left"
        elif bias_score <= -0.2:
            return "center-left"
        elif bias_score <= 0.2:
            return "center"
        elif bias_score <= 0.6:
            return "center-right"
        else:
            return "right"

    def _extract_bias_keywords(self, title: str, content: str) -> list[str]:
        """Extract bias-related keywords from text"""
        text = f"{title} {content}".lower()
        found_keywords = []

        all_keywords = {**self.left_keywords, **self.right_keywords, **self.neutral_keywords}

        for keyword in all_keywords.keys():
            if keyword in text:
                found_keywords.append(keyword)

        return found_keywords[:10]  # Return top 10

    def _identify_bias_indicators(self, title: str, content: str) -> list[str]:
        """Identify bias indicators in text"""
        text = f"{title} {content}".lower()
        indicators = []

        for category, words in self.bias_indicators.items():
            for word in words:
                if word in text:
                    indicators.append(f"{category}: {word}")

        return indicators[:5]  # Return top 5

    def _get_neutral_bias(self) -> dict[str, Any]:
        """Return neutral bias analysis for errors"""
        return {
            "political_bias": "center",
            "bias_score": 0.0,
            "sentiment_score": 0.0,
            "language_bias_score": 0.0,
            "topic_bias_score": 0.0,
            "overall_bias_score": 0.0,
            "bias_keywords": [],
            "bias_indicators": [],
            "source_bias": {
                "political_bias": "center",
                "bias_score": 0.0,
                "credibility_score": 0.5,
                "factuality_score": 0.5,
            },
        }

    def get_bias_summary(self, article_ids: list[int]) -> dict[str, Any]:
        """Get bias summary for multiple articles"""
        try:
            query = text("""
                SELECT
                    aba.political_bias,
                    aba.overall_bias_score,
                    COUNT(*) as count
                FROM article_bias_analysis aba
                WHERE aba.article_id = ANY(:article_ids)
                GROUP BY aba.political_bias, aba.overall_bias_score
                ORDER BY count DESC
            """)

            result = self.db.execute(query, {"article_ids": article_ids}).fetchall()

            bias_summary = {
                "total_articles": len(article_ids),
                "bias_distribution": {},
                "average_bias_score": 0.0,
            }

            total_score = 0.0
            for row in result:
                bias = row[0]
                score = float(row[1])
                count = row[2]

                bias_summary["bias_distribution"][bias] = count
                total_score += score * count

            if len(article_ids) > 0:
                bias_summary["average_bias_score"] = total_score / len(article_ids)

            return bias_summary
        except Exception as e:
            logger.error(f"Error getting bias summary: {e}")
            return {"total_articles": 0, "bias_distribution": {}, "average_bias_score": 0.0}
