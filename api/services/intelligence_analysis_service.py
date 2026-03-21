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
import json
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

    # =========================================================================
    # ACTIONABLE KNOWLEDGE ASSEMBLERS
    # =========================================================================

    @staticmethod
    def _normalize_claim_part(value: Optional[str]) -> str:
        txt = (value or "").strip().lower()
        txt = re.sub(r"\s+", " ", txt)
        return txt

    @staticmethod
    def _extract_storyline_id_for_schema(storyline_id_raw: Optional[str], schema: str) -> Optional[int]:
        """
        storyline_id formats seen:
        - "schema:id" (preferred for tracked_events bridge)
        - "id" (legacy/plain)
        """
        if not storyline_id_raw:
            return None
        raw = str(storyline_id_raw).strip()
        if not raw:
            return None
        if ":" in raw:
            left, right = raw.split(":", 1)
            if left != schema:
                return None
            try:
                return int(right)
            except ValueError:
                return None
        try:
            return int(raw)
        except ValueError:
            return None

    def build_event_storyline_claim_consistency(
        self,
        domain: str,
        limit_events: int = 25,
        min_claim_confidence: float = 0.55,
    ) -> Dict[str, Any]:
        """
        Assemble event-storyline-claim consistency:
        - grouped contested claims (same subject+predicate, divergent objects)
        - stable facts tied to event participants
        - refresh recommendations for storyline/editorial updates
        """
        schema = domain.replace("-", "_")
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT te.id, te.event_name, te.event_type, te.storyline_id,
                           te.key_participant_entity_ids, te.updated_at
                    FROM intelligence.tracked_events te
                    WHERE te.storyline_id IS NOT NULL
                    ORDER BY te.updated_at DESC NULLS LAST, te.id DESC
                    LIMIT %s
                    """,
                    (limit_events,),
                )
                events_raw = cur.fetchall()

                event_rows: List[Dict[str, Any]] = []
                total_contested = 0
                total_claims = 0
                storyline_refresh_candidates = 0

                for ev in events_raw:
                    storyline_id = self._extract_storyline_id_for_schema(ev.get("storyline_id"), schema)
                    if storyline_id is None:
                        continue

                    # Pull context IDs from event chronicles developments JSON
                    cur.execute(
                        """
                        SELECT DISTINCT (d->>'context_id')::int AS context_id
                        FROM intelligence.event_chronicles ec
                        CROSS JOIN LATERAL jsonb_array_elements(
                            COALESCE(ec.developments, '[]'::jsonb)
                        ) d
                        WHERE ec.event_id = %s
                          AND d ? 'context_id'
                        """,
                        (ev["id"],),
                    )
                    context_ids = [r["context_id"] for r in cur.fetchall() if r.get("context_id") is not None]
                    if not context_ids:
                        continue

                    # Claims mapped to this event via chronicle contexts
                    cur.execute(
                        """
                        SELECT id, context_id, subject_text, predicate_text, object_text,
                               confidence, created_at
                        FROM intelligence.extracted_claims
                        WHERE context_id = ANY(%s)
                          AND COALESCE(confidence, 0) >= %s
                        ORDER BY created_at DESC
                        """,
                        (context_ids, min_claim_confidence),
                    )
                    claim_rows = cur.fetchall()
                    total_claims += len(claim_rows)

                    grouped: Dict[str, Dict[str, Any]] = {}
                    for claim in claim_rows:
                        subj = self._normalize_claim_part(claim.get("subject_text"))
                        pred = self._normalize_claim_part(claim.get("predicate_text"))
                        obj = self._normalize_claim_part(claim.get("object_text"))
                        if not subj or not pred:
                            continue
                        key = f"{subj}::{pred}"
                        grp = grouped.setdefault(
                            key,
                            {
                                "subject": claim.get("subject_text") or subj,
                                "predicate": claim.get("predicate_text") or pred,
                                "objects": {},
                                "claims_count": 0,
                            },
                        )
                        grp["claims_count"] += 1
                        grp["objects"][obj or ""] = grp["objects"].get(obj or "", 0) + 1

                    contested_claims: List[Dict[str, Any]] = []
                    for grp in grouped.values():
                        object_variants = [
                            {"object": o, "count": c}
                            for o, c in grp["objects"].items()
                            if o
                        ]
                        object_variants.sort(key=lambda x: x["count"], reverse=True)
                        if len(object_variants) >= 2:
                            contested_claims.append(
                                {
                                    "subject": grp["subject"],
                                    "predicate": grp["predicate"],
                                    "objects": object_variants[:5],
                                    "claims_count": grp["claims_count"],
                                }
                            )

                    total_contested += len(contested_claims)

                    # Stable facts from participants linked to the event
                    participant_ids = ev.get("key_participant_entity_ids") or []
                    if isinstance(participant_ids, str):
                        try:
                            participant_ids = json.loads(participant_ids)
                        except Exception:
                            participant_ids = []
                    participant_ids = [int(x) for x in participant_ids if isinstance(x, (int, float))]

                    stable_facts: List[Dict[str, Any]] = []
                    if participant_ids:
                        cur.execute(
                            """
                            SELECT
                                vf.entity_profile_id,
                                vf.fact_type,
                                vf.fact_text,
                                vf.confidence,
                                vf.created_at,
                                COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name') AS entity_name
                            FROM intelligence.versioned_facts vf
                            JOIN intelligence.entity_profiles ep ON ep.id = vf.entity_profile_id
                            WHERE vf.entity_profile_id = ANY(%s)
                              AND vf.superseded_by_id IS NULL
                            ORDER BY COALESCE(vf.confidence, 0) DESC, vf.created_at DESC
                            LIMIT 20
                            """,
                            (participant_ids,),
                        )
                        for r in cur.fetchall():
                            stable_facts.append(
                                {
                                    "entity_profile_id": r["entity_profile_id"],
                                    "entity_name": r.get("entity_name") or "Unknown",
                                    "fact_type": r["fact_type"],
                                    "fact_text": r["fact_text"],
                                    "confidence": float(r["confidence"]) if r.get("confidence") is not None else None,
                                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                                }
                            )

                    refresh_recommended = len(contested_claims) > 0
                    if refresh_recommended:
                        storyline_refresh_candidates += 1

                    event_rows.append(
                        {
                            "event_id": ev["id"],
                            "event_name": ev.get("event_name") or "",
                            "event_type": ev.get("event_type") or "",
                            "storyline_id": storyline_id,
                            "context_count": len(context_ids),
                            "claims_count": len(claim_rows),
                            "contested_claims": contested_claims,
                            "stable_facts": stable_facts,
                            "refresh_recommended": refresh_recommended,
                        }
                    )

                return {
                    "domain": domain,
                    "events_analyzed": len(event_rows),
                    "total_claims": total_claims,
                    "total_contested_claim_groups": total_contested,
                    "storyline_refresh_candidates": storyline_refresh_candidates,
                    "events": event_rows,
                }
        finally:
            conn.close()

    def get_participant_position_deltas(
        self,
        domain: str,
        days: int = 30,
        min_delta_records: int = 1,
    ) -> Dict[str, Any]:
        """
        Compare participant positions over time:
        1) primary from intelligence.entity_positions
        2) fallback from versioned_facts (fact_type=POSITION/STATEMENT)
        """
        schema = domain.replace("-", "_")
        domain_key = schema
        conn = self.get_db_connection()
        since = datetime.now() - timedelta(days=max(1, days))
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Focus on participants in recently updated events to keep signal high
                cur.execute(
                    """
                    SELECT DISTINCT jsonb_array_elements_text(COALESCE(key_participant_entity_ids, '[]'::jsonb))::int AS entity_profile_id
                    FROM intelligence.tracked_events
                    WHERE updated_at >= %s
                      AND key_participant_entity_ids IS NOT NULL
                    LIMIT 300
                    """,
                    (since,),
                )
                participant_ids = [r["entity_profile_id"] for r in cur.fetchall() if r.get("entity_profile_id")]

                if not participant_ids:
                    return {
                        "domain": domain,
                        "days": days,
                        "participants_analyzed": 0,
                        "participants_with_deltas": 0,
                        "deltas": [],
                    }

                # Entity names
                cur.execute(
                    """
                    SELECT id, COALESCE(metadata->>'canonical_name', metadata->>'name') AS entity_name
                    FROM intelligence.entity_profiles
                    WHERE id = ANY(%s)
                      AND domain_key = %s
                    """,
                    (participant_ids, domain_key),
                )
                name_map = {r["id"]: (r.get("entity_name") or f"Entity {r['id']}") for r in cur.fetchall()}

                deltas: List[Dict[str, Any]] = []

                # Primary: entity_positions
                for entity_id in participant_ids:
                    cur.execute(
                        """
                        SELECT topic, position, confidence, date_range, created_at
                        FROM intelligence.entity_positions
                        WHERE domain_key = %s
                          AND entity_id = %s
                          AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT 6
                        """,
                        (domain_key, entity_id, since),
                    )
                    pos_rows = cur.fetchall()
                    if len(pos_rows) >= 2:
                        latest = pos_rows[0]
                        previous = pos_rows[1]
                        changed = (latest.get("position") or "").strip() != (previous.get("position") or "").strip()
                        deltas.append(
                            {
                                "entity_profile_id": entity_id,
                                "entity_name": name_map.get(entity_id, f"Entity {entity_id}"),
                                "topic": latest.get("topic") or previous.get("topic"),
                                "latest_position": latest.get("position"),
                                "previous_position": previous.get("position"),
                                "changed": changed,
                                "confidence": float(latest["confidence"]) if latest.get("confidence") is not None else None,
                                "source": "entity_positions",
                                "latest_at": latest["created_at"].isoformat() if latest.get("created_at") else None,
                                "previous_at": previous["created_at"].isoformat() if previous.get("created_at") else None,
                            }
                        )
                        continue

                    # Fallback: versioned_facts for POSITION/STATEMENT
                    cur.execute(
                        """
                        SELECT fact_type, fact_text, confidence, created_at
                        FROM intelligence.versioned_facts
                        WHERE entity_profile_id = %s
                          AND fact_type IN ('POSITION', 'STATEMENT')
                          AND created_at >= %s
                        ORDER BY created_at DESC
                        LIMIT 6
                        """,
                        (entity_id, since),
                    )
                    fact_rows = cur.fetchall()
                    if len(fact_rows) >= 2:
                        latest = fact_rows[0]
                        previous = fact_rows[1]
                        changed = (latest.get("fact_text") or "").strip() != (previous.get("fact_text") or "").strip()
                        deltas.append(
                            {
                                "entity_profile_id": entity_id,
                                "entity_name": name_map.get(entity_id, f"Entity {entity_id}"),
                                "topic": None,
                                "latest_position": latest.get("fact_text"),
                                "previous_position": previous.get("fact_text"),
                                "changed": changed,
                                "confidence": float(latest["confidence"]) if latest.get("confidence") is not None else None,
                                "source": "versioned_facts",
                                "latest_at": latest["created_at"].isoformat() if latest.get("created_at") else None,
                                "previous_at": previous["created_at"].isoformat() if previous.get("created_at") else None,
                            }
                        )

                deltas = [d for d in deltas if d.get("changed") or min_delta_records <= 0]
                changed_count = len([d for d in deltas if d.get("changed")])
                return {
                    "domain": domain,
                    "days": days,
                    "participants_analyzed": len(participant_ids),
                    "participants_with_deltas": changed_count,
                    "deltas": deltas[:100],
                }
        finally:
            conn.close()

    def assemble_causal_chains(
        self,
        days: int = 30,
        min_strength: float = 0.5,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Build cross-domain causal chain candidates from correlation groups:
        event sequence + participant overlap + momentum.
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT correlation_id, domain_1, domain_2, event_ids, correlation_strength,
                           discovered_at
                    FROM intelligence.cross_domain_correlations
                    WHERE discovered_at >= NOW() - (%s * INTERVAL '1 day')
                      AND correlation_strength >= %s
                    ORDER BY correlation_strength DESC, discovered_at DESC
                    LIMIT %s
                    """,
                    (max(1, days), min_strength, limit),
                )
                corr_rows = cur.fetchall()

                chains: List[Dict[str, Any]] = []
                for corr in corr_rows:
                    event_ids = corr.get("event_ids") or []
                    if isinstance(event_ids, str):
                        try:
                            event_ids = json.loads(event_ids)
                        except Exception:
                            event_ids = []
                    event_ids = [int(x) for x in event_ids if isinstance(x, (int, float))]
                    if len(event_ids) < 2:
                        continue

                    cur.execute(
                        """
                        SELECT id, event_name, event_type, start_date, created_at,
                               COALESCE(domain_keys, '{}'::text[]) AS domain_keys,
                               COALESCE(key_participant_entity_ids, '[]'::jsonb) AS key_participant_entity_ids
                        FROM intelligence.tracked_events
                        WHERE id = ANY(%s)
                        """,
                        (event_ids,),
                    )
                    ev_rows = cur.fetchall()
                    if len(ev_rows) < 2:
                        continue

                    def _sort_key(r: Dict[str, Any]):
                        return r.get("start_date") or r.get("created_at") or datetime.now()

                    ev_rows.sort(key=_sort_key)
                    nodes: List[Dict[str, Any]] = []
                    for e in ev_rows:
                        participants = e.get("key_participant_entity_ids") or []
                        if isinstance(participants, str):
                            try:
                                participants = json.loads(participants)
                            except Exception:
                                participants = []
                        participants = [int(x) for x in participants if isinstance(x, (int, float))]
                        nodes.append(
                            {
                                "event_id": e["id"],
                                "event_name": e.get("event_name") or "",
                                "event_type": e.get("event_type") or "",
                                "date": str(e.get("start_date") or "") or (
                                    e["created_at"].isoformat() if e.get("created_at") else None
                                ),
                                "domains": list(e.get("domain_keys") or []),
                                "participant_entity_profile_ids": participants[:20],
                            }
                        )

                    edges: List[Dict[str, Any]] = []
                    for i in range(len(nodes) - 1):
                        a = nodes[i]
                        b = nodes[i + 1]
                        overlap = set(a.get("participant_entity_profile_ids") or []) & set(
                            b.get("participant_entity_profile_ids") or []
                        )
                        reason_parts = []
                        if overlap:
                            reason_parts.append(f"shared_participants={len(overlap)}")
                        if set(a.get("domains") or []) != set(b.get("domains") or []):
                            reason_parts.append("cross_domain_transition")
                        reason_parts.append("temporal_sequence")
                        edges.append(
                            {
                                "from_event_id": a["event_id"],
                                "to_event_id": b["event_id"],
                                "confidence": round(
                                    min(
                                        1.0,
                                        float(corr.get("correlation_strength") or 0.0)
                                        + (0.1 if overlap else 0.0),
                                    ),
                                    3,
                                ),
                                "reason": ", ".join(reason_parts),
                            }
                        )

                    chains.append(
                        {
                            "correlation_id": str(corr["correlation_id"]),
                            "domains": [corr.get("domain_1"), corr.get("domain_2")],
                            "strength": float(corr.get("correlation_strength") or 0.0),
                            "discovered_at": corr["discovered_at"].isoformat() if corr.get("discovered_at") else None,
                            "nodes": nodes,
                            "edges": edges,
                        }
                    )

                return {
                    "days": days,
                    "min_strength": min_strength,
                    "chains_count": len(chains),
                    "chains": chains,
                }
        finally:
            conn.close()

    def build_narrative_divergence_map(
        self,
        domain: str,
        event_id: int,
        min_contexts_per_cluster: int = 1,
    ) -> Dict[str, Any]:
        """
        Side-by-side narrative framing for a tracked event:
        groups contexts by source cluster and extracts framing signals.
        """
        schema = domain.replace("-", "_")
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, event_name, event_type, geographic_scope, start_date
                    FROM intelligence.tracked_events
                    WHERE id = %s
                    """,
                    (event_id,),
                )
                event_row = cur.fetchone()
                if not event_row:
                    raise ValueError(f"Tracked event {event_id} not found")

                cur.execute(
                    """
                    SELECT DISTINCT (d->>'context_id')::int AS context_id
                    FROM intelligence.event_chronicles ec
                    CROSS JOIN LATERAL jsonb_array_elements(
                        COALESCE(ec.developments, '[]'::jsonb)
                    ) d
                    WHERE ec.event_id = %s
                      AND d ? 'context_id'
                    """,
                    (event_id,),
                )
                context_ids = [r["context_id"] for r in cur.fetchall() if r.get("context_id") is not None]
                if not context_ids:
                    return {
                        "event_id": event_id,
                        "event_name": event_row.get("event_name"),
                        "clusters": [],
                        "message": "No contexts linked to this event yet",
                    }

                cur.execute(
                    f"""
                    SELECT
                        c.id AS context_id,
                        c.title,
                        c.content,
                        c.metadata,
                        a.id AS article_id,
                        COALESCE(a.source_name, a.source_domain, c.metadata->>'source_name', c.metadata->>'source_domain', 'unknown') AS source_label
                    FROM intelligence.contexts c
                    LEFT JOIN intelligence.article_to_context a2c ON a2c.context_id = c.id
                    LEFT JOIN {schema}.articles a ON a.id = a2c.article_id
                    WHERE c.id = ANY(%s)
                    """,
                    (context_ids,),
                )
                rows = cur.fetchall()

                clusters: Dict[str, Dict[str, Any]] = {}
                token_stop = {
                    "the", "and", "for", "with", "from", "that", "this", "were", "have", "has",
                    "will", "into", "their", "about", "after", "before", "while", "where", "when",
                    "said", "says", "over", "under", "more", "than", "they", "them", "been",
                }
                for r in rows:
                    source = (r.get("source_label") or "unknown").strip().lower()
                    source = re.sub(r"^www\.", "", source)
                    key = source[:80] or "unknown"
                    cluster = clusters.setdefault(
                        key,
                        {
                            "source_cluster": key,
                            "context_ids": [],
                            "headlines": [],
                            "entity_terms": Counter(),
                            "framing_terms": Counter(),
                        },
                    )
                    cluster["context_ids"].append(r["context_id"])
                    if r.get("title"):
                        cluster["headlines"].append(r["title"])

                    text = (r.get("content") or "")[:3000].lower()
                    tokens = re.findall(r"[a-z][a-z\-]{3,}", text)
                    for t in tokens:
                        if t in token_stop:
                            continue
                        cluster["framing_terms"][t] += 1

                # Entity framing terms by source cluster
                cur.execute(
                    """
                    SELECT
                        cem.context_id,
                        COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name') AS entity_name
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.entity_profiles ep ON ep.id = cem.entity_profile_id
                    WHERE cem.context_id = ANY(%s)
                    """,
                    (context_ids,),
                )
                context_to_cluster = {}
                for ckey, cval in clusters.items():
                    for cid in cval["context_ids"]:
                        context_to_cluster[cid] = ckey
                for rr in cur.fetchall():
                    cid = rr.get("context_id")
                    ename = (rr.get("entity_name") or "").strip()
                    if not cid or not ename:
                        continue
                    ckey = context_to_cluster.get(cid)
                    if ckey and ckey in clusters:
                        clusters[ckey]["entity_terms"][ename] += 1

                cluster_rows = []
                for c in clusters.values():
                    if len(c["context_ids"]) < min_contexts_per_cluster:
                        continue
                    cluster_rows.append(
                        {
                            "source_cluster": c["source_cluster"],
                            "context_count": len(c["context_ids"]),
                            "context_ids": c["context_ids"][:30],
                            "sample_headlines": c["headlines"][:5],
                            "entity_framing_terms": [
                                {"term": n, "count": cnt}
                                for n, cnt in c["entity_terms"].most_common(10)
                            ],
                            "lexical_framing_terms": [
                                {"term": n, "count": cnt}
                                for n, cnt in c["framing_terms"].most_common(15)
                            ],
                        }
                    )

                cluster_rows.sort(key=lambda x: x["context_count"], reverse=True)
                return {
                    "event_id": event_id,
                    "event_name": event_row.get("event_name"),
                    "event_type": event_row.get("event_type"),
                    "geographic_scope": event_row.get("geographic_scope"),
                    "start_date": str(event_row.get("start_date")) if event_row.get("start_date") else None,
                    "clusters": cluster_rows,
                    "contexts_total": len(context_ids),
                }
        finally:
            conn.close()

    def build_watchlist_theme_trigger_bridge(
        self,
        domain: str,
        create_alerts: bool = False,
        max_items: int = 25,
    ) -> Dict[str, Any]:
        """
        Bridge watched storylines to emerging themes/events and optionally create alerts.
        """
        schema = domain.replace("-", "_")
        domain_key = schema
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Watchlist seeds (storyline + core entity names)
                cur.execute(
                    """
                    SELECT w.id AS watchlist_id, w.storyline_id, COALESCE(s.title, '') AS storyline_title
                    FROM watchlist w
                    LEFT JOIN storylines s ON s.id = w.storyline_id
                    ORDER BY w.updated_at DESC NULLS LAST, w.created_at DESC
                    LIMIT %s
                    """,
                    (max_items,),
                )
                watch_rows = cur.fetchall()
                if not watch_rows:
                    return {"domain": domain, "triggers": [], "alerts_created": 0}

                storyline_ids = [r["storyline_id"] for r in watch_rows]
                cur.execute(
                    """
                    SELECT storyline_id, entity_name
                    FROM story_entity_index
                    WHERE storyline_id = ANY(%s)
                      AND is_core_entity = TRUE
                    """,
                    (storyline_ids,),
                )
                entities_by_story: Dict[int, List[str]] = {}
                for r in cur.fetchall():
                    sid = r["storyline_id"]
                    entities_by_story.setdefault(sid, []).append((r.get("entity_name") or "").strip())

                # Trending themes from topic clusters (recent)
                cur.execute(
                    f"""
                    SELECT tc.id, tc.cluster_name, COUNT(atc.article_id) AS article_count
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON atc.topic_cluster_id = tc.id
                    GROUP BY tc.id, tc.cluster_name
                    HAVING COUNT(atc.article_id) > 0
                    ORDER BY article_count DESC, tc.id DESC
                    LIMIT 100
                    """
                )
                themes = cur.fetchall()

                # Recent events for domain
                cur.execute(
                    """
                    SELECT id, event_name, event_type, key_participant_entity_ids, domain_keys
                    FROM intelligence.tracked_events
                    WHERE updated_at >= NOW() - INTERVAL '14 days'
                    ORDER BY updated_at DESC
                    LIMIT 200
                    """
                )
                events = cur.fetchall()

                # Build participant name lookup
                participant_ids = set()
                for ev in events:
                    pids = ev.get("key_participant_entity_ids") or []
                    if isinstance(pids, str):
                        try:
                            pids = json.loads(pids)
                        except Exception:
                            pids = []
                    for pid in pids:
                        if isinstance(pid, (int, float)):
                            participant_ids.add(int(pid))
                participant_name = {}
                if participant_ids:
                    cur.execute(
                        """
                        SELECT id, COALESCE(metadata->>'canonical_name', metadata->>'name') AS entity_name
                        FROM intelligence.entity_profiles
                        WHERE id = ANY(%s)
                          AND domain_key = %s
                        """,
                        (list(participant_ids), domain_key),
                    )
                    participant_name = {r["id"]: (r.get("entity_name") or "").lower() for r in cur.fetchall()}

                triggers = []
                alerts_created = 0
                for w in watch_rows:
                    sid = w["storyline_id"]
                    seed_entities = [e for e in entities_by_story.get(sid, []) if e]
                    seed_lower = {e.lower() for e in seed_entities}
                    if not seed_lower:
                        continue

                    matched_themes = []
                    for t in themes:
                        tname = (t.get("cluster_name") or "").lower()
                        if not tname:
                            continue
                        if any(se in tname or tname in se for se in seed_lower):
                            matched_themes.append(
                                {"theme_id": t["id"], "theme_name": t["cluster_name"], "article_count": int(t["article_count"] or 0)}
                            )

                    matched_events = []
                    for ev in events:
                        # domain guard if domain_keys exists
                        dks = ev.get("domain_keys") or []
                        if isinstance(dks, str):
                            try:
                                dks = json.loads(dks)
                            except Exception:
                                dks = []
                        if dks and domain_key not in list(dks):
                            continue

                        ename = (ev.get("event_name") or "").lower()
                        pids = ev.get("key_participant_entity_ids") or []
                        if isinstance(pids, str):
                            try:
                                pids = json.loads(pids)
                            except Exception:
                                pids = []
                        pnames = {participant_name.get(int(pid), "") for pid in pids if isinstance(pid, (int, float))}
                        if any(se in ename for se in seed_lower) or (seed_lower & pnames):
                            matched_events.append(
                                {"event_id": ev["id"], "event_name": ev.get("event_name"), "event_type": ev.get("event_type")}
                            )

                    if not matched_themes and not matched_events:
                        continue

                    trigger = {
                        "watchlist_id": w["watchlist_id"],
                        "storyline_id": sid,
                        "storyline_title": w.get("storyline_title") or "",
                        "seed_entities": seed_entities[:12],
                        "matched_themes": matched_themes[:10],
                        "matched_events": matched_events[:10],
                        "impact_score": len(matched_themes) * 0.6 + len(matched_events) * 1.0,
                    }
                    triggers.append(trigger)

                    if create_alerts:
                        cur.execute(
                            """
                            INSERT INTO watchlist_alerts (watchlist_id, storyline_id, alert_type, title, body)
                            VALUES (%s, %s, 'pattern_match', %s, %s)
                            """,
                            (
                                w["watchlist_id"],
                                sid,
                                f"Watchlist impacted by emerging themes ({domain})",
                                f"Matched {len(matched_themes)} themes and {len(matched_events)} tracked events for watched storyline.",
                            ),
                        )
                        alerts_created += 1

                if create_alerts and alerts_created:
                    conn.commit()
                elif create_alerts:
                    conn.rollback()

                triggers.sort(key=lambda x: x["impact_score"], reverse=True)
                return {
                    "domain": domain,
                    "triggers": triggers[:max_items],
                    "alerts_created": alerts_created,
                }
        except Exception:
            if create_alerts:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            conn.close()

    def build_document_intelligence_integration(
        self,
        domain: str,
        days: int = 30,
        persist_links: bool = False,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """
        Attach processed PDF document contexts to active themes and event chains.
        Optionally persists storyline/event links into intelligence.document_intelligence.
        """
        schema = domain.replace("-", "_")
        domain_key = schema
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, title, source_name, source_url, publication_date, entities_mentioned, key_findings
                    FROM intelligence.processed_documents
                    WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (max(1, days), limit),
                )
                docs = cur.fetchall()
                if not docs:
                    return {"domain": domain, "documents": [], "links_persisted": 0}

                # Event participants (recent)
                cur.execute(
                    """
                    SELECT id, event_name, event_type, key_participant_entity_ids, domain_keys
                    FROM intelligence.tracked_events
                    WHERE updated_at >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY updated_at DESC
                    LIMIT 300
                    """,
                    (max(1, days),),
                )
                events = cur.fetchall()
                participant_ids = set()
                for ev in events:
                    pids = ev.get("key_participant_entity_ids") or []
                    if isinstance(pids, str):
                        try:
                            pids = json.loads(pids)
                        except Exception:
                            pids = []
                    for pid in pids:
                        if isinstance(pid, (int, float)):
                            participant_ids.add(int(pid))
                profile_to_name = {}
                if participant_ids:
                    cur.execute(
                        """
                        SELECT id, COALESCE(metadata->>'canonical_name', metadata->>'name') AS name
                        FROM intelligence.entity_profiles
                        WHERE id = ANY(%s)
                          AND domain_key = %s
                        """,
                        (list(participant_ids), domain_key),
                    )
                    profile_to_name = {r["id"]: (r.get("name") or "").lower() for r in cur.fetchall()}

                # Theme lookup map (cluster_name)
                cur.execute(
                    f"""
                    SELECT tc.id, tc.cluster_name, COUNT(atc.article_id) AS article_count
                    FROM {schema}.topic_clusters tc
                    LEFT JOIN {schema}.article_topic_clusters atc ON atc.topic_cluster_id = tc.id
                    GROUP BY tc.id, tc.cluster_name
                    HAVING COUNT(atc.article_id) > 0
                    ORDER BY article_count DESC
                    LIMIT 200
                    """
                )
                themes = cur.fetchall()
                theme_names = [(t["id"], (t.get("cluster_name") or "").lower(), int(t.get("article_count") or 0), t.get("cluster_name")) for t in themes]

                links_persisted = 0
                out_docs = []
                for d in docs:
                    doc_id = d["id"]
                    cur.execute(
                        """
                        SELECT c.id AS context_id, c.content
                        FROM intelligence.contexts c
                        WHERE c.source_type = 'pdf_section'
                          AND c.domain_key = %s
                          AND c.metadata->>'document_id' = %s
                        """,
                        (domain_key, str(doc_id)),
                    )
                    crows = cur.fetchall()
                    context_ids = [r["context_id"] for r in crows]

                    # entity mentions from document contexts
                    profile_ids = []
                    if context_ids:
                        cur.execute(
                            """
                            SELECT DISTINCT cem.entity_profile_id
                            FROM intelligence.context_entity_mentions cem
                            WHERE cem.context_id = ANY(%s)
                            """,
                            (context_ids,),
                        )
                        profile_ids = [r["entity_profile_id"] for r in cur.fetchall()]
                    profile_set = set(profile_ids)

                    # related events by participant overlap
                    related_events = []
                    for ev in events:
                        dks = ev.get("domain_keys") or []
                        if isinstance(dks, str):
                            try:
                                dks = json.loads(dks)
                            except Exception:
                                dks = []
                        if dks and domain_key not in list(dks):
                            continue
                        pids = ev.get("key_participant_entity_ids") or []
                        if isinstance(pids, str):
                            try:
                                pids = json.loads(pids)
                            except Exception:
                                pids = []
                        epids = {int(x) for x in pids if isinstance(x, (int, float))}
                        overlap = len(profile_set & epids)
                        if overlap > 0:
                            related_events.append(
                                {
                                    "event_id": ev["id"],
                                    "event_name": ev.get("event_name"),
                                    "event_type": ev.get("event_type"),
                                    "participant_overlap": overlap,
                                }
                            )
                    related_events.sort(key=lambda x: x["participant_overlap"], reverse=True)

                    # related themes by matching theme names to entities/findings/content
                    tokens = set()
                    entities = d.get("entities_mentioned") or []
                    if isinstance(entities, str):
                        try:
                            entities = json.loads(entities)
                        except Exception:
                            entities = []
                    for e in entities:
                        if isinstance(e, str):
                            tokens.add(e.lower())
                    findings = d.get("key_findings") or []
                    if isinstance(findings, str):
                        try:
                            findings = json.loads(findings)
                        except Exception:
                            findings = []
                    for f in findings:
                        if isinstance(f, str):
                            tokens.update(re.findall(r"[a-z][a-z\-]{3,}", f.lower()))
                    for r in crows:
                        txt = (r.get("content") or "")[:1500].lower()
                        tokens.update(re.findall(r"[a-z][a-z\-]{4,}", txt))

                    related_themes = []
                    for tid, tnorm, acount, tlabel in theme_names:
                        if not tnorm:
                            continue
                        if any(tok in tnorm or tnorm in tok for tok in list(tokens)[:300]):
                            related_themes.append({"theme_id": tid, "theme_name": tlabel, "article_count": acount})
                    related_themes = related_themes[:12]

                    storyline_connections = []
                    for ev in related_events[:8]:
                        storyline_connections.append(
                            {
                                "event_id": ev["event_id"],
                                "event_name": ev["event_name"],
                                "participant_overlap": ev["participant_overlap"],
                            }
                        )
                    for th in related_themes[:8]:
                        storyline_connections.append(
                            {"theme_id": th["theme_id"], "theme_name": th["theme_name"], "source": "theme_match"}
                        )

                    if persist_links:
                        cur.execute(
                            """
                            UPDATE intelligence.document_intelligence
                            SET storyline_connections = %s,
                                impact_assessment = %s,
                                created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                            WHERE document_id = %s
                            """,
                            (
                                json.dumps(storyline_connections),
                                f"Auto-linked to {len(related_events)} events and {len(related_themes)} themes",
                                doc_id,
                            ),
                        )
                        if cur.rowcount == 0:
                            cur.execute(
                                """
                                INSERT INTO intelligence.document_intelligence (
                                    document_id, storyline_connections, impact_assessment
                                )
                                VALUES (%s, %s, %s)
                                """,
                                (
                                    doc_id,
                                    json.dumps(storyline_connections),
                                    f"Auto-linked to {len(related_events)} events and {len(related_themes)} themes",
                                ),
                            )
                        links_persisted += 1

                    out_docs.append(
                        {
                            "document_id": doc_id,
                            "title": d.get("title"),
                            "source_name": d.get("source_name"),
                            "source_url": d.get("source_url"),
                            "context_count": len(context_ids),
                            "related_events": related_events[:12],
                            "related_themes": related_themes,
                        }
                    )

                if persist_links:
                    conn.commit()

                return {
                    "domain": domain,
                    "documents": out_docs,
                    "links_persisted": links_persisted,
                }
        except Exception:
            if persist_links:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            conn.close()


# Singleton instance
_intelligence_service = None


def get_intelligence_service() -> IntelligenceAnalysisService:
    """Get or create the intelligence analysis service singleton"""
    global _intelligence_service
    if _intelligence_service is None:
        _intelligence_service = IntelligenceAnalysisService()
    return _intelligence_service

