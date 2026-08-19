#!/usr/bin/env python3
"""
ONE-OFF CATCHUP (not always-on methodology): after storyline-first teaser
fulltext reset, re-score membership on affected episodes.

Steady-state membership review (mega drain) is separate. This script only
targets storylines whose members were tagged by
``reset_teaser_enrichment_for_fulltext.py --in-storyline``
(``metadata.fulltext_reset.wave``), calling ``review_storyline_membership``
directly — bypassing the mega-only drain (article_count >= 50).

Do not schedule this in AutomationManager. Leave
``STORYLINE_MEMBERSHIP_AUTO_APPLY`` alone (default propose-only for small
episodes). Mid-band rows land in ``intelligence.storyline_membership_actions``.

Usage (from repo root, after CE + UIE have drained the wave):
  PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py
  PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py --apply
  PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py --apply --domain politics

See docs/STORYLINE_TEASER_FULLTEXT_REPROCESS.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _load_dotenv_from_repo_root() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)


def _storyline_ids_for_wave(
    cur,
    *,
    schema: str,
    wave: str,
) -> list[int]:
    """Distinct active storyline IDs with at least one wave-tagged member."""
    cur.execute(
        f"""
        SELECT DISTINCT sa.storyline_id
        FROM {schema}.storyline_articles sa
        JOIN {schema}.articles a ON a.id = sa.article_id
        JOIN {schema}.storylines s ON s.id = sa.storyline_id
        WHERE s.merged_into_id IS NULL
          AND COALESCE(s.status, 'active') = 'active'
          AND a.metadata #>> '{{fulltext_reset,wave}}' = %s
        ORDER BY sa.storyline_id
        """,
        (wave,),
    )
    return [int(r[0]) for r in cur.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run membership review (default is dry-run list only)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        default=None,
        help="Limit to one domain key (repeatable)",
    )
    parser.add_argument(
        "--wave",
        default="storyline",
        help="Match metadata.fulltext_reset.wave (default: storyline)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max storylines per domain (0 = all)",
    )
    parser.add_argument(
        "--review-dry-run",
        action="store_true",
        help="Pass dry_run=True into review_storyline_membership (observe only)",
    )
    args = parser.parse_args()

    _load_dotenv_from_repo_root()

    try:
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import pipeline_url_schema_pairs
        from services.storyline_membership_review_service import (
            review_storyline_membership,
        )
    except ImportError:
        print(
            "Import failed: run from repo root with PYTHONPATH=api",
            file=sys.stderr,
        )
        return 1

    wave = (args.wave or "storyline").strip() or "storyline"
    wanted = {d.strip() for d in (args.domains or []) if d and d.strip()}
    pairs = [
        (dk, sch)
        for dk, sch in pipeline_url_schema_pairs()
        if not wanted or dk in wanted
    ]
    if not pairs:
        print("No matching pipeline domains.")
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"{mode}: ONE-OFF CATCHUP — membership review for wave={wave!r}")
    print(
        "Note: not the always-on mega membership drain; only wave-tagged storylines."
    )

    totals = {
        "storylines": 0,
        "scored": 0,
        "kept": 0,
        "demoted": 0,
        "unlinked": 0,
        "queued": 0,
        "errors": 0,
    }

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for domain_key, schema in pairs:
                    ids = _storyline_ids_for_wave(cur, schema=schema, wave=wave)
                    if args.limit and args.limit > 0:
                        ids = ids[: max(1, int(args.limit))]
                    print(
                        f"  {domain_key:24} schema={schema:22} "
                        f"storylines={len(ids)}"
                    )
                    totals["storylines"] += len(ids)
                    if not args.apply:
                        continue
                    for sid in ids:
                        try:
                            st = review_storyline_membership(
                                domain_key,
                                sid,
                                dry_run=True if args.review_dry_run else None,
                            )
                            if st.get("error"):
                                totals["errors"] += 1
                                print(
                                    f"    storyline {sid}: error={st.get('error')}"
                                )
                                continue
                            for k in ("scored", "kept", "demoted", "unlinked", "queued"):
                                totals[k] += int(st.get(k, 0) or 0)
                            print(
                                f"    storyline {sid}: scored={st.get('scored', 0)} "
                                f"kept={st.get('kept', 0)} demoted={st.get('demoted', 0)} "
                                f"unlinked={st.get('unlinked', 0)} queued={st.get('queued', 0)}"
                            )
                        except Exception as e:
                            totals["errors"] += 1
                            print(f"    storyline {sid}: ERROR {e}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("totals:", totals)
    if not args.apply and totals["storylines"]:
        print("Re-run with --apply to call review_storyline_membership on these IDs.")
    return 0 if totals["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
