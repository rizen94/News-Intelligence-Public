"""
Advanced Topic Extraction Service
Creates dynamic word clouds and big picture topic analysis
"""

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TopicInsight:
    """Represents a topic insight with metadata"""

    name: str
    frequency: int
    relevance_score: float
    trend_direction: str  # 'rising', 'falling', 'stable'
    articles: list[int]
    keywords: list[str]
    sentiment: str
    category: str
    created_at: datetime


class AdvancedTopicExtractor:
    """Advanced topic extraction using multiple techniques"""

    def __init__(self, db_connection_func, schema: str = "politics"):
        self.get_db_connection = db_connection_func
        self.schema = schema

        # Topic categories for better organization
        self.topic_categories = {
            "politics": [
                "election",
                "president",
                "congress",
                "vote",
                "campaign",
                "policy",
                "government",
            ],
            "economy": [
                "market",
                "economy",
                "inflation",
                "recession",
                "gdp",
                "unemployment",
                "financial",
            ],
            "technology": ["ai", "tech", "software", "digital", "innovation", "cyber", "data"],
            "environment": [
                "climate",
                "environment",
                "carbon",
                "green",
                "sustainability",
                "renewable",
            ],
            "health": [
                "health",
                "medical",
                "covid",
                "vaccine",
                "pandemic",
                "healthcare",
                "disease",
            ],
            "international": ["war", "conflict", "military", "defense", "security", "diplomacy"],
            "social": ["social", "community", "culture", "society", "education", "justice"],
            "business": ["business", "corporate", "industry", "trade", "commerce", "startup"],
        }

        # Comprehensive stop words to filter out common words
        self.stop_words = {
            # Articles and pronouns
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
            "being",
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
            "must",
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
            "me",
            "him",
            "her",
            "us",
            "them",
            # Common verbs (base forms)
            "said",
            "says",
            "say",
            "get",
            "got",
            "go",
            "went",
            "come",
            "came",
            "see",
            "saw",
            "know",
            "knew",
            "think",
            "thought",
            "take",
            "took",
            "make",
            "made",
            "give",
            "gave",
            "use",
            "used",
            "find",
            "found",
            "tell",
            "told",
            "ask",
            "asked",
            "work",
            "worked",
            "try",
            "tried",
            "call",
            "called",
            "need",
            "needed",
            "want",
            "wanted",
            "seem",
            "seemed",
            "feel",
            "felt",
            "become",
            "became",
            "leave",
            "left",
            "put",
            "set",
            "run",
            "ran",
            "move",
            "moved",
            "live",
            "lived",
            "believe",
            "believed",
            "hold",
            "held",
            # More action verbs
            "complete",
            "finish",
            "finished",
            "start",
            "started",
            "begin",
            "began",
            "end",
            "ended",
            "reach",
            "reached",
            "reach",
            "chase",
            "chased",
            "catch",
            "caught",
            "win",
            "won",
            "lose",
            "lost",
            "beat",
            "beaten",
            "defeat",
            "defeated",
            "play",
            "played",
            "score",
            "scored",
            "scoring",
            "break",
            "broke",
            "broken",
            "hit",
            "hitting",
            "strike",
            "struck",
            "throw",
            "threw",
            "thrown",
            "run",
            "runs",
            "running",
            "walk",
            "walked",
            "walking",
            "jump",
            "jumped",
            "jumping",
            # Present participles (verb forms ending in -ing)
            "becoming",
            "getting",
            "going",
            "coming",
            "seeing",
            "knowing",
            "thinking",
            "taking",
            "making",
            "giving",
            "using",
            "finding",
            "telling",
            "asking",
            "working",
            "trying",
            "calling",
            "needing",
            "wanting",
            "seeming",
            "feeling",
            "becoming",
            "leaving",
            "putting",
            "setting",
            "running",
            "moving",
            "living",
            "believing",
            "holding",
            "finishing",
            "starting",
            "beginning",
            "ending",
            "reaching",
            "chasing",
            "catching",
            "winning",
            "losing",
            "beating",
            "defeating",
            "playing",
            "scoring",
            "breaking",
            "hitting",
            "striking",
            "throwing",
            "walking",
            "jumping",
            # Common news/reporting verbs
            "report",
            "reported",
            "reporting",
            "announce",
            "announced",
            "announcing",
            "confirm",
            "confirmed",
            "reveal",
            "revealed",
            "revealing",
            "claim",
            "claimed",
            "claiming",
            "state",
            "stated",
            "stating",
            "declare",
            "declared",
            "declaring",
            "note",
            "noted",
            "noting",
            "add",
            "added",
            "adding",
            "explain",
            "explained",
            "explaining",
            "describe",
            "described",
            "describing",
            "show",
            "showed",
            "showing",
            "indicate",
            "indicated",
            "indicating",
            "suggest",
            "suggested",
            "suggesting",
            # Verbs that don't make good topics
            "happen",
            "happened",
            "happening",
            "occur",
            "occurred",
            "occurring",
            "continue",
            "continued",
            "continuing",
            "begin",
            "began",
            "beginning",
            "start",
            "started",
            "starting",
            # Common adjectives/adverbs
            "new",
            "old",
            "good",
            "bad",
            "long",
            "short",
            "big",
            "small",
            "high",
            "low",
            "early",
            "late",
            "right",
            "wrong",
            "first",
            "last",
            "next",
            "previous",
            "only",
            "also",
            "very",
            "much",
            "many",
            "more",
            "most",
            "some",
            "any",
            "all",
            "each",
            "every",
            "both",
            "half",
            "full",
            "empty",
            # Action/state adjectives that aren't meaningful topics
            "complete",
            "finished",
            "unfinished",
            "started",
            "beginning",
            "ending",
            "ongoing",
            "active",
            "inactive",
            "open",
            "closed",
            "public",
            "private",
            "free",
            "available",
            "unavailable",
            # Sports/action descriptors
            "unbeaten",
            "defeated",
            "winning",
            "losing",
            "leading",
            "trailing",
            "ahead",
            "behind",
            "final",
            "semi",
            "quarter",
            "round",
            "match",
            "game",
            "match",
            "matchup",
            # Common nouns (generic)
            "time",
            "year",
            "people",
            "way",
            "day",
            "man",
            "thing",
            "woman",
            "life",
            "child",
            "world",
            "school",
            "state",
            "family",
            "student",
            "group",
            "country",
            "problem",
            "hand",
            "part",
            "place",
            "case",
            "week",
            "company",
            "system",
            "program",
            "question",
            "work",
            "government",
            "number",
            "night",
            "point",
            "home",
            "water",
            "room",
            "mother",
            "area",
            "money",
            "story",
            "fact",
            "month",
            "lot",
            "right",
            "study",
            "book",
            "eye",
            "job",
            "word",
            "business",
            "issue",
            "side",
            "kind",
            "head",
            "house",
            "service",
            "friend",
            "father",
            "power",
            "hour",
            "game",
            "line",
            "end",
            "member",
            "law",
            "car",
            "city",
            "community",
            "name",
            "president",
            "team",
            "minute",
            "idea",
            "kid",
            "body",
            "information",
            "back",
            "parent",
            "face",
            "others",
            "level",
            "office",
            "door",
            "health",
            "person",
            "art",
            "war",
            "history",
            "party",
            "result",
            "change",
            "morning",
            "reason",
            "research",
            "girl",
            "guy",
            "moment",
            "air",
            "teacher",
            "force",
            "education",
            # Sports/game specific nouns that are too generic
            "cup",
            "championship",
            "tournament",
            "league",
            "series",
            "season",
            "playoff",
            "final",
            "semi",
            "quarter",
            "round",
            "match",
            "matchup",
            "game",
            "play",
            "player",
            "players",
            "fan",
            "fans",
            "coach",
            "team",
            "teams",
            "score",
            "scores",
            "point",
            "points",
            # News/article specific words
            "article",
            "articles",
            "news",
            "report",
            "reports",
            "story",
            "stories",
            "update",
            "updates",
            "latest",
            "breaking",
            "according",
            "source",
            "sources",
            "official",
            "officials",
            # Common connectors and filler words
            "one",
            "two",
            "three",
            "four",
            "five",
            "first",
            "second",
            "third",
            "when",
            "where",
            "why",
            "how",
            "what",
            "who",
            "which",
            "there",
            "here",
            "just",
            "now",
            "then",
            "than",
            "well",
            # Additional common words
            "way",
            "day",
            "may",
            "way",
            "up",
            "out",
            "so",
            "if",
            "about",
            "into",
            "through",
            "during",
            "including",
            "against",
            "among",
            "throughout",
            "despite",
            "towards",
            "upon",
            "concerning",
            "like",
            "such",
            "same",
            "other",
            "another",
            "own",
            "its",
            "our",
            "your",
            "their",
            "his",
            "her",
            "my",
            "yourself",
            "itself",
            "themselves",
            "ourselves",
            "himself",
            "herself",
            # Common phrases parts that aren't meaningful alone
            "from",
            "during",
            "before",
            "after",
            "above",
            "below",
            "under",
            "over",
            "across",
            "around",
            "inside",
            "outside",
            "within",
            "without",
            "through",
            "between",
            "among",
            "toward",
            "towards",
        }

        # Additional filter: common meaningless single words (less than 4 chars, very common)
        self.uncommon_short_words = {
            "fly",
            "run",
            "set",
            "try",
            "win",
            "cut",
            "hit",
            "put",
            "let",
            "yet",
            "nor",
            "ago",
            "per",
            "via",
            "etc",
            "etc.",
            "vs",
            "vs.",
            "ie",
            "ie.",
            "eg",
            "eg.",
            "mr",
            "mrs",
            "dr",
            "pm",
            "am",
            "uk",
            "us",
            "tv",
            "ai",
            "id",
            "ad",
            "bc",
            "ce",
            "qa",
            "hr",
            "it",
            "it's",
            "is'nt",
            "don't",
            "won't",
            "can't",
            "hasn't",
            "haven't",
            "didn't",
            "wouldn't",
            "couldn't",
            "shouldn't",
            # Common action words that are too generic
            "cup",
            "final",
            "semi",
            "match",
            "game",
            "play",
            "score",
            "point",
            "round",
            "team",
        }

        # Words that indicate a phrase is likely not a meaningful topic (too verb-heavy)
        self.verb_indicators = {
            "becoming",
            "reaching",
            "chasing",
            "completing",
            "finishing",
            "starting",
            "ending",
            "winning",
            "losing",
            "playing",
            "scoring",
            "beating",
            "defeating",
            "running",
            "breaking",
            "hitting",
            "striking",
            "throwing",
            "catching",
            "jumping",
            "walking",
            "reporting",
            "announcing",
            "confirming",
            "revealing",
            "claiming",
            "stating",
            "declaring",
            "explaining",
            "describing",
            "showing",
            "indicating",
            "suggesting",
            "happening",
            "occurring",
            "continuing",
            "beginning",
            "starting",
            "finishing",
        }

        # Well-known compound phrases that should be allowed even if they contain stop words
        self.allowed_compound_phrases = {
            "world cup",
            "world series",
            "super bowl",
            "olympic games",
            "olympics",
            "united states",
            "united kingdom",
            "new york",
            "los angeles",
            "san francisco",
            "prime minister",
            "president",
            "white house",
            "supreme court",
            "house representatives",
        }

        # Web-related terms that should never be topics (unless tech-focused)
        self.web_artifacts = {
            "href",
            "http",
            "https",
            "www",
            "url",
            "html",
            "htm",
            "css",
            "js",
            "javascript",
            "xml",
            "json",
            "api",
            "www",
            "com",
            "org",
            "net",
            "edu",
            "gov",
            "link",
            "links",
            "anchor",
            "tag",
            "tags",
            "attribute",
            "attributes",
            "element",
            "elements",
            "domain",
            "domains",
            "website",
            "websites",
            "webpage",
            "webpages",
            "page",
            "pages",
            "click",
            "view",
            "read",
            "more",
            "here",
            "there",
            "source",
            "sources",
        }

    def _clean_text_for_topic_extraction(self, text: str) -> str:
        """Clean text by removing HTML tags, URLs, and web artifacts before topic extraction"""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)

        # Remove URLs (http://, https://, www.)
        text = re.sub(r"https?://[^\s]+", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"www\.[^\s]+", " ", text, flags=re.IGNORECASE)
        text = re.sub(
            r"[a-zA-Z0-9-]+\.(com|org|net|edu|gov|io|co|uk|us|de|fr|ca|au|jp|cn)[^\s]*",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        # Remove email addresses
        text = re.sub(r"\S+@\S+", " ", text)

        # Remove HTML entities
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        text = re.sub(r"&#\d+;", " ", text)

        # Remove HTML/XML attributes and tags (additional cleanup)
        text = re.sub(r'[a-z]+="[^"]*"', " ", text, flags=re.IGNORECASE)  # Remove attributes
        text = re.sub(r"/[a-z]+>", " ", text, flags=re.IGNORECASE)  # Remove closing tags

        # Remove web-related artifacts that might appear as standalone words
        # Split into words and filter
        words = text.split()
        cleaned_words = []
        for word in words:
            word_lower = word.lower().strip(".,;:!?()[]{}\"'")
            # Skip web artifacts
            if word_lower in self.web_artifacts:
                continue
            # Skip words that start with web prefixes (like "http", "www", etc.)
            if any(word_lower.startswith(artifact) for artifact in ["http", "www", "href", "url"]):
                continue
            # Skip if word contains typical URL/HTML patterns
            if re.match(r"^(href|http|https|www|\.com|\.org|\.net)", word_lower):
                continue
            cleaned_words.append(word)

        text = " ".join(cleaned_words)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def extract_topics_from_articles(self, time_period_hours: int = 24) -> list[TopicInsight]:
        """Extract topics from recent articles using multiple techniques"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return []

            try:
                with conn.cursor() as cur:
                    # Get recent articles
                    cutoff_time = datetime.now() - timedelta(hours=time_period_hours)

                    cur.execute(
                        f"""
                        SELECT id, title, content, summary, published_at, sentiment_score, source_domain
                        FROM {self.schema}.articles
                        WHERE created_at >= %s
                        AND content IS NOT NULL
                        AND LENGTH(content) > 100
                        ORDER BY published_at DESC
                    """,
                        (cutoff_time,),
                    )

                    articles = cur.fetchall()

                    if not articles:
                        logger.info("No recent articles found for topic extraction")
                        return []

                    # Extract topics using multiple techniques
                    topics = self._extract_topics_multi_technique(articles)

                    # Analyze trends
                    topics = self._analyze_topic_trends(topics)

                    # Categorize topics
                    topics = self._categorize_topics(topics)

                    return topics

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return []

    def _extract_topics_multi_technique(self, articles: list[tuple]) -> list[TopicInsight]:
        """Extract topics using multiple techniques - prioritize phrases over single words"""
        topics = []

        # Technique 1: Phrase extraction (HIGHEST PRIORITY - most meaningful)
        phrase_topics = self._extract_phrase_topics(articles)
        topics.extend(phrase_topics)

        # Technique 2: Entity-based topics (SECOND PRIORITY - specific entities)
        entity_topics = self._extract_entity_topics(articles)
        topics.extend(entity_topics)

        # Technique 3: Keyword frequency analysis (LOWEST PRIORITY - single words)
        # Always extract keywords to ensure we get a large pool of topics
        # Removed the condition that limited extraction - we want more topics
        keyword_topics = self._extract_keyword_topics(articles)
        topics.extend(keyword_topics)

        # Merge similar topics (phrases take precedence)
        topics = self._merge_similar_topics(topics)

        # Sort by relevance score and frequency (phrases should rank higher)
        topics.sort(key=lambda t: (t.relevance_score, t.frequency), reverse=True)

        # Increased limit to 200 topics for larger pool (was 50)
        # This allows more granular topics like "Donald Trump", "2026 elections", etc.
        return topics[:200]

    def _extract_keyword_topics(self, articles: list[tuple]) -> list[TopicInsight]:
        """Extract topics based on keyword frequency - prioritize meaningful words"""
        word_freq = Counter()
        article_keywords = defaultdict(list)

        for (
            article_id,
            title,
            content,
            summary,
            published_at,
            sentiment_score,
            source_domain,
        ) in articles:
            # Combine title and content for analysis
            raw_text = f"{title} {summary or ''} {content or ''}"

            # Clean text to remove HTML, URLs, and web artifacts
            cleaned_text = self._clean_text_for_topic_extraction(raw_text).lower()

            # Extract words (minimum 4 characters for meaningful topics, alphanumeric)
            words = re.findall(r"\b[a-zA-Z]{4,}\b", cleaned_text)

            # Filter stop words and uncommon short words
            filtered_words = [
                word
                for word in words
                if word not in self.stop_words
                and word not in self.uncommon_short_words
                and len(word) >= 4  # Ensure minimum length
            ]

            for word in filtered_words:
                word_freq[word] += 1
                article_keywords[word].append(article_id)

        # Create topics from frequent keywords with LOWER threshold for more granular topics
        topics = []
        for word, freq in word_freq.most_common(100):  # Top 100 keywords (increased from 30)
            # LOWER frequency threshold - allow topics appearing in just 1 article
            # This captures more specific, granular topics like "Trump", "elections", etc.
            if freq >= 1 and len(word) >= 4:
                # Filter out words that are too generic or common
                if not self._is_too_generic(word):
                    topics.append(
                        TopicInsight(
                            name=word.title(),
                            frequency=freq,
                            relevance_score=min(freq / 15.0, 1.0),  # Adjusted normalization
                            trend_direction="stable",
                            articles=article_keywords[word],
                            keywords=[word],
                            sentiment="neutral",
                            category="general",
                            created_at=datetime.now(),
                        )
                    )

        return topics

    def _is_too_generic(self, word: str) -> bool:
        """Check if a word is too generic to be a meaningful topic"""
        word_lower = word.lower()

        # Check against web artifacts list first
        if word_lower in self.web_artifacts:
            return True

        generic_patterns = [
            r"^(page|link|site|web|url|http|www|html|pdf|htm|css|js|javascript|xml|json)$",
            r"^(click|view|read|show|see|page|article|news|story|report|media)$",
            r"^(image|photo|picture|video|audio|file|document)$",
            r"^(date|time|year|month|day|hour|minute|second)$",
            r"^(today|yesterday|tomorrow|week|month|year)$",
            r"^(here|there|where|when|what|how|why|who)$",
            r"^(said|says|according|report|reported|news|media|story)$",
            r"^(href|https|http|www|url|anchor|tag|attribute|element)$",
            r"^(domain|website|webpage|source|sources|com|org|net)$",
        ]
        for pattern in generic_patterns:
            if re.match(pattern, word_lower):
                return True

        # Check if word starts with web-related prefixes
        if any(word_lower.startswith(prefix) for prefix in ["http", "www", "href", "url", "www"]):
            return True

        return False

    def _extract_phrase_topics(self, articles: list[tuple]) -> list[TopicInsight]:
        """Extract topics based on common meaningful phrases (2-4 words)"""
        phrase_freq = Counter()
        article_phrases = defaultdict(list)

        for (
            article_id,
            title,
            content,
            summary,
            published_at,
            sentiment_score,
            source_domain,
        ) in articles:
            # Use title and summary primarily (they contain the most relevant phrases)
            # Long-form articles — use first 5000 chars for topic extraction
            content_preview = (content or "")[:5000] if content else ""
            raw_text = f"{title} {summary or ''} {content_preview}"

            # Clean text to remove HTML, URLs, and web artifacts
            text = self._clean_text_for_topic_extraction(raw_text).lower()

            # Extract words (minimum 3 characters for phrases)
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text)

            # Filter stop words
            filtered_words = [
                word
                for word in words
                if word not in self.stop_words and word not in self.uncommon_short_words
            ]

            # Extract 2-word phrases (highest priority)
            for i in range(len(filtered_words) - 1):
                word1, word2 = filtered_words[i], filtered_words[i + 1]
                # Ensure both words are meaningful (4+ chars or in category keywords)
                if (len(word1) >= 4 or word1 in self._get_category_all_keywords()) and (
                    len(word2) >= 4 or word2 in self._get_category_all_keywords()
                ):
                    # Skip if both words are verbs (not a good topic)
                    if word1 in self.verb_indicators and word2 in self.verb_indicators:
                        continue
                    phrase = f"{word1} {word2}"
                    if len(phrase) > 8:  # Minimum meaningful phrase length
                        phrase_freq[phrase] += 1
                        article_phrases[phrase].append(article_id)

            # Extract 3-word phrases (high value)
            for i in range(len(filtered_words) - 2):
                word1, word2, word3 = (
                    filtered_words[i],
                    filtered_words[i + 1],
                    filtered_words[i + 2],
                )
                # At least 2 of 3 words should be meaningful (4+ chars)
                meaningful_count = sum(
                    1
                    for w in [word1, word2, word3]
                    if len(w) >= 4 or w in self._get_category_all_keywords()
                )
                if meaningful_count >= 2:
                    # Skip if too many verbs (not a good topic phrase)
                    verb_count = sum(1 for w in [word1, word2, word3] if w in self.verb_indicators)
                    if verb_count >= 2:  # If 2+ verbs, skip it
                        continue
                    phrase = f"{word1} {word2} {word3}"
                    if len(phrase) > 12 and not any(
                        word in self.stop_words for word in [word1, word2, word3]
                    ):
                        phrase_freq[phrase] += 1
                        article_phrases[phrase].append(article_id)

            # Extract 4-word phrases (very specific, high value)
            for i in range(len(filtered_words) - 3):
                word1, word2, word3, word4 = filtered_words[i : i + 4]
                # At least 3 of 4 words should be meaningful
                meaningful_count = sum(
                    1
                    for w in [word1, word2, word3, word4]
                    if len(w) >= 4 or w in self._get_category_all_keywords()
                )
                if meaningful_count >= 3:
                    # Skip if too many verbs (not a good topic phrase)
                    verb_count = sum(
                        1 for w in [word1, word2, word3, word4] if w in self.verb_indicators
                    )
                    if verb_count >= 2:  # If 2+ verbs in a 4-word phrase, likely not a good topic
                        continue
                    phrase = f"{word1} {word2} {word3} {word4}"
                    if len(phrase) > 18 and not any(
                        word in self.stop_words for word in [word1, word2, word3, word4]
                    ):
                        phrase_freq[phrase] += 1
                        article_phrases[phrase].append(article_id)

        # Create topics from frequent phrases with LOWER threshold for more granular topics
        topics = []
        for phrase, freq in phrase_freq.most_common(150):  # Top 150 phrases (increased from 50)
            # LOWER threshold - allow topics appearing in just 1 article
            # This captures specific topics like "Donald Trump", "2026 elections", etc.
            if freq >= 1:
                # Filter out generic phrases
                if not self._is_too_generic_phrase(phrase):
                    topics.append(
                        TopicInsight(
                            name=phrase.title(),
                            frequency=freq,
                            relevance_score=min(freq / 4.0, 1.0),  # Phrases get higher relevance
                            trend_direction="stable",
                            articles=list(set(article_phrases[phrase])),  # Remove duplicates
                            keywords=phrase.split(),
                            sentiment="neutral",
                            category="general",
                            created_at=datetime.now(),
                        )
                    )

        return topics

    def _get_category_all_keywords(self) -> set:
        """Get all category keywords as a set for fast lookup"""
        all_keywords = set()
        for keywords in self.topic_categories.values():
            all_keywords.update(keywords)
        return all_keywords

    def _is_too_generic_phrase(self, phrase: str) -> bool:
        """Check if a phrase is too generic to be a meaningful topic"""
        words = phrase.lower().split()
        if len(words) < 2:
            return True

        phrase_lower = phrase.lower()

        # Allow well-known compound phrases even if they contain stop words
        if phrase_lower in self.allowed_compound_phrases:
            return False

        # Check for common generic patterns
        generic_patterns = [
            r"^(click|view|read|show|see)\s+(here|more|link)",
            r"^(read|see|view)\s+(full|entire|complete)\s+(article|story|report)",
            r"^(more|read|continue)\s+(on|at|here)",
            r"^(page|link|site|web)\s+\d+",
            r"^(this|that|these|those)\s+(is|are|was|were)",
            r"^(date|time)\s+(of|for)",
        ]

        for pattern in generic_patterns:
            if re.match(pattern, phrase_lower):
                return True

        # Filter phrases where too many words are generic stop words
        generic_word_count = sum(
            1 for word in words if word in self.stop_words or word in self.uncommon_short_words
        )
        if generic_word_count > len(words) / 2:
            return True

        # Filter verb-heavy phrases (phrases with too many action verbs)
        verb_count = sum(1 for word in words if word in self.verb_indicators)
        # If more than half the words are verbs, it's probably not a good topic
        if verb_count > len(words) / 2:
            return True

        # Filter phrases that start or end with verbs (usually not good topics)
        if len(words) >= 2:
            first_word = words[0]
            last_word = words[-1]
            if first_word in self.verb_indicators or last_word in self.verb_indicators:
                # Allow if it's a clear noun phrase (like "Running Back" in sports)
                # But reject if it's clearly verb-heavy
                if verb_count >= len(words) / 2:
                    return True

        # Reject phrases that are just verb sequences (e.g., "Reach Chase Complete")
        if len(words) >= 3:
            # If all words are verbs or verb-like, reject
            all_verbs = all(
                word in self.verb_indicators or word in self.stop_words for word in words
            )
            if all_verbs:
                return True

        return False

    def _extract_entity_topics(self, articles: list[tuple]) -> list[TopicInsight]:
        """Extract topics based on named entities - people, places, organizations"""
        entity_freq = Counter()
        article_entities = defaultdict(list)

        # Common entity patterns that aren't meaningful (days, months, common words)
        non_entity_words = {
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
            "The",
            "A",
            "An",
            "And",
            "Or",
            "But",
            "In",
            "On",
            "At",
            "To",
            "For",
            "Of",
            "With",
            "By",
            "From",
            "About",
            "This",
            "That",
            "These",
            "Those",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        }

        # Extract entities from titles, summaries, AND content (expanded for better coverage)
        for (
            article_id,
            title,
            content,
            summary,
            published_at,
            sentiment_score,
            source_domain,
        ) in articles:
            # Include more content to capture entities mentioned in body text
            content_preview = (content or "")[:1500] if content else ""  # First 1500 chars
            raw_text = f"{title} {summary or ''} {content_preview}"

            # Clean text to remove HTML, URLs, and web artifacts
            text = self._clean_text_for_topic_extraction(raw_text)

            # Find capitalized words (potential entities) - MORE AGGRESSIVE
            # Pattern: word starting with capital letter, followed by lowercase
            # Reduced minimum length from 4 to 3 to capture names like "Biden", "Trump", etc.
            entities = re.findall(r"\b[A-Z][a-z]{2,}\b", text)  # Minimum 3 chars (was 4)

            # Also find multi-word capitalized entities (e.g., "United States", "New York", "Donald Trump")
            # More aggressive pattern to capture person names and specific events
            multi_word_entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)

            # Also capture year-based topics (e.g., "2026 elections", "2024 campaign")
            year_entities = re.findall(r"\b(20\d{2})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
            for year, topic in year_entities:
                if len(topic) >= 3:  # Minimum topic length
                    multi_word_entities.append(f"{year} {topic}")

            for entity in entities + multi_word_entities:
                entity_lower = entity.lower()
                # Filter out web artifacts
                if entity_lower in self.web_artifacts:
                    continue
                # Filter out entities that start with web prefixes
                if any(
                    entity_lower.startswith(prefix) for prefix in ["http", "www", "href", "url"]
                ):
                    continue
                # Filter out common non-entities
                if entity not in non_entity_words and entity_lower not in self.stop_words:
                    # Additional filtering: ignore single-letter abbreviations followed by period
                    if not re.match(r"^[A-Z]\.$", entity):
                        # Additional check: ensure it's not too generic
                        if not self._is_too_generic(entity_lower):
                            entity_freq[entity] += 1
                            article_entities[entity].append(article_id)

        # Create topics from frequent entities with LOWER threshold for more granular topics
        topics = []
        for entity, freq in entity_freq.most_common(100):  # Top 100 entities (increased from 25)
            # LOWER threshold - allow entities appearing in just 1 article
            # This captures specific people, places, events like "Donald Trump", "White House", etc.
            if (
                freq >= 1 and len(entity) >= 3
            ):  # Reduced min length from 4 to 3 for names like "Biden"
                # Filter out entities that are too generic
                if not self._is_too_generic(entity):
                    topics.append(
                        TopicInsight(
                            name=entity,
                            frequency=freq,
                            relevance_score=min(freq / 6.0, 1.0),  # Entities get good relevance
                            trend_direction="stable",
                            articles=list(set(article_entities[entity])),  # Remove duplicates
                            keywords=[entity],
                            sentiment="neutral",
                            category="entity",
                            created_at=datetime.now(),
                        )
                    )

        return topics

    def _merge_similar_topics(self, topics: list[TopicInsight]) -> list[TopicInsight]:
        """Merge similar topics to avoid duplicates - phrases take precedence over single words"""
        merged_topics = []
        processed = set()

        # Sort topics: phrases first (longer names), then by frequency
        sorted_topics = sorted(
            topics, key=lambda t: (len(t.name.split()), t.frequency), reverse=True
        )

        for topic in sorted_topics:
            if topic.name.lower() in processed:
                continue

            # Find similar topics
            similar_topics = [topic]
            for other_topic in sorted_topics:
                if (
                    other_topic.name.lower() != topic.name.lower()
                    and other_topic.name.lower() not in processed
                    and self._are_topics_similar(topic, other_topic)
                ):
                    similar_topics.append(other_topic)
                    processed.add(other_topic.name.lower())

            # Merge similar topics - prefer longer phrases over single words
            if len(similar_topics) > 1:
                merged_topic = self._merge_topic_list(similar_topics)
                merged_topics.append(merged_topic)
            else:
                merged_topics.append(topic)

            processed.add(topic.name.lower())

        return merged_topics

    def _are_topics_similar(self, topic1: TopicInsight, topic2: TopicInsight) -> bool:
        """Check if two topics are similar enough to merge"""
        name1_lower = topic1.name.lower()
        name2_lower = topic2.name.lower()

        # Check if one topic name contains the other (e.g., "World" in "World Cup")
        if name1_lower in name2_lower or name2_lower in name1_lower:
            # Ensure it's not just a substring accident (e.g., "art" in "start")
            words1 = set(name1_lower.split())
            words2 = set(name2_lower.split())

            # If any complete word from one topic is in the other, merge them
            if words1.intersection(words2):
                return True

            # Also check if one is a prefix/suffix of the other (with word boundaries)
            if len(name1_lower) >= 4 and len(name2_lower) >= 4:
                # Check word boundary containment
                if re.search(r"\b" + re.escape(name1_lower) + r"\b", name2_lower) or re.search(
                    r"\b" + re.escape(name2_lower) + r"\b", name1_lower
                ):
                    return True

        # Check keyword overlap
        keywords1 = set(topic1.keywords)
        keywords2 = set(topic2.keywords)

        overlap = len(keywords1.intersection(keywords2))
        total = len(keywords1.union(keywords2))

        similarity = overlap / total if total > 0 else 0
        return similarity > 0.4  # 40% similarity threshold (raised for better quality)

    def _merge_topic_list(self, topics: list[TopicInsight]) -> TopicInsight:
        """Merge a list of similar topics into one - prefer longer phrases"""
        if not topics:
            return None

        # Prefer longer phrases (multi-word topics) over single words
        # If multiple topics have the same word count, prefer the most frequent
        base_topic = max(
            topics, key=lambda t: (len(t.name.split()), t.frequency, t.relevance_score)
        )

        # Merge all data
        all_articles = []
        all_keywords = set()

        for topic in topics:
            all_articles.extend(topic.articles)
            all_keywords.update(topic.keywords)

        # Remove duplicates
        all_articles = list(set(all_articles))

        # Use the base topic's name (which should be the longest/most specific)
        # Update frequency to reflect merged articles
        merged_frequency = len(all_articles)

        return TopicInsight(
            name=base_topic.name,
            frequency=merged_frequency,
            relevance_score=max(t.relevance_score for t in topics),  # Use highest relevance
            trend_direction=base_topic.trend_direction,
            articles=all_articles,
            keywords=list(all_keywords),
            sentiment=base_topic.sentiment,
            category=base_topic.category,
            created_at=datetime.now(),
        )

    def _analyze_topic_trends(self, topics: list[TopicInsight]) -> list[TopicInsight]:
        """Analyze trends for topics (simplified)"""
        # For now, mark all as stable
        # In a real implementation, you'd compare with historical data
        for topic in topics:
            topic.trend_direction = "stable"

        return topics

    def _categorize_topics(self, topics: list[TopicInsight]) -> list[TopicInsight]:
        """Categorize topics based on keywords"""
        for topic in topics:
            topic.category = self._determine_category(topic.keywords)

        return topics

    def _determine_category(self, keywords: list[str]) -> str:
        """Determine the category for a topic based on keywords"""
        keyword_scores = defaultdict(int)

        for keyword in keywords:
            keyword_lower = keyword.lower()
            for category, category_keywords in self.topic_categories.items():
                if keyword_lower in category_keywords:
                    keyword_scores[category] += 1

        if keyword_scores:
            return max(keyword_scores.items(), key=lambda x: x[1])[0]

        return "general"

    def generate_word_cloud_data(self, topics: list[TopicInsight]) -> dict[str, Any]:
        """Generate word cloud data for visualization"""
        word_cloud_data = {
            "words": [],
            "categories": defaultdict(list),
            "trends": {"rising": [], "falling": [], "stable": []},
            "summary": {
                "total_topics": len(topics),
                "total_articles": sum(t.frequency for t in topics),
                "categories": len(set(t.category for t in topics)),
            },
        }

        for topic in topics:
            # Add to word cloud
            word_cloud_data["words"].append(
                {
                    "text": topic.name,
                    "size": min(topic.frequency * 10, 100),  # Scale for visualization
                    "frequency": topic.frequency,
                    "relevance": topic.relevance_score,
                    "articles": len(topic.articles),
                }
            )

            # Add to categories
            word_cloud_data["categories"][topic.category].append(
                {
                    "name": topic.name,
                    "frequency": topic.frequency,
                    "relevance": topic.relevance_score,
                }
            )

            # Add to trends
            word_cloud_data["trends"][topic.trend_direction].append(
                {"name": topic.name, "frequency": topic.frequency}
            )

        return word_cloud_data

    def save_topics_to_database(self, topics: list[TopicInsight]) -> bool:
        """Save extracted topics to database with transaction rollback on error"""
        conn = None
        try:
            conn = self.get_db_connection()
            if not conn:
                logger.error("Failed to get database connection")
                return False

            try:
                # Use transaction context (psycopg2 uses autocommit=False by default)
                with conn.cursor() as cur:
                    # Set search path to domain schema
                    cur.execute(f"SET search_path TO {self.schema}, public")

                    topics_saved = 0
                    relationships_saved = 0

                    for topic_idx, topic in enumerate(topics, 1):
                        try:
                            # Check if topic cluster already exists (no UNIQUE constraint, so we check manually)
                            cur.execute(
                                f"SELECT id FROM {self.schema}.topic_clusters WHERE cluster_name = %s",
                                (topic.name,),
                            )
                            existing = cur.fetchone()

                            if existing:
                                # Update existing topic cluster incrementally
                                topic_id = existing[0]
                                cur.execute(
                                    f"""
                                    UPDATE {self.schema}.topic_clusters
                                    SET
                                        updated_at = NOW(),
                                        relevance_score = GREATEST(relevance_score, %s)
                                    WHERE id = %s
                                """,
                                    (topic.relevance_score, topic_id),
                                )
                            else:
                                # Insert new topic cluster
                                cur.execute(
                                    f"""
                                    INSERT INTO {self.schema}.topic_clusters (cluster_name, created_at, updated_at)
                                    VALUES (%s, NOW(), NOW())
                                    RETURNING id
                                """,
                                    (topic.name,),
                                )
                                row = cur.fetchone()
                                if row and len(row) > 0:
                                    topic_id = row[0]
                                else:
                                    raise Exception(
                                        f"Failed to create topic cluster '{topic.name}'"
                                    )

                            # Insert article-topic relationships
                            for article_id in topic.articles:
                                try:
                                    # confidence_score has default value, but we'll set it explicitly
                                    cur.execute(
                                        f"""
                                        INSERT INTO {self.schema}.article_topic_clusters
                                            (article_id, topic_cluster_id, relevance_score, confidence_score)
                                        VALUES (%s, %s, %s, %s)
                                        ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
                                            relevance_score = EXCLUDED.relevance_score,
                                            confidence_score = EXCLUDED.confidence_score
                                    """,
                                        (
                                            article_id,
                                            topic_id,
                                            topic.relevance_score,
                                            topic.relevance_score,
                                        ),
                                    )
                                    relationships_saved += 1
                                except Exception as rel_error:
                                    logger.warning(
                                        f"Failed to save relationship for article {article_id} to topic {topic_id}: {rel_error}"
                                    )
                                    # Continue with other relationships
                                    continue

                            # Save keywords to topic_keywords table for word cloud
                            for keyword in topic.keywords:
                                try:
                                    # Use EXCLUDED for ON CONFLICT updates (PostgreSQL syntax)
                                    cur.execute(
                                        f"""
                                        INSERT INTO {self.schema}.topic_keywords
                                            (topic_cluster_id, keyword, keyword_type, frequency_count, importance_score, last_seen_at)
                                        VALUES (%s, %s, %s, %s, %s, NOW())
                                        ON CONFLICT (topic_cluster_id, keyword) DO UPDATE SET
                                            frequency_count = {self.schema}.topic_keywords.frequency_count + 1,
                                            importance_score = GREATEST({self.schema}.topic_keywords.importance_score, EXCLUDED.importance_score),
                                            last_seen_at = NOW()
                                    """,
                                        (
                                            topic_id,
                                            keyword,
                                            "general",  # Can be enhanced to detect entity types
                                            topic.frequency,
                                            topic.relevance_score,
                                        ),
                                    )
                                except Exception as keyword_error:
                                    logger.warning(
                                        f"Failed to save keyword '{keyword}' for topic '{topic.name}': {keyword_error}"
                                    )
                                    continue

                            topics_saved += 1
                            logger.debug(
                                f"Saved topic {topic_idx}/{len(topics)}: '{topic.name}' ({len(topic.articles)} articles, {len(topic.keywords)} keywords)"
                            )

                        except Exception as topic_error:
                            logger.error(f"Failed to save topic '{topic.name}': {topic_error}")
                            logger.exception("Topic save error traceback:")
                            # Continue with other topics instead of failing entire batch
                            continue

                    # Update topic cluster article_count
                    for topic in topics:
                        try:
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.topic_clusters
                                SET article_count = (
                                    SELECT COUNT(*)
                                    FROM {self.schema}.article_topic_clusters
                                    WHERE topic_cluster_id = {self.schema}.topic_clusters.id
                                ),
                                updated_at = NOW()
                                WHERE cluster_name = %s
                            """,
                                (topic.name,),
                            )
                        except Exception as update_error:
                            logger.warning(
                                f"Failed to update article_count for topic '{topic.name}': {update_error}"
                            )

                    # Commit transaction if we got here
                    conn.commit()
                    logger.info(
                        f"✅ Successfully saved {topics_saved}/{len(topics)} topics, {relationships_saved} relationships, and keywords to database"
                    )
                    return topics_saved > 0  # Return True if at least one topic was saved

            except Exception as db_error:
                # Rollback transaction on any error
                if conn:
                    try:
                        conn.rollback()
                        logger.error(f"❌ Database error, transaction rolled back: {db_error}")
                    except Exception as rollback_error:
                        logger.error(f"❌ Failed to rollback transaction: {rollback_error}")
                logger.exception("Database error traceback:")
                return False
            finally:
                # Close connection
                if conn:
                    try:
                        conn.close()
                    except Exception as close_error:
                        logger.warning(f"Error closing connection: {close_error}")

        except Exception as e:
            logger.error(f"❌ Error saving topics to database: {e}")
            logger.exception("Full error traceback:")
            return False
