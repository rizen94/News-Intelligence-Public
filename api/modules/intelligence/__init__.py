"""
News Intelligence System v2.5 - Intelligence Module
Transforms raw articles into ML-ready processed data with enhanced intelligence
"""

from .article_processor import ArticleProcessor
from .content_clusterer import ContentClusterer
from .ml_data_preparer import MLDataPreparer
from .intelligence_orchestrator import IntelligenceOrchestrator
from .enhanced_entity_extractor import EnhancedEntityExtractor, EventCandidate
from .article_deduplicator import ArticleDeduplicator
from .content_cleaner import ContentCleaner
from .language_detector import LanguageDetector
from .quality_validator import QualityValidator
from .article_stager import ArticleStager
from .data_preparation_pipeline import DataPreparationPipeline

__all__ = [
    'ArticleProcessor',
    'ContentClusterer', 
    'MLDataPreparer',
    'IntelligenceOrchestrator',
    'EnhancedEntityExtractor',
    'EventCandidate',
    'ArticleDeduplicator',
    'ContentCleaner',
    'LanguageDetector',
    'QualityValidator',
    'ArticleStager',
    'DataPreparationPipeline'
]

__version__ = '2.5.0'
__description__ = 'Enhanced intelligence processing pipeline with language detection, quality validation, content cleaning, and staging for ML-ready data preparation'
