#!/usr/bin/env python3
"""Verify generated onboarding YAML matches domain spec (runtime fields)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_API = Path(__file__).resolve().parent.parent
_DOMAINS = _API / "config" / "domains"
_SPECS = _DOMAINS / "specs"

if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.domain_spec import DomainSpec  # noqa: E402
from shared.services.domain_rss_seed import extract_seed_feed_category, extract_seed_feed_urls  # noqa: E402


def _norm_urls(cfg: dict[str, Any]) -> set[str]:
    return {u.strip() for u in extract_seed_feed_urls(cfg) if u.strip()}


def _compare(spec: DomainSpec, yaml_dict: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = spec.to_yaml_dict()
    for key in ("domain_key", "schema_name", "display_name", "is_active"):
        if yaml_dict.get(key) != expected.get(key):
            errors.append(f"{key}: yaml={yaml_dict.get(key)!r} spec={expected.get(key)!r}")
    if (yaml_dict.get("description") or "").strip() != (expected.get("description") or "").strip():
        errors.append("description mismatch")
    if int(yaml_dict.get("display_order") or 99) != int(expected.get("display_order") or 99):
        errors.append("display_order mismatch")
    if _norm_urls(yaml_dict) != _norm_urls(expected):
        errors.append(
            f"RSS URL set mismatch: yaml={len(_norm_urls(yaml_dict))} spec={len(_norm_urls(expected))}"
        )
    ycat = extract_seed_feed_category(yaml_dict)
    scat = spec.rss.seed_feed_category
    if ycat != scat and not (ycat == "General" and scat == "General"):
        errors.append(f"seed_feed_category: yaml={ycat!r} spec={scat!r}")
    yfa = yaml_dict.get("focus_areas") or []
    if list(yfa) != list(spec.focus_areas):
        errors.append("focus_areas mismatch")
    yllm = (yaml_dict.get("llm_prompt_guidance") or "").strip()
    if yllm != spec.llm_prompt_guidance.strip():
        errors.append("llm_prompt_guidance mismatch")
    ywa = yaml_dict.get("workload_assumptions")
    if spec.workload_assumptions is not None:
        if not isinstance(ywa, dict):
            errors.append("workload_assumptions missing in yaml")
        elif ywa != spec.workload_assumptions.model_dump():
            errors.append("workload_assumptions mismatch")
    elif ywa:
        errors.append("yaml has workload_assumptions but spec does not")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Spec vs generated YAML parity")
    parser.add_argument("--spec", type=Path, help="Single spec file")
    parser.add_argument("--all", action="store_true", help="All specs/*.domain.json")
    args = parser.parse_args()

    import yaml

    spec_paths: list[Path] = []
    if args.all:
        spec_paths = sorted(_SPECS.glob("*.domain.json"))
        spec_paths = [p for p in spec_paths if not p.name.startswith("_")]
    elif args.spec:
        spec_paths = [args.spec.resolve()]
    else:
        raise SystemExit("Specify --spec or --all")

    failed = 0
    for sp in spec_paths:
        spec = DomainSpec.from_json_file(sp)
        ypath = _DOMAINS / f"{spec.domain_key}.yaml"
        if not ypath.is_file():
            print(f"FAIL {sp.name}: missing {ypath}")
            failed += 1
            continue
        text = ypath.read_text(encoding="utf-8")
        if "Generated from specs/" not in text.split("\n", 1)[0]:
            print(f"WARN {ypath}: missing generated header (may be hand-edited)")
        body = text.split("\n", 1)[-1] if "\n" in text else text
        yaml_dict = yaml.safe_load(body)
        if not isinstance(yaml_dict, dict):
            print(f"FAIL {ypath}: invalid yaml")
            failed += 1
            continue
        errs = _compare(spec, yaml_dict)
        if errs:
            print(f"FAIL {spec.domain_key}:")
            for e in errs:
                print(f"  - {e}")
            failed += 1
        else:
            print(f"OK {spec.domain_key}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
