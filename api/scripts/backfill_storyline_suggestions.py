#!/usr/bin/env python3
"""
backfill_storyline_suggestions.py

Backfills storyline article suggestions using entity overlap clustering and semantic similarity.

This script runs the entity_overlap_clusterer to generate cluster-based suggestions,
then processes them for insertion into the database.
"""

import sys
import os
sys.path.insert(0, '/home/pete/Documents/projects/news_intelligence')

from datetime import datetime
import uuid


def main():
    print("Starting backfill of storyline suggestions...")
    print("=" * 60)
    
    # Import and run the entity overlap clusterer
    try:
        from api.scripts.entity_overlap_clusterer import EntityOverlapClusterer
        
        clusterer = EntityOverlapClusterer()
        
        # Run clustering for both domains
        domains = ['politics', 'finance']
        results = clusterer.run(domains=domains)
        
        print(f"\nClustering Results:")
        for domain, data in results.items():
            print(f"  {domain.upper()}: {data['clusters']} clusters generated")
            
        print("\nBackfill process completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during backfill: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()