#!/usr/bin/env python3
"""
Scan extracted_claims for similar clusters (subject echoes + repeated triples).

For Cursor / Obsidian agents reviewing discovery candidates.

  PYTHONPATH=api uv run python api/scripts/scan_similar_claims.py
  PYTHONPATH=api uv run python api/scripts/scan_similar_claims.py --query "SpaceX" --since-days 14
  PYTHONPATH=api uv run python api/scripts/scan_similar_claims.py --domain-key politics --write-vault
  PYTHONPATH=api uv run python api/scripts/scan_similar_claims.py --format markdown --min-count 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_API_ROOT / ".env", override=False)
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and (_PROJECT_ROOT / ".db_password_widow").is_file():
    os.environ.setdefault("DB_PASSWORD", (_PROJECT_ROOT / ".db_password_widow").read_text().strip())


def _format_markdown(result: dict) -> str:
    lines = [
        "# Similar claim clusters",
        "",
        f"- Since: {result.get('scan_since')} ({result.get('since_days')}d)",
        f"- Domain: {result.get('domain_key') or 'all'}",
        f"- Query: {result.get('query') or '(none)'}",
        f"- Clusters: {result.get('cluster_count')}",
        "",
    ]
    for section, key in (
        ("Subject echoes", "subject_echo_clusters"),
        ("Repeated triples", "triple_repeat_clusters"),
    ):
        clusters = result.get(key) or []
        if not clusters:
            continue
        lines.extend([f"## {section}", ""])
        for i, c in enumerate(clusters, start=1):
            lines.append(f"### {i}. {c.get('subject_norm', c.get('cluster_type'))}")
            lines.append(
                f"- Claims: {c.get('claim_count')} | Contexts: {c.get('context_count')} "
                f"| Domains: {', '.join(c.get('domains') or [])} "
                f"| Avg conf: {c.get('avg_confidence')}"
            )
            lines.append(f"- {c.get('note_hint')}")
            lines.append("")
            for s in c.get("sample_claims") or []:
                pred = s.get("predicate_text") or "?"
                obj = s.get("object_text") or "?"
                lines.append(
                    f"  - claim `{s.get('id')}` ctx `{s.get('context_id')}` "
                    f"({s.get('domain_key')}): "
                    f"**{s.get('subject_text')}** {pred} {obj}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Find similar extracted_claim clusters")
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--min-count", type=int, default=3, help="Min claims per subject cluster")
    parser.add_argument("--min-contexts", type=int, default=2, help="Min distinct contexts")
    parser.add_argument("--domain-key", default=None)
    parser.add_argument("--query", default=None, help="ILIKE filter on subject/predicate/object")
    parser.add_argument(
        "--mode",
        choices=("subject", "triple", "both"),
        default="both",
    )
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument(
        "--write-vault",
        action="store_true",
        help="Write markdown to NEWS_INTEL_VAULT_PATH/00_Inbox/similar-claims-YYYYMMDD.md",
    )
    args = parser.parse_args()

    from services.claim_similarity_service import scan_similar_claim_clusters

    result = scan_similar_claim_clusters(
        since_days=args.since_days,
        min_claim_count=args.min_count,
        min_context_count=args.min_contexts,
        domain_key=args.domain_key,
        query=args.query,
        mode=args.mode,
        limit=args.limit,
    )

    if args.write_vault:
        from services import vault_bridge_service as vault

        md = _format_markdown(result)
        w = vault.write_similar_claim_clusters(md, meta=result)
        if not w.get("ok"):
            print(f"Vault write failed: {w.get('error')}", file=sys.stderr)
            return 1
        print(f"Wrote vault note: {w.get('path')}")
    elif args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(_format_markdown(result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
