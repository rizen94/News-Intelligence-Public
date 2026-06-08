"""
Citation marker normalization — map LLM [CIT:...] keys to registered cit_* IDs.

LLMs often drop the ``ref_`` prefix from reference seed IDs (e.g. REF-eu_russia_* vs REF-ref_eu_russia_*).
"""

from __future__ import annotations

import re
from typing import Any

_CITATION_MARKER = re.compile(r"\[CIT:([^\]]+)\]")


def expand_citation_key_aliases(citation_key: str) -> set[str]:
    """All marker strings that should resolve to one registered citation."""
    key = (citation_key or "").strip()
    if not key:
        return set()

    aliases: set[str] = {key, key.lower()}
    if "-" not in key:
        return aliases

    prefix, rest = key.split("-", 1)
    prefix_u = prefix.upper()
    aliases.add(rest)
    aliases.add(rest.lower())
    aliases.add(f"{prefix_u}-{rest}")

    if prefix_u == "REF":
        if rest.startswith("ref_"):
            short = rest[4:]
            aliases.add(f"REF-{short}")
            aliases.add(f"ref-{short}")
            aliases.add(short)
            aliases.add(short.lower())
        elif rest.startswith("ref-"):
            short = rest[4:]
            aliases.add(f"REF-{short}")
            aliases.add(short)

    return {a for a in aliases if a}


def build_marker_lookup(
    citations: list[dict[str, Any]],
    *,
    key_field: str = "citation_key",
    id_field: str = "citation_id",
) -> dict[str, str]:
    """Map citation marker strings (exact + aliases) → cit_* id."""
    lookup: dict[str, str] = {}
    for item in citations:
        cid = item.get(id_field)
        ckey = item.get(key_field)
        if not cid or not ckey:
            continue
        for alias in expand_citation_key_aliases(str(ckey)):
            lookup[alias] = str(cid)
    return lookup


def resolve_marker_to_citation_id(marker: str, lookup: dict[str, str]) -> str | None:
    raw = (marker or "").strip()
    if not raw:
        return None
    if raw.startswith("cit_"):
        return raw
    if raw in lookup:
        return lookup[raw]
    lower = raw.lower()
    lower_lookup = {k.lower(): v for k, v in lookup.items()}
    if lower in lower_lookup:
        return lower_lookup[lower]

    # Suffix match: REF-eu_russia_* → REF-ref_eu_russia_*
    if "-" in raw:
        prefix, suffix = raw.split("-", 1)
        norm_suffix = suffix[4:] if suffix.startswith("ref_") else suffix
        norm_suffix_l = norm_suffix.lower()
        matches: list[tuple[str, str]] = []
        for k, cid in lookup.items():
            if "-" not in k:
                continue
            kp, ks = k.split("-", 1)
            if kp.upper() != prefix.upper():
                continue
            ks_norm = ks[4:] if ks.startswith("ref_") else ks
            if ks_norm.lower() == norm_suffix_l or ks.lower().endswith(suffix.lower()):
                matches.append((k, cid))
        if len(matches) == 1:
            return matches[0][1]
        if len(matches) > 1:
            exact = [cid for k, cid in matches if k.lower() == lower]
            if exact:
                return exact[0]
            return max(matches, key=lambda x: len(x[0]))[1]
    return None


def rewrite_citation_markers(content: str, lookup: dict[str, str]) -> tuple[str, list[str]]:
    """
    Rewrite [CIT:KEY] → [CIT:cit_*]. Returns (new_content, unresolved_marker_strings).
    """
    unresolved: list[str] = []

    def repl(match: re.Match[str]) -> str:
        raw = match.group(1).strip()
        cid = resolve_marker_to_citation_id(raw, lookup)
        if cid:
            return f"[CIT:{cid}]"
        if not raw.startswith("cit_"):
            unresolved.append(raw)
        return match.group(0)

    return _CITATION_MARKER.sub(repl, content), unresolved


def count_citation_markers(content: str) -> int:
    return len(_CITATION_MARKER.findall(content or ""))
