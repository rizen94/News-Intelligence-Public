#!/usr/bin/env python3
"""Diagnose zero article ingestion in RSS collector by testing gate rejection logic."""

import os, sys, re, textwrap, json
from collections import Counter

# ── 0. Environment setup ────────────────────────────────────────────────
os.environ.setdefault("DEVELOPMENT_MODE", "false")
sys.path.insert(0, ".")
sys.path.insert(1, "api")

# ── 1. Patch shared/__init__.py to skip router imports (temporarily) ─────
INIT_PATH = os.path.join(os.path.dirname(__file__), "api", "shared", "__init__.py")
original_content = open(INIT_PATH).read()

def patch_init():
    """Comment out router import lines so shared/__init__ doesn't try to import domains."""
    lines = original_content.splitlines(keepends=True)
    patched = []
    for line in lines:
        stripped = line.rstrip('\n')
        if re.search(r'^\s*from\s+\.\.domains\.', line):
            patched.append('# ' + line)  # comment out router imports
        elif re.search(r'^\s*(ROUTERS)\s*=\s*\(', line):
            patched.append('ROUTERS = ()  # PATCHED: skip for diagnostics\n')
        else:
            patched.append(line)
    
    new_content = ''.join(patched)
    open(INIT_PATH, 'w').write(new_content)
    print("✓ Patched shared/__init__.py (router imports disabled for diagnostics)")

def unpatch_init():
    """Restore original file."""
    open(INIT_PATH, 'w').write(original_content)
    print("✓ Restored shared/__init__.py")

# ── 2. Import gate functions ────────────────────────────────────────────
patch_init()

from api.collectors.rss_collector import (
    is_excluded_content,
    is_clickbait_title,
    is_advertisement,
    calculate_article_quality_score,
    calculate_article_impact_score,
)

unpatch_init()
print("✓ Gate functions loaded\n")

# ── 3. Test gate logic with synthetic articles ──────────────────────────
print("=" * 70)
print("GATE FUNCTION VALIDATION (synthetic articles)")
print("=" * 70)

test_cases = [
    {
        "name": "Legitimate science article",
        "title": "AI breakthrough in quantum computing achieves new milestone",
        "content": "Researchers at MIT have achieved a significant breakthrough in quantum computing, demonstrating error correction at scale for the first time. The work shows fault-tolerant quantum operations using a new topological coding scheme.",
    },
    {
        "name": "Clickbait celebrity news",
        "title": "You Won't Believe What This Celebrity Did Next!",
        "content": "Fans were shocked by the latest revelation from Hollywood's biggest star, who recently made a stunning announcement that has taken everyone by surprise.",
    },
    {
        "name": "Advertisement-style (bad)",
        "title": "Best Mortgage Rates - Compare Now!",
        "content": "<div><a href='#'>Click here for the best mortgage rates today!</a></div>",
    },
    {
        "name": "Very short article",
        "title": "Short Update: Market News",
        "content": "This is too short for analysis.",
    },
    {
        "name": "Financial news (good)",
        "title": "Federal Reserve Raises Interest Rates by 25 Basis Points",
        "content": "The Federal Reserve announced today a quarter-point increase in the federal funds rate, bringing it to 5.25-5.50%, citing persistent inflation pressures and a robust labor market that continues to exceed expectations.",
    },
    {
        "name": "Political news (good)",
        "title": "Senate Passes Bipartisan Infrastructure Bill with Strong Majorities",
        "content": "The U.S. Senate voted 69-30 on Thursday to approve a comprehensive infrastructure package that allocates $1.2 trillion toward roads, bridges, broadband, and clean energy projects over the next five years.",
    },
    {
        "name": "Content with ad URLs",
        "title": "Breaking: Major Market Move Detected",
        "content": "<script src='https://example.com/ads/banner.js'></script><img src='tracker.gif'><p>Stocks surged today amid growing investor confidence in the tech sector.</p>",
    },
]

for tc in test_cases:
    print(f"\n--- {tc['name']} ---")
    
    excluded = is_excluded_content(tc['title'], tc['content'], 'Test Feed', 'https://example.com')
    clickbait = is_clickbait_title(tc['title'])
    ad = is_advertisement(tc['title'], tc['content'])
    quality = calculate_article_quality_score(tc['title'], tc['content'], 'Test Feed', 'https://example.com')
    impact = calculate_article_impact_score(tc['title'], tc['content'])
    
    rejected = excluded or clickbait or ad
    
    print(f"  quality={quality:.3f}  impact={impact:.3f}")
    print(f"  excluded={excluded}  clickbait={clickbait}  ad={ad}")
    print(f"  → {('REJECTED' if rejected else 'PASS')}")

# ── 4. Check real articles in the database ───────────────────────────────
print("\n" + "=" * 70)
print("REAL ARTICLE ANALYSIS (from PostgreSQL)")
print("=" * 70)

try:
    from shared.database import get_db_connection_context
    
    with get_db_connection_context() as conn:
        # Get all articles from RSS collector that failed or were never created
        print("\n--- Article counts by status ---")
        statuses = conn.execute("""
            SELECT status, COUNT(*) FROM articles GROUP BY status ORDER BY COUNT(*) DESC
        """).fetchall()
        for s, c in statuses:
            print(f"  {s}: {c}")
        
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        print(f"\nTotal articles: {total}")
        
        # Get most recent articles with state reasons (top 20)
        if total > 0:
            print("\n--- Most recent articles ---")
            rows = conn.execute("""
                SELECT id, title, status_reason, created_at
                FROM articles
                ORDER BY created_at DESC
                LIMIT 15
            """).fetchall()
            
            for row in rows:
                reason = row[2] or "None"
                print(f"  {row[0]} | {row[1][:60]}... | reason={reason} | {row[3]}")
        
        # Get RSS feed state
        print("\n--- RSS Feeds ---")
        feeds = conn.execute("""
            SELECT source_url, status, updated_at, last_error
            FROM rss_feeds
            ORDER BY updated_at DESC
            LIMIT 10
        """).fetchall()
        
        if feeds:
            for f in feeds:
                err = (f[3] or "None")[:80]
                print(f"  {f[0]} | status={f[1]} | updated={f[2]} | err={err}")
        else:
            print("  No RSS feeds registered!")
        
        # Check article content quality distribution (for articles that passed gates)
        if total > 0:
            print("\n--- Quality score distribution ---")
            buckets = conn.execute("""
                SELECT 
                    CASE 
                        WHEN quality_score IS NULL THEN 'NULL'
                        WHEN quality_score < 0.3 THEN '0.0-0.3'
                        WHEN quality_score < 0.5 THEN '0.3-0.5'
                        WHEN quality_score < 0.7 THEN '0.5-0.7'
                        ELSE '0.7+'
                    END as bucket,
                    COUNT(*) as cnt
                FROM articles
                GROUP BY bucket
            """).fetchall()
            
            for bucket, cnt in buckets:
                print(f"  {bucket}: {cnt}")
        
        # Check if there are articles with NULL status (never completed)
        null_status = conn.execute("""
            SELECT COUNT(*) FROM articles WHERE status IS NULL OR status = 'failed'
        """).fetchone()[0]
        if null_status > 0:
            print(f"\n⚠ {null_status} articles have NULL or failed status")
        
        # Count by feed and most recent article date per feed  
        print("\n--- Articles per RSS feed ---")
        article_counts = conn.execute("""
            SELECT source_url, COUNT(*) as cnt, 
                   MAX(created_at) as latest, 
                   MIN(created_at) as earliest
            FROM articles
            GROUP BY source_url
            ORDER BY cnt DESC
        """).fetchall()
        
        if article_counts:
            for url, cnt, latest, earliest in article_counts:
                print(f"  {url}: {cnt} articles (range: {earliest} → {latest})")
        else:
            print("  No articles found in any feed!")

except Exception as e:
    import traceback
    print(f"✗ Database query failed:")
    print(f"  Error: {e}")
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)
