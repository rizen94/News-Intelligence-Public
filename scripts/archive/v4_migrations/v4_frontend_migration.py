#!/usr/bin/env python3
"""
News Intelligence System 4.0 Frontend Migration Script
Updates frontend components to use v4 data structures
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

def update_api_service():
    """Update API service to use v4 endpoints"""
    print("🔄 Updating API service...")
    
    file_path = "web/src/services/apiService.ts"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update API endpoints to use v4
        replacements = [
            ('/api/articles', '/api/v4/articles'),
            ('/api/storylines', '/api/v4/storylines'),
            ('/api/rss-feeds', '/api/v4/rss-feeds'),
            ('/api/system-monitoring', '/api/v4/system-monitoring'),
            ('/api/content-analysis', '/api/v4/content-analysis'),
            ('/api/user-management', '/api/v4/user-management'),
            ('/api/intelligence-hub', '/api/v4/intelligence-hub'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def update_dashboard_component():
    """Update dashboard component for v4 data structures"""
    print("🔄 Updating dashboard component...")
    
    file_path = "web/src/pages/Dashboard/EnhancedDashboard.js"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update data structure expectations
        replacements = [
            ('data?.total_count', 'data?.total'),
            ('data?.feeds?.length', 'data?.total'),
            ('data?.storylines?.length', 'data?.total'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def update_articles_component():
    """Update articles component for v4 data structures"""
    print("🔄 Updating articles component...")
    
    file_path = "web/src/pages/Articles/EnhancedArticles.js"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update field mappings
        replacements = [
            ('published_date', 'published_at'),
            ('source', 'source_domain'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def update_storylines_component():
    """Update storylines component for v4 data structures"""
    print("🔄 Updating storylines component...")
    
    file_path = "web/src/pages/Storylines/EnhancedStorylines.js"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update field mappings
        replacements = [
            ('created_date', 'created_at'),
            ('updated_date', 'updated_at'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def update_rss_feeds_component():
    """Update RSS feeds component for v4 data structures"""
    print("🔄 Updating RSS feeds component...")
    
    file_path = "web/src/pages/RSSFeeds/EnhancedRSSFeeds.js"
    if os.path.exists(file_path):
        backup_file(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update field mappings
        replacements = [
            ('last_fetch', 'last_fetched_at'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"   ✅ Updated: {file_path}")
    else:
        print(f"   ⚠️ File not found: {file_path}")

def create_v4_frontend_compatibility():
    """Create frontend compatibility layer"""
    print("🔄 Creating frontend v4 compatibility layer...")
    
    compatibility_code = '''
// V4 Frontend Compatibility Layer
// This module provides compatibility between legacy frontend expectations and v4 data

export const v4Compatibility = {
  // Map v4 article fields to legacy expectations
  mapArticle: (article) => ({
    ...article,
    published_date: article.published_at,
    source: article.source_domain,
  }),
  
  // Map v4 storyline fields to legacy expectations
  mapStoryline: (storyline) => ({
    ...storyline,
    created_date: storyline.created_at,
    updated_date: storyline.updated_at,
  }),
  
  // Map v4 RSS feed fields to legacy expectations
  mapRSSFeed: (feed) => ({
    ...feed,
    last_fetch: feed.last_fetched_at,
  }),
  
  // Map v4 API response structure
  mapAPIResponse: (response) => ({
    ...response,
    data: {
      ...response.data,
      total_count: response.data?.total || response.data?.total_count,
      feeds: response.data?.feeds || response.data?.items,
      storylines: response.data?.storylines || response.data?.items,
    }
  })
};

export default v4Compatibility;
'''
    
    with open("web/src/services/v4Compatibility.js", 'w') as f:
        f.write(compatibility_code)
    
    print("   ✅ Created: web/src/services/v4Compatibility.js")

def main():
    """Main migration function"""
    print("🚀 Starting News Intelligence System 4.0 Frontend Migration")
    print("=" * 65)
    
    try:
        # Update all frontend components
        update_api_service()
        update_dashboard_component()
        update_articles_component()
        update_storylines_component()
        update_rss_feeds_component()
        
        # Create compatibility layer
        create_v4_frontend_compatibility()
        
        print("\n🎉 Frontend Migration completed successfully!")
        print("📊 All frontend components updated for v4 compatibility")
        print("🔄 Next steps: Test frontend functionality and restart services")
        
    except Exception as e:
        print(f"❌ Frontend Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
