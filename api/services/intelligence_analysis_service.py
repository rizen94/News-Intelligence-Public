"""
Intelligence Analysis Service
Provides RAG-enhanced analysis, quality assessment, anomaly detection, and impact assessment.

Features:
1. RAG-Enhanced Analysis - Deep context retrieval for storylines
5. Quality Assessment - Narrative coherence, factual validation
6. Anomaly Detection - Unusual pattern identification
7. Impact Assessment - Consequence analysis
"""

import logging
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from concurrent.futures import ThreadPoolExecutor
import os

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.1:8b"
MAX_CONTEXT_ARTICLES = 20
ANOMALY_THRESHOLD = 2.0  # Standard deviations for anomaly detection


@dataclass
class RAGContext:
    """Context retrieved via RAG for a storyline"""
    storyline_id: int
    query: str
    retrieved_articles: List[Dict[str, Any]]
    context_summary: str
    relevance_scores: List[float]
    historical_context: str
    related_entities: List[str]
    temporal_span: Tuple[datetime, datetime]
    source_diversity: float
    retrieval_time_ms: float


@dataclass
class QualityAssessment:
    """Quality assessment for a storyline"""
    storyline_id: int
    overall_score: float  # 0-1
    coherence_score: float  # Narrative flow
    factual_score: float  # Cross-source verification
    completeness_score: float  # Coverage depth
    source_diversity_score: float  # Multiple perspectives
    temporal_consistency_score: float  # Timeline accuracy
    issues: List[str]
    recommendations: List[str]
    assessed_at: datetime


@dataclass
class AnomalyReport:
    """Anomaly detection results"""
    entity_type: str  # 'article', 'storyline', 'topic', 'source'
    entity_id: int
    anomaly_type: str  # 'outlier', 'sudden_spike', 'pattern_break', 'unusual_entity'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    detected_value: float
    expected_range: Tuple[float, float]
    supporting_evidence: List[str]
    detected_at: datetime


@dataclass
class ImpactAssessment:
    """Impact assessment for a storyline or article"""
    entity_type: str
    entity_id: int
    overall_impact_score: float  # 0-1
    reach_score: float  # How many sources covered it
    significance_score: float  # Importance of topic
    velocity_score: float  # How fast it's spreading
    longevity_prediction: str  # 'short', 'medium', 'long'
    affected_domains: List[str]
    key_stakeholders: List[str]
    potential_consequences: List[str]
    confidence: float
    assessed_at: datetime


class IntelligenceAnalysisService:
    """
    Comprehensive intelligence analysis service providing:
    - RAG-Enhanced Analysis
    - Quality Assessment
    - Anomaly Detection
    - Impact Assessment
    """

    def __init__(self, db_config: Dict[str, Any] = None):
        if db_config is None:
            from shared.database.connection import get_db_config
            db_config = get_db_config()
        self.db_config = db_config
        self.executor = ThreadPoolExecutor(max_workers=4)
        logger.info("Intelligence Analysis Service initialized")

    def get_db_connection(self):
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection as _get_conn
        return _get_conn()

    # =========================================================================
    # RAG-ENHANCED ANALYSIS
    # =========================================================================

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Ollama"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text[:8000]},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("embedding")
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
        return None

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def retrieve_context_for_storyline(
        self,
        domain: str,
        storyline_id: int,
        query: Optional[str] = None,
        max_articles: int = MAX_CONTEXT_ARTICLES
    ) -> RAGContext:
        """
        RAG-enhanced context retrieval for a storyline.
        Retrieves relevant articles based on semantic similarity.
        """
        start_time = datetime.now()
        schema = domain.replace('-', '_')

        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get storyline details
                cur.execute(f"""
                    SELECT s.*, array_agg(sa.article_id) as article_ids
                    FROM {schema}.storylines s
                    LEFT JOIN {schema}.storyline_articles sa ON s.id = sa.storyline_id
                    WHERE s.id = %s
                    GROUP BY s.id
                """, (storyline_id,))
                storyline = cur.fetchone()

                if not storyline:
                    raise ValueError(f"Storyline {storyline_id} not found")

                # Build query from storyline if not provided
                if not query:
                    query = f"{storyline['title']} {storyline.get('description', '')}"

                # Generate query embedding
                query_embedding = self.generate_embedding(query)
                if not query_embedding:
                    raise ValueError("Failed to generate query embedding")

                # Retrieve articles with embeddings
                cur.execute(f"""
                    SELECT id, title, content, source_name, published_at, embedding_vector,
                           extracted_entities
                    FROM {schema}.articles
                    WHERE embedding_vector IS NOT NULL
                    ORDER BY published_at DESC
                    LIMIT 500
                """)
                articles = cur.fetchall()

                # Calculate similarities and rank
                scored_articles = []
                for article in articles:
                    if article['embedding_vector']:
                        try:
                            emb = [float(x) for x in article['embedding_vector'].strip('[]').split(',')]
                            sim = self.cosine_similarity(query_embedding, emb)
                            scored_articles.append((article, sim))
                        except:
                            continue

                # Sort by similarity and take top N
                scored_articles.sort(key=lambda x: x[1], reverse=True)
                top_articles = scored_articles[:max_articles]

                # Extract context information
                retrieved = [a[0] for a in top_articles]
                relevance_scores = [a[1] for a in top_articles]

                # Calculate temporal span
                dates = [a['published_at'] for a in retrieved if a.get('published_at')]
                temporal_span = (min(dates), max(dates)) if dates else (datetime.now(), datetime.now())

                # Calculate source diversity
                sources = set(a.get('source_name', 'unknown') for a in retrieved)
                source_diversity = len(sources) / max(len(retrieved), 1)

                # Extract related entities
                all_entities = []
                for a in retrieved:
                    if a.get('extracted_entities'):
                        try:
                            entities = a['extracted_entities'] if isinstance(a['extracted_entities'], list) else []
                            all_entities.extend(entities)
                        except:
                            pass
                entity_counts = Counter(all_entities)
                related_entities = [e for e, _ in entity_counts.most_common(20)]

                # Generate context summary using LLM
                context_text = "\n".join([
                    f"- {a['title']}" for a in retrieved[:10]
                ])
                context_summary = self._generate_context_summary(query, context_text)

                # Generate historical context
                historical_context = self._generate_historical_context(
                    storyline['title'],
                    retrieved
                )

                retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

                return RAGContext(
                    storyline_id=storyline_id,
                    query=query,
                    retrieved_articles=[{
                        'id': a['id'],
                        'title': a['title'],
                        'source': a.get('source_name'),
                        'published_at': str(a.get('published_at')),
                        'relevance': round(s, 3)
                    } for a, s in top_articles],
                    context_summary=context_summary,
                    relevance_scores=relevance_scores,
                    historical_context=historical_context,
                    related_entities=related_entities,
                    temporal_span=temporal_span,
                    source_diversity=source_diversity,
                    retrieval_time_ms=retrieval_time
                )
        finally:
            conn.close()

    def _generate_context_summary(self, query: str, context: str) -> str:
        """Generate a summary of retrieved context using LLM"""
        try:
            prompt = f"""Based on these news articles related to "{query}", provide a brief 2-3 sentence summary of the key context:

{context}

Summary:"""
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Context summary generation failed: {e}")
        return "Context summary unavailable"

    def _generate_historical_context(self, title: str, articles: List[Dict]) -> str:
        """Generate historical context from articles"""
        try:
            oldest = min(articles, key=lambda x: x.get('published_at', datetime.now()))
            newest = max(articles, key=lambda x: x.get('published_at', datetime.now()))

            prompt = f"""For the news story "{title}", provide brief historical context based on articles spanning from {oldest.get('published_at')} to {newest.get('published_at')}. Key headlines include:

{chr(10).join([f"- {a['title']}" for a in articles[:5]])}

Historical context (2-3 sentences):"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Historical context generation failed: {e}")
        return "Historical context unavailable"

    # =========================================================================
    # QUALITY ASSESSMENT
    # =========================================================================

    def assess_storyline_quality(
        self,
        domain: str,
        storyline_id: int
    ) -> QualityAssessment:
        """
        Comprehensive quality assessment of a storyline.
        Evaluates coherence, factual accuracy, completeness, and more.
        """
        schema = domain.replace('-', '_')
        conn = self.get_db_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get storyline with articles
                cur.execute(f"""
                    SELECT s.*,
                           array_agg(DISTINCT a.id) as article_ids,
                           array_agg(DISTINCT a.source_name) as sources,
                           array_agg(DISTINCT a.title) as article_titles,
                           MIN(a.published_at) as earliest_article,
                           MAX(a.published_at) as latest_article,
                           COUNT(DISTINCT a.id) as article_count
                    FROM {schema}.storylines s
                    LEFT JOIN {schema}.storyline_articles sa ON s.id = sa.storyline_id
                    LEFT JOIN {schema}.articles a ON sa.article_id = a.id
                    WHERE s.id = %s
                    GROUP BY s.id
                """, (storyline_id,))
                storyline = cur.fetchone()

                if not storyline:
                    raise ValueError(f"Storyline {storyline_id} not found")

                issues = []
                recommendations = []

                # 1. Coherence Score - Does the narrative flow make sense?
                coherence_score = self._assess_coherence(storyline, cur, schema)
                if coherence_score < 0.6:
                    issues.append("Low narrative coherence - articles may not be strongly related")
                    recommendations.append("Consider reviewing article assignments for relevance")

                # 2. Factual Score - Cross-source verification
                factual_score = self._assess_factual_accuracy(storyline, cur, schema)
                if factual_score < 0.7:
                    issues.append("Limited cross-source verification")
                    recommendations.append("Add articles from additional sources to verify facts")

                # 3. Completeness Score - Coverage depth
                completeness_score = self._assess_completeness(storyline)
                if completeness_score < 0.5:
                    issues.append("Storyline may lack complete coverage")
                    recommendations.append("Consider adding more articles to provide fuller context")

                # 4. Source Diversity Score
                sources = [s for s in (storyline.get('sources') or []) if s]
                source_diversity_score = min(len(set(sources)) / 5, 1.0)  # 5+ sources = 1.0
                if source_diversity_score < 0.4:
                    issues.append("Limited source diversity")
                    recommendations.append("Include articles from more diverse sources")

                # 5. Temporal Consistency Score
                temporal_score = self._assess_temporal_consistency(storyline, cur, schema)
                if temporal_score < 0.7:
                    issues.append("Potential timeline gaps or inconsistencies")
                    recommendations.append("Review timeline for missing events or date errors")

                # Calculate overall score
                overall_score = (
                    coherence_score * 0.25 +
                    factual_score * 0.25 +
                    completeness_score * 0.20 +
                    source_diversity_score * 0.15 +
                    temporal_score * 0.15
                )

                return QualityAssessment(
                    storyline_id=storyline_id,
                    overall_score=round(overall_score, 3),
                    coherence_score=round(coherence_score, 3),
                    factual_score=round(factual_score, 3),
                    completeness_score=round(completeness_score, 3),
                    source_diversity_score=round(source_diversity_score, 3),
                    temporal_consistency_score=round(temporal_score, 3),
                    issues=issues,
                    recommendations=recommendations,
                    assessed_at=datetime.now()
                )
        finally:
            conn.close()

    def _assess_coherence(self, storyline: Dict, cur, schema: str) -> float:
        """Assess narrative coherence using entity overlap and semantic similarity"""
        article_ids = [a for a in (storyline.get('article_ids') or []) if a]
        if len(article_ids) < 2:
            return 0.5  # Can't assess coherence with < 2 articles

        # Get embeddings for articles
        cur.execute(f"""
            SELECT id, embedding_vector, extracted_entities
            FROM {schema}.articles
            WHERE id = ANY(%s) AND embedding_vector IS NOT NULL
        """, (article_ids,))
        articles = cur.fetchall()

        if len(articles) < 2:
            return 0.5

        # Calculate pairwise similarities
        similarities = []
        for i, a1 in enumerate(articles):
            for a2 in articles[i+1:]:
                try:
                    emb1 = [float(x) for x in a1['embedding_vector'].strip('[]').split(',')]
                    emb2 = [float(x) for x in a2['embedding_vector'].strip('[]').split(',')]
                    sim = self.cosine_similarity(emb1, emb2)
                    similarities.append(sim)
                except:
                    continue

        if not similarities:
            return 0.5

        # High average similarity = high coherence
        avg_similarity = np.mean(similarities)
        return min(avg_similarity * 1.5, 1.0)  # Scale up, cap at 1.0

    def _assess_factual_accuracy(self, storyline: Dict, cur, schema: str) -> float:
        """Assess factual accuracy through cross-source verification"""
        sources = [s for s in (storyline.get('sources') or []) if s]
        unique_sources = set(sources)

        # More sources = higher confidence in facts
        if len(unique_sources) >= 5:
            return 0.9
        elif len(unique_sources) >= 3:
            return 0.75
        elif len(unique_sources) >= 2:
            return 0.6
        else:
            return 0.4

    def _assess_completeness(self, storyline: Dict) -> float:
        """Assess storyline completeness"""
        article_count = storyline.get('article_count', 0) or 0

        # More articles generally = more complete coverage
        if article_count >= 20:
            return 1.0
        elif article_count >= 10:
            return 0.8
        elif article_count >= 5:
            return 0.6
        elif article_count >= 2:
            return 0.4
        else:
            return 0.2

    def _assess_temporal_consistency(self, storyline: Dict, cur, schema: str) -> float:
        """Assess temporal consistency of storyline"""
        earliest = storyline.get('earliest_article')
        latest = storyline.get('latest_article')

        if not earliest or not latest:
            return 0.5

        # Check for reasonable time span
        span = (latest - earliest).days if hasattr(latest - earliest, 'days') else 0

        if span > 365:
            return 0.6  # Very long stories may have gaps
        elif span > 30:
            return 0.8
        else:
            return 0.9

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================

    def detect_anomalies(
        self,
        domain: str,
        hours: int = 24,
        sensitivity: float = ANOMALY_THRESHOLD
    ) -> List[AnomalyReport]:
        """
        Detect anomalies in article flow, storyline patterns, and entity mentions.
        """
        schema = domain.replace('-', '_')
        anomalies = []
        conn = self.get_db_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cutoff = datetime.now() - timedelta(hours=hours)

                # 1. Detect article volume spikes
                anomalies.extend(self._detect_volume_spikes(cur, schema, cutoff, sensitivity))

                # 2. Detect unusual entity mentions
                anomalies.extend(self._detect_entity_anomalies(cur, schema, cutoff, sensitivity))

                # 3. Detect source behavior anomalies
                anomalies.extend(self._detect_source_anomalies(cur, schema, cutoff, sensitivity))

                # 4. Detect storyline growth anomalies
                anomalies.extend(self._detect_storyline_anomalies(cur, schema, cutoff, sensitivity))

        finally:
            conn.close()

        return anomalies

    def _detect_volume_spikes(self, cur, schema: str, cutoff: datetime, threshold: float) -> List[AnomalyReport]:
        """Detect unusual spikes in article volume"""
        anomalies = []

        # Get hourly article counts for past week
        cur.execute(f"""
            SELECT date_trunc('hour', created_at) as hour, COUNT(*) as count
            FROM {schema}.articles
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY hour
            ORDER BY hour
        """)
        hourly_counts = cur.fetchall()

        if len(hourly_counts) < 24:
            return anomalies

        counts = [h['count'] for h in hourly_counts]
        mean = np.mean(counts)
        std = np.std(counts)

        if std == 0:
            return anomalies

        # Check recent hours for anomalies
        for row in hourly_counts[-24:]:
            z_score = (row['count'] - mean) / std
            if abs(z_score) > threshold:
                severity = 'critical' if abs(z_score) > 3 else 'high' if abs(z_score) > 2.5 else 'medium'
                anomalies.append(AnomalyReport(
                    entity_type='article_volume',
                    entity_id=0,
                    anomaly_type='sudden_spike' if z_score > 0 else 'sudden_drop',
                    severity=severity,
                    description=f"Unusual article volume at {row['hour']}: {row['count']} articles (expected {mean:.1f} ± {std:.1f})",
                    detected_value=float(row['count']),
                    expected_range=(mean - threshold * std, mean + threshold * std),
                    supporting_evidence=[f"Z-score: {z_score:.2f}"],
                    detected_at=datetime.now()
                ))

        return anomalies

    def _detect_entity_anomalies(self, cur, schema: str, cutoff: datetime, threshold: float) -> List[AnomalyReport]:
        """Detect unusual entity mention patterns"""
        anomalies = []

        # This would require entity tracking over time - simplified version
        cur.execute(f"""
            SELECT extracted_entities, COUNT(*) as article_count
            FROM {schema}.articles
            WHERE created_at > %s AND extracted_entities IS NOT NULL
            GROUP BY extracted_entities
            HAVING COUNT(*) > 5
        """, (cutoff,))

        return anomalies

    def _detect_source_anomalies(self, cur, schema: str, cutoff: datetime, threshold: float) -> List[AnomalyReport]:
        """Detect unusual source behavior"""
        anomalies = []

        # Get source publishing patterns
        cur.execute(f"""
            SELECT source_name, COUNT(*) as recent_count
            FROM {schema}.articles
            WHERE created_at > %s AND source_name IS NOT NULL
            GROUP BY source_name
        """, (cutoff,))
        recent_sources = {r['source_name']: r['recent_count'] for r in cur.fetchall()}

        # Compare to historical average
        cur.execute(f"""
            SELECT source_name, COUNT(*) / 7.0 as daily_avg
            FROM {schema}.articles
            WHERE created_at > NOW() - INTERVAL '7 days' AND source_name IS NOT NULL
            GROUP BY source_name
        """)
        historical = {r['source_name']: r['daily_avg'] for r in cur.fetchall()}

        for source, recent in recent_sources.items():
            hist_avg = historical.get(source, 1)
            if hist_avg > 0:
                ratio = recent / hist_avg
                if ratio > 3:  # 3x normal output
                    anomalies.append(AnomalyReport(
                        entity_type='source',
                        entity_id=0,
                        anomaly_type='unusual_activity',
                        severity='medium',
                        description=f"Source '{source}' publishing {ratio:.1f}x normal volume",
                        detected_value=float(recent),
                        expected_range=(0, hist_avg * 2),
                        supporting_evidence=[f"Historical daily avg: {hist_avg:.1f}"],
                        detected_at=datetime.now()
                    ))

        return anomalies

    def _detect_storyline_anomalies(self, cur, schema: str, cutoff: datetime, threshold: float) -> List[AnomalyReport]:
        """Detect unusual storyline growth patterns"""
        anomalies = []

        # Get storylines with rapid growth
        cur.execute(f"""
            SELECT s.id, s.title, s.article_count,
                   COUNT(sa.article_id) as recent_additions
            FROM {schema}.storylines s
            LEFT JOIN {schema}.storyline_articles sa ON s.id = sa.storyline_id
            LEFT JOIN {schema}.articles a ON sa.article_id = a.id AND a.created_at > %s
            GROUP BY s.id, s.title, s.article_count
            HAVING COUNT(sa.article_id) > 5
        """, (cutoff,))

        for row in cur.fetchall():
            total = row['article_count'] or 1
            recent = row['recent_additions']
            growth_rate = recent / total

            if growth_rate > 0.5:  # 50%+ growth in recent period
                anomalies.append(AnomalyReport(
                    entity_type='storyline',
                    entity_id=row['id'],
                    anomaly_type='rapid_growth',
                    severity='medium' if growth_rate < 1 else 'high',
                    description=f"Storyline '{row['title'][:50]}' growing rapidly: {recent} new articles ({growth_rate*100:.0f}% growth)",
                    detected_value=float(recent),
                    expected_range=(0, total * 0.3),
                    supporting_evidence=[f"Total articles: {total}", f"Growth rate: {growth_rate*100:.1f}%"],
                    detected_at=datetime.now()
                ))

        return anomalies

    # =========================================================================
    # IMPACT ASSESSMENT
    # =========================================================================

    def assess_storyline_impact(
        self,
        domain: str,
        storyline_id: int
    ) -> ImpactAssessment:
        """
        Comprehensive impact assessment for a storyline.
        Evaluates reach, significance, velocity, and potential consequences.
        """
        schema = domain.replace('-', '_')
        conn = self.get_db_connection()

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get storyline with articles
                cur.execute(f"""
                    SELECT s.*,
                           array_agg(DISTINCT a.source_name) as sources,
                           array_agg(DISTINCT a.extracted_entities) as all_entities,
                           COUNT(DISTINCT a.id) as article_count,
                           MIN(a.published_at) as first_article,
                           MAX(a.published_at) as last_article
                    FROM {schema}.storylines s
                    LEFT JOIN {schema}.storyline_articles sa ON s.id = sa.storyline_id
                    LEFT JOIN {schema}.articles a ON sa.article_id = a.id
                    WHERE s.id = %s
                    GROUP BY s.id
                """, (storyline_id,))
                storyline = cur.fetchone()

                if not storyline:
                    raise ValueError(f"Storyline {storyline_id} not found")

                # 1. Reach Score - How many sources covered it
                sources = [s for s in (storyline.get('sources') or []) if s]
                reach_score = min(len(set(sources)) / 10, 1.0)  # 10+ sources = max reach

                # 2. Significance Score - Based on entities and topic
                significance_score = self._calculate_significance(storyline)

                # 3. Velocity Score - How fast the story is developing
                velocity_score = self._calculate_velocity(storyline)

                # 4. Longevity Prediction
                longevity = self._predict_longevity(storyline, velocity_score)

                # 5. Affected Domains
                affected_domains = self._identify_affected_domains(storyline)

                # 6. Key Stakeholders
                stakeholders = self._extract_stakeholders(storyline)

                # 7. Potential Consequences (LLM-generated)
                consequences = self._predict_consequences(storyline)

                # Calculate overall impact
                overall_impact = (
                    reach_score * 0.3 +
                    significance_score * 0.35 +
                    velocity_score * 0.25 +
                    (0.1 if longevity == 'long' else 0.05 if longevity == 'medium' else 0.02)
                )

                return ImpactAssessment(
                    entity_type='storyline',
                    entity_id=storyline_id,
                    overall_impact_score=round(overall_impact, 3),
                    reach_score=round(reach_score, 3),
                    significance_score=round(significance_score, 3),
                    velocity_score=round(velocity_score, 3),
                    longevity_prediction=longevity,
                    affected_domains=affected_domains,
                    key_stakeholders=stakeholders[:10],
                    potential_consequences=consequences,
                    confidence=0.75,
                    assessed_at=datetime.now()
                )
        finally:
            conn.close()

    def _calculate_significance(self, storyline: Dict) -> float:
        """Calculate significance score based on content"""
        title = storyline.get('title', '').lower()
        description = storyline.get('description', '').lower()
        content = f"{title} {description}"

        # High-significance keywords
        high_sig = ['crisis', 'emergency', 'breaking', 'major', 'critical', 'war', 'death', 'scandal']
        med_sig = ['announce', 'policy', 'government', 'election', 'market', 'economic']

        score = 0.5  # Base score
        for word in high_sig:
            if word in content:
                score += 0.1
        for word in med_sig:
            if word in content:
                score += 0.05

        # Article count adds to significance
        article_count = storyline.get('article_count', 0) or 0
        score += min(article_count / 50, 0.3)  # Up to 0.3 for 50+ articles

        return min(score, 1.0)

    def _calculate_velocity(self, storyline: Dict) -> float:
        """Calculate how fast the story is developing"""
        first = storyline.get('first_article')
        last = storyline.get('last_article')
        count = storyline.get('article_count', 0) or 0

        if not first or not last or count < 2:
            return 0.3

        span_hours = max((last - first).total_seconds() / 3600, 1)
        articles_per_hour = count / span_hours

        # High velocity = more articles per hour
        if articles_per_hour > 2:
            return 0.9
        elif articles_per_hour > 1:
            return 0.7
        elif articles_per_hour > 0.5:
            return 0.5
        else:
            return 0.3

    def _predict_longevity(self, storyline: Dict, velocity: float) -> str:
        """Predict how long the story will remain relevant"""
        article_count = storyline.get('article_count', 0) or 0
        first = storyline.get('first_article')
        last = storyline.get('last_article')

        if not first or not last:
            return 'short'

        span_days = (last - first).days if hasattr(last - first, 'days') else 0

        # Stories that have lasted and are still active tend to continue
        if span_days > 7 and velocity > 0.5:
            return 'long'
        elif span_days > 3 or article_count > 10:
            return 'medium'
        else:
            return 'short'

    def _identify_affected_domains(self, storyline: Dict) -> List[str]:
        """Identify which domains/sectors are affected"""
        content = f"{storyline.get('title', '')} {storyline.get('description', '')}".lower()

        domains = []
        domain_keywords = {
            'politics': ['government', 'election', 'policy', 'congress', 'senate', 'president'],
            'finance': ['market', 'stock', 'economy', 'bank', 'investment', 'trade'],
            'technology': ['tech', 'ai', 'software', 'digital', 'cyber', 'innovation'],
            'healthcare': ['health', 'medical', 'hospital', 'disease', 'vaccine', 'drug'],
            'environment': ['climate', 'environment', 'pollution', 'energy', 'sustainable'],
            'international': ['foreign', 'international', 'global', 'treaty', 'diplomatic'],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in content for kw in keywords):
                domains.append(domain)

        return domains if domains else ['general']

    def _extract_stakeholders(self, storyline: Dict) -> List[str]:
        """Extract key stakeholders from storyline entities"""
        entities = storyline.get('all_entities', [])
        stakeholders = []

        for e in entities:
            if e and isinstance(e, list):
                stakeholders.extend(e)
            elif e and isinstance(e, str):
                stakeholders.append(e)

        # Return unique stakeholders
        return list(set(stakeholders))[:20]

    def _predict_consequences(self, storyline: Dict) -> List[str]:
        """Use LLM to predict potential consequences"""
        try:
            prompt = f"""Based on this news storyline, predict 3-5 potential consequences or implications:

Title: {storyline.get('title', 'Unknown')}
Description: {storyline.get('description', 'No description')}
Article Count: {storyline.get('article_count', 0)}

List potential consequences (one per line):"""

            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=30
            )

            if response.status_code == 200:
                text = response.json().get("response", "")
                lines = [l.strip().lstrip('-•').strip() for l in text.split('\n') if l.strip()]
                return lines[:5]

        except Exception as e:
            logger.error(f"Consequence prediction failed: {e}")

        return ["Unable to predict consequences"]


# Singleton instance
_intelligence_service = None


def get_intelligence_service() -> IntelligenceAnalysisService:
    """Get or create the intelligence analysis service singleton"""
    global _intelligence_service
    if _intelligence_service is None:
        _intelligence_service = IntelligenceAnalysisService()
    return _intelligence_service

