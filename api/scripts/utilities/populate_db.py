#!/usr/bin/env python3
"""
Database Population Script for News Intelligence System v2.7.0
This script adds sample data to the database for testing and validation.
"""

import os
import sys
import psycopg2
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection. Uses shared DB config (run from api/ or PYTHONPATH=api)."""
    try:
        import sys
        _api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if _api not in sys.path:
            sys.path.insert(0, _api)
        from shared.database.connection import get_db_connection
        return get_db_connection()
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

def populate_articles(conn):
    """Populate articles table with sample data"""
    try:
        cursor = conn.cursor()
        
        # Sample articles data
        articles_data = [
            ('Breaking: Major Tech Merger Announced', 
             'Two major technology companies have announced a historic merger that will reshape the industry landscape. The deal, valued at over $50 billion, represents one of the largest technology mergers in recent history.',
             'https://example.com/tech-merger', 'Tech News Daily', 'Technology', 'en', 0.89),
            ('Global Climate Summit Reaches Historic Agreement',
             'World leaders have reached a landmark agreement on climate change during the recent summit. The accord sets ambitious targets for carbon reduction and renewable energy adoption.',
             'https://example.com/climate-summit', 'World News', 'Environment', 'en', 0.92),
            ('AI Breakthrough in Medical Diagnosis',
             'Researchers have developed a new artificial intelligence system that can diagnose rare diseases with unprecedented accuracy. The system achieved 95% accuracy in clinical trials.',
             'https://example.com/ai-medical', 'Science Daily', 'Health', 'en', 0.94),
            ('Economic Recovery Shows Strong Momentum',
             'New economic data indicates a robust recovery across multiple sectors. Employment numbers are up, and consumer confidence has reached a 10-year high.',
             'https://example.com/economic-recovery', 'Business Times', 'Economy', 'en', 0.87),
            ('Space Tourism Company Announces First Commercial Flight',
             'A private space company has announced its first commercial passenger flight to orbit. The mission is scheduled for next year and will carry six civilian passengers.',
             'https://example.com/space-tourism', 'Space News', 'Science', 'en', 0.91),
            ('Cybersecurity Threat Detected in Banking Systems',
             'Security researchers have identified a sophisticated cyber attack targeting major banking institutions. The threat has been contained, but experts warn of similar attacks.',
             'https://example.com/cyber-threat', 'Security Weekly', 'Technology', 'en', 0.88),
            ('New Renewable Energy Plant Opens',
             'A massive solar and wind energy facility has opened in the desert region. The plant will provide clean energy to over 100,000 homes.',
             'https://example.com/renewable-energy', 'Green News', 'Environment', 'en', 0.90),
            ('Breakthrough in Quantum Computing',
             'Scientists have achieved a major milestone in quantum computing, successfully maintaining quantum coherence for over 10 minutes. This breakthrough could accelerate the development of practical quantum computers.',
             'https://example.com/quantum-computing', 'Tech Review', 'Technology', 'en', 0.93),
            ('Global Supply Chain Crisis Easing',
             'Recent data shows that the global supply chain crisis is beginning to ease. Port congestion has decreased, and shipping times are returning to pre-pandemic levels.',
             'https://example.com/supply-chain', 'Trade Journal', 'Economy', 'en', 0.86),
            ('New Cancer Treatment Shows Promise',
             'Clinical trials of a novel cancer treatment have shown remarkable results. The therapy targets cancer cells while leaving healthy cells unharmed.',
             'https://example.com/cancer-treatment', 'Medical News', 'Health', 'en', 0.95)
        ]
        
        # Insert articles
        for i, (title, content, url, source, category, language, quality_score) in enumerate(articles_data):
            published_date = datetime.now() - timedelta(hours=2 + i*2)
            cursor.execute("""
                INSERT INTO articles (title, content, url, source, published_date, category, language, quality_score, processing_status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (title, content, url, source, published_date, category, language, quality_score, 'processed', datetime.now()))
        
        conn.commit()
        print(f"✓ Inserted {len(articles_data)} articles")
        return True
        
    except Exception as e:
        print(f"Error populating articles: {e}")
        conn.rollback()
        return False

def populate_entities(conn):
    """Populate entities table with sample data"""
    try:
        cursor = conn.cursor()
        
        entities_data = [
            ('TechCorp', 'ORG', 15, 0.95, 'Technology'),
            ('InnovateTech', 'ORG', 12, 0.93, 'Technology'),
            ('John Smith', 'PERSON', 8, 0.87, 'Technology'),
            ('United Nations', 'ORG', 18, 0.98, 'Politics'),
            ('Paris', 'GPE', 12, 0.96, 'Politics'),
            ('Climate Action', 'ORG', 8, 0.89, 'Environment'),
            ('Elon Musk', 'PERSON', 25, 0.92, 'Technology'),
            ('Apple Inc.', 'ORG', 20, 0.88, 'Technology'),
            ('United States', 'GPE', 30, 0.91, 'Politics'),
            ('China', 'GPE', 22, 0.89, 'Economy'),
            ('Dr. Sarah Johnson', 'PERSON', 15, 0.94, 'Health'),
            ('Microsoft', 'ORG', 18, 0.87, 'Technology'),
            ('London', 'GPE', 14, 0.85, 'Politics'),
            ('Tesla', 'ORG', 16, 0.90, 'Technology'),
            ('Climate Change', 'CONCEPT', 28, 0.93, 'Environment')
        ]
        
        # Insert entities
        for text, type_, frequency, confidence, category in entities_data:
            cursor.execute("""
                INSERT INTO entities (text, type, frequency, confidence, category, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (text, type_, frequency, confidence, category, datetime.now()))
        
        conn.commit()
        print(f"✓ Inserted {len(entities_data)} entities")
        return True
        
    except Exception as e:
        print(f"Error populating entities: {e}")
        conn.rollback()
        return False

def populate_clusters(conn):
    """Populate article clusters table with sample data"""
    try:
        cursor = conn.cursor()
        
        clusters_data = [
            ('Tech Industry Mergers', 'Technology', 5, 0.87, 'active'),
            ('Climate Change Summit', 'Environment', 3, 0.92, 'active'),
            ('AI and Medical Breakthroughs', 'Health', 2, 0.89, 'active'),
            ('Economic Recovery Trends', 'Economy', 2, 0.85, 'active'),
            ('Space Exploration Advances', 'Science', 1, 0.78, 'active')
        ]
        
        # Insert clusters
        for name, topic, article_count, cohesion_score, status in clusters_data:
            cursor.execute("""
                INSERT INTO article_clusters (name, topic, article_count, cohesion_score, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (name, topic, article_count, cohesion_score, status, datetime.now()))
        
        conn.commit()
        print(f"✓ Inserted {len(clusters_data)} clusters")
        return True
        
    except Exception as e:
        print(f"Error populating clusters: {e}")
        conn.rollback()
        return False

def link_articles_to_entities(conn):
    """Link articles to entities"""
    try:
        cursor = conn.cursor()
        
        # Get article and entity IDs
        cursor.execute("SELECT id FROM articles ORDER BY id LIMIT 10")
        article_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM entities ORDER BY id LIMIT 15")
        entity_ids = [row[0] for row in cursor.fetchall()]
        
        # Create some random links
        links = []
        for i, article_id in enumerate(article_ids):
            # Link each article to 2-3 entities
            for j in range(2, 4):
                if i + j < len(entity_ids):
                    confidence = 0.85 + (i * 0.02)  # Varying confidence scores
                    links.append((article_id, entity_ids[i + j - 2], confidence))
        
        # Insert links
        for article_id, entity_id, confidence in links:
            cursor.execute("""
                INSERT INTO article_entities (article_id, entity_id, confidence)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (article_id, entity_id, confidence))
        
        conn.commit()
        print(f"✓ Created {len(links)} article-entity links")
        return True
        
    except Exception as e:
        print(f"Error linking articles to entities: {e}")
        conn.rollback()
        return False

def link_articles_to_clusters(conn):
    """Link articles to clusters"""
    try:
        cursor = conn.cursor()
        
        # Get article and cluster IDs
        cursor.execute("SELECT id FROM articles ORDER BY id LIMIT 10")
        article_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM article_clusters ORDER BY id LIMIT 5")
        cluster_ids = [row[0] for row in cursor.fetchall()]
        
        # Distribute articles across clusters
        links = []
        for i, article_id in enumerate(article_ids):
            cluster_id = cluster_ids[i % len(cluster_ids)]
            relevance = 0.8 + (i * 0.02)
            links.append((cluster_id, article_id, relevance))
        
        # Insert links
        for cluster_id, article_id, relevance in links:
            cursor.execute("""
                INSERT INTO cluster_articles (cluster_id, article_id, relevance_score)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (cluster_id, article_id, relevance))
        
        conn.commit()
        print(f"✓ Created {len(links)} article-cluster links")
        return True
        
    except Exception as e:
        print(f"Error linking articles to clusters: {e}")
        conn.rollback()
        return False

def main():
    """Main function to populate database"""
    print("🚀 Starting database population...")
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        # Populate tables
        success = True
        success &= populate_articles(conn)
        success &= populate_entities(conn)
        success &= populate_clusters(conn)
        success &= link_articles_to_entities(conn)
        success &= link_articles_to_clusters(conn)
        
        if success:
            print("✅ Database population completed successfully!")
            
            # Show summary
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            article_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM entities")
            entity_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM article_clusters")
            cluster_count = cursor.fetchone()[0]
            
            print(f"\n📊 Database Summary:")
            print(f"   Articles: {article_count}")
            print(f"   Entities: {entity_count}")
            print(f"   Clusters: {cluster_count}")
            
        else:
            print("❌ Database population failed!")
            
    except Exception as e:
        print(f"❌ Error during population: {e}")
        success = False
    
    finally:
        conn.close()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
