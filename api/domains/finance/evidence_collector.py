"""
Evidence Collector — aggregates RSS (finance-domain articles), API summary (gold/FRED),
and RAG (finance vector store) into a single bundle for analysis prompts.
Does not replace the finance orchestrator's refresh or vector retrieval; adds RSS
(and optional API summary) so the prompt can include recent news.
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
) -> dict[str, Any]:
    """
    Collect evidence from RSS (finance-domain articles), optional API summary, optional RAG.
    Returns dict: rss_snippets, api_summary (or None), rag_chunks (or []).
    The finance orchestrator already does refresh + vector store; this adds RSS and
    optionally a short API summary for the prompt.
    """
    result: dict[str, Any] = {
        "rss_snippets": [],
        "api_summary": None,
        "rag_chunks": [],
    }

    if include_rss:
        try:
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
                r = vs_query([vec], n_results=5)
                docs = r.get("documents", [[]])[0] or []
                result["rag_chunks"] = [d for d in docs if d][:5]
        except Exception as e:
            logger.debug("Evidence collector RAG failed: %s", e)

    return result
