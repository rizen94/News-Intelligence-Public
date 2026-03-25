"""
Congress.gov API v3 — bill metadata, CRS summaries, and text version listings.

Official legislative text is the anchor for comparing media claims to statutory language.
Register for a free key: https://api.congress.gov/sign-up/

Environment: CONGRESS_GOV_API_KEY (sent as header X-API-Key).

Downstream: pair responses with ``intelligence.extracted_claims`` (subject/predicate/object)
via entity resolution + optional LLM entailment; not implemented in this module.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

CONGRESS_GOV_V3_BASE = "https://api.congress.gov/v3"
USER_AGENT = "NewsIntelligence/1.0 (https://github.com/)"
DEFAULT_TIMEOUT = 45


def congress_gov_api_key() -> str:
    return (os.environ.get("CONGRESS_GOV_API_KEY") or "").strip()


def is_congress_gov_configured() -> bool:
    return bool(congress_gov_api_key())


def _headers() -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    key = congress_gov_api_key()
    if key:
        h["X-API-Key"] = key
    return h


def congress_gov_request(
    subpath: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    GET ``/v3/{subpath}``. Returns:
    ``{"success": True, "data": <parsed JSON>}`` or
    ``{"success": False, "error": str, "status_code": int | None}``.
    """
    key = congress_gov_api_key()
    if not key:
        return {
            "success": False,
            "error": "CONGRESS_GOV_API_KEY is not set",
            "status_code": None,
        }

    path = subpath.strip().lstrip("/")
    url = f"{CONGRESS_GOV_V3_BASE}/{path}"
    try:
        r = requests.get(url, headers=_headers(), params=params or {}, timeout=timeout)
        if r.status_code == 200:
            try:
                return {"success": True, "data": r.json()}
            except ValueError as e:
                logger.warning("Congress.gov JSON parse error: %s", e)
                return {
                    "success": False,
                    "error": "Invalid JSON from Congress.gov",
                    "status_code": r.status_code,
                }
        err_txt = (r.text or "")[:500]
        return {
            "success": False,
            "error": f"Congress.gov HTTP {r.status_code}: {err_txt}",
            "status_code": r.status_code,
        }
    except requests.RequestException as e:
        logger.warning("Congress.gov request failed: %s", e)
        return {"success": False, "error": str(e), "status_code": None}


def fetch_bill(congress: int, bill_type: str, bill_number: int) -> dict[str, Any]:
    """Bill detail (metadata, titles, actions, committees, etc.)."""
    bt = (bill_type or "").strip().lower()
    return congress_gov_request(f"bill/{congress}/{bt}/{bill_number}")


def fetch_bill_summaries(congress: int, bill_type: str, bill_number: int) -> dict[str, Any]:
    """CRS-written summaries when published for the bill."""
    bt = (bill_type or "").strip().lower()
    return congress_gov_request(f"bill/{congress}/{bt}/{bill_number}/summaries")


def fetch_bill_text_versions(congress: int, bill_type: str, bill_number: int) -> dict[str, Any]:
    """List of text versions (links to full text; use ``url`` from items to retrieve HTML/PDF)."""
    bt = (bill_type or "").strip().lower()
    return congress_gov_request(f"bill/{congress}/{bt}/{bill_number}/text")


def search_bills(
    congress: int,
    *,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List/search bills within a Congress session (API path ``bill/{congress}``).
    Optional ``q`` is passed through when supported by the API for the session list.
    """
    limit = max(1, min(250, limit))
    offset = max(0, offset)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if query and query.strip():
        params["q"] = query.strip()
    return congress_gov_request(f"bill/{congress}", params=params)
