#!/usr/bin/env python3
"""
Script to analyze entity overlap distributions and validate threshold assumptions.
This script analyzes actual data patterns to determine optimal threshold values
for entity overlap detection rather than using fixed rules of thumb.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
import statistics
import json

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

SCHEMAS = ("politics", "finance", "science_tech")

def get_db_connection():
    """Get database connection"""
    from shared.database.connection import get_db_connection
    return get_db_connection()

def analyze_entity_overlap_distribution(cur, schema: str) -> dict:
    """
    Analyze entity overlap distributions for a domain schema.
    Returns statistics about entity overlap counts.
    """
    print(f"Analyzing entity overlap distribution for {schema}...")
    
    # Query to get entity overlap counts between storylines and events
    query = f"""
    WITH storyline_entity_counts AS (
        SELECT 
            storyline_id,
            COUNT(*) as entity_count
        FROM {schema}.story_entity_index
        GROUP BY storyline_id
    ),
    event_entity_matches AS (
        SELECT 
            ce.id as event_id,
            ce.storyline_id,
            COUNT(sei.entity_name) as overlap_count
        FROM public.chronological_events ce
        INNER JOIN {schema}.articles a ON a.id = ce.source_article_id
        LEFT JOIN {schema}.story_entity_index sei ON sei.storyline_id = ce.storyline_id
        WHERE ce.storyline_id IS NOT NULL 
            AND ce.storyline_id ~ '^[0-9]+$'
            AND ce.storyline_id::integer IN (
                SELECT storyline_id FROM storyline_entity_counts
            )
        GROUP BY ce.id, ce.storyline_id
    )
    SELECT 
        overlap_count,
        COUNT(*) as frequency
    FROM event_entity_matches
    GROUP BY overlap_count
    ORDER BY overlap_count
    """
    
    cur.execute(query)
    results = cur.fetchall()
    
    # Convert to distribution data
    overlap_counts = [row[0] for row in results]
    frequencies = [row[1] for row in results]
    
    if not overlap_counts:
        return {
            "schema": schema,
            "total_events": 0,
            "total_storylines": 0,
            "min_overlap": 0,
            "max_overlap": 0,
            "mean_overlap": 0,
            "median_overlap": 0,
            "std_dev": 0,
            "distribution": {}
        }
    
    total_events = sum(frequencies)
    total_storylines = len(overlap_counts)
    
    # Calculate statistics
    mean_overlap = statistics.mean(overlap_counts) if overlap_counts else 0
    median_overlap = statistics.median(overlap_counts) if overlap_counts else 0
    std_dev = statistics.stdev(overlap_counts) if len(overlap_counts) > 1 else 0
    
    # Create distribution
    distribution = dict(zip(overlap_counts, frequencies))
    
    return {
        "schema": schema,
        "total_events": total_events,
        "total_storylines": total_storylines,
        "min_overlap": min(overlap_counts),
        "max_overlap": max(overlap_counts),
        "mean_overlap": round(mean_overlap, 2),
        "median_overlap": median_overlap,
        "std_dev": round(std_dev, 2),
        "distribution": distribution
    }

def analyze_storyline_entity_stats(cur, schema: str) -> dict:
    """Analyze overall entity statistics for storylines in a domain"""
    query = f"""
    SELECT 
        COUNT(*) as total_storylines,
        COUNT(DISTINCT storyline_id) as unique_storylines,
        COUNT(*) as total_entities,
        COUNT(DISTINCT entity_name) as unique_entities,
        AVG(entity_count) as avg_entities_per_storyline
    FROM (
        SELECT 
            storyline_id,
            COUNT(*) as entity_count
        FROM {schema}.story_entity_index
        GROUP BY storyline_id
    ) sub
    """
    
    cur.execute(query)
    result = cur.fetchone()
    
    if result:
        return {
            "schema": schema,
            "total_storylines": result[0],
            "unique_storylines": result[1],
            "total_entities": result[2],
            "unique_entities": result[3],
            "avg_entities_per_storyline": round(result[4], 2) if result[4] else 0
        }
    return {
        "schema": schema,
        "total_storylines": 0,
        "unique_storylines": 0,
        "total_entities": 0,
        "unique_entities": 0,
        "avg_entities_per_storyline": 0
    }

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--output-file",
        metavar="PATH",
        help="Write analysis results to JSON file",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed analysis output"
    )
    args = p.parse_args()

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    try:
        cur = conn.cursor()
        
        # Get overall statistics for each domain
        domain_stats = []
        overlap_analysis = []
        
        for schema in SCHEMAS:
            # Get entity statistics for storylines
            storyline_stats = analyze_storyline_entity_stats(cur, schema)
            domain_stats.append(storyline_stats)
            
            # Get overlap distribution
            overlap_dist = analyze_entity_overlap_distribution(cur, schema)
            overlap_analysis.append(overlap_dist)
            
            if args.verbose:
                print(f"\n{schema.upper()} Domain Statistics:")
                print(f"  Total Storylines: {storyline_stats['total_storylines']}")
                print(f"  Total Entities: {storyline_stats['total_entities']}")
                print(f"  Average Entities per Storyline: {storyline_stats['avg_entities_per_storyline']}")
                print(f"  Overlap Distribution: {overlap_dist['distribution']}")
        
        # Calculate overall statistics
        total_events = sum(dist['total_events'] for dist in overlap_analysis)
        total_storylines = sum(dist['total_storylines'] for dist in overlap_analysis)
        
        # Create summary
        summary = {
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "domains": SCHEMAS,
            "total_events_analyzed": total_events,
            "total_storylines_analyzed": total_storylines,
            "domain_statistics": domain_stats,
            "overlap_distributions": overlap_analysis,
            "recommendations": generate_recommendations(overlap_analysis)
        }
        
        # Print results
        print("\n" + "="*60)
        print("ENTITY OVERLAP ANALYSIS RESULTS")
        print("="*60)
        print(f"Analysis timestamp: {summary['analysis_timestamp']}")
        print(f"Total events analyzed: {summary['total_events_analyzed']}")
        print(f"Total storylines analyzed: {summary['total_storylines_analyzed']}")
        print("\nDomain Statistics:")
        
        for stats in domain_stats:
            print(f"  {stats['schema'].upper()}:")
            print(f"    Storylines: {stats['total_storylines']}")
            print(f"    Entities: {stats['total_entities']}")
            print(f"    Avg entities/storyline: {stats['avg_entities_per_storyline']}")
        
        print("\nOverlap Distribution Analysis:")
        for dist in overlap_analysis:
            print(f"  {dist['schema'].upper()}:")
            print(f"    Min overlap: {dist['min_overlap']}")
            print(f"    Max overlap: {dist['max_overlap']}")
            print(f"    Mean overlap: {dist['mean_overlap']}")
            print(f"    Median overlap: {dist['median_overlap']}")
            print(f"    Std deviation: {dist['std_dev']}")
            print(f"    Distribution: {dist['distribution']}")
        
        print("\nRecommendations:")
        for rec in summary['recommendations']:
            print(f"  • {rec}")
        
        # Write to file if specified
        if args.output_file:
            output_path = args.output_file if os.path.isabs(args.output_file) else os.path.join(ROOT, args.output_file)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"\nResults written to: {output_path}")
        
        return 0
        
    finally:
        cur.close()
        conn.close()

def generate_recommendations(overlap_analysis: list) -> list:
    """Generate data-driven recommendations based on overlap analysis"""
    recommendations = []
    
    # Check if we have sufficient data
    if not overlap_analysis:
        recommendations.append("No data available for analysis")
        return recommendations
    
    # Analyze overlap patterns
    all_min_overlaps = [dist['min_overlap'] for dist in overlap_analysis]
    all_max_overlaps = [dist['max_overlap'] for dist in overlap_analysis]
    all_mean_overlaps = [dist['mean_overlap'] for dist in overlap_analysis]
    
    # Determine if current threshold of 2 is appropriate
    mean_of_means = statistics.mean(all_mean_overlaps) if all_mean_overlaps else 0
    
    if mean_of_means < 2:
        recommendations.append(f"Current threshold of 2 entities may be too high. Average overlap is {mean_of_means:.1f}")
    elif mean_of_means > 5:
        recommendations.append(f"Current threshold of 2 entities may be too low. Average overlap is {mean_of_means:.1f}")
    else:
        recommendations.append(f"Current threshold of 2 entities is appropriate for average overlap of {mean_of_means:.1f}")
    
    # Check for distribution patterns
    for dist in overlap_analysis:
        if dist['distribution']:
            max_overlap = max(dist['distribution'].keys())
            if max_overlap <= 2:
                recommendations.append(f"Domain {dist['schema']}: Most storylines have ≤2 entity overlaps - consider if threshold needs adjustment")
            elif max_overlap > 10:
                recommendations.append(f"Domain {dist['schema']}: Some storylines have >10 entity overlaps - may need to adjust threshold for better filtering")
    
    # Suggest statistical approach
    recommendations.append("Use statistical analysis of overlap distributions rather than fixed thresholds")
    recommendations.append("Consider percentile-based thresholds (e.g., 75th percentile of overlap counts)")
    recommendations.append("Implement dynamic threshold adjustment based on domain-specific patterns")
    
    return recommendations

if __name__ == "__main__":
    raise SystemExit(main())