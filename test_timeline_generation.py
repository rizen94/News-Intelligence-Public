#!/usr/bin/env python3
"""
Test script for timeline generation
"""

import sys
import os
import json

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from modules.ml.timeline_generator import TimelineGenerator
from config.database import get_db_config

def test_timeline_generation():
    """Test timeline generation with Ukraine storyline"""
    try:
        # Get database config
        db_config = get_db_config()
        
        # Initialize timeline generator
        timeline_generator = TimelineGenerator(db_config)
        
        # Ukraine storyline data
        storyline_data = {
            "name": "Ukraine-Russia Conflict 2024",
            "description": "Comprehensive tracking of the ongoing conflict between Ukraine and Russia",
            "keywords": ["ukraine", "russia", "conflict", "war", "military", "zelensky", "putin"],
            "entities": ["Volodymyr Zelensky", "Vladimir Putin", "Ukraine", "Russia", "NATO"]
        }
        
        print("🤖 Testing timeline generation...")
        
        # Generate timeline events
        events = timeline_generator.generate_timeline_events(
            storyline_id="ukraine_russia_conflict_2024",
            storyline_data=storyline_data,
            max_events=10
        )
        
        print(f"✅ Generated {len(events)} timeline events")
        
        for i, event in enumerate(events):
            print(f"\nEvent {i+1}:")
            print(f"  Title: {event.title}")
            print(f"  Date: {event.event_date}")
            print(f"  Type: {event.event_type}")
            print(f"  Importance: {event.importance_score}")
            print(f"  Description: {event.description[:100]}...")
        
        return events
        
    except Exception as e:
        print(f"❌ Error testing timeline generation: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    test_timeline_generation()
