"""
News orchestrator — topic-aware shortlist from finance articles, contexts, and disclosures.
Parses query/topic to score and rank news, RSS-derived articles, and intelligence contexts
so analysis gets a relevant shortlist in addition to price data.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

# Terms that must match as whole words to avoid false positives (e.g. "gold" vs "Goldman Sachs")
WORD_BOUNDARY_TERMS: frozenset[str] = frozenset({"gold"})

# Topic -> search terms (for scoring relevance)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "gold": ["gold", "bullion", "precious metal", "yellow metal", "ounce", "oz"],
    "silver": ["silver", "precious metal", "industrial metal", "ounce", "oz"],
    "platinum": ["platinum", "pgm", "palladium", "precious metal", "catalyst", "automotive"],
    "edgar": ["sec", "filing", "10-k", "disclosure", "earnings", "mining"],
    "fred": ["fed", "federal reserve", "inflation", "rate", "gdp", "employment"],
    "all": ["gold", "silver", "platinum", "commodity", "precious metal", "market", "mining"],
}


def _terms_for_topic_and_query(topic: str, query: str | None) -> set[str]:
    """Build set of lowercase terms for scoring: topic keywords + words from query."""
    terms = set()
    topic_lower = (topic or "").lower()
    for t in TOPIC_KEYWORDS.get(topic_lower, []):
        terms.add(t)
    if topic_lower and topic_lower not in terms:
        terms.add(topic_lower)
    if query:
        for word in re.findall(r"[a-z0-9]+", query.lower()):
            if len(word) >= 2:
                terms.add(word)
    return terms


def _term_matches(text: str, term: str, topic: str | None = None) -> bool:
    """True if term appears in text. Terms in WORD_BOUNDARY_TERMS match as whole word only (e.g. gold vs Goldman Sachs)."""
    if not text or not term:
        return False
    lower = text.lower()
    if topic and term in WORD_BOUNDARY_TERMS:
        return bool(re.search(r"\b" + re.escape(term) + r"\b", lower))
    if " " in term:
        return term in lower
    return term in lower


def _score_text(text: str, terms: set[str], topic: str | None = None) -> float:
    """Score text by number of term matches (case-insensitive). topic used for word-boundary rules (e.g. gold vs Goldman)."""
    if not text or not terms:
        return 0.0
    return sum(1 for t in terms if _term_matches(text, t, topic))


def is_relevant_to_commodity(text: str | None, commodity: str) -> bool:
    """
    Return True if text (e.g. event_name) is relevant to the given commodity.
    Uses TOPIC_KEYWORDS for gold/silver/platinum; "gold" matches as whole word only
    so "Goldman Sachs" is not treated as gold-the-metal.
    """
    if not text or not commodity:
        return False
    topic_lower = commodity.lower()
    if topic_lower not in TOPIC_KEYWORDS:
        return True
    terms = set(TOPIC_KEYWORDS[topic_lower])
    return _score_text(text, terms, topic=topic_lower) >= 1


def get_shortlist(
    query: str | None = None,
    topic: str = "gold",
    *,
    hours: int = 168,
    max_items: int = 20,
    include_contexts: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch finance articles and optionally contexts, score by topic/query relevance,
    return a shortlist of items for the analysis prompt.
    Each item: { "id", "title", "snippet", "url", "source", "published_at" }.
    """
    terms = _terms_for_topic_and_query(topic, query)
    shortlist: list[tuple[float, dict[str, Any]]] = []

    # 1) Finance-domain articles (RSS-derived)
    try:
        from domains.news_aggregation.services.article_service import ArticleService
        article_svc = ArticleService(domain="finance")
        published_after = datetime.now(timezone.utc) - timedelta(hours=hours)
        res = article_svc.get_articles(
            limit=150,
            offset=0,
            include_content=True,
            filters={"published_after": published_after},
        )
        articles = (res.get("data") or {}).get("articles") or []
        for a in articles:
            title = (a.get("title") or "")[:500]
            content = a.get("content") or a.get("summary") or ""
            snippet = (content or title)[:400]
            pub = a.get("published_at") or a.get("published_date")
            published_at = pub.isoformat() if hasattr(pub, "isoformat") else str(pub) if pub else ""
            score = _score_text(title, terms, topic=topic) * 2.0 + _score_text(snippet, terms, topic=topic)
            shortlist.append((score, {
                "id": a.get("id"),
                "title": title,
                "snippet": snippet,
                "url": a.get("url") or "",
                "source": a.get("source_domain") or a.get("source") or "finance",
                "published_at": published_at,
            }))
    except Exception as e:
        logger.warning("News orchestrator articles fetch failed: %s", e)

    # 2) Intelligence contexts (finance domain) — reporting/disclosures summarized as contexts
    if include_contexts and terms:
        try:
            from shared.database.connection import get_db_connection
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, title, content, created_at
                        FROM intelligence.contexts
                        WHERE domain_key = 'finance'
                          AND created_at >= NOW() - make_interval(hours => %s)
                        ORDER BY created_at DESC
                        LIMIT 100
                        """,
                        (max(hours, 24),),
                    )
                    rows = cur.fetchall()
                conn.close()
                for row in rows:
                    ctx_id, title, content, created_at = row
                    title = (title or "")[:500]
                    snippet = (content or "")[:400]
                    score = _score_text(title, terms, topic=topic) * 2.0 + _score_text(snippet, terms, topic=topic)
                    shortlist.append((score, {
                        "id": f"ctx-{ctx_id}",
                        "title": title,
                        "snippet": snippet,
                        "url": "",
                        "source": "context",
                        "published_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else "",
                    }))
        except Exception as e:
            logger.debug("News orchestrator contexts fetch failed: %s", e)

    # Sort by score descending and take top max_items
    shortlist.sort(key=lambda x: -x[0])
    out = [item for _, item in shortlist[:max_items]]
    if terms and shortlist:
        logger.info("News orchestrator shortlist: topic=%s terms=%d items=%d top_score=%.0f",
                    topic, len(terms), len(out), shortlist[0][0] if shortlist else 0)
    return out


def shortlist_to_rss_snippets(shortlist: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert shortlist to the rss_snippets shape expected by evidence collector / prompt."""
    return [
        {
            "id": s.get("id"),
            "title": s.get("title", ""),
            "snippet": s.get("snippet", ""),
            "published_at": s.get("published_at", ""),
            "url": s.get("url", ""),
        }
        for s in shortlist
    ]
