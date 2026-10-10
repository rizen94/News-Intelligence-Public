"""
Article content enrichment service (v8).
Fetches full article text via trafilatura for articles with short or missing content.
After enrichment, triggers re-extraction (entities, topics, context update).
Supports inline enrichment at RSS ingestion and batch backlog drain with attempt tracking.
Rejects paywall/subscription pages so we don't store FT-style "Subscribe to unlock" text as body.
Fallbacks: live -> browser (headless) -> Wayback -> archive.today. If all fail, article is removed (bad datapoint).
"""

import configparser
import json
import logging
import os
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Env flags for fallback steps (each optional)
_ENABLE_BROWSER = os.environ.get("ENABLE_BROWSER_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_ENABLE_WAYBACK = os.environ.get("ENABLE_WAYBACK_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_ENABLE_ARCHIVETODAY = os.environ.get("ENABLE_ARCHIVETODAY_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Rate limit for external fallback requests (seconds)
_WAYBACK_SLEEP = 1.5
_ARCHIVETODAY_SLEEP = 1.5
_FETCH_TIMEOUT = 10

MAX_CONTENT_CHARS = 50_000
MIN_CONTENT_TO_ENRICH = 500
# ArXiv RSS abstracts are typically 1–2k chars — above MIN_CONTENT_TO_ENRICH — so they
# never enter the normal enrichment backlog. Treat abs URLs / abstract-shaped bodies specially.
ARXIV_ABSTRACT_CONTENT_MAX = 3500
# Burst (48h catch-up): 0.4s between fetches; revert to 0.6 after catch-up
RATE_LIMIT_SLEEP = 0.4


def arxiv_id_from_url(url: str) -> str | None:
    """Extract bare arXiv id from abs/pdf/html/export URLs (e.g. 2608.17176 or 2608.17176v1)."""
    if not url:
        return None
    m = re.search(
        r"arxiv\.org/(?:abs|pdf|html|ps)/(?:arxiv[:/])?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)",
        url,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"arxiv\.org/pdf/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)\.pdf", url, re.I)
    return m.group(1) if m else None


def is_arxiv_abs_url(url: str) -> bool:
    return bool(url) and "arxiv.org/abs/" in url.lower()


def looks_like_arxiv_abstract_only(content: str | None) -> bool:
    """True when stored body is RSS-style abstract, not full paper text."""
    text = (content or "").strip()
    if not text or len(text) > ARXIV_ABSTRACT_CONTENT_MAX:
        return False
    low = text.lower()
    if "abstract:" in low or low.startswith("arxiv:"):
        return True
    # Short body on abs URL is almost always abstract-only
    return len(text) < ARXIV_ABSTRACT_CONTENT_MAX


def needs_arxiv_fulltext(url: str, content: str | None = None) -> bool:
    if not is_arxiv_abs_url(url) and not arxiv_id_from_url(url or ""):
        return False
    if is_arxiv_abs_url(url):
        return looks_like_arxiv_abstract_only(content) if content else True
    return looks_like_arxiv_abstract_only(content)


def _strip_arxiv_html_chrome(text: str) -> str:
    """Drop nav/footer chrome left after HTML extraction."""
    if not text:
        return ""
    # Prefer from Abstract / Introduction onward when present
    for marker in ("###### Abstract", "## Abstract", "Abstract\n", "##  1 Introduction", "## 1 Introduction"):
        idx = text.find(marker)
        if idx > 0 and idx < len(text) // 2:
            text = text[idx:]
            break
    # Truncate experimental HTML footer
    for end in (
        "\n## Instructions for reporting errors",
        "\nExperimental support, please",
        "\nHave a free development cycle?",
    ):
        cut = text.find(end)
        if cut > 2000:
            text = text[:cut]
    return text.strip()


def _fetch_arxiv_full_text(url: str) -> str:
    """
    Full paper body for arXiv abs links: prefer experimental HTML, then PDF text extract.
    Uses existing download + pdfplumber/pymupdf stack (same as document pipeline).
    """
    aid = arxiv_id_from_url(url)
    if not aid:
        return ""
    # Drop version suffix for html path stability (v1 pages exist; bare id redirects)
    aid_base = re.sub(r"v\d+$", "", aid)

    # 1) HTML full text (Crawl4AI-equivalent path: fetch + trafilatura)
    html_urls = (
        f"https://arxiv.org/html/{aid}",
        f"https://arxiv.org/html/{aid_base}",
        f"https://arxiv.org/html/{aid_base}v1",
    )
    try:
        import trafilatura

        for html_url in html_urls:
            try:
                downloaded = trafilatura.fetch_url(html_url, config=_ONDEMAND_CONFIG or _FAST_CONFIG)
                if not downloaded or len(downloaded) < 2000:
                    continue
                extracted = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=True,
                    include_formatting=True,
                    config=_ONDEMAND_CONFIG or _FAST_CONFIG,
                )
                text = _strip_arxiv_html_chrome(_finalize_extracted_text(extracted or ""))
                if text and len(text) >= ARXIV_ABSTRACT_CONTENT_MAX:
                    return text[:MAX_CONTENT_CHARS]
            except Exception as e:
                logger.debug("arxiv html fetch failed %s: %s", html_url, e)
    except Exception as e:
        logger.debug("arxiv html path unavailable: %s", e)

    # 2) PDF via shared document download + extractors
    pdf_url = f"https://arxiv.org/pdf/{aid_base}.pdf"
    try:
        from services.document_download_service import download_pdf
        from services.document_processing_service import _extract_text_from_pdf

        pdf_bytes, err = download_pdf(pdf_url, head_first=True)
        if err or not pdf_bytes:
            logger.debug("arxiv pdf download failed %s: %s", pdf_url, err)
        elif pdf_bytes:
            extraction = _extract_text_from_pdf(pdf_bytes)
            raw = (
                (extraction or {}).get("total_text")
                or (extraction or {}).get("text")
                or ""
            )
            text = _finalize_extracted_text(raw)
            if text and len(text) >= 800:
                return text[:MAX_CONTENT_CHARS]
    except Exception as e:
        logger.debug("arxiv pdf extract failed %s: %s", pdf_url, e)

    return ""


def _make_fast_config():
    """Trafilatura config with 10s timeout so we move on quickly from slow/dead URLs."""
    try:
        from trafilatura.settings import DEFAULT_CONFIG

        cfg = configparser.ConfigParser()
        cfg.read_dict(DEFAULT_CONFIG)
        cfg.set("DEFAULT", "download_timeout", "10")
        cfg.set("DEFAULT", "extraction_timeout", "10")
        return cfg
    except Exception:
        return None


_FAST_CONFIG = _make_fast_config()


def _make_on_demand_config():
    """Slightly longer timeouts for user-triggered fetches (article reader)."""
    try:
        from trafilatura.settings import DEFAULT_CONFIG

        cfg = configparser.ConfigParser()
        cfg.read_dict(DEFAULT_CONFIG)
        cfg.set("DEFAULT", "download_timeout", "25")
        cfg.set("DEFAULT", "extraction_timeout", "25")
        return cfg
    except Exception:
        return _FAST_CONFIG


_ONDEMAND_CONFIG = _make_on_demand_config()

# Browser-like UA: some publishers return stub HTML to library/default clients (e.g. BBC).
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Boilerplate extracted when video/embed players fail (extension blockers, etc.) — not usable article text.
_BODY_BOILERPLATE_SUBSTRINGS: tuple[str, ...] = (
    "browser extensions seems to be blocking the video player",
    "to watch this content, you may need to disable it on this site",
)

# Phrases that indicate the extracted "content" is a paywall/subscription block instead of the article
_PAYWALL_PHRASES = (
    "subscribe to unlock",
    "try unlimited access",
    "only $1 for 4 weeks",
    "then $75 per month",
    "cancel anytime during your trial",
    "complete digital access",
    "pay a year upfront and save",
    "premium digital",
    "standard digital",
    "essential digital access",
    "explore our full range of subscriptions",
    "for individuals",
    "for multiple readers",
    "why the ft?",
    "terms & conditions apply",
    "explore more offers",
    "discover all the plans",
    "check whether you already have access",
    "paid annually",
    "delivered saturday plus complete digital",
)

# If text contains this many distinct paywall phrases, treat as paywall (don't save as enriched)
_PAYWALL_PHRASE_THRESHOLD = 2
# Or if text is short and contains any pricing-like line
_PAYWALL_PRICING_RE = re.compile(r"\$\d+\s*(per month|/month|/year|per year)", re.I)


def _is_paywall_content(text: str) -> bool:
    """True if extracted text looks like a subscription/paywall block rather than article body."""
    if not text or len(text.strip()) < 50:
        return False
    lower = text.lower().strip()
    count = sum(1 for p in _PAYWALL_PHRASES if p in lower)
    if count >= _PAYWALL_PHRASE_THRESHOLD:
        return True
    if count >= 1 and _PAYWALL_PRICING_RE.search(text):
        return True
    # Short content that's mostly paywall (e.g. < 400 chars and has one phrase)
    if len(text) < 400 and count >= 1:
        return True
    return False


# Soft-403 / chrome / cookie walls that must never stay enrichment_status=enriched (F9).
_FALSE_ENRICHED_NEEDLES = (
    "access denied",
    "403 forbidden",
    "enable javascript",
    "please enable cookies",
    "cookie consent",
    "subscribe to continue",
    "sign in to continue",
    "log in to continue",
    "create a free account",
    "are you a robot",
    "cf-browser-verification",
    "attention required",
    "just a moment",
)


def is_false_enriched_body(text: str | None, *, min_chars: int = 200) -> bool:
    """True when body is too thin or looks like chrome/error — not yieldable journalism."""
    body = (text or "").strip()
    if len(body) < int(min_chars):
        return True
    if _is_paywall_content(body):
        return True
    lower = body.lower()
    if any(n in lower for n in _FALSE_ENRICHED_NEEDLES):
        return True
    for frag in _BODY_BOILERPLATE_SUBSTRINGS:
        if frag in lower and len(body) < 800:
            return True
    return False


_SENTENCE_BOUNDARY_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def strip_boilerplate_sentences(text: str) -> str:
    """
    Remove sentences that match known non-article stubs (e.g. blocked video player messages).
    Applied after paragraph spacing so storyline excerpts and readers stay clean.
    """
    if not text or not str(text).strip():
        return (text or "").strip()
    needles = _BODY_BOILERPLATE_SUBSTRINGS
    paras = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
    out_paras: list[str] = []
    for para in paras:
        p = para.strip()
        if not p:
            continue
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY_SPLIT_RE.split(p) if s.strip()]
        if not sentences:
            continue
        low_block = p.lower()
        if len(sentences) == 1 and _SENTENCE_BOUNDARY_SPLIT_RE.search(p) is None:
            if any(n in low_block for n in needles):
                continue
            out_paras.append(p)
            continue
        kept: list[str] = []
        for s in sentences:
            low = s.lower()
            if any(n in low for n in needles):
                continue
            kept.append(s)
        if kept:
            out_paras.append(" ".join(kept))
    return "\n\n".join(out_paras).strip()


def format_article_content_excerpt(raw: str | None, max_len: int) -> str | None:
    """Normalize a DB snippet for API responses (paragraphs + boilerplate strip + truncate)."""
    if raw is None:
        return None
    out = format_article_body_paragraphs(str(raw).strip())
    if not out:
        return None
    return out[:max_len] if len(out) > max_len else out


def format_article_body_paragraphs(text: str) -> str:
    """
    Insert blank lines between paragraphs for readability in the article reader.
    Scraped text often arrives as a single block or with only single newlines.
    """
    if not text or not str(text).strip():
        return (text or "").strip()

    out = str(text).replace("\r\n", "\n").replace("\r", "\n")
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n[ \t]+", "\n", out)
    # Line break after sentence end when the next line starts a new sentence or list item.
    out = re.sub(r"(?<=[.!?])\n+(?=[A-Z0-9\"'(\[])", "\n\n", out)
    out = re.sub(r"(?<=[.!?])\n+(?=\d+\.\s)", "\n\n", out)

    if "\n\n" not in out.strip():
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])", out.strip())
        if len(sentences) >= 4:
            paragraphs: list[str] = []
            chunk: list[str] = []
            chunk_len = 0
            for sentence in sentences:
                s = sentence.strip()
                if not s:
                    continue
                chunk.append(s)
                chunk_len += len(s)
                if len(chunk) >= 3 or chunk_len >= 420:
                    paragraphs.append(" ".join(chunk))
                    chunk = []
                    chunk_len = 0
            if chunk:
                paragraphs.append(" ".join(chunk))
            if len(paragraphs) >= 2:
                out = "\n\n".join(paragraphs)

    out = re.sub(r"\n{3,}", "\n\n", out)
    return strip_boilerplate_sentences(out.strip())


def _finalize_extracted_text(text: str) -> str:
    """Paywall check + paragraph spacing for stored and returned article bodies."""
    # PDF extractors can emit NUL bytes; Postgres rejects them in text columns.
    text = (text or "").replace("\x00", "").strip()
    if not text:
        return ""
    if _is_paywall_content(text):
        return ""
    return format_article_body_paragraphs(text)


def _extract_from_html(html: str) -> str:
    """Extract main text from HTML with trafilatura; return empty if paywall or failure."""
    if not html or len(html.strip()) < 100:
        return ""
    try:
        import trafilatura

        text = (
            trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_formatting=True,
                config=_FAST_CONFIG,
            )
            if _FAST_CONFIG
            else trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                include_formatting=True,
            )
        )
        return _finalize_extracted_text(text)
    except Exception as e:
        logger.debug("trafilatura extract from HTML failed: %s", e)
        return ""


def _fetch_live_with_browser_ua(url: str) -> str:
    """Fetch HTML with a common browser User-Agent, then extract text (fallback when trafilatura fetch is empty)."""
    if not url or not url.strip():
        return ""
    try:
        req = Request(
            url.strip(),
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = _extract_from_html(html)
        if text:
            logger.debug("Browser-UA live fetch succeeded for %s", url[:80])
        return text
    except (URLError, HTTPError, OSError, ValueError) as e:
        logger.debug("Browser-UA live fetch failed for %s: %s", url[:80], e)
        return ""


def _fetch_via_wayback(url: str) -> str:
    """Try to get article text from an Internet Archive (Wayback) snapshot. Returns empty on failure or paywall."""
    if not _ENABLE_WAYBACK or not url or not url.strip():
        return ""
    try:
        time.sleep(_WAYBACK_SLEEP)
        availability_url = "https://archive.org/wayback/available?url=" + quote(url, safe="")
        req = Request(availability_url, headers={"User-Agent": "NewsIntelligence/1.0"})
        with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        snap = (data.get("archived_snapshots") or {}).get("closest")
        if not snap:
            return ""
        snapshot_url = snap.get("url") or (
            "https://web.archive.org/web/{}/{}".format(snap.get("timestamp", ""), url)
        )
        req2 = Request(snapshot_url, headers={"User-Agent": "NewsIntelligence/1.0"})
        with urlopen(req2, timeout=_FETCH_TIMEOUT) as resp2:
            html = resp2.read().decode("utf-8", errors="replace")
        text = _extract_from_html(html)
        if text:
            logger.debug("Wayback snapshot used for %s", url[:80])
        return text
    except (URLError, HTTPError, json.JSONDecodeError, OSError) as e:
        logger.debug("Wayback fetch failed for %s: %s", url[:80], e)
        return ""


def _fetch_via_browser(url: str) -> str:
    """Try to get article text via headless browser (Playwright). Returns empty on failure or paywall."""
    if not _ENABLE_BROWSER or not url or not url.strip():
        return ""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("playwright not installed; skip browser enrichment")
        return ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(2000)
                html = page.content()
            finally:
                browser.close()
        text = _extract_from_html(html)
        if text:
            logger.debug("Browser fetch used for %s", url[:80])
        return text
    except Exception as e:
        logger.debug("Browser fetch failed for %s: %s", url[:80], e)
        return ""


def _fetch_via_archivetoday(url: str) -> str:
    """Try to get article text from an archive.today (Memento) snapshot. Returns empty on failure or paywall."""
    if not _ENABLE_ARCHIVETODAY or not url or not url.strip():
        return ""
    try:
        time.sleep(_ARCHIVETODAY_SLEEP)
        # TimeGate: request may redirect to a memento; we need the final page body
        gate_url = "https://archive.today/timegate/" + url
        req = Request(gate_url, headers={"User-Agent": "NewsIntelligence/1.0"})
        with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # If we got a real page (not "not archived" or error), try to extract
        if "not found" in html.lower()[:2000] or "no snapshot" in html.lower()[:2000]:
            return ""
        text = _extract_from_html(html)
        if text:
            logger.debug("archive.today snapshot used for %s", url[:80])
        return text
    except (URLError, HTTPError, OSError) as e:
        logger.debug("archive.today fetch failed for %s: %s", url[:80], e)
        return ""


def _remove_article(conn, schema_name: str, article_id: int) -> None:
    """Mark article as removed (bad datapoint). Soft-delete: set enrichment_status = 'removed'."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {schema_name}.articles SET enrichment_status = 'removed', updated_at = NOW() WHERE id = %s""",
                (article_id,),
            )
            cur.execute(
                f"""DELETE FROM {schema_name}.topic_extraction_queue WHERE article_id = %s""",
                (article_id,),
            )
        conn.commit()
        logger.info("Article removed (bad datapoint): %s.articles id=%s", schema_name, article_id)
    except Exception as e:
        logger.warning("Remove article failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass


def demote_false_enriched_batch(*, limit_per_schema: int = 40) -> int:
    """Demote existing enrichment_status=enriched rows whose body fails the F9 yieldable check."""
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs

    demoted = 0
    pairs = list(pipeline_url_schema_pairs())
    if not pairs:
        return 0
    with get_db_connection_context() as conn:
        for _dk, schema_name in pairs:
            try:
                with conn.cursor() as cur:
                    # Prefer rows that match the F9 SQL proxy so remasurement moves.
                    # Include EEL-linked sources (A3 residual) even when created_at is older.
                    cur.execute(
                        f"""
                        SELECT id, content
                        FROM {schema_name}.articles
                        WHERE enrichment_status = 'enriched'
                          AND (
                            created_at > NOW() - INTERVAL '14 days'
                            OR id IN (
                              SELECT DISTINCT ce.source_article_id
                              FROM intelligence.event_episode_links eel
                              JOIN public.chronological_events ce ON ce.id = eel.event_id
                              WHERE eel.domain_key = %s
                                AND eel.created_at > NOW() - INTERVAL '14 days'
                                AND ce.source_article_id IS NOT NULL
                                AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                            )
                          )
                          AND (
                            LENGTH(COALESCE(content,'')) < 200
                            OR content ILIKE '%%access denied%%'
                            OR content ILIKE '%%subscribe%%'
                            OR content ILIKE '%%enable javascript%%'
                            OR content ILIKE '%%cookie%%'
                            OR content ILIKE '%%403%%'
                            OR content ILIKE '%%sign in to continue%%'
                          )
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (_dk, int(limit_per_schema)),
                    )
                    rows = cur.fetchall() or []
                for aid, content in rows:
                    if not is_false_enriched_body(content):
                        continue
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE {schema_name}.articles
                            SET enrichment_status = 'failed', updated_at = NOW()
                            WHERE id = %s AND enrichment_status = 'enriched'
                            """,
                            (int(aid),),
                        )
                        demoted += int(cur.rowcount or 0)
                conn.commit()
            except Exception as e:
                logger.debug("demote_false_enriched %s: %s", schema_name, e)
                try:
                    conn.rollback()
                except Exception:
                    pass
    if demoted:
        logger.info("F9 demoted false-enriched articles: %s", demoted)
    return demoted


def enrich_articles_batch(batch_size: int = 20) -> int:
    """
    Drain enrichment backlog: select by enrichment_status/attempts, fetch with trafilatura (10s timeout),
    update status and attempts; keep RSS content on failure; prune after 3 attempts.
    Returns count of enriched articles.

    Fair share: each active domain may fetch up to ceil(batch_size / n_domains) candidates per call
    (capped by remaining success budget), so high display_order silos are not starved by earlier domains.
    """
    try:
        demote_false_enriched_batch(limit_per_schema=max(10, int(batch_size)))
    except Exception as e:
        logger.debug("demote_false_enriched_batch: %s", e)
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed; skipping content enrichment")
        return 0

    from shared.database.connection import get_db_config, get_db_connection
    from shared.domain_registry import pipeline_url_schema_pairs

    from shared.article_processing_gates import (
        strict_enrichment_applies,
        strict_enrichment_cutoff_utc,
    )
    from shared.pipeline_article_selection import sql_order_created_at

    from services.context_processor_service import (
        ensure_context_for_article,
        sync_context_from_article_after_content_change,
        update_context_content_for_article,
    )

    conn = get_db_connection()
    if not conn:
        logger.warning("Content enrichment: no DB connection")
        return 0

    default_timeout_ms = get_db_config().get("statement_timeout_ms", 120000)
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '300s'")
        enriched = 0
        remaining = batch_size
        pairs = list(pipeline_url_schema_pairs())
        if not pairs:
            return 0
        n_domains = len(pairs)
        share = max(1, (batch_size + n_domains - 1) // n_domains)
        _ca_ord = sql_order_created_at()
        batch_commit_every = 10
        pending_commits = 0

        def _flush_commit(force: bool = False) -> None:
            nonlocal pending_commits
            if force or pending_commits >= batch_commit_every:
                conn.commit()
                pending_commits = 0

        for domain_key, schema_name in pairs:
            if remaining <= 0:
                break
            fetch_limit = min(share, remaining)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, url, content, created_at, enrichment_status
                    FROM {schema_name}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    ORDER BY COALESCE(enrichment_attempts, 0) ASC, created_at {_ca_ord}
                    LIMIT %s
                    """,
                    (fetch_limit,),
                )
                rows = cur.fetchall()

            for article_id, url, existing_content, created_at, row_status in rows:
                if remaining <= 0:
                    break
                if not url or not url.strip():
                    continue
                # Strict-ingest long RSS: pending without a second trafilatura pass.
                # ArXiv abs abstracts are 1–2k chars (above MIN_CONTENT_TO_ENRICH) but
                # still need PDF/HTML fulltext — do not fast-path mark them enriched.
                if (
                    strict_enrichment_cutoff_utc() is not None
                    and strict_enrichment_applies(created_at)
                    and existing_content
                    and len((existing_content or "").strip()) >= MIN_CONTENT_TO_ENRICH
                    and (row_status is None or (row_status or "").strip() == "pending")
                    and not needs_arxiv_fulltext(url, existing_content)
                ):
                    fast_rows = 0
                    if is_false_enriched_body(existing_content):
                        with conn.cursor() as cur:
                            cur.execute(
                                f"""
                                UPDATE {schema_name}.articles
                                SET enrichment_status = 'failed', updated_at = NOW()
                                WHERE id = %s
                                  AND (enrichment_status IS NULL OR enrichment_status = 'pending')
                                """,
                                (article_id,),
                            )
                            fast_rows = cur.rowcount or 0
                        if fast_rows:
                            conn.commit()
                            remaining -= 1
                            time.sleep(RATE_LIMIT_SLEEP)
                        continue
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE {schema_name}.articles
                            SET enrichment_status = 'enriched', updated_at = NOW()
                            WHERE id = %s
                              AND (enrichment_status IS NULL OR enrichment_status = 'pending')
                            """,
                            (article_id,),
                        )
                        fast_rows = cur.rowcount or 0
                    if fast_rows:
                        conn.commit()
                        enriched += 1
                        remaining -= 1
                        try:
                            ensure_context_for_article(domain_key, article_id)
                        except Exception as ctx_e:
                            logger.debug(
                                "enrichment fast-path context %s/%s: %s",
                                domain_key,
                                article_id,
                                ctx_e,
                            )
                        time.sleep(RATE_LIMIT_SLEEP)
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {schema_name}.articles SET enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1, updated_at = NOW() WHERE id = %s""",
                        (article_id,),
                    )
                pending_commits += 1
                _flush_commit()

                text = _fetch_full_text(url)
                if text:
                    text = text[:MAX_CONTENT_CHARS]
                with conn.cursor() as cur:
                    if text and is_false_enriched_body(text):
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET content = %s, enrichment_status = 'failed', updated_at = NOW() WHERE id = %s""",
                            (text[:2000], article_id),
                        )
                        pending_commits += 1
                        _flush_commit()
                        remaining -= 1
                        time.sleep(RATE_LIMIT_SLEEP)
                        continue
                    if text:
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET content = %s, enrichment_status = 'enriched', updated_at = NOW() WHERE id = %s""",
                            (text, article_id),
                        )
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET entities = NULL WHERE id = %s""",
                            (article_id,),
                        )
                        cur.execute(
                            f"""
                            INSERT INTO {schema_name}.topic_extraction_queue (article_id, status, priority, created_at)
                            VALUES (%s, 'pending', 3, NOW())
                            ON CONFLICT (article_id) DO UPDATE SET status = 'pending', priority = 3, created_at = NOW()
                            """,
                            (article_id,),
                        )
                    else:
                        # All paths (live, browser, wayback, archivetoday) failed: remove as bad datapoint
                        _remove_article(conn, schema_name, article_id)
                        conn.commit()
                        time.sleep(RATE_LIMIT_SLEEP)
                        continue
                pending_commits += 1
                _flush_commit()

                if text:
                    enriched += 1
                    remaining -= 1
                    update_context_content_for_article(domain_key, article_id)
                    try:
                        from services.research_paper_classifier import paper_metadata_patch
                        from services.research_paper_profile_service import (
                            ensure_pending_profile,
                            stamp_article_research_metadata,
                        )

                        patch = stamp_article_research_metadata(
                            schema_name, article_id, url, title=None
                        )
                        if patch:
                            ensure_pending_profile(
                                domain_key,
                                article_id,
                                url=url,
                                metadata=patch,
                            )
                    except Exception as paper_e:
                        logger.debug(
                            "enrichment research stamp %s/%s: %s",
                            domain_key,
                            article_id,
                            paper_e,
                        )

                time.sleep(RATE_LIMIT_SLEEP)

            _flush_commit(force=True)

        for _dk, sch in pairs:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {sch}.articles SET enrichment_status = 'inaccessible' WHERE enrichment_status = 'failed' AND enrichment_attempts >= 3"""
                )
            pending_commits += 1
        _flush_commit(force=True)

        if enriched > 0:
            logger.info("Content enrichment (v8): %s articles enriched", enriched)
        return enriched
    except Exception as e:
        logger.warning("Content enrichment failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{default_timeout_ms}'")
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def _fetch_full_text(url: str, config=None) -> str:
    """Fetch URL and extract main content. Tries: live -> browser (if enabled) -> Wayback (if enabled) -> archive.today (if enabled).
    Returns empty string when all attempted paths fail or return paywall content."""
    # 0. arXiv abs → HTML full text or PDF extract (RSS only stores abstracts)
    if is_arxiv_abs_url(url) or arxiv_id_from_url(url):
        arxiv_text = _fetch_arxiv_full_text(url)
        if arxiv_text:
            return arxiv_text

    # 1. Live (trafilatura fetch_url + extract)
    try:
        import trafilatura

        cfg = config if config is not None else _FAST_CONFIG
        downloaded = trafilatura.fetch_url(url, config=cfg) if cfg else trafilatura.fetch_url(url)
        if downloaded:
            text = (
                trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    include_formatting=True,
                    config=cfg,
                )
                if cfg
                else trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False,
                    include_formatting=True,
                )
            )
            text = _finalize_extracted_text(text)
            if text:
                return text
    except Exception as e:
        logger.debug("trafilatura fetch failed for %s: %s", url[:80], e)

    # 1b. Same live URL with browser User-Agent (some CDNs block non-browser clients)
    text = _finalize_extracted_text(_fetch_live_with_browser_ua(url))
    if text:
        return text

    # 2. Browser (headless)
    text = _finalize_extracted_text(_fetch_via_browser(url))
    if text:
        return text

    # 3. Wayback
    text = _finalize_extracted_text(_fetch_via_wayback(url))
    if text:
        return text

    # 4. archive.today
    text = _finalize_extracted_text(_fetch_via_archivetoday(url))
    if text:
        return text

    return ""


def enrich_article_content(url: str) -> tuple:
    """Fetch full text for a single URL (for inline use at RSS ingestion).
    Returns (content, success). content is full text or empty string; success is True iff content is non-empty."""
    text = _fetch_full_text(url)
    return (text[:MAX_CONTENT_CHARS] if text else "", bool(text))


def fetch_full_content_for_article(domain_key: str, article_id: int) -> dict[str, Any]:
    """
    On-demand full text for the article reader UI. Persists content and queues re-processing on success.
    Unlike batch enrichment, does not soft-delete the article when extraction fails.
    """
    try:
        import trafilatura  # noqa: F401
    except ImportError:
        return {
            "success": False,
            "not_found": False,
            "message": "Content extraction is not available (trafilatura missing).",
            "content": None,
        }

    from shared.database.connection import get_ui_db_connection_context

    from services.context_processor_service import (
        sync_context_from_article_after_content_change,
    )

    from shared.domain_registry import resolve_domain_schema

    schema_name = resolve_domain_schema(domain_key)

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT url, content FROM {schema_name}.articles WHERE id = %s",
                    (article_id,),
                )
                row = cur.fetchone()
            if not row:
                return {
                    "success": False,
                    "not_found": True,
                    "message": "Article not found",
                    "content": None,
                }
            url, existing = row[0], (row[1] or "")
            existing_stripped = format_article_body_paragraphs(existing.strip())
            # ArXiv abs abstracts are typically 1–2k chars — skip early return so
            # on-demand UI still fetches full PDF/HTML paper text.
            if (
                len(existing_stripped) >= 80
                and not needs_arxiv_fulltext(str(url or ""), existing)
            ):
                return {
                    "success": True,
                    "not_found": False,
                    "message": None,
                    "content": existing_stripped,
                }
            if not url or not str(url).strip():
                return {
                    "success": False,
                    "not_found": False,
                    "message": "Article has no source URL",
                    "content": existing_stripped or None,
                }

            text = _fetch_full_text(str(url).strip(), config=_ONDEMAND_CONFIG)
            if not text:
                return {
                    "success": False,
                    "not_found": False,
                    "message": (
                        "Could not download article text. The site may block automated access, "
                        "require JavaScript, or use a paywall. Try opening the original link."
                    ),
                    "content": existing.strip() or None,
                }
            text = text[:MAX_CONTENT_CHARS]
            if is_false_enriched_body(text):
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {schema_name}.articles SET content = %s, enrichment_status = 'failed',
                            updated_at = NOW() WHERE id = %s""",
                        (text[:2000], article_id),
                    )
                conn.commit()
                return {
                    "success": False,
                    "not_found": False,
                    "message": "Fetched page looks like a paywall, soft-block, or chrome — not stored as enriched.",
                    "content": existing.strip() or None,
                }
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {schema_name}.articles SET content = %s, enrichment_status = 'enriched',
                        updated_at = NOW() WHERE id = %s""",
                    (text, article_id),
                )
                cur.execute(
                    f"UPDATE {schema_name}.articles SET entities = NULL WHERE id = %s",
                    (article_id,),
                )
                cur.execute(
                    f"""
                    INSERT INTO {schema_name}.topic_extraction_queue (article_id, status, priority, created_at)
                    VALUES (%s, 'pending', 3, NOW())
                    ON CONFLICT (article_id) DO UPDATE SET status = 'pending', priority = 3, created_at = NOW()
                    """,
                    (article_id,),
                )
            conn.commit()

        sync_context_from_article_after_content_change(domain_key, article_id)
        return {"success": True, "not_found": False, "message": None, "content": text}
    except Exception as e:
        logger.warning("fetch_full_content_for_article failed: %s", e, exc_info=True)
        return {
            "success": False,
            "not_found": False,
            "message": "Failed to update article content.",
            "content": None,
        }
