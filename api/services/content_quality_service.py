"""
Content Quality Service — clickbait/sensationalism detection and 4-tier quality classification.
Prioritizes factual, substantive content for briefings and storylines.
See docs/CONTENT_QUALITY_STANDARDS.md.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Default thresholds (override via config)
QUALITY_CONFIG = {
    "min_tier_for_storylines": 3,
    "min_tier_for_briefings": 2,
    "min_tier_for_events": 2,
    "auto_reject_clickbait_threshold": 0.8,
    "require_named_sources_for_tier_1": True,
    "min_word_count_for_analysis": 200,
    "emotion_word_density_threshold": 0.3,
}


class ContentQualityService:
    """Analyze article quality: clickbait, fact density, source quality, emotional manipulation."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = {**QUALITY_CONFIG, **(config or {})}
        self.clickbait_patterns = {
            "headline_triggers": [
                r"BREAKING:",
                r"SHOCKING:",
                r"EXCLUSIVE:",
                r"You Won't Believe",
                r"This One.*Thing",
                r"Doctors Hate",
                r"With This.*Trick",
                r"One Weird Trick",
                r"Number \d+ Will",
                r"Changed Everything",
                r"Game Changer",
                r"Going Viral",
                r"Trending Now",
            ],
            "emotional_words": [
                "slams",
                "blasts",
                "destroys",
                "obliterates",
                "furious",
                "outrage",
                "panic",
                "chaos",
                "devastating",
                "shocking",
                "explosive",
                "bombshell",
                "nightmare",
                "horror",
            ],
            "vague_patterns": [
                r"What.*Happened Next",
                r"The.*Reason Why",
                r"Everyone Is.*Talking About",
                r"They Don't Want You to Know",
                r"This One (Thing|Trick|Secret)",
            ],
        }

    def analyze_content_quality(self, article: dict[str, Any]) -> dict[str, Any]:
        """
        Comprehensive quality analysis including clickbait detection.
        article: dict with title, content (or summary), source_domain/source, url (optional).
        Returns: quality_score (0-1), quality_tier (1-4), scores dict, flags list, recommendation.
        """
        title = (article.get("title") or "").strip()
        content = (article.get("content") or article.get("summary") or "").strip()
        source = (article.get("source_domain") or article.get("source") or "").strip()
        (article.get("url") or "").strip()

        scores = {
            "clickbait_score": self._detect_clickbait(title, content),
            "fact_density": self._calculate_fact_density(content),
            "source_quality": self._assess_source_quality(source, content),
            "emotional_manipulation": self._detect_emotional_manipulation(title, content),
            "information_depth": self._measure_information_depth(content),
            "claim_specificity": self._evaluate_claim_specificity(content),
        }

        # Weighted composite (0-1); lower clickbait and emotion = better
        quality_score = (
            scores["fact_density"] * 0.30
            + scores["source_quality"] * 0.25
            + scores["information_depth"] * 0.20
            + scores["claim_specificity"] * 0.15
            + (1.0 - scores["clickbait_score"]) * 0.05
            + (1.0 - scores["emotional_manipulation"]) * 0.05
        )
        quality_score = max(0.0, min(1.0, quality_score))

        tier = self._assign_quality_tier(quality_score, scores)
        flags = self._generate_quality_flags(scores)
        recommendation = self._generate_recommendation(tier, scores)

        return {
            "quality_score": round(quality_score, 4),
            "quality_tier": tier,
            "scores": {k: round(v, 4) for k, v in scores.items()},
            "flags": flags,
            "recommendation": recommendation,
        }

    def _detect_clickbait(self, title: str, content: str) -> float:
        """Return 0-1 clickbait score (higher = more clickbait)."""
        try:
            from collectors.rss_collector import is_clickbait_title
        except Exception:

            def is_clickbait_title(t):
                return False

        score = 0.0
        content_lower = (content or "").lower()

        if is_clickbait_title(title):
            score += 0.4

        for pattern in self.clickbait_patterns["headline_triggers"]:
            if re.search(pattern, title or "", re.IGNORECASE):
                score += 0.15

        for pattern in self.clickbait_patterns["vague_patterns"]:
            if re.search(pattern, title or "", re.IGNORECASE):
                score += 0.12

        words = (content or "").split()
        if words:
            emotional_count = sum(
                1 for w in self.clickbait_patterns["emotional_words"] if w in content_lower
            )
            score += min(0.25, (emotional_count / max(len(words) / 100, 1)) * 0.5)

        word_count = len((content or "").split())
        if word_count < self.config.get("min_word_count_for_analysis", 200):
            score += 0.2

        return min(score, 1.0)

    def _calculate_fact_density(self, content: str) -> float:
        """Heuristic fact density: named sources, numbers, dates, quotes."""
        if not content:
            return 0.0
        content.lower()
        words = content.split()
        if not words:
            return 0.0

        fact_signals = 0
        # Named attribution
        for pattern in [
            r"according to [A-Za-z][^.,]+",
            r"[A-Za-z][^.]+\s+said\s",
            r"[A-Za-z][^.]+\s+told\s",
            r"per\s+[A-Za-z]",
            r"citing\s+[A-Za-z]",
        ]:
            fact_signals += len(re.findall(pattern, content, re.IGNORECASE))

        # Numbers and dates
        fact_signals += len(re.findall(r"\d{1,4}[-/]\d{1,2}[-/]\d{2,4}", content))
        fact_signals += len(re.findall(r"\b\d+(?:\.\d+)?%", content))
        fact_signals += len(re.findall(r"\b\d{2,}\b", content))

        # Quotes
        fact_signals += content.count('"') // 2 + content.count("'") // 2

        # Normalize by length (cap so long fluff doesn't score too low)
        density = min(1.0, fact_signals / max(len(words) / 80, 1) * 0.4)
        return round(density, 4)

    def _assess_source_quality(self, source: str, content: str) -> float:
        """Source reliability 0-1: known outlets + named/institutional sources in text."""
        score = 0.3  # base for unknown
        source_lower = (source or "").lower()

        tier1_sources = [
            "reuters",
            "ap news",
            "associated press",
            "bbc",
            "bloomberg",
            "financial times",
            "wall street journal",
            "wsj",
            "economist",
            "new york times",
            "washington post",
            "npr",
            "ap",
            "afp",
        ]
        tier2_sources = [
            "guardian",
            "cnn",
            "fox news",
            "nbc",
            "abc",
            "cbs",
            "pbs",
            "marketwatch",
            "cnbc",
            "forbes",
            "fortune",
            "politico",
            "axios",
        ]
        if any(s in source_lower for s in tier1_sources):
            score = 0.9
        elif any(s in source_lower for s in tier2_sources):
            score = 0.75

        text = (content or "").lower()
        # Named/institutional in body boosts slightly
        if re.search(r"according to|said (?:a|the)|spokesperson|official", text):
            score = min(1.0, score + 0.1)
        if re.search(r"department of|ministry of|university of|institute|bureau of", text):
            score = min(1.0, score + 0.05)

        return min(1.0, score)

    def _detect_emotional_manipulation(self, title: str, content: str) -> float:
        """0-1: density of emotional/sensational language."""
        text = ((title or "") + " " + (content or "")).lower()
        words = text.split()
        if not words:
            return 0.0
        count = sum(1 for w in self.clickbait_patterns["emotional_words"] if w in text)
        return min(1.0, count / max(len(words) / 150, 1) * 0.5)

    def _measure_information_depth(self, content: str) -> float:
        """0-1: length and structure (paragraphs, completeness)."""
        if not content:
            return 0.0
        words = content.split()
        score = min(1.0, len(words) / 600) * 0.5  # length cap at ~600 words
        paragraphs = len([p for p in content.split("\n") if p.strip()])
        score += min(0.3, paragraphs * 0.02)
        # Who/what/when/where
        text_lower = content.lower()
        if re.search(r"\b(who|what|when|where|why|how)\b", text_lower):
            score += 0.2
        return min(1.0, score)

    def _evaluate_claim_specificity(self, content: str) -> float:
        """0-1: numbers, names, quotes."""
        if not content:
            return 0.0
        words = content.split()
        if not words:
            return 0.0
        specificity = 0.0
        if re.search(r"\d+(?:\.\d+)?%|\$\d+|\d+ (?:million|billion|thousand)", content):
            specificity += 0.35
        if re.findall(r"[A-Z][a-z]+ [A-Z][a-z]+", content):  # rough "Name Name"
            specificity += 0.35
        if '"' in content or "'" in content:
            specificity += 0.3
        return min(1.0, specificity)

    def _assign_quality_tier(self, quality_score: float, scores: dict[str, float]) -> int:
        """Map 0-1 score to tier 1-4. Tier 4 = low-value/clickbait."""
        if scores.get("clickbait_score", 0) >= self.config.get(
            "auto_reject_clickbait_threshold", 0.8
        ):
            return 4
        if quality_score >= 0.8:
            return 1
        if quality_score >= 0.6:
            return 2
        if quality_score >= 0.4:
            return 3
        return 4

    def _generate_quality_flags(self, scores: dict[str, float]) -> list[str]:
        flags = []
        if scores.get("clickbait_score", 0) >= 0.5:
            flags.append("clickbait_risk")
        if scores.get("emotional_manipulation", 0) >= self.config.get(
            "emotion_word_density_threshold", 0.3
        ):
            flags.append("high_emotion")
        if scores.get("fact_density", 0) < 0.2:
            flags.append("low_fact_density")
        if scores.get("source_quality", 0) < 0.5:
            flags.append("low_source_quality")
        if scores.get("information_depth", 0) < 0.2:
            flags.append("shallow")
        return flags

    def _generate_recommendation(self, tier: int, scores: dict[str, float]) -> str:
        if tier == 1:
            return "intelligence_grade"
        if tier == 2:
            return "standard_reporting"
        if tier == 3:
            return "aggregated_commentary"
        return "low_value_demote"


def get_content_quality_service(config: dict[str, Any] | None = None) -> ContentQualityService:
    """Return a new ContentQualityService instance."""
    return ContentQualityService(config=config)


def update_article_quality_in_db(
    article_id: int,
    schema: str,
    result: dict[str, Any],
) -> bool:
    """
    Persist quality result to articles.quality_tier, quality_scores, etc.
    Call after analyze_content_quality(). Returns True on success.
    """
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return False
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET quality_tier = %s, quality_scores = %s,
                    clickbait_probability = %s, fact_density = %s,
                    source_reliability = %s, quality_flags = %s
                WHERE id = %s
                """,
                (
                    result.get("quality_tier", 3),
                    json.dumps(result.get("scores") or {}),
                    (result.get("scores") or {}).get("clickbait_score"),
                    (result.get("scores") or {}).get("fact_density"),
                    (result.get("scores") or {}).get("source_quality"),
                    (result.get("flags") or []),
                    article_id,
                ),
            )
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("update_article_quality_in_db: %s", e)
        return False
