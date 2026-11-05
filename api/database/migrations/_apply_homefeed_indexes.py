import subprocess, sys

schemas = [
    "artificial_intelligence",
    "finance", 
    "legal",
    "medicine",
    "neurodiversity",
    "politics",
    "public",
]

for schema in schemas:
    # Clean index prefix (replace hyphens with underscores)
    idx_prefix = schema.replace('-', '_')
    
    for name, clause, cols in [
        ("status_timeline", f"merged_into_id IS NULL", "(status, updated_at DESC NULLS LAST)"),
        ("last_refinement", "status IN ('storyline_processing','ready_for_review')", "(last_refinement DESC NULLS LAST)"),
    ]:
        sql = f"""CREATE INDEX IF NOT EXISTS idx_{idx_prefix}_storylines_{name} ON {schema}.storylines {cols} WHERE {clause};"""
        result = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-d", "news_intel", "-t", "-A", "-c", sql],
            capture_output=True, text=True, cwd="/tmp"
        )
        if result.returncode != 0:
            print(f"FAIL [{name} {schema}]: {result.stderr.strip()}", file=sys.stderr)
        else:
            print(f"OK   [{name} {schema}]")

# Note: Index on storyline_articles (storyline_id, added_at DESC) was created by M239.
# last_article_added_at is an aggregate alias (MAX(sa.added_at)) — not a real column.
