"""
SEC EDGAR recent filings (8-K / 10-K / 13D) → finance chronological_events.

Uses data.sec.gov submissions + full-text search recent filings.
Requires EDGAR_USER_AGENT. Feature: edgar_collector (default off)
"""

from __future__ import annotations

import logging
import time
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
from config.settings import EDGAR_RATE_LIMIT_PER_SECOND, EDGAR_USER_AGENT

logger = logging.getLogger(__name__)

FEATURE_KEY = "edgar_collector"
DATA_SEC = "https://data.sec.gov"
SUBMISSIONS_URL = f"{DATA_SEC}/submissions/CIK{{cik}}.json"

DEFAULT_FORMS = ("8-K", "10-K", "SC 13D", "13D")
# Small default watchlist (CIK zero-padded); override via EDGAR_COLLECTOR_CIKS
DEFAULT_CIKS = (
    "0000320193",  # AAPL
    "0000789019",  # MSFT
    "0001018724",  # AMZN
    "0001652044",  # GOOGL
    "0001045810",  # NVDA
    "0000756894",  # GOLD (Barrick)
    "0001164727",  # NEM
)

_last_req = 0.0


def _rate_limit() -> None:
    global _last_req
    spacing = 1.0 / max(1, int(EDGAR_RATE_LIMIT_PER_SECOND or 8))
    elapsed = time.monotonic() - _last_req
    if elapsed < spacing:
        time.sleep(spacing - elapsed)
    _last_req = time.monotonic()
    rate_limit_sleep(0)  # still update shared clock


def _headers() -> dict[str, str]:
    return {
        "User-Agent": EDGAR_USER_AGENT or "NewsIntelligence research@example.com",
        "Accept": "application/json",
    }


def _cik_list() -> list[str]:
    raw = (env_str("EDGAR_COLLECTOR_CIKS") or "").strip()
    if raw:
        return [c.strip().zfill(10) for c in raw.split(",") if c.strip()]
    return list(DEFAULT_CIKS)


def _form_set() -> set[str]:
    raw = (env_str("EDGAR_COLLECTOR_FORMS") or ",".join(DEFAULT_FORMS)).strip()
    return {f.strip().upper() for f in raw.split(",") if f.strip()}


def fetch_company_recent_filings(cik: str, *, limit: int = 15) -> list[dict[str, Any]]:
    cik_padded = cik.zfill(10)
    url = SUBMISSIONS_URL.format(cik=cik_padded)
    _rate_limit()
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        if r.status_code == 429:
            logger.warning("EDGAR rate limited for CIK %s", cik_padded)
            return []
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("EDGAR submissions failed CIK %s: %s", cik_padded, e)
        return []

    recent = (data.get("filings") or {}).get("recent") or {}
    acc = recent.get("accessionNumber") or []
    forms = recent.get("form") or []
    dates = recent.get("filingDate") or []
    primaries = recent.get("primaryDocument") or []
    name = data.get("name") or data.get("entityType") or cik_padded
    ticker = ""
    tickers = data.get("tickers") or []
    if isinstance(tickers, list) and tickers:
        ticker = str(tickers[0])

    wanted = _form_set()
    out: list[dict[str, Any]] = []
    for i, accession in enumerate(acc):
        form = (forms[i] if i < len(forms) else "").upper()
        # Normalize SC 13D / 13D variants
        form_norm = form.replace(" ", "")
        match = form in wanted or any(
            form_norm.startswith(w.replace(" ", "")) for w in wanted
        )
        if not match:
            continue
        filing_date = dates[i] if i < len(dates) else None
        primary = primaries[i] if i < len(primaries) else ""
        acc_nodash = str(accession).replace("-", "")
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik_padded)}/{acc_nodash}/{primary}"
            if primary
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_padded}"
        )
        out.append(
            {
                "cik": cik_padded,
                "company": name,
                "ticker": ticker,
                "accession": accession,
                "form": form,
                "filing_date": filing_date,
                "url": doc_url,
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_fulltext_recent(*, forms: list[str] | None = None, size: int = 20) -> list[dict[str, Any]]:
    """
    Best-effort EFTS recent hits. Endpoint shape varies; failures return [].
    """
    form_q = " OR ".join(f'formType:"{f}"' for f in (forms or list(DEFAULT_FORMS)[:3]))
    params = {"q": form_q, "dateRange": "custom", "startdt": "2024-01-01", "forms": ",".join(forms or list(DEFAULT_FORMS))}
    _rate_limit()
    try:
        r = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": form_q, "from": 0, "size": size},
            headers=_headers(),
            timeout=30,
        )
        if r.status_code >= 400:
            logger.debug("EDGAR full-text search HTTP %s — skip", r.status_code)
            return []
        payload = r.json()
        hits = (
            ((payload.get("hits") or {}).get("hits"))
            if isinstance(payload, dict)
            else None
        )
        if not hits:
            return []
        out = []
        for hit in hits[:size]:
            src = hit.get("_source") if isinstance(hit, dict) else None
            if not isinstance(src, dict):
                continue
            out.append(
                {
                    "cik": str(src.get("entity_id") or src.get("ciks") or "")[:10],
                    "company": src.get("display_names") or src.get("entity_name") or "SEC filer",
                    "ticker": "",
                    "accession": src.get("adsh") or src.get("accession_no") or hit.get("_id"),
                    "form": src.get("form") or src.get("file_type") or "8-K",
                    "filing_date": src.get("file_date") or src.get("period_ending"),
                    "url": src.get("file_url") or "",
                }
            )
        return out
    except Exception as e:
        logger.debug("EDGAR full-text search skipped: %s", e)
        return []


def _filing_to_event(row: dict[str, Any]) -> dict[str, Any] | None:
    accession = row.get("accession")
    if not accession:
        return None
    form = row.get("form") or "filing"
    company = row.get("company") or row.get("cik") or "SEC filer"
    ticker = row.get("ticker") or ""
    title = f"{ticker + ' — ' if ticker else ''}{company}: {form} filed"
    event_type = "report_release"
    if "8-K" in str(form).upper():
        event_type = "market_shift"
    elif "13D" in str(form).upper().replace(" ", ""):
        event_type = "investigation"
    return {
        "event_id": stable_event_id("edgar", str(accession)),
        "title": title[:500],
        "domain_key": "finance",
        "extraction_method": "edgar",
        "event_type": event_type,
        "description": (row.get("url") or "")[:2000],
        "actual_event_date": row.get("filing_date"),
        "importance_score": 0.6 if "8-K" in str(form).upper() else 0.5,
        "extraction_confidence": 0.85,
        "location": "United States",
        "verification_source": row.get("url") or "sec.gov/edgar",
        "source_text": row.get("url"),
        "tags": ["edgar", str(form), str(row.get("cik") or "")],
        "key_actors": [{"name": str(company), "role": "issuer"}],
        "metadata_extra": {"accession": str(accession), "form": str(form)},
    }


def collect_edgar(
    *,
    filings_per_cik: int | None = None,
    include_fulltext: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not collector_enabled(FEATURE_KEY, env_flag="EDGAR_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}
    if not (EDGAR_USER_AGENT or "").strip():
        return {"skipped": True, "reason": "EDGAR_USER_AGENT not set", "inserted": 0}

    per = filings_per_cik if filings_per_cik is not None else env_int("EDGAR_COLLECTOR_FILINGS_PER_CIK", 8)
    rows: list[dict[str, Any]] = []
    for cik in _cik_list():
        rows.extend(fetch_company_recent_filings(cik, limit=per))

    if include_fulltext and env_str("EDGAR_COLLECTOR_FULLTEXT", "true").lower() in (
        "1",
        "true",
        "yes",
    ):
        rows.extend(fetch_fulltext_recent(size=env_int("EDGAR_COLLECTOR_FULLTEXT_SIZE", 15)))

    # Dedupe by accession
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        acc = str(row.get("accession") or "")
        if not acc or acc in seen:
            continue
        seen.add(acc)
        unique.append(row)

    if dry_run:
        return {
            "skipped": False,
            "dry_run": True,
            "fetched": len(unique),
            "inserted": 0,
            "would_insert": len(unique),
        }

    inserted = 0
    for row in unique:
        ev = _filing_to_event(row)
        if not ev:
            continue
        if upsert_chronological_event(**ev):
            inserted += 1

    logger.info("EDGAR collector: filings=%s inserted=%s", len(unique), inserted)
    return {
        "skipped": False,
        "fetched": len(unique),
        "inserted": inserted,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_edgar(), indent=2, default=str))
