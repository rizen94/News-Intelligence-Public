"""Enrich vault notes with grounded Wikipedia evidence (wiki RAG).

Uses the existing Wikipedia knowledge path:
  - local ``intelligence.wikipedia_knowledge`` (dump / preseed cache)
  - MediaWiki REST summary fallback via ``lookup_entity_with_fallback``

Writes a replaceable ``## Wikipedia background`` section with citation URLs.
Does **not** call LLMs — only retrieved extracts.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

WIKI_SECTION_HEADER = "## Wikipedia background"
_WIKI_SECTION_RE = re.compile(
    r"\n## Wikipedia background\n(?:.*?)(?=\n## |\Z)",
    re.S,
)

# Priority Situation hubs → Wikipedia search terms (grounded titles, not prose).
PRIORITY_HUB_QUERIES: dict[str, list[str]] = {
    "us_institutions": [
        "Federal government of the United States",
        "United States Department of Justice",
        "United States Congress",
        "Supreme Court of the United States",
        "White House",
    ],
    "china_trade_tech": [
        "China–United States trade war",
        "Rare-earth element",
        "Semiconductor industry",
        "CHIPS and Science Act",
    ],
    "russia_ukraine": [
        "Russo-Ukrainian War",
        "Russian invasion of Ukraine",
        "NATO",
        "Volodymyr Zelenskyy",
    ],
    "climate_resource_policy": [
        "Climate change",
        "Critical raw materials",
        "Energy transition",
        "Paris Agreement",
    ],
    "farage_reform_boats": [
        "Nigel Farage",
        "Reform UK",
        "English Channel migrant crossings",
    ],
    "venezuela_boe_gold": [
        "Bank of England",
        "Venezuela",
        "Gold reserve",
    ],
    "ai_governance": [
        "Regulation of artificial intelligence",
        "OpenAI",
        "AI safety",
        "Artificial Intelligence Act",
    ],
    "market_trends": [
        "Federal Reserve",
        "United States Consumer Price Index",
        "Bond market",
        "Foreign exchange market",
    ],
    "resource_movements": [
        "Petroleum",
        "Strait of Hormuz",
        "OPEC",
        "Gold as an investment",
    ],
    "iran_war": [
        "Iran",
        "Iran–Israel proxy conflict",
        "Strait of Hormuz",
        "Islamic Revolutionary Guard Corps",
    ],
    "inflation_iran_war": [
        "Inflation",
        "Price of oil",
        "Iran",
    ],
}

DEFAULT_PRIORITY_HUBS = tuple(PRIORITY_HUB_QUERIES.keys())

# Living entities seeded recently / high priority for wiki background.
PRIORITY_ENTITY_TITLES: tuple[str, ...] = (
    "Federal Reserve",
    "oil",
    "gold",
    "OPEC+",
    "Strait of Hormuz",
    "Iran",
    "China",
    "Israel",
    "NATO",
    "OpenAI",
    "Anthropic",
    "White House",
    "Congress",
    "FBI",
    "United Nations",
    "Vladimir Putin",
    "Donald J. Trump",
    "Nigel Farage",
    "Venezuela",
    "State Department",
    "Department of Justice",
    "Department of Defense",
    "European Union",
    "European Central Bank",
    "Bank of England",
    "Saudi Arabia",
    "Ukraine",
    "Russia",
    "Taiwan",
    "Semiconductor",
    "NVIDIA",
    "Google DeepMind",
    "Meta AI",
)

# Ambiguous vault titles → preferred Wikipedia lookup title
ENTITY_WIKI_QUERY_OVERRIDE: dict[str, str] = {
    "Congress": "United States Congress",
    "oil": "Petroleum",
    "gold": "Gold",
    "OPEC+": "OPEC",
    "ICE": "U.S. Immigration and Customs Enforcement",
    "Senate": "United States Senate",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "to",
        "as",
        "an",
        "united",
        "states",
    }
)


def _query_tokens(query: str) -> set[str]:
    toks = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", query or "") if len(t) > 2}
    return toks - _STOP


def _titles_close(query: str, title: str) -> bool:
    qn = re.sub(r"[\s\-–—]+", " ", (query or "").lower()).strip()
    tn = re.sub(r"[\s\-–—]+", " ", (title or "").lower()).strip()
    if not qn or not tn:
        return False
    if qn == tn or qn in tn or tn in qn:
        return True
    qtoks = _query_tokens(query)
    if len(qtoks) >= 2:
        return sum(1 for t in qtoks if t in tn) >= max(2, (len(qtoks) + 1) // 2)
    only = next(iter(qtoks), "")
    return len(only) >= 4 and only in tn


def _hit_relevant(title: str, extract: str, query: str) -> bool:
    """Reject noisy local-FTS matches (title must share meaningful tokens with query)."""
    del extract  # title gate only — extracts can mention anything
    return _titles_close(query, title)


def _normalize_hit(
    raw: dict[str, Any],
    *,
    query: str,
    require_title_match: bool = True,
) -> dict[str, Any] | None:
    title = str(raw.get("title") or "").strip()
    extract = str(raw.get("extract") or raw.get("summary") or raw.get("abstract") or "").strip()
    if not title or not extract or len(extract) < 40:
        return None
    if require_title_match and not _hit_relevant(title, extract, query):
        return None
    url = str(raw.get("url") or raw.get("page_url") or "").strip()
    if not url and raw.get("page_id"):
        url = f"https://en.wikipedia.org/wiki/?curid={raw['page_id']}"
    if not url:
        from urllib.parse import quote

        url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
    return {
        "query": query,
        "title": title,
        "extract": extract[:1600],
        "url": url,
        "page_id": raw.get("page_id") or raw.get("pageid"),
        "source": "wikipedia",
    }


def _api_summary_for_query(query: str) -> dict[str, Any] | None:
    """Wikipedia REST summary for query (or first search hit). Closes no DB handles."""
    try:
        from modules.ml.rag_external_services import WikipediaService

        wiki = WikipediaService()
        summary = wiki.get_article_summary(query)
        if summary and summary.get("extract"):
            return summary
        results = wiki.search_articles(query, limit=1) or []
        if results:
            title = results[0].get("title") or ""
            if title:
                summary = wiki.get_article_summary(title)
                if summary and summary.get("extract"):
                    return summary
    except Exception as e:
        logger.debug("wiki api summary %s: %s", query[:60], e)
    return None


def retrieve_wiki_hits(
    queries: list[str],
    *,
    max_hits: int = 5,
    allow_api_fallback: bool = True,
) -> list[dict[str, Any]]:
    """Retrieve Wikipedia summaries for queries; dedupe by title.

    Prefer Wikipedia REST summary (grounded). Local ``wikipedia_knowledge`` is
    used only when the stored title is a close match to the query — avoiding
    noisy FTS false positives from the dump.
    """
    from services.wikipedia_knowledge_service import lookup_entity

    hits: list[dict[str, Any]] = []
    seen_titles: set[str] = set()

    def _accept(hit: dict[str, Any] | None) -> bool:
        if not hit:
            return False
        key = hit["title"].lower()
        if key in seen_titles:
            return False
        seen_titles.add(key)
        hits.append(hit)
        return True

    for q in queries:
        q = (q or "").strip()
        if not q:
            continue

        # 1) API-first when allowed (best title fidelity for operator enrichment)
        if allow_api_fallback:
            api_raw = _api_summary_for_query(q)
            # MediaWiki search already disambiguates — don't over-filter API titles
            if _accept(
                _normalize_hit(api_raw, query=q, require_title_match=False) if api_raw else None
            ):
                if len(hits) >= max_hits:
                    break
                continue

        # 2) Local exact/alias/prefix only if title is close to the query
        try:
            local = lookup_entity(q)
        except Exception as e:
            logger.debug("wiki local %s: %s", q[:60], e)
            local = None
        if local and _titles_close(q, str(local.get("title") or "")):
            _accept(_normalize_hit(local, query=q, require_title_match=True))
        if len(hits) >= max_hits:
            break

    return hits[:max_hits]


def build_wiki_section(hits: list[dict[str, Any]], *, label: str) -> str:
    lines = [
        WIKI_SECTION_HEADER,
        "",
        f"_Retrieved {_now_iso()[:19]}Z via NI wiki RAG "
        f"(local ``wikipedia_knowledge`` + Wikipedia summary API). "
        f"Background only — not NI narrative._",
        "",
        f"_Target: {label}_",
        "",
    ]
    if not hits:
        lines.append("_No Wikipedia hits for configured queries._")
        lines.append("")
        return "\n".join(lines)

    for h in hits:
        title = h["title"]
        url = h["url"]
        extract = (h["extract"] or "").replace("\n", " ").strip()
        lines.append(f"### [{title}]({url})")
        lines.append("")
        lines.append(f"> {extract}")
        lines.append("")
        lines.append(f"- Source: Wikipedia — [{title}]({url})")
        if h.get("query") and h["query"].lower() != title.lower():
            lines.append(f"- Lookup query: `{h['query']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def patch_wiki_section(body: str, wiki_md: str) -> str:
    text = body or ""
    block = "\n" + wiki_md.strip() + "\n"
    if _WIKI_SECTION_RE.search(text):
        return _WIKI_SECTION_RE.sub(block, text, count=1)
    # Prefer before Non-RSS API section, then Sources, else append
    for marker in (
        "\n## Non-RSS evidence (API)\n",
        "\n## Sources\n",
        "\n## Timeline\n",
    ):
        if marker in text:
            return text.replace(marker, block + marker, 1)
    return text.rstrip() + "\n" + block


def _queries_for_hub(cluster_key: str, hub: dict[str, Any]) -> list[str]:
    configured = list(PRIORITY_HUB_QUERIES.get(cluster_key) or [])
    if configured:
        return configured
    meta = hub.get("metadata") if isinstance(hub.get("metadata"), dict) else {}
    themes = meta.get("themes") or meta.get("theme_tokens") or []
    out: list[str] = []
    title = str(hub.get("title") or "").split("(")[0].strip()
    if title:
        # Strip "situation" / trailing dash noise
        title = re.sub(r"\s*[—–-]\s*.*$", "", title).strip()
        if title:
            out.append(title)
    for t in themes:
        t = str(t).strip()
        if t and t not in out:
            out.append(t)
    return out[:6]


def apply_wiki_to_hub(
    cluster_key: str,
    *,
    force: bool = False,
    dry_run: bool = False,
    allow_api_fallback: bool = True,
    max_hits: int = 5,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_cluster_hub_service import get_cluster_hub
    from services.vault_notes_registry_service import upsert_vault_note

    hub = get_cluster_hub(cluster_key=cluster_key)
    if not hub:
        return {"ok": False, "kind": "hub", "cluster_key": cluster_key, "error": "hub_missing"}
    path = str(hub.get("vault_path") or "")
    if not path:
        return {"ok": False, "kind": "hub", "cluster_key": cluster_key, "error": "no_path"}

    meta = dict(hub.get("metadata") or {})
    if meta.get("wiki_enriched_at") and not force:
        return {
            "ok": True,
            "kind": "hub",
            "cluster_key": cluster_key,
            "skipped": "already_enriched",
            "path": path,
        }

    queries = _queries_for_hub(cluster_key, hub)
    hits = retrieve_wiki_hits(
        queries, max_hits=max_hits, allow_api_fallback=allow_api_fallback
    )
    wiki_md = build_wiki_section(hits, label=f"Situation `{cluster_key}`")
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "kind": "hub",
            "cluster_key": cluster_key,
            "queries": queries,
            "hit_titles": [h["title"] for h in hits],
            "wiki_chars": len(wiki_md),
        }

    root = vault_root()
    fp = root / path
    if not fp.is_file():
        return {
            "ok": False,
            "kind": "hub",
            "cluster_key": cluster_key,
            "error": "file_missing",
            "path": path,
        }
    existing = fp.read_text(encoding="utf-8")
    patched = patch_wiki_section(existing, wiki_md).replace("\x00", "")
    fp.write_text(patched, encoding="utf-8")

    meta["wiki_enriched_at"] = _now_iso()
    meta["wiki_enrichment_source"] = "vault_wiki_enrichment_service"
    meta["wiki_hit_titles"] = [h["title"] for h in hits]
    upsert_vault_note(
        domain_key=str(hub.get("domain_key") or meta.get("domain_key") or "politics"),
        note_type="cluster",
        object_id=int(hub["object_id"]),
        vault_path=path,
        title=hub.get("title"),
        note_status="note_ready",
        lifecycle=str(hub.get("lifecycle") or "living"),
        body_md=patched,
        summary_md=(hub.get("summary_md") or None),
        metadata=meta,
        tags_source="ni_structural",
    )
    return {
        "ok": True,
        "kind": "hub",
        "cluster_key": cluster_key,
        "path": path,
        "hit_n": len(hits),
        "hit_titles": [h["title"] for h in hits],
        "wiki_chars": len(wiki_md),
    }


def _list_living_entities(*, titles: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if titles:
                cur.execute(
                    """
                    SELECT id, domain_key, object_id, vault_path, title, lifecycle,
                           metadata, body_md, summary_md
                    FROM intelligence.vault_notes
                    WHERE note_type = 'entity'
                      AND lifecycle = 'living'
                      AND title = ANY(%s)
                    ORDER BY mention_count DESC NULLS LAST
                    LIMIT %s
                    """,
                    (list(titles), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, domain_key, object_id, vault_path, title, lifecycle,
                           metadata, body_md, summary_md
                    FROM intelligence.vault_notes
                    WHERE note_type = 'entity'
                      AND lifecycle = 'living'
                    ORDER BY mention_count DESC NULLS LAST
                    LIMIT %s
                    """,
                    (limit,),
                )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in (cur.fetchall() or [])]


def apply_wiki_to_entity(
    note: dict[str, Any],
    *,
    force: bool = False,
    dry_run: bool = False,
    allow_api_fallback: bool = True,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import upsert_vault_note

    path = str(note.get("vault_path") or "")
    title = str(note.get("title") or "").strip()
    if not path or not title:
        return {"ok": False, "kind": "entity", "error": "missing_path_or_title"}

    meta = note.get("metadata") if isinstance(note.get("metadata"), dict) else {}
    meta = dict(meta or {})
    if meta.get("wiki_enriched_at") and not force:
        return {
            "ok": True,
            "kind": "entity",
            "title": title,
            "skipped": "already_enriched",
            "path": path,
        }

    queries = [title]
    override = ENTITY_WIKI_QUERY_OVERRIDE.get(title)
    if override:
        queries = [override, title]
    # Prefer entity_canonical name if object_id present
    oid = note.get("object_id")
    domain = str(note.get("domain_key") or "politics")
    if oid:
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT canonical_name
                        FROM {domain}.entity_canonical
                        WHERE id = %s
                        """,
                        (int(oid),),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        cname = str(row[0]).strip()
                        if cname and cname not in queries:
                            queries.insert(0, cname)
        except Exception as e:
            logger.debug("entity_canonical lookup %s/%s: %s", domain, oid, e)

    hits = retrieve_wiki_hits(queries, max_hits=2, allow_api_fallback=allow_api_fallback)
    wiki_md = build_wiki_section(hits, label=f"Entity `{title}`")
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "kind": "entity",
            "title": title,
            "queries": queries,
            "hit_titles": [h["title"] for h in hits],
            "wiki_chars": len(wiki_md),
        }

    root = vault_root()
    fp = root / path
    if not fp.is_file():
        return {
            "ok": False,
            "kind": "entity",
            "title": title,
            "error": "file_missing",
            "path": path,
        }
    existing = fp.read_text(encoding="utf-8")
    patched = patch_wiki_section(existing, wiki_md).replace("\x00", "")
    fp.write_text(patched, encoding="utf-8")

    meta["wiki_enriched_at"] = _now_iso()
    meta["wiki_enrichment_source"] = "vault_wiki_enrichment_service"
    meta["wiki_hit_titles"] = [h["title"] for h in hits]
    upsert_vault_note(
        domain_key=domain,
        note_type="entity",
        object_id=int(oid or 0),
        vault_path=path,
        title=title,
        note_status="note_ready",
        lifecycle=str(note.get("lifecycle") or "living"),
        body_md=patched,
        summary_md=(note.get("summary_md") or None),
        metadata=meta,
        tags_source="ni_structural",
    )
    return {
        "ok": True,
        "kind": "entity",
        "title": title,
        "path": path,
        "hit_n": len(hits),
        "hit_titles": [h["title"] for h in hits],
        "wiki_chars": len(wiki_md),
    }


def enrich_priority_vault_wiki(
    *,
    hubs: list[str] | None = None,
    entity_limit: int = 15,
    include_entities: bool = True,
    force: bool = False,
    dry_run: bool = False,
    allow_api_fallback: bool = True,
    hub_max_hits: int = 4,
) -> dict[str, Any]:
    """Capped operator pass: priority Situation hubs, then living entities."""
    hub_keys = list(hubs or DEFAULT_PRIORITY_HUBS)
    results: list[dict[str, Any]] = []

    for ck in hub_keys:
        try:
            results.append(
                apply_wiki_to_hub(
                    ck,
                    force=force,
                    dry_run=dry_run,
                    allow_api_fallback=allow_api_fallback,
                    max_hits=hub_max_hits,
                )
            )
        except Exception as e:
            logger.exception("wiki hub %s", ck)
            results.append({"ok": False, "kind": "hub", "cluster_key": ck, "error": str(e)})

    entity_results: list[dict[str, Any]] = []
    if include_entities and entity_limit > 0:
        notes = _list_living_entities(
            titles=list(PRIORITY_ENTITY_TITLES),
            limit=entity_limit,
        )
        # If fewer than limit matched priority titles, fill with top living
        if len(notes) < entity_limit:
            have = {n["vault_path"] for n in notes}
            for extra in _list_living_entities(titles=None, limit=entity_limit * 2):
                if extra["vault_path"] in have:
                    continue
                notes.append(extra)
                if len(notes) >= entity_limit:
                    break
        for note in notes[:entity_limit]:
            try:
                entity_results.append(
                    apply_wiki_to_entity(
                        note,
                        force=force,
                        dry_run=dry_run,
                        allow_api_fallback=allow_api_fallback,
                    )
                )
            except Exception as e:
                logger.exception("wiki entity %s", note.get("title"))
                entity_results.append(
                    {
                        "ok": False,
                        "kind": "entity",
                        "title": note.get("title"),
                        "error": str(e),
                    }
                )

    all_r = results + entity_results
    improved = [
        r
        for r in all_r
        if r.get("ok") and not r.get("skipped") and not r.get("dry_run") and r.get("hit_n", 0) > 0
    ]
    return {
        "ok": True,
        "hub_n": len(results),
        "hub_ok": sum(1 for r in results if r.get("ok")),
        "entity_n": len(entity_results),
        "entity_ok": sum(1 for r in entity_results if r.get("ok")),
        "improved_n": len(improved),
        "results": all_r,
    }
