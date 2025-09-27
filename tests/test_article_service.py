#!/usr/bin/env python3
"""
Test ArticleService to debug the issue
"""

import sys
import os
sys.path.append('api')

from config.database import get_db_session
from services.article_service import ArticleService

def test_article_service():
    """Test ArticleService directly"""
    try:
        print("🔍 Testing ArticleService...")
        
        # Get database session directly
        db = get_db_session()
        print(f"✅ Database session type: {type(db)}")
        
        # Create ArticleService
        service = ArticleService(db)
        print(f"✅ ArticleService created successfully")
        
        # Test get_stats method
        import asyncio
        stats = asyncio.run(service.get_stats())
        print(f"✅ get_stats() returned: {stats}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_article_service()

