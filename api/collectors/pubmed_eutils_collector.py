"""
NCBI PubMed E-utilities collector (esearch + efetch).

Maps MeSH PublicationType → study_design via shared.evidence_grade.
Feature: pubmed_eutils_collector (default off).
Env: PUBMED_EUTILS_COLLECTOR_ENABLED and/or NEURODIVERSITY_COLLECTORS_ENABLED;
optional NCBI_EMAIL / NCBI_API_KEY.
"""

from __future__ import annotations

import logging
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
from shared.evidence_grade import mesh_publication_type_to_study_design

logger = logging.getLogger(__name__)

FEATURE_KEY = "pubmed_eutils_collector"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
USER_AGENT = "NewsIntelligence/11.0 (pubmed-eutils; research@localhost)"

DEFAULT_TERM = (
    '(autism OR ADHD OR AuDHD OR "attention deficit" OR ASD OR neurodiversity)'
    "[Title/Abstract]"
)


def _neuro_collectors_enabled() -> bool:
    raw = (env_str("NEURODIVERSITY_COLLECTORS_ENABLED", "") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    if _neuro_collectors_enabled():
        return True
    return collector_enabled(FEATURE_KEY, env_flag="PUBMED_EUTILS_COLLECTOR_ENABLED")


def _domain_key() -> str:
    return (env_str("PUBMED_DOMAIN_KEY", "neurodiversity") or "neurodiversity").strip()


def _search_term() -> str:
    return (env_str("PUBMED_EUTILS_TERM", "") or "").strip() or DEFAULT_TERM


def _ncbi_params() -> dict[str, str]:
    params: dict[str, str] = {}
    email = (env_str("NCBI_EMAIL", "") or "").strip()
    api_key = (env_str("NCBI_API_KEY", "") or "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/xml"}


def _interval() -> float:
    # With API key NCBI allows ~10 rps; without ~3 rps. Stay polite.
    if (env_str("NCBI_API_KEY", "") or "").strip():
        return env_float("PUBMED_EUTILS_MIN_INTERVAL_SECONDS", 0.12)
    return env_float("PUBMED_EUTILS_MIN_INTERVAL_SECONDS", 0.4)


def esearch_pmids(
    *,
    term: str | None = None,
    retmax: int = 25,
) -> list[str]:
    retmax = max(1, min(200, retmax))
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": term or _search_term(),
        "retmax": retmax,
        "retmode": "json",
        "sort": "pub_date",
        **_ncbi_params(),
    }
    rate_limit_sleep(_interval())
    try:
        r = requests.get(
            ESEARCH,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("PubMed esearch failed: %s", e)
        return []
    idlist = ((data.get("esearchresult") or {}).get("idlist")) or []
    return [str(x) for x in idlist]


def efetch_pubmed_xml(pmids: list[str]) -> str | None:
    if not pmids:
        return None
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        **_ncbi_params(),
    }
    rate_limit_sleep(_interval())
    try:
        r = requests.get(EFETCH, params=params, headers=_headers(), timeout=90)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.warning("PubMed efetch failed: %s", e)
        return None


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_text(parent: Element, path_locals: tuple[str, ...]) -> str:
    """Best-effort nested text by local tag names."""
    nodes: list[Element] = [parent]
    for name in path_locals:
        next_nodes: list[Element] = []
        for n in nodes:
            for child in list(n):
                if _local(child.tag) == name:
                    next_nodes.append(child)
        nodes = next_nodes
        if not nodes:
            return ""
    return "".join(nodes[0].itertext()).strip()


def parse_pubmed_articles(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("PubMed XML parse error: %s", e)
        return []

    articles: list[dict[str, Any]] = []
    for art in root.iter():
        if _local(art.tag) != "PubmedArticle":
            continue
        pmid = ""
        for el in art.iter():
            if _local(el.tag) == "PMID" and (el.text or "").strip():
                pmid = (el.text or "").strip()
                break
        title = _find_text(art, ("ArticleTitle",)) or _find_text(
            art, ("MedlineCitation", "Article", "ArticleTitle")
        )
        if not title:
            # walk
            for el in art.iter():
                if _local(el.tag) == "ArticleTitle":
                    title = "".join(el.itertext()).strip()
                    break
        abstract_parts: list[str] = []
        for el in art.iter():
            if _local(el.tag) == "AbstractText":
                t = "".join(el.itertext()).strip()
                if t:
                    abstract_parts.append(t)
        abstract = "\n\n".join(abstract_parts)

        doi = None
        pmcid = None
        for el in art.iter():
            if _local(el.tag) == "ArticleId":
                id_type = (el.attrib.get("IdType") or "").lower()
                val = (el.text or "").strip()
                if id_type == "doi" and val:
                    doi = val
                elif id_type == "pmc" and val:
                    pmcid = val if val.upper().startswith("PMC") else f"PMC{val}"

        pub_types: list[str] = []
        for el in art.iter():
            if _local(el.tag) == "PublicationType" and (el.text or "").strip():
                pub_types.append((el.text or "").strip())

        study_design = "unknown"
        for pt in pub_types:
            mapped = mesh_publication_type_to_study_design(pt)
            if mapped != "unknown":
                study_design = mapped
                # Prefer strongest: meta/systematic/rct over weaker
                if mapped in ("meta_analysis", "systematic_review", "rct"):
                    break

        authors: list[str] = []
        for el in art.iter():
            if _local(el.tag) != "Author":
                continue
            last = ""
            fore = ""
            collective = ""
            for child in list(el):
                ln = _local(child.tag)
                if ln == "LastName":
                    last = (child.text or "").strip()
                elif ln == "ForeName":
                    fore = (child.text or "").strip()
                elif ln == "CollectiveName":
                    collective = (child.text or "").strip()
            name = collective or f"{fore} {last}".strip()
            if name:
                authors.append(name)

        year = ""
        for el in art.iter():
            if _local(el.tag) == "PubDate":
                for child in list(el):
                    if _local(child.tag) == "Year" and (child.text or "").strip():
                        year = (child.text or "").strip()
                        break
                break

        # Reference list (when present in MedlineCitation)
        citations: list[dict[str, Any]] = []
        for el in art.iter():
            if _local(el.tag) != "Reference":
                continue
            cite: dict[str, Any] = {}
            for child in el.iter():
                ln = _local(child.tag)
                if ln == "Citation" and child.text:
                    cite["raw"] = (child.text or "").strip()[:2000]
                elif ln == "ArticleId":
                    id_type = (child.attrib.get("IdType") or "").lower()
                    val = (child.text or "").strip()
                    if id_type == "doi":
                        cite["doi"] = val
                    elif id_type == "pubmed":
                        cite["pmid"] = val
            if cite:
                citations.append(cite)
            if len(citations) >= 500:
                break

        if not pmid and not title:
            continue
        articles.append(
            {
                "pmid": pmid,
                "pmcid": pmcid,
                "doi": doi,
                "title": title or f"PMID {pmid}",
                "abstract": abstract,
                "authors": authors[:40],
                "pub_types": pub_types,
                "study_design": study_design,
                "year": year,
                "citations": citations,
            }
        )
    return articles


def ingest_article(row: dict[str, Any], *, domain_key: str | None = None) -> dict[str, Any]:
    dk = domain_key or _domain_key()
    pmid = str(row.get("pmid") or "").strip() or None
    title = (row.get("title") or "").strip()
    if not title:
        return {"ok": False, "reason": "no_title"}
    doi = (row.get("doi") or None)
    pmcid = (row.get("pmcid") or None)
    abstract = (row.get("abstract") or "").strip()
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (
        f"https://doi.org/{doi}" if doi else ""
    )
    if not url:
        return {"ok": False, "reason": "no_url"}

    pub_date = f"{row['year']}-01-01" if row.get("year") else None
    # PubMed efetch rarely includes full text; abstract_only unless PMC full text later.
    abstract_only = True
    study_design = row.get("study_design") or "unknown"
    citations = list(row.get("citations") or [])

    article_id = upsert_publication_article(
        domain_key=dk,
        title=title,
        url=url,
        content=abstract or title,
        summary=abstract or title,
        published_at=pub_date,
        source_domain="pubmed.ncbi.nlm.nih.gov",
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        abstract_only=abstract_only,
        authors=list(row.get("authors") or []),
        study_design=study_design,
        metadata_extra={
            "source": "pubmed_eutils",
            "publication_types": row.get("pub_types") or [],
        },
    )

    doc_id = None
    if abstract or citations:
        doc_id = upsert_processed_document(
            source_url=url,
            title=title,
            source_type="pubmed",
            source_name="PubMed",
            publication_date=pub_date,
            authors=list(row.get("authors") or []),
            citations=citations,
            abstract_only=True,
            extracted_sections=(
                [{"heading": "abstract", "content": abstract[:50_000]}] if abstract else []
            ),
            metadata_extra={
                "doi": doi,
                "pmid": pmid,
                "pmcid": pmcid,
                "domain_key": dk,
                "article_id": article_id,
                "study_design": study_design,
                "publication_types": row.get("pub_types") or [],
            },
        )

    return {
        "ok": article_id is not None,
        "article_id": article_id,
        "document_id": doc_id,
        "study_design": study_design,
        "abstract_only": abstract_only,
    }


def collect_pubmed_eutils(
    *,
    retmax: int | None = None,
    term: str | None = None,
    domain_key: str | None = None,
) -> dict[str, Any]:
    if not is_enabled():
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}

    limit = retmax if retmax is not None else env_int("PUBMED_EUTILS_RETMAX", 25)
    pmids = esearch_pmids(term=term, retmax=limit)
    if not pmids:
        return {
            "skipped": False,
            "fetched": 0,
            "inserted": 0,
            "errors": 0,
            "term": term or _search_term(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    # Batch efetch in chunks of 50
    inserted = 0
    docs = 0
    errors = 0
    parsed_total = 0
    chunk_size = 50
    for i in range(0, len(pmids), chunk_size):
        chunk = pmids[i : i + chunk_size]
        xml_text = efetch_pubmed_xml(chunk)
        if not xml_text:
            errors += len(chunk)
            continue
        rows = parse_pubmed_articles(xml_text)
        parsed_total += len(rows)
        for row in rows:
            try:
                out = ingest_article(row, domain_key=domain_key)
                if out.get("ok"):
                    inserted += 1
                else:
                    errors += 1
                if out.get("document_id"):
                    docs += 1
            except Exception as e:
                errors += 1
                logger.warning("PubMed ingest error: %s", e)

    logger.info(
        "PubMed eutils collector: pmids=%s parsed=%s articles=%s docs=%s errors=%s",
        len(pmids),
        parsed_total,
        inserted,
        docs,
        errors,
    )
    return {
        "skipped": False,
        "fetched": len(pmids),
        "parsed": parsed_total,
        "inserted": inserted,
        "documents": docs,
        "errors": errors,
        "term": term or _search_term(),
        "domain_key": domain_key or _domain_key(),
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json
    import os
    import sys

    if "--force" in sys.argv:
        os.environ["PUBMED_EUTILS_COLLECTOR_ENABLED"] = "true"
    print(json.dumps(collect_pubmed_eutils(), indent=2, default=str))
