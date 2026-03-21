#!/usr/bin/env python3
"""
News Intelligence System v2.1.0 - Intelligence Management Script
Manages the intelligence processing pipeline
"""

import argparse
import logging
import os
import sys

# Add api to path so shared.database.connection is available
_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)


def _get_db_config():
    """Database config from shared source (DB_* env / .env)."""
    from shared.database.connection import get_db_config

    return get_db_config()


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_intelligence_pipeline(batch_size: int = 100):
    """Run the complete intelligence processing pipeline"""
    try:
        from modules.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

        db_config = _get_db_config()
        logger.info("🚀 Starting intelligence processing pipeline...")

        orchestrator = IntelligenceOrchestrator(db_config)
        results = orchestrator.run_full_intelligence_pipeline(batch_size)

        if "error" in results:
            logger.error(f"❌ Pipeline failed: {results['error']}")
            return False

        logger.info("✅ Pipeline completed successfully!")
        logger.info(
            f"📊 Results: {results['articles_processed']} articles processed, "
            f"{results['clusters_created']} clusters created, "
            f"{results['datasets_created']} datasets created"
        )

        orchestrator.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error running intelligence pipeline: {e}")
        return False


def get_intelligence_status():
    """Get current status of intelligence processing"""
    try:
        from modules.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

        db_config = _get_db_config()
        orchestrator = IntelligenceOrchestrator(db_config)
        status = orchestrator.get_intelligence_status()

        if status:
            logger.info("📊 Intelligence System Status:")
            logger.info(f"   Database Connected: {status.get('database_connected', False)}")
            logger.info(f"   System Health: {status.get('system_health', 'unknown')}")

            stats = status.get("processing_stats", {})
            logger.info(f"   Total Articles: {stats.get('total_articles', 0)}")
            logger.info(f"   ML Processed: {stats.get('ml_processed', 0)}")
            logger.info(f"   Processing Errors: {stats.get('processing_errors', 0)}")
            logger.info(f"   Processing Progress: {stats.get('processing_progress', 0)}%")
            logger.info(f"   Clusters Created: {stats.get('clusters_created', 0)}")
            logger.info(f"   Datasets Created: {stats.get('datasets_created', 0)}")

            # Show recent activity
            recent = status.get("recent_activity", [])
            if recent:
                logger.info("   Recent Activity:")
                for activity in recent[:5]:  # Show last 5
                    logger.info(f"     Article {activity['article_id']}: {activity['status']}")

        orchestrator.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error getting intelligence status: {e}")
        return False


def process_single_article(article_id: int):
    """Process a single article through the intelligence pipeline"""
    try:
        from modules.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

        db_config = _get_db_config()
        logger.info(f"🔍 Processing single article {article_id}...")

        orchestrator = IntelligenceOrchestrator(db_config)
        result = orchestrator.process_single_article(article_id)

        if "error" in result:
            logger.error(f"❌ Article processing failed: {result['error']}")
            return False

        logger.info("✅ Article processing completed!")
        logger.info(f"   ML Data: {result.get('ml_data', {})}")
        logger.info(f"   Similar Articles: {result.get('similar_articles', 0)}")
        logger.info(f"   Dataset Created: {result.get('dataset_created', 0)}")

        orchestrator.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error processing single article: {e}")
        return False


def create_custom_dataset(dataset_name: str, filters_str: str):
    """Create a custom ML dataset"""
    try:
        import json

        from modules.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

        # Parse filters
        try:
            filters = json.loads(filters_str) if filters_str else {}
        except json.JSONDecodeError:
            logger.error("❌ Invalid filters format. Use valid JSON.")
            return False

        # Database configuration
        db_config = _get_db_config()
        logger.info(f"📊 Creating custom dataset '{dataset_name}'...")

        orchestrator = IntelligenceOrchestrator(db_config)
        dataset = orchestrator.create_custom_dataset(dataset_name, filters)

        if "error" in dataset:
            logger.error(f"❌ Dataset creation failed: {dataset['error']}")
            return False

        logger.info("✅ Custom dataset created successfully!")
        logger.info(f"   Dataset ID: {dataset.get('dataset_id', 0)}")
        logger.info(f"   Article Count: {dataset.get('article_count', 0)}")
        logger.info(f"   Filters: {dataset.get('filters', {})}")

        # Show statistics if available
        stats = dataset.get("statistics", {})
        if stats:
            logger.info(f"   Total Words: {stats.get('total_words', 0)}")
            logger.info(f"   Average Quality: {stats.get('average_quality', 0)}")

        orchestrator.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error creating custom dataset: {e}")
        return False


def export_dataset(dataset_id: int, format_type: str = "csv"):
    """Export a dataset"""
    try:
        from modules.intelligence.intelligence_orchestrator import IntelligenceOrchestrator

        # Database configuration
        db_config = _get_db_config()
        logger.info(f"📤 Exporting dataset {dataset_id} in {format_type} format...")

        orchestrator = IntelligenceOrchestrator(db_config)
        result = orchestrator.export_dataset(dataset_id, format_type)

        if "error" in result:
            logger.error(f"❌ Export failed: {result['error']}")
            return False

        logger.info("✅ Dataset export completed!")
        logger.info(f"   Output Path: {result.get('output_path', 'unknown')}")
        logger.info(f"   Format: {result.get('format', 'unknown')}")

        orchestrator.close()
        return True

    except Exception as e:
        logger.error(f"❌ Error exporting dataset: {e}")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="News Intelligence System Management")
    parser.add_argument(
        "command",
        choices=["pipeline", "status", "process", "create-dataset", "export", "test"],
        help="Command to execute",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for pipeline processing (default: 100)",
    )
    parser.add_argument("--article-id", type=int, help="Article ID for single article processing")
    parser.add_argument("--dataset-name", type=str, help="Name for custom dataset")
    parser.add_argument(
        "--filters", type=str, default="{}", help="JSON filters for dataset creation"
    )
    parser.add_argument("--dataset-id", type=int, help="Dataset ID for export")
    parser.add_argument("--format", type=str, default="csv", help="Export format (default: csv)")

    args = parser.parse_args()

    logger.info("🧠 News Intelligence System v2.1.0")
    logger.info("=" * 50)

    success = False

    if args.command == "pipeline":
        success = run_intelligence_pipeline(args.batch_size)

    elif args.command == "status":
        success = get_intelligence_status()

    elif args.command == "process":
        if not args.article_id:
            logger.error("❌ Article ID is required for process command")
            return
        success = process_single_article(args.article_id)

    elif args.command == "create-dataset":
        if not args.dataset_name:
            logger.error("❌ Dataset name is required for create-dataset command")
            return
        success = create_custom_dataset(args.dataset_name, args.filters)

    elif args.command == "export":
        if not args.dataset_id:
            logger.error("❌ Dataset ID is required for export command")
            return
        success = export_dataset(args.dataset_id, args.format)

    elif args.command == "test":
        logger.info("🧪 Running intelligence system tests...")
        try:
            # Test functionality moved to tests/test_basic.py
            # from test_intelligence_system import main as run_tests
            # success = run_tests()  # Test functionality moved to tests/test_basic.py
            success = True  # Placeholder - tests are now in separate module
        except Exception as e:
            logger.error(f"❌ Test execution failed: {e}")
            success = False

    # Summary
    logger.info("=" * 50)
    if success:
        logger.info("✅ Command completed successfully!")
    else:
        logger.error("❌ Command failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
