#!/usr/bin/env python3
"""Emit an n=20 hand_F4 scoring sheet (understand arc?) from the quality baseline sample.

  PYTHONPATH=api .venv/bin/python api/scripts/hand_f4_scoring_kit.py \\
    --out docs/HAND_F4_SCORING_SHEET.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "api"))

env_file = _ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_ROOT / "docs" / "HAND_F4_SCORING_SHEET.md"))
    ap.add_argument("--json-out", default=str(_ROOT / "data" / "hand_f4_scoring_sheet.json"))
    args = ap.parse_args()

    # Reuse baseline sample construction
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "q0", str(_ROOT / "api" / "scripts" / "quality_reader_baseline_q0.py")
    )
    assert spec and spec.loader
    q0 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q0)
    data = q0.run_baseline()
    sample = data.get("hand_proxy_sample") or []

    rows = []
    for i, h in enumerate(sample[:20], 1):
        rows.append(
            {
                "n": i,
                "domain": h.get("domain"),
                "storyline_id": h.get("storyline_id"),
                "title": h.get("title") or h.get("storyline_title") or "",
                "brief_source": h.get("brief_source"),
                "proxy_F4": h.get("proxy_F4_understand_arc"),
                "score_1_to_5": "",
                "notes": "",
            }
        )

    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Hand F4 scoring sheet (understand arc?)",
        "",
        f"Generated: `{datetime.now(timezone.utc).isoformat()}` (UTC)",
        "",
        "Score each storyline **1–5** after reading Home/pack brief (living expansion or durable).",
        "Pass bar: mean ≥ **3.5** on n=20 (see `docs/QUALITY_READER_LOOP.md`).",
        "",
        "| # | Domain | Storyline | Title | brief_source | Proxy | Your 1–5 | Notes |",
        "|---|--------|-----------|-------|--------------|-------|----------|-------|",
    ]
    for r in rows:
        title = str(r["title"] or "").replace("|", "/")[:60]
        lines.append(
            f"| {r['n']} | {r['domain']} | {r['storyline_id']} | {title} | "
            f"{r.get('brief_source') or ''} | {r.get('proxy_F4')} |  |  |"
        )
    lines.extend(
        [
            "",
            "## How to score",
            "",
            "- **5** — clear arc, citeable, I know what changed and why it matters",
            "- **3** — partial; need another click or the durable/live label is confusing",
            "- **1** — magnet / incoherent / empty / wrong story",
            "",
            f"JSON: `{args.json_out}`",
            "",
        ]
    )
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out} (n={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
