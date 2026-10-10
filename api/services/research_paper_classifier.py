"""
Domain-agnostic scientific paper classifier.

Stamps article metadata:
  content_kind=research_paper, paper_host, preprint_id / arxiv_id / doi when known.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

CONTENT_KIND_RESEARCH_PAPER = "research_paper"

# Preprint / academic hosts (hostname suffix match).
_PREPRINT_HOSTS = (
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "chemrxiv.org",
    "psyarxiv.com",
    "osf.io",
    "ssrn.com",
    "researchsquare.com",
    "preprints.org",
    "eartharxiv.org",
    "techrxiv.org",
    "hal.science",
    "hal.archives-ouvertes.fr",
)

_ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html|ps)/(?:arxiv[:/])?|arxiv:)\s*([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)",
    re.I,
)
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
_PUBMED_RE = re.compile(r"(?:pubmed\.ncbi\.nlm\.nih\.gov/\d+|ncbi\.nlm\.nih\.gov/pubmed/\d+)", re.I)


def _host(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _host_is_preprint(host: str) -> str | None:
    if not host:
        return None
    for h in _PREPRINT_HOSTS:
        if host == h or host.endswith("." + h):
            return h
    return None


def extract_arxiv_id(url: str | None, text: str | None = None) -> str | None:
    blob = f"{url or ''} {text or ''}"
    m = _ARXIV_ID_RE.search(blob)
    return m.group(1) if m else None


def extract_doi(url: str | None, text: str | None = None) -> str | None:
    blob = f"{url or ''} {text or ''}"
    m = _DOI_RE.search(blob)
    return m.group(0).rstrip(").,;") if m else None


def classify_research_paper(
    url: str | None,
    *,
    source_domain: str | None = None,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Return metadata fragment to merge when the URL/source looks like a scientific paper.
    None when not a paper.
    """
    if metadata and (metadata.get("content_kind") or "").strip().lower() == CONTENT_KIND_RESEARCH_PAPER:
        # Already classified — refresh ids if missing
        out = {"content_kind": CONTENT_KIND_RESEARCH_PAPER}
        if metadata.get("paper_host"):
            out["paper_host"] = metadata["paper_host"]
        aid = metadata.get("arxiv_id") or extract_arxiv_id(url)
        if aid:
            out["arxiv_id"] = aid
            out["preprint_id"] = metadata.get("preprint_id") or f"arxiv:{aid}"
        doi = metadata.get("doi") or extract_doi(url)
        if doi:
            out["doi"] = doi
        return out

    host = _host(url)
    paper_host = _host_is_preprint(host)
    src = (source_domain or "").lower()
    title_l = (title or "").lower()

    is_paper = bool(paper_host)
    if not is_paper and host and (
        "ieee.org" in host
        or "acm.org" in host
        or "springer" in host
        or "nature.com" in host
        or "science.org" in host
        or "plos.org" in host
        or "frontiersin.org" in host
        or "mdpi.com" in host
        or "sciencedirect.com" in host
        or "wiley.com" in host
        or "nih.gov" in host
    ):
        # Journal / publisher pages — treat as paper when URL looks like article DOI path
        if extract_doi(url) or "/doi/" in (url or "").lower() or "/articles/" in (url or "").lower():
            is_paper = True
            paper_host = host
    if not is_paper and _PUBMED_RE.search(url or ""):
        is_paper = True
        paper_host = "pubmed.ncbi.nlm.nih.gov"
    if not is_paper and ("arxiv" in src or "biorxiv" in src or "medrxiv" in src or "pubmed" in src):
        is_paper = True
        paper_host = paper_host or host or "unknown-preprint"
    if not is_paper and metadata and str(metadata.get("document_type") or "").lower() == "paper":
        is_paper = True
        paper_host = paper_host or host or "document"

    if not is_paper:
        return None

    out: dict[str, Any] = {
        "content_kind": CONTENT_KIND_RESEARCH_PAPER,
        "paper_host": paper_host or host or "unknown",
        "pipeline_skip": {
            "event_extraction_skip": True,
            "claim_extraction_skip": True,
        },
    }
    arxiv_id = extract_arxiv_id(url, title)
    if arxiv_id:
        out["arxiv_id"] = arxiv_id
        out["preprint_id"] = f"arxiv:{arxiv_id}"
    doi = extract_doi(url, title)
    if doi:
        out["doi"] = doi
    return out


def is_research_paper_metadata(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    return (metadata.get("content_kind") or "").strip().lower() == CONTENT_KIND_RESEARCH_PAPER


def is_research_paper_url(url: str | None) -> bool:
    return classify_research_paper(url) is not None


def paper_metadata_patch(
    url: str | None,
    *,
    source_domain: str | None = None,
    title: str | None = None,
    existing_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fragment suitable for ``metadata = COALESCE(metadata,'{}') || patch``."""
    frag = classify_research_paper(
        url,
        source_domain=source_domain,
        title=title,
        metadata=existing_metadata,
    )
    return frag or {}
