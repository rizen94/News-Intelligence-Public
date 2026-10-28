"""
External research ingest — n8n / SearXNG / vault notes → processed_document members.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

from config.runtime import external_research_ingest_enabled
from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_attach_gate import attach_allowed, storyline_title_from_package

from services.editorial_package_service import add_member, get_package

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    try:
        p = urlparse(u)
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))
    except Exception:
        return u.lower().strip()


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _url_already_on_package(cur, package_id: int, url: str) -> bool:
    norm = _normalize_url(url)
    if not norm:
        return False
    cur.execute(
        """
        SELECT 1 FROM intelligence.editorial_package_members m
        WHERE m.package_id = %s AND m.status = 'active'
          AND (
            COALESCE(m.provenance->>'source_url', '') ILIKE %s
            OR COALESCE(m.provenance->>'url', '') ILIKE %s
          )
        LIMIT 1
        """,
        (int(package_id), f"%{norm.split('//')[-1]}%", f"%{norm.split('//')[-1]}%"),
    )
    if cur.fetchone():
        return True
    cur.execute(
        """
        SELECT 1 FROM intelligence.processed_documents d
        WHERE COALESCE(d.metadata->>'normalized_url', d.source_url, '') = %s
           OR d.source_url = %s
        LIMIT 1
        """,
        (norm, url),
    )
    return bool(cur.fetchone())


def _domain_exclusions(cur, domain_key: str) -> list[str]:
    try:
        cur.execute(
            """
            SELECT topic_filter FROM intelligence.domain_synthesis_config
            WHERE domain_key = %s LIMIT 1
            """,
            (domain_key,),
        )
        row = cur.fetchone()
        if not row:
            return []
        tf = row[0] if isinstance(row[0], dict) else {}
        ex = tf.get("exclude_keywords") or []
        return [str(x).lower() for x in ex if x]
    except Exception:
        return []


def attach_external_research(
    package_id: int,
    items: list[dict[str, Any]],
    *,
    actor: str = "n8n_external_research",
) -> dict[str, Any]:
    if not external_research_ingest_enabled():
        return {"ok": False, "error": "external_research_ingest disabled"}

    pkg = get_package(package_id, include=True) or {}
    if not pkg:
        raise LookupError(f"package {package_id} not found")
    modal = str(pkg.get("primary_modal") or "research")
    dk = (pkg.get("domain_keys") or [None])[0]
    title = str(pkg.get("working_title") or "")
    stub = str(pkg.get("summary_stub") or "")
    storyline_title = storyline_title_from_package(pkg)

    attached: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            exclusions = _domain_exclusions(cur, str(dk or ""))
            for item in items:
                url = str(item.get("url") or "").strip()
                label = str(item.get("title") or url)[:240]
                if not url:
                    skipped.append({"url": url, "reason": "missing_url"})
                    continue
                blob = f"{label} {item.get('summary_text') or ''} {url}".lower()
                if any(x and x in blob for x in exclusions):
                    skipped.append({"url": url, "reason": "excluded_keyword"})
                    continue
                if _url_already_on_package(cur, package_id, url):
                    deduped.append({"url": url})
                    continue
                quotes = item.get("quotes") or []
                quote = None
                if isinstance(quotes, list):
                    for q in quotes:
                        if isinstance(q, str) and q.strip() and q.strip().lower() != label.lower():
                            quote = q.strip()[:500]
                            break
                prov = {
                    "label": label,
                    "source_url": url,
                    "quote": quote,
                    "origin": "searxng",
                    "vault_note_path": item.get("vault_note_path"),
                    "captured_at": item.get("captured_at"),
                }
                ok, flags = attach_allowed(
                    title=title,
                    stub=stub,
                    provenance=prov,
                    member_type="processed_document",
                    storyline_title=storyline_title,
                )
                if not ok:
                    skipped.append({"url": url, "reason": "theme_gate", "flags": flags})
                    continue
                meta = {
                    "origin": "searxng",
                    "package_id": package_id,
                    "vault_note_path": item.get("vault_note_path"),
                    "captured_at": item.get("captured_at"),
                    "normalized_url": _normalize_url(url),
                    "entities": item.get("entities") or [],
                }
                cur.execute(
                    """
                    INSERT INTO intelligence.processed_documents
                        (title, source_url, metadata, source_type, source_name, document_type)
                    VALUES (%s, %s, %s::jsonb, 'web_capture', 'searxng', 'web_page')
                    RETURNING id
                    """,
                    (label, url, json.dumps(meta)),
                )
                doc_row = cur.fetchone()
                doc_id = int(doc_row[0])
                member = add_member(
                    package_id,
                    member_type="processed_document",
                    member_id=doc_id,
                    member_family="research" if modal == "research" else "narrative",
                    domain_key=dk,
                    role="supporting",
                    added_by_modal="system",
                    added_by=actor,
                    provenance=prov,
                    actor=actor,
                )
                attached.append({"url": url, "document_id": doc_id, "member_id": member.get("id")})
            conn.commit()

    republish: dict[str, Any] | None = None
    if attached:
        try:
            from services.news_story_service import auto_republish_for_new_members

            republish = auto_republish_for_new_members(
                int(package_id),
                actor=actor,
            )
        except Exception as e:
            logger.warning("external_research auto_republish failed package=%s: %s", package_id, e)
            republish = {"skipped": True, "error": str(e)}

    return {
        "ok": True,
        "package_id": package_id,
        "attached": attached,
        "skipped": skipped,
        "deduped": deduped,
        "auto_republish": republish,
    }
