"""
Historic context source adapters — fetch from news API, Wikipedia, EDGAR, FRED in a common shape.
Each adapter returns list of findings; run in parallel so one failure does not block others.
Findings: title, snippet, url, source_id, source_date, raw (optional).
"""

import logging
from datetime import datetime
from typing import Any
from urllib.parse import quote

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("historic_context")
except Exception:
    logger = logging.getLogger(__name__)

# Common finding shape
Finding = dict[str, Any]  # title, snippet, url, source_id, source_date (date or None), raw


def fetch_news_api(query: str, start_date: str, end_date: str, limit: int = 20) -> list[Finding]:
    """NewsAPI everything endpoint with date range. Returns list of findings or empty on error."""
    try:
        from config.settings import NEWS_API_KEY

        if not (NEWS_API_KEY and NEWS_API_KEY != "your_newsapi_key_here"):
            logger.debug("NewsAPI key not configured, skipping historic news source")
            return []
        import requests

        params = {
            "q": query,
            "from": start_date,
            "to": end_date,
            "sortBy": "relevancy",
            "pageSize": min(limit, 100),
            "language": "en",
            "apiKey": NEWS_API_KEY,
        }
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        articles = data.get("articles") or []
        out: list[Finding] = []
        for a in articles:
            pub = a.get("publishedAt") or ""
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00")).date() if pub else None
            except Exception:
                dt = None
            snippet = (a.get("description") or a.get("content") or "")[:500]
            if not snippet and a.get("title"):
                snippet = a.get("title", "")
            out.append(
                {
                    "title": (a.get("title") or "")[:500],
                    "snippet": snippet or "(no snippet)",
                    "url": a.get("url") or "",
                    "source_id": "news_api",
                    "source_date": dt,
                    "raw": {"source": a.get("source", {}).get("name"), "publishedAt": pub},
                }
            )
        return out
    except Exception as e:
        logger.warning("Historic source news_api failed: %s", e)
        return []


def fetch_wikipedia(query: str, start_date: str, end_date: str, limit: int = 15) -> list[Finding]:
    """Wikipedia search + summary for query. Date range used for relevance hint; API has no date filter."""
    try:
        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": "NewsIntelligenceSystem/1.0 (historic context)"})
        # Search
        params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet|timestamp",
        }
        r = session.get("https://en.wikipedia.org/w/api.php", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("query", {}).get("search") or []
        out: list[Finding] = []
        for item in items[:limit]:
            title = item.get("title", "")
            snippet = (
                (item.get("snippet") or "")
                .replace('<span class="searchmatch">', "")
                .replace("</span>", "")
            )
            ts = item.get("timestamp", "")
            try:
                source_date = (
                    datetime.fromisoformat(ts.replace("Z", "+00:00")).date() if ts else None
                )
            except Exception:
                source_date = None
            url = f"https://en.wikipedia.org/wiki/{quote(title)}" if title else ""
            out.append(
                {
                    "title": title[:500],
                    "snippet": snippet[:500] if snippet else title,
                    "url": url,
                    "source_id": "wikipedia",
                    "source_date": source_date,
                    "raw": {"pageid": item.get("pageid"), "timestamp": ts},
                }
            )
        return out
    except Exception as e:
        logger.warning("Historic source wikipedia failed: %s", e)
        return []


def fetch_edgar(query: str, start_date: str, end_date: str, limit: int = 15) -> list[Finding]:
    """EDGAR: fetch 10-K index for mining companies, filter by filing date in range, return as findings."""
    try:
        from domains.finance.data_sources.edgar import MINING_COMPANIES, fetch_filing_index

        try:
            start_d = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_d = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return []
        out: list[Finding] = []
        for cik, ticker, name in MINING_COMPANIES[:10]:
            idx_result = fetch_filing_index(cik, form_filter="10-K")
            if not idx_result.success or not idx_result.data:
                continue
            for f in idx_result.data[:5]:
                filing_date_s = f.get("filing_date")
                if not filing_date_s:
                    continue
                try:
                    filing_d = datetime.strptime(filing_date_s, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if start_d <= filing_d <= end_d:
                    acc = f.get("accession_number", "")
                    form = f.get("form", "10-K")
                    title = f"{name} ({ticker}) {form} filed {filing_date_s}"
                    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&dateb=&owner=include&count=40"
                    out.append(
                        {
                            "title": title[:500],
                            "snippet": f"SEC filing {form} for {name} filed on {filing_date_s}. Accession: {acc}.",
                            "url": url,
                            "source_id": "edgar",
                            "source_date": filing_d,
                            "raw": {"cik": cik, "accession_number": acc, "form": form},
                        }
                    )
                    if len(out) >= limit:
                        return out
        return out
    except Exception as e:
        logger.warning("Historic source edgar failed: %s", e)
        return []


def fetch_fred(query: str, start_date: str, end_date: str, limit: int = 30) -> list[Finding]:
    """FRED: commodity history in range; format as findings (e.g. platinum price on date)."""
    try:
        from config.settings import FRED_API_KEY
        from domains.finance.data_sources.fred_commodity import (
            FRED_SERIES_BY_METAL,
            fetch_commodity_history_from_fred,
        )

        if not FRED_API_KEY:
            return []
        query_lower = (query or "").lower()
        metals = ["gold", "silver", "platinum"] if not query_lower else []
        for m in ["gold", "silver", "platinum"]:
            if m in query_lower:
                metals = [m]
                break
        if not metals:
            metals = list(FRED_SERIES_BY_METAL.keys())
        out: list[Finding] = []
        for metal in metals:
            res = fetch_commodity_history_from_fred(
                metal, start=start_date, end=end_date, store=False
            )
            if not res.success or not res.data:
                continue
            obs = res.data[-limit:]
            for o in obs:
                d = o.get("date", "")
                v = o.get("value")
                unit = o.get("unit", "USD/toz")
                out.append(
                    {
                        "title": f"{metal.title()} price on {d}",
                        "snippet": f"{metal.title()} {d}: {v} {unit}",
                        "url": "",
                        "source_id": "fred",
                        "source_date": datetime.strptime(d, "%Y-%m-%d").date()
                        if len(d) == 10
                        else None,
                        "raw": {"metal": metal, "value": v, "unit": unit},
                    }
                )
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        logger.warning("Historic source fred failed: %s", e)
        return []


# Registry: source_id -> (callable, description)
SOURCE_ADAPTERS: dict[str, tuple[Any, str]] = {
    "news_api": (fetch_news_api, "News API (date-range news)"),
    "wikipedia": (fetch_wikipedia, "Wikipedia search"),
    "edgar": (fetch_edgar, "SEC EDGAR 10-K filings"),
    "fred": (fetch_fred, "FRED commodity history"),
}


def fetch_all_sources_parallel(
    query: str,
    start_date: str,
    end_date: str,
    source_ids: list[str] | None = None,
    limit_per_source: int = 20,
) -> dict[str, list[Finding]]:
    """
    Call each enabled source in parallel. Returns { source_id: [findings] }.
    One source failing does not affect others.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ids = source_ids or list(SOURCE_ADAPTERS.keys())
    results: dict[str, list[Finding]] = {}
    with ThreadPoolExecutor(max_workers=len(ids)) as executor:
        futures = {}
        for sid in ids:
            if sid not in SOURCE_ADAPTERS:
                continue
            fn, _ = SOURCE_ADAPTERS[sid]
            futures[executor.submit(fn, query, start_date, end_date, limit_per_source)] = sid
        for future in as_completed(futures):
            sid = futures[future]
            try:
                findings = future.result()
                results[sid] = findings or []
            except Exception as e:
                logger.warning("Historic source %s raised: %s", sid, e)
                results[sid] = []
    return results
