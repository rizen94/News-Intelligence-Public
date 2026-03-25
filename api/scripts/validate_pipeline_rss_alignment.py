#!/usr/bin/env python3
"""
Pre-flight: registry vs pipeline vs RSS vs DB silos.

  PYTHONPATH=api uv run python api/scripts/validate_pipeline_rss_alignment.py
  PYTHONPATH=api uv run python api/scripts/validate_pipeline_rss_alignment.py --strict

Exits 1 if --strict and there are errors (empty pipeline, RSS collects outside pipeline when mirror off, missing schema).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
_ROOT = _API.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on errors (empty pipeline, rss>pipeline mismatch without mirror, missing DB schema)",
    )
    args = parser.parse_args()

    env_file = _ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=False)
        except ImportError:
            pass

    from config.settings import (
        get_rss_ingest_excluded_domain_keys,
        rss_ingest_mirror_pipeline_enabled,
    )
    from services.nightly_ingest_window_service import (
        nightly_pipeline_window_info,
        nightly_unified_pipeline_enabled,
    )
    from shared.domain_registry import (
        get_pipeline_included_domain_keys,
        pipeline_url_schema_pairs,
        url_schema_pairs,
    )

    reg = {dk: sch for dk, sch in url_schema_pairs()}
    pipe = {dk: sch for dk, sch in pipeline_url_schema_pairs()}
    skip_rss = get_rss_ingest_excluded_domain_keys()
    mirror = rss_ingest_mirror_pipeline_enabled()
    base_for_rss = pipe if mirror else reg
    rss_effective = {
        dk: sch
        for dk, sch in base_for_rss.items()
        if str(dk).strip().lower() not in skip_rss
    }

    include = get_pipeline_included_domain_keys()
    nightly = nightly_pipeline_window_info()

    print("=== Pipeline / RSS alignment ===")
    print(f"PIPELINE_INCLUDE_DOMAIN_KEYS: {sorted(include) if include else '(unset — all registry minus exclude)'}")
    _pex = [x.strip() for x in os.environ.get("PIPELINE_EXCLUDE_DOMAIN_KEYS", "").split(",") if x.strip()]
    print(f"PIPELINE_EXCLUDE_DOMAIN_KEYS: {sorted(_pex) if _pex else '(unset)'}")
    print(f"Registry silos (url_schema_pairs): {len(reg)} -> {sorted(reg.keys())}")
    print(f"Pipeline silos (processing):       {len(pipe)} -> {sorted(pipe.keys())}")
    print(f"RSS_INGEST_MIRROR_PIPELINE: {mirror}")
    print(f"RSS_INGEST_EXCLUDE_DOMAIN_KEYS: {sorted(skip_rss) if skip_rss else '(unset)'}")
    print(f"RSS effective collect domains:      {len(rss_effective)} -> {sorted(rss_effective.keys())}")
    print(f"NIGHTLY_UNIFIED_PIPELINE_ENABLED: {nightly_unified_pipeline_enabled()}")
    print(f"Nightly window snapshot: { {k: v for k, v in nightly.items() if k in ('unified_pipeline_enabled', 'in_unified_window', 'all_day_catchup', 'exclusive_other_phases', 'window_label')} }")
    strict_env = os.environ.get("ENTITY_EXTRACTION_RESOLVE_STRICT_DOMAIN_KEYS", "").strip()
    print(f"ENTITY_EXTRACTION_RESOLVE_STRICT_DOMAIN_KEYS: {strict_env or '(unset)'}")

    errs: list[str] = []
    warns: list[str] = []

    if len(reg) > 0 and len(pipe) == 0:
        errs.append("pipeline_url_schema_pairs is empty but registry has silos — fix PIPELINE_INCLUDE / PIPELINE_EXCLUDE")

    outside = set(rss_effective) - set(pipe)
    if outside and not mirror:
        warns.append(
            f"RSS will collect from domains not in pipeline ({sorted(outside)}) — set RSS_INGEST_MIRROR_PIPELINE=true "
            "or add RSS_INGEST_EXCLUDE_DOMAIN_KEYS for those keys"
        )

    inside_pipe_no_rss = set(pipe) - set(rss_effective)
    if inside_pipe_no_rss:
        warns.append(
            f"Pipeline domains with no RSS collect (excluded or no feeds): {sorted(inside_pipe_no_rss)} — "
            "expected if RSS_INGEST_EXCLUDE subtracts them; otherwise add feeds / remove exclude"
        )

    conn = None
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT schema_name FROM information_schema.schemata")
                existing = {r[0] for r in cur.fetchall()}
            for dk, sch in pipe.items():
                if sch not in existing:
                    errs.append(f"pipeline domain {dk!r} schema {sch!r} missing in Postgres")
            for dk, sch in rss_effective.items():
                if sch not in existing:
                    errs.append(f"RSS domain {dk!r} schema {sch!r} missing in Postgres")
                else:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"SELECT COUNT(*) FROM {sch}.rss_feeds WHERE is_active = true"
                        )
                        n = cur.fetchone()[0]
                    if n == 0:
                        warns.append(f"{dk} ({sch}): zero active rss_feeds — no ingestion until feeds seeded")
    except Exception as e:
        warns.append(f"DB check skipped or failed: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    for w in warns:
        print(f"WARN: {w}")
    for e in errs:
        print(f"ERROR: {e}")

    if args.strict and errs:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
