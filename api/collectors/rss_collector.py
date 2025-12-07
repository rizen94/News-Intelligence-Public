#!/usr/bin/env python3
"""
RSS Feed Collector for News Intelligence System v3.0.0
Collects articles from RSS feeds with advanced deduplication.
Excludes sports, entertainment, and pop culture content.
"""

import os
import logging
import signal
import feedparser
import psycopg2
import re
from datetime import datetime
from typing import Dict, List, Optional

# Import deduplication system
try:
    from modules.deduplication import DeduplicationManager
    DEDUPLICATION_AVAILABLE = True
except ImportError:
    DEDUPLICATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Deduplication system not available - falling back to basic collection")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import configuration from unified API config
try:
    from config.database import get_db_config  # use API's DB config
    DB_CONFIG = get_db_config()
    # Add timeouts/options
    DB_CONFIG.update({
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'
    })
except Exception as e:
    logger.error(f"Failed to load database config: {e}")
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'news_intelligence'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'
    }

def get_db_connection():
    """Get database connection with timeout protection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def is_excluded_content(title: str, content: str, feed_name: str = "", feed_url: str = "") -> bool:
    """
    Check if article should be excluded (sports, entertainment, pop culture)
    
    Args:
        title: Article title
        content: Article content/summary
        feed_name: Name of the RSS feed
        feed_url: URL of the RSS feed
        
    Returns:
        True if article should be excluded, False otherwise
    """
    # Combine all text for checking
    text_to_check = f"{title} {content} {feed_name}".lower()
    
    # Sports keywords (comprehensive list)
    sports_keywords = [
        # General sports terms
        'sport', 'sports', 'athlete', 'athletes', 'athletic', 'athletics',
        'game', 'games', 'match', 'matches', 'team', 'teams', 'player', 'players',
        'coach', 'coaches', 'league', 'leagues', 'championship', 'championships',
        'tournament', 'tournaments', 'playoff', 'playoffs', 'season', 'seasons',
        'score', 'scores', 'scoring', 'win', 'wins', 'won', 'lose', 'lost', 'loss',
        'victory', 'defeat', 'beat', 'beating', 'defeated',
        
        # Specific sports
        'football', 'soccer', 'basketball', 'baseball', 'hockey', 'tennis',
        'golf', 'cricket', 'rugby', 'volleyball', 'swimming', 'track', 'field',
        'boxing', 'mma', 'ufc', 'wrestling', 'cycling', 'racing', 'nascar',
        'formula', 'f1', 'motorsport', 'olympic', 'olympics', 'paralympic',
        'world cup', 'super bowl', 'stanley cup', 'world series', 'final four',
        'nba', 'nfl', 'mlb', 'nhl', 'fifa', 'uefa', 'ncaa',
        
        # Sports-related terms
        'stadium', 'arena', 'field', 'court', 'pitch', 'referee', 'umpire',
        'quarterback', 'pitcher', 'goalkeeper', 'goalie', 'draft', 'trades',
        'recruiting', 'signing', 'contract', 'extension', 'free agency',
        'fantasy football', 'fantasy baseball', 'fantasy basketball',
        'betting', 'odds', 'spread', 'over/under', 'pick em',
        
        # Common sports phrases
        'game-winning', 'game-winning', 'comeback', 'upset', 'blowout',
        'injury report', 'injury update', 'starting lineup', 'depth chart',
        'power rankings', 'mvp', 'all-star', 'hall of fame', 'rookie', 'veteran',
        'trade deadline', 'free agency', 'draft pick', 'prospect', 'recruit'
    ]
    
    # Entertainment keywords
    entertainment_keywords = [
        # General entertainment
        'entertainment', 'celebrity', 'celebrities', 'celebrity news',
        'hollywood', 'tinseltown', 'star', 'stars', 'superstar', 'superstars',
        'red carpet', 'awards show', 'award ceremony', 'oscars', 'grammys',
        'emmys', 'golden globe', 'golden globes', 'tony awards',
        
        # TV/Streaming
        'tv show', 'television show', 'reality tv', 'reality show', 'series finale',
        'season premiere', 'new episode', 'streaming', 'netflix', 'hulu', 'disney+',
        'hbo max', 'prime video', 'peacock', 'paramount+', 'apple tv+',
        'tv ratings', 'viewership', 'nielsen ratings',
        
        # Movies
        'movie', 'movies', 'film', 'films', 'cinema', 'box office', 'opening weekend',
        'sequel', 'prequel', 'remake', 'reboot', 'franchise', 'franchises',
        'oscar', 'oscars', 'academy award', 'best picture', 'best actor', 'best actress',
        'director', 'screenplay', 'cinematography', 'film festival', 'premiere',
        'trailer', 'teaser', 'behind the scenes', 'making of',
        
        # Music (pop culture)
        'music', 'song', 'songs', 'album', 'albums', 'single', 'singles',
        'artist', 'artists', 'singer', 'singers', 'rapper', 'rappers',
        'concert', 'concerts', 'tour', 'tours', 'tour dates', 'live show',
        'grammy', 'grammys', 'billboard', 'hot 100', 'top 40', 'chart',
        'music video', 'mv', 'viral song', 'trending song', 'spotify', 'apple music',
        'itunes', 'soundcloud', 'youtube music',
        
        # Celebrity gossip/personalities
        'gossip', 'rumor', 'rumors', 'scandal', 'scandals', 'affair', 'affairs',
        'dating', 'engaged', 'married', 'divorce', 'breakup', 'break up',
        'paparazzi', 'tabloid', 'tabloids', 'paparazzi photo', 'exclusive',
        'kardashian', 'jenner', 'real housewives', 'bachelor', 'bachelorette',
        'love island', 'too hot to handle', 'dating show',
        
        # Showbiz news
        'showbiz', 'show business', 'tinseltown', 'la la land',
        'casting news', 'audition', 'role', 'part', 'character', 'cast',
        'director', 'producer', 'screenwriter', 'showrunner',
    ]
    
    # Pop culture keywords
    pop_culture_keywords = [
        # Social media influencers
        'influencer', 'influencers', 'tiktok', 'tik tok', 'instagram model',
        'youtube star', 'youtuber', 'youtubers', 'streamer', 'streamers',
        'twitch', 'onlyfans', 'snapchat', 'tiktok star', 'viral video',
        'viral moment', 'trending', 'trending topic', 'meme', 'memes',
        
        # Video games (pop culture)
        'video game', 'video games', 'gaming', 'gamer', 'gamers', 'esports',
        'playstation', 'xbox', 'nintendo', 'switch', 'ps5', 'xbox series',
        'call of duty', 'fortnite', 'minecraft', 'among us', 'fall guys',
        'streaming', 'twitch stream', 'speedrun', 'achievement', 'trophy',
        
        # Comics/Anime/Manga (pop culture)
        'comic', 'comics', 'comic book', 'superhero', 'superheroes', 'supervillain',
        'mcu', 'marvel', 'dc comics', 'batman', 'superman', 'spider-man',
        'anime', 'manga', 'cosplay', 'convention', 'comic con',
        
        # Fandom/Geek culture
        'fandom', 'fan theory', 'fan theories', 'ship', 'shipping', 'fanfiction',
        'convention', 'con', 'expo', 'fandom drama', 'stan', 'stanning',
        'kpop', 'jpop', 'boy band', 'girl group', 'idol', 'idols',
        
        # Fashion/Beauty (pop culture)
        'fashion week', 'red carpet fashion', 'street style', 'trend',
        'vogue', 'cosmopolitan', 'elle', 'harper\'s bazaar', 'style',
        'makeup', 'beauty', 'skincare', 'beauty guru', 'mua',
        
        # Reality TV/Dating Shows
        'bachelor', 'bachelorette', 'love island', 'too hot to handle',
        'married at first sight', 'the challenge', 'survivor', 'amazing race',
        'real housewives', 'keeping up with', 'vanderpump rules',
        '90 day fiance', 'love after lockup', 'real world', 'road rules'
    ]
    
    # Check for exclusion keywords
    all_exclusion_keywords = sports_keywords + entertainment_keywords + pop_culture_keywords
    
    for keyword in all_exclusion_keywords:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text_to_check):
            logger.debug(f"Article excluded (matched keyword '{keyword}'): {title[:60]}...")
            return True
    
    # Additional pattern matching for common phrases
    # Note: We avoid matching "vs" alone as it appears in political/news contexts too
    exclusion_patterns = [
        r'\b\d+\s*-\s*\d+\s*(final|score|points?|goals?)\b',  # "3-2 final" (sports score)
        r'\b(football|basketball|baseball|hockey|soccer|tennis|golf|cricket)\s+(game|match|season|league|team)\b',
        r'\b\w+\s+vs\.?\s+\w+\s+(game|match|final|semifinal|championship)\b',  # "Team vs Team game" (sports-specific)
        r'\b(oscar|grammy|emmy|tony|golden globe)\s+(nomination|winner|nominee|awards?)\b',
        r'\b(album|single|ep)\s+release\b',
        r'\b(tv|television)\s+(show|series|premiere|episode)\b',
        r'\bcelebrity\s+(news|gossip|rumor|scandal)\b',
        r'\b(pop|rock|hip hop|rap|country)\s+(music|song|album|single)\b',
        r'\b(video game|gaming|esports)\s+(news|update|release)\b',
        r'\b(box office|opening weekend|film festival)\b'
    ]
    
    for pattern in exclusion_patterns:
        if re.search(pattern, text_to_check):
            logger.debug(f"Article excluded (matched pattern '{pattern}'): {title[:60]}...")
            return True
    
    return False

def collect_rss_feeds() -> int:
    """
    Collect articles from all active RSS feeds with deduplication
    Returns: Number of articles added
    """
    logger.info("Starting RSS feed collection with deduplication...")
    
    # Initialize deduplication manager if available
    dedup_manager = None
    if DEDUPLICATION_AVAILABLE:
        try:
            dedup_manager = DeduplicationManager(DB_CONFIG)
            logger.info("Deduplication system initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize deduplication system: {e}")
            dedup_manager = None
    
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return 0
    
    try:
        cur = conn.cursor()
        
        # Get all active RSS feeds
        cur.execute("""
            SELECT id, feed_name, feed_url, NULL as category 
            FROM rss_feeds 
            WHERE is_active = true
        """)
        feeds = cur.fetchall()
        
        total_articles_added = 0
        total_duplicates_rejected = 0
        total_excluded = 0
        
        for feed_id, feed_name, feed_url, feed_category in feeds:
            logger.info(f"Processing feed: {feed_name} ({feed_url})")
            
            try:
                # Set timeout for RSS parsing
                def timeout_handler(signum, frame):
                    raise TimeoutError("RSS parsing timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout
                
                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                signal.alarm(0)  # Cancel timeout
                
                articles_added = 0
                
                for entry in feed.entries[:50]:
                    try:
                        # Extract article data
                        title = entry.get('title', '')[:500]  # Limit title length
                        url = entry.get('link', '')[:500]    # Limit URL length
                        content = entry.get('summary', '') or entry.get('description', '')
                        
                        # Filter out sports, entertainment, and pop culture content
                        if is_excluded_content(title, content, feed_name, feed_url):
                            total_excluded += 1
                            logger.debug(f"Skipping excluded article: {title[:60]}...")
                            continue
                        
                        # Parse published date
                        published_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            published_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            published_date = datetime(*entry.updated_parsed[:6])
                        else:
                            published_date = datetime.now()
                        
                        # Check for duplicates before inserting
                        cur.execute("""
                            SELECT id FROM articles 
                            WHERE url = %s OR (title = %s AND source_domain = %s)
                        """, (url, title, feed_name))
                        
                        if cur.fetchone():
                            # Article already exists, skip it
                            total_duplicates_rejected += 1
                            logger.debug(f"Skipping duplicate article: {title[:60]}...")
                            continue
                        
                        # Per-article savepoint to avoid aborting whole transaction
                        cur.execute("SAVEPOINT sp_article")
                        # Insert article (use canonical schema columns)
                        cur.execute("""
                            INSERT INTO articles
                            (title, url, content, summary, published_at, created_at, source_domain)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            title,
                            url,
                            content,
                            None,
                            published_date,
                            datetime.now(),
                            feed_name
                        ))
                        
                        if cur.rowcount > 0:
                            articles_added += 1
                        
                    except Exception as e:
                        logger.warning(f"Error processing article from {feed_name}: {e}")
                        try:
                            cur.execute("ROLLBACK TO SAVEPOINT sp_article")
                        except Exception as e2:
                            logger.warning(f"Failed to rollback to savepoint: {e2}")
                        continue
                
                # Update last fetched timestamp
                cur.execute("""
                    UPDATE rss_feeds 
                    SET last_fetched_at = NOW() 
                    WHERE id = %s
                """, (feed_id,))
                
                total_articles_added += articles_added
                logger.info(f"Added {articles_added} articles from {feed_name}")
                
            except TimeoutError:
                logger.error(f"Timeout processing feed: {feed_name}")
                continue
            except Exception as e:
                logger.error(f"Error processing feed {feed_name}: {e}")
                continue
        
        conn.commit()
        
        # Log final results
        logger.info(f"RSS collection completed:")
        logger.info(f"  Articles added: {total_articles_added}")
        if total_excluded > 0:
            logger.info(f"  Articles excluded (sports/entertainment/pop culture): {total_excluded}")
        if dedup_manager and total_duplicates_rejected > 0:
            logger.info(f"  Duplicates rejected: {total_duplicates_rejected}")
        
        return total_articles_added
        
    except Exception as e:
        logger.error(f"Error during RSS collection: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

def collect_rss_feed(feed_url: str, feed_name: str = "Unknown") -> int:
    """
    Collect articles from a specific RSS feed
    Args:
        feed_url: URL of the RSS feed
        feed_name: Name of the feed for logging
    Returns:
        Number of articles added
    """
    logger.info(f"Collecting from single feed: {feed_name}")
    
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cur = conn.cursor()
        
        # Parse RSS feed with timeout
        def timeout_handler(signum, frame):
            raise TimeoutError("RSS parsing timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)
        
        feed = feedparser.parse(feed_url)
        signal.alarm(0)
        
        articles_added = 0
        
        for entry in feed.entries:
            try:
                title = entry.get('title', '')[:500]
                url = entry.get('link', '')[:500]
                content = entry.get('summary', '') or entry.get('description', '')
                
                # Filter out sports, entertainment, and pop culture content
                if is_excluded_content(title, content, feed_name, feed_url):
                    logger.debug(f"Skipping excluded article: {title[:60]}...")
                    continue
                
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_date = datetime(*entry.updated_parsed[:6])
                else:
                    published_date = datetime.now()
                
                # Check for duplicates before inserting
                cur.execute("""
                    SELECT id FROM articles 
                    WHERE url = %s OR (title = %s AND source_domain = %s)
                """, (url, title, feed_name))
                
                if cur.fetchone():
                    # Article already exists, skip it
                    logger.debug(f"Skipping duplicate article: {title[:60]}...")
                    continue
                
                cur.execute("""
                    INSERT INTO articles
                    (title, url, content, summary, published_at, created_at, source_domain)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    title, url, content, None, published_date, datetime.now(), feed_name
                ))
                
                if cur.rowcount > 0:
                    articles_added += 1
                    
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
                continue
        
        conn.commit()
        logger.info(f"Added {articles_added} articles from {feed_name}")
        return articles_added
        
    except TimeoutError:
        logger.error(f"Timeout processing feed: {feed_name}")
        return 0
    except Exception as e:
        logger.error(f"Error processing feed {feed_name}: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test RSS collection
    print("Testing RSS collection...")
    result = collect_rss_feeds()
    print(f"Collection completed. Articles added: {result}")
