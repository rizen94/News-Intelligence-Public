"""
Scan politics/legal articles for federal bill citations; fetch Congress.gov snapshots.

Requires CONGRESS_GOV_API_KEY. Stores rows in intelligence.legislative_references
and marks scans in intelligence.legislative_article_scans.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from psycopg2.extras import Json, RealDictCursor

from shared.database.connection import get_db_connection_context
from shared.domain_registry import is_valid_domain_key, resolve_domain_schema
from shared.services.congress_gov_client import (
    fetch_bill,
    fetch_bill_summaries,
    fetch_bill_text_versions,
    is_congress_gov_configured,
)

logger = logging.getLogger(__name__)

# Domains that use federal bill citations (schema must exist). Override with LEGISLATIVE_SCAN_DOMAIN_KEYS.
LEGISLATIVE_SCAN_DOMAIN_KEYS: tuple[str, ...] = ("politics", "legal")


def legislative_scan_domain_keys() -> tuple[str, ...]:
    """Comma-separated URL domain keys, e.g. ``politics,legal``. Invalid keys are skipped."""
    raw = os.environ.get("LEGISLATIVE_SCAN_DOMAIN_KEYS", "").strip()
    if not raw:
        return LEGISLATIVE_SCAN_DOMAIN_KEYS
    out: list[str] = []
    for part in raw.split(","):
        p = part.strip().lower().replace("_", "-")
        if not p:
            continue
        if is_valid_domain_key(p):
            out.append(p)
        else:
            logger.debug("legislative_references: LEGISLATIVE_SCAN_DOMAIN_KEYS skip unknown %r", p)
    return tuple(out) if out else LEGISLATIVE_SCAN_DOMAIN_KEYS

DEFAULT_CONGRESS = int(os.environ.get("LEGISLATIVE_DEFAULT_CONGRESS", "118"))
SCAN_ARTICLE_DAYS = int(os.environ.get("LEGISLATIVE_SCAN_ARTICLE_DAYS", "90"))
MAX_TEXT_CHARS = 80000
SLEEP_BETWEEN_CONGRESS_GOV_CALLS = float(
    os.environ.get("LEGISLATIVE_FETCH_SLEEP_SECONDS", "0.35")
)

# Longer patterns first (H.J.Res before H.R.).
_BILL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bH\.?\s*J\.?\s*R\.?\s*[ .]*(\d+)\b"), "hjres"),
    (re.compile(r"(?i)(?:^|[\s\(\[,;])S\.?\s*J\.?\s*R\.?\s*[ .]*(\d+)\b"), "sjres"),
    (re.compile(r"(?i)\bH\.?\s*Con\.?\s*R\.?\s*[ .]*(\d+)\b"), "hconres"),
    (re.compile(r"(?i)(?:^|[\s\(\[,;])S\.?\s*Con\.?\s*R\.?\s*[ .]*(\d+)\b"), "sconres"),
    (re.compile(r"(?i)\bH\.?\s*R\.?\s*Res\.?\s*[ .]*(\d+)\b"), "hres"),
    (re.compile(r"(?i)(?:^|[\s\(\[,;])S\.?\s*Res\.?\s*[ .]*(\d+)\b"), "sres"),
    (re.compile(r"(?i)\bH\.?\s*R\.?\s*[ .]*(\d+)\b"), "hr"),
    (re.compile(r"(?i)(?:^|[\s\(\[,;])S\.\s*(\d+)\b"), "s"),
]


def infer_congress_from_text(text: str) -> int | None:
    m = re.search(r"(?i)(\d{1,3})(?:st|nd|rd|th)\s+Congress", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def extract_bill_mentions(text: str) -> list[tuple[int, str, int]]:
    """
    Extract (congress, bill_type, bill_number) tuples; deduped.
    Congress from explicit 'Nth Congress' or LEGISLATIVE_DEFAULT_CONGRESS.
    """
    if not text or len(text.strip()) < 20:
        return []
    congress_base = infer_congress_from_text(text) or DEFAULT_CONGRESS
    seen: set[tuple[int, str, int]] = set()
    out: list[tuple[int, str, int]] = []
    for rx, btype in _BILL_PATTERNS:
        for m in rx.finditer(text):
            try:
                num = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if num < 1 or num > 1_000_000:
                continue
            key = (congress_base, btype, num)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def _article_body(row: dict[str, Any]) -> str:
    parts = [
        (row.get("title") or "")[:2000],
        (row.get("summary") or "")[:8000],
        (row.get("content") or "")[:MAX_TEXT_CHARS],
    ]
    return "\n\n".join(p for p in parts if p)


def _select_unscanned_articles(domain_key: str, limit: int) -> list[dict[str, Any]]:
    schema = resolve_domain_schema(domain_key)
    q = f"""
        SELECT a.id, a.title, a.summary, a.content
        FROM {schema}.articles a
        WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
          AND a.created_at > NOW() - INTERVAL '{SCAN_ARTICLE_DAYS} days'
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.legislative_article_scans s
              WHERE s.domain_key = %s AND s.article_id = a.id
          )
        ORDER BY a.created_at DESC
        LIMIT %s
    """
    with get_db_connection_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(q, (domain_key, limit))
            return [dict(r) for r in cur.fetchall()]


def _upsert_reference(
    domain_key: str,
    article_id: int,
    congress: int,
    bill_type: str,
    bill_number: int,
    bill_metadata: dict[str, Any] | None,
    summaries: dict[str, Any] | None,
    text_versions: dict[str, Any] | None,
    fetch_status: str,
    fetch_error: str | None,
) -> None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.legislative_references (
                    domain_key, article_id, congress, bill_type, bill_number,
                    bill_metadata, summaries, text_versions,
                    fetch_status, fetch_error, fetched_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (domain_key, article_id, congress, bill_type, bill_number)
                DO UPDATE SET
                    bill_metadata = EXCLUDED.bill_metadata,
                    summaries = EXCLUDED.summaries,
                    text_versions = EXCLUDED.text_versions,
                    fetch_status = EXCLUDED.fetch_status,
                    fetch_error = EXCLUDED.fetch_error,
                    fetched_at = EXCLUDED.fetched_at,
                    updated_at = NOW()
                """,
                (
                    domain_key,
                    article_id,
                    congress,
                    bill_type.lower().strip(),
                    bill_number,
                    Json(bill_metadata) if bill_metadata is not None else None,
                    Json(summaries) if summaries is not None else None,
                    Json(text_versions) if text_versions is not None else None,
                    fetch_status,
                    fetch_error,
                ),
            )
        conn.commit()


def _mark_scan(domain_key: str, article_id: int, bills_found: int) -> None:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.legislative_article_scans (domain_key, article_id, bills_found, scanned_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (domain_key, article_id) DO UPDATE SET
                    bills_found = EXCLUDED.bills_found,
                    scanned_at = NOW()
                """,
                (domain_key, article_id, bills_found),
            )
        conn.commit()


def run_legislative_reference_batch(
    *,
    article_limit_per_domain: int = 8,
    domain_keys: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    Process unscanned articles in each domain; fetch Congress.gov for each detected bill.
    Returns stats dict for automation logging.
    """
    if not is_congress_gov_configured():
        return {
            "skipped": True,
            "reason": "CONGRESS_GOV_API_KEY not set",
            "articles_scanned": 0,
            "references_upserted": 0,
        }

    domains = domain_keys or legislative_scan_domain_keys()
    articles_scanned = 0
    references_upserted = 0

    for domain_key in domains:
        if not is_valid_domain_key(domain_key):
            logger.debug("legislative_references: skip inactive domain %s", domain_key)
            continue

        rows = _select_unscanned_articles(domain_key, article_limit_per_domain)
        for row in rows:
            aid = int(row["id"])
            body = _article_body(row)
            mentions = extract_bill_mentions(body)
            articles_scanned += 1

            if not mentions:
                _mark_scan(domain_key, aid, 0)
                continue

            n_ok = 0
            for congress, btype, bnum in mentions:
                time.sleep(SLEEP_BETWEEN_CONGRESS_GOV_CALLS)
                bill_r = fetch_bill(congress, btype, bnum)
                if not bill_r.get("success"):
                    _upsert_reference(
                        domain_key,
                        aid,
                        congress,
                        btype,
                        bnum,
                        None,
                        None,
                        None,
                        "error",
                        (bill_r.get("error") or "")[:2000],
                    )
                    references_upserted += 1
                    continue

                time.sleep(SLEEP_BETWEEN_CONGRESS_GOV_CALLS)
                sum_r = fetch_bill_summaries(congress, btype, bnum)
                time.sleep(SLEEP_BETWEEN_CONGRESS_GOV_CALLS)
                txt_r = fetch_bill_text_versions(congress, btype, bnum)

                summaries_data = sum_r.get("data") if sum_r.get("success") else None
                text_data = txt_r.get("data") if txt_r.get("success") else None
                err_parts = []
                if not sum_r.get("success"):
                    err_parts.append(f"summaries: {sum_r.get('error', '')}")
                if not txt_r.get("success"):
                    err_parts.append(f"text: {txt_r.get('error', '')}")

                fetch_status = "ok" if not err_parts else "partial"
                fetch_error = "; ".join(err_parts) if err_parts else None

                _upsert_reference(
                    domain_key,
                    aid,
                    congress,
                    btype,
                    bnum,
                    bill_r.get("data"),
                    summaries_data,
                    text_data,
                    fetch_status,
                    fetch_error,
                )
                references_upserted += 1

            _mark_scan(domain_key, aid, len(mentions))

    if articles_scanned > 0:
        logger.info(
            "legislative_references: scanned %s articles, upserted %s bill snapshots",
            articles_scanned,
            references_upserted,
        )

    return {
        "skipped": False,
        "articles_scanned": articles_scanned,
        "references_upserted": references_upserted,
    }
