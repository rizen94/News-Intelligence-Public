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

        text = (
            trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
                config=_FAST_CONFIG,
            )
            if _FAST_CONFIG
            else trafilatura.extract(html, include_comments=False, include_tables=False)
        )
        text = (text or "").strip()
        if text and _is_paywall_content(text):
            return ""
        return text
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


def enrich_articles_batch(batch_size: int = 20) -> int:
    """
    Drain enrichment backlog: select by enrichment_status/attempts, fetch with trafilatura (10s timeout),
    update status and attempts; keep RSS content on failure; prune after 3 attempts.
    Returns count of enriched articles.

    Fair share: each active domain may fetch up to ceil(batch_size / n_domains) candidates per call
    (capped by remaining success budget), so high display_order silos are not starved by earlier domains.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed; skipping content enrichment")
        return 0

    from shared.database.connection import get_db_config, get_db_connection
    from shared.domain_registry import url_schema_pairs

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
        pairs = list(url_schema_pairs())
        if not pairs:
            return 0
        n_domains = len(pairs)
        share = max(1, (batch_size + n_domains - 1) // n_domains)

        for domain_key, schema_name in pairs:
            if remaining <= 0:
                break
            fetch_limit = min(share, remaining)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, url, content
                    FROM {schema_name}.articles
                    WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                      AND COALESCE(enrichment_attempts, 0) < 3
                      AND url IS NOT NULL AND url != ''
                    ORDER BY COALESCE(enrichment_attempts, 0) ASC, created_at DESC
                    LIMIT %s
                    """,
                    (fetch_limit,),
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
                conn.commit()

                if text:
                    enriched += 1
                    remaining -= 1
                    update_context_content_for_article(domain_key, article_id)

                time.sleep(RATE_LIMIT_SLEEP)

        for _dk, sch in pairs:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {sch}.articles SET enrichment_status = 'inaccessible' WHERE enrichment_status = 'failed' AND enrichment_attempts >= 3"""
                )
            conn.commit()

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
                    config=cfg,
                )
                if cfg
                else trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            )
            text = (text or "").strip()
            if text and not _is_paywall_content(text):
                return text
            if text:
                logger.debug("Paywall/subscription content rejected for %s", url[:80])
    except Exception as e:
        logger.debug("trafilatura fetch failed for %s: %s", url[:80], e)

    # 1b. Same live URL with browser User-Agent (some CDNs block non-browser clients)
    text = _fetch_live_with_browser_ua(url)
    if text:
        return text

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

    from services.context_processor_service import update_context_content_for_article

    schema_name = domain_key.replace("-", "_")

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
            if not url or not str(url).strip():
                return {
                    "success": False,
                    "not_found": False,
                    "message": "Article has no source URL",
                    "content": existing.strip() or None,
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

        update_context_content_for_article(domain_key, article_id)
        return {"success": True, "not_found": False, "message": None, "content": text}
    except Exception as e:
        logger.warning("fetch_full_content_for_article failed: %s", e, exc_info=True)
        return {
            "success": False,
            "not_found": False,
            "message": "Failed to update article content.",
            "content": None,
        }
