#!/usr/bin/env python3
"""
Test script to demonstrate improved narrative-focused summarization
"""

import requests
import json

def test_improved_summary():
    """Test the improved summarization approach"""
    
    # Get current storyline
    response = requests.get("http://localhost:8000/api/storyline/4/")
    if response.status_code != 200:
        print("❌ Failed to get storyline")
        return
    
    storyline_data = response.json()
    articles = storyline_data['data']['storyline']['articles']
    
    print("🔍 ANALYZING CURRENT APPROACH")
    print("=" * 50)
    print(f"Storyline: {storyline_data['data']['storyline']['title']}")
    print(f"Articles: {len(articles)}")
    print()
    
    # Show current approach (full content dumping)
    print("❌ CURRENT APPROACH (Content Dumping):")
    print("-" * 40)
    for i, article in enumerate(articles[:2], 1):  # Show first 2 articles
        print(f"Article {i}: {article['title']}")
        content = article.get('content', '')[:200] + "..." if len(article.get('content', '')) > 200 else article.get('content', '')
        print(f"Content: {content}")
        print()
    
    print("✅ IMPROVED APPROACH (Narrative Building):")
    print("-" * 40)
    
    # Show improved approach (key points extraction)
    for i, article in enumerate(articles[:2], 1):  # Show first 2 articles
        print(f"Story Element {i}: {article['title']}")
        print(f"Source: {article.get('source', 'Unknown')}")
        print(f"Date: {article.get('published_at', 'Unknown')}")
        
        # Extract key narrative elements
        content = article.get('content', '')
        if content:
            # Take first 2-3 sentences as key points
            sentences = content.split('. ')[:3]
            print("Key Narrative Points:")
            for j, sentence in enumerate(sentences, 1):
                if sentence.strip() and len(sentence.strip()) > 15:
                    clean_sentence = sentence.strip()
                    if not clean_sentence.endswith('.'):
                        clean_sentence += '.'
                    print(f"  • {clean_sentence}")
        print()
    
    print("🎯 NARRATIVE FOCUS:")
    print("- Focus on how story elements connect")
    print("- Build a cohesive narrative from components")
    print("- Use titles as story guidelines")
    print("- Extract key points instead of full content")
    print("- Create unified story arc")

if __name__ == "__main__":
    test_improved_summary()
