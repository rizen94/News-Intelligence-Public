"""
Advanced Deduplication Service for News Intelligence System
Implements multi-layered duplicate detection and article clustering
"""

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import nltk
import numpy as np
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from psycopg2.extras import RealDictCursor
from shared.database.connection import (
    get_db_connection,
    get_db_connection_context,
    get_ephemeral_db_connection_context,
)
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class ArticleMetadata:
    """Article metadata for comparison"""

    id: int
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    author: str | None = None
    content_hash: str | None = None
    word_count: int = 0
    entities: dict = None
    tags: list[str] = None


@dataclass
class DuplicateResult:
    """Result of duplicate detection"""

    is_duplicate: bool
    similarity_score: float
    duplicate_type: str  # 'exact', 'near_exact', 'semantic', 'cross_source'
    matched_article_id: int | None = None
    confidence: float = 0.0
    reasons: list[str] = None


@dataclass
class ClusterResult:
    """Result of article clustering"""

    cluster_id: int
    articles: list[ArticleMetadata]
    centroid_title: str
    centroid_content: str
    cluster_size: int
    similarity_threshold: float
    storyline_suggestion: str | None = None


class AdvancedDeduplicationService:
    """
    Advanced deduplication service with multi-layered detection and clustering
    """

    def __init__(self, db_config: dict):
        """Initialize the deduplication service"""
        self.db_config = db_config
        self.stemmer = PorterStemmer()

        # Download required NLTK data
        try:
            nltk.data.find("tokenizers/punkt")
            nltk.data.find("corpora/stopwords")
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("stopwords", quiet=True)

        self.stop_words = set(stopwords.words("english"))

        # Configuration
        self.config = {
            "content_hash_threshold": 0.95,  # Exact content match
            "semantic_similarity_threshold": 0.75,  # Semantic similarity
            "cross_source_threshold": 0.70,  # Cross-source similarity
            "clustering_eps": 0.3,  # DBSCAN epsilon
            "clustering_min_samples": 2,  # Minimum cluster size
            "max_content_length": 10000,  # Truncate for processing
            "min_content_length": 100,  # Minimum content for analysis
        }

        # Initialize TF-IDF vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=5000, stop_words="english", ngram_range=(1, 2), min_df=2, max_df=0.8
        )

    def generate_content_hash(self, content: str, title: str = None) -> str:
        """
        Generate robust content hash for exact duplicate detection

        Args:
            content: Article content
            title: Article title (optional)

        Returns:
            SHA256 hash of normalized content
        """
        try:
            # Normalize content for consistent hashing
            normalized_content = self._normalize_content_for_hash(content)

            # Include title if provided
            if title:
                normalized_title = self._normalize_content_for_hash(title)
                combined = f"{normalized_title}|{normalized_content}"
            else:
                combined = normalized_content

            # Generate SHA256 hash
            content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

            logger.debug(f"Generated content hash: {content_hash[:16]}...")
            return content_hash

        except Exception as e:
            logger.error(f"Error generating content hash: {e}")
            return ""

    def _normalize_content_for_hash(self, content: str) -> str:
        """Normalize content for consistent hashing"""
        if not content:
            return ""

        # Convert to lowercase
        normalized = content.lower()

        # Remove HTML tags
        normalized = re.sub(r"<[^>]+>", "", normalized)

        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized)

        # Normalize punctuation
        normalized = re.sub(r'[""' "`]", '"', normalized)
        normalized = re.sub(r"[–—]", "-", normalized)
        normalized = re.sub(r"[…]", "...", normalized)

        # Remove extra spaces around punctuation
        normalized = re.sub(r"\s+([.,!?;:])", r"\1", normalized)

        # Remove common artifacts
        normalized = normalized.replace("\xa0", " ")
        normalized = normalized.replace("\u2019", "'")
        normalized = normalized.replace("\u2018", "'")
        normalized = normalized.replace("\u201c", '"')
        normalized = normalized.replace("\u201d", '"')

        return normalized.strip()

    def check_same_source_duplicates(self, article: ArticleMetadata) -> DuplicateResult:
        """
        Check for duplicates from the same source

        Args:
            article: Article to check

        Returns:
            DuplicateResult with detection results
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Check by URL first (most reliable)
            cursor.execute(
                """
                SELECT id, title, content, url, published_at, content_hash
                FROM articles
                WHERE url = %s AND source = %s
            """,
                (article.url, article.source),
            )

            url_match = cursor.fetchone()
            if url_match:
                conn.close()
                return DuplicateResult(
                    is_duplicate=True,
                    similarity_score=1.0,
                    duplicate_type="exact",
                    matched_article_id=url_match["id"],
                    confidence=1.0,
                    reasons=["Exact URL match from same source"],
                )

            # Check by content hash
            if article.content_hash:
                cursor.execute(
                    """
                    SELECT id, title, content, url, published_at, content_hash
                    FROM articles
                    WHERE content_hash = %s AND source = %s
                """,
                    (article.content_hash, article.source),
                )

                hash_match = cursor.fetchone()
                if hash_match:
                    conn.close()
                    return DuplicateResult(
                        is_duplicate=True,
                        similarity_score=1.0,
                        duplicate_type="exact",
                        matched_article_id=hash_match["id"],
                        confidence=1.0,
                        reasons=["Exact content hash match from same source"],
                    )

            # Check for near-duplicates (high similarity)
            cursor.execute(
                """
                SELECT id, title, content, url, published_at, content_hash
                FROM articles
                WHERE source = %s
                AND published_at > %s
                ORDER BY published_at DESC
                LIMIT 100
            """,
                (article.source, datetime.now() - timedelta(days=7)),
            )

            recent_articles = cursor.fetchall()
            conn.close()

            # Check similarity with recent articles
            for recent_article in recent_articles:
                similarity = self._calculate_content_similarity(
                    article.content, recent_article["content"]
                )

                if similarity >= self.config["content_hash_threshold"]:
                    return DuplicateResult(
                        is_duplicate=True,
                        similarity_score=similarity,
                        duplicate_type="near_exact",
                        matched_article_id=recent_article["id"],
                        confidence=similarity,
                        reasons=[f"High content similarity ({similarity:.2f}) from same source"],
                    )

            return DuplicateResult(
                is_duplicate=False,
                similarity_score=0.0,
                duplicate_type="none",
                confidence=1.0,
                reasons=["No duplicates found in same source"],
            )

        except Exception as e:
            logger.error(f"Error checking same-source duplicates: {e}")
            return DuplicateResult(
                is_duplicate=False,
                similarity_score=0.0,
                duplicate_type="error",
                confidence=0.0,
                reasons=[f"Error during duplicate check: {str(e)}"],
            )

    def check_cross_source_duplicates(self, article: ArticleMetadata) -> DuplicateResult:
        """
        Check for duplicates from different sources

        Args:
            article: Article to check

        Returns:
            DuplicateResult with detection results
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get recent articles from other sources
            cursor.execute(
                """
                SELECT id, title, content, url, source, published_at, content_hash
                FROM articles
                WHERE source != %s
                AND published_at > %s
                AND LENGTH(content) > %s
                ORDER BY published_at DESC
                LIMIT 200
            """,
                (
                    article.source,
                    datetime.now() - timedelta(days=3),
                    self.config["min_content_length"],
                ),
            )

            recent_articles = cursor.fetchall()
            conn.close()

            best_match = None
            best_similarity = 0.0

            # Check similarity with articles from other sources
            for recent_article in recent_articles:
                # Calculate multiple similarity metrics
                content_similarity = self._calculate_content_similarity(
                    article.content, recent_article["content"]
                )

                title_similarity = self._calculate_title_similarity(
                    article.title, recent_article["title"]
                )

                # Weighted similarity score
                combined_similarity = content_similarity * 0.7 + title_similarity * 0.3

                if combined_similarity > best_similarity:
                    best_similarity = combined_similarity
                    best_match = recent_article

            # Check if similarity exceeds threshold
            if best_match and best_similarity >= self.config["cross_source_threshold"]:
                return DuplicateResult(
                    is_duplicate=True,
                    similarity_score=best_similarity,
                    duplicate_type="cross_source",
                    matched_article_id=best_match["id"],
                    confidence=best_similarity,
                    reasons=[
                        f"Cross-source similarity ({best_similarity:.2f})",
                        f"Matched with {best_match['source']} article",
                    ],
                )

            return DuplicateResult(
                is_duplicate=False,
                similarity_score=best_similarity,
                duplicate_type="none",
                confidence=1.0 - best_similarity,
                reasons=["No cross-source duplicates found"],
            )

        except Exception as e:
            logger.error(f"Error checking cross-source duplicates: {e}")
            return DuplicateResult(
                is_duplicate=False,
                similarity_score=0.0,
                duplicate_type="error",
                confidence=0.0,
                reasons=[f"Error during cross-source check: {str(e)}"],
            )

    def cluster_similar_articles(self, articles: list[ArticleMetadata]) -> list[ClusterResult]:
        """
        Cluster articles by similarity for storyline suggestions

        Args:
            articles: List of articles to cluster

        Returns:
            List of ClusterResult objects
        """
        try:
            if len(articles) < 2:
                return []

            # Prepare text data for clustering
            texts = []
            article_ids = []

            for article in articles:
                # Combine title and content for clustering
                combined_text = f"{article.title} {article.content}"
                texts.append(self._preprocess_for_clustering(combined_text))
                article_ids.append(article.id)

            # Create TF-IDF matrix
            tfidf_matrix = self.vectorizer.fit_transform(texts)

            # Perform DBSCAN clustering
            clustering = DBSCAN(
                eps=self.config["clustering_eps"],
                min_samples=self.config["clustering_min_samples"],
                metric="cosine",
            )

            cluster_labels = clustering.fit_predict(tfidf_matrix)

            # Group articles by cluster
            clusters = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                if label != -1:  # -1 is noise in DBSCAN
                    clusters[label].append(articles[i])

            # Create cluster results
            cluster_results = []
            for cluster_id, cluster_articles in clusters.items():
                if len(cluster_articles) >= self.config["clustering_min_samples"]:
                    # Calculate cluster centroid
                    centroid_title, centroid_content = self._calculate_cluster_centroid(
                        cluster_articles, tfidf_matrix, cluster_id, cluster_labels
                    )

                    # Generate storyline suggestion
                    storyline_suggestion = self._generate_storyline_suggestion(
                        cluster_articles, centroid_title
                    )

                    cluster_result = ClusterResult(
                        cluster_id=cluster_id,
                        articles=cluster_articles,
                        centroid_title=centroid_title,
                        centroid_content=centroid_content,
                        cluster_size=len(cluster_articles),
                        similarity_threshold=self.config["clustering_eps"],
                        storyline_suggestion=storyline_suggestion,
                    )

                    cluster_results.append(cluster_result)

            logger.info(f"Created {len(cluster_results)} clusters from {len(articles)} articles")
            return cluster_results

        except Exception as e:
            logger.error(f"Error clustering articles: {e}")
            return []

    def find_storyline_candidates(self, article: ArticleMetadata) -> list[ClusterResult]:
        """
        Find existing storylines that this article could belong to

        Args:
            article: Article to find candidates for

        Returns:
            List of ClusterResult objects representing potential storylines
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get recent articles that could be similar
            cursor.execute(
                """
                SELECT a.id, a.title, a.content, a.url, a.source, a.published_at,
                       s.id as storyline_id, s.title as storyline_title
                FROM articles a
                LEFT JOIN storyline_articles sa ON a.id = sa.article_id
                LEFT JOIN storylines s ON sa.storyline_id = s.id
                WHERE a.published_at > %s
                AND LENGTH(a.content) > %s
                ORDER BY a.published_at DESC
                LIMIT 500
            """,
                (datetime.now() - timedelta(days=7), self.config["min_content_length"]),
            )

            recent_articles = cursor.fetchall()
            conn.close()

            # Convert to ArticleMetadata objects
            articles_for_clustering = []
            for row in recent_articles:
                article_meta = ArticleMetadata(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    url=row["url"],
                    source=row["source"],
                    published_at=row["published_at"],
                )
                articles_for_clustering.append(article_meta)

            # Add the new article
            articles_for_clustering.append(article)

            # Perform clustering
            clusters = self.cluster_similar_articles(articles_for_clustering)

            # Filter clusters that contain the new article
            relevant_clusters = []
            for cluster in clusters:
                if any(a.id == article.id for a in cluster.articles):
                    relevant_clusters.append(cluster)

            return relevant_clusters

        except Exception as e:
            logger.error(f"Error finding storyline candidates: {e}")
            return []

    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate content similarity using multiple methods"""
        try:
            if not content1 or not content2:
                return 0.0

            # Normalize content
            norm1 = self._normalize_content_for_hash(content1)
            norm2 = self._normalize_content_for_hash(content2)

            # Exact match
            if norm1 == norm2:
                return 1.0

            # Jaccard similarity on words
            words1 = set(norm1.split())
            words2 = set(norm2.split())

            if len(words1) == 0 or len(words2) == 0:
                return 0.0

            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))

            jaccard_similarity = intersection / union if union > 0 else 0.0

            # TF-IDF cosine similarity
            try:
                tfidf_matrix = self.vectorizer.fit_transform([norm1, norm2])
                cosine_sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

                # Combine both methods
                combined_similarity = jaccard_similarity * 0.4 + cosine_sim * 0.6
                return combined_similarity

            except Exception:
                # Fallback to Jaccard similarity only
                return jaccard_similarity

        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.0

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate title similarity"""
        try:
            if not title1 or not title2:
                return 0.0

            # Normalize titles
            norm1 = self._normalize_content_for_hash(title1)
            norm2 = self._normalize_content_for_hash(title2)

            # Exact match
            if norm1 == norm2:
                return 1.0

            # Word overlap similarity
            words1 = set(norm1.split())
            words2 = set(norm2.split())

            if len(words1) == 0 or len(words2) == 0:
                return 0.0

            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))

            return intersection / union if union > 0 else 0.0

        except Exception as e:
            logger.error(f"Error calculating title similarity: {e}")
            return 0.0

    def _preprocess_for_clustering(self, text: str) -> str:
        """Preprocess text for clustering"""
        try:
            # Convert to lowercase
            text = text.lower()

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", "", text)

            # Remove URLs
            text = re.sub(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                "",
                text,
            )

            # Remove extra whitespace
            text = re.sub(r"\s+", " ", text)

            # Tokenize and stem
            tokens = word_tokenize(text)
            tokens = [self.stemmer.stem(token) for token in tokens if token.isalpha()]

            # Remove stop words
            tokens = [token for token in tokens if token not in self.stop_words]

            return " ".join(tokens)

        except Exception as e:
            logger.error(f"Error preprocessing text for clustering: {e}")
            return text

    def _calculate_cluster_centroid(
        self, articles: list[ArticleMetadata], tfidf_matrix, cluster_id: int, cluster_labels
    ) -> tuple[str, str]:
        """Calculate cluster centroid"""
        try:
            # Find articles in this cluster
            cluster_indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]

            if not cluster_indices:
                return "", ""

            # Get TF-IDF vectors for cluster articles
            cluster_vectors = tfidf_matrix[cluster_indices]

            # Calculate centroid vector
            centroid_vector = np.mean(cluster_vectors.toarray(), axis=0)

            # Find article closest to centroid
            similarities = cosine_similarity(cluster_vectors, centroid_vector.reshape(1, -1))
            closest_idx = cluster_indices[np.argmax(similarities)]

            closest_article = articles[closest_idx]
            return closest_article.title, closest_article.content[:500]  # Truncate content

        except Exception as e:
            logger.error(f"Error calculating cluster centroid: {e}")
            return "", ""

    def _generate_storyline_suggestion(
        self, articles: list[ArticleMetadata], centroid_title: str
    ) -> str:
        """Generate storyline suggestion from cluster"""
        try:
            # Extract common keywords from titles
            all_titles = [article.title for article in articles]

            # Find common words
            word_counts = defaultdict(int)
            for title in all_titles:
                words = title.lower().split()
                for word in words:
                    if len(word) > 3 and word not in self.stop_words:
                        word_counts[word] += 1

            # Get most common words
            common_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            keywords = [word for word, count in common_words if count > 1]

            # Generate suggestion
            if keywords:
                suggestion = f"Storyline: {' '.join(keywords).title()}"
            else:
                suggestion = f"Storyline: {centroid_title[:50]}..."

            return suggestion

        except Exception as e:
            logger.error(f"Error generating storyline suggestion: {e}")
            return f"Storyline: {centroid_title[:50]}..."

    async def detect_duplicates(
        self,
        article_ids: list[int] | None = None,
        time_window_hours: int = 24,
        max_articles: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Detect duplicates among articles (alias for detect_duplicates_batch for compatibility).

        Args:
            article_ids: Optional list of specific article IDs to check
            time_window_hours: Time window for recent articles (default 24 hours)
            max_articles: Maximum number of articles to process (ignored, uses limit in query)
            **kwargs: Additional arguments for compatibility

        Returns:
            Dictionary with duplicate detection results
        """
        return await self.detect_duplicates_batch(article_ids, time_window_hours)

    async def detect_duplicates_batch(
        self, article_ids: list[int] | None = None, time_window_hours: int = 24
    ) -> dict[str, Any]:
        """
        Detect duplicates in a batch of articles.

        Args:
            article_ids: Optional list of specific article IDs to check
            time_window_hours: Time window for recent articles (default 24 hours)

        Returns:
            Dictionary with duplicate detection results
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get articles to process
            if article_ids:
                placeholders = ",".join(["%s"] * len(article_ids))
                cursor.execute(
                    f"""
                    SELECT id, title, content, url, source_domain as source,
                           published_at, content_hash, author, word_count
                    FROM articles
                    WHERE id IN ({placeholders})
                    AND LENGTH(content) >= %s
                    ORDER BY published_at DESC
                """,
                    article_ids + [self.config["min_content_length"]],
                )
            else:
                cursor.execute(
                    """
                    SELECT id, title, content, url, source_domain as source,
                           published_at, content_hash, author, word_count
                    FROM articles
                    WHERE published_at >= %s
                    AND LENGTH(content) >= %s
                    AND is_duplicate = false
                    ORDER BY published_at DESC
                    LIMIT 1000
                """,
                    (
                        datetime.now() - timedelta(hours=time_window_hours),
                        self.config["min_content_length"],
                    ),
                )

            articles_data = cursor.fetchall()
            conn.close()

            if len(articles_data) < 2:
                return {
                    "duplicates_found": 0,
                    "clusters_created": 0,
                    "articles_processed": len(articles_data),
                    "message": "Not enough articles to process",
                }

            # Convert to ArticleMetadata objects
            articles = []
            for row in articles_data:
                article = ArticleMetadata(
                    id=row["id"],
                    title=row["title"] or "",
                    content=row["content"] or "",
                    url=row["url"] or "",
                    source=row["source"] or "",
                    published_at=row["published_at"],
                    author=row.get("author"),
                    content_hash=row.get("content_hash"),
                    word_count=row.get("word_count", 0),
                )
                articles.append(article)

            # Detect duplicates
            duplicate_pairs = []
            for i, article1 in enumerate(articles):
                for article2 in articles[i + 1 :]:
                    # Check same source first
                    if article1.source == article2.source:
                        result = self.check_same_source_duplicates(article1)
                        if result.is_duplicate and result.matched_article_id == article2.id:
                            duplicate_pairs.append(
                                {
                                    "article1_id": article1.id,
                                    "article2_id": article2.id,
                                    "similarity_score": result.similarity_score,
                                    "duplicate_type": result.duplicate_type,
                                }
                            )
                    else:
                        # Check cross-source
                        result = self.check_cross_source_duplicates(article1)
                        if result.is_duplicate and result.matched_article_id == article2.id:
                            duplicate_pairs.append(
                                {
                                    "article1_id": article1.id,
                                    "article2_id": article2.id,
                                    "similarity_score": result.similarity_score,
                                    "duplicate_type": result.duplicate_type,
                                }
                            )

            # Create clusters
            clusters = self.cluster_similar_articles(articles)

            # Save results
            await self._save_duplicate_results(duplicate_pairs, clusters)

            return {
                "duplicates_found": len(duplicate_pairs),
                "clusters_created": len(clusters),
                "articles_processed": len(articles),
                "duplicate_pairs": len(duplicate_pairs),
                "clusters": len(clusters),
            }

        except Exception as e:
            logger.error(f"Error in batch duplicate detection: {e}")
            return {"error": str(e)}

    async def _save_duplicate_results(
        self, duplicate_pairs: list[dict], clusters: list[ClusterResult]
    ):
        """Save duplicate detection results to database"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Save duplicate pairs
            for pair in duplicate_pairs:
                cursor.execute(
                    """
                    INSERT INTO duplicate_pairs (
                        article1_id, article2_id, similarity_score,
                        duplicate_type, detected_at, status
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (article1_id, article2_id) DO UPDATE SET
                        similarity_score = EXCLUDED.similarity_score,
                        duplicate_type = EXCLUDED.duplicate_type,
                        detected_at = EXCLUDED.detected_at
                """,
                    (
                        pair["article1_id"],
                        pair["article2_id"],
                        pair["similarity_score"],
                        pair["duplicate_type"],
                        datetime.now(),
                        "active",
                    ),
                )

            # Save clusters and update articles
            for cluster in clusters:
                # Determine canonical article (first in cluster)
                canonical_id = cluster.articles[0].id if cluster.articles else None

                for article in cluster.articles:
                    is_canonical = article.id == canonical_id
                    cursor.execute(
                        """
                        UPDATE articles
                        SET cluster_id = %s,
                            is_duplicate = %s,
                            canonical_article_id = %s
                        WHERE id = %s
                    """,
                        (
                            cluster.cluster_id,
                            not is_canonical,
                            canonical_id if not is_canonical else None,
                            article.id,
                        ),
                    )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error saving duplicate results: {e}")
            if "conn" in locals():
                conn.rollback()
                conn.close()

    def get_deduplication_stats(self, *, use_ephemeral_connection: bool = False) -> dict[str, Any]:
        """Get deduplication statistics.

        When ``use_ephemeral_connection`` is True (e.g. daily briefing), use a one-off connection
        that fully disconnects on exit instead of returning a session to the shared pool.
        """
        ctx = (
            get_ephemeral_db_connection_context
            if use_ephemeral_connection
            else get_db_connection_context
        )
        try:
            with ctx() as conn:
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Total articles
                cursor.execute("SELECT COUNT(*) FROM articles")
                total_articles = cursor.fetchone()[0]

                # Duplicate articles
                cursor.execute("SELECT COUNT(*) FROM articles WHERE is_duplicate = true")
                duplicate_articles = cursor.fetchone()[0]

                # Clusters
                cursor.execute(
                    "SELECT COUNT(DISTINCT cluster_id) FROM articles WHERE cluster_id IS NOT NULL"
                )
                clusters = cursor.fetchone()[0]

                # Duplicate pairs
                cursor.execute("SELECT COUNT(*) FROM duplicate_pairs WHERE status = 'active'")
                duplicate_pairs = cursor.fetchone()[0]

                # Recent duplicates (last 24 hours)
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM duplicate_pairs
                    WHERE detected_at >= %s
                """,
                    (datetime.now() - timedelta(hours=24),),
                )
                recent_duplicates = cursor.fetchone()[0]

            return {
                "total_articles": total_articles,
                "duplicate_articles": duplicate_articles,
                "clusters": clusters,
                "duplicate_pairs": duplicate_pairs,
                "recent_duplicates": recent_duplicates,
                "duplicate_rate": (duplicate_articles / total_articles * 100)
                if total_articles > 0
                else 0,
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting deduplication stats: {e}")
            return {"error": str(e)}


# Global instance factory
def get_deduplication_service(db_config: dict | None = None) -> AdvancedDeduplicationService:
    """
    Get or create deduplication service instance.

    Args:
        db_config: Database configuration dictionary. If None, uses environment variables.

    Returns:
        AdvancedDeduplicationService instance
    """

    if db_config is None:
        from shared.database.connection import get_db_config

        db_config = get_db_config()

    return AdvancedDeduplicationService(db_config)
