"""Extra framing packs for package compose / publish assemble.

Complements ``package_vault_context_service`` (vault hubs/entities) with:
  - causal_edges + open narrative_expectations
  - storyline_rag_context / GDELT when vault is thin
  - MemPalace watches → editorial_priority metadata
  - congress_trade_signals for finance packages

All packs are **background / framing** unless explicitly attached as members
elsewhere. Citeable facts remain package members (``[@mN]``).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)


def _as_dict(val: Any) -> dict[str, Any]:
    return val if isinstance(val, dict) else {}


def _tokens(text: str) -> set[str]:
    normalized = re.sub(r"[-–—_/]+", " ", (text or "").lower())
    return {m.group(0) for m in _TOKEN_RE.finditer(normalized) if len(m.group(0)) > 2}


def parse_package_storyline(package: dict[str, Any]) -> tuple[str | None, int | None]:
    """Return (domain_key, storyline_id) from legacy_seed or metadata."""
    meta = _as_dict(package.get("metadata"))
    try:
        from services.editorial_package_narrative_service import _parse_legacy_seed

        dk, sid = _parse_legacy_seed(meta)
        if dk and sid is not None:
            return dk, int(sid)
    except Exception:
        pass
    seed = str(meta.get("legacy_seed") or "")
    m = re.match(r"storyline:([^:]+):(\d+)$", seed)
    if m:
        return m.group(1), int(m.group(2))
    try:
        sid = meta.get("storyline_id") or meta.get("source_storyline_id")
        if sid is not None:
            domains = list(package.get("domain_keys") or [])
            return (str(domains[0]) if domains else None), int(sid)
    except (TypeError, ValueError):
        pass
    return None, None


def collect_causal_framing(package: dict[str, Any], *, limit: int = 12) -> list[dict[str, Any]]:
    try:
        from services.editorial_package_narrative_service import _collect_causal_edges

        return (_collect_causal_edges(package) or [])[:limit]
    except Exception as e:
        logger.debug("collect_causal_framing: %s", e)
        return []


def collect_open_expectations(
    package: dict[str, Any], *, limit: int = 8
) -> list[dict[str, Any]]:
    dk, sid = parse_package_storyline(package)
    domains = [str(d) for d in (package.get("domain_keys") or []) if d]
    try:
        from services.expectation_tracking_service import list_expectations

        rows: list[dict[str, Any]] = []
        if dk:
            rows.extend(
                list_expectations(domain_key=dk, overdue_only=False, limit=limit * 2)
            )
        elif domains:
            for d in domains[:2]:
                rows.extend(
                    list_expectations(domain_key=d, overdue_only=False, limit=limit)
                )
        # Prefer storyline match + open/overdue
        out: list[dict[str, Any]] = []
        for r in rows:
            st = str(r.get("status") or "")
            if st not in ("open", "due_soon", "overdue"):
                continue
            if sid is not None and r.get("storyline_id") not in (None, sid, str(sid)):
                # Keep domain-open expectations lightly if no storyline match later
                pass
            out.append(
                {
                    "id": r.get("id"),
                    "claim_text": (r.get("claim_text") or "")[:400],
                    "expected_outcome": (r.get("expected_outcome") or "")[:240],
                    "due_date": str(r.get("due_date") or "")[:10] or None,
                    "status": st,
                    "domain_key": r.get("domain_key"),
                    "storyline_id": r.get("storyline_id"),
                    "confidence": r.get("confidence"),
                }
            )
        # Storyline-matched first
        if sid is not None:
            out.sort(
                key=lambda x: (
                    0 if x.get("storyline_id") in (sid, str(sid)) else 1,
                    0 if x.get("status") == "overdue" else 1,
                )
            )
        return out[:limit]
    except Exception as e:
        logger.debug("collect_open_expectations: %s", e)
        return []


def collect_storyline_rag_framing(
    package: dict[str, Any],
    *,
    max_chars: int = 2800,
    vault_note_n: int = 0,
    vault_thin_threshold: int = 2,
) -> dict[str, Any]:
    """Load stored Wikipedia/GDELT rag when vault background is thin or missing."""
    if vault_note_n >= vault_thin_threshold:
        return {"ok": True, "skipped": "vault_sufficient", "text": "", "chars": 0}
    dk, sid = parse_package_storyline(package)
    if not dk or sid is None:
        return {"ok": False, "skipped": "no_storyline", "text": "", "chars": 0}
    try:
        from shared.database.connection import get_db_connection_context
        from services.storyline_rag_context_service import render_rag_context_for_llm

        rag_data = None
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT rag_data FROM intelligence.storyline_rag_context
                    WHERE domain_key = %s AND storyline_id = %s
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (dk, int(sid)),
                )
                row = cur.fetchone()
                if row and row[0]:
                    rag_data = row[0] if isinstance(row[0], dict) else None
        text = render_rag_context_for_llm(rag_data, max_chars=max_chars)
        return {
            "ok": bool(text),
            "domain_key": dk,
            "storyline_id": int(sid),
            "text": text,
            "chars": len(text),
            "has_gdelt": bool(
                isinstance(rag_data, dict)
                and isinstance((rag_data.get("gdelt") or {}).get("events"), list)
                and (rag_data.get("gdelt") or {}).get("events")
            ),
            "has_wikipedia": bool(
                isinstance(rag_data, dict) and rag_data.get("wikipedia")
            ),
        }
    except Exception as e:
        logger.debug("collect_storyline_rag_framing: %s", e)
        return {"ok": False, "error": str(e), "text": "", "chars": 0}


def match_mempalace_priority(package: dict[str, Any]) -> dict[str, Any]:
    """Match package title/storyline against MemPalace watches / preferred."""
    try:
        from services.mempalace_brief_memory import (
            load_editorial_memory,
            mempalace_brief_enabled,
        )

        if not mempalace_brief_enabled():
            return {"ok": False, "skipped": "disabled", "priority": None}
        mem = load_editorial_memory(limit=12)
        if not mem.get("ok"):
            return {
                "ok": False,
                "skipped": "mempalace_unavailable",
                "error": mem.get("error"),
                "priority": None,
            }
        title = str(package.get("working_title") or "")
        title_toks = _tokens(title)
        dk, sid = parse_package_storyline(package)
        best: dict[str, Any] | None = None
        best_score = 0.0
        for room_key, priority in (
            ("preferred", "preferred"),
            ("watches", "watch"),
            ("skip", "skip"),
        ):
            for item in mem.get(room_key) or []:
                # load_editorial_memory returns plain strings; older paths may use dicts.
                if isinstance(item, str):
                    content = item
                    meta: dict[str, Any] = {}
                elif isinstance(item, dict):
                    content = str(
                        item.get("content")
                        or item.get("drawer")
                        or item.get("text")
                        or item.get("snippet")
                        or ""
                    )
                    meta = _as_dict(item.get("metadata") or item.get("meta"))
                else:
                    continue
                # Hand-pinned drawers encode ids inline:
                # "watch: Title domain=politics storyline_id=9512 reason=…"
                m_sid = re.search(r"storyline_id\s*=\s*(\d+)", content, re.I)
                m_dk = re.search(r"domain\s*=\s*([a-z0-9_-]+)", content, re.I)
                item_sid = (
                    meta.get("storyline_id")
                    or (item.get("storyline_id") if isinstance(item, dict) else None)
                    or (int(m_sid.group(1)) if m_sid else None)
                )
                item_dk = (
                    meta.get("domain_key")
                    or (item.get("domain_key") if isinstance(item, dict) else None)
                    or (m_dk.group(1) if m_dk else None)
                )
                score = 0.0
                if sid is not None and item_sid is not None and str(item_sid) == str(sid):
                    score += 3.0
                if dk and item_dk and str(item_dk) == str(dk):
                    score += 0.5
                overlap = len(title_toks & _tokens(content))
                if overlap >= 2:
                    score += overlap * 0.4
                if score > best_score:
                    best_score = score
                    best = {
                        "priority": priority,
                        "score": round(score, 3),
                        "snippet": content[:280],
                        "storyline_id": item_sid,
                        "domain_key": item_dk,
                        "room": room_key,
                    }
        if not best or best_score < 1.0:
            return {"ok": True, "priority": None, "matched": False}
        return {"ok": True, "matched": True, **best}
    except Exception as e:
        logger.debug("match_mempalace_priority: %s", e)
        return {"ok": False, "error": str(e), "priority": None}


def apply_mempalace_priority_to_package(
    package_id: int, match: dict[str, Any]
) -> None:
    """Stamp metadata.editorial_priority when MemPalace match is watch/prefer."""
    if not match.get("matched") or match.get("priority") not in ("watch", "preferred"):
        return
    try:
        from shared.database.connection import get_db_connection_context
        import json

        patch = {
            "editorial_priority": match.get("priority"),
            "editorial_priority_score": match.get("score"),
            "editorial_priority_source": "mempalace",
            "editorial_priority_snippet": (match.get("snippet") or "")[:240],
        }
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.editorial_packages
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(patch), int(package_id)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("apply_mempalace_priority_to_package: %s", e)


def collect_congress_trade_signal_framing(
    package: dict[str, Any], *, limit: int = 8
) -> dict[str, Any]:
    """Top congress_trade_signals for finance packages (empty if no rows/key)."""
    domains = {str(d).lower() for d in (package.get("domain_keys") or []) if d}
    title = str(package.get("working_title") or "").lower()
    finance_ish = "finance" in domains or any(
        t in title for t in ("stock", "ticker", "fed", "market", "earnings", "trade")
    )
    if not finance_ish:
        return {"ok": True, "skipped": "not_finance", "signals": [], "n": 0}
    try:
        from services.congress_trade_signals_service import list_congress_signals

        rows = list_congress_signals(eligible_only=True, limit=max(20, limit))
        # Prefer tickers mentioned in title/stub
        blob = f"{package.get('working_title') or ''} {package.get('summary_stub') or ''}"
        blob_u = blob.upper()
        scored: list[tuple[float, dict[str, Any]]] = []
        for r in rows:
            ticker = str(r.get("ticker") or "").upper()
            if not ticker:
                continue
            score = float(r.get("signal_score") or 0)
            if ticker in blob_u or f" {ticker} " in f" {blob_u} ":
                score += 2.0
            scored.append(
                (
                    score,
                    {
                        "id": r.get("id"),
                        "ticker": ticker,
                        "signal_score": r.get("signal_score"),
                        "as_of_date": str(r.get("as_of_date") or "")[:10] or None,
                        "quiver_trade_id": r.get("quiver_trade_id"),
                        "eligible": r.get("eligible"),
                    },
                )
            )
        scored.sort(key=lambda x: -x[0])
        signals = [s for _, s in scored[:limit]]
        return {
            "ok": True,
            "n": len(signals),
            "signals": signals,
            "policy": "background_only_not_citeable",
        }
    except Exception as e:
        logger.debug("collect_congress_trade_signal_framing: %s", e)
        return {"ok": False, "error": str(e), "signals": [], "n": 0}


def build_compose_enrichment_pack(
    package: dict[str, Any],
    *,
    vault_note_n: int = 0,
    apply_mempalace: bool = True,
) -> dict[str, Any]:
    """Aggregate framing packs for compose payload."""
    causal = collect_causal_framing(package)
    expectations = collect_open_expectations(package)
    rag = collect_storyline_rag_framing(package, vault_note_n=vault_note_n)
    mem = match_mempalace_priority(package)
    if apply_mempalace and package.get("id") and mem.get("matched"):
        try:
            apply_mempalace_priority_to_package(int(package["id"]), mem)
        except Exception:
            pass
    congress = collect_congress_trade_signal_framing(package)

    denser = bool(
        mem.get("priority") in ("watch", "preferred")
        or (congress.get("n") or 0) > 0
        or len(causal) >= 3
    )

    return {
        "ok": True,
        "causal_edges": causal,
        "open_expectations": expectations,
        "storyline_rag": rag,
        "mempalace": {
            "priority": mem.get("priority"),
            "matched": bool(mem.get("matched")),
            "score": mem.get("score"),
            "snippet": mem.get("snippet"),
        },
        "congress_trade_signals": congress,
        "assemble_hints": {
            "denser_assemble": denser,
            "prefer_publish_member_budget": denser,
            "reason": (
                "mempalace_watch"
                if mem.get("priority") in ("watch", "preferred")
                else "signals_or_causal"
                if denser
                else None
            ),
        },
        "policy": "background_only_not_citeable",
    }
