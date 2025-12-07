#!/usr/bin/env python3
"""
News Intelligence System 4.0 API Migration Script
Updates all API endpoints to use v4 schema
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

def backup_file(file_path):
    """Create backup of file before modification"""
    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"   📁 Backed up: {file_path} → {backup_path}")
    return backup_path

def update_news_aggregation_routes():
    """Update news aggregation routes to use v4 tables"""
    print("🔄 Updating news aggregation routes...")
    
    file_path = "api/domains/news_aggregation/routes/news_aggregation.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace table references
    replacements = [
        ('FROM articles', 'FROM articles_v4'),
        ('INSERT INTO articles', 'INSERT INTO articles_v4'),
        ('UPDATE articles', 'UPDATE articles_v4'),
        ('DELETE FROM articles', 'DELETE FROM articles_v4'),
        ('FROM rss_feeds', 'FROM rss_feeds_v4'),
        ('INSERT INTO rss_feeds', 'INSERT INTO rss_feeds_v4'),
        ('UPDATE rss_feeds', 'UPDATE rss_feeds_v4'),
        ('DELETE FROM rss_feeds', 'DELETE FROM rss_feeds_v4'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Updated: {file_path}")

def update_storyline_management_routes():
    """Update storyline management routes to use v4 tables"""
    print("🔄 Updating storyline management routes...")
    
    file_path = "api/domains/storyline_management/routes/storyline_management.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace table references
    replacements = [
        ('FROM storylines', 'FROM storylines_v4'),
        ('INSERT INTO storylines', 'INSERT INTO storylines_v4'),
        ('UPDATE storylines', 'UPDATE storylines_v4'),
        ('DELETE FROM storylines', 'DELETE FROM storylines_v4'),
        ('FROM storyline_articles', 'FROM storyline_articles_v4'),
        ('INSERT INTO storyline_articles', 'INSERT INTO storyline_articles_v4'),
        ('UPDATE storyline_articles', 'UPDATE storyline_articles_v4'),
        ('DELETE FROM storyline_articles', 'DELETE FROM storyline_articles_v4'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Updated: {file_path}")

def update_content_analysis_routes():
    """Update content analysis routes to use v4 tables"""
    print("🔄 Updating content analysis routes...")
    
    file_path = "api/domains/content_analysis/routes/content_analysis.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace table references
    replacements = [
        ('FROM articles', 'FROM articles_v4'),
        ('FROM topic_clusters', 'FROM topic_clusters_v4'),
        ('FROM article_topic_clusters', 'FROM article_topics_v4'),
        ('INSERT INTO topic_clusters', 'INSERT INTO topic_clusters_v4'),
        ('INSERT INTO article_topic_clusters', 'INSERT INTO article_topics_v4'),
        ('UPDATE topic_clusters', 'UPDATE topic_clusters_v4'),
        ('UPDATE article_topic_clusters', 'UPDATE article_topics_v4'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Updated: {file_path}")

def update_system_monitoring_routes():
    """Update system monitoring routes to use v4 tables"""
    print("🔄 Updating system monitoring routes...")
    
    file_path = "api/domains/system_monitoring/routes/system_monitoring.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace table references
    replacements = [
        ('FROM system_metrics', 'FROM system_metrics_v4'),
        ('FROM pipeline_traces', 'FROM pipeline_traces_v4'),
        ('INSERT INTO system_metrics', 'INSERT INTO system_metrics_v4'),
        ('INSERT INTO pipeline_traces', 'INSERT INTO pipeline_traces_v4'),
        ('UPDATE system_metrics', 'UPDATE system_metrics_v4'),
        ('UPDATE pipeline_traces', 'UPDATE pipeline_traces_v4'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Updated: {file_path}")

def update_user_management_routes():
    """Update user management routes to use v4 tables"""
    print("🔄 Updating user management routes...")
    
    file_path = "api/domains/user_management/routes/user_management.py"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace table references
        replacements = [
            ('FROM users', 'FROM users_v4'),
            ('INSERT INTO users', 'INSERT INTO users_v4'),
            ('UPDATE users', 'UPDATE users_v4'),
            ('DELETE FROM users', 'DELETE FROM users_v4'),
            ('FROM user_preferences', 'FROM user_preferences_v4'),
            ('INSERT INTO user_preferences', 'INSERT INTO user_preferences_v4'),
            ('UPDATE user_preferences', 'UPDATE user_preferences_v4'),
            ('DELETE FROM user_preferences', 'DELETE FROM user_preferences_v4'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def update_intelligence_hub_routes():
    """Update intelligence hub routes to use v4 tables"""
    print("🔄 Updating intelligence hub routes...")
    
    file_path = "api/domains/intelligence_hub/routes/intelligence_hub.py"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Replace table references
        replacements = [
            ('FROM articles', 'FROM articles_v4'),
            ('FROM storylines', 'FROM storylines_v4'),
            ('FROM topic_clusters', 'FROM topic_clusters_v4'),
            ('FROM analysis_results', 'FROM analysis_results_v4'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def create_v4_api_compatibility_layer():
    """Create API compatibility layer for smooth transition"""
    print("🔄 Creating v4 API compatibility layer...")
    
    compatibility_code = '''
# V4 API Compatibility Layer
# This module provides compatibility between legacy API calls and v4 schema

def get_articles_v4_compatibility():
    """Compatibility function for articles API"""
    # Maps legacy article fields to v4 fields
    field_mapping = {
        'published_date': 'published_at',
        'source': 'source_domain',
        'feed_id': 'feed_id',
        'content_hash': 'content_hash',
        'processing_status': 'processing_status'
    }
    return field_mapping

def get_storylines_v4_compatibility():
    """Compatibility function for storylines API"""
    field_mapping = {
        'created_date': 'created_at',
        'updated_date': 'updated_at',
        'status': 'status'
    }
    return field_mapping

def get_rss_feeds_v4_compatibility():
    """Compatibility function for RSS feeds API"""
    field_mapping = {
        'feed_name': 'feed_name',
        'feed_url': 'feed_url',
        'is_active': 'is_active',
        'last_fetch': 'last_fetched_at'
    }
    return field_mapping
'''
    
    with open("api/v4_compatibility.py", 'w') as f:
        f.write(compatibility_code)
    
    print("   ✅ Created: api/v4_compatibility.py")

def main():
    """Main migration function"""
    print("🚀 Starting News Intelligence System 4.0 API Migration")
    print("=" * 60)
    
    try:
        # Update all route files
        update_news_aggregation_routes()
        update_storyline_management_routes()
        update_content_analysis_routes()
        update_system_monitoring_routes()
        update_user_management_routes()
        update_intelligence_hub_routes()
        
        # Create compatibility layer
        create_v4_api_compatibility_layer()
        
        print("\n🎉 API Migration completed successfully!")
        print("📊 All API endpoints updated to use v4 schema")
        print("🔄 Next steps: Test API endpoints and update frontend")
        
    except Exception as e:
        print(f"❌ API Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
