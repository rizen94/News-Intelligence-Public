"""
Article content enrichment service (v7).
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
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# Env flags for fallback steps (each optional)
_ENABLE_BROWSER = os.environ.get("ENABLE_BROWSER_ENRICHMENT", "").strip().lower() in ("1", "true", "yes")
_ENABLE_WAYBACK = os.environ.get("ENABLE_WAYBACK_ENRICHMENT", "").strip().lower() in ("1", "true", "yes")
_ENABLE_ARCHIVETODAY = os.environ.get("ENABLE_ARCHIVETODAY_ENRICHMENT", "").strip().lower() in ("1", "true", "yes")

# Rate limit for external fallback requests (seconds)
_WAYBACK_SLEEP = 1.5
_ARCHIVETODAY_SLEEP = 1.5
_FETCH_TIMEOUT = 10

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}

MAX_CONTENT_CHARS = 50_000
MIN_CONTENT_TO_ENRICH = 500
# Burst (48h catch-up): 0.4s between fetches; revert to 0.6 after catch-up
RATE_LIMIT_SLEEP = 0.4


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


def _extract_from_html(html: str) -> str:
    """Extract main text from HTML with trafilatura; return empty if paywall or failure."""
    if not html or len(html.strip()) < 100:
        return ""
    try:
        import trafilatura
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            config=_FAST_CONFIG,
        ) if _FAST_CONFIG else trafilatura.extract(html, include_comments=False, include_tables=False)
        text = (text or "").strip()
        if text and _is_paywall_content(text):
            return ""
        return text
    except Exception as e:
        logger.debug("trafilatura extract from HTML failed: %s", e)
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
        snapshot_url = snap.get("url") or ("https://web.archive.org/web/%s/%s" % (snap.get("timestamp", ""), url))
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


def enrich_articles_batch(batch_size: int = 20) -> int:
    """
    Drain enrichment backlog: select by enrichment_status/attempts, fetch with trafilatura (10s timeout),
    update status and attempts; keep RSS content on failure; prune after 3 attempts.
    Returns count of enriched articles.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed; skipping content enrichment")
        return 0

    from shared.database.connection import get_db_connection, get_db_config
    from services.context_processor_service import update_context_content_for_article

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
        for domain_key, schema_name in DOMAIN_SCHEMA.items():
            if remaining <= 0:
                break
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, url, content
                    FROM {schema_name}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND enrichment_attempts < 3
                      AND url IS NOT NULL AND url != ''
                    ORDER BY enrichment_attempts ASC, created_at DESC
                    LIMIT %s
                    """,
                    (remaining,),
                )
                rows = cur.fetchall()

            for article_id, url, existing_content in rows:
                if remaining <= 0:
                    break
                if not url or not url.strip():
                    continue
                with conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {schema_name}.articles SET enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1, updated_at = NOW() WHERE id = %s""",
                        (article_id,),
                    )
                conn.commit()

                text = _fetch_full_text(url)
                if text:
                    text = text[:MAX_CONTENT_CHARS]
                with conn.cursor() as cur:
                    if text:
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET content = %s, enrichment_status = 'enriched', updated_at = NOW() WHERE id = %s""",
                            (text, article_id),
                        )
                        cur.execute(f"""UPDATE {schema_name}.articles SET entities = NULL WHERE id = %s""", (article_id,))
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
                conn.commit()

                if text:
                    enriched += 1
                    remaining -= 1
                    update_context_content_for_article(domain_key, article_id)

                time.sleep(RATE_LIMIT_SLEEP)

            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {schema_name}.articles SET enrichment_status = 'inaccessible' WHERE enrichment_status = 'failed' AND enrichment_attempts >= 3"""
                )
            conn.commit()

        if enriched > 0:
            logger.info("Content enrichment (v7): %s articles enriched", enriched)
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
    # 1. Live (trafilatura fetch_url + extract)
    try:
        import trafilatura
        cfg = config if config is not None else _FAST_CONFIG
        downloaded = trafilatura.fetch_url(url, config=cfg) if cfg else trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                config=cfg,
            ) if cfg else trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            text = (text or "").strip()
            if text and not _is_paywall_content(text):
                return text
            if text:
                logger.debug("Paywall/subscription content rejected for %s", url[:80])
    except Exception as e:
        logger.debug("trafilatura fetch failed for %s: %s", url[:80], e)

    # 2. Browser (headless)
    text = _fetch_via_browser(url)
    if text:
        return text

    # 3. Wayback
    text = _fetch_via_wayback(url)
    if text:
        return text

    # 4. archive.today
    text = _fetch_via_archivetoday(url)
    if text:
        return text

    return ""


def enrich_article_content(url: str) -> tuple:
    """Fetch full text for a single URL (for inline use at RSS ingestion).
    Returns (content, success). content is full text or empty string; success is True iff content is non-empty."""
    text = _fetch_full_text(url)
    return (text[:MAX_CONTENT_CHARS] if text else "", bool(text))
