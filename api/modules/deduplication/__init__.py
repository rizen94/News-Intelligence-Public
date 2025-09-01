"""
Advanced Deduplication System for News Intelligence
"""

from .content_normalizer import ContentNormalizer
from .deduplication_engine import DeduplicationEngine
from .deduplication_manager import DeduplicationManager

__all__ = [
    'ContentNormalizer',
    'DeduplicationEngine', 
    'DeduplicationManager'
]

__version__ = '3.0.0'
