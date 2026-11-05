#!/usr/bin/env python3
"""Batch rescore ALL scoreable storylines using the exact QualityAssessmentService formula.

Outputs:
  - CSV report of every storyline's old vs new score + component breakdown
  - Tier distribution comparison (old vs new)
  - Per-domain stats
  - --apply writes scores to DB

Formula (from api/domains/storyline_management/services/quality_assessment_service.py):

    overall = q_metrics * 0.3 + coherence * 0.3 + accuracy * 0.2 + standards * 0.2

    q_metrics     = avg_quality*0.4 + avg_credibility*0.3 + diversity_score*0.2 + completeness*0.1
    coherence     = temporal*0.3   + thematic*0.4       + source_coherence*0.3
    accuracy      = avg_credibility*0.6 + verification*0.4
    standards     = count_score*0.3 + diversity_score*0.3 + summary_score*0.2 + avg_quality*0.2
"""
from __future__ import annotations

import argparse, csv, logging, os, sys, io
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_URI = os.environ.get("NEWS_INTEL_DATABASE_URI") or \
    "postgresql://newsapp:v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw@192.168.93.101:5432/news_intel"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("batch_rescore")

DOMAINS_SCHEMA = [
    ("artificial_intelligence", "storylines"),
    ("legal", "storylines"),
    ("medicine", "storylines"),
    ("neurodiversity", "storylines"),
    ("public", "storylines"),
]


def _str(val):
    """Safely convert to lowercase string."""
    if val is None:
        return ""
    return str(val).lower()


def calc_quality_metrics(articles):
    n = len(articles)
    if n == 0:
        return {
            "quality_score": 0.0, "avg_article_quality": 0.5, "avg_credibility": 0.5,
            "diversity_score": 0.0, "completeness": 0.0, "source_diversity": 0,
        }

    source_domains = set()
    for a in articles:
        sd = a.get("source_domain")
        if sd is not None:
            source_domains.add(str(sd).lower())
    source_diversity = len(source_domains)
    diversity_score = min(1.0, source_diversity / max(n, 1) * 2.0)

    qscores = []
    for a in articles:
        q = a.get("quality_score")
        if q is not None:
            try:
                qscores.append(float(q))
            except (TypeError, ValueError):
                pass
    avg_quality = sum(qscores) / len(qscores) if qscores else 0.5

    completeness = min(1.0, n / 10.0)
    quality_score = avg_quality * 0.4 + avg_quality * 0.3 + diversity_score * 0.2 + completeness * 0.1

    return {
        "quality_score": quality_score, "avg_article_quality": avg_quality,
        "avg_credibility": avg_quality, "source_diversity": source_diversity,
        "diversity_score": diversity_score, "completeness": completeness,
    }


def calc_coherence(articles, storyline_title, storyline_desc):
    n = len(articles)
    if n == 0:
        return {"coherence_score": 0.0, "temporal": 1.0, "thematic": 0.0, "source_cohere": 0.0}

    dates = []
    for a in articles:
        dt = a.get("published_at")
        if dt is not None:
            try:
                dates.append(str(dt))
            except Exception:
                pass
    temporal = 1.0 if len(dates) == n and dates == sorted(dates) else 0.7

    title_kw = set(_str(storyline_title).split()) | set(_str(storyline_desc).split())
    article_matches = sum(
        1 for a in articles
        if title_kw & set(_str(a.get("title") or "").split())
    )
    thematic = article_matches / n if n > 0 else 0.0

    source_domains = [str(a.get("source_domain") or "").lower() for a in articles if a.get("source_domain")]
    unique_sources = len(set(source_domains))
    source_cohere = min(1.0, unique_sources / max(n, 1) * 1.5)

    coherence_score = temporal * 0.3 + thematic * 0.4 + source_cohere * 0.3
    return {
        "coherence_score": coherence_score, "temporal": temporal,
        "thematic": thematic, "source_cohere": source_cohere,
        "article_matches": article_matches,
    }


def calc_accuracy(articles):
    n = len(articles)
    if n == 0:
        return {"accuracy_score": 0.0, "cross_source_verification": 0.0, "source_count": 0, "avg_credibility": 0.5}

    source_domains = set()
    for a in articles:
        sd = a.get("source_domain")
        if sd is not None:
            source_domains.add(str(sd).lower())
    verification_score = min(1.0, len(source_domains) / 3.0)

    credibility_scores = []
    for a in articles:
        q = a.get("quality_score")
        if q is not None:
            try:
                credibility_scores.append(float(q))
            except (TypeError, ValueError):
                pass
    avg_credibility = sum(credibility_scores) / len(credibility_scores) if credibility_scores else 0.5

    accuracy_score = avg_credibility * 0.6 + verification_score * 0.4
    return {
        "accuracy_score": accuracy_score, "cross_source_verification": verification_score,
        "source_count": len(source_domains), "avg_credibility": avg_credibility,
    }


def calc_standards(articles, has_summary):
    n = len(articles)
    count_score = min(1.0, n / 5.0)

    source_domains = set()
    for a in articles:
        sd = a.get("source_domain")
        if sd is not None:
            source_domains.add(str(sd).lower())
    diversity_score = min(1.0, len(source_domains) / 3.0)

    summary_score = 1.0 if has_summary else 0.5

    quality_scores = []
    for a in articles:
        q = a.get("quality_score")
        if q is not None:
            try:
                quality_scores.append(float(q))
            except (TypeError, ValueError):
                pass
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    standards_score = count_score * 0.3 + diversity_score * 0.3 + summary_score * 0.2 + avg_quality * 0.2
    return {
        "standards_score": standards_score, "article_count_score": count_score,
        "diversity_score": diversity_score, "summary_score": summary_score,
        "avg_quality": avg_quality,
    }


def calc_overall(articles, title, desc, has_summary):
    qm = calc_quality_metrics(articles)
    coh = calc_coherence(articles, title, desc)
    acc = calc_accuracy(articles)
    std = calc_standards(articles, has_summary)

    overall = (qm["quality_score"] * 0.3 +
               coh["coherence_score"] * 0.3 +
               acc["accuracy_score"] * 0.2 +
               std["standards_score"] * 0.2)

    return {
        "overall": overall,
        "q_metrics": qm, "coh": coh, "acc": acc, "std": std,
    }


def _score_to_tier(score):
    if score >= 0.6:
        return "tier_1"
    elif score >= 0.4:
        return "tier_2"
    elif score >= 0.3:
        return "tier_3"
    else:
        return "tier_4"


def main():
    p = argparse.ArgumentParser(description="Batch rescore ALL scoreable storylines")
    p.add_argument("--apply", action="store_true", help="Write scores to DB (default: dry-run)")
    args = p.parse_args()

    label = "APPLY" if args.apply else "DRY-RUN"
    logger.info("Starting batch rescore %s ...", label)

    conn = psycopg2.connect(DB_URI)

    all_results = []
    tier_dist_old = defaultdict(int)
    tier_dist_new = defaultdict(int)
    total_scored = 0

    # CSV output buffer
    csv_rows = []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for schema, table in DOMAINS_SCHEMA:
                logger.info("Processing %s.%s ...", schema, table)

                cur.execute(f"""
                    SELECT s.id, COALESCE(s.title, '') as title,
                           COALESCE(CAST(s.description AS text), '') as description,
                           COALESCE(s.article_count, 0) as article_count,
                           s.status,
                           s.quality_score as old_quality,
                           CASE WHEN s.analysis_summary IS NOT NULL AND CAST(s.analysis_summary AS text) != '' THEN true ELSE false END as has_summary
                    FROM {schema}.{table} s
                    WHERE EXISTS (SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id)
                      AND s.status NOT IN ('completed','dormant','failed')
                    ORDER BY s.updated_at DESC
                """)

                rows = list(cur.fetchall())
                domain_stats = {"total": len(rows), "scored": 0, "errors": 0}

                for row in rows:
                    sid = int(row["id"])
                    title = str(row.get("title") or "")
                    desc = str(row.get("description") or "")
                    has_summary = bool(row.get("has_summary"))
                    old_score = float(row["old_quality"]) if row["old_quality"] is not None else 0.0

                    cur.execute(f"""
                        SELECT a.quality_score::float as quality_score,
                               COALESCE(a.source_domain,'') as source_domain,
                               a.published_at,
                               COALESCE(a.title, '') as title
                        FROM {schema}.articles a
                        JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    """, (sid,))

                    arts = list(cur.fetchall())
                    if not arts:
                        domain_stats["errors"] += 1
                        continue

                    n_arts = len(arts)
                    total_scored += 1

                    try:
                        result = calc_overall(arts, title, desc, has_summary)
                        new_score = result["overall"]
                        qm = result["q_metrics"]
                        coh = result["coh"]
                        acc = result["acc"]
                        std_s = result["std"]

                        delta = round(new_score - old_score, 4)
                        entry = {
                            "id": sid,
                            "domain": schema,
                            "title_short": title[:80],
                            "article_count": n_arts,
                            "old_score": round(old_score, 4),
                            "new_score": round(new_score, 4),
                            "delta": delta,
                            "moved_tier": "",
                        }

                        old_tier = _score_to_tier(old_score)
                        new_tier = _score_to_tier(new_score)
                        entry["old_tier"] = old_tier
                        entry["new_tier"] = new_tier
                        if old_tier != new_tier:
                            entry["moved_tier"] = f"{old_tier}->{new_tier}"
                        tier_dist_old[old_tier] += 1
                        tier_dist_new[new_tier] += 1

                        # Per-storyline component breakdown
                        csv_rows.append({
                            "storyline_id": sid,
                            "domain": schema,
                            "title_short": title[:80],
                            "article_count": n_arts,
                            "old_score": f"{old_score:.4f}",
                            "new_score": f"{new_score:.4f}",
                            "delta": f"{delta:+.4f}",
                            "moved_tier": entry["moved_tier"],
                            # Quality Metrics (weight 0.3)
                            "qm_quality": f"{qm['quality_score']:.4f} (avg_q={qm['avg_article_quality']:.2f}, div={qm['diversity_score']:.2f}, comp={qm['completeness']:.2f})",
                            # Coherence (weight 0.3)
                            "coh_temporal": f"{coh['temporal']:.2f} (dates)",
                            "coh_thematic": f"{coh['thematic']:.2f} ({coh.get('article_matches',0)} matched / {n_arts})",
                            "coh_source": f"{coh['source_cohere']:.2f}",
                            # Accuracy (weight 0.2)
                            "acc_avg_cred": f"{acc['avg_credibility']:.4f} (artifacts)",
                            "acc_verification": f"{acc['cross_source_verification']:.2f} ({acc['source_count']} sources)",
                            # Standards (weight 0.2)
                            "std_count": f"{std_s['article_count_score']:.2f} (count={n_arts}/5)",
                            "std_diversity": f"{std_s['diversity_score']:.2f}",
                            "std_summary": f"{std_s['summary_score']:.1f} {'=yes' if has_summary else '=no'}",
                        })

                        all_results.append(entry)
                        domain_stats["scored"] += 1

                    except Exception as e:
                        logger.warning("  Error scoring %s.%s id=%d: %s", schema, table, sid, e)
                        import traceback; traceback.print_exc()
                        domain_stats["errors"] += 1
                        continue

                updated = 0
                if args.apply and domain_stats["scored"] > 0:
                    for entry in all_results:
                        if entry["domain"] == schema and abs(entry["delta"]) > 0.0001:
                            try:
                                cur.execute(f"""
                                    UPDATE {schema}.{table}
                                    SET quality_score=%s, factual_accuracy_score=%s,
                                        narrative_quality_score=%s, updated_at=NOW()
                                    WHERE id=%s
                                """, (entry["new_score"],
                                      round(new_score * 0.95, 4) if new_score else None,
                                      round(new_score * 1.05, 4) if new_score else None,
                                      entry["id"]))
                                if cur.rowcount > 0:
                                    updated += 1
                            except Exception as e:
                                logger.warning("  Update failed for %d: %s", entry["id"], e)
                    conn.commit()

                domain_stats["updated"] = updated
                domain_score_sum = sum(e["new_score"] for e in all_results if e["domain"] == schema)
                domain_count = sum(1 for e in all_results if e["domain"] == schema)
                domain_stats["new_avg_score"] = round(domain_score_sum / max(domain_count, 1), 4)

                logger.info("  %s: %d total, %d scored (%.3f avg new), %d updated",
                           schema, domain_stats["total"], domain_stats["scored"],
                           domain_stats["new_avg_score"], domain_stats.get("updated", 0))

    finally:
        conn.close()

    # ---- CSV Report ----
    if csv_rows:
        report_path = Path("/home/pete/Documents/projects/news_intelligence/api/scripts/reports/batch_rescore_report.csv")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
            writer.writeheader()
            writer.writerows(csv_rows)

        logger.info("Full per-storyline report written to %s (%d rows)", report_path, len(csv_rows))

    # ---- Console Summary ----
    print("\n" + "=" * 80)
    print(f"BATCH RESCORE {label} SUMMARY ({len(all_results)} storylines scored)")
    print("=" * 80)

    if not all_results:
        print("No storylines with articles found.")
        return

    scores = [r["new_score"] for r in all_results]
    deltas = [r["delta"] for r in all_results]

    # Overall stats
    print(f"\nScore distribution (NEW):")
    print(f"  Min:     {min(scores):.4f}")
    print(f"  Max:     {max(scores):.4f}")
    print(f"  Avg:     {sum(scores)/len(scores):.4f}")
    mid = len(scores) // 2
    print(f"  Median:  {sorted(scores)[mid]:.4f}")

    # Tier distribution comparison
    all_tiers = sorted(set(list(tier_dist_old.keys()) + list(tier_dist_new.keys())))
    print(f"\nTier distribution:")
    hdr = f"{'Tier':>10s} | {'OLD count':>10s} | {'OLD %':>8s} | {'NEW count':>10s} | {'NEW %':>8s}"
    bar = "- " * 39
    print(hdr)
    print(bar)

    for tier in all_tiers:
        old_n = tier_dist_old.get(tier, 0)
        new_n = tier_dist_new.get(tier, 0)
        old_pct = old_n / total_scored * 100 if total_scored else 0
        new_pct = new_n / len(all_results) * 100 if all_results else 0
        change = new_n - old_n
        arrow = f"{'+' if change > 0 else ''}{change}"
        print(f"{tier:>10s} | {old_n:>10d} | {old_pct:>7.1f}% | {new_n:>10d} | {new_pct:>7.1f}% | {arrow}")

    # Score bands
    bands = [(0, 0.2, "0.0-0.2"), (0.2, 0.3, "0.2-0.3"), (0.3, 0.4, "0.3-0.4"),
             (0.4, 0.6, "0.4-0.6"), (0.6, 999, "0.6+ (tier_1/tier_2)")]
    print(f"\nScore bands:")
    for lo, hi, lb in bands:
        c = sum(1 for s in scores if lo <= s < hi)
        pct = c / len(scores) * 100 if scores else 0
        print(f"  {lb:>25s}: {c:>4d} ({pct:5.1f}%)")

    # Delta stats
    pos = sum(1 for d in deltas if d > 0.01)
    neg = sum(1 for d in deltas if d < -0.01)
    flat = len(deltas) - pos - neg
    print(f"\nScore changes: {pos} up, {neg} down, {flat} ~same")
    max_gain = max(deltas) if deltas else 0
    max_loss = min(deltas) if deltas else 0
    print(f"  Max gain:   +{max_gain:.4f}")
    print(f"  Max loss:   {max_loss:.4f}")

    # Tier movers (any change)
    moved = [r for r in all_results if abs(r["delta"]) > 0.001]
    tier_moved = [r for r in moved if r.get("moved_tier")]
    if tier_moved:
        print(f"\nTIER MOVERS ({len(tier_moved)} storylines):")
        for r in sorted(tier_moved, key=lambda x: abs(x["delta"]), reverse=True):
            sign = "+" if r["delta"] > 0 else ""
            print(f"  {r['id']:>6d} | {sign}{r['delta']:+.4f} ({r['old_tier']}->{r['new_tier']}) | ~{r['article_count']} arts | {r['domain']}")

    # Top scored (NEW formula)
    top10 = sorted(all_results, key=lambda x: x["new_score"], reverse=True)[:10]
    print(f"\nTop 10 (NEW formula):")
    for r in top10:
        sign = "+" if r["delta"] > 0 else ""
        print(f"  {r['id']:>6d} | {r['new_score']:.4f} (was {r['old_score']:.4f}, {sign}{r['delta']:+.4f}) | ~{r['article_count']} arts | {r.get('moved_tier','')}")

    # Biggest movers
    big_movers = sorted(all_results, key=lambda x: abs(x["delta"]), reverse=True)[:10]
    any_significant = any(abs(r["delta"]) > 0.001 for r in all_results)
    if any_significant:
        print(f"\nBiggest score changes:")
        for r in big_movers[:10]:
            sign = "+" if r["delta"] > 0 else ""
            print(f"  {r['id']:>6d} | {sign}{r['delta']:+.4f} ({r['old_tier']}->{r['new_tier']}) | ~{r['article_count']} arts | {r['domain']}")

    if not args.apply:
        print("\nNo changes made. Run with --apply to write scores.")
    else:
        print(f"\nAPPLIED {len(all_results)} score updates to database.")


if __name__ == "__main__":
    main()
