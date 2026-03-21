"""
Source credibility tiers from orchestrator_governance.yaml (section source_credibility).

Used at RSS ingest to tag feeds and optionally scale heuristic quality_score.
Tiers are matched in order: first matching tier wins, else default_tier applies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceCredibilityResult:
    """Resolved tier for a feed URL + feed name."""

    tier_id: str
    label: str
    multiplier: float
    requires_corroboration: bool
    matched_rule: str  # e.g. "host_suffix:.gov", "host_contains:reuters", "default"

    def to_metadata_dict(self, feed_url: str) -> dict[str, Any]:
        return {
            "tier": self.tier_id,
            "label": self.label,
            "multiplier": self.multiplier,
            "requires_corroboration": self.requires_corroboration,
            "matched_rule": self.matched_rule,
            "feed_url": (feed_url or "")[:500],
        }


def _cfg() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("source_credibility") or {}
        if not isinstance(raw, dict):
            return {}
        return raw
    except Exception as e:
        logger.debug("source_credibility config: %s", e)
        return {}


def _host(feed_url: str) -> str:
    if not feed_url or not str(feed_url).strip():
        return ""
    try:
        p = urlparse(feed_url.strip())
        h = (p.hostname or "").lower()
        return h
    except Exception:
        return ""


def _norm_name(feed_name: str) -> str:
    return (feed_name or "").strip().lower()


def resolve_source_credibility(feed_url: str, feed_name: str = "") -> SourceCredibilityResult:
    """
    Resolve credibility tier from governance YAML.

    Matching (per tier, in tier_order):
    - host_suffixes: hostname ends with entry (e.g. ".gov")
    - host_contains: substring of hostname
    - name_keywords: substring of feed_name (case-insensitive)

    If no tier matches, uses default_tier definition (must exist under tiers).
    """
    c = _cfg()
    if not c.get("enabled", True):
        return SourceCredibilityResult(
            tier_id="disabled",
            label="Credibility tiers disabled",
            multiplier=float(c.get("disabled_multiplier", 1.0)),
            requires_corroboration=False,
            matched_rule="disabled",
        )

    tiers: dict[str, Any] = c.get("tiers") or {}
    tier_order: list[str] = list(c.get("tier_order") or list(tiers.keys()))
    default_id = str(c.get("default_tier") or "tier_2")

    host = _host(feed_url)
    name = _norm_name(feed_name)

    def _check_tier(tier_id: str) -> SourceCredibilityResult | None:
        spec = tiers.get(tier_id)
        if not isinstance(spec, dict):
            return None

        label = str(spec.get("label") or tier_id)
        mult = float(spec.get("multiplier", 1.0))
        req = bool(spec.get("requires_corroboration", False))

        for suf in spec.get("host_suffixes") or []:
            s = str(suf).lower().strip()
            if s and host.endswith(s):
                return SourceCredibilityResult(
                    tier_id=tier_id,
                    label=label,
                    multiplier=mult,
                    requires_corroboration=req,
                    matched_rule=f"host_suffix:{suf}",
                )

        for sub in spec.get("host_contains") or []:
            sub_l = str(sub).lower().strip()
            if sub_l and sub_l in host:
                return SourceCredibilityResult(
                    tier_id=tier_id,
                    label=label,
                    multiplier=mult,
                    requires_corroboration=req,
                    matched_rule=f"host_contains:{sub}",
                )

        for kw in spec.get("name_keywords") or []:
            kw_l = str(kw).lower().strip()
            if kw_l and kw_l in name:
                return SourceCredibilityResult(
                    tier_id=tier_id,
                    label=label,
                    multiplier=mult,
                    requires_corroboration=req,
                    matched_rule=f"name_keyword:{kw}",
                )

        return None

    for tid in tier_order:
        hit = _check_tier(str(tid))
        if hit:
            return hit

    # Explicit default tier (no pattern match — use tier's multiplier/flags only)
    dspec = tiers.get(default_id)
    if isinstance(dspec, dict):
        return SourceCredibilityResult(
            tier_id=default_id,
            label=str(dspec.get("label") or default_id),
            multiplier=float(dspec.get("multiplier", 0.85)),
            requires_corroboration=bool(dspec.get("requires_corroboration", False)),
            matched_rule="default_tier",
        )

    return SourceCredibilityResult(
        tier_id="tier_unknown",
        label="Unknown tier config",
        multiplier=1.0,
        requires_corroboration=False,
        matched_rule="fallback",
    )


def apply_credibility_to_quality_score(
    quality_score: float,
    feed_url: str,
    feed_name: str = "",
) -> tuple[float, SourceCredibilityResult]:
    """
    Optionally scale quality_score by tier multiplier when apply_to_quality_score is true.
    Returns (adjusted_quality, result).
    """
    c = _cfg()
    result = resolve_source_credibility(feed_url, feed_name)
    if not c.get("apply_to_quality_score", True):
        return max(0.0, min(1.0, float(quality_score))), result
    if result.tier_id == "disabled":
        return max(0.0, min(1.0, float(quality_score))), result
    q = float(quality_score) * float(result.multiplier)
    return max(0.0, min(1.0, q)), result
