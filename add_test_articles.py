#!/usr/bin/env python3
"""
Script to add test Ukraine-related articles for timeline testing
"""

import sys
import os
import psycopg2
from datetime import datetime, timedelta

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from config.database import get_db_config

def add_test_ukraine_articles():
    """Add test Ukraine-related articles"""
    try:
        # Get database config
        db_config = get_db_config()
        
        # Connect to database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        # Test articles about Ukraine conflict
        test_articles = [
            {
                "title": "Ukraine Reports Major Military Victory in Eastern Front",
                "content": "Ukrainian forces have successfully repelled Russian advances in the Donbas region, marking a significant military victory. The operation involved coordinated strikes against Russian positions and resulted in the liberation of several key towns. President Zelensky praised the bravery of Ukrainian soldiers and called for continued international support.",
                "summary": "Ukraine achieves major military victory in Donbas region, liberating key towns from Russian control.",
                "source": "BBC News",
                "url": "https://bbc.com/ukraine-victory-donbas",
                "published_date": datetime.now() - timedelta(days=1),
                "category": "Military",
                "processing_status": "completed"
            },
            {
                "title": "NATO Approves Additional Military Aid Package for Ukraine",
                "content": "NATO member states have unanimously approved a new $2.5 billion military aid package for Ukraine, including advanced weapons systems and ammunition. The package includes HIMARS rocket systems, anti-aircraft missiles, and armored vehicles. Secretary General Stoltenberg emphasized NATO's unwavering support for Ukraine's sovereignty.",
                "summary": "NATO approves $2.5B military aid package for Ukraine including advanced weapons systems.",
                "source": "Reuters",
                "url": "https://reuters.com/nato-ukraine-aid-package",
                "published_date": datetime.now() - timedelta(days=2),
                "category": "Military",
                "processing_status": "completed"
            },
            {
                "title": "Russian Missile Strike Hits Ukrainian Hospital in Kharkiv",
                "content": "A Russian missile strike has hit a civilian hospital in Kharkiv, killing at least 12 people and injuring dozens more. The attack occurred during morning hours when the hospital was treating patients. Ukrainian officials have condemned the attack as a war crime, while Russia claims it was targeting military infrastructure.",
                "summary": "Russian missile strike hits civilian hospital in Kharkiv, killing 12 and injuring dozens.",
                "source": "CNN",
                "url": "https://cnn.com/russia-hospital-strike-kharkiv",
                "published_date": datetime.now() - timedelta(days=3),
                "category": "Humanitarian",
                "processing_status": "completed"
            },
            {
                "title": "EU Imposes New Sanctions on Russian Energy Sector",
                "content": "The European Union has announced new sanctions targeting Russia's energy sector, including restrictions on oil and gas imports. The sanctions aim to reduce Russia's ability to fund its military operations in Ukraine. Several EU countries have already begun reducing their dependence on Russian energy.",
                "summary": "EU imposes new sanctions on Russian energy sector to reduce funding for military operations.",
                "source": "AP News",
                "url": "https://apnews.com/eu-russia-energy-sanctions",
                "published_date": datetime.now() - timedelta(days=4),
                "category": "Economic",
                "processing_status": "completed"
            },
            {
                "title": "Ukrainian Refugees Reach 5 Million Mark",
                "content": "The number of Ukrainian refugees fleeing the conflict has reached 5 million, according to UNHCR data. Most refugees have found shelter in neighboring countries like Poland, Romania, and Hungary. The UN has called for increased international support to help host countries manage the refugee crisis.",
                "summary": "Ukrainian refugee count reaches 5 million, with most finding shelter in neighboring countries.",
                "source": "UN News",
                "url": "https://news.un.org/ukraine-refugees-5-million",
                "published_date": datetime.now() - timedelta(days=5),
                "category": "Humanitarian",
                "processing_status": "completed"
            }
        ]
        
        # Insert test articles
        for article in test_articles:
            cur.execute("""
                INSERT INTO articles (
                    title, content, summary, source, url, published_date, 
                    category, processing_status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                article["title"],
                article["content"],
                article["summary"],
                article["source"],
                article["url"],
                article["published_date"],
                article["category"],
                article["processing_status"],
                datetime.now(),
                datetime.now()
            ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ Successfully added {len(test_articles)} test Ukraine-related articles")
        
    except Exception as e:
        print(f"❌ Error adding test articles: {e}")

if __name__ == "__main__":
    add_test_ukraine_articles()
