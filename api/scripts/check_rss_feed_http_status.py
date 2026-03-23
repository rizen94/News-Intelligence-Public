#!/usr/bin/env python3
"""
HTTP probe every RSS feed URL stored in domain silos ({schema}.rss_feeds).

For each feed, performs several GET requests (like repeated curls), records status code,
latency, and errors. Use to find dead URLs, 403/451 blocks, or TLS issues.

  cd /path/to/repo && PYTHONPATH=api uv run python api/scripts/check_rss_feed_http_status.py
  PYTHONPATH=api uv run python api/scripts/check_rss_feed_http_status.py -o /tmp/rss_probe.csv
  PYTHONPATH=api uv run python api/scripts/check_rss_feed_http_status.py --attempts 5 --timeout 25

Requires DB_* in env (same as API). Feeds come from registry domains via url_schema_pairs().
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api = Path(__file__).resolve().parent.parent
    load_dotenv(_api / ".env", override=False)
    load_dotenv(_api.parent / ".env", override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; NewsIntel-RSS-FeedCheck/1.0; +https://github.com/) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_once(url: str, timeout: float, session) -> dict:
    """Single GET; returns keys: http_status, ok, elapsed_ms, error, content_type, bytes_len."""
    t0 = time.perf_counter()
    out = {
        "http_status": "",
        "ok": False,
        "elapsed_ms": 0.0,
        "error": "",
        "content_type": "",
        "bytes_len": 0,
    }
    try:
        r = session.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": os.environ.get("RSS_FEED_CHECK_USER_AGENT", DEFAULT_UA),
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        out["http_status"] = r.status_code
        out["ok"] = r.ok
        ct = r.headers.get("Content-Type", "")
        out["content_type"] = (ct or "")[:200]
        body = r.content or b""
        out["bytes_len"] = len(body)
    except Exception as e:
        out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        out["error"] = f"{type(e).__name__}: {e}"[:500]
        out["ok"] = False
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "HTTP-probe RSS feed URLs from {schema}.rss_feeds for all registry domains; "
            "record status, timing, and errors (multiple GETs per URL)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Number of GETs per feed URL (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Per-request timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.4,
        help="Seconds to sleep between attempts for the same feed (default: 0.4)",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Also probe feeds where is_active is false",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Write CSV to this path (default: print table to stdout only)",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="With -o, write CSV only; suppress human summary on stderr",
    )
    args = parser.parse_args()

    if args.attempts < 1:
        print("ERROR: --attempts must be >= 1", file=sys.stderr)
        return 1

    try:
        import requests
    except ImportError:
        print("ERROR: pip install requests", file=sys.stderr)
        return 1

    from shared.database.connection import get_db_connection
    from shared.domain_registry import url_schema_pairs

    pairs = list(url_schema_pairs())
    if not pairs:
        print("No domains in registry.", file=sys.stderr)
        return 1

    rows_out: list[dict] = []
    session = requests.Session()

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            for domain_key, schema in pairs:
                active_clause = "" if args.include_inactive else "WHERE is_active = true"
                try:
                    cur.execute(
                        f"""
                        SELECT id, feed_name, feed_url, is_active
                        FROM {schema}.rss_feeds
                        {active_clause}
                        ORDER BY id
                        """
                    )
                    feeds = cur.fetchall()
                except Exception as e:
                    print(f"WARN: {schema}.rss_feeds: {e}", file=sys.stderr)
                    continue

                for fid, name, url, is_active in feeds:
                    if not url or not str(url).strip():
                        for attempt in range(1, args.attempts + 1):
                            rows_out.append(
                                {
                                    "domain_key": domain_key,
                                    "schema": schema,
                                    "feed_id": fid,
                                    "feed_name": name or "",
                                    "feed_url": "",
                                    "is_active": is_active,
                                    "attempt": attempt,
                                    "http_status": "",
                                    "ok": False,
                                    "elapsed_ms": "",
                                    "error": "empty feed_url",
                                    "content_type": "",
                                    "bytes_len": 0,
                                }
                            )
                        continue

                    url_s = str(url).strip()
                    for attempt in range(1, args.attempts + 1):
                        res = _fetch_once(url_s, args.timeout, session)
                        rows_out.append(
                            {
                                "domain_key": domain_key,
                                "schema": schema,
                                "feed_id": fid,
                                "feed_name": (name or "")[:500],
                                "feed_url": url_s[:2000],
                                "is_active": is_active,
                                "attempt": attempt,
                                "http_status": res["http_status"],
                                "ok": res["ok"],
                                "elapsed_ms": res["elapsed_ms"],
                                "error": res["error"],
                                "content_type": res["content_type"],
                                "bytes_len": res["bytes_len"],
                            }
                        )
                        if attempt < args.attempts and args.pause > 0:
                            time.sleep(args.pause)
    finally:
        conn.close()

    fieldnames = [
        "domain_key",
        "schema",
        "feed_id",
        "feed_name",
        "feed_url",
        "is_active",
        "attempt",
        "http_status",
        "ok",
        "elapsed_ms",
        "error",
        "content_type",
        "bytes_len",
    ]

    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows_out)
        if not args.csv_only:
            print(f"Wrote {len(rows_out)} row(s) to {args.output}", file=sys.stderr)
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    if args.csv_only:
        return 0

    # Summary: last attempt per feed
    bad = 0
    by_feed: dict[tuple, dict] = {}
    for r in rows_out:
        key = (r["domain_key"], r["schema"], r["feed_id"], r["feed_url"])
        if r["attempt"] == args.attempts:
            by_feed[key] = r

    for r in by_feed.values():
        if r.get("error"):
            bad += 1
        elif not r.get("ok"):
            bad += 1
        else:
            try:
                if int(r.get("http_status") or 0) >= 400:
                    bad += 1
            except (TypeError, ValueError):
                bad += 1

    print(
        f"\nSummary: {len(by_feed)} feed(s) probed ({args.attempts} attempt(s) each); "
        f"problematic on last attempt: {bad}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
