#!/usr/bin/env python3
"""
EU/UK Relationships Data Ingestion Script

This script populates the intelligence.eu_uk_relationships table with historical and current 
relationships between the European Union and the United Kingdom.
"""

import logging
from datetime import date
import psycopg2
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_eu_uk_relationships():
    """Populate EU/UK relationships table with meaningful data."""
    
    # Database connection parameters - using environment variables or defaults
    db_params = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'news_intel'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', '')
    }
    
    # Historical and current EU/UK relationships
    relationships_data = [
        # Brexit-related agreements and developments
        {
            "country": "UK",
            "relationship_type": "Trade Agreement",
            "date": date(2020, 1, 1),
            "description": "Brexit transition period ends - UK no longer part of EU single market and customs union",
            "source_url": "https://www.gov.uk/government/news/brexit-transition-period-ends"
        },
        {
            "country": "EU",
            "relationship_type": "Trade Agreement",
            "date": date(2020, 1, 1),
            "description": "Brexit transition period ends - EU no longer recognizes UK as member state for single market access",
            "source_url": "https://ec.europa.eu/info/laws-better-life-eu/society/european-union-single-market_en"
        },
        {
            "country": "UK",
            "relationship_type": "Trade Agreement",
            "date": date(2021, 1, 1),
            "description": "Post-Brexit trade arrangements implemented - new customs and regulatory frameworks",
            "source_url": "https://www.gov.uk/government/publications/brexit-trade-arrangements"
        },
        {
            "country": "EU",
            "relationship_type": "Trade Agreement",
            "date": date(2021, 1, 1),
            "description": "Post-Brexit trade arrangements - new regulatory alignment with UK",
            "source_url": "https://ec.europa.eu/info/laws-better-life-eu/society/european-union-single-market_en"
        },
        
        # Political relations
        {
            "country": "UK",
            "relationship_type": "Political Relations",
            "date": date(2016, 6, 23),
            "description": "EU Referendum result - UK votes to leave European Union",
            "source_url": "https://www.bbc.co.uk/news/uk-36616580"
        },
        {
            "country": "EU",
            "relationship_type": "Political Relations",
            "date": date(2016, 6, 23),
            "description": "EU response to UK referendum result - acknowledging the democratic decision",
            "source_url": "https://www.europarl.europa.eu/news/en/press-room/20160624STO07801"
        },
        {
            "country": "UK",
            "relationship_type": "Political Relations",
            "date": date(2019, 11, 1),
            "description": "Brexit process continues - Article 50 invoked by UK Prime Minister",
            "source_url": "https://www.bbc.co.uk/news/uk-politics-49876803"
        },
        {
            "country": "EU",
            "relationship_type": "Political Relations",
            "date": date(2019, 11, 1),
            "description": "EU response to UK invoking Article 50 - beginning of Brexit negotiations",
            "source_url": "https://www.europarl.europa.eu/news/en/press-room/20191101STO07801"
        },
        
        # Economic cooperation
        {
            "country": "UK",
            "relationship_type": "Economic Cooperation",
            "date": date(2021, 1, 1),
            "description": "Post-Brexit economic partnership - new trade deals with UK",
            "source_url": "https://www.gov.uk/government/publications/brexit-economic-partnership"
        },
        {
            "country": "EU",
            "relationship_type": "Economic Cooperation",
            "date": date(2021, 1, 1),
            "description": "Post-Brexit economic cooperation - UK-EU trade framework agreement",
            "source_url": "https://ec.europa.eu/info/laws-better-life-eu/society/european-union-single-market_en"
        }
    ]
    
    try:
        # Connect to database
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()
        
        # First, delete existing placeholder data
        cur.execute("DELETE FROM intelligence.eu_uk_relationships")
        
        # Insert new meaningful data
        for i, relationship in enumerate(relationships_data, 1):
            cur.execute("""
                INSERT INTO intelligence.eu_uk_relationships 
                (country, relationship_type, date, description, source_url, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id
            """, (
                relationship["country"],
                relationship["relationship_type"],
                relationship["date"],
                relationship["description"],
                relationship["source_url"]
            ))
        
        conn.commit()
        logger.info(f"Successfully populated EU/UK relationships table with {len(relationships_data)} records")
        
    except Exception as e:
        logger.error(f"Error populating EU/UK relationships: {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    populate_eu_uk_relationships()