import psycopg2
import sys

DB = {
    'host': '127.0.0.1',
    'port': 6432,
    'dbname': 'news_intel',
    'user': 'newsapp',
    'password': 'v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw'
}

def migrate():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    
    # Create schemas
    for s in ['narratives', 'infrastructure']:
        cur.execute('CREATE SCHEMA IF NOT EXISTS ' + s)
        conn.commit()
    
    tables = [
        ('chronological_events', 'narratives'),
        ('storyline_article_suggestions', 'narratives'),
    ]
    
    for src, tgt in tables:
        print(f'Migrating {src} -> {tgt}', flush=True)
        cur.execute('SELECT count(*) FROM public.' + src)
        cnt = cur.fetchone()[0]
        print(f'  rows: {cnt}', flush=True)
        
        cur.execute('CREATE TABLE ' + tgt + '.' + src + ' (LIKE public.' + src + ' INCLUDING ALL)')
        conn.commit()
        
        cur.execute('INSERT INTO ' + tgt + '.' + src + ' SELECT * FROM public.' + src)
        conn.commit()
        print(f'  inserted OK', flush=True)
    
    conn.close()

if __name__ == '__main__':
    migrate()
    print('DONE')
