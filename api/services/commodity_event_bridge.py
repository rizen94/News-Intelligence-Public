"""
Cross-domain commodity map bridge — which non-finance tracked_events may appear on finance commodity maps,
text signals for post-discovery enrichment, and static map overlay metadata.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _non_finance_domain_tokens() -> frozenset[str]:
    """Lowercased URL keys and schema names for active silos except finance (cross-domain map provenance)."""
    from shared.domain_registry import domain_key_to_schema, get_active_domain_keys

    out: set[str] = set()
    for dk in get_active_domain_keys():
        if dk == "finance":
            continue
        out.add(dk.lower())
        try:
            out.add(domain_key_to_schema(dk).lower())
        except KeyError:
            pass
    return frozenset(out)


# Event types that often carry geopolitical / macro signal for commodity maps.
CROSS_DOMAIN_GEO_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "conflict",
        "diplomatic",
        "policy",
        "investigation",
        "economic",
        "trade",
        "geopolitical",
        "security",
        "regulatory",
        "election",
        "other",
    }
)

# When these appear with commodity anchors, append finance to domain_keys (enrichment).
_MACRO_COMMODITY_MARKERS: frozenset[str] = frozenset(
    {
        "opec",
        "wti",
        "brent",
        "oil",
        "gas",
        "lng",
        "pipeline",
        "refiner",
        "strait",
        "hormuz",
        "malacca",
        "suez",
        "panama canal",
        "shipping",
        "tanker",
        "freight",
        "sanction",
        "embargo",
        "tariff",
        "export ban",
        "supply chain",
        "mine",
        "mining",
        "smelter",
        "gold",
        "silver",
        "platinum",
        "palladium",
        "fed ",
        "federal reserve",
        "interest rate",
        "commodity",
        "futures",
    }
)

_LOGISTICS_MARKERS: frozenset[str] = frozenset(
    {
        "shipping",
        "port",
        "strait",
        "canal",
        "vessel",
        "tanker",
        "freight",
        "logistics",
        "supply chain",
        "chokepoint",
    }
)


def cross_domain_sql_domains_array() -> list[str]:
    """URL keys and schema-style tokens for active silos except finance (tracked_events.domain_keys)."""
    from shared.domain_registry import domain_key_to_schema, get_active_domain_keys

    ordered: list[str] = []
    seen: set[str] = set()
    for dk in get_active_domain_keys():
        if dk == "finance":
            continue
        for token in (dk, dk.replace("-", "_"), domain_key_to_schema(dk)):
            if token and token not in seen:
                seen.add(token)
                ordered.append(token)
    return ordered


def maybe_append_finance_domain_key(
    conn,
    event_id: int,
    event_name: str,
    geographic_scope: str,
    summary: str,
    current_keys: list[str],
) -> None:
    """If the event text looks macro/commodity-linked, append finance to domain_keys (deduped)."""
    if not conn:
        return
    lowered = [str(k).lower() for k in (current_keys or [])]
    if "finance" in lowered:
        return
    blob = f"{event_name or ''} {geographic_scope or ''} {summary or ''}"
    if not text_suggests_macro_commodity_link(blob):
        return
    new_keys = list(dict.fromkeys(list(current_keys or []) + ["finance"]))
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.tracked_events
                SET domain_keys = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_keys, event_id),
            )
    except Exception as e:
        logger.debug("maybe_append_finance_domain_key: %s", e)


def text_suggests_macro_commodity_link(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _MACRO_COMMODITY_MARKERS)


def text_suggests_logistics_signal(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _LOGISTICS_MARKERS)


def row_eligible_for_cross_domain_geo(event_type: str | None) -> bool:
    et = (event_type or "other").lower()
    return et in CROSS_DOMAIN_GEO_EVENT_TYPES


def geo_event_provenance(domain_keys: list[str] | None, path_domain: str = "finance") -> str:
    """How the row is positioned for the finance commodity map."""
    dk = [str(x).lower() for x in (domain_keys or [])]
    if path_domain.lower() in dk:
        return "finance_native"
    cross = _non_finance_domain_tokens()
    if set(dk) & cross:
        return "cross_domain"
    return "other"


def event_visible_on_commodity_map(
    text: str,
    commodity: str,
    *,
    include_supply_chain_geo: bool = False,
) -> bool:
    """Whether a cross-domain row should appear on the map for this commodity."""
    try:
        from domains.finance.news_orchestrator import is_relevant_to_commodity
    except Exception:
        return False
    t = (text or "").lower()
    cid = (commodity or "").lower()
    if is_relevant_to_commodity(text, cid):
        return True
    if not include_supply_chain_geo or not text_suggests_logistics_signal(text):
        return False
    if cid in ("oil", "gas") and any(
        x in t for x in ("oil", "gas", "lng", "energy", "fuel", "petrol", "diesel")
    ):
        return True
    if cid in ("gold", "silver", "platinum") and any(
        x in t for x in ("mine", "mining", "smelter", "refin", "bullion", "metal")
    ):
        return True
    return False


def load_map_overlays_for_commodity(commodity_id: str) -> dict[str, Any]:
    """
    Static reference points / lines for map layers (not live AIS).
    Returns GeoJSON-ish dict: { "type": "FeatureCollection", "features": [...], "disclaimer": "..." }
    """
    path = Path(__file__).resolve().parent.parent / "config" / "commodity_map_overlays.yaml"
    out: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [],
        "disclaimer": "Reference geography only — not real-time vessel or cargo tracking.",
    }
    if not path.is_file():
        return out
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        feats = []
        for layer in raw.get("overlays") or []:
            comms = [str(c).lower() for c in (layer.get("commodities") or [])]
            if comms and commodity_id.lower() not in comms:
                continue
            geom = layer.get("geometry")
            if not geom:
                continue
            feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": layer.get("id"),
                        "label": layer.get("label"),
                        "layer": layer.get("layer", "reference"),
                    },
                    "geometry": geom,
                }
            )
        out["features"] = feats
    except Exception as e:
        logger.debug("load_map_overlays_for_commodity: %s", e)
    return out
