"""
Module Reloader Utility
Provides functions to force reload modules during development
"""

import importlib
import logging
import sys

logger = logging.getLogger(__name__)


def reload_project_modules():
    """Reload all project modules"""
    logger.info("🔄 Reloading project modules...")

    # List of modules to reload
    modules_to_reload = [
        "main_v4",
        "domains.system_monitoring.routes.system_monitoring",
        "domains.news_aggregation.routes.news_aggregation",
        "domains.content_analysis.routes.content_analysis",
        "domains.storyline_management.routes.storyline_management",
        "domains.intelligence_hub.routes.intelligence_hub",
        "domains.user_management.routes.user_management",
        "shared.database.connection",
        "shared.services.llm_service",
        "services.automation_manager",
        "services.ml_processing_service",
    ]

    reloaded_count = 0
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
                logger.info(f"   ✅ Reloaded: {module_name}")
                reloaded_count += 1
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to reload {module_name}: {e}")

    logger.info(f"🔄 Reloaded {reloaded_count} modules")
    return reloaded_count


def clear_module_cache():
    """Clear module cache for project modules"""
    logger.info("🧹 Clearing module cache...")

    modules_to_remove = []
    for module_name in sys.modules:
        if any(path in module_name for path in ["domains", "shared", "services", "main_v4"]):
            modules_to_remove.append(module_name)

    for module_name in modules_to_remove:
        del sys.modules[module_name]
        logger.info(f"   🗑️ Removed: {module_name}")

    logger.info(f"🧹 Cleared {len(modules_to_remove)} modules from cache")


def force_import_reload(module_name):
    """Force reload a specific module"""
    if module_name in sys.modules:
        del sys.modules[module_name]

    try:
        importlib.import_module(module_name)
        logger.info(f"✅ Force reloaded: {module_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to reload {module_name}: {e}")
        return False
