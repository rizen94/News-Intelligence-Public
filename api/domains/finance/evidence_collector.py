"""
Evidence Collector — aggregates RSS (finance-domain articles), API summary (gold/FRED),
and RAG (finance vector store) into a single bundle for analysis prompts.
Uses the news orchestrator for topic-aware shortlist when query/topic are present.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


def collect(
    query: str | None = None,
    topic: str = "gold",
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    hours: int = 168,
    max_rss: int = 15,
    include_rss: bool = True,
    include_api_summary: bool = False,
    include_rag: bool = False,
    include_historic_context: bool = False,
    historic_max_expansions: int = 1,
    use_news_orchestrator: bool = True,
) -> dict[str, Any]:
    """
    Collect evidence from RSS (finance-domain articles), optional API summary, optional RAG.
    When use_news_orchestrator is True and query or topic is set, uses the news orchestrator
    to build a topic-relevant shortlist from articles and contexts. Otherwise falls back to
    last N articles.
    When include_historic_context is True and start_date/end_date are set, runs the historic
    context orchestrator (multi-source parallel fetch, relevance + agreement) and adds
    historic_context_summary and historic_context_events to the result.
    historic_max_expansions: when > 1, allows extra time-window expansions for prior significant events (deeper context).
    Returns dict: rss_snippets, api_summary (or None), rag_chunks (or []), historic_context_summary (or None), historic_context_events (or []).
    """
    result: dict[str, Any] = {
        "rss_snippets": [],
        "api_summary": None,
        "rag_chunks": [],
        "historic_context_summary": None,
        "historic_context_events": [],
    }

    if include_rss:
        try:
            if use_news_orchestrator and (query or topic):
                from domains.finance.news_orchestrator import get_shortlist, shortlist_to_rss_snippets
                shortlist = get_shortlist(
                    query=query,
                    topic=topic,
                    hours=hours,
                    max_items=max_rss,
                    include_contexts=True,
                )
                result["rss_snippets"] = shortlist_to_rss_snippets(shortlist)
            else:
                from domains.news_aggregation.services.article_service import ArticleService
                article_svc = ArticleService(domain="finance")
                published_after = datetime.now(timezone.utc) - timedelta(hours=hours)
                res = article_svc.get_articles(
                    limit=max_rss,
                    offset=0,
                    include_content=True,
                    filters={"published_after": published_after},
                )
                articles = (res.get("data") or {}).get("articles") or []
                for a in articles:
                    snippet = (a.get("summary") or a.get("content") or "")[:400]
                    pub = a.get("published_at") or a.get("published_date")
                    result["rss_snippets"].append({
                        "id": a.get("id"),
                        "title": a.get("title") or "",
                        "snippet": snippet,
                        "published_at": pub.isoformat() if hasattr(pub, "isoformat") else str(pub) if pub else "",
                        "url": a.get("url") or "",
                    })
        except Exception as e:
            logger.warning("Evidence collector RSS fetch failed: %s", e)

    if include_api_summary:
        try:
            from domains.finance.gold_amalgamator import get_stored
            stored = get_stored(start=start_date, end=end_date)
            if stored:
                total = sum(len(obs) for obs in stored.values() if isinstance(obs, list))
                result["api_summary"] = {
                    "sources": list(stored.keys()),
                    "total_observations": total,
                    "date_range": {"start": start_date, "end": end_date},
                }
        except Exception as e:
            logger.warning("Evidence collector API summary failed: %s", e)

    if include_rag and query:
        try:
            from domains.finance.embedding import embed_text
            from domains.finance.data.vector_store import query as vs_query
            vec = embed_text(query)
            if vec:
                r = vs_query([vec], n_results=15)
                docs = r.get("documents", [[]])[0] or []
                result["rag_chunks"] = [d for d in docs if d][:15]
        except Exception as e:
            logger.debug("Evidence collector RAG failed: %s", e)

    if include_historic_context and query and start_date and end_date:
        try:
            logger.info("Fetching historic context: query=%r topic=%s range=%s to %s", query[:60], topic, start_date, end_date)
            from services.historic_context_orchestrator import run_historic_context
            h = run_historic_context(
                query=query,
                start_date=start_date,
                end_date=end_date,
                topic=topic,
                trigger_type="analysis",
                max_expansions=max(1, int(historic_max_expansions)),
            )
            if h.get("success"):
                result["historic_context_summary"] = h.get("summary")
                result["historic_context_events"] = h.get("events") or []
                logger.info("Historic context success: summary %d chars, %d events", len(h.get("summary") or ""), len(h.get("events") or []))
            else:
                logger.warning("Historic context returned success=False: %s", h.get("error", "unknown"))
        except Exception as e:
            logger.warning("Evidence collector historic context failed: %s", e)

    return result
