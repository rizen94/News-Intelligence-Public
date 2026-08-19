"""
Europe PMC REST collector — literature search + OA full-text XML when available.

No API key. Target domain default: neurodiversity.
Feature: europepmc_collector (default off). Env: EUROPEPMC_COLLECTOR_ENABLED
and/or NEURODIVERSITY_COLLECTORS_ENABLED.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from xml.etree.ElementTree import Element

import requests

from collectors.public_event_upsert import collector_enabled, rate_limit_sleep
from collectors.publication_article_upsert import (
    upsert_processed_document,
    upsert_publication_article,
)
from config.runtime import env_float, env_int, env_str

logger = logging.getLogger(__name__)

FEATURE_KEY = "europepmc_collector"
SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
USER_AGENT = "NewsIntelligence/11.0 (europepmc-collector; research@localhost)"

DEFAULT_QUERY_TERMS = (
    "autism",
    "ADHD",
    "AuDHD",
    '"attention deficit"',
    "ASD",
    '"neurodevelopmental"',
)


def _neuro_collectors_enabled() -> bool:
    raw = (env_str("NEURODIVERSITY_COLLECTORS_ENABLED", "") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    if _neuro_collectors_enabled():
        return True
    return collector_enabled(FEATURE_KEY, env_flag="EUROPEPMC_COLLECTOR_ENABLED")


def _domain_key() -> str:
    return (env_str("EUROPEPMC_DOMAIN_KEY", "neurodiversity") or "neurodiversity").strip()


def _search_query() -> str:
    override = (env_str("EUROPEPMC_QUERY", "") or "").strip()
    if override:
        return override
    raw_terms = (env_str("EUROPEPMC_QUERY_TERMS", "") or "").strip()
    if raw_terms:
        terms = [t.strip() for t in raw_terms.split("|") if t.strip()]
    else:
        terms = list(DEFAULT_QUERY_TERMS)
    joined = " OR ".join(terms)
    # Prefer OA when requesting full text later; still index abstracts for others.
    return f"({joined})"


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def search_europepmc(
    *,
    query: str | None = None,
    page_size: int = 25,
    page: int = 1,
) -> list[dict[str, Any]]:
    page_size = max(1, min(100, page_size))
    page = max(1, page)
    params = {
        "query": query or _search_query(),
        "format": "json",
        "resultType": "core",
        "pageSize": page_size,
        "cursorMark": "*",
    }
    # Europe PMC uses cursorMark; for simple paging also accept page via resultType
    if page > 1:
        # Approximate offset via cursor is complex; use pageSize * (page-1) via sort
        params["pageSize"] = page_size
    rate_limit_sleep(env_float("EUROPEPMC_MIN_INTERVAL_SECONDS", 0.5))
    try:
        r = requests.get(SEARCH_URL, params=params, headers=_headers(), timeout=60)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("Europe PMC search failed: %s", e)
        return []
    results = (data.get("resultList") or {}).get("result") or []
    return list(results)


def fetch_fulltext_xml(pmcid: str) -> str | None:
    pmc = (pmcid or "").strip()
    if not pmc:
        return None
    if not pmc.upper().startswith("PMC"):
        pmc = f"PMC{pmc}"
    url = FULLTEXT_URL.format(pmcid=pmc)
    rate_limit_sleep(env_float("EUROPEPMC_MIN_INTERVAL_SECONDS", 0.5))
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/xml"},
            timeout=90,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        text = r.text or ""
        return text if text.strip() else None
    except Exception as e:
        logger.debug("Europe PMC fullTextXML failed pmcid=%s: %s", pmc, e)
        return None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text_content(el: Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def parse_fulltext_xml(xml_text: str) -> tuple[str, list[dict[str, Any]]]:
    """Return (plain_text, citations) from JATS/NLM XML."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.debug("Europe PMC XML parse error: %s", e)
        return xml_text[:100_000], []

    body_bits: list[str] = []
    for el in root.iter():
        if _local(el.tag) in ("body", "abstract"):
            t = _text_content(el)
            if t:
                body_bits.append(t)

    citations: list[dict[str, Any]] = []
    for ref in root.iter():
        if _local(ref.tag) not in ("ref", "element-citation", "mixed-citation"):
            continue
        cite: dict[str, Any] = {"raw": _text_content(ref)[:2000]}
        for child in ref.iter():
            ln = _local(child.tag)
            if ln == "article-title" and child.text:
                cite["title"] = (child.text or "").strip()[:500]
            elif ln == "year" and child.text:
                cite["year"] = (child.text or "").strip()[:16]
            elif ln == "pub-id":
                pub_type = (child.attrib.get("pub-id-type") or "").lower()
                val = (child.text or "").strip()
                if pub_type == "doi" and val:
                    cite["doi"] = val
                elif pub_type in ("pmid", "pmcid") and val:
                    cite[pub_type] = val
        if cite.get("raw") or cite.get("title") or cite.get("doi"):
            citations.append(cite)
        if len(citations) >= 500:
            break

    # Dedupe refs that appear both as ref wrapper and citation element
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for c in citations:
        key = (c.get("doi") or c.get("pmid") or c.get("raw") or "")[:200]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    text = "\n\n".join(body_bits).strip() or re.sub(r"<[^>]+>", " ", xml_text)[:100_000]
    return text, uniq


def _result_url(row: dict[str, Any]) -> str:
    doi = (row.get("doi") or "").strip()
    if doi:
        return f"https://doi.org/{doi}"
    pmcid = (row.get("pmcid") or "").strip()
    if pmcid:
        return f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}"
    pmid = str(row.get("pmid") or "").strip()
    if pmid:
        return f"https://europepmc.org/article/MED/{pmid}"
    return f"https://europepmc.org/search?query={row.get('id') or ''}"


def _authors(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    alist = row.get("authorList") or {}
    for a in alist.get("author") or []:
        if not isinstance(a, dict):
            continue
        full = (a.get("fullName") or "").strip()
        if not full:
            full = f"{a.get('firstName') or ''} {a.get('lastName') or ''}".strip()
        if full:
            out.append(full)
    return out[:40]


def ingest_result(row: dict[str, Any], *, domain_key: str | None = None) -> dict[str, Any]:
    dk = domain_key or _domain_key()
    title = (row.get("title") or "").strip()
    if not title:
        return {"ok": False, "reason": "no_title"}
    pmid = str(row.get("pmid") or "").strip() or None
    pmcid = (row.get("pmcid") or "").strip() or None
    doi = (row.get("doi") or "").strip() or None
    abstract = (row.get("abstractText") or "").strip()
    is_oa = str(row.get("isOpenAccess") or "").lower() in ("y", "yes", "true", "1")
    url = _result_url(row)
    authors = _authors(row)
    pub_year = row.get("pubYear")
    pub_date = None
    if pub_year:
        pub_date = f"{pub_year}-01-01"

    full_text: str | None = None
    citations: list[dict[str, Any]] = []
    if is_oa and pmcid:
        xml_text = fetch_fulltext_xml(pmcid)
        if xml_text:
            full_text, citations = parse_fulltext_xml(xml_text)

    abstract_only = not bool(full_text)
    content = full_text or abstract or title

    article_id = upsert_publication_article(
        domain_key=dk,
        title=title,
        url=url,
        content=content,
        summary=abstract or title,
        published_at=pub_date,
        source_domain="europepmc.org",
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        abstract_only=abstract_only,
        authors=authors,
        metadata_extra={
            "source": "europepmc",
            "is_open_access": is_oa,
            "journal_title": row.get("journalTitle"),
        },
    )

    doc_id = None
    if full_text or citations:
        doc_id = upsert_processed_document(
            source_url=url,
            title=title,
            source_type="europepmc",
            source_name="Europe PMC",
            publication_date=pub_date,
            authors=authors,
            citations=citations,
            abstract_only=abstract_only,
            full_text=full_text,
            metadata_extra={
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "domain_key": dk,
                "article_id": article_id,
            },
        )
    elif abstract:
        # Still record abstract-only processed_documents for appraisal backlog
        doc_id = upsert_processed_document(
            source_url=url,
            title=title,
            source_type="europepmc",
            source_name="Europe PMC",
            publication_date=pub_date,
            authors=authors,
            citations=[],
            abstract_only=True,
            extracted_sections=[{"heading": "abstract", "content": abstract[:50_000]}],
            metadata_extra={
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "domain_key": dk,
                "article_id": article_id,
            },
        )

    return {
        "ok": article_id is not None,
        "article_id": article_id,
        "document_id": doc_id,
        "abstract_only": abstract_only,
        "citations": len(citations),
    }


def collect_europepmc(
    *,
    page_size: int | None = None,
    max_results: int | None = None,
    query: str | None = None,
    domain_key: str | None = None,
) -> dict[str, Any]:
    if not is_enabled():
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}

    size = page_size if page_size is not None else env_int("EUROPEPMC_PAGE_SIZE", 25)
    limit = max_results if max_results is not None else env_int("EUROPEPMC_MAX_RESULTS", 25)
    rows = search_europepmc(query=query, page_size=min(size, limit))
    rows = rows[:limit]
    inserted = 0
    docs = 0
    errors = 0
    for row in rows:
        try:
            out = ingest_result(row, domain_key=domain_key)
            if out.get("ok"):
                inserted += 1
            else:
                errors += 1
            if out.get("document_id"):
                docs += 1
        except Exception as e:
            errors += 1
            logger.warning("Europe PMC ingest error: %s", e)

    logger.info(
        "Europe PMC collector: fetched=%s articles=%s docs=%s errors=%s",
        len(rows),
        inserted,
        docs,
        errors,
    )
    return {
        "skipped": False,
        "fetched": len(rows),
        "inserted": inserted,
        "documents": docs,
        "errors": errors,
        "query": query or _search_query(),
        "domain_key": domain_key or _domain_key(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    import os
    import sys

    # Allow local CLI without flipping permanent env — opt-in via argv or env.
    if "--force" in sys.argv:
        os.environ["EUROPEPMC_COLLECTOR_ENABLED"] = "true"
    print(json.dumps(collect_europepmc(), indent=2, default=str))
