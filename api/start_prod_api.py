#!/usr/bin/env python3
"""
Production API Server
Optimized for performance without hot reloading
"""

import os
import sys
import logging
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent.parent
api_root = Path(__file__).parent
sys.path.insert(0, str(api_root))
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_api_server():
    """Start the API server in production mode"""
    logger.info("🚀 Starting News Intelligence System v4.0 API (Production Mode)")
    
    try:
        from main_v4 import app
        logger.info("✅ Main application imported successfully")
        
        import uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8001,
            log_level="info",
            reload=False  # No hot reloading in production
        )
    except Exception as e:
        logger.error(f"❌ Failed to start API server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    start_api_server()
