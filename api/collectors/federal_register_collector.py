"""
Federal Register API v1 documents → chronological_events (legal / politics).

No API key required. Feature: federal_register_collector (default off)
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

FEATURE_KEY = "federal_register_collector"
BASE = "https://www.federalregister.gov/api/v1/documents.json"
USER_AGENT = "NewsIntelligence/1.0 (public-data-collector)"


def fetch_documents(
    *,
    per_page: int = 50,
    term: str | None = None,
) -> list[dict[str, Any]]:
    per_page = max(1, min(100, per_page))
    params: dict[str, Any] = {
        "per_page": per_page,
        "order": "newest",
        "fields[]": [
            "document_number",
            "title",
            "type",
            "publication_date",
            "abstract",
            "html_url",
            "agencies",
            "significant",
        ],
    }
    q = (term or env_str("FEDERAL_REGISTER_SEARCH_TERM", "") or "").strip()
    if q:
        params["conditions[term]"] = q
    rate_limit_sleep()
    try:
        r = requests.get(
            BASE,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=45,
        )
        r.raise_for_status()
        return list(r.json().get("results") or [])
    except Exception as e:
        logger.warning("Federal Register fetch failed: %s", e)
        return []


def _doc_to_event(doc: dict[str, Any]) -> dict[str, Any] | None:
    doc_num = doc.get("document_number")
    if not doc_num:
        return None
    agencies = doc.get("agencies") or []
    agency_names = []
    for a in agencies:
        if isinstance(a, dict) and a.get("name"):
            agency_names.append(str(a["name"]))
        elif isinstance(a, str):
            agency_names.append(a)
    title = doc.get("title") or f"Federal Register {doc_num}"
    doc_type = (doc.get("type") or "rule").lower().replace(" ", "_")
    event_type = "policy_decision" if "rule" in doc_type or "notice" in doc_type else "legislation"
    return {
        "event_id": stable_event_id("federal_register", str(doc_num)),
        "title": str(title)[:500],
        "domain_key": "legal",
        "extraction_method": "federal_register",
        "event_type": event_type,
        "description": (doc.get("abstract") or doc.get("html_url") or "")[:4000],
        "actual_event_date": doc.get("publication_date"),
        "importance_score": 0.65 if doc.get("significant") else 0.45,
        "extraction_confidence": 0.9,
        "location": "United States",
        "verification_source": doc.get("html_url") or "federalregister.gov",
        "source_text": doc.get("html_url"),
        "tags": ["federal_register", doc_type] + agency_names[:5],
        "key_actors": [{"name": n, "role": "agency"} for n in agency_names[:8]],
        "metadata_extra": {"document_number": str(doc_num)},
    }


def collect_federal_register(
    *, per_page: int | None = None, term: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    if not collector_enabled(FEATURE_KEY, env_flag="FEDERAL_REGISTER_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}

    size = per_page if per_page is not None else env_int("FEDERAL_REGISTER_PER_PAGE", 50)
    docs = fetch_documents(per_page=size, term=term)
    if dry_run:
        return {
            "skipped": False,
            "dry_run": True,
            "fetched": len(docs),
            "inserted": 0,
            "would_insert": len(docs),
        }
    inserted = 0
    errors = 0
    for doc in docs:
        ev = _doc_to_event(doc)
        if not ev:
            errors += 1
            continue
        if upsert_chronological_event(**ev):
            inserted += 1
    logger.info(
        "Federal Register collector: fetched=%s inserted=%s errors=%s",
        len(docs),
        inserted,
        errors,
    )
    return {
        "skipped": False,
        "fetched": len(docs),
        "inserted": inserted,
        "errors": errors,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_federal_register(), indent=2, default=str))
