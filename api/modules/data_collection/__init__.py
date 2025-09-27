# Data Collection Module for News Intelligence System
# This module provides data collection capabilities including RSS feeds,
# web scraping, and other data sources.

from modules.rss_feed_service import RSSFeedService, RSSFeed, Article
from modules.feed_scheduler import FeedScheduler

__all__ = [
    'RSSFeedService',
    'RSSFeed', 
    'Article',
    'FeedScheduler'
]
