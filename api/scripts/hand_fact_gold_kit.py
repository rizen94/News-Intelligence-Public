#!/usr/bin/env python3
"""Emit an n=15–20 Trump fact gold sheet from the v3 background ledger.

Score after morning prime / Pull: does the living brief match Supported sequence?

  PYTHONPATH=api .venv/bin/python api/scripts/hand_fact_gold_kit.py \\
    --out docs/HAND_FACT_GOLD_SHEET.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "api"))

# Seeded from 40_Reference/timelines/trump_politics_background_review.md (pass 3).
LEDGER_FACTS: list[dict] = [
    {
        "fact": "Todd Blanche nominated permanent AG (2026-06-04)",
        "theme": "appointment",
        "evidence": "CE 130693",
        "storyline_ids": [7697, 7709],
        "status": "Supported",
    },
    {
        "fact": "Blanche rescinds $1.8B anti-weaponization fund; holdouts advance nomination (2026-08-03)",
        "theme": "legislation",
        "evidence": "CE 145375/145299; storylines 5505/5653",
        "storyline_ids": [5505, 5343],
        "status": "Strong",
    },
    {
        "fact": "Senate narrowly confirms Blanche AG (2026-08-08)",
        "theme": "appointment",
        "evidence": "CE 148025; storylines 7697/7709",
        "storyline_ids": [7697, 7709],
        "status": "Strong",
    },
    {
        "fact": "$1.8B fund sequence: judicial block → political scrap/rescind → confirmation (not a single atom)",
        "theme": "contradiction",
        "evidence": "CE 130852/129790/145299; storylines 5343/5505",
        "storyline_ids": [5343, 5505, 7697],
        "status": "Strong",
    },
    {
        "fact": "Capital One closes Trump Org accounts amid AML concerns (2026-08-02)",
        "theme": "controversy",
        "evidence": "CE 145152; storylines 5362/5343",
        "storyline_ids": [5362, 5343],
        "status": "Strong",
    },
    {
        "fact": "Karoline Leavitt resigns as press secretary (2026-08-12–13); dual frames (family vs credibility)",
        "theme": "appointment",
        "evidence": "CE 148913/149106; storylines 9653/9966",
        "storyline_ids": [9653, 9966],
        "status": "Supported",
    },
    {
        "fact": "Kevin Warsh confirmed Fed Chair (2026-05-17)",
        "theme": "appointment",
        "evidence": "CE 151972",
        "storyline_ids": [],
        "status": "Supported",
    },
    {
        "fact": "SCOTUS keeps Lisa Cook as Fed governor (prefer CE 146343 over conflicting fire claim)",
        "theme": "contradiction",
        "evidence": "CE 146343 vs CONFLICT 128264",
        "storyline_ids": [],
        "status": "CONFLICT",
    },
    {
        "fact": "Birthright: early SCOTUS blocks stronger than 2026 EO 'admin win' CE claims",
        "theme": "contradiction",
        "evidence": "CE 111914/112172 vs CONFLICT 128264/146280",
        "storyline_ids": [],
        "status": "CONFLICT",
    },
    {
        "fact": "Mail-in voting EO / USPS rules: TRO → PI → SCOTUS stay fights (2026-08–09)",
        "theme": "legislation",
        "evidence": "CE 156318/157890/156378",
        "storyline_ids": [],
        "status": "Strong",
    },
    {
        "fact": "E. Jean Carroll rehearing denied; judgment stands (~$5–5.6m) (2026-08)",
        "theme": "lawsuit",
        "evidence": "CE legal cluster Aug 2026",
        "storyline_ids": [6792],
        "status": "Strong",
    },
    {
        "fact": "Trump refiles ~$10B WSJ defamation suit over Epstein reporting (2026-05-28)",
        "theme": "lawsuit",
        "evidence": "CE 131410; storyline 6792",
        "storyline_ids": [6792],
        "status": "Supported",
    },
    {
        "fact": "USS Abraham Lincoln families denounce Trump/Hegseth over deployment conditions",
        "theme": "controversy",
        "evidence": "storylines 11806/11773",
        "storyline_ids": [11806, 11773],
        "status": "Supported",
    },
    {
        "fact": "Admin deleted/altered ~400 federal datasets (public health/education/labor framing)",
        "theme": "controversy",
        "evidence": "CE 154523/154542; claims n≈3",
        "storyline_ids": [],
        "status": "Supported",
    },
    {
        "fact": "SCOTUS: IEEPA does not authorize unilateral tariffs (Learning Resources v. Trump)",
        "theme": "lawsuit",
        "evidence": "CE 149978/137427",
        "storyline_ids": [],
        "status": "Strong",
    },
    {
        "fact": "Blanche declines full DOJ independence pledge; denies Trump orders prosecutions (2026-08-16)",
        "theme": "appointment",
        "evidence": "CE 153333",
        "storyline_ids": [7697, 7709],
        "status": "Supported",
    },
    {
        "fact": "Childhood vaccine schedule EOs (MMR / cut 18→11) (2026-08-10–16)",
        "theme": "legislation",
        "evidence": "CE 150475/152626/152743",
        "storyline_ids": [],
        "status": "Supported",
    },
    {
        "fact": "One Big Beautiful Bill Act signed 2025-07-04 (tax cuts + safety-net cuts)",
        "theme": "legislation",
        "evidence": "CE 150645/147211",
        "storyline_ids": [],
        "status": "Supported",
    },
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_ROOT / "docs" / "HAND_FACT_GOLD_SHEET.md"))
    ap.add_argument(
        "--json-out", default=str(_ROOT / "data" / "hand_fact_gold_sheet.json")
    )
    args = ap.parse_args()

    rows = []
    for i, f in enumerate(LEDGER_FACTS[:20], 1):
        rows.append(
            {
                "n": i,
                "fact": f["fact"],
                "theme": f["theme"],
                "evidence": f["evidence"],
                "storyline_ids": f.get("storyline_ids") or [],
                "status": f["status"],
                "score_1_to_5": "",
                "notes": "",
                "source_ledger": "40_Reference/timelines/trump_politics_background_review.md",
            }
        )

    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(
        json.dumps(rows, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Hand fact gold sheet (Trump v3 ledger)",
        "",
        f"Generated: `{datetime.now(timezone.utc).isoformat()}` (UTC)",
        "",
        "Seeded from the Pass-3 NI background review (not a random `versioned_facts` dump).",
        "Score after morning prime / Pull on related expansions: does the brief match **Supported** sequence?",
        "Pass bar: mean ≥ **3.5** on n=15–20 (see `docs/QUALITY_READER_LOOP.md`).",
        "",
        "| # | Theme | Status | Fact | Evidence | Storylines | Your 1–5 | Notes |",
        "|---|-------|--------|------|----------|------------|----------|-------|",
    ]
    for r in rows:
        fact = str(r["fact"]).replace("|", "/")[:70]
        evid = str(r["evidence"]).replace("|", "/")[:40]
        sids = ",".join(str(x) for x in r["storyline_ids"]) or "—"
        lines.append(
            f"| {r['n']} | {r['theme']} | {r['status']} | {fact} | {evid} | {sids} |  |  |"
        )
    lines.extend(
        [
            "",
            "## How to score",
            "",
            "- **5** — expansion/brief matches Supported/Strong sequence; CONFLICT sides not asserted as settled",
            "- **3** — topic-right but wrong order/frame (e.g. fund 'scrapped' without block→rescind→confirm)",
            "- **1** — asserts CONFLICT atom as settled, or grounds on junk/off-topic entity brief",
            "",
            f"JSON: `{args.json_out}`",
            "",
            "Hygiene before/after for hand-priority arcs: `data/trump_p3_hygiene.json`.",
            "",
        ]
    )
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out} (n={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
