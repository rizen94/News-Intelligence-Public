#!/usr/bin/env python3
"""Test entity extraction: run on one article and show results."""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from shared.database.connection import get_db_connection
    from services.article_entity_extraction_service import get_article_entity_extraction_service

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO politics, public")
            cur.execute("""
                SELECT id, title, content FROM politics.articles
                WHERE content IS NOT NULL AND LENGTH(content) > 200
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
        
        if not row:
            print("No articles found in politics.articles")
            return 0
        
        article_id, title, content = row
        print(f"Testing entity extraction on article {article_id}:")
        print(f"  Title: {title[:80]}...")
        print()

        svc = get_article_entity_extraction_service()
        result = await svc.extract_and_store(article_id, title, content, schema="politics")
        
        if result.get("success"):
            c = result.get("counts", {})
            print("✅ Entity extraction completed:")
            print(f"   Entities (people/orgs/subjects/events): {c.get('entities', 0)}")
            print(f"   Dates: {c.get('dates', 0)}")
            print(f"   Times: {c.get('times', 0)}")
            print(f"   Countries: {c.get('countries', 0)}")
            print(f"   Keywords: {c.get('keywords', 0)}")
            
            # Show stored entities
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT entity_name, entity_type, mention_source, confidence
                    FROM politics.article_entities WHERE article_id = %s
                    ORDER BY entity_type, entity_name LIMIT 20
                """, (article_id,))
                rows = cur.fetchall()
                if rows:
                    print()
                    print("Sample entities stored:")
                    for name, etype, source, conf in rows:
                        print(f"   - {name} ({etype}, {source}, conf={conf})")
        else:
            print(f"❌ Extraction failed: {result.get('error', result.get('reason', 'unknown'))}")
            return 1
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
