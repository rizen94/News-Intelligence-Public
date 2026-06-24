"""Spine ingest CLI — preload sources per revised strategy."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NRI identity spine ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    edgar_p = sub.add_parser("edgar", help="SEC EDGAR companies (CIK-deduped)")
    edgar_p.add_argument("--limit", type=int, default=None, help="Max companies (default: all deduped)")

    gleif_p = sub.add_parser("gleif", help="GLEIF LEI Golden Copy CSV")
    gleif_p.add_argument("--path", type=str, default=None)
    gleif_p.add_argument("--limit", type=int, default=None)

    wd_p = sub.add_parser("wikidata-crosswalk", help="Wikidata Phase 1 crosswalk hub")
    wd_p.add_argument("--path", type=str, default=None)
    wd_p.add_argument("--limit", type=int, default=None)

    wd2_p = sub.add_parser("wikidata-notable", help="Wikidata Phase 2 notable slice")
    wd2_p.add_argument("--path", type=str, default=None)
    wd2_p.add_argument("--limit", type=int, default=None)

    cong_p = sub.add_parser("congress", help="unitedstates/congress-legislators")
    cong_p.add_argument("--limit", type=int, default=None)

    sub.add_parser("anchor-join", help="Audit deterministic anchor collisions")

    all_p = sub.add_parser("preload-all", help="EDGAR + congress + anchor audit (NAS sources if present)")
    all_p.add_argument("--edgar-limit", type=int, default=None)

    args = parser.parse_args(argv)

    if args.command == "edgar":
        from nri_core.spine.ingest.mappers.edgar import ingest_edgar_subset

        n = ingest_edgar_subset(limit=args.limit)
        print(f"EDGAR ingested: {n}")
    elif args.command == "gleif":
        from pathlib import Path

        from nri_core.spine.ingest.gleif.loader import ingest_gleif_file

        path = Path(args.path) if args.path else None
        n = ingest_gleif_file(path=path, limit=args.limit)
        print(f"GLEIF ingested: {n}")
    elif args.command == "wikidata-crosswalk":
        from pathlib import Path

        from nri_core.spine.ingest.wikidata.crosswalk import ingest_crosswalk_file

        path = Path(args.path) if args.path else None
        n = ingest_crosswalk_file(path=path, limit=args.limit)
        print(f"Wikidata crosswalk ingested: {n}")
    elif args.command == "wikidata-notable":
        from pathlib import Path

        from nri_core.spine.ingest.wikidata.notable import ingest_notable_file

        path = Path(args.path) if args.path else None
        n = ingest_notable_file(path=path, limit=args.limit)
        print(f"Wikidata notable ingested: {n}")
    elif args.command == "congress":
        from nri_core.spine.ingest.mappers.congress import ingest_congress_legislators

        n = ingest_congress_legislators(limit=args.limit)
        print(f"Congress legislators ingested: {n}")
    elif args.command == "anchor-join":
        from nri_core.spine.resolution.anchor_join import run_anchor_join_audit

        stats = run_anchor_join_audit()
        print(f"Anchor join audit: {stats}")
    elif args.command == "preload-all":
        from nri_core.spine.ingest.gleif.loader import ingest_gleif_file
        from nri_core.spine.ingest.mappers.congress import ingest_congress_legislators
        from nri_core.spine.ingest.mappers.edgar import ingest_edgar_subset
        from nri_core.spine.ingest.wikidata.crosswalk import ingest_crosswalk_file
        from nri_core.spine.resolution.anchor_join import run_anchor_join_audit

        results = {
            "edgar": ingest_edgar_subset(limit=args.edgar_limit),
            "gleif": ingest_gleif_file(),
            "wikidata_crosswalk": ingest_crosswalk_file(),
            "congress": ingest_congress_legislators(),
            "anchor_join": run_anchor_join_audit(),
        }
        print(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
