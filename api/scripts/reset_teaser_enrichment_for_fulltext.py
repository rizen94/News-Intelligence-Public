#!/usr/bin/env python3
"""
ONE-OFF CATCHUP (not always-on methodology): reset false-enriched RSS teasers
so content_enrichment must fetch full article text.

Steady-state ingest already leaves short RSS as ``pending`` (fulltext-first gate).
This script only repairs historical rows that were wrongly marked ``enriched``
with a teaser body. Prefer ``--in-storyline`` (~2k storyline-linked rows), not
the full ~13k orphan teasers.

Tags ``metadata.fulltext_reset`` so the companion one-off review script can
target the same wave. Do not wire this into AutomationManager schedules.

Usage (from repo root):
  PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py --in-storyline
  PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py --in-storyline --apply
  PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py --in-storyline --apply --domain politics

See docs/STORYLINE_TEASER_FULLTEXT_REPROCESS.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates (default is dry-run)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        dest="domains",
        default=None,
        help="Limit to one domain key (repeatable)",
    )
    parser.add_argument(
        "--in-storyline",
        action="store_true",
        help=(
            "Only reset teasers that already sit on a storyline "
            "(recommended first wave; avoids scraping ~13k orphans)"
        ),
    )
    parser.add_argument(
        "--paywall-hosts",
        action="store_true",
        help=(
            "Only reset short-enriched rows whose URL matches known paywall hosts "
            "(bloomberg/ft/wsj/etc). Safer than resetting all orphans."
        ),
    )
    parser.add_argument(
        "--wave",
        default="storyline",
        help="Value written to metadata.fulltext_reset.wave (default: storyline)",
    )
    args = parser.parse_args()

    _load_dotenv_from_repo_root()

    try:
        from shared.article_processing_gates import fulltext_min_chars
        from shared.database.connection import get_db_connection_context
        from shared.domain_registry import pipeline_url_schema_pairs
        from services.article_content_enrichment_service import (
            _KNOWN_PAYWALL_HOST_FRAGMENTS,
        )
    except ImportError:
        print(
            "Import failed: run from repo root with PYTHONPATH=api",
            file=sys.stderr,
        )
        return 1

    min_chars = fulltext_min_chars()
    wanted = {d.strip() for d in (args.domains or []) if d and d.strip()}
    pairs = [
        (dk, sch)
        for dk, sch in pipeline_url_schema_pairs()
        if not wanted or dk in wanted
    ]
    if not pairs:
        print("No matching pipeline domains.")
        return 1

    wave = (args.wave or "storyline").strip() or "storyline"
    if args.paywall_hosts:
        scope = "paywall-host teasers"
        if not args.wave or args.wave == "storyline":
            wave = "paywall_hosts"
    elif args.in_storyline:
        scope = "in-storyline teasers"
    else:
        scope = "ALL teasers"
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"{mode}: ONE-OFF CATCHUP — reset enriched rows with "
        f"LENGTH(content) < {min_chars} ({scope})"
    )
    print(
        "Note: this is not steady-state ingest; new teasers already stay pending "
        "under the fulltext-first gate."
    )
    if not args.in_storyline and not args.paywall_hosts:
        print(
            "WARNING: without --in-storyline/--paywall-hosts this queues every "
            "short-enriched row (~13k). Prefer a scoped flag for the first wave.",
            file=sys.stderr,
        )

    storyline_clause = ""
    if args.in_storyline:
        storyline_clause = """
          AND EXISTS (
            SELECT 1 FROM {schema}.storyline_articles sa
            WHERE sa.article_id = a.id
          )
        """

    paywall_clause = ""
    if args.paywall_hosts:
        # position() avoids ILIKE %…% issues under psycopg2 pyformat.
        host_preds = " OR ".join(
            f"position('{frag}' in lower(COALESCE(a.url, ''))) > 0"
            for frag in _KNOWN_PAYWALL_HOST_FRAGMENTS
        )
        paywall_clause = f" AND ({host_preds}) "

    reset_meta = json.dumps(
        {
            "fulltext_reset": {
                "wave": wave,
                "at": datetime.now(timezone.utc).isoformat(),
                "in_storyline": bool(args.in_storyline),
                "paywall_hosts": bool(args.paywall_hosts),
            }
        }
    )

    total = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for domain_key, schema in pairs:
                    where_extra = storyline_clause.format(schema=schema) if storyline_clause else ""
                    where_extra += paywall_clause
                    cur.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM {schema}.articles a
                        WHERE a.enrichment_status = 'enriched'
                          AND LENGTH(COALESCE(a.content, '')) < %s
                          {where_extra}
                        """,
                        (min_chars,),
                    )
                    n = int((cur.fetchone() or [0])[0] or 0)
                    print(f"  {domain_key:24} schema={schema:22} teaser_enriched={n}")
                    if not args.apply or n == 0:
                        total += n
                        continue
                    cur.execute(
                        f"""
                        UPDATE {schema}.articles a
                        SET enrichment_status = 'pending',
                            enrichment_attempts = 0,
                            metadata = (
                              COALESCE(a.metadata, '{{}}'::jsonb)
                              #- '{{pipeline,unified_intake_extraction}}'
                              #- '{{pipeline,entity_extraction}}'
                              #- '{{pipeline,event_extraction}}'
                            ) || %s::jsonb,
                            updated_at = NOW()
                        WHERE a.enrichment_status = 'enriched'
                          AND LENGTH(COALESCE(a.content, '')) < %s
                          {where_extra}
                        """,
                        (reset_meta, min_chars),
                    )
                    updated = cur.rowcount or 0
                    total += updated
                    print(f"    updated={updated}")
            if args.apply:
                conn.commit()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"{'reset' if args.apply else 'would reset'}: {total}")
    if not args.apply and total:
        flags = []
        if args.in_storyline:
            flags.append("--in-storyline")
        if args.paywall_hosts:
            flags.append("--paywall-hosts")
        print("Re-run with --apply " + " ".join(flags) + " to queue them for content_enrichment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
