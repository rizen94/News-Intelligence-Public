#!/usr/bin/env python3
"""
Development API Server with Hot Reloading
Fixes persistent code loading issues by forcing module reloading
"""

import os
import sys
import logging
import importlib
import uvicorn
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

def clear_python_cache():
    """Clear all Python cache files"""
    logger.info("🧹 Clearing Python cache...")
    
    # Clear __pycache__ directories
    for root, dirs, files in os.walk(api_root):
        for dir_name in dirs[:]:  # Use slice to avoid modifying list while iterating
            if dir_name == '__pycache__':
                cache_path = os.path.join(root, dir_name)
                import shutil
                shutil.rmtree(cache_path, ignore_errors=True)
                logger.info(f"   Removed: {cache_path}")
                dirs.remove(dir_name)  # Don't recurse into removed directory
    
    # Clear .pyc files
    for root, dirs, files in os.walk(api_root):
        for file in files:
            if file.endswith('.pyc'):
                pyc_path = os.path.join(root, file)
                os.remove(pyc_path)
                logger.info(f"   Removed: {pyc_path}")

def force_module_reload():
    """Force reload of all project modules"""
    logger.info("🔄 Forcing module reload...")
    
    # Clear sys.modules for project modules
    modules_to_remove = []
    for module_name in sys.modules:
        if any(path in module_name for path in ['domains', 'shared', 'services', 'main_v4']):
            modules_to_remove.append(module_name)
    
    for module_name in modules_to_remove:
        del sys.modules[module_name]
        logger.info(f"   Removed from cache: {module_name}")

def start_api_server():
    """Start the API server with proper module loading"""
    logger.info("🚀 Starting News Intelligence System v4.0 API (Development Mode)")
    
    # Clear cache and force reload
    clear_python_cache()
    force_module_reload()
    
    # Import and start the app
    try:
        from main_v4 import app
        logger.info("✅ Main application imported successfully")
        
        # Start uvicorn with proper configuration
        uvicorn.run(
            "main_v4:app",  # Use import string for proper reload
            host="0.0.0.0",
            port=8001,
            log_level="info",
            reload=True,  # Enable hot reloading
            reload_dirs=[str(api_root)]  # Watch API directory for changes
        )
    except Exception as e:
        logger.error(f"❌ Failed to start API server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    start_api_server()
