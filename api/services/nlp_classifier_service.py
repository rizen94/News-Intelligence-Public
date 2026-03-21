"""
NLP Classifier Service for News Intelligence System v3.0
Local zero-shot classification for content filtering using HuggingFace transformers
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

# Try to import transformers, fall back to basic text analysis if not available
try:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers library not available - using basic text analysis")

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of content classification"""

    label: str
    confidence: float
    is_relevant: bool
    reasoning: str


class NLPClassifierService:
    """Local NLP classifier for content filtering and categorization"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.classifier = None
        self.tokenizer = None
        self.model = None
        self.categories = [
            "politics",
            "economy",
            "technology",
            "climate",
            "world",
            "business",
            "entertainment",
            "sports",
            "lifestyle",
            "gossip",
        ]
        self.relevant_categories = [
            "politics",
            "economy",
            "technology",
            "climate",
            "world",
            "business",
        ]
        self.threshold = 0.7

        if TRANSFORMERS_AVAILABLE:
            self._initialize_classifier()
        else:
            self.logger.warning(
                "Using basic text analysis - install transformers for better classification"
            )

    def _initialize_classifier(self):
        """Initialize the HuggingFace classifier"""
        try:
            # Use a lightweight model for zero-shot classification
            model_name = "facebook/bart-large-mnli"

            self.logger.info(f"Loading NLP classifier: {model_name}")
            self.classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=-1,  # Use CPU for now
            )
            self.logger.info("NLP classifier initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize NLP classifier: {e}")
            self.classifier = None

    async def classify_article(self, title: str, content: str) -> ClassificationResult:
        """Classify an article and determine if it's relevant"""
        try:
            # Combine title and content for classification
            text = f"{title} {content}".strip()

            if not text:
                return ClassificationResult(
                    label="unknown", confidence=0.0, is_relevant=False, reasoning="Empty content"
                )

            if self.classifier:
                return await self._classify_with_transformers(text)
            else:
                return await self._classify_with_basic_analysis(text)

        except Exception as e:
            self.logger.error(f"Error classifying article: {e}")
            return ClassificationResult(
                label="error",
                confidence=0.0,
                is_relevant=False,
                reasoning=f"Classification error: {str(e)}",
            )

    async def _classify_with_transformers(self, text: str) -> ClassificationResult:
        """Classify using HuggingFace transformers"""
        try:
            # Run classification in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.classifier, text, self.categories)

            # Get the best classification
            best_label = result["labels"][0]
            best_confidence = result["scores"][0]

            # Determine if relevant
            is_relevant = (
                best_label in self.relevant_categories and best_confidence >= self.threshold
            )

            reasoning = f"Classified as '{best_label}' with {best_confidence:.2f} confidence"
            if not is_relevant:
                if best_label not in self.relevant_categories:
                    reasoning += f" (category '{best_label}' not in relevant categories)"
                else:
                    reasoning += (
                        f" (confidence {best_confidence:.2f} below threshold {self.threshold})"
                    )

            return ClassificationResult(
                label=best_label,
                confidence=best_confidence,
                is_relevant=is_relevant,
                reasoning=reasoning,
            )

        except Exception as e:
            self.logger.error(f"Error in transformer classification: {e}")
            return await self._classify_with_basic_analysis(text)

    async def _classify_with_basic_analysis(self, text: str) -> ClassificationResult:
        """Fallback classification using basic text analysis"""
        try:
            text_lower = text.lower()

            # Define keyword patterns for each category
            category_keywords = {
                "politics": [
                    "election",
                    "government",
                    "policy",
                    "legislation",
                    "congress",
                    "senate",
                    "parliament",
                    "democracy",
                    "voting",
                    "president",
                    "prime minister",
                    "political",
                    "campaign",
                    "candidate",
                    "vote",
                    "ballot",
                ],
                "economy": [
                    "economy",
                    "economic",
                    "financial",
                    "market",
                    "business",
                    "trade",
                    "inflation",
                    "gdp",
                    "unemployment",
                    "recession",
                    "growth",
                    "fiscal",
                    "monetary",
                    "bank",
                    "investment",
                    "stock",
                    "currency",
                ],
                "technology": [
                    "tech",
                    "technology",
                    "innovation",
                    "ai",
                    "artificial intelligence",
                    "cybersecurity",
                    "digital",
                    "software",
                    "hardware",
                    "computer",
                    "internet",
                    "data",
                    "algorithm",
                    "machine learning",
                    "blockchain",
                ],
                "climate": [
                    "climate",
                    "environment",
                    "carbon",
                    "renewable",
                    "sustainability",
                    "green",
                    "emissions",
                    "global warming",
                    "climate change",
                    "pollution",
                    "energy",
                    "solar",
                    "wind",
                    "fossil fuel",
                    "carbon footprint",
                ],
                "world": [
                    "international",
                    "global",
                    "world",
                    "foreign",
                    "diplomacy",
                    "conflict",
                    "peace",
                    "treaty",
                    "summit",
                    "united nations",
                    "international",
                    "global",
                    "worldwide",
                    "overseas",
                    "international relations",
                ],
                "business": [
                    "business",
                    "corporate",
                    "company",
                    "industry",
                    "market",
                    "finance",
                    "investment",
                    "merger",
                    "acquisition",
                    "revenue",
                    "profit",
                    "earnings",
                ],
                "entertainment": [
                    "celebrity",
                    "movie",
                    "film",
                    "actor",
                    "actress",
                    "singer",
                    "musician",
                    "hollywood",
                    "oscar",
                    "grammy",
                    "emmy",
                    "entertainment",
                    "show",
                    "television",
                    "tv",
                    "series",
                    "drama",
                    "comedy",
                ],
                "sports": [
                    "sports",
                    "football",
                    "basketball",
                    "baseball",
                    "soccer",
                    "hockey",
                    "nfl",
                    "nba",
                    "mlb",
                    "nhl",
                    "olympics",
                    "world cup",
                    "championship",
                    "game",
                    "match",
                    "player",
                    "team",
                    "coach",
                ],
                "lifestyle": [
                    "fashion",
                    "beauty",
                    "makeup",
                    "lifestyle",
                    "trending",
                    "viral",
                    "social media",
                    "instagram",
                    "tiktok",
                    "influencer",
                    "style",
                    "design",
                    "art",
                    "culture",
                    "food",
                    "travel",
                ],
                "gossip": [
                    "gossip",
                    "rumor",
                    "scandal",
                    "divorce",
                    "marriage",
                    "dating",
                    "relationship",
                    "breakup",
                    "cheating",
                    "affair",
                    "drama",
                ],
            }

            # Calculate scores for each category
            category_scores = {}
            for category, keywords in category_keywords.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                category_scores[category] = score

            # Find the category with the highest score
            if not category_scores or max(category_scores.values()) == 0:
                return ClassificationResult(
                    label="unknown",
                    confidence=0.0,
                    is_relevant=False,
                    reasoning="No category keywords found",
                )

            best_category = max(category_scores, key=category_scores.get)
            best_score = category_scores[best_category]

            # Normalize confidence (basic heuristic)
            max_possible_score = len(category_keywords[best_category])
            confidence = min(best_score / max_possible_score, 1.0)

            # Determine if relevant
            is_relevant = best_category in self.relevant_categories and confidence >= 0.3

            reasoning = f"Basic analysis: '{best_category}' category with {best_score} keyword matches (confidence: {confidence:.2f})"
            if not is_relevant:
                if best_category not in self.relevant_categories:
                    reasoning += f" (category '{best_category}' not relevant)"
                else:
                    reasoning += f" (confidence {confidence:.2f} below threshold)"

            return ClassificationResult(
                label=best_category,
                confidence=confidence,
                is_relevant=is_relevant,
                reasoning=reasoning,
            )

        except Exception as e:
            self.logger.error(f"Error in basic classification: {e}")
            return ClassificationResult(
                label="error",
                confidence=0.0,
                is_relevant=False,
                reasoning=f"Basic analysis error: {str(e)}",
            )

    async def batch_classify_articles(
        self, articles: list[dict[str, Any]]
    ) -> list[ClassificationResult]:
        """Classify multiple articles in batch"""
        try:
            tasks = []
            for article in articles:
                title = article.get("title", "")
                content = article.get("content", "")
                task = asyncio.create_task(self.classify_article(title, content))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle any exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error classifying article {i}: {result}")
                    processed_results.append(
                        ClassificationResult(
                            label="error",
                            confidence=0.0,
                            is_relevant=False,
                            reasoning=f"Batch processing error: {str(result)}",
                        )
                    )
                else:
                    processed_results.append(result)

            return processed_results

        except Exception as e:
            self.logger.error(f"Error in batch classification: {e}")
            return [
                ClassificationResult(
                    label="error",
                    confidence=0.0,
                    is_relevant=False,
                    reasoning=f"Batch processing error: {str(e)}",
                )
                for _ in articles
            ]

    async def get_classification_stats(self) -> dict[str, Any]:
        """Get statistics about classification performance"""
        try:
            return {
                "classifier_available": self.classifier is not None,
                "transformers_available": TRANSFORMERS_AVAILABLE,
                "categories": self.categories,
                "relevant_categories": self.relevant_categories,
                "threshold": self.threshold,
                "model_name": "facebook/bart-large-mnli"
                if self.classifier
                else "basic_text_analysis",
            }
        except Exception as e:
            self.logger.error(f"Error getting classification stats: {e}")
            return {"error": str(e)}

    async def update_classification_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Update classification configuration"""
        try:
            if "categories" in config:
                self.categories = config["categories"]

            if "relevant_categories" in config:
                self.relevant_categories = config["relevant_categories"]

            if "threshold" in config:
                self.threshold = float(config["threshold"])

            self.logger.info("Classification configuration updated")
            return {
                "status": "updated",
                "message": "Classification configuration updated successfully",
            }
        except Exception as e:
            self.logger.error(f"Error updating classification config: {e}")
            return {"error": str(e)}


# Global classifier instance
_classifier_instance = None


async def get_classifier() -> NLPClassifierService:
    """Get or create global classifier instance"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = NLPClassifierService()
    return _classifier_instance
