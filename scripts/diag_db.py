#!/usr/bin/env python3
import psycopg2, sys

conn = psycopg2.connect(
    host='192.168.93.101', port=5432, dbname='news_intel',
    user='newsapp', password='v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw'
)
cur = conn.cursor()

# 1. STATUS COUNTS
cur.execute("SELECT processing_status, count(*) FROM articles GROUP BY processing_status ORDER BY count DESC LIMIT 20;")
print('=== ARTICLES BY STATUS ===')
for row in cur.fetchall(): print(f'  {row[0]:30s} : {row[1]:>6}')

# 2. RECENCY
cur.execute("SELECT count(*) FROM articles WHERE discovered_at >= now() - interval '24 hours'")
print(f'\nLast 24h   : {cur.fetchone()[0]}')
cur.execute("SELECT count(*) FROM articles WHERE discovered_at >= now() - interval '7 days'")
print(f'Last 7d    : {cur.fetchone()[0]}')
cur.execute("SELECT count(*) FROM articles WHERE discovered_at >= now() - interval '30 days'")
print(f'Last 30d   : {cur.fetchone()[0]}')
cur.execute("SELECT count(*) FROM articles;")
print(f'Total      : {cur.fetchone()[0]}')

# 3. OLDEST PENDING (none exist, but check)
cur.execute("SELECT id, substring(title from 1 for 60), processing_status, discovered_at FROM articles WHERE processing_status = 'pending' ORDER BY discovered_at ASC LIMIT 5;")
print('\n=== OLDEST 5 PENDING ===')
rows = cur.fetchall()
if rows:
    for row in rows: print(f'  #{row[0]} | {str(row[1]):45s} | status={row[2]:10s} | {row[3]}')
else:
    print('  (none found)')

# 4. NEWEST (any)
cur.execute("SELECT id, substring(title from 1 for 60), processing_status, discovered_at FROM articles ORDER BY discovered_at DESC LIMIT 5;")
print('\n=== NEWEST 5 (any status) ===')
rows = cur.fetchall()
if rows:
    for row in rows: print(f'  #{row[0]} | {str(row[1]):45s} | status={row[2]:10s} | {row[3]}')
else:
    print('  (none found)')

# 5. DOMAINS
cur.execute("SELECT domain_name, display_name, enabled FROM domains ORDER BY domain_name;")
print('\n=== DOMAINS ===')
for row in cur.fetchall(): print(f'  {row[0]:25s} | {row[1]:30s} | {row[2]}')

# 6. RSS FEEDS (sample)
cur.execute("SELECT title, url, last_checked FROM rss_feeds ORDER BY last_updated DESC LIMIT 8;")
print('\n=== RSS FEEDS (last_updated desc) ===')
for row in cur.fetchall(): print(f'  {str(row[0]):45s} | {str(row[1]):60s} | checked={row[2]}')

# 7. ARTICLES PER DOMAIN
cur.execute("SELECT d.domain_name, count(*) FROM articles a JOIN domains d ON a.domain_id = d.id GROUP BY d.domain_name ORDER BY count(*) DESC LIMIT 15;")
print('\n=== ARTICLES BY DOMAIN ===')
for row in cur.fetchall(): print(f'  {row[0]:25s} : {row[1]}')

# 8. STORYLINES COUNT
cur.execute("SELECT status, count(*) FROM storylines GROUP BY status ORDER BY count DESC;")
print('\n=== STORYLINES BY STATUS ===')
for row in cur.fetchall(): print(f'  {row[0]:30s} : {row[1]:>6}')

conn.close()
