# ML Module for News Intelligence System
# This module provides machine learning capabilities including summarization,
# content analysis, and intelligent processing.

from .background_processor import BackgroundMLProcessor
from .content_analyzer import ContentAnalyzer

# Note: ContentDeduplicationService has been consolidated into AdvancedDeduplicationService
# Use: from modules.deduplication.advanced_deduplication_service import AdvancedDeduplicationService
from .daily_briefing_service import DailyBriefingService
from .quality_scorer import QualityScorer
from .storyline_tracker import StorylineTracker
from .summarization_service import MLSummarizationService

__all__ = [
    "MLSummarizationService",
    "ContentAnalyzer",
    "QualityScorer",
    "StorylineTracker",
    "DailyBriefingService",
    "BackgroundMLProcessor",
]
