#!/usr/bin/env python3
"""
Test server startup to identify blocking issues
"""

import sys
import os
sys.path.append('api')

print("Testing server startup...")

try:
    print("1. Importing main...")
    from api.main import app
    print("✅ Main imported successfully")
    
    print("2. Testing database connection...")
    from api.database.connection import get_db_config
    db_config = get_db_config()
    print(f"✅ Database config: {db_config}")
    
    print("3. Testing automation manager...")
    from api.services.automation_manager import AutomationManager
    automation = AutomationManager(db_config)
    print("✅ Automation manager created")
    
    print("4. Testing article processor...")
    from api.services.article_processing_service import get_article_processor
    processor = get_article_processor()
    print("✅ Article processor created")
    
    print("5. Testing dynamic resource service...")
    from api.services.dynamic_resource_service import get_dynamic_resource_service
    resource_service = get_dynamic_resource_service()
    print("✅ Dynamic resource service created")
    
    print("6. Testing RSS processing service...")
    from api.services.rss_processing_service import get_rss_processor
    rss_processor = get_rss_processor()
    print("✅ RSS processor created")
    
    print("7. Testing API cache service...")
    from api.services.api_cache_service import get_cache_service
    cache_service = get_cache_service()
    print("✅ Cache service created")
    
    print("\n🎉 All services loaded successfully!")
    print("The server should start without issues.")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
