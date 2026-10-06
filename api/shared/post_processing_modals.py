"""
Post-processing modal catalog SSOT (v11).

Modals own domain allowlists. Inside a modal, search/work is cross-domain over
the allowlist. Domains remain tags on content.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODAL_KEYS: frozenset[str] = frozenset(
    {"research", "narrative", "reduction", "editor"}
)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "post_processing_modals.yaml"

_DEFAULT_MODALS: dict[str, dict[str, Any]] = {
    "research": {
        "label": "Research",
        "allowed_domains": [
            "medicine",
            "neurodiversity",
            "artificial-intelligence",
        ],
    },
    "narrative": {
        "label": "Narrative",
        "allowed_domains": ["politics", "finance", "legal"],
    },
    "reduction": {
        "label": "Reduction",
        "allowed_domains": [
            "medicine",
            "neurodiversity",
            "artificial-intelligence",
            "politics",
            "finance",
            "legal",
        ],
    },
    "editor": {
        "label": "Editor",
        "allowed_domains": [
            "medicine",
            "neurodiversity",
            "artificial-intelligence",
            "politics",
            "finance",
            "legal",
        ],
    },
}


def clear_modal_catalog_cache() -> None:
    load_modal_catalog.cache_clear()


@lru_cache(maxsize=1)
def load_modal_catalog() -> dict[str, dict[str, Any]]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        return _catalog_from_defaults()

    if not _CONFIG_PATH.is_file():
        return _catalog_from_defaults()
    try:
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception as e:  # pragma: no cover
        logger.warning("post_processing_modals.yaml load failed: %s", e)
        return _catalog_from_defaults()

    modals = raw.get("modals") if isinstance(raw, dict) else None
    if not isinstance(modals, dict):
        return _catalog_from_defaults()

    out: dict[str, dict[str, Any]] = {}
    for key in ("research", "narrative", "reduction", "editor"):
        entry = modals.get(key) if isinstance(modals.get(key), dict) else {}
        domains = entry.get("allowed_domains") or _DEFAULT_MODALS[key]["allowed_domains"]
        cleaned = [
            str(d).strip()
            for d in domains
            if isinstance(d, str) and str(d).strip()
        ]
        out[key] = {
            "key": key,
            "label": str(entry.get("label") or _DEFAULT_MODALS[key]["label"]),
            "description": str(entry.get("description") or ""),
            "allowed_domains": cleaned,
        }
    return out


def _catalog_from_defaults() -> dict[str, dict[str, Any]]:
    return {
        k: {
            "key": k,
            "label": str(v.get("label") or k),
            "description": str(v.get("description") or ""),
            "allowed_domains": list(v.get("allowed_domains") or []),
        }
        for k, v in _DEFAULT_MODALS.items()
    }


def list_modals() -> list[dict[str, Any]]:
    cat = load_modal_catalog()
    out: list[dict[str, Any]] = []
    for k in ("research", "narrative", "reduction", "editor"):
        if k not in cat:
            continue
        entry = dict(cat[k])
        entry.setdefault("key", k)
        out.append(entry)
    return out


def allowed_domains_for_modal(modal: str) -> list[str]:
    key = (modal or "").strip().lower()
    cat = load_modal_catalog()
    if key not in cat:
        return []
    return list(cat[key]["allowed_domains"])


def modals_for_domain(domain_key: str) -> list[str]:
    dk = (domain_key or "").strip()
    if not dk:
        return []
    return [
        str(m.get("key") or "")
        for m in list_modals()
        if m.get("key") and dk in (m.get("allowed_domains") or [])
    ]


def domain_in_modal(domain_key: str, modal: str) -> bool:
    return (domain_key or "").strip() in allowed_domains_for_modal(modal)


def normalize_domain_filter(
    modal: str,
    requested: list[str] | None,
) -> list[str]:
    """Intersect request with allowlist; empty request → full allowlist."""
    allow = allowed_domains_for_modal(modal)
    if not requested:
        return list(allow)
    req = [str(d).strip() for d in requested if str(d).strip()]
    return [d for d in req if d in allow]
