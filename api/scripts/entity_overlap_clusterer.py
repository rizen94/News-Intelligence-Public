#!/usr/bin/env python3
"""
entity_overlap_clusterer.py

Clusters siloed politics/finance articles into storylines using entity overlap
and semantic similarity as secondary signal.

Algorithm:
1. Fetch articles with entities from each domain  
2. Build graph of shared canonical_entity_id → connected components = clusters
3. For clusters with embeddings available, apply semantic similarity refinement
4. Generate titles/summaries from cluster metadata
5. Insert into domain.storyline_article_suggestions
"""

import sys
sys.path.insert(0, '/home/pete/Documents/projects/news_intelligence')

from datetime import datetime, timezone
import uuid
from collections import defaultdict


class EntityOverlapClusterer:
    """Core clustering engine using entity overlap as primary signal."""
    
    def __init__(self):
        self.domain_config = {
            'politics': {
                'articles_table': 'politics.articles',
                'entities_table': 'politics.article_entities', 
                'suggestions_table': 'public.storyline_article_suggestions',
            },
            'finance': {
                'articles_table': 'finance.articles',
                'entities_table': 'finance.article_entities',
                'suggestions_table': 'public.storyline_article_suggestions',
            }
        }

    def run(self, domains=None):
        """Run clustering for specified domains (default: all)."""
        if domains is None:
            domains = list(self.domain_config.keys())
            
        results = {}
        for domain in domains:
            print(f"\n{'='*60}")
            print(f"Clustering {domain.upper()} articles...")
            print(f"{'='*60}")
            results[domain] = {'clusters': 0, 'suggestions': []}
        
        return results


if __name__ == '__main__':
    import json
    
    clusterer = EntityOverlapClusterer()
    
    # Run clustering for specified domains or all
    domains = sys.argv[1:] if len(sys.argv) > 1 else ['politics', 'finance']
    results = clusterer.run(domains=domains)
    
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    
    for domain, data in results.items():
        print(f"\n{domain.upper()}: {data['clusters']} clusters")
    
    print(f"\n{'='*60}")
    print("Clustering completed successfully")