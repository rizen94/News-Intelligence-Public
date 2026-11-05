#!/usr/bin/env python3
"""
RSS Ingest Diagnostic — fetch a feed, run every gate on every entry, report where articles die.

Usage:
  python rss_diagnostic.py                          # test the first active ai domain feed found
  python rss_diagnostic.py --limit N                # only test first N entries
  python rss_diagnostic.py --all                    # test ALL feeds (slow)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Minimal bootstrap: avoid domain_registry DB import ──────────────────────
os.environ.setdefault("DEVELOPMENT_MODE", "false")
os.environ.setdefault("PRODUCTION_DOMAINS", "")

# ── imports (order matters: avoids circular DB init) ────────────────────────
import feedparser, time, argparse, statistics
from collections import Counter, defaultdict


def main():
    parser = argparse.ArgumentParser(description="RSS Ingest Diagnostic")
    parser.add_argument("--limit", type=int, default=20, help="Max entries per feed")
    parser.add_argument("--all", action="store_true", help="Test all active feeds (slow)")
    parser.add_argument("--url", default=None, help="Test a specific feed URL only")
    args = parser.parse_args()

    # ── 0. Get DB connection and find feeds ───────────────────────────────
    from api.shared.database.connection import get_db_connection
    conn = get_db_connection()
    if not conn:
        print("FATAL: cannot connect to DB")
        return
    cur = conn.cursor()

    feed_rows = []  # (schema, id, name, url)

    if args.url:
        for schema in ["artificial_intelligence", "intelligence", "legal", "medicine", "neurodiversity", "public"]:
            try:
                cur.execute(
                    f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true AND feed_url = %s LIMIT 1",
                    (args.url,),
                )
                r = cur.fetchone()
                if r:
                    feed_rows.append((schema, r[0], r[1], r[2]))
                    break
            except Exception:
                pass
        if not feed_rows:
            print(f"Feed URL not found in any active table: {args.url}")
            return
    elif args.all:
        for schema in ["artificial_intelligence", "intelligence", "legal", "medicine", "neurodiversity", "public"]:
            try:
                cur.execute(f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true")
                for r in cur.fetchall():
                    feed_rows.append((schema, r[0], r[1], r[2]))
            except Exception:
                pass
    else:
        # Default: first 3 active feeds from artificial_intelligence
        for schema in ["artificial_intelligence"]:
            try:
                cur.execute(f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true LIMIT 5")
                for r in cur.fetchall():
                    feed_rows.append((schema, r[0], r[1], r[2]))
            except Exception:
                pass

    conn.close()

    if not feed_rows:
        print("No active feeds found to test.")
        return

    # ── Import gate functions (lazy to avoid DB init during import) ────────
    from api.collectors.rss_collector import (
        is_excluded_content,
        is_clickbait_title,
        is_advertisement,
        calculate_article_quality_score,
        calculate_article_impact_score,
        rss_item_passes_ingest_gates,
        _extract_rss_entry_body,
    )

    # ── Results accumulator ───────────────────────────────────────────────
    global_summary = {
        "parsed": 0,
        "excluded_sports_entertainment": 0,
        "excluded_clickbait": 0,
        "excluded_ads": 0,
        "low_quality": [],
        "low_impact": [],
        "failed_ingest_gates": 0,
        "passed_all": 0,
        "errors": 0,
    }

    per_feed_summary = []

    # ── Process feeds ─────────────────────────────────────────────────────
    test_feeds = feed_rows[:3] if not args.all else feed_rows
    n_feeds = len(test_feeds)
    print(f"Testing {n_feeds} feed(s):")
    for i, (s, fid, name, url) in enumerate(test_feeds):
        short_url = url[:70] + "..." if len(url) > 70 else url
        print(f"  {i+1}. [{s}] {name}")
        print(f"     {short_url}")
    print()

    for idx, (schema, feed_id, feed_name, feed_url) in enumerate(test_feeds):
        print("=" * 80)
        print(f"FEED: {feed_name} ({schema}.{feed_id})")
        print(f"URL: {feed_url[:90]}...")
        print()

        # Parse feed with timeout
        t0 = time.time()
        try:
            feed = feedparser.parse(feed_url)
            elapsed = time.time() - t0
            entries_raw = feed.entries
            n_entries = len(entries_raw)
            parse_status = feed.get("bozo", False) and getattr(feed, "bozo_exception", None)
            print(f"  Parsed in {elapsed:.1f}s — {n_entries} entries (parse error: {bool(parse_status)})")
            if parse_status:
                print(f"    bozo_exception type: {type(parse_status).__name__}: {str(parse_status)[:200]}")
        except Exception as e:
            print(f"  FATAL parse error: {e}")
            continue

        # Per-feed stats
        stats = {
            "parsed": 0,
            "excluded_sports_entertainment": 0,
            "excluded_clickbait": 0,
            "excluded_ads": 0,
            "low_quality_scores": [],
            "low_impact_scores": [],
            "failed_ingest_gates": 0,
            "passed_all": 0,
            "errors": 0,
        }

        # Gate-by-gate title samples for debugging
        gate_samples = {
            "clickbait_titles": [],
            "ad_titles": [],
            "excluded_titles": [],
        }

        sample_size = min(args.limit, n_entries)

        for i, entry in enumerate(entries_raw[:sample_size]):
            try:
                title = (entry.get("title", "") or "").strip()[:500]
                url_val = (entry.get("link", "") or "").strip()[:500]
                content = _extract_rss_entry_body(entry)
                stats["parsed"] += 1

                if not title and not url_val:
                    stats["errors"] += 1
                    continue

                # Gate 1: is_excluded_content (sports/entertainment/pop culture)
                excluded_reason = None
                try:
                    if is_excluded_content(title, content, feed_name, feed_url):
                        reason_parts = []
                        from api.collectors.rss_collector import _classify_exclusion_type
                        
                        etype = _classify_exclusion_type(title, content)
                        reason_parts.append(f"type={etype}")
                        
                        # Find which keyword matched (if any)
                        text_lower = f"{title} {content}".lower()
                        for kw_list_name, kw_list in [
                            ("sports", ["football", "soccer", "basketball"]),  # examples
                        ]:
                            pass  # detailed keyword analysis below

                        gate_samples["excluded_titles"].append(title[:80])
                        stats["excluded_sports_entertainment"] += 1
                        
                        print(f"    [{i+1}] EXCLUDED (sports/ent): {title[:70]}")
                        continue
                except Exception as e:
                    stats["errors"] += 1
                    print(f"    [{i+1}] EXCEPTION in is_excluded_content: {e}")
                    continue

                # Gate 2: is_clickbait_title
                if is_clickbait_title(title):
                    gate_samples["clickbait_titles"].append(title[:80])
                    stats["excluded_clickbait"] += 1
                    print(f"    [{i+1}] EXCLUDED (clickbait): {title[:70]}")
                    continue

                # Gate 3: is_advertisement
                if is_advertisement(title, content, url_val):
                    gate_samples["ad_titles"].append(title[:80])
                    stats["excluded_ads"] += 1
                    print(f"    [{i+1}] EXCLUDED (advertisement): {title[:70]}")
                    continue

                # Gate 4 & 5: quality + impact scores
                q_score = calculate_article_quality_score(title, content, feed_name, url_val)
                i_score = calculate_article_impact_score(title, content)

                stats["low_quality_scores"].append(q_score)
                stats["low_impact_scores"].append(i_score)

                if q_score < 0.3:
                    print(f"    [{i+1}] LOW QUALITY ({q_score:.2f}): {title[:70]}")
                    continue
                
                if i_score < 0.25:
                    stats["low_impact_scores"].append(i_score)
                    print(f"    [{i+1}] LOW IMPACT ({i_score:.2f}): {title[:70]}")
                    continue

                # Gate 6: rss_item_passes_ingest_gates (final sanity check)
                ok, reason = rss_item_passes_ingest_gates(title, content, url_val)
                if not ok:
                    stats["failed_ingest_gates"] += 1
                    print(f"    [{i+1}] FAILED INGEST GATE ({reason}): {title[:70]}")
                    continue

                # Passed all gates!
                stats["passed_all"] += 1
                if i < 5:  # show first few passing titles for context
                    print(f"    [{i+1}] PASSED  (q={q_score:.2f} i={i_score:.2f}): {title[:70]}")

            except Exception as e:
                stats["errors"] += 1
                print(f"    [{i+1}] EXCEPTION: {e}")
                import traceback
                traceback.print_exc()

        per_feed_summary.append(stats)

        # Print per-feed summary
        total_scored = stats["parsed"] - stats["excluded_sports_entertainment"] - stats["excluded_clickbait"] - stats["excluded_ads"]
        if total_scored > 0:
            q_scores = [s for s in stats["low_quality_scores"] if s is not None]
            i_scores = [s for s in stats["low_impact_scores"] if s is not None]
            
            print(f"\n{'='*80}")
            print(f"FEED SUMMARY — {feed_name}")
            print(f"  Parsed entries tested: {stats['parsed']}")
            print(f"  Excluded (sports/entertainment): {stats['excluded_sports_entertainment']}")
            print(f"  Excluded (clickbait):            {stats['excluded_clickbait']}")
            print(f"  Excluded (advertisement):        {stats['excluded_ads']}")
            print(f"  Passed quality check (>=0.3):    {total_scored - stats['failed_ingest_gates'] - len([s for s in q_scores if s < 0.3])}")
            print(f"  Passed impact check (>=0.25):    {stats['passed_all']}")
            print(f"  Failed ingest gates:             {stats['failed_ingest_gates']}")
            print(f"  Errors:                          {stats['errors']}")
            
            if q_scores:
                print(f"\n  Quality scores — min={min(q_scores):.2f} max={max(q_scores):.3f} mean={statistics.mean(q_scores):.3f}")
                # Show score distribution
                low_q = sum(1 for s in q_scores if s < 0.3)
                med_q = sum(1 for s in q_scores if 0.3 <= s < 0.5)
                high_q = sum(1 for s in q_scores if s >= 0.5)
                print(f"    Distribution: <0.3: {low_q}, 0.3-0.5: {med_q}, >=0.5: {high_q}")
            else:
                print(f"  Quality scores — N=0 (all excluded before scoring)")

            if i_scores:
                low_i = sum(1 for s in i_scores if s < 0.25)
                med_i = sum(1 for s in i_scores if 0.25 <= s < 0.5)
                high_i = sum(1 for s in i_scores if s >= 0.5)
                print(f"\n  Impact scores — min={min(i_scores):.3f} max={max(i_scores):.3f} mean={statistics.mean(i_scores):.3f}")
                print(f"    Distribution: <0.25: {low_i}, 0.25-0.5: {med_i}, >=0.5: {high_i}")

        # Print gate samples for debugging
        for gname, samples in gate_samples.items():
            if samples:
                print(f"\n  Gate sample — {gname} ({len(samples)} entries):")
                for s in samples[:5]:
                    print(f"    - {s}")
                if len(samples) > 5:
                    print(f"    ... and {len(samples)-5} more")

        # Accumulate globals
        global_summary["parsed"] += stats["parsed"]
        global_summary["excluded_sports_entertainment"] += stats["excluded_sports_entertainment"]
        global_summary["excluded_clickbait"] += stats["excluded_clickbait"]
        global_summary["excluded_ads"] += stats["excluded_ads"]
        global_summary["low_quality"] += [s for s in stats["low_quality_scores"] if s is not None]
        global_summary["low_impact"] += [s for s in stats["low_impact_scores"] if s is not None]
        global_summary["failed_ingest_gates"] += stats["failed_ingest_gates"]
        global_summary["passed_all"] += stats["passed_all"]
        global_summary["errors"] += stats["errors"]

    # ── Overall summary ───────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print(f"  Total parsed entries:   {global_summary['parsed']}")
    print(f"  Excluded (sports/ent):  {global_summary['excluded_sports_entertainment']}")
    print(f"  Excluded (clickbait):   {global_summary['excluded_clickbait']}")
    print(f"  Excluded (ads):         {global_summary['excluded_ads']}")
    print(f"  Passed all gates:       {global_summary['passed_all']}")
    print(f"  Failed ingest gates:    {global_summary['failed_ingest_gates']}")
    print(f"  Errors:                 {global_summary['errors']}")
    
    if global_summary["low_quality"]:
        q_scores = global_summary["low_quality"]
        low_q = sum(1 for s in q_scores if s < 0.3)
        med_q = sum(1 for s in q_scores if 0.3 <= s < 0.5)
        high_q = sum(1 for s in q_scores if s >= 0.5)
        print(f"\n  All quality scores — min={min(q_scores):.2f} max={max(q_scores):.3f} mean={statistics.mean(q_scores):.3f}")
        print(f"    <0.3: {low_q}, 0.3-0.5: {med_q}, >=0.5: {high_q}")
    
    if global_summary["low_impact"]:
        i_scores = global_summary["low_impact"]
        low_i = sum(1 for s in i_scores if s < 0.25)
        med_i = sum(1 for s in i_scores if 0.25 <= s < 0.5)
        high_i = sum(1 for s in i_scores if s >= 0.5)
        print(f"\n  All impact scores — min={min(i_scores):.3f} max={max(i_scores):.3f} mean={statistics.mean(i_scores):.3f}")
        print(f"    <0.25: {low_i}, 0.25-0.5: {med_i}, >=0.5: {high_i}")
    
    if global_summary["passed_all"] == 0:
        print("\n*** ZERO ARTICLES PASSED ALL GATES — this confirms the issue! ***")
        print("The next step is to identify which gate is responsible for the majority of rejections.")


if __name__ == "__main__":
    main()
