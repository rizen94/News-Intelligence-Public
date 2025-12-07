#!/usr/bin/env python3
"""
Comprehensive API route fix for v4 schema
"""

import os
import re

def fix_file(file_path, replacements):
    """Fix a file with multiple replacements"""
    print(f"🔧 Fixing {file_path}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"   ✅ Fixed: {file_path}")
    else:
        print(f"   ⚠️ No changes needed: {file_path}")

# Fix news aggregation routes
fix_file("domains/news_aggregation/routes/news_aggregation.py", [
    ("summary, quality_score, word_count,", "content,"),
    ("quality_score,", ""),
    ("word_count,", ""),
    ("summary,", "content,"),
    ("published_date", "published_at"),
    ("source", "source_domain"),
    ("last_fetch", "last_fetched_at"),
])

# Fix storyline management routes
fix_file("domains/storyline_management/routes/storyline_management.py", [
    ("article_count, quality_score, status,", "status,"),
    ("quality_score,", ""),
    ("article_count,", ""),
    ("created_date", "created_at"),
    ("updated_date", "updated_at"),
])

print("🎉 API route fixing completed!")
