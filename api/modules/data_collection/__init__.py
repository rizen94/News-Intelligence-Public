# Data Collection Module for News Intelligence System
# This module provides data collection capabilities including RSS feeds,
# web scraping, and other data sources.

from modules.feed_scheduler import FeedScheduler
from modules.rss_feed_service import Article, RSSFeed, RSSFeedService

__all__ = ["RSSFeedService", "RSSFeed", "Article", "FeedScheduler"]
