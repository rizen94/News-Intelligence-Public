#!/usr/bin/env python3
"""
Create basic clusters from existing articles
"""

import os
import sys
from datetime import datetime


def _get_db_config():
    """Database config from shared source. Run from api/ or PYTHONPATH=api."""
    import sys

    _api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _api not in sys.path:
        sys.path.insert(0, _api)
    from shared.database.connection import get_db_config

    return get_db_config()


def create_basic_clusters():
    """Create basic clusters from existing articles"""
    print("Creating basic clusters from existing articles...")

    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        print("✓ Connected to database")

        # Get articles by source to create basic clusters
        cursor.execute("""
            SELECT source, COUNT(*) as article_count
            FROM articles
            WHERE source IS NOT NULL AND source != ''
            GROUP BY source
            ORDER BY article_count DESC
        """)

        sources = cursor.fetchall()
        print(f"Found {len(sources)} sources")

        clusters_created = 0

        for source, article_count in sources:
            if article_count >= 2:  # Only create clusters for sources with multiple articles
                # Create cluster
                cursor.execute(
                    """
                    INSERT INTO article_clusters (name, topic, article_count, status, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (f"{source} Articles", "General News", article_count, "active", datetime.now()),
                )

                result = cursor.fetchone()
                if result:
                    cluster_id = result[0]

                    # Add articles to cluster
                    cursor.execute(
                        """
                        INSERT INTO cluster_articles (cluster_id, article_id, relevance_score)
                        SELECT %s, id, 1.0
                        FROM articles
                        WHERE source = %s
                        ON CONFLICT (cluster_id, article_id) DO NOTHING
                    """,
                        (cluster_id, source),
                    )

                    clusters_created += 1
                    print(f"   ✓ Created cluster '{source} Articles' with {article_count} articles")

        # Create category-based clusters
        cursor.execute("""
            SELECT category, COUNT(*) as article_count
            FROM articles
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY article_count DESC
        """)

        categories = cursor.fetchall()
        print(f"Found {len(categories)} categories")

        for category, article_count in categories:
            if article_count >= 2:  # Only create clusters for categories with multiple articles
                # Create cluster
                cursor.execute(
                    """
                    INSERT INTO article_clusters (name, topic, article_count, status, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (f"{category} News", category, article_count, "active", datetime.now()),
                )

                result = cursor.fetchone()
                if result:
                    cluster_id = result[0]

                    # Add articles to cluster
                    cursor.execute(
                        """
                        INSERT INTO cluster_articles (cluster_id, article_id, relevance_score)
                        SELECT %s, id, 1.0
                        FROM articles
                        WHERE category = %s
                        ON CONFLICT (cluster_id, article_id) DO NOTHING
                    """,
                        (cluster_id, category),
                    )

                    clusters_created += 1
                    print(f"   ✓ Created cluster '{category} News' with {article_count} articles")

        conn.commit()
        print(f"\n✅ Created {clusters_created} clusters successfully!")

        # Show final cluster count
        cursor.execute("SELECT COUNT(*) FROM article_clusters")
        total_clusters = cursor.fetchone()[0]
        print(f"Total clusters in database: {total_clusters}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = create_basic_clusters()
    sys.exit(0 if success else 1)
