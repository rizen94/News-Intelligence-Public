"""
Optional web research for morning storyline expansions.

Generates 1–3 search queries from title/anchors, fetches a few public pages
via trafilatura / urllib, returns prompt excerpts. Never blocks morning prime
on failure. Governance via env caps.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from shared.vault_note_contract import MORNING_WEB_MAX_URLS_PER_STORY

logger = logging.getLogger(__name__)

_UA = "NewsIntelligenceMorningPrime/1.0 (+https://news-intelligence-ag.duckdns.org)"


def morning_web_research_enabled() -> bool:
    raw = os.environ.get("NI_MORNING_WEB_RESEARCH", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    # Default on when morning prime runs — light fetch only
    return True


def _max_urls() -> int:
    try:
        return max(0, min(5, int(os.environ.get("MORNING_WEB_MAX_URLS", MORNING_WEB_MAX_URLS_PER_STORY))))
    except ValueError:
        return MORNING_WEB_MAX_URLS_PER_STORY


def build_search_queries(
    *,
    title: str,
    domain_key: str,
    anchor_entities: list[str] | None = None,
) -> list[str]:
    ents = [e.strip() for e in (anchor_entities or []) if e and str(e).strip()][:3]
    base = (title or "").strip()[:120]
    qs = []
    if base:
        qs.append(f"{base} latest news")
    if ents:
        qs.append(f"{' '.join(ents)} {domain_key} update")
    if base and ents:
        qs.append(f"{ents[0]} {base.split()[0] if base.split() else ''} news")
    # dedupe
    seen: set[str] = set()
    out: list[str] = []
    for q in qs:
        qn = " ".join(q.split())
        if qn.lower() in seen or len(qn) < 6:
            continue
        seen.add(qn.lower())
        out.append(qn)
    return out[:3]


def _duckduckgo_html_links(query: str, *, limit: int = 3) -> list[str]:
    """Lightweight HTML search — no API key. Best-effort."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("ddg search failed: %s", e)
        return []
    links: list[str] = []
    for m in re.finditer(r'uddg=([^&"]+)', html):
        try:
            target = urllib.parse.unquote(m.group(1))
        except Exception:
            continue
        if not target.startswith("http"):
            continue
        if "duckduckgo.com" in target:
            continue
        if target in links:
            continue
        links.append(target)
        if len(links) >= limit:
            break
    return links


def _fetch_text(url: str, *, max_chars: int = 2500) -> str:
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False) or ""
            return text.strip()[:max_chars]
    except Exception as e:
        logger.debug("trafilatura %s: %s", url[:80], e)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read(120_000).decode("utf-8", errors="replace")
        # crude strip
        text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception as e:
        logger.debug("fetch %s: %s", url[:80], e)
        return ""


def research_web_for_storyline(
    *,
    title: str,
    domain_key: str,
    storyline_id: int,
    anchor_entities: list[str] | None = None,
) -> dict[str, Any]:
    """Return web_evidence text + url list for the expansion prompt."""
    if not morning_web_research_enabled() or _max_urls() <= 0:
        return {
            "ok": True,
            "skipped": True,
            "evidence_text": "",
            "urls": [],
            "queries": [],
        }
    queries = build_search_queries(
        title=title, domain_key=domain_key, anchor_entities=anchor_entities
    )
    urls: list[str] = []
    for q in queries:
        for u in _duckduckgo_html_links(q, limit=2):
            if u not in urls:
                urls.append(u)
            if len(urls) >= _max_urls():
                break
        if len(urls) >= _max_urls():
            break

    chunks: list[str] = []
    used_urls: list[str] = []
    for u in urls:
        text = _fetch_text(u)
        if len(text) < 120:
            continue
        chunks.append(f"Source: {u}\n{text[:2000]}")
        used_urls.append(u)
        if len(chunks) >= _max_urls():
            break

    evidence = "\n\n".join(chunks)[:8000]
    return {
        "ok": True,
        "skipped": False,
        "evidence_text": evidence,
        "urls": used_urls,
        "queries": queries,
        "storyline_id": storyline_id,
        "domain_key": domain_key,
    }
