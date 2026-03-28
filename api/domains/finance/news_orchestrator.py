"""
News orchestrator — topic-aware shortlist from finance articles, contexts, and disclosures.
Parses query/topic to score and rank news, RSS-derived articles, and intelligence contexts
so analysis gets a relevant shortlist in addition to price data.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import finance_intelligence_context_domain_key

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

# Fallback when topic is not in commodity registry (edgar, fred, all)
WORD_BOUNDARY_TERMS_FALLBACK: frozenset[str] = frozenset({"gold"})
TOPIC_KEYWORDS_FALLBACK: dict[str, list[str]] = {
    "gold": ["gold", "bullion", "precious metal", "yellow metal", "ounce", "oz"],
    "silver": ["silver", "precious metal", "industrial metal", "ounce", "oz"],
    "platinum": ["platinum", "pgm", "palladium", "precious metal", "catalyst", "automotive"],
    "edgar": ["sec", "filing", "10-k", "disclosure", "earnings", "mining"],
    "fred": ["fed", "federal reserve", "inflation", "rate", "gdp", "employment"],
    "all": ["gold", "silver", "platinum", "commodity", "precious metal", "market", "mining"],
}


def _get_topic_keywords(topic: str) -> list[str]:
    """Topic keywords from registry if commodity, else fallback dict."""
    cid = (topic or "").lower()
    try:
        from domains.finance.commodity_registry import get_commodity_ids
        from domains.finance.commodity_registry import get_topic_keywords as reg_keywords

        if cid in [x.lower() for x in get_commodity_ids()]:
            kw = reg_keywords(cid)
            if kw:
                return kw
    except Exception:
        pass
    return TOPIC_KEYWORDS_FALLBACK.get(cid, []) if cid else []


def _get_word_boundary_terms(topic: str) -> frozenset[str]:
    """Word-boundary terms from registry if commodity, else fallback."""
    try:
        from domains.finance.commodity_registry import get_commodity_ids
        from domains.finance.commodity_registry import get_word_boundary_terms as reg_boundary

        cid = (topic or "").lower()
        if cid in [x.lower() for x in get_commodity_ids()]:
            terms = reg_boundary(cid)
            if terms:
                return frozenset(terms)
    except Exception:
        pass
    return WORD_BOUNDARY_TERMS_FALLBACK


def _terms_for_topic_and_query(topic: str, query: str | None) -> set[str]:
    """Build set of lowercase terms for scoring: topic keywords + words from query."""
    terms = set()
    topic_lower = (topic or "").lower()
    for t in _get_topic_keywords(topic_lower):
        terms.add(t)
    if topic_lower and topic_lower not in terms:
        terms.add(topic_lower)
    if query:
        for word in re.findall(r"[a-z0-9]+", query.lower()):
            if len(word) >= 2:
                terms.add(word)
    return terms


# Words immediately before "oil …" that indicate non–crude-oil meaning (cooking, cosmetics, etc.)
_OIL_NON_ENERGY_PREFIX_WORDS: frozenset[str] = frozenset(
    {
        "cooking",
        "olive",
        "motor",
        "essential",
        "vegetable",
        "coconut",
        "fish",
        "hemp",
        "palm",
        "seed",
        "canola",
        "sunflower",
        "linseed",
    }
)


def _anchor_term_matches(
    text: str, anchor: str, *, commodity: str | None = None
) -> bool:
    """
    Single token: whole word only. Multi-word phrase: bounded match so
    'oil price' is not a prefix match inside 'oil prices' unless the anchor is that phrase.

    For commodity ``oil``, phrases starting with ``oil `` (except ``crude oil``) are rejected
    when the word immediately before the phrase is a non-energy oil (e.g. cooking, olive).
    """
    a = (anchor or "").strip().lower()
    if not a or not text:
        return False
    lower = text.lower()
    if " " in a:
        pattern = r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])"
        m = re.search(pattern, lower)
        if not m:
            return False
        if (
            (commodity or "").lower() == "oil"
            and a.startswith("oil ")
            and a != "crude oil"
        ):
            window = lower[max(0, m.start() - 60) : m.start()]
            words = re.findall(r"[a-z]+", window)
            if words and words[-1] in _OIL_NON_ENERGY_PREFIX_WORDS:
                return False
        return True
    return bool(re.search(r"\b" + re.escape(a) + r"\b", lower))


def _term_matches(text: str, term: str, topic: str | None = None) -> bool:
    """True if term appears in text. Terms in word_boundary set match as whole word only (e.g. gold vs Goldman Sachs)."""
    if not text or not term:
        return False
    lower = text.lower()
    boundary = _get_word_boundary_terms(topic or "")
    if topic and term in boundary:
        return bool(re.search(r"\b" + re.escape(term) + r"\b", lower))
    if " " in term:
        return term in lower
    return term in lower


def _score_text(text: str, terms: set[str], topic: str | None = None) -> float:
    """Score text by number of term matches (case-insensitive). topic used for word-boundary rules (e.g. gold vs Goldman)."""
    if not text or not terms:
        return 0.0
    return sum(1 for t in terms if _term_matches(text, t, topic))


def _matches_non_financial_exclude(text: str | None, commodity: str) -> bool:
    """True if text matches any non_financial_exclude phrase/keyword for this commodity (registry only)."""
    if not text or not commodity:
        return False
    try:
        from domains.finance.commodity_registry import get_commodity_ids, get_non_financial_exclude

        cid = (commodity or "").lower()
        if cid not in [x.lower() for x in get_commodity_ids()]:
            return False
        exclude_list = get_non_financial_exclude(cid)
        if not exclude_list:
            return False
        lower = text.lower()
        for phrase in exclude_list:
            if phrase and phrase.lower() in lower:
                return True
    except Exception:
        pass
    return False


def _financial_score(text: str | None, commodity: str) -> float:
    """Count of financial_signals present in text (registry commodities only)."""
    if not text or not commodity:
        return 0.0
    try:
        from domains.finance.commodity_registry import get_commodity_ids, get_financial_signals

        cid = (commodity or "").lower()
        if cid not in [x.lower() for x in get_commodity_ids()]:
            return 0.0
        signals = get_financial_signals(cid)
        if not signals:
            return 0.0
        lower = text.lower()
        return sum(1 for s in signals if s and s.lower() in lower)
    except Exception:
        return 0.0


def is_relevant_to_commodity(text: str | None, commodity: str) -> bool:
    """
    Return True if text (e.g. event_name, article body) is relevant to the given commodity.
    For registry commodities with relevance_anchors, at least one anchor must match (stops
    silver/copper stories from matching gold via shared terms like 'ounce' or 'precious metal').
    Otherwise uses topic_keywords + word_boundary scoring.
    """
    if not text or not commodity:
        return False
    topic_lower = (commodity or "").lower()
    try:
        from domains.finance.commodity_registry import get_commodity_ids, get_relevance_anchors

        in_registry = topic_lower in [x.lower() for x in get_commodity_ids()]
        if in_registry:
            anchors = get_relevance_anchors(topic_lower)
            if anchors:
                return any(
                    _anchor_term_matches(text, a, commodity=topic_lower) for a in anchors
                )
    except Exception:
        pass
    terms = set(_get_topic_keywords(topic_lower))
    if not terms:
        return True
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
    topic_lower = (topic or "").lower()
    try:
        from domains.finance.commodity_registry import get_commodity_ids

        is_registry_commodity = topic_lower in [x.lower() for x in get_commodity_ids()]
    except Exception:
        is_registry_commodity = False

    # 1) Finance-domain articles (RSS-derived) — FINANCE_PG_CONTENT_DOMAIN_KEY selects silo (finance vs finance-2)
    try:
        from config.settings import finance_postgres_content_domain_key
        from domains.news_aggregation.services.article_service import ArticleService

        fin_dk = finance_postgres_content_domain_key()
        article_svc = ArticleService(domain=fin_dk)
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
            combined = f"{title} {snippet}"
            if is_registry_commodity and not is_relevant_to_commodity(combined, topic_lower):
                continue
            if is_registry_commodity and _matches_non_financial_exclude(combined, topic_lower):
                continue
            topic_score = _score_text(title, terms, topic=topic) * 2.0 + _score_text(
                snippet, terms, topic=topic
            )
            financial = _financial_score(combined, topic_lower)
            if is_registry_commodity and topic_score >= 1 and financial < 1:
                continue
            score = topic_score * 2.0 + financial
            pub = a.get("published_at") or a.get("published_date")
            published_at = pub.isoformat() if hasattr(pub, "isoformat") else str(pub) if pub else ""
            shortlist.append(
                (
                    score,
                    {
                        "id": a.get("id"),
                        "title": title,
                        "snippet": snippet,
                        "url": a.get("url") or "",
                        "source": a.get("source_domain") or a.get("source") or fin_dk,
                        "published_at": published_at,
                    },
                )
            )
    except Exception as e:
        logger.warning("News orchestrator articles fetch failed: %s", e)

    # 2) Intelligence contexts (finance domain) — reporting/disclosures summarized as contexts
    if include_contexts and terms:
        try:
            from shared.database.connection import get_db_connection

            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    ctx_dk = finance_intelligence_context_domain_key()
                    cur.execute(
                        """
                        SELECT id, title, content, created_at
                        FROM intelligence.contexts
                        WHERE domain_key = %s
                          AND created_at >= NOW() - make_interval(hours => %s)
                        ORDER BY created_at DESC
                        LIMIT 100
                        """,
                        (ctx_dk, max(hours, 24)),
                    )
                    rows = cur.fetchall()
                conn.close()
                for row in rows:
                    ctx_id, title, content, created_at = row
                    title = (title or "")[:500]
                    snippet = (content or "")[:400]
                    combined = f"{title} {snippet}"
                    if is_registry_commodity and not is_relevant_to_commodity(
                        combined, topic_lower
                    ):
                        continue
                    if is_registry_commodity and _matches_non_financial_exclude(
                        combined, topic_lower
                    ):
                        continue
                    topic_score = _score_text(title, terms, topic=topic) * 2.0 + _score_text(
                        snippet, terms, topic=topic
                    )
                    financial = _financial_score(combined, topic_lower)
                    if is_registry_commodity and topic_score >= 1 and financial < 1:
                        continue
                    score = topic_score * 2.0 + financial
                    shortlist.append(
                        (
                            score,
                            {
                                "id": f"ctx-{ctx_id}",
                                "title": title,
                                "snippet": snippet,
                                "url": "",
                                "source": "context",
                                "published_at": created_at.isoformat()
                                if hasattr(created_at, "isoformat")
                                else str(created_at)
                                if created_at
                                else "",
                            },
                        )
                    )
        except Exception as e:
            logger.debug("News orchestrator contexts fetch failed: %s", e)

    # Sort by score descending and take top max_items
    shortlist.sort(key=lambda x: -x[0])
    out = [item for _, item in shortlist[:max_items]]
    if terms and shortlist:
        logger.info(
            "News orchestrator shortlist: topic=%s terms=%d items=%d top_score=%.0f",
            topic,
            len(terms),
            len(out),
            shortlist[0][0] if shortlist else 0,
        )
    return out


def get_supply_chain_items(
    commodity: str,
    *,
    hours: int = 168,
    max_items: int = 15,
) -> list[dict[str, Any]]:
    """
    Fetch finance-domain contexts (EDGAR, mining, supply-chain) relevant to the commodity.
    Same relevance rules as get_shortlist: topic + financial signals, exclude non-financial.
    Returns list of { id, title, snippet, url, source, published_at }.
    """
    topic_lower = (commodity or "").lower()
    terms = _terms_for_topic_and_query(topic_lower, None)
    try:
        from domains.finance.commodity_registry import get_commodity_ids

        is_registry_commodity = topic_lower in [x.lower() for x in get_commodity_ids()]
    except Exception:
        is_registry_commodity = False
    shortlist: list[tuple[float, dict[str, Any]]] = []
    try:
        from config.settings import finance_intelligence_context_domain_key
        from shared.database.connection import get_db_connection

        ctx_dk = finance_intelligence_context_domain_key()
        conn = get_db_connection()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, content, created_at
                FROM intelligence.contexts
                WHERE domain_key = %s
                  AND created_at >= NOW() - make_interval(hours => %s)
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (ctx_dk, max(hours, 24)),
            )
            rows = cur.fetchall()
        conn.close()
        for row in rows:
            ctx_id, title, content, created_at = row
            title = (title or "")[:500]
            snippet = (content or "")[:400]
            combined = f"{title} {snippet}"
            if is_registry_commodity and not is_relevant_to_commodity(combined, topic_lower):
                continue
            if is_registry_commodity and _matches_non_financial_exclude(combined, topic_lower):
                continue
            topic_score = _score_text(title, terms, topic=topic_lower) * 2.0 + _score_text(
                snippet, terms, topic=topic_lower
            )
            financial = _financial_score(combined, topic_lower)
            if is_registry_commodity and topic_score >= 1 and financial < 1:
                continue
            score = topic_score * 2.0 + financial
            shortlist.append(
                (
                    score,
                    {
                        "id": f"ctx-{ctx_id}",
                        "title": title,
                        "snippet": snippet,
                        "url": "",
                        "source": "context",
                        "published_at": created_at.isoformat()
                        if hasattr(created_at, "isoformat")
                        else str(created_at)
                        if created_at
                        else "",
                    },
                )
            )
    except Exception as e:
        logger.debug("Supply chain contexts fetch failed: %s", e)
        return []
    shortlist.sort(key=lambda x: -x[0])
    return [item for _, item in shortlist[:max_items]]


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
