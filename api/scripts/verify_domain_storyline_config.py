#!/usr/bin/env python3
"""
Print resolved storyline_development profiles for pipeline-active domains.

  PYTHONPATH=api uv run python api/scripts/verify_domain_storyline_config.py
  PYTHONPATH=api uv run python api/scripts/verify_domain_storyline_config.py --domain medicine
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.domain_synthesis_config import get_storyline_development_config  # noqa: E402
from shared.domain_registry import get_pipeline_active_domain_keys  # noqa: E402


def _profile_dict(domain: str) -> dict:
    dev = get_storyline_development_config(domain)
    return {
        "domain": domain,
        "discovery": {
            "clustering_similarity_threshold": dev.discovery.clustering_similarity_threshold,
            "min_cluster_size": dev.discovery.min_cluster_size,
            "semantic_weight": dev.discovery.semantic_weight,
            "entity_weight": dev.discovery.entity_weight,
            "temporal_weight": dev.discovery.temporal_weight,
        },
        "proactive": {
            "keyword_similarity_threshold": dev.proactive.keyword_similarity_threshold,
            "min_articles": dev.proactive.min_articles,
            "promote_min_articles": dev.proactive.promote_min_articles,
            "promote_min_confidence": dev.proactive.promote_min_confidence,
            "lookback_hours": dev.proactive.lookback_hours,
        },
        "consolidation": {
            "merge_similarity_threshold": dev.consolidation.merge_similarity_threshold,
            "parent_similarity_threshold": dev.consolidation.parent_similarity_threshold,
            "min_articles_for_mega": dev.consolidation.min_articles_for_mega,
        },
        "narrative": {
            "outbreak_keywords": dev.narrative.outbreak_keywords[:8],
            "allow_promote_pair_on_outbreak": dev.narrative.allow_promote_pair_on_outbreak,
            "credible_source_domains": dev.narrative.credible_source_domains[:8],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify per-domain storyline development config")
    parser.add_argument("--domain", help="Single domain key (default: all pipeline-active)")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    domains = [args.domain] if args.domain else list(get_pipeline_active_domain_keys())
    profiles = [_profile_dict(d) for d in domains]

    if args.json:
        print(json.dumps(profiles, indent=2))
        return 0

    for p in profiles:
        print(f"\n=== {p['domain']} ===")
        print(json.dumps(p, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
