"""Parse OPML into RSS feed entries for setup."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


def parse_opml(opml_text: str, default_domain_key: str = "") -> list[dict[str, str]]:
    feeds: list[dict[str, str]] = []
    try:
        root = ET.fromstring(opml_text)
    except ET.ParseError:
        return feeds

    for outline in root.iter("outline"):
        url = outline.get("xmlUrl") or outline.get("htmlUrl") or ""
        if not url or not url.startswith(("http://", "https://")):
            continue
        title = outline.get("title") or outline.get("text") or url
        dk = default_domain_key
        if not dk:
            cat = (outline.get("category") or title or "").lower()
            dk = re.sub(r"[^a-z0-9]+", "-", cat).strip("-")[:48] or "imported"
        feeds.append({"url": url.strip(), "title": title.strip()[:255], "domain_key": dk})
    return feeds


def merge_opml_into_domains(
    opml_text: str,
    domains: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Return flat feed list with domain_key assigned to first domain if no match."""
    parsed = parse_opml(opml_text)
    if not domains:
        return parsed
    default = domains[0]["domain_key"]
    keys = {d["domain_key"] for d in domains}
    for f in parsed:
        if f.get("domain_key") not in keys:
            f["domain_key"] = default
    return parsed
