"""
Document collector service (v8).
Automated discovery of PDF documents from government and academic sources.
Inserts metadata into intelligence.processed_documents for document_processing phase.
"""

import logging
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalize URL for dedupe (strip fragments + common tracking params)."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        if not p.scheme:
            return url.strip()
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
            and k.lower() not in {"gclid", "fbclid", "mc_cid", "mc_eid"}
        ]
        clean = p._replace(fragment="", query=urlencode(query, doseq=True))
        return urlunparse(clean)
    except Exception:
        return url.strip()


def _extract_pdf_from_entry(entry: Any, base_url: Optional[str] = None) -> Optional[str]:
    """Best-effort PDF URL extraction from feed entry fields."""
    candidates: List[str] = []
    link = (entry.get("link") or "").strip()
    if link:
        candidates.append(link)
    for enc in getattr(entry, "enclosures", []) or []:
        href = (enc.get("href") or enc.get("url") or "").strip()
        if href:
            candidates.append(href)
    for lk in getattr(entry, "links", []) or []:
        href = (lk.get("href") or "").strip()
        ltype = (lk.get("type") or "").lower()
        if href and ("pdf" in ltype or href.lower().endswith(".pdf") or ".pdf" in href.lower()):
            candidates.append(href)
    summary = entry.get("summary") or ""
    if summary:
        # Capture quoted links that contain .pdf
        for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', summary, re.I):
            candidates.append(m.group(1))
        # Capture unquoted direct .pdf urls
        for m in re.finditer(r'(https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*)', summary, re.I):
            candidates.append(m.group(1))

    for c in candidates:
        if not c:
            continue
        if base_url:
            c = urljoin(base_url, c)
        if ".pdf" in c.lower():
            return _normalize_url(c)
    return None


def _resolve_pdf_url_from_page(url: str, timeout: int = 20) -> Optional[str]:
    """Resolve a direct PDF URL from a landing page when feed only has HTML links."""
    try:
        import requests
    except Exception:
        return None
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsIntelligence/1.0; +https://news-intel/document-bot)",
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        if resp.status_code >= 400:
            return None
        html = resp.text or ""
        for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I):
            return _normalize_url(urljoin(resp.url or url, m.group(1)))
    except Exception as e:
        logger.debug("Resolve landing page PDF failed for %s: %s", url, e)
    return None


def _fetch_crs(max_items: int) -> List[Tuple[str, str, str, str]]:
    """Congressional Research Service reports. Returns (url, title, source_name, document_type)."""
    import feedparser
    out: List[Tuple[str, str, str, str]] = []
    try:
        feed = feedparser.parse("https://crsreports.congress.gov/rss/reports", request_headers={"User-Agent": "NewsIntelligence/1.0"})
        for i, entry in enumerate(feed.entries):
            if i >= max_items:
                break
            link = _extract_pdf_from_entry(entry, "https://crsreports.congress.gov")
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            out.append((link, title or "CRS Report", "Congressional Research Service", "report"))
    except Exception as e:
        logger.warning("CRS fetch failed: %s", e)
    return out


def _fetch_gao(max_items: int) -> List[Tuple[str, str, str, str]]:
    """GAO reports RSS. Returns (url, title, source_name, document_type)."""
    import feedparser
    out: List[Tuple[str, str, str, str]] = []
    try:
        feed = feedparser.parse("https://www.gao.gov/rss/reports.xml", request_headers={"User-Agent": "NewsIntelligence/1.0"})
        for i, entry in enumerate(feed.entries):
            if i >= max_items:
                break
            link = _extract_pdf_from_entry(entry, "https://www.gao.gov")
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            out.append((link, title or "GAO Report", "Government Accountability Office", "report"))
    except Exception as e:
        logger.warning("GAO fetch failed: %s", e)
    return out


def _fetch_cbo(max_items: int) -> List[Tuple[str, str, str, str]]:
    """Congressional Budget Office publications. Returns (url, title, source_name, document_type)."""
    import feedparser
    out: List[Tuple[str, str, str, str]] = []
    try:
        feed = feedparser.parse("https://www.cbo.gov/publications/all/rss.xml", request_headers={"User-Agent": "NewsIntelligence/1.0"})
        for i, entry in enumerate(feed.entries):
            if i >= max_items:
                break
            link = _extract_pdf_from_entry(entry, "https://www.cbo.gov")
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            out.append((link, title or "CBO Publication", "Congressional Budget Office", "report"))
    except Exception as e:
        logger.warning("CBO fetch failed: %s", e)
    return out


def _fetch_arxiv(max_items: int) -> List[Tuple[str, str, str, str]]:
    """arXiv recent papers (cs.AI, cs.CL). Returns (pdf_url, title, source_name, document_type)."""
    import urllib.request
    import xml.etree.ElementTree as ET
    out: List[Tuple[str, str, str, str]] = []
    try:
        # Query cs.AI, cs.CL - last 7 days
        url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL&sortBy=submittedDate&max_results=" + str(max_items)
        req = urllib.request.Request(url, headers={"User-Agent": "NewsIntelligence/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            tree = ET.parse(resp)
        root = tree.getroot()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            id_el = entry.find("atom:id", ns)
            title_el = entry.find("atom:title", ns)
            if id_el is None or id_el.text is None:
                continue
            arxiv_id = id_el.text.strip().split("/")[-1]
            pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf"
            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else arxiv_id
            out.append((_normalize_url(pdf_url), title or arxiv_id, "arXiv", "paper"))
    except Exception as e:
        logger.warning("arXiv fetch failed: %s", e)
    return out


# Source key -> (domain_filter, fetcher)
# domain_filter: None = all, or "politics"|"finance"|"science-tech"
SOURCES = {
    "crs": ("politics", _fetch_crs),
    "gao": (None, _fetch_gao),
    "cbo": (None, _fetch_cbo),
    "arxiv": ("science-tech", _fetch_arxiv),
}


def collect_documents(domain: Optional[str] = None, max_per_source: int = 10) -> int:
    """
    Run enabled document sources; insert new URLs into intelligence.processed_documents.
    domain: if set, only run sources that match this domain (politics|finance|science-tech).
    Returns count of new documents inserted.
    """
    from shared.database.connection import get_db_connection

    try:
        from config.orchestrator_governance import get_orchestrator_governance_config
        config = get_orchestrator_governance_config()
    except Exception:
        config = {}
    doc_sources = config.get("document_sources") or {}
    enabled = doc_sources.get("automated_sources") or list(SOURCES.keys())

    conn = get_db_connection()
    if not conn:
        logger.warning("Document collector: no DB connection")
        return 0

    inserted = 0
    try:
        with conn.cursor() as cur:
            for source_key in enabled:
                if source_key not in SOURCES:
                    continue
                domain_filter, fetcher = SOURCES[source_key]
                if domain and domain_filter and domain_filter != domain:
                    continue
                try:
                    items = fetcher(max_per_source)
                except Exception as e:
                    logger.warning("Document source %s failed: %s", source_key, e)
                    continue
                for url, title, source_name, document_type in items:
                    if not url or not url.strip():
                        continue
                    clean_url = _normalize_url(url)
                    metadata: Dict[str, Any] = {}
                    if ".pdf" not in clean_url.lower():
                        resolved = _resolve_pdf_url_from_page(clean_url)
                        if resolved:
                            clean_url = resolved
                        else:
                            # Keep known landing-page sources so document_processing can use
                            # browser/html resolver fallback to discover the PDF URL later.
                            if source_key in {"gao", "cbo"}:
                                metadata = {"collection": {"resolver_needed": True, "source_url_kind": "landing_page"}}
                            else:
                                continue
                    # Dedupe by source_url
                    cur.execute(
                        "SELECT 1 FROM intelligence.processed_documents WHERE source_url = %s LIMIT 1",
                        (clean_url,),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """
                        INSERT INTO intelligence.processed_documents
                        (source_type, source_name, source_url, title, document_type, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (source_key, source_name, clean_url, (title or "")[:2000], document_type, metadata or None),
                    )
                    inserted += 1
        conn.commit()
        conn.close()
        if inserted > 0:
            logger.info("Document collection (v8): %s new documents from %s", inserted, list(enabled))
        return inserted
    except Exception as e:
        logger.warning("Document collection failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0
