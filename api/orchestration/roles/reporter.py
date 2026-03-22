"""
Reporter role for Newsroom Orchestrator v6.

Polls DB for recently discovered articles (does not run RSS). Emits ARTICLE_INGESTED
and optionally BREAKING_NEWS. Circuit breaker: after N consecutive failures skip for K minutes.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from orchestration.events.envelope import EventEnvelope
from orchestration.events.types import EventType
from shared.domain_registry import get_active_domain_keys

logger = logging.getLogger("orchestration")

# Circuit breaker state (global)
_reporter_failures = 0
_reporter_unhealthy_until: float = 0


def _is_breaking_news(title: str, summary: str, keywords: list) -> bool:
    if not keywords:
        return False
    text = (title or "") + " " + (summary or "")
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords if kw)


def reporter_tick(
    orchestrator: Any,
    get_db_connection: Callable,
    config: dict[str, Any],
) -> None:
    """
    Poll each domain's articles for discovered_at in last N minutes; emit ARTICLE_INGESTED
    and BREAKING_NEWS. Does not run RSS.
    """
    global _reporter_failures, _reporter_unhealthy_until
    cb = config.get("circuit_breaker") or {}
    failure_threshold = cb.get("failure_threshold", 5)
    recovery_minutes = cb.get("recovery_minutes", 15)
    if _reporter_failures >= failure_threshold:
        if time.time() < _reporter_unhealthy_until:
            logger.debug("Reporter circuit breaker open, skipping tick")
            return
        _reporter_unhealthy_until = 0
        _reporter_failures = 0

    reporter_cfg = config.get("reporter") or {}
    window_minutes = reporter_cfg.get("new_article_window_minutes", 15)
    breaking_keywords = reporter_cfg.get("breaking_news_keywords") or []
    domains = list(get_active_domain_keys())

    from orchestration.plugins.rss_source import get_new_articles

    articles = get_new_articles(get_db_connection, window_minutes=window_minutes, domains=domains)
    try:
        emitted = 0
        for a in articles:
            domain_key = a["domain_key"]
            article_id = a["article_id"]
            title = a["title"]
            summary = a.get("summary", "")
            dedup = f"{domain_key}:{article_id}"
            payload = {
                "domain_key": domain_key,
                "article_id": article_id,
                "title": title,
                "summary": summary,
            }
            orchestrator.emit(
                EventEnvelope(
                    event_type=EventType.ARTICLE_INGESTED,
                    payload=payload,
                    priority=2,
                    domain=domain_key,
                    deduplication_key=dedup,
                )
            )
            emitted += 1
            if _is_breaking_news(title, summary, breaking_keywords):
                orchestrator.emit(
                    EventEnvelope(
                        event_type=EventType.BREAKING_NEWS,
                        payload=payload,
                        priority=1,
                        domain=domain_key,
                        deduplication_key=dedup,
                    )
                )
        if emitted:
            logger.info("Reporter emitted %s ARTICLE_INGESTED events", emitted)
        _reporter_failures = 0
    except Exception as e:
        _reporter_failures += 1
        logger.exception("Reporter tick failed: %s", e)
        if _reporter_failures >= failure_threshold:
            _reporter_unhealthy_until = time.time() + recovery_minutes * 60
            logger.warning("Reporter circuit breaker open for %s minutes", recovery_minutes)
