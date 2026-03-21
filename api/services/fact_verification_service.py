"""
Fact verification service — multi-source corroboration, contradiction detection,
source reliability scoring, and completeness assessment.

Operates on extracted_claims, article content, and entity data to assess factual
confidence. Each claim gets a verification_status (corroborated, contested,
unverified, contradicted) with supporting evidence.

T3.3 of V6_QUALITY_FIRST_TODO.md.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}

# Minimum articles/sources needed to move from "unverified" to "corroborated"
MIN_CORROBORATION_SOURCES = 2
MIN_CORROBORATION_ARTICLES = 3

# Source reliability tiers (can be extended via config)
SOURCE_RELIABILITY_TIERS = {
    "tier_1": {
        "score": 0.95,
        "patterns": [
            "reuters", "associated press", "ap news", "bbc",
            "npr", "pbs", "c-span",
        ],
    },
    "tier_2": {
        "score": 0.85,
        "patterns": [
            "new york times", "washington post", "wall street journal",
            "financial times", "the economist", "bloomberg",
            "the guardian", "politico",
        ],
    },
    "tier_3": {
        "score": 0.70,
        "patterns": [
            "cnn", "abc news", "cbs news", "nbc news", "fox news",
            "usa today", "los angeles times",
        ],
    },
    "tier_4": {
        "score": 0.50,
        "patterns": [],  # everything else
    },
}

CONTRADICTION_PROMPT = """Analyze these two claims and determine if they contradict each other.

Claim A: {claim_a}
Claim B: {claim_b}

Respond with ONLY a JSON object:
{{"contradiction": true/false, "explanation": "brief explanation", "confidence": 0.0-1.0}}"""

COMPLETENESS_PROMPT = """Assess the completeness of coverage for this topic based on the available information.

Topic: {topic}
Number of sources: {source_count}
Number of articles: {article_count}
Key claims:
{claims_text}

Evaluate:
1. Are multiple perspectives represented?
2. Are there obvious gaps (missing context, unaddressed questions)?
3. Is the timeline of events clear?

Respond with ONLY a JSON object:
{{"completeness_score": 0.0-1.0, "perspectives_covered": ["list"], "gaps": ["list"], "assessment": "brief text"}}"""


# ---------------------------------------------------------------------------
# Source reliability scoring
# ---------------------------------------------------------------------------

def score_source_reliability(source_domain: str) -> Dict[str, Any]:
    """
    Score a source domain's reliability based on known tiers.
    Returns {score: 0.0-1.0, tier: str, source: str}.
    """
    source_lower = (source_domain or "").lower().strip()
    if not source_lower:
        return {"score": 0.3, "tier": "unknown", "source": source_domain}

    for tier_name, tier_data in SOURCE_RELIABILITY_TIERS.items():
        for pattern in tier_data["patterns"]:
            if pattern in source_lower or source_lower in pattern:
                return {
                    "score": tier_data["score"],
                    "tier": tier_name,
                    "source": source_domain,
                }

    return {"score": SOURCE_RELIABILITY_TIERS["tier_4"]["score"], "tier": "tier_4", "source": source_domain}


def score_source_reliability_batch(source_domains: List[str]) -> Dict[str, Dict[str, Any]]:
    """Score reliability for multiple sources."""
    return {s: score_source_reliability(s) for s in set(source_domains)}


# ---------------------------------------------------------------------------
# Multi-source corroboration
# ---------------------------------------------------------------------------

def corroborate_claim(
    claim_text: str,
    domain_key: str,
    hours: int = 72,
    claim_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Check if a claim is corroborated by multiple independent sources.

    Searches articles for similar content and counts distinct source_domain
    values that mention key terms from the claim.

    Returns:
    {
        status: "corroborated" | "partially_corroborated" | "unverified" | "single_source",
        source_count: int,
        article_count: int,
        sources: [{source, reliability_score, article_title}],
        confidence: 0.0-1.0,
    }
    """
    schema = DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "error": "Database connection failed"}

    try:
        # Extract key terms from claim for search
        key_terms = _extract_key_terms(claim_text)
        if not key_terms:
            conn.close()
            return {
                "status": "unverified",
                "source_count": 0,
                "article_count": 0,
                "sources": [],
                "confidence": 0.0,
                "reason": "Could not extract key terms from claim",
            }

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with conn.cursor() as cur:
            # Search for articles containing key terms
            search_query = " & ".join(f"'{t}'" for t in key_terms[:5])
            cur.execute(
                f"""
                SELECT a.id, a.title, a.source_domain, a.published_at,
                       LEFT(a.content, 500)
                FROM {schema}.articles a
                WHERE a.published_at >= %s
                  AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.content, ''))
                      @@ to_tsquery('english', %s)
                ORDER BY a.published_at DESC
                LIMIT 50
                """,
                (cutoff, search_query),
            )
            articles = cur.fetchall()

        conn.close()

        if not articles:
            return {
                "status": "unverified",
                "source_count": 0,
                "article_count": 0,
                "sources": [],
                "confidence": 0.0,
            }

        # Aggregate by source
        source_articles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for aid, title, source, pub_at, excerpt in articles:
            source_articles[source or "unknown"].append({
                "article_id": aid,
                "title": title or "",
                "published_at": pub_at.isoformat() if pub_at else None,
                "excerpt": (excerpt or "")[:200],
            })

        sources = []
        for source, arts in source_articles.items():
            rel = score_source_reliability(source)
            sources.append({
                "source": source,
                "reliability_score": rel["score"],
                "tier": rel["tier"],
                "article_count": len(arts),
                "articles": arts[:3],
            })

        sources.sort(key=lambda s: s["reliability_score"], reverse=True)
        source_count = len(sources)
        article_count = len(articles)

        # Determine status
        if source_count >= MIN_CORROBORATION_SOURCES and article_count >= MIN_CORROBORATION_ARTICLES:
            status = "corroborated"
            avg_reliability = sum(s["reliability_score"] for s in sources) / len(sources)
            confidence = min(1.0, avg_reliability * (0.5 + 0.5 * min(source_count / 5, 1.0)))
        elif source_count >= 2:
            status = "partially_corroborated"
            confidence = 0.5
        elif article_count >= 1:
            status = "single_source"
            confidence = sources[0]["reliability_score"] * 0.5 if sources else 0.3
        else:
            status = "unverified"
            confidence = 0.0

        return {
            "status": status,
            "source_count": source_count,
            "article_count": article_count,
            "sources": sources[:10],
            "confidence": round(confidence, 2),
            "key_terms_used": key_terms[:5],
        }
    except Exception as e:
        logger.warning("corroborate_claim: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


def _extract_key_terms(text: str) -> List[str]:
    """Extract significant terms from a claim for full-text search."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "has", "have", "had",
        "be", "been", "being", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "up", "about", "into", "through",
        "during", "before", "after", "above", "below", "between", "out",
        "that", "this", "these", "those", "it", "its", "he", "she", "they",
        "we", "his", "her", "their", "our", "my", "your", "and", "but",
        "or", "nor", "not", "no", "so", "if", "than", "too", "very",
        "said", "says", "according", "also", "just", "more", "some", "any",
        "other", "new", "been", "who", "which", "when", "where", "how",
    }
    words = re.findall(r"[a-zA-Z]+", text.lower())
    terms = [w for w in words if w not in stop_words and len(w) >= 3]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:10]


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------

def detect_contradictions(
    domain_key: str,
    claim_ids: Optional[List[int]] = None,
    hours: int = 48,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Find contradicting claims within a domain's recent extracted_claims.
    Groups claims by subject, then checks pairs for contradiction using
    heuristics and optionally LLM.

    Returns {contradictions: [{claim_a, claim_b, explanation, confidence}]}.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "contradictions": [], "error": "Database connection failed"}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with conn.cursor() as cur:
            if claim_ids:
                placeholders = ",".join(["%s"] * len(claim_ids))
                cur.execute(
                    f"""
                    SELECT ec.id, ec.subject_text, ec.predicate_text, ec.object_text,
                           ec.confidence, ec.context_id
                    FROM intelligence.extracted_claims ec
                    WHERE ec.id IN ({placeholders})
                    ORDER BY ec.created_at DESC
                    """,
                    tuple(claim_ids),
                )
            else:
                cur.execute(
                    """
                    SELECT ec.id, ec.subject_text, ec.predicate_text, ec.object_text,
                           ec.confidence, ec.context_id
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    WHERE c.domain_key = %s
                      AND ec.created_at >= %s
                    ORDER BY ec.created_at DESC
                    LIMIT %s
                    """,
                    (domain_key, cutoff, limit * 2),
                )
            claims = cur.fetchall()

        conn.close()

        if len(claims) < 2:
            return {"success": True, "contradictions": [], "claims_checked": len(claims)}

        # Group by subject for efficient comparison
        subject_groups: Dict[str, List[Tuple]] = defaultdict(list)
        for claim in claims:
            subject = (claim[1] or "").lower().strip()
            if subject:
                # Normalize subject for grouping
                normalized = re.sub(r"\s+", " ", subject)
                subject_groups[normalized].append(claim)

        contradictions = []

        for subject, group_claims in subject_groups.items():
            if len(group_claims) < 2:
                continue

            for i in range(len(group_claims)):
                for j in range(i + 1, len(group_claims)):
                    ca = group_claims[i]
                    cb = group_claims[j]

                    pred_a = (ca[2] or "").lower()
                    pred_b = (cb[2] or "").lower()
                    obj_a = (ca[3] or "").lower()
                    obj_b = (cb[3] or "").lower()

                    contradiction = _check_contradiction_heuristic(
                        pred_a, obj_a, pred_b, obj_b,
                    )

                    if contradiction:
                        contradictions.append({
                            "claim_a": {
                                "id": ca[0],
                                "subject": ca[1],
                                "predicate": ca[2],
                                "object": ca[3],
                                "confidence": float(ca[4]) if ca[4] else None,
                            },
                            "claim_b": {
                                "id": cb[0],
                                "subject": cb[1],
                                "predicate": cb[2],
                                "object": cb[3],
                                "confidence": float(cb[4]) if cb[4] else None,
                            },
                            "explanation": contradiction["explanation"],
                            "confidence": contradiction["confidence"],
                        })

                        if len(contradictions) >= limit:
                            break
                if len(contradictions) >= limit:
                    break
            if len(contradictions) >= limit:
                break

        return {
            "success": True,
            "contradictions": contradictions,
            "claims_checked": len(claims),
            "subjects_analyzed": len(subject_groups),
        }
    except Exception as e:
        logger.warning("detect_contradictions: %s", e)
        return {"success": False, "contradictions": [], "error": str(e)}


def _check_contradiction_heuristic(
    pred_a: str, obj_a: str,
    pred_b: str, obj_b: str,
) -> Optional[Dict[str, Any]]:
    """Heuristic contradiction detection between two claims about the same subject."""
    negation_pairs = [
        ("support", "oppose"), ("approve", "reject"), ("increase", "decrease"),
        ("rise", "fall"), ("gain", "lose"), ("win", "lose"),
        ("confirm", "deny"), ("agree", "disagree"), ("accept", "reject"),
        ("pass", "fail"), ("allow", "ban"), ("expand", "shrink"),
        ("strengthen", "weaken"), ("advance", "retreat"),
    ]

    for pos, neg in negation_pairs:
        if (pos in pred_a and neg in pred_b) or (neg in pred_a and pos in pred_b):
            return {
                "explanation": f"Opposing predicates: '{pred_a}' vs '{pred_b}'",
                "confidence": 0.8,
            }

    # Numeric contradiction: same predicate but different numbers
    nums_a = re.findall(r"\d+\.?\d*", obj_a)
    nums_b = re.findall(r"\d+\.?\d*", obj_b)
    if nums_a and nums_b and pred_a and pred_b:
        # Same verb/predicate but different numbers
        pred_words_a = set(pred_a.split())
        pred_words_b = set(pred_b.split())
        if pred_words_a & pred_words_b:
            try:
                val_a = float(nums_a[0])
                val_b = float(nums_b[0])
                if val_a != val_b and max(val_a, val_b) > 0:
                    diff_pct = abs(val_a - val_b) / max(val_a, val_b)
                    if diff_pct > 0.2:
                        return {
                            "explanation": f"Different figures: {val_a} vs {val_b} ({diff_pct:.0%} difference)",
                            "confidence": 0.6,
                        }
            except (ValueError, ZeroDivisionError):
                pass

    # Direct negation in predicate
    if "not " in pred_a and "not " not in pred_b and pred_a.replace("not ", "") == pred_b:
        return {"explanation": "Direct negation", "confidence": 0.9}
    if "not " in pred_b and "not " not in pred_a and pred_b.replace("not ", "") == pred_a:
        return {"explanation": "Direct negation", "confidence": 0.9}

    return None


# ---------------------------------------------------------------------------
# Completeness assessment
# ---------------------------------------------------------------------------

def assess_completeness(
    domain_key: str,
    topic: Optional[str] = None,
    storyline_id: Optional[int] = None,
    hours: int = 72,
) -> Dict[str, Any]:
    """
    Assess how completely a topic or storyline is covered:
    - Number of distinct sources
    - Diversity of perspectives (sentiment spread)
    - Temporal coverage (are recent developments included?)
    - Key questions answered vs. unanswered

    Returns {completeness_score, source_diversity, temporal_coverage, gaps, assessment}.
    """
    schema = DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    try:
        with conn.cursor() as cur:
            if storyline_id:
                # Articles from storyline
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at,
                           a.sentiment_score, COALESCE(a.metadata, '{{}}'::jsonb),
                           LEFT(a.content, 500)
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC
                    """,
                    (storyline_id,),
                )
            elif topic:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at,
                           a.sentiment_score, COALESCE(a.metadata, '{{}}'::jsonb),
                           LEFT(a.content, 500)
                    FROM {schema}.articles a
                    WHERE a.published_at >= %s
                      AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.content, ''))
                          @@ plainto_tsquery('english', %s)
                    ORDER BY a.published_at DESC
                    LIMIT 100
                    """,
                    (cutoff, topic),
                )
            else:
                conn.close()
                return {"success": False, "error": "Provide topic or storyline_id"}

            articles = cur.fetchall()

            # Get claims related to these articles
            article_ids = [a[0] for a in articles]
            claims = []
            if article_ids:
                cur.execute(
                    """
                    SELECT ec.subject_text, ec.predicate_text, ec.object_text, ec.confidence
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                    WHERE atc.article_id = ANY(%s)
                    ORDER BY ec.confidence DESC NULLS LAST
                    LIMIT 30
                    """,
                    (article_ids,),
                )
                for row in cur.fetchall():
                    claims.append({
                        "subject": row[0] or "",
                        "predicate": row[1] or "",
                        "object": row[2] or "",
                        "confidence": float(row[3]) if row[3] is not None else None,
                    })

        conn.close()

        if not articles:
            return {
                "success": True,
                "completeness_score": 0.0,
                "source_diversity": {"unique_sources": 0, "score": 0.0},
                "temporal_coverage": {"score": 0.0},
                "sentiment_spread": {"score": 0.0},
                "gaps": ["No articles found for this topic"],
                "assessment": "No coverage found.",
                "article_count": 0,
            }

        # Source diversity
        sources = set()
        source_reliabilities = []
        for a in articles:
            src = a[2] or "unknown"
            sources.add(src)
            source_reliabilities.append(score_source_reliability(src)["score"])

        source_count = len(sources)
        source_diversity_score = min(1.0, source_count / 5)  # 5+ sources = perfect

        # Temporal coverage: how well-spread are articles over the time window?
        dates = [a[3] for a in articles if a[3]]
        if len(dates) >= 2:
            date_range = (max(dates) - min(dates)).total_seconds()
            window_seconds = hours * 3600
            temporal_score = min(1.0, date_range / max(window_seconds * 0.5, 1))
        elif dates:
            temporal_score = 0.3
        else:
            temporal_score = 0.0

        # Sentiment spread: diverse sentiments suggest multiple perspectives
        sentiments = [float(a[4]) for a in articles if a[4] is not None]
        if len(sentiments) >= 2:
            sent_range = max(sentiments) - min(sentiments)
            sentiment_score = min(1.0, sent_range / 0.5)  # 0.5+ range = diverse
        else:
            sentiment_score = 0.3

        # Identify gaps
        gaps = []
        if source_count < 3:
            gaps.append(f"Only {source_count} source(s) — limited corroboration potential")
        if len(articles) < 5:
            gaps.append(f"Only {len(articles)} article(s) — thin coverage")
        if temporal_score < 0.3:
            gaps.append("Temporal clustering — articles concentrated in a narrow time window")
        if sentiment_score < 0.3 and len(sentiments) >= 3:
            gaps.append("Uniform sentiment — missing alternative perspectives")
        if not claims:
            gaps.append("No structured claims extracted — factual analysis limited")

        # LLM completeness assessment (optional)
        llm_assessment = None
        if topic and claims:
            llm_assessment = _llm_completeness_check(
                topic, source_count, len(articles), claims,
            )

        # Composite score
        completeness_score = (
            source_diversity_score * 0.35 +
            temporal_score * 0.25 +
            sentiment_score * 0.2 +
            (1.0 - min(len(gaps) / 5, 1.0)) * 0.2
        )

        assessment_text = llm_assessment.get("assessment", "") if llm_assessment else ""
        if not assessment_text:
            assessment_text = (
                f"Coverage from {source_count} source(s) across {len(articles)} articles. "
                f"{'Well-corroborated.' if source_count >= 3 else 'Limited source diversity.'} "
                f"{'Multiple perspectives represented.' if sentiment_score > 0.5 else 'Perspective diversity could be improved.'}"
            )

        return {
            "success": True,
            "completeness_score": round(completeness_score, 2),
            "source_diversity": {
                "unique_sources": source_count,
                "sources": list(sources),
                "average_reliability": round(sum(source_reliabilities) / len(source_reliabilities), 2) if source_reliabilities else 0,
                "score": round(source_diversity_score, 2),
            },
            "temporal_coverage": {
                "article_count": len(articles),
                "date_range_hours": round((max(dates) - min(dates)).total_seconds() / 3600, 1) if len(dates) >= 2 else 0,
                "score": round(temporal_score, 2),
            },
            "sentiment_spread": {
                "min": round(min(sentiments), 2) if sentiments else None,
                "max": round(max(sentiments), 2) if sentiments else None,
                "score": round(sentiment_score, 2),
            },
            "claims_count": len(claims),
            "gaps": gaps,
            "assessment": assessment_text,
            "llm_assessment": llm_assessment,
            "article_count": len(articles),
        }
    except Exception as e:
        logger.warning("assess_completeness: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _llm_completeness_check(
    topic: str,
    source_count: int,
    article_count: int,
    claims: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Use LLM to assess completeness (optional enhancement)."""
    claims_text = "\n".join(
        f"- {c['subject']} {c['predicate']} {c['object']}"
        for c in claims[:10]
    )

    try:
        from shared.services.llm_service import LLMService
        llm = LLMService()
        prompt = COMPLETENESS_PROMPT.format(
            topic=topic,
            source_count=source_count,
            article_count=article_count,
            claims_text=claims_text,
        )
        response = llm.generate(prompt, max_tokens=400)
        if response:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            return json.loads(cleaned)
    except Exception as e:
        logger.debug("LLM completeness check: %s", e)

    return None


# ---------------------------------------------------------------------------
# Verify a specific claim (full pipeline)
# ---------------------------------------------------------------------------

def verify_claim(
    claim_id: int,
    domain_key: str,
    hours: int = 72,
) -> Dict[str, Any]:
    """
    Full verification pipeline for a single extracted claim:
      1. Load claim from DB
      2. Run multi-source corroboration
      3. Check for contradictions with other claims about the same subject
      4. Score source reliability
      5. Return combined verification result
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, subject_text, predicate_text, object_text, confidence, context_id
                FROM intelligence.extracted_claims
                WHERE id = %s
                """,
                (claim_id,),
            )
            claim_row = cur.fetchone()
            if not claim_row:
                conn.close()
                return {"success": False, "error": f"Claim {claim_id} not found"}

            claim = {
                "id": claim_row[0],
                "subject": claim_row[1] or "",
                "predicate": claim_row[2] or "",
                "object": claim_row[3] or "",
                "confidence": float(claim_row[4]) if claim_row[4] else None,
                "context_id": claim_row[5],
            }

            # Get the article source for this claim
            source_domain = None
            cur.execute(
                """
                SELECT c.source_type, c.domain_key FROM intelligence.contexts c
                WHERE c.id = %s
                """,
                (claim["context_id"],),
            )
            ctx_row = cur.fetchone()
            if ctx_row:
                source_domain = ctx_row[0]

        conn.close()

        claim_text = f"{claim['subject']} {claim['predicate']} {claim['object']}"

        # 1. Corroboration
        corroboration = corroborate_claim(claim_text, domain_key, hours=hours, claim_id=claim_id)

        # 2. Contradictions
        contradictions = detect_contradictions(domain_key, hours=hours, limit=10)
        related_contradictions = [
            c for c in contradictions.get("contradictions", [])
            if c["claim_a"]["id"] == claim_id or c["claim_b"]["id"] == claim_id
        ]

        # 3. Source reliability
        source_reliability = score_source_reliability(source_domain or "")

        # Combined verification status
        if related_contradictions:
            verification_status = "contested"
            verification_confidence = max(
                0.3,
                corroboration.get("confidence", 0) -
                max(c["confidence"] for c in related_contradictions) * 0.3,
            )
        elif corroboration.get("status") == "corroborated":
            verification_status = "corroborated"
            verification_confidence = corroboration.get("confidence", 0.7)
        elif corroboration.get("status") == "partially_corroborated":
            verification_status = "partially_verified"
            verification_confidence = corroboration.get("confidence", 0.5)
        else:
            verification_status = "unverified"
            verification_confidence = min(
                source_reliability.get("score", 0.5) * 0.5,
                claim.get("confidence", 0.5) or 0.5,
            )

        return {
            "success": True,
            "claim": claim,
            "verification_status": verification_status,
            "verification_confidence": round(verification_confidence, 2),
            "corroboration": corroboration,
            "contradictions": related_contradictions,
            "source_reliability": source_reliability,
        }
    except Exception as e:
        logger.warning("verify_claim: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Batch verification
# ---------------------------------------------------------------------------

def verify_recent_claims(
    domain_key: str,
    hours: int = 24,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Verify the most recent high-confidence claims in a domain.
    Returns summary statistics and per-claim verification results.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ec.id
                FROM intelligence.extracted_claims ec
                JOIN intelligence.contexts c ON c.id = ec.context_id
                WHERE c.domain_key = %s
                  AND ec.created_at >= NOW() - INTERVAL '%s hours'
                  AND ec.confidence >= 0.5
                ORDER BY ec.confidence DESC, ec.created_at DESC
                LIMIT %s
                """,
                (domain_key, hours, limit),
            )
            claim_ids = [row[0] for row in cur.fetchall()]
        conn.close()

        if not claim_ids:
            return {"success": True, "claims_verified": 0, "results": []}

        results = []
        status_counts: Dict[str, int] = defaultdict(int)

        for cid in claim_ids:
            r = verify_claim(cid, domain_key, hours=hours * 3)
            status = r.get("verification_status", "error")
            status_counts[status] += 1
            results.append({
                "claim_id": cid,
                "claim_text": f"{r.get('claim', {}).get('subject', '')} {r.get('claim', {}).get('predicate', '')} {r.get('claim', {}).get('object', '')}",
                "status": status,
                "confidence": r.get("verification_confidence", 0),
                "source_count": r.get("corroboration", {}).get("source_count", 0),
                "contradiction_count": len(r.get("contradictions", [])),
            })

        return {
            "success": True,
            "claims_verified": len(results),
            "status_summary": dict(status_counts),
            "results": results,
        }
    except Exception as e:
        logger.warning("verify_recent_claims: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
