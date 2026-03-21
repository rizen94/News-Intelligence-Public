#!/usr/bin/env python3
"""
Process articles and create clusters. Run from api/ or with PYTHONPATH=api.
"""

import os
import sys

# Ensure api is on path for shared and domain modules
_API = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _API not in sys.path:
    sys.path.insert(0, _API)

from modules.intelligence.article_processor import ArticleProcessor
from modules.intelligence.content_clusterer import ContentClusterer
from services.pattern_entity_extractor import PatternEntityExtractor
from shared.database.connection import get_db_config


def process_articles():
    """Process articles and create clusters"""
    print("Processing articles and creating clusters...")

    try:
        db_config = get_db_config()
        ap = ArticleProcessor(db_config)
        cc = ContentClusterer(db_config)
        ee = PatternEntityExtractor()

        print("✓ All processors created successfully")

        # Process articles
        print("\n1. Processing articles...")
        processed_articles = ap.batch_process_articles(limit=50)
        processed_count = len(processed_articles)
        print(f"   ✓ Processed {processed_count} articles")

        # Extract entities (for a sample article)
        print("\n2. Extracting entities...")
        if processed_articles:
            sample_article = processed_articles[0]
            content = sample_article.get("content", "")
            entities = ee.extract_entities(content)
            entity_count = len(entities)
            print(f"   ✓ Extracted {entity_count} entities from sample article")
        else:
            print("   ⚠️ No articles to process")
            entity_count = 0

        # Create clusters
        print("\n3. Creating clusters...")
        clusters = cc.create_article_clusters(min_cluster_size=2, max_cluster_size=10)
        cluster_count = len(clusters)
        print(f"   ✓ Created {cluster_count} clusters")

        print("\n✅ Processing completed successfully!")
        print(f"   - Articles processed: {processed_count}")
        print(f"   - Entities extracted: {entity_count}")
        print(f"   - Clusters created: {cluster_count}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = process_articles()
    sys.exit(0 if success else 1)
