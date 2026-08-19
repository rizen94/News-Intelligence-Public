"""
Massachusetts / Newton local legislative stubs → chronological_events.

- MA Legislature open API (malegislature.gov) when reachable
- Newton city agendas scrape stub (graceful skip if URL unreachable)

Feature: ma_newton_collector (default off)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import requests

from collectors.public_event_upsert import (
    collector_enabled,
    rate_limit_sleep,
    stable_event_id,
    upsert_chronological_event,
)
from config.runtime import env_str

logger = logging.getLogger(__name__)

FEATURE_KEY = "ma_newton_collector"
USER_AGENT = "NewsIntelligence/1.0 (public-data-collector; local-civic)"
MA_LEGISLATURE_DOCS = "https://malegislature.gov/api/Documents"
MA_LEGISLATURE_BILLS = "https://malegislature.gov/api/Documents?DocumentTypeCode=b"
DEFAULT_NEWTON_AGENDAS_URL = (
    "https://www.newtonma.gov/government/city-clerk/city-council-agendas-minutes"
)


def _get(url: str, *, timeout: int = 30) -> requests.Response | None:
    rate_limit_sleep()
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html, */*"},
            timeout=timeout,
        )
        if r.status_code >= 400:
            logger.info("MA/Newton URL unreachable %s → HTTP %s", url, r.status_code)
            return None
        return r
    except requests.RequestException as e:
        logger.info("MA/Newton URL unreachable %s: %s", url, e)
        return None


def fetch_ma_legislature_documents(*, limit: int = 25) -> list[dict[str, Any]]:
    """Best-effort MA Legislature API; returns [] when unreachable."""
    url = (env_str("MA_LEGISLATURE_API_URL") or MA_LEGISLATURE_BILLS).strip()
    r = _get(url)
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        logger.info("MA Legislature response not JSON — skip")
        return []
    if isinstance(data, list):
        return data[:limit]
    if isinstance(data, dict):
        for key in ("value", "results", "documents", "Items"):
            if isinstance(data.get(key), list):
                return data[key][:limit]
    return []


def _ma_doc_to_event(doc: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = (
        doc.get("BillNumber")
        or doc.get("DocumentNumber")
        or doc.get("Id")
        or doc.get("id")
        or doc.get("GeneralCourtNumber")
    )
    title = doc.get("Title") or doc.get("title") or doc.get("Name")
    if not doc_id and not title:
        return None
    external = str(doc_id or title)
    filed = (
        doc.get("LastActionDate")
        or doc.get("CreatedOn")
        or doc.get("PublicationDate")
        or doc.get("date")
    )
    return {
        "event_id": stable_event_id("ma_legislature", external),
        "title": str(title or f"MA bill {doc_id}")[:500],
        "domain_key": "politics",
        "extraction_method": "ma_legislature",
        "event_type": "legislation",
        "description": str(doc.get("Summary") or doc.get("Description") or "")[:4000],
        "actual_event_date": filed,
        "importance_score": 0.4,
        "extraction_confidence": 0.7,
        "location": "Massachusetts",
        "verification_source": "malegislature.gov",
        "tags": ["ma_legislature", "massachusetts"],
        "metadata_extra": {"doc_id": external},
    }


def fetch_newton_agenda_stubs() -> list[dict[str, Any]]:
    """
    Lightweight HTML/RSS probe for Newton agendas.
    Produces stub events from linked PDFs/titles when the page is reachable.
    """
    url = (env_str("NEWTON_AGENDAS_URL") or DEFAULT_NEWTON_AGENDAS_URL).strip()
    if not url:
        return []
    r = _get(url, timeout=25)
    if r is None:
        return []
    ctype = (r.headers.get("Content-Type") or "").lower()
    text = r.text or ""
    stubs: list[dict[str, Any]] = []

    # Optional RSS/Atom
    if "xml" in ctype or text.lstrip().startswith("<?xml") or "<rss" in text[:200].lower():
        try:
            root = ElementTree.fromstring(text)
            for item in root.iter():
                tag = item.tag.lower().split("}")[-1]
                if tag not in ("item", "entry"):
                    continue
                title_el = None
                link_el = None
                date_el = None
                for child in item:
                    ctag = child.tag.lower().split("}")[-1]
                    if ctag == "title":
                        title_el = child
                    elif ctag in ("link",):
                        link_el = child
                    elif ctag in ("pubdate", "updated", "published"):
                        date_el = child
                title = (title_el.text or "").strip() if title_el is not None else ""
                href = ""
                if link_el is not None:
                    href = (link_el.get("href") or link_el.text or "").strip()
                if not title:
                    continue
                stubs.append(
                    {
                        "title": title,
                        "url": href or url,
                        "date": (date_el.text or "").strip() if date_el is not None else None,
                    }
                )
                if len(stubs) >= 15:
                    break
            return stubs
        except ElementTree.ParseError:
            pass

    # HTML: harvest agenda-looking anchors
    import re

    for m in re.finditer(
        r'href=["\']([^"\']+)["\'][^>]*>([^<]{8,200})</a>',
        text,
        flags=re.I,
    ):
        href, label = m.group(1), m.group(2).strip()
        low = f"{href} {label}".lower()
        if not any(k in low for k in ("agenda", "minutes", "council", "meeting", "packet")):
            continue
        if href.startswith("/"):
            from urllib.parse import urljoin

            href = urljoin(url, href)
        stubs.append({"title": label, "url": href, "date": None})
        if len(stubs) >= 15:
            break
    return stubs


def collect_ma_newton() -> dict[str, Any]:
    if not collector_enabled(FEATURE_KEY, env_flag="MA_NEWTON_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}

    inserted = 0
    ma_docs = fetch_ma_legislature_documents()
    for doc in ma_docs:
        if not isinstance(doc, dict):
            continue
        ev = _ma_doc_to_event(doc)
        if not ev:
            continue
        if upsert_chronological_event(**ev):
            inserted += 1

    newton_stubs = fetch_newton_agenda_stubs()
    for stub in newton_stubs:
        title = stub.get("title") or "Newton agenda"
        url = stub.get("url") or ""
        event_id = stable_event_id("newton_agenda", url or title)
        if upsert_chronological_event(
            event_id=event_id,
            title=str(title)[:500],
            domain_key="politics",
            extraction_method="newton_agenda",
            event_type="meeting",
            description=url[:2000],
            actual_event_date=stub.get("date"),
            importance_score=0.35,
            extraction_confidence=0.5,
            location="Newton, MA",
            verification_source=url or "newtonma.gov",
            source_text=url or None,
            tags=["newton", "local_government", "agenda"],
            temporal_status="unknown" if not stub.get("date") else "occurred",
            date_precision="unknown" if not stub.get("date") else "exact",
        ):
            inserted += 1

    result = {
        "skipped": False,
        "ma_docs_fetched": len(ma_docs),
        "newton_stubs_fetched": len(newton_stubs),
        "inserted": inserted,
        "ma_reachable": bool(ma_docs),
        "newton_reachable": bool(newton_stubs),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    if not ma_docs and not newton_stubs:
        result["note"] = "sources unreachable or empty — graceful no-op"
    logger.info("MA/Newton collector: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_ma_newton(), indent=2, default=str))
