"""
Shared vocabulary and helpers for per-domain ``story_entity_index`` (SEI).

SEI entity_type CHECK (migration 179 + 200 / 291) allows only a closed set.
Article-entity types like ``subject`` / ``recurring_event`` must be mapped before upsert.
"""

from __future__ import annotations

from typing import Any

# Closed set matching story_entity_index_entity_type_check (incl. family via 200/291).
SEI_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "person",
        "organization",
        "location",
        "case_number",
        "legislation_id",
        "event",
        "other",
        "family",
    }
)

# article_entities / entity_canonical → SEI CHECK vocabulary
_ENTITY_TYPE_MAP: dict[str, str] = {
    "person": "person",
    "organization": "organization",
    "location": "location",
    "case_number": "case_number",
    "legislation_id": "legislation_id",
    "event": "event",
    "other": "other",
    "family": "family",
    "subject": "other",
    "recurring_event": "event",
    "unknown": "other",
}


def map_entity_type_for_sei(
    raw: Any,
    *,
    family_allowed: bool = True,
) -> str:
    """
    Map an article_entities / entity_canonical type into a SEI CHECK-safe value.

    When ``family_allowed`` is False (e.g. neurodiversity before migration 291),
    ``family`` degrades to ``other``.
    """
    key = (str(raw or "").strip().lower() or "other")
    mapped = _ENTITY_TYPE_MAP.get(key, "other")
    if mapped == "family" and not family_allowed:
        return "other"
    if mapped not in SEI_ENTITY_TYPES:
        return "other"
    return mapped


HUB_ENTITY_ROLES = frozenset({"who", "what", "where"})
MATTER_ENTITY_ROLES = frozenset({"party", "matter"})


def _domain_synthesis_config_module():
    """Load domain_synthesis_config without importing services package __init__ (DB)."""
    import importlib.util
    import sys
    from pathlib import Path

    name = "services.domain_synthesis_config"
    if name in sys.modules:
        return sys.modules[name]
    path = (
        Path(__file__).resolve().parents[1] / "services" / "domain_synthesis_config.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclass/circular refs see the name
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_entity_role_for_sei(
    *,
    domain_key: str,
    entity_name: str | None,
    entity_type: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Return (entity_role, hub_key) for SEI indexing.

    Hub facets → who|what|where + hub_key. Case/legislation → matter.
    Non-hub persons/orgs → party when durable; else None.
    """
    et = (entity_type or "").strip().lower()
    if et in ("case_number", "legislation_id"):
        return "matter", None
    try:
        dsc = _domain_synthesis_config_module()
        cfg = dsc.get_domain_synthesis_config(domain_key)
        facet = cfg.match_hub_facet(entity_name)
        if facet:
            return facet.role, facet.key
    except Exception:
        pass
    if et in ("person", "organization", "company", "legal_entity"):
        return "party", None
    return None, None
