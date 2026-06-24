"""SEC EDGAR CIK → FtM Company mapper (standalone, no NI imports)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_HEADERS = {"User-Agent": "NewsReviewInvestigator/0.1 (contact@example.com)"}

# Instrument / fund tail patterns — shared CIKs that won't match news prose.
_INSTRUMENT_TITLE_RE = re.compile(
    r"\b("
    r"warrant|warrants|units?|preferred|preference|depositary|adr|ads|"
    r"etf|etn|trust|fund|income\s+shares|notes?\s+due|debenture|"
    r"rights?\s+to\s+purchase|subscription\s+receipt"
    r")\b",
    re.I,
)
_INSTRUMENT_TICKER_RE = re.compile(r"[-+][WPUR]$|\.WS$|\.U$|\.RT$", re.I)


@dataclass
class EdgarCompany:
    cik: str
    ticker: str
    title: str


def _pad_cik(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


def is_instrument_tail(company: EdgarCompany) -> bool:
    """Filter warrants, preferreds, units, ADRs, ETFs/trusts sharing issuer CIKs."""
    title = company.title or ""
    ticker = company.ticker or ""
    if _INSTRUMENT_TITLE_RE.search(title):
        return True
    if _INSTRUMENT_TICKER_RE.search(ticker):
        return True
    if len(ticker) > 5 and ticker.endswith(("W", "U", "R")):
        return True
    return False


def _operating_company_score(company: EdgarCompany) -> tuple[int, int]:
    """Prefer shorter tickers and titles without instrument keywords."""
    title = company.title or ""
    penalty = 1 if _INSTRUMENT_TITLE_RE.search(title) else 0
    return (penalty, len(title))


def dedupe_by_cik(companies: Iterable[EdgarCompany]) -> list[EdgarCompany]:
    """One canonical operating company per CIK."""
    by_cik: dict[str, EdgarCompany] = {}
    for company in companies:
        if is_instrument_tail(company):
            continue
        existing = by_cik.get(company.cik)
        if existing is None or _operating_company_score(company) < _operating_company_score(existing):
            by_cik[company.cik] = company
    return sorted(by_cik.values(), key=lambda c: c.cik)


def fetch_company_tickers() -> list[EdgarCompany]:
    with httpx.Client(headers=SEC_HEADERS, timeout=60.0) as client:
        resp = client.get(SEC_TICKERS_URL)
        resp.raise_for_status()
        payload = resp.json()
    companies: list[EdgarCompany] = []
    for entry in payload.values():
        companies.append(
            EdgarCompany(
                cik=_pad_cik(entry["cik_str"]),
                ticker=str(entry.get("ticker", "")),
                title=str(entry.get("title", "")),
            )
        )
    return companies


def load_deduped_companies(limit: int | None = None) -> list[EdgarCompany]:
    companies = dedupe_by_cik(fetch_company_tickers())
    if limit is not None:
        return companies[:limit]
    return companies


def company_to_ftm_entity(company: EdgarCompany) -> dict[str, Any]:
    entity_id = hashlib.sha1(f"edgar:{company.cik}".encode()).hexdigest()[:16]
    return {
        "id": entity_id,
        "schema_name": "Company",
        "caption": company.title,
        "dataset": "edgar",
        "referents": [f"ussec:cik:{company.cik}"],
        "statements": [
            {"prop": "name", "value": company.title},
            {"prop": "ticker", "value": company.ticker},
            {"prop": "cik", "value": company.cik},
        ],
        "anchors": [
            {"type": "cik", "value": company.cik},
        ],
    }


def ingest_edgar_subset(limit: int | None = None) -> int:
    from nri_core.spine.store import postgres_store

    companies = load_deduped_companies(limit=limit)
    count = 0
    for company in companies:
        entity = company_to_ftm_entity(company)
        postgres_store.upsert_entity(
            entity_id=entity["id"],
            schema_name=entity["schema_name"],
            caption=entity["caption"],
            dataset=entity["dataset"],
            referents=entity["referents"],
        )
        for stmt in entity["statements"]:
            postgres_store.upsert_statement(
                entity_id=entity["id"],
                dataset=entity["dataset"],
                schema_name=entity["schema_name"],
                prop=stmt["prop"],
                value=stmt["value"],
                origin="edgar",
            )
        for anchor in entity["anchors"]:
            postgres_store.upsert_anchor(entity["id"], anchor["type"], anchor["value"])
        count += 1
    return count
