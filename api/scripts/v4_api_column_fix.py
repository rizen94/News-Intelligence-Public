#!/usr/bin/env python3
"""
News Intelligence System 4.0 API Column Fix Script
Fixes API routes to use correct v4 table columns
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime

def backup_file(file_path):
    """Create backup of file before modification"""
    backup_path = f"{file_path}.backup_columns_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"   📁 Backed up: {file_path} → {backup_path}")
    return backup_path

def fix_news_aggregation_routes():
    """Fix news aggregation routes to use correct v4 columns"""
    print("🔄 Fixing news aggregation routes...")
    
    file_path = "api/domains/news_aggregation/routes/news_aggregation.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix column references for articles_v4
    replacements = [
        # Remove non-existent columns
        ('summary, quality_score, word_count,', 'content,'),
        ('quality_score,', ''),
        ('word_count,', ''),
        ('summary,', 'content,'),
        # Fix field mappings
        ('published_date', 'published_at'),
        ('source', 'source_domain'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Fixed: {file_path}")

def fix_storyline_management_routes():
    """Fix storyline management routes to use correct v4 columns"""
    print("🔄 Fixing storyline management routes...")
    
    file_path = "api/domains/storyline_management/routes/storyline_management.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix column references for storylines_v4
    replacements = [
        # Remove non-existent columns
        ('article_count, quality_score, status,', 'status,'),
        ('quality_score,', ''),
        ('article_count,', ''),
        # Fix field mappings
        ('created_date', 'created_at'),
        ('updated_date', 'updated_at'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Fixed: {file_path}")

def fix_rss_feeds_routes():
    """Fix RSS feeds routes to use correct v4 columns"""
    print("🔄 Fixing RSS feeds routes...")
    
    file_path = "api/domains/news_aggregation/routes/news_aggregation.py"
    backup_file(file_path)
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix column references for rss_feeds_v4
    replacements = [
        # Remove non-existent columns
        ('quality_score,', ''),
        ('last_fetch,', 'last_fetched_at,'),
        # Fix field mappings
        ('last_fetch', 'last_fetched_at'),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"   ✅ Fixed: {file_path}")

def main():
    """Main function"""
    print("🚀 Starting News Intelligence System 4.0 API Column Fix")
    print("=" * 60)
    
    try:
        fix_news_aggregation_routes()
        fix_storyline_management_routes()
        fix_rss_feeds_routes()
        
        print("\n🎉 API Column Fix completed successfully!")
        print("📊 All API routes updated to use correct v4 columns")
        print("🔄 Next steps: Test API endpoints")
        
    except Exception as e:
        print(f"❌ API Column Fix failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
