"""Ingestion modules package for News Intelligence System v2.0.0"""

# Conditional imports to handle dependency issues gracefully
try:
    from .article_pruner import ArticlePruner
except ImportError:
    ArticlePruner = None

# Future modules (for v2.1+)
try:
    from .data_cleaner import DataCleaner
except ImportError:
    DataCleaner = None

try:
    from .entity_extractor import EntityExtractor
except ImportError:
    EntityExtractor = None

try:
    from .cluster_summarizer import ClusterSummarizer
except ImportError:
    ClusterSummarizer = None

try:
    from .story_tracker import StoryTracker
except ImportError:
    StoryTracker = None

try:
    from .story_researcher import StoryResearcher
except ImportError:
    StoryResearcher = None

try:
    from .story_manager import StoryManager
except ImportError:
    StoryManager = None

try:
    from .news_ingestion import NewsIngestion
except ImportError:
    NewsIngestion = None

try:
    from .article_clustering import ArticleClusterer
except ImportError:
    ArticleClusterer = None

# Export available modules
__all__ = [
    'ArticlePruner',
    'DataCleaner',
    'EntityExtractor', 
    'ClusterSummarizer',
    'StoryTracker',
    'StoryResearcher',
    'StoryManager',
    'NewsIngestion',
    'ArticleClusterer'
]
