
# V4 API Compatibility Layer
# This module provides compatibility between legacy API calls and v4 schema

def get_articles_v4_compatibility():
    """Compatibility function for articles API"""
    # Maps legacy article fields to v4 fields
    field_mapping = {
        'published_date': 'published_at',
        'source': 'source_domain',
        'feed_id': 'feed_id',
        'content_hash': 'content_hash',
        'processing_status': 'processing_status'
    }
    return field_mapping

def get_storylines_v4_compatibility():
    """Compatibility function for storylines API"""
    field_mapping = {
        'created_date': 'created_at',
        'updated_date': 'updated_at',
        'status': 'status'
    }
    return field_mapping

def get_rss_feeds_v4_compatibility():
    """Compatibility function for RSS feeds API"""
    field_mapping = {
        'feed_name': 'feed_name',
        'feed_url': 'feed_url',
        'is_active': 'is_active',
        'last_fetch': 'last_fetched_at'
    }
    return field_mapping
