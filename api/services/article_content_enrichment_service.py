"""
Article content enrichment service (v8).
Fetches full article text via trafilatura for articles with short or missing content.
After enrichment, triggers re-extraction (entities, topics, context update).
Supports inline enrichment at RSS ingestion and batch backlog drain with attempt tracking.
Rejects paywall/subscription pages so we don't store FT-style "Subscribe to unlock" text as body.
Fallbacks: live -> browser (headless) -> Wayback -> archive.today.
A fetch that cannot produce a full article (≥ fulltext_min_chars) is ``failed``;
after 3 failed attempts the row is ``inaccessible``. Do not soft-delete on first miss.
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
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

from shared.article_text_metrics import compute_word_count

logger = logging.getLogger(__name__)
_ENABLE_BROWSER = env_str("ENABLE_BROWSER_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_ENABLE_WAYBACK = env_str("ENABLE_WAYBACK_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
_ENABLE_ARCHIVETODAY = env_str("ENABLE_ARCHIVETODAY_ENRICHMENT", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Rate limit for external fallback requests (seconds)
_WAYBACK_SLEEP = 1.5
_ARCHIVETODAY_SLEEP = 1.5
_FETCH_TIMEOUT = 10

MAX_CONTENT_CHARS = 50_000
# Historical skip-fetch floor; live skip uses fulltext_min_chars() (default 900).
MIN_CONTENT_TO_ENRICH = 500
# Drop intake pass markers when we replace a teaser with a real body so UIE re-runs.
_CLEAR_INTAKE_PASS_MARKERS = (
    "COALESCE(metadata, '{}'::jsonb)"
    " #- '{pipeline,unified_intake_extraction}'"
    " #- '{pipeline,entity_extraction}'"
    " #- '{pipeline,event_extraction}'"
)

_topic_queue_cache: dict[str, bool] = {}


def _topic_extraction_queue_available(conn, schema_name: str) -> bool:
    """Some domain schemas (legal, medicine) lacked topic_extraction_queue until migration 236."""
    if schema_name in _topic_queue_cache:
        return _topic_queue_cache[schema_name]
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'topic_extraction_queue'
                """,
                (schema_name,),
            )
            ok = cur.fetchone() is not None
    except Exception:
        ok = False
    _topic_queue_cache[schema_name] = ok
    return ok


def _enqueue_topic_extraction(cur, schema_name: str, article_id: int) -> None:
    cur.execute(
        f"""
        INSERT INTO {schema_name}.topic_extraction_queue (article_id, status, priority, created_at)
        VALUES (%s, 'pending', 3, NOW())
        ON CONFLICT (article_id) DO UPDATE SET status = 'pending', priority = 3, created_at = NOW()
        """,
        (article_id,),
    )
# Burst (48h catch-up): base pause between host slots; parallel workers share the budget.
RATE_LIMIT_SLEEP = 0.4


def _enrichment_fetch_parallel() -> int:
    try:
        return max(1, min(16, int(env_str("CONTENT_ENRICHMENT_FETCH_PARALLEL", "8"))))
    except ValueError:
        return 8


def _enrichment_per_host_limit() -> int:
    try:
        return max(1, min(4, int(env_str("CONTENT_ENRICHMENT_PER_HOST_LIMIT", "2"))))
    except ValueError:
        return 2


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
    # Bloomberg / WSJ / Economist subscribe chrome
    "bloomberg.com/subscriptions",
    "already a subscriber",
    "sign in to continue reading",
    "create a bloomberg account",
    "subscribe to bloomberg",
    "to continue reading this article",
    "this article is for subscribers",
    "wsj.com/subscribe",
    "subscribe to wsj",
    "subscriber content",
    "economist.com/subscribe",
    "subscribe to the economist",
)

# Known hard-paywall publishers: try archives even when global ENABLE_* is off.
_KNOWN_PAYWALL_HOST_FRAGMENTS = (
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "economist.com",
    "barrons.com",
    "marketwatch.com",
    "nytimes.com",
    "washingtonpost.com",
    "theathletic.com",
    "businessinsider.com",
)

# Headline-only / paywall terminal demotion (never UIE-eligible).
HEADLINE_ONLY_QUALITY_CAP = 0.20


def is_known_paywall_host(url: str | None) -> bool:
    """True when URL host matches a known hard-paywall publisher."""
    if not url:
        return False
    try:
        from urllib.parse import urlparse

        host = (urlparse(url).netloc or "").lower()
    except Exception:
        host = (url or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return any(frag in host for frag in _KNOWN_PAYWALL_HOST_FRAGMENTS)


def _archives_enabled_for_url(url: str | None) -> bool:
    """Global archive flags, or auto-enable for known paywall hosts."""
    if _ENABLE_WAYBACK or _ENABLE_ARCHIVETODAY:
        return True
    return is_known_paywall_host(url)

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
    text = (text or "").strip()
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


def _fetch_via_wayback(url: str, *, force: bool = False) -> str:
    """Try to get article text from an Internet Archive (Wayback) snapshot. Returns empty on failure or paywall."""
    if not force and not _ENABLE_WAYBACK:
        return ""
    if not url or not url.strip():
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


def _fetch_via_archivetoday(url: str, *, force: bool = False) -> str:
    """Try to get article text from an archive.today (Memento) snapshot. Returns empty on failure or paywall."""
    if not force and not _ENABLE_ARCHIVETODAY:
        return ""
    if not url or not url.strip():
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
            if _topic_extraction_queue_available(conn, schema_name):
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


def enrich_articles_batch(
    batch_size: int = 20,
    *,
    scoped_ids_by_schema: dict[str, list[int]] | None = None,
) -> int:
    """
    Drain enrichment backlog: select by enrichment_status/attempts, fetch with trafilatura (10s timeout),
    update status and attempts; keep RSS content on failure; mark failed when fetch is
    below the fulltext bar; ``inaccessible`` after 3 attempts.
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
    from shared.domain_registry import pipeline_url_schema_pairs

    from shared.article_processing_gates import (
        body_is_fulltext,
    )
    from shared.pipeline_article_selection import sql_order_created_at

    from services.context_processor_service import (
        sync_context_from_article_after_content_change,
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
        removed = 0
        remaining = batch_size
        pairs = list(pipeline_url_schema_pairs())
        if not pairs:
            return 0
        if scoped_ids_by_schema:
            work_pairs = [
                (dk, sch)
                for dk, sch in pairs
                if scoped_ids_by_schema.get(sch)
            ]
        else:
            work_pairs = pairs
        n_domains = max(1, len(work_pairs))
        share = max(1, (batch_size + n_domains - 1) // n_domains)
        _ca_ord = sql_order_created_at()
        batch_commit_every = 10
        pending_commits = 0

        def _reopen_conn():
            nonlocal conn
            c = get_db_connection()
            if c:
                with c.cursor() as cur:
                    cur.execute("SET statement_timeout = '300s'")
            conn = c
            return conn

        def _release_conn_for_fetch():
            nonlocal conn
            _flush_commit(force=True)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            conn = None

        def _flush_commit(force: bool = False) -> None:
            nonlocal pending_commits
            if force or pending_commits >= batch_commit_every:
                conn.commit()
                pending_commits = 0

        for domain_key, schema_name in work_pairs:
            if remaining <= 0:
                break
            # Title-only triage for ClinicalTrials.gov etc. before spending fetch budget.
            try:
                from shared.fulltext_pull_gate import triage_thin_link_articles

                triage_thin_link_articles(
                    conn,
                    domain_key=domain_key,
                    schema_name=schema_name,
                    limit=max(10, min(80, share * 2)),
                )
            except Exception as triage_e:
                logger.debug("fulltext_pull triage %s: %s", domain_key, triage_e)

            scoped_ids = None
            if scoped_ids_by_schema:
                scoped_ids = scoped_ids_by_schema.get(schema_name) or []
                if not scoped_ids:
                    continue
                fetch_limit = len(scoped_ids)
            else:
                fetch_limit = min(share, remaining)
            # Historical short-enriched teasers stay parked until an operator
            # reset (e.g. reset_teaser_enrichment_for_fulltext.py --in-storyline).
            needs_fetch = """(
                enrichment_status IS NULL
                OR enrichment_status IN ('pending', 'failed')
            )"""
            with conn.cursor() as cur:
                if scoped_ids:
                    cur.execute(
                        f"""
                        SELECT id, url, content, created_at, enrichment_status
                        FROM {schema_name}.articles
                        WHERE id = ANY(%s)
                          AND {needs_fetch}
                          AND COALESCE(enrichment_attempts, 0) < 3
                          AND url IS NOT NULL AND url != ''
                        ORDER BY COALESCE(enrichment_attempts, 0) ASC, created_at {_ca_ord}
                        """,
                        (scoped_ids,),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT id, url, content, created_at, enrichment_status
                        FROM {schema_name}.articles
                        WHERE {needs_fetch}
                          AND COALESCE(enrichment_attempts, 0) < 3
                          AND url IS NOT NULL AND url != ''
                        ORDER BY COALESCE(enrichment_attempts, 0) ASC, created_at {_ca_ord}
                        LIMIT %s
                        """,
                        (fetch_limit,),
                    )
                rows = cur.fetchall()

            to_fetch: list[tuple[int, str, str | None, str | None]] = []
            for article_id, url, existing_content, created_at, row_status in rows:
                if remaining <= 0:
                    break
                if not url or not url.strip():
                    continue
                # Thin-link pending that somehow skipped triage: decide pull vs defer now.
                try:
                    from shared.fulltext_pull_gate import (
                        STATUS_PULL_DEFERRED,
                        evaluate_fulltext_pull,
                        is_thin_link_host,
                    )

                    if is_thin_link_host(url) and (
                        row_status is None or (row_status or "").strip() in ("pending", "failed")
                    ):
                        # Need title for scoring — load lightly if gate applies.
                        with conn.cursor() as tcur:
                            tcur.execute(
                                f"SELECT title, quality_score FROM {schema_name}.articles WHERE id = %s",
                                (article_id,),
                            )
                            trow = tcur.fetchone()
                        title = trow[0] if trow else ""
                        q = float(trow[1]) if trow and trow[1] is not None else None
                        verdict = evaluate_fulltext_pull(
                            title=title,
                            url=url,
                            content=existing_content,
                            domain_key=domain_key,
                            schema=schema_name,
                            quality_score=q,
                        )
                        if verdict.get("decision") == "defer":
                            with conn.cursor() as ucur:
                                ucur.execute(
                                    f"""
                                    UPDATE {schema_name}.articles
                                    SET enrichment_status = %s,
                                        metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                                        updated_at = NOW()
                                    WHERE id = %s
                                    """,
                                    (
                                        STATUS_PULL_DEFERRED,
                                        json.dumps(
                                            {
                                                "fulltext_pull": {
                                                    "triaged": True,
                                                    "decision": "defer",
                                                    "reason": verdict.get("reason"),
                                                }
                                            }
                                        ),
                                        article_id,
                                    ),
                                )
                            pending_commits += 1
                            _flush_commit()
                            continue
                except Exception as gate_e:
                    logger.debug("inline fulltext gate %s/%s: %s", domain_key, article_id, gate_e)

                # Already have a full article body: promote to enriched, do not re-fetch.
                if (
                    existing_content
                    and body_is_fulltext(existing_content)
                    and (row_status is None or (row_status or "").strip() in ("pending", "failed"))
                ):
                    fast_rows = 0
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
                            sync_context_from_article_after_content_change(domain_key, article_id)
                        except Exception as ctx_e:
                            logger.debug(
                                "enrichment fast-path context %s/%s: %s",
                                domain_key,
                                article_id,
                                ctx_e,
                            )
                    time.sleep(RATE_LIMIT_SLEEP / max(1, _enrichment_fetch_parallel()))
                    continue
                to_fetch.append((int(article_id), str(url).strip(), existing_content, row_status))
                if len(to_fetch) >= remaining:
                    break

            if not to_fetch:
                continue

            # Bump attempts for the whole fetch set, then release the DB connection.
            fetch_ids = [aid for aid, *_ in to_fetch]
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {schema_name}.articles
                    SET enrichment_attempts = COALESCE(enrichment_attempts, 0) + 1,
                        updated_at = NOW()
                    WHERE id = ANY(%s)
                    """,
                    (fetch_ids,),
                )
            conn.commit()
            _release_conn_for_fetch()

            from concurrent.futures import ThreadPoolExecutor, as_completed
            from collections import defaultdict
            from threading import Semaphore
            from urllib.parse import urlparse

            host_limit = _enrichment_per_host_limit()
            host_gates: dict[str, Semaphore] = defaultdict(lambda: Semaphore(host_limit))
            workers = min(_enrichment_fetch_parallel(), max(1, len(to_fetch)))
            pause = RATE_LIMIT_SLEEP / max(1, workers)

            def _fetch_one(item: tuple[int, str, str | None, str | None]) -> tuple[int, str, str]:
                article_id, url, _ec, _st = item
                host = (urlparse(url).netloc or "").lower() or "_"
                with host_gates[host]:
                    text = _fetch_full_text(url) or ""
                    if pause > 0:
                        time.sleep(pause)
                    return article_id, url, text[:MAX_CONTENT_CHARS] if text else ""

            fetched: list[tuple[int, str, str]] = []
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_fetch_one, item) for item in to_fetch]
                for fut in as_completed(futures):
                    try:
                        fetched.append(fut.result())
                    except Exception as e:
                        logger.debug("enrichment parallel fetch failed: %s", e)

            if not _reopen_conn():
                logger.warning(
                    "Content enrichment: no DB connection after parallel fetch (%s items)",
                    len(to_fetch),
                )
                continue

            for article_id, url, text in fetched:
                if remaining <= 0:
                    break
                with conn.cursor() as cur:
                    from shared.fulltext_pull_gate import is_clinicaltrials_boilerplate

                    usable = (
                        bool(text)
                        and not is_clinicaltrials_boilerplate(text)
                        and body_is_fulltext(text)
                    )
                    if usable:
                        wc = compute_word_count(text)
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET content = %s, word_count = %s,
                                enrichment_status = 'enriched',
                                metadata = {_CLEAR_INTAKE_PASS_MARKERS},
                                updated_at = NOW() WHERE id = %s""",
                            (text, wc, article_id),
                        )
                        cur.execute(
                            f"""UPDATE {schema_name}.articles SET entities = NULL WHERE id = %s""",
                            (article_id,),
                        )
                        if _topic_extraction_queue_available(conn, schema_name):
                            _enqueue_topic_extraction(cur, schema_name, article_id)
                        pending_commits += 1
                        _flush_commit()
                        enriched += 1
                        remaining -= 1
                        try:
                            sync_context_from_article_after_content_change(domain_key, article_id)
                        except Exception as ctx_e:
                            logger.debug(
                                "enrichment context %s/%s: %s",
                                domain_key,
                                article_id,
                                ctx_e,
                            )
                    elif body_is_fulltext(
                        next((ec for aid, _u, ec, _st in to_fetch if aid == article_id), None)
                    ):
                        # Fetch missed but RSS/DB already has a full article — do not fail it.
                        cur.execute(
                            f"""UPDATE {schema_name}.articles
                                SET enrichment_status = 'enriched', updated_at = NOW()
                                WHERE id = %s""",
                            (article_id,),
                        )
                        pending_commits += 1
                        _flush_commit()
                        enriched += 1
                        remaining -= 1
                    else:
                        # Paywall, 403, chrome, or short scrape: keep teaser, fail + demote quality.
                        fetch_url = next(
                            (u for aid, u, _ec, _st in to_fetch if aid == article_id),
                            "",
                        )
                        demote_meta = {
                            "headline_only": True,
                            "paywall_or_teaser": True,
                            "paywall_host": is_known_paywall_host(fetch_url),
                        }
                        cur.execute(
                            f"""UPDATE {schema_name}.articles
                                SET enrichment_status = 'failed',
                                    quality_score = LEAST(
                                        COALESCE(quality_score, %s),
                                        %s
                                    ),
                                    metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                                    updated_at = NOW()
                                WHERE id = %s""",
                            (
                                HEADLINE_ONLY_QUALITY_CAP,
                                HEADLINE_ONLY_QUALITY_CAP,
                                json.dumps(demote_meta),
                                article_id,
                            ),
                        )
                        pending_commits += 1
                        _flush_commit()
                        removed += 1
                        remaining -= 1

            _flush_commit(force=True)

        for _dk, sch in pairs:
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {sch}.articles
                       SET enrichment_status = 'inaccessible',
                           quality_score = LEAST(
                               COALESCE(quality_score, %s),
                               %s
                           ),
                           metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb
                       WHERE enrichment_status = 'failed'
                         AND enrichment_attempts >= 3""",
                    (
                        HEADLINE_ONLY_QUALITY_CAP,
                        HEADLINE_ONLY_QUALITY_CAP,
                        json.dumps(
                            {
                                "headline_only": True,
                                "paywall_or_teaser": True,
                            }
                        ),
                    ),
                )
            pending_commits += 1
        _flush_commit(force=True)

        handled = enriched + removed
        if enriched > 0 or removed > 0:
            logger.info(
                "Content enrichment (v8): %s enriched, %s failed/inaccessible (parallel=%s)",
                enriched,
                removed,
                _enrichment_fetch_parallel(),
            )
        # Return handled count so stall detection sees paywall drain as progress
        return handled
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
    Returns empty string when all attempted paths fail or return paywall content.

    ClinicalTrials.gov and other thin-link hosts use the registry API first — HTML/RSS
    bodies are title junk / study-manager boilerplate.
    """
    try:
        from shared.fulltext_pull_gate import is_clinicaltrials_boilerplate, is_thin_link_host

        if is_thin_link_host(url):
            from services.clinicaltrials_study_fetch import fetch_clinicaltrials_study_body

            text, ok = fetch_clinicaltrials_study_body(url)
            if ok and text and not is_clinicaltrials_boilerplate(text):
                finalized = _finalize_extracted_text(text) or text.strip()
                if finalized and len(finalized) >= 80:
                    return finalized
            # Do not fall through to trafilatura — it only captures CT.gov chrome.
            return ""
    except Exception as e:
        logger.debug("thin-link registry fetch for %s: %s", (url or "")[:80], e)

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

    force_archives = _archives_enabled_for_url(url)
    # Known paywall hosts: try archives before spending on headless browser.
    if is_known_paywall_host(url):
        text = _finalize_extracted_text(_fetch_via_wayback(url, force=True))
        if text:
            return text
        text = _finalize_extracted_text(_fetch_via_archivetoday(url, force=True))
        if text:
            return text

    # 2. Browser (headless)
    text = _finalize_extracted_text(_fetch_via_browser(url))
    if text:
        return text

    # 3. Wayback
    text = _finalize_extracted_text(
        _fetch_via_wayback(url, force=force_archives or _ENABLE_WAYBACK)
    )
    if text:
        return text

    # 4. archive.today
    text = _finalize_extracted_text(
        _fetch_via_archivetoday(url, force=force_archives or _ENABLE_ARCHIVETODAY)
    )
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
            from shared.article_processing_gates import body_is_fulltext

            if body_is_fulltext(existing_stripped):
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
            if not body_is_fulltext(text):
                return {
                    "success": False,
                    "not_found": False,
                    "message": (
                        "Downloaded text is still a teaser or paywall chrome, not a full article."
                    ),
                    "content": existing.strip() or None,
                }
            wc = compute_word_count(text)
            with conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {schema_name}.articles SET content = %s, word_count = %s,
                        enrichment_status = 'enriched',
                        metadata = {_CLEAR_INTAKE_PASS_MARKERS},
                        updated_at = NOW() WHERE id = %s""",
                    (text, wc, article_id),
                )
                cur.execute(
                    f"UPDATE {schema_name}.articles SET entities = NULL WHERE id = %s",
                    (article_id,),
                )
                if _topic_extraction_queue_available(conn, schema_name):
                    _enqueue_topic_extraction(cur, schema_name, article_id)
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
