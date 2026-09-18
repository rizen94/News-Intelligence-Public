"""
CourtListener REST v4 — recent opinions → chronological_events (legal).

Env: COURTLISTENER_API_TOKEN (Authorization: Token …)
Feature: courtlistener_collector (default off)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from collectors.public_event_upsert import (
    collector_enabled,
    rate_limit_sleep,
    stable_event_id,
    upsert_chronological_event,
)
from config.runtime import env_int, env_str

logger = logging.getLogger(__name__)

FEATURE_KEY = "courtlistener_collector"
BASE = "https://www.courtlistener.com/api/rest/v4"
USER_AGENT = "NewsIntelligence/1.0 (public-data-collector)"


def _token() -> str:
    return (env_str("COURTLISTENER_API_TOKEN") or "").strip()


def _headers() -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Token {tok}"
    return h


def fetch_recent_opinions(*, page_size: int = 20, pages: int = 1) -> list[dict[str, Any]]:
    """Search recent case-law opinions (type=o), newest first."""
    if not _token():
        logger.info("COURTLISTENER_API_TOKEN unset — skip CourtListener fetch")
        return []
    page_size = max(1, min(100, page_size))
    pages = max(1, min(5, pages))
    out: list[dict[str, Any]] = []
    url = f"{BASE}/search/"
    params: dict[str, Any] = {
        "type": "o",
        "order_by": "dateFiled desc",
        "page_size": page_size,
    }
    for _ in range(pages):
        rate_limit_sleep(env_int("COURTLISTENER_MIN_INTERVAL_MS", 1200) / 1000.0)
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=45)
            if r.status_code == 429:
                logger.warning("CourtListener rate limited")
                break
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.warning("CourtListener fetch failed: %s", e)
            break
        results = data.get("results") or []
        if not results:
            break
        out.extend(results)
        next_url = data.get("next")
        if not next_url:
            break
        url = next_url
        params = {}
    return out


def _opinion_to_event(row: dict[str, Any]) -> dict[str, Any] | None:
    cluster_id = row.get("cluster_id") or row.get("id") or row.get("opinion_id")
    if cluster_id is None:
        return None
    title = (
        row.get("caseName")
        or row.get("caseNameFull")
        or row.get("absolute_url")
        or f"CourtListener opinion {cluster_id}"
    )
    filed = row.get("dateFiled") or row.get("date_filed") or row.get("dateArgued")
    court = row.get("court") or row.get("court_id") or ""
    snippet = row.get("snippet") or row.get("text") or ""
    abs_url = row.get("absolute_url") or ""
    if abs_url and abs_url.startswith("/"):
        abs_url = f"https://www.courtlistener.com{abs_url}"
    event_id = stable_event_id("courtlistener", str(cluster_id))
    return {
        "event_id": event_id,
        "title": str(title)[:500],
        "domain_key": "legal",
        "extraction_method": "courtlistener",
        "event_type": "court_ruling",
        "description": (snippet or abs_url or "")[:4000],
        "actual_event_date": filed,
        "importance_score": 0.55,
        "extraction_confidence": 0.8,
        "location": str(court)[:200] if court else None,
        "verification_source": abs_url or "courtlistener",
        "source_text": abs_url or None,
        "tags": ["courtlistener", "legal", str(court)[:40]] if court else ["courtlistener", "legal"],
        "metadata_extra": {"cluster_id": str(cluster_id)},
    }


def collect_courtlistener(
    *,
    page_size: int | None = None,
    pages: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not collector_enabled(FEATURE_KEY, env_flag="COURTLISTENER_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}
    if not _token():
        return {"skipped": True, "reason": "COURTLISTENER_API_TOKEN not set", "inserted": 0}

    size = page_size if page_size is not None else env_int("COURTLISTENER_PAGE_SIZE", 20)
    n_pages = pages if pages is not None else env_int("COURTLISTENER_PAGES", 1)
    rows = fetch_recent_opinions(page_size=size, pages=n_pages)
    if dry_run:
        return {
            "skipped": False,
            "dry_run": True,
            "fetched": len(rows),
            "inserted": 0,
            "would_insert": len(rows),
        }
    inserted = 0
    errors = 0
    for row in rows:
        ev = _opinion_to_event(row)
        if not ev:
            errors += 1
            continue
        if upsert_chronological_event(**ev):
            inserted += 1
    logger.info(
        "CourtListener collector: fetched=%s inserted=%s errors=%s",
        len(rows),
        inserted,
        errors,
    )
    return {
        "skipped": False,
        "fetched": len(rows),
        "inserted": inserted,
        "errors": errors,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_courtlistener(), indent=2, default=str))
