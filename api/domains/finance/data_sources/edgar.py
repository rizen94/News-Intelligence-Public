"""
SEC EDGAR 10-K/40-F fetcher for mining companies.
Index → Download → Section extractor. Rate limit: 10 req/sec.
"""

import logging
import re
import time
from datetime import datetime, timezone

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import EDGAR_USER_AGENT, EDGAR_RATE_LIMIT_PER_SECOND
from shared.data_result import DataResult
from domains.finance.data_sources.base import DataSourceBase

SEC_BASE = "https://www.sec.gov"
DATA_SEC = "https://data.sec.gov"
SUBMISSIONS_URL = f"{DATA_SEC}/submissions/CIK{{cik}}.json"
ARCHIVES_BASE = f"{SEC_BASE}/Archives/edgar/data"

# Mining companies: CIK (zero-padded to 10), ticker, name
MINING_COMPANIES = [
    ("0000756894", "GOLD", "Barrick Gold"),   # Barrick Gold Corp
    ("0001164727", "NEM", "Newmont"),         # Newmont
    ("0000831259", "FCX", "Freeport-McMoRan"),
    ("0000001832", "AEM", "Agnico Eagle"),
    ("0001326389", "WPM", "Wheaton Precious Metals"),
]

_MIN_SPACING = 1.0 / EDGAR_RATE_LIMIT_PER_SECOND
_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_SPACING:
        time.sleep(_MIN_SPACING - elapsed)
    _last_request_time = time.monotonic()


def _headers(accept_json: bool = False) -> dict:
    h = {
        "User-Agent": EDGAR_USER_AGENT or "NewsIntelligence research@example.com",
    }
    if accept_json:
        h["Accept"] = "application/json"
    return h


def fetch_filing_index(cik: str, form_filter: str | None = "10-K") -> DataResult[list[dict]]:
    """
    Fetch recent 10-K (or 40-F for foreign issuers) filings for a CIK.
    Returns list of {accession_number, filing_date, form, primary_document, ...}.
    """
    cik_padded = cik.zfill(10)
    url = SUBMISSIONS_URL.format(cik=cik_padded)
    _rate_limit()
    t0 = time.perf_counter()
    try:
        import requests
        r = requests.get(url, headers=_headers(accept_json=True), timeout=30)
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call
            log_external_call(
                url=url,
                status="success" if r.status_code == 200 else "error",
                duration_ms=duration_ms,
                source="edgar",
                operation="index",
                cik=cik_padded,
                status_code=r.status_code,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        if r.status_code == 429:
            return DataResult.fail("EDGAR rate limited (429)", "rate_limit")
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call
            log_external_call(
                url=url,
                status="error",
                duration_ms=duration_ms,
                error=str(e),
                source="edgar",
                operation="index",
                cik=cik_padded,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        logger.warning("EDGAR fetch index failed for CIK %s: %s", cik, e)
        return DataResult.fail(str(e), "network")

    filings = data.get("filings", {}).get("recent", {})
    if not filings:
        return DataResult.fail("No filings in response", "no_data")
    acc_nums = filings.get("accessionNumber", [])
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    primaries = filings.get("primaryDocument", [])
    n = len(acc_nums)
    out = []
    for i in range(n):
        form = forms[i] if i < len(forms) else ""
        if form_filter and form != form_filter and form != "40-F":
            continue
        acc = acc_nums[i] if i < len(acc_nums) else ""
        if not acc:
            continue
        prim = primaries[i] if i < len(primaries) else ""
        date = dates[i] if i < len(dates) else ""
        out.append({
            "accession_number": acc,
            "filing_date": date,
            "form": form,
            "primary_document": prim,
            "cik": cik_padded,
        })
    return DataResult.ok(out[:20])  # Limit to 20 most recent


def download_filing(cik: str, accession_number: str, primary_document: str) -> DataResult[str]:
    """
    Download primary document HTML. Accession: 0001193125-26-079280.
    URL: .../data/{cik}/{acc_no_dashes_removed}/{primary_doc}
    """
    acc_clean = accession_number.replace("-", "")
    cik_stripped = cik.lstrip("0") or "0"
    url = f"{ARCHIVES_BASE}/{cik_stripped}/{acc_clean}/{primary_document}"
    _rate_limit()
    t0 = time.perf_counter()
    try:
        import requests
        r = requests.get(url, headers=_headers(), timeout=60)
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call
            log_external_call(
                url=url,
                status="success" if r.status_code == 200 else "error",
                duration_ms=duration_ms,
                source="edgar",
                operation="download",
                accession=accession_number,
                status_code=r.status_code,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        if r.status_code == 429:
            return DataResult.fail("EDGAR rate limited (429)", "rate_limit")
        r.raise_for_status()
        r.encoding = "utf-8"
        return DataResult.ok(r.text)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.activity_logger import log_external_call
            log_external_call(
                url=url,
                status="error",
                duration_ms=duration_ms,
                error=str(e),
                source="edgar",
                operation="download",
                accession=accession_number,
            )
        except Exception as _e:
            logger.debug("Activity log skip: %s", _e)
        logger.warning("EDGAR download failed %s: %s", url, e)
        return DataResult.fail(str(e), "network")


def get_filing_index_from_cache(service: str, params: dict):
    """Check api_cache for edgar index. Service='edgar', params={cik, form}."""
    from domains.finance.data.api_cache import get as cache_get
    return cache_get(service, params)


def set_filing_index_cache(service: str, params: dict, data: list, ttl: int = 3600 * 12):
    from domains.finance.data.api_cache import set as cache_set
    from domains.finance.data.api_cache import EDGAR_TTL
    return cache_set(service, params, {"filings": data}, ttl_seconds=EDGAR_TTL)


def fetch_index_cached(cik: str, form_filter: str | None = "10-K") -> DataResult[list[dict]]:
    """Fetch index with api_cache. Cache under service='edgar'."""
    params = {"cik": cik, "form": form_filter or "10-K"}
    cached = get_filing_index_from_cache("edgar", params)
    if cached:
        return DataResult.ok(cached.get("filings", []))
    result = fetch_filing_index(cik, form_filter)
    if result.success and result.data:
        set_filing_index_cache("edgar", params, result.data)
    return result


def download_filing_cached(
    cik: str, accession_number: str, primary_document: str
) -> DataResult[str]:
    """Download filing with api_cache. Cache under service='edgar_filing'."""
    from domains.finance.data.api_cache import get as cache_get, set as cache_set
    from domains.finance.data.api_cache import EDGAR_TTL

    params = {"cik": cik, "accession": accession_number, "primary": primary_document}
    cached = cache_get("edgar_filing", params)
    if cached:
        return DataResult.ok(cached.get("html", ""))
    result = download_filing(cik, accession_number, primary_document)
    if result.success and result.data:
        cache_set("edgar_filing", params, {"html": result.data}, ttl_seconds=EDGAR_TTL)
    return result


# Section extractor — Item 1/1A (Business), Item 7/7A (MD&A), Item 8 (Financials)
_WANTED_ITEMS = {1, 7, 8}


def extract_sections(html: str, document_id: str, source: str = "edgar_10k") -> list:
    """
    Extract Item 1/1A (Business), Item 7/7A (MD&A), Item 8 from 10-K/40-F HTML.
    Returns list of EvidenceChunk. Uses first occurrence of each wanted Item.
    """
    from domains.finance.data.evidence_chunk import EvidenceChunk

    if not html or not html.strip():
        return []

    text = html.replace("&#8217;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 100:
        return []

    chunks = []
    now = datetime.now(timezone.utc)
    # Match "Item N" or "Item NA" (e.g. Item 1A, Item 7, Item 8)
    pattern = r"Item\s+(\d+)(?:[A-Za-z])?(?:\s|[\.\,])"
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    taken = set()  # Which main number we already took (1, 7, or 8)
    for i, m in enumerate(matches):
        try:
            num = int(m.group(1))
        except (ValueError, IndexError):
            continue
        if num not in _WANTED_ITEMS or num in taken:
            continue
        taken.add(num)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        part = text[start:end].strip()
        if len(part) < 500:  # Skip short refs like "refer to Item 8"
            taken.discard(num)
            continue
        if len(part) > 12000:
            part = part[:12000] + " [truncated]"
        chunks.append(
            EvidenceChunk(
                text=part,
                source=source,
                document_id=document_id,
                chunk_index=len(chunks),
                timestamp=now,
                metadata={"section": f"Item {num}", "length": len(part)},
            )
        )
    return chunks[:12]


def get_client(config: dict | None = None):
    """Factory for EDGAR client (used by loader). Returns object with fetch methods."""
    return EdgarClient(config or {})


class EdgarClient(DataSourceBase):
    """EDGAR adapter — index, download, extract. Document-based; fetch_observations returns []."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.name = config.get("name", "SEC EDGAR")

    def fetch_observations(self, series_id: str, **kwargs) -> DataResult:
        """EDGAR is document-based; no time series. Returns empty."""
        return DataResult.ok([])

    def fetch_10k_index(self, cik: str, use_cache: bool = True) -> DataResult[list[dict]]:
        if use_cache:
            return fetch_index_cached(cik, "10-K")
        return fetch_filing_index(cik, "10-K")

    def download_filing(
        self, cik: str, accession_number: str, primary_document: str, use_cache: bool = True
    ) -> DataResult[str]:
        if use_cache:
            return download_filing_cached(cik, accession_number, primary_document)
        return download_filing(cik, accession_number, primary_document)

    def extract_chunks(self, html: str, document_id: str) -> list:
        return extract_sections(html, document_id)


def ingest_edgar_10ks(
    companies: list[tuple[str, str, str]] | None = None,
    filings_per_company: int = 1,
    record_ledger: bool = True,
) -> tuple[int, list[str]]:
    """
    Fetch 10-K filings for mining companies, extract Item 1/7/8, embed and ingest.
    Returns (count_embedded, chunk_ids).
    """
    from domains.finance.embedding import ingest_evidence_chunks

    companies = companies or MINING_COMPANIES
    client = EdgarClient({"name": "SEC EDGAR"})
    all_chunks = []

    for cik, ticker, name in companies:
        idx_result = client.fetch_10k_index(cik)
        if not idx_result.success or not idx_result.data:
            logger.warning("EDGAR index failed for %s (%s): %s", ticker, cik, idx_result.error)
            continue
        filings = idx_result.data[:filings_per_company]
        for f in filings:
            acc = f.get("accession_number", "")
            prim = f.get("primary_document", "")
            if not acc or not prim:
                continue
            doc_result = client.download_filing(cik, acc, prim)
            if not doc_result.success or not doc_result.data:
                logger.warning("EDGAR download failed %s %s: %s", ticker, acc, doc_result.error)
                continue
            doc_id = f"{ticker}_{acc.replace('-', '')}"
            chunks = client.extract_chunks(doc_result.data, doc_id)
            all_chunks.extend(chunks)
            logger.info("EDGAR %s %s: extracted %d chunks", ticker, acc, len(chunks))

    return ingest_evidence_chunks(all_chunks, record_ledger=record_ledger)
