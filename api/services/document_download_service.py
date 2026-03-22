"""
PDF download and URL resolution (HTTP + optional Playwright).

Used by document_processing_service (fetch/download) and document_collector_service
(landing-page PDF discovery). Behaviour matches docs/PDF_INGESTION_PIPELINE.md.
"""

from __future__ import annotations

import logging
import os
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

logger = logging.getLogger(__name__)


def normalize_source_url(url: str) -> str:
    """Normalize URL for dedupe (strip fragments + common tracking params). Shared with collector insert path."""
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

MAX_PDF_SIZE_MB = 50
DOWNLOAD_TIMEOUT = 45
DOWNLOAD_RETRIES = 2
RETRY_BACKOFF_SEC = 5
# Don't retry these; mark document as permanently failed so we stop re-queuing.
# 403 is intentionally excluded: many sources return temporary bot/WAF blocks.
PERMANENT_HTTP_CODES = (404, 410)
ENABLE_BROWSER_PDF_FALLBACK = os.getenv("ENABLE_BROWSER_PDF_FALLBACK", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}


def download_pdf(
    url: str, max_mb: int = MAX_PDF_SIZE_MB, head_first: bool = True
) -> tuple[bytes | None, str | None]:
    """
    Download PDF from URL. Returns (bytes, None) or (None, error).
    - Optional HEAD request first to fail fast on 404/403/410.
    - Retries with backoff for timeouts and 5xx (not for 4xx except where we retry).
    """
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NewsIntelligence/1.0; +https://news-intel/document-bot)",
        "Accept": "application/pdf,*/*",
    }

    # Fail fast on permanent HTTP errors (saves bandwidth and time)
    if head_first:
        try:
            head_resp = requests.head(
                url,
                timeout=10,
                allow_redirects=True,
                headers=headers,
            )
            if head_resp.status_code in PERMANENT_HTTP_CODES:
                return None, f"HTTP {head_resp.status_code} (permanent)"
            if head_resp.status_code >= 400 and head_resp.status_code < 500:
                return None, f"HTTP {head_resp.status_code}"
        except requests.exceptions.Timeout:
            return None, "HEAD timeout"
        except requests.exceptions.RequestException as e:
            # HEAD can fail (e.g. 405 Method Not Allowed); proceed to GET
            logger.debug("HEAD request failed, trying GET: %s", e)

    # GET with retries for timeout and 5xx only
    last_error: str | None = None
    for attempt in range(DOWNLOAD_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True, headers=headers)
            resp.raise_for_status()

            content = resp.content
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                if len(content) >= 5 and content[:5] != b"%PDF-":
                    return None, f"Not a PDF (Content-Type: {content_type})"

            size = len(content)
            if size > max_mb * 1024 * 1024:
                return None, f"PDF too large: {size / 1024 / 1024:.1f} MB (max {max_mb} MB)"

            return content, None
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code in PERMANENT_HTTP_CODES:
                return None, f"HTTP {e.response.status_code} (permanent)"
            if e.response is not None and 400 <= e.response.status_code < 500:
                return None, f"HTTP {e.response.status_code}"
            # 5xx: retry
            last_error = f"HTTP {e.response.status_code}" if e.response else str(e)
        except requests.exceptions.Timeout:
            last_error = f"Download timeout ({DOWNLOAD_TIMEOUT}s)"
        except requests.exceptions.RequestException as e:
            last_error = f"Download failed: {e}"

        if attempt < DOWNLOAD_RETRIES:
            time.sleep(RETRY_BACKOFF_SEC)

    return None, last_error or "Download failed"


def resolve_pdf_url_from_landing_page(url: str, timeout: int = 20) -> str | None:
    """
    Resolve a direct PDF URL from an HTML landing page (GET + href scan).
    Returns a normalized URL. Used by document_collector_service and fetch_pdf_from_url.
    """
    import requests

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
        base = resp.url or url
        # First: explicit .pdf links
        for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I):
            return normalize_source_url(urljoin(base, m.group(1)))
        # Second: common download endpoints that imply file payload
        for m in re.finditer(
            r'href=["\']([^"\']*(?:download|attachment|file)[^"\']*)["\']', html, re.I
        ):
            candidate = urljoin(base, m.group(1))
            if "pdf" in candidate.lower():
                return normalize_source_url(candidate)
    except Exception as e:
        logger.debug("Landing-page PDF resolve failed for %s: %s", url, e)
    return None


def _resolve_pdf_url_via_browser(url: str, timeout_ms: int = 20000) -> str | None:
    """Browser-based fallback: render page and discover PDF links/network responses."""
    if not ENABLE_BROWSER_PDF_FALLBACK:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("playwright not installed; skip browser PDF fallback")
        return None

    found: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()

                def _on_response(resp):
                    try:
                        ct = (resp.headers.get("content-type") or "").lower()
                    except Exception:
                        ct = ""
                    rurl = resp.url or ""
                    if "pdf" in ct or ".pdf" in rurl.lower():
                        found.append(rurl)

                page.on("response", _on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(2500)

                if found:
                    return normalize_source_url(found[0])

                links = (
                    page.eval_on_selector_all(
                        "a[href]",
                        "els => els.map(e => e.href).filter(Boolean)",
                    )
                    or []
                )
                for href in links:
                    if ".pdf" in str(href).lower():
                        return normalize_source_url(str(href))

                html = page.content() or ""
                for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.I):
                    return normalize_source_url(urljoin(page.url or url, m.group(1)))
            finally:
                browser.close()
    except Exception as e:
        logger.debug("Browser PDF resolve failed for %s: %s", url, e)
    return None


def fetch_pdf_from_url(
    url: str,
) -> tuple[bytes | None, str | None, str | None, str | None]:
    """
    Download PDF bytes from a URL, with landing-page and browser resolution fallbacks.

    Returns (pdf_bytes, error, final_pdf_url, resolved_via) where resolved_via is
    \"html\", \"browser\", or None. On failure, pdf_bytes is None and error is set.
    Mirrors the former _process_from_url download phase in document_processing_service.
    """
    pdf_url = url
    resolved_via: str | None = None
    pdf_bytes, download_error = download_pdf(pdf_url)
    should_try_resolution = bool(download_error) and any(
        marker in download_error.lower()
        for marker in ("not a pdf", "http 4", "timeout", "download failed")
    )
    if should_try_resolution:
        resolved = resolve_pdf_url_from_landing_page(url)
        if resolved and resolved != url:
            pdf_url = resolved
            resolved_via = "html"
            pdf_bytes, download_error = download_pdf(pdf_url, head_first=False)
    if should_try_resolution and download_error:
        resolved_browser = _resolve_pdf_url_via_browser(url)
        if resolved_browser and resolved_browser != url:
            pdf_url = resolved_browser
            resolved_via = "browser"
            pdf_bytes, download_error = download_pdf(pdf_url, head_first=False)
    return pdf_bytes, download_error, pdf_url, resolved_via
