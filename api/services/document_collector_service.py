"""
Document collector service (v7).
Automated discovery of PDF documents from government and academic sources.
Inserts metadata into intelligence.processed_documents for document_processing phase.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _fetch_crs(max_items: int) -> List[Tuple[str, str, str, str]]:
    """Congressional Research Service reports. Returns (url, title, source_name, document_type)."""
    import feedparser
    out: List[Tuple[str, str, str, str]] = []
    try:
        feed = feedparser.parse("https://crsreports.congress.gov/rss/reports", request_headers={"User-Agent": "NewsIntelligence/1.0"})
        for i, entry in enumerate(feed.entries):
            if i >= max_items:
                break
            link = entry.get("link") or ""
            if not link or ".pdf" not in link.lower():
                # Some entries link to HTML; skip or use as fallback
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
            link = entry.get("link") or ""
            if not link:
                continue
            # GAO often has PDF link in summary or link
            if ".pdf" not in link.lower() and entry.get("summary"):
                m = re.search(r'href="([^"]+\.pdf[^"]*)"', entry.summary, re.I)
                if m:
                    link = m.group(1)
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
            link = entry.get("link") or ""
            if not link:
                continue
            if ".pdf" not in link.lower():
                # CBO often has PDF in enclosure
                for enc in getattr(entry, "enclosures", []) or []:
                    href = enc.get("href") or enc.get("url") or ""
                    if ".pdf" in href.lower():
                        link = href
                        break
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
            out.append((pdf_url, title or arxiv_id, "arXiv", "paper"))
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
                    # Dedupe by source_url
                    cur.execute(
                        "SELECT 1 FROM intelligence.processed_documents WHERE source_url = %s LIMIT 1",
                        (url.strip(),),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """
                        INSERT INTO intelligence.processed_documents
                        (source_type, source_name, source_url, title, document_type)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (source_key, source_name, url.strip(), (title or "")[:2000], document_type),
                    )
                    inserted += 1
        conn.commit()
        conn.close()
        if inserted > 0:
            logger.info("Document collection (v7): %s new documents from %s", inserted, list(enabled))
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
