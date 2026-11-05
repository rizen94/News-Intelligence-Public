import psycopg2
conn = psycopg2.connect(
    host='192.168.93.101', port=6432,
    database='news_intel', user='newsapp', password='v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw'
)
cur = conn.cursor()

# All score columns ranges for pending
print('=== ALL SCORE COLUMNS (pending) ===')
cur.execute("""
SELECT 
  min(relevance_score), max(relevance_score), round(avg(relevance_score)::numeric,4),
  min(semantic_score), max(semantic_score), round(avg(semantic_score)::numeric,4),
  min(keyword_score), max(keyword_score), round(avg(keyword_score)::numeric,4),
  min(quality_score), max(quality_score), round(avg(quality_score)::numeric,4)
FROM public.storyline_article_suggestions 
WHERE status = 'pending' AND combined_score IS NOT NULL;
""")
print(cur.fetchall())

# keyword_score distribution
print('\n=== keyword_score dist (pending) ===')
cur.execute("""
SELECT keyword_score, count(*) 
FROM public.storyline_article_suggestions 
WHERE status='pending' AND combined_score IS NOT NULL
GROUP BY keyword_score ORDER BY keyword_score;
""")
for r in cur.fetchall(): print(f'  kw={r[0]}: {r[1]} items')

# quality_score distribution  
print('\n=== quality_score dist (pending) ===')
cur.execute("""
SELECT quality_score, count(*) 
FROM public.storyline_article_suggestions 
WHERE status='pending' AND combined_score IS NOT NULL
GROUP BY quality_score ORDER BY quality_score;
""")
for r in cur.fetchall(): print(f'  qual={r[0]}: {r[1]} items')

# Approved items scores
print('\n=== Top approved items ===')
cur.execute("""
SELECT keyword_score, quality_score, combined_score, relevance_score, semantic_score, storyline_id
FROM public.storyline_article_suggestions 
WHERE status='approved' ORDER BY combined_score DESC LIMIT 10;
""")
for r in cur.fetchall(): print(f'  {r}')

# What do the top-scoring pending items look like?
print('\n=== Top-pending items ===')
cur.execute("""
SELECT keyword_score, quality_score, combined_score, relevance_score, semantic_score, storyline_id
FROM public.storyline_article_suggestions 
WHERE status='pending' AND combined_score IS NOT NULL
ORDER BY combined_score DESC LIMIT 5;
""")
for r in cur.fetchall(): print(f'  {r}')

# What about the keyword score = 0.5? Is that a cap or minimum?
print('\n=== How many items have exactly kw=0.5? ===')
cur.execute("""
SELECT count(*) FROM public.storyline_article_suggestions 
WHERE status='pending' AND keyword_score = 0.5;
""")
print(f'  {cur.fetchone()[0]} items have kw=0.5')

# What's the distribution of storyline_ids in pending?
print('\n=== Top storylines by pending count ===')
cur.execute("""
SELECT storyline_id, count(*) as cnt, 
       min(combined_score), max(combined_score), round(avg(combined_score)::numeric,4)
FROM public.storyline_article_suggestions 
WHERE status='pending' AND combined_score IS NOT NULL
GROUP BY storyline_id ORDER BY cnt DESC LIMIT 10;
""")
for r in cur.fetchall(): print(f'  sl={r[0]}: {r[1]} items, score={r[2]}-{r[3]}, avg={r[4]}')

# Total items per status
print('\n=== TOTAL per status ===')
cur.execute("""
SELECT status, count(*) FROM public.storyline_article_suggestions GROUP BY status ORDER BY count(*) DESC;
""")
for r in cur.fetchall(): print(f'  {r}')

conn.close()
print('\nDONE')
