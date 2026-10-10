"""Retrieve vault notes as background context for package compose / evidence expand.

Vault is **framing**, not citation SSOT: Situation hubs, living entities, wiki
background, dossiers, and API evidence sections orient the writer. Publishable
facts must still come from package members (``[@mN]``).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)
_SECTION_HEADERS = (
    "## Wikipedia background",
    "## Entity dossier",
    "## Non-RSS evidence (API)",
    "## Energy (EIA)",
    "## Congress trades (Quiver)",
    "## Energy / rates (macro series)",
    "## CURRENT BRIEF",
)

# Prefer Situation hubs we seed + living entities with wiki/dossier density.
_PRIORITY_CLUSTER_KEYS = (
    "us_institutions",
    "china_trade_tech",
    "russia_ukraine",
    "climate_resource_policy",
    "farage_reform_boats",
    "venezuela_boe_gold",
    "ai_governance",
    "market_trends",
    "resource_movements",
    "iran_war",
    "inflation_iran_war",
)


def _tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "over",
        "under",
        "about",
        "after",
        "before",
        "news",
        "update",
        "story",
        "report",
    }
    # Split hyphenated compounds (US-Iran → us, iran) so hub hints match.
    normalized = re.sub(r"[-–—_/]+", " ", (text or "").lower())
    return {
        m.group(0).lower()
        for m in _TOKEN_RE.finditer(normalized)
        if m.group(0).lower() not in stop and len(m.group(0)) > 2
    }


def _extract_priority_sections(body: str | None, *, max_chars: int = 1800) -> str:
    """Pull replaceable enrichment sections; fall back to leading body prose."""
    text = (body or "").strip()
    if not text:
        return ""
    chunks: list[str] = []
    for header in _SECTION_HEADERS:
        idx = text.find(header)
        if idx < 0:
            continue
        rest = text[idx + len(header) :]
        nxt = len(rest)
        for h2 in _SECTION_HEADERS:
            j = rest.find("\n## ")
            if 0 <= j < nxt:
                nxt = j
        block = (header + rest[:nxt]).strip()
        if len(block) > 80:
            chunks.append(block[:900])
        if sum(len(c) for c in chunks) >= max_chars:
            break
    if chunks:
        out = "\n\n".join(chunks)
        return out[:max_chars]
    # Strip frontmatter-ish first lines
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("---") or s.startswith("ni_") or s.startswith("tags:"):
            continue
        if s.startswith("#"):
            continue
        lines.append(s)
        if sum(len(x) for x in lines) > max_chars:
            break
    return "\n".join(lines)[:max_chars]


def _meta_dict(val: Any) -> dict[str, Any]:
    return val if isinstance(val, dict) else {}


def _cluster_keys_from_package(package: dict[str, Any]) -> list[str]:
    meta = _meta_dict(package.get("metadata"))
    keys: list[str] = []
    for raw in (
        meta.get("related_situations"),
        meta.get("cluster_keys"),
        meta.get("situation_hubs"),
        meta.get("vault_cluster_keys"),
    ):
        if isinstance(raw, list):
            for x in raw:
                s = str(x or "").strip()
                if s and s not in keys:
                    keys.append(s)
        elif isinstance(raw, str) and raw.strip():
            for part in re.split(r"[,;\s]+", raw.strip()):
                if part and part not in keys:
                    keys.append(part)
    # Title soft-match against known priority hubs
    title_toks = _tokens(str(package.get("working_title") or ""))
    hub_hints = {
        "us_institutions": {"white", "house", "congress", "justice", "court", "fbi"},
        "china_trade_tech": {"china", "chip", "tariff", "huawei", "semiconductor"},
        "russia_ukraine": {"ukraine", "russia", "putin", "nato", "kyiv"},
        "climate_resource_policy": {"climate", "mineral", "epa", "paris"},
        "venezuela_boe_gold": {"venezuela", "maduro", "gold"},
        "ai_governance": {"openai", "anthropic", "governance", "ai"},
        "market_trends": {"fed", "inflation", "cpi", "rates", "bond"},
        "resource_movements": {"oil", "wti", "opec", "hormuz", "crude"},
        "iran_war": {"iran", "hormuz", "tehran", "irgc"},
        "farage_reform_boats": {"farage", "reform", "channel", "migrant"},
    }
    for hub, hints in hub_hints.items():
        if len(title_toks & hints) >= 1 and hub not in keys:
            keys.append(hub)
    # Cap + prefer known priority first
    ordered = [k for k in _PRIORITY_CLUSTER_KEYS if k in keys]
    for k in keys:
        if k not in ordered:
            ordered.append(k)
    return ordered[:6]


def retrieve_vault_context_for_package(
    package: dict[str, Any],
    *,
    limit: int = 8,
    max_chars: int = 4500,
) -> dict[str, Any]:
    """Ranked vault background for one editorial package.

    Returns notes + ``evidence_text`` suitable for compose/evidence-expand prompts.
    """
    title = str(package.get("working_title") or "").strip()
    stub = str(package.get("summary_stub") or "").strip()
    domains = [str(d) for d in (package.get("domain_keys") or []) if d]
    q_toks = _tokens(f"{title} {stub}")
    cluster_keys = _cluster_keys_from_package(package)
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(row: dict[str, Any], *, rank: str, score: float = 1.0) -> None:
        path = str(row.get("vault_path") or "")
        if not path or path in seen:
            return
        excerpt = _extract_priority_sections(row.get("body_md") or row.get("summary_md"))
        if len(excerpt) < 60:
            return
        seen.add(path)
        notes.append(
            {
                "vault_path": path,
                "title": row.get("title"),
                "note_type": row.get("note_type"),
                "domain_key": row.get("domain_key"),
                "lifecycle": row.get("lifecycle"),
                "rank": rank,
                "score": round(score, 4),
                "excerpt": excerpt[:1200],
                "cluster_key": row.get("cluster_key"),
            }
        )

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                # 1) Hard: Situation hubs by cluster_key
                if cluster_keys:
                    cur.execute(
                        """
                        SELECT vault_path, title, note_type, domain_key, lifecycle,
                               body_md, summary_md,
                               COALESCE(metadata->>'cluster_key', '') AS cluster_key
                        FROM intelligence.vault_notes
                        WHERE note_type = 'cluster'
                          AND COALESCE(lifecycle, 'living') NOT IN ('index', 'archived', 'frozen')
                          AND (
                            metadata->>'cluster_key' = ANY(%s)
                            OR vault_path LIKE ANY(
                              ARRAY(SELECT '%%/' || k || '.md' FROM unnest(%s::text[]) AS k)
                            )
                          )
                        ORDER BY note_updated_at DESC NULLS LAST
                        LIMIT 12
                        """,
                        (cluster_keys, cluster_keys),
                    )
                    cols = [d[0] for d in cur.description]
                    for r in cur.fetchall() or []:
                        _add(dict(zip(cols, r)), rank="hub", score=1.2)

                # 2) Soft: living entities / clusters with token overlap
                cur.execute(
                    """
                    SELECT vault_path, title, note_type, domain_key, lifecycle,
                           body_md, summary_md, metadata,
                           COALESCE(metadata->>'cluster_key', '') AS cluster_key
                    FROM intelligence.vault_notes
                    WHERE note_type IN ('entity', 'cluster')
                      AND COALESCE(lifecycle, 'living') IN ('living', 'stub')
                      AND (
                        %s::text[] IS NULL
                        OR cardinality(%s::text[]) = 0
                        OR domain_key = ANY(%s)
                        OR domain_key IS NULL
                      )
                      AND (
                        body_md ILIKE '%%## Wikipedia background%%'
                        OR body_md ILIKE '%%## Entity dossier%%'
                        OR body_md ILIKE '%%## Non-RSS evidence%%'
                        OR body_md ILIKE '%%## Energy (EIA)%%'
                        OR lifecycle = 'living'
                      )
                    ORDER BY note_updated_at DESC NULLS LAST
                    LIMIT 200
                    """,
                    (domains or None, domains or None, domains or None),
                )
                cols = [d[0] for d in cur.description]
                soft: list[tuple[float, dict[str, Any]]] = []
                for r in cur.fetchall() or []:
                    row = dict(zip(cols, r))
                    path = str(row.get("vault_path") or "")
                    if path in seen:
                        continue
                    meta = _meta_dict(row.get("metadata"))
                    stored = meta.get("rag_tokens") or []
                    if isinstance(stored, list) and stored:
                        bag = {str(t).lower() for t in stored}
                    else:
                        bag = _tokens(f"{row.get('title') or ''} {row.get('summary_md') or ''}")
                    if not q_toks or not bag:
                        continue
                    overlap = len(q_toks & bag)
                    if overlap < 2:
                        continue
                    score = overlap / max(len(q_toks | bag), 1)
                    if row.get("note_type") == "cluster":
                        score += 0.05
                    if row.get("domain_key") in domains:
                        score += 0.03
                    soft.append((score, row))
                soft.sort(key=lambda x: -x[0])
                for score, row in soft[: max(4, limit)]:
                    _add(row, rank="soft", score=score)
    except Exception as e:
        logger.warning("retrieve_vault_context_for_package failed: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "notes": [],
            "evidence_text": "",
            "cluster_keys": cluster_keys,
            "note_n": 0,
        }

    notes = notes[: max(1, int(limit))]
    chunks: list[str] = []
    used = 0
    for n in notes:
        block = (
            f"[{n.get('note_type')}] {n.get('title') or n.get('vault_path')}"
            f" ({n.get('vault_path')})\n{n.get('excerpt') or ''}"
        )
        if used + len(block) > max_chars and chunks:
            break
        chunks.append(block)
        used += len(block)

    evidence_text = "\n\n---\n\n".join(chunks)
    return {
        "ok": True,
        "notes": notes,
        "evidence_text": evidence_text,
        "cluster_keys": cluster_keys,
        "note_n": len(notes),
        "chars": len(evidence_text),
        "policy": "background_only_not_citeable",
    }
