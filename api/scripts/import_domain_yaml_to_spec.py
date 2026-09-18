#!/usr/bin/env python3
"""Import hand-authored api/config/domains/*.yaml into specs/{domain_key}.domain.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_API = Path(__file__).resolve().parent.parent
_DOMAINS = _API / "config" / "domains"
_SPECS = _DOMAINS / "specs"

if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.services.domain_rss_seed import extract_seed_feed_entries, extract_seed_feed_category  # noqa: E402

# Known applied silo migrations (metadata only).
_MIGRATION_REF_BY_KEY: dict[str, str] = {
    "medicine": "187_medicine_domain_silo.sql",
    "legal": "180_legal_domain_silo.sql",
    "artificial-intelligence": "188_artificial_intelligence_domain_silo.sql",
    "politics": "201_politics2_finance2_domain_silos.sql",
    "finance": "201_politics2_finance2_domain_silos.sql",
}

_ARTICLE_TOPIC_CLUSTERS_KEYS = frozenset(
    {
        "medicine",
        "legal",
        "artificial-intelligence",
        "environment-climate",
        "politics",
        "finance",
    }
)


def _yaml_to_spec_dict(data: dict[str, Any]) -> dict[str, Any]:
    dk = str(data.get("domain_key") or "").strip()
    feeds_raw = []
    for entry in extract_seed_feed_entries(data):
        item: dict[str, Any] = {"feed_url": entry.feed_url}
        if entry.feed_name:
            item["feed_name"] = entry.feed_name
        if entry.fetch_interval_seconds is not None:
            item["fetch_interval_seconds"] = entry.fetch_interval_seconds
        feeds_raw.append(item)

    wa = data.get("workload_assumptions")
    workload = None
    if isinstance(wa, dict):
        workload = {
            "expected_active_feeds": int(wa.get("expected_active_feeds") or 0),
            "rough_new_articles_per_day": int(wa.get("rough_new_articles_per_day") or 0),
            "llm_heavy_phases_enabled": bool(wa.get("llm_heavy_phases_enabled", True)),
        }

    focus = data.get("focus_areas")
    focus_list = [str(x) for x in focus] if isinstance(focus, list) else []

    return {
        "version": 1,
        "domain_key": dk,
        "schema_name": str(data.get("schema_name") or "").strip(),
        "display_name": str(data.get("display_name") or "").strip(),
        "description": str(data.get("description") or "").strip(),
        "display_order": int(data.get("display_order") or 99),
        "is_active": bool(data.get("is_active", True)),
        "database": {
            "clone_from": "politics",
            "include_article_topic_clusters": dk in _ARTICLE_TOPIC_CLUSTERS_KEYS,
            "migration_ref": _MIGRATION_REF_BY_KEY.get(dk),
        },
        "rss": {
            "seed_feed_category": extract_seed_feed_category(data),
            "feeds": feeds_raw,
        },
        "focus_areas": focus_list,
        "llm_prompt_guidance": str(data.get("llm_prompt_guidance") or "").strip(),
        "workload_assumptions": workload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="YAML onboarding → domain spec JSON")
    parser.add_argument("--yaml", type=Path, help="Single YAML file")
    parser.add_argument("--all", action="store_true", help="Import all non-_*.yaml in domains/")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    import yaml

    paths: list[Path] = []
    if args.all:
        paths = sorted(p for p in _DOMAINS.glob("*.yaml") if not p.name.startswith("_"))
    elif args.yaml:
        paths = [args.yaml.resolve()]
    else:
        raise SystemExit("Specify --yaml PATH or --all")

    _SPECS.mkdir(parents=True, exist_ok=True)
    for ypath in paths:
        data = yaml.safe_load(ypath.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print(f"Skip invalid: {ypath}")
            continue
        dk = str(data.get("domain_key") or ypath.stem).strip()
        out = _SPECS / f"{dk}.domain.json"
        if out.exists() and not args.force:
            print(f"Skip exists: {out}")
            continue
        spec_dict = _yaml_to_spec_dict(data)
        out.write_text(json.dumps(spec_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
