#!/usr/bin/env python3
"""
ML Processor Startup Script
Starts the background ML processing service
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.modules.ml.background_processor import BackgroundMLProcessor
from api.config.database import get_db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ml_processor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Start the ML processor"""
    try:
        logger.info("🚀 Starting ML Processor...")
        
        # Get database configuration
        db_config = get_db_config()
        
        # Initialize ML processor
        ml_processor = BackgroundMLProcessor(
            db_config=db_config,
            ollama_url="http://localhost:11434"
        )
        
        # Start workers
        ml_processor.start_workers()
        logger.info("✅ ML Processor started successfully")
        
        # Keep running
        try:
            while True:
                time.sleep(10)
                # Log status every 10 seconds
                stats = ml_processor.get_stats()
                logger.info(f"📊 ML Processor Stats: {stats}")
                
        except KeyboardInterrupt:
            logger.info("🛑 Stopping ML Processor...")
            ml_processor.stop_workers()
            logger.info("✅ ML Processor stopped")
            
    except Exception as e:
        logger.error(f"❌ Failed to start ML Processor: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
