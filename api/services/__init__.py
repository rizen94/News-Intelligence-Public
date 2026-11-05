"""
News Intelligence System v3.0 - Services Package
All service modules for the News Intelligence System
"""

# Import all services for easy access
# Note: api_cache_service consolidated into smart_cache_service
from .advanced_monitoring_service import get_advanced_monitoring_service
from .article_processing_service import ArticleProcessingService
from .automation_manager import get_automation_manager
from .circuit_breaker_service import get_circuit_breaker_service
from .distributed_cache_service import get_distributed_cache_service
from .dynamic_resource_service import get_dynamic_resource_service
from .early_quality_service import get_early_quality_service
from .predictive_scaling_service import get_predictive_scaling_service

# Note: monitoring_service and health_service consolidated into advanced_monitoring_service
from .rag import RAGService
from .smart_cache_service import get_cache_service, get_smart_cache_service

__all__ = [
    "get_automation_manager",
    "get_early_quality_service",
    "get_smart_cache_service",
    "get_dynamic_resource_service",
    "get_circuit_breaker_service",
    "get_predictive_scaling_service",
    "get_distributed_cache_service",
    "get_advanced_monitoring_service",
    "RAGService",
    "ArticleProcessingService",
]
