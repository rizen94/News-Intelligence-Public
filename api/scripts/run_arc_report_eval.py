#!/usr/bin/env python3
"""Run arc report golden-question eval harness (structure checks, no LLM judge).

  PYTHONPATH=api uv run python api/scripts/run_arc_report_eval.py
  PYTHONPATH=api uv run python api/scripts/run_arc_report_eval.py --arc resource_geopolitics
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from services.slow_report_service import get_latest_arc_report

_EVAL_PATH = Path(__file__).resolve().parents[2] / "tests" / "eval" / "arc_report_golden_questions.yaml"
_CIT = re.compile(r"\[CIT:[^\]]+\]")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arc", default=None)
    args = p.parse_args()

    if not _EVAL_PATH.is_file():
        print(f"Missing eval file: {_EVAL_PATH}")
        return 1

    with open(_EVAL_PATH) as f:
        spec = yaml.safe_load(f) or {}

    arcs = spec.get("arcs") or {}
    failed = 0
    passed = 0

    for arc_id, arc_spec in arcs.items():
        if args.arc and arc_id != args.arc:
            continue
        report = get_latest_arc_report(arc_id)
        if not report:
            print(f"FAIL {arc_id}: no report in intelligence.arc_reports")
            failed += 1
            continue
        content = report.get("content_markdown") or ""
        words = len(content.split())
        citations = report.get("citations") or []
        validation = report.get("validation") or {}

        for q in arc_spec.get("questions") or []:
            qid = q.get("id") or "?"
            ok = True
            reasons: list[str] = []

            min_markers = q.get("min_citation_markers") or 0
            markers = len(_CIT.findall(content))
            if markers < min_markers:
                ok = False
                reasons.append(f"citations {markers} < {min_markers}")

            for ref_id in q.get("must_include_reference_ids") or []:
                key = f"REF-{ref_id}"
                found = key in content or any(
                    (isinstance(c, dict) and (c.get("citation_key") == key))
                    or (
                        isinstance(c, dict)
                        and isinstance(c.get("metadata"), dict)
                        and c.get("metadata", {}).get("citation_key") == key
                    )
                    for c in citations
                )
                if not found:
                    ok = False
                    reasons.append(f"missing ref {ref_id}")

            if not validation.get("passed", True):
                ok = False
                reasons.append("validation failed")

            if ok:
                print(f"PASS {arc_id}/{qid} ({words} words)")
                passed += 1
            else:
                print(f"FAIL {arc_id}/{qid}: {'; '.join(reasons)}")
                failed += 1

    print(f"\nSummary: passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
