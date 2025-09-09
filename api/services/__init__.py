"""
News Intelligence System v3.0 - Services Package
All service modules for the News Intelligence System
"""

# Import all services for easy access
from .automation_manager import get_automation_manager
from .early_quality_service import get_early_quality_service
from .smart_cache_service import get_smart_cache_service
from .dynamic_resource_service import get_dynamic_resource_service
from .circuit_breaker_service import get_circuit_breaker_service
from .predictive_scaling_service import get_predictive_scaling_service
from .distributed_cache_service import get_distributed_cache_service
from .advanced_monitoring_service import get_advanced_monitoring_service
from .monitoring_service import get_monitoring_service
from .rag_service import RAGService
from .article_processing_service import ArticleProcessingService

__all__ = [
    'get_automation_manager',
    'get_early_quality_service', 
    'get_smart_cache_service',
    'get_dynamic_resource_service',
    'get_circuit_breaker_service',
    'get_predictive_scaling_service',
    'get_distributed_cache_service',
    'get_advanced_monitoring_service',
    'get_monitoring_service',
    'RAGService',
    'ArticleProcessingService'
]


