"""
Shared article read facade — cross-domain callers use this instead of importing
domains.news_aggregation.services.article_service directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def get_domain_articles(
    domain: str,
    *,
    limit: int = 50,
    offset: int = 0,
    include_content: bool = True,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return articles for a domain using the news_aggregation ArticleService."""
    from domains.news_aggregation.services.article_service import ArticleService

    svc = ArticleService(domain=domain)
    return svc.get_articles(
        limit=limit,
        offset=offset,
        include_content=include_content,
        filters=filters or {},
    )


def get_recent_domain_articles(
    domain: str,
    *,
    published_after: datetime,
    limit: int = 200,
    include_content: bool = False,
) -> list[dict[str, Any]]:
    """Convenience helper: recent articles as a plain list of dicts."""
    res = get_domain_articles(
        domain,
        limit=limit,
        offset=0,
        include_content=include_content,
        filters={"published_after": published_after},
    )
    data = res.get("data") or {}
    articles = data.get("articles") or []
    return [dict(a) for a in articles]
