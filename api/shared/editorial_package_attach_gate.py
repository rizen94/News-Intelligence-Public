"""Theme/geo/unrelated gate for attaching members to editorial packages.

Shared by storyline seed, continuation refresh, research/narrative validate,
and published-safe odd-man-out prune. Suppress is per-package membership only —
never-attached candidates are simply skipped (no suppress stamp).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from shared.editorial_package_theme import (
    extract_case_party_tokens,
    is_theme_mismatch,
    theme_tokens,
)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_GEO_STOP = frozenset(
    {
        "united",
        "states",
        "america",
        "us",
        "usa",
        "uk",
        "europe",
        "asia",
        "africa",
        "world",
        "global",
        "international",
        "north",
        "south",
        "east",
        "west",
        "city",
        "county",
        "state",
        "province",
        "region",
    }
)

# Flags that should block attach (same spirit as reduction hard/soft removes).
ATTACH_BLOCK_FLAGS: frozenset[str] = frozenset(
    {"theme_mismatch", "unrelated", "geo_mismatch", "entity_mismatch"}
)


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def candidate_text_blob(
    *,
    label: str = "",
    quote: str = "",
    location: str = "",
    parties: list[Any] | None = None,
    extra: str = "",
) -> str:
    bits = [label, quote, location, extra]
    if parties:
        bits.extend(str(x) for x in parties if x)
    return " ".join(str(b or "") for b in bits)


def location_tokens(location: str | None) -> set[str]:
    return {t for t in _tokenize(location or "") if t not in _GEO_STOP}


def dominant_location_tokens_from_members(members: list[dict[str, Any]]) -> set[str]:
    counts: Counter[str] = Counter()
    for m in members:
        if m.get("status") not in (None, "active"):
            continue
        prov = _as_dict(m.get("provenance"))
        for t in location_tokens(str(prov.get("location") or "")):
            counts[t] += 1
    if not counts:
        return set()
    dominant = {t for t, c in counts.items() if c >= 2}
    return dominant or {t for t, _ in counts.most_common(5)}


def score_attach_candidate(
    *,
    title: str,
    stub: str = "",
    candidate_text: str,
    location: str | None = None,
    dominant_geo: set[str] | None = None,
    member_type: str | None = None,
) -> list[str]:
    """Return reduction-style pre_flags for a would-be attach candidate."""
    flags: list[str] = []
    title = title or ""
    stub = stub or ""
    blob = candidate_text or ""
    core_tokens = _tokenize(f"{title} {stub}")
    text_tokens = _tokenize(blob)

    if is_theme_mismatch(blob, title=title, stub=stub):
        flags.append("theme_mismatch")
    if (
        "theme_mismatch" not in flags
        and core_tokens
        and _jaccard(core_tokens, text_tokens) < 0.08
        and len(text_tokens) >= 3
    ):
        flags.append("unrelated")

    loc = location_tokens(location)
    geo = dominant_geo or set()
    if geo and loc and not (loc & geo) and len(loc) >= 1:
        flags.append("geo_mismatch")

    if (member_type or "") == "entity":
        if core_tokens and _jaccard(core_tokens, text_tokens) < 0.05:
            flags.append("entity_mismatch")

    return flags


def should_block_attach(flags: list[str] | None) -> bool:
    return bool(ATTACH_BLOCK_FLAGS & {str(f) for f in (flags or [])})


_STORYLINE_STUB_RE = re.compile(r"^from\s+\w[\w-]*\s+storyline\s+\d+\s*$", re.I)


def package_title_is_thin(title: str, stub: str = "") -> bool:
    """True when working_title lacks a distinctive spine for theme matching."""
    title = (title or "").strip()
    stub = (stub or "").strip()
    spine = theme_tokens(title) | extract_case_party_tokens(title)
    if len(spine) >= 2:
        return False
    if len(title) < 12:
        return True
    if stub and _STORYLINE_STUB_RE.match(stub.lower()) and len(spine) < 2:
        return True
    return len(spine) < 1


def resolve_attach_spine(
    title: str,
    stub: str = "",
    *,
    storyline_title: str | None = None,
) -> tuple[str, str]:
    """Prefer storyline title when package working_title is generic/thin."""
    title = (title or "").strip()
    stub = (stub or "").strip()
    if not package_title_is_thin(title, stub):
        return title, stub
    fallback = (storyline_title or "").strip()
    if fallback:
        return fallback, stub
    return title, stub


def fetch_storyline_title(domain_key: str | None, storyline_id: int | None) -> str:
    """Load episode title for attach-spine fallback (best-effort)."""
    dk = (domain_key or "").strip()
    if not dk or storyline_id is None:
        return ""
    try:
        from shared.database.connection import get_ui_db_connection_context
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(dk)
        if not schema:
            return ""
        sid = int(storyline_id)
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT title FROM {schema}.storylines WHERE id = %s",
                    (sid,),
                )
                row = cur.fetchone()
        return (row[0] or "").strip() if row else ""
    except Exception:
        return ""


def storyline_title_from_package(pkg: dict[str, Any] | None) -> str:
    meta = _package_metadata(pkg)
    dk = str(
        meta.get("source_domain_key")
        or (pkg or {}).get("domain_keys", [None])[0]
        or ""
    ).strip()
    sid = meta.get("source_storyline_id") or meta.get("storyline_id")
    try:
        sid_i = int(sid) if sid is not None else None
    except (TypeError, ValueError):
        sid_i = None
    return fetch_storyline_title(dk, sid_i) if sid_i else ""


def attach_allowed(
    *,
    title: str,
    stub: str = "",
    provenance: dict[str, Any] | None = None,
    dominant_geo: set[str] | None = None,
    member_type: str | None = None,
    extra_text: str = "",
    storyline_title: str | None = None,
) -> tuple[bool, list[str]]:
    """Return (ok_to_attach, flags)."""
    prov = _as_dict(provenance)
    parties = prov.get("parties") if isinstance(prov.get("parties"), list) else None
    blob = candidate_text_blob(
        label=str(prov.get("label") or ""),
        quote=str(prov.get("quote") or ""),
        location=str(prov.get("location") or ""),
        parties=parties,
        extra=extra_text,
    )
    gate_title, gate_stub = resolve_attach_spine(
        title, stub, storyline_title=storyline_title
    )
    flags = score_attach_candidate(
        title=gate_title,
        stub=gate_stub,
        candidate_text=blob,
        location=str(prov.get("location") or ""),
        dominant_geo=dominant_geo,
        member_type=member_type,
    )
    return (not should_block_attach(flags), flags)


def _package_metadata(pkg: dict[str, Any] | None) -> dict[str, Any]:
    if not pkg:
        return {}
    meta = pkg.get("metadata")
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            obj = json.loads(meta)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def membership_drifted_since_prune(pkg: dict[str, Any] | None) -> bool:
    """True when membership grew / changed after last odd-man-out stamp."""
    if not pkg:
        return False
    meta = _package_metadata(pkg)
    last_at = meta.get("last_odd_man_out_at")
    if not last_at:
        # Never stamped — treat as needing prune before republish clearance.
        return True
    last_count = meta.get("last_odd_man_out_active_count")
    active = [
        m
        for m in (pkg.get("members") or [])
        if m.get("status") in (None, "active")
    ]
    if last_count is not None and len(active) > int(last_count):
        return True
    try:
        last_dt = datetime.fromisoformat(str(last_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    for m in active:
        raw = m.get("added_at")
        if raw is None:
            continue
        if isinstance(raw, datetime):
            dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        else:
            try:
                dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
        if dt > last_dt:
            return True
    return False
