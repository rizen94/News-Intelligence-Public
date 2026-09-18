#!/usr/bin/env python3
"""
Enhanced RSS Feed Collector for News Intelligence System v2.0.0
Collects articles from RSS feeds and extracts full content from URLs.
"""

import logging
import signal
import time
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Use shared connection (run with api as cwd or PYTHONPATH=api)
def _get_connection():
    from shared.database.connection import get_db_connection

    return get_db_connection()


def clean_content_preserve_paragraphs(content: str) -> str:
    """
    Clean content while preserving paragraph structure
    Args:
        content: Raw content string
    Returns:
        Cleaned content with preserved paragraph breaks
    """
    if not content:
        return ""

    # Split into lines and clean each line
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        # Clean the line but preserve structure
        cleaned_line = " ".join(line.split())  # Remove extra whitespace within line
        if cleaned_line.strip():  # Only keep non-empty lines
            cleaned_lines.append(cleaned_line.strip())

    # Join lines, preserving paragraph breaks
    # Use double newlines to separate paragraphs
    content = "\n\n".join(cleaned_lines)

    # Clean up excessive whitespace while preserving structure
    content = content.replace("\n\n\n", "\n\n")  # Remove triple newlines
    content = content.replace("  ", " ")  # Remove double spaces

    return content


def get_db_connection():
    """Get database connection from shared pool (raises if DB unreachable)."""
    return _get_connection()


def extract_article_content(url: str, timeout: int = 10) -> str:
    """
    Extract full article content from URL
    Args:
        url: Article URL
        timeout: Request timeout in seconds
    Returns:
        Extracted content or empty string
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Try to find main content areas
        content_selectors = [
            "article",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            ".main-content",
        ]

        content = ""
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = " ".join([elem.get_text(strip=True) for elem in elements])
                break

        # If no main content found, get body text
        if not content:
            content = soup.get_text(strip=True)

        # Clean up content while preserving paragraph breaks
        content = clean_content_preserve_paragraphs(content)

        return content[:10000]  # Limit content length

    except Exception as e:
        logger.warning(f"Error extracting content from {url}: {e}")
        return ""


def collect_enhanced_rss() -> int:
    """
    Collect articles from RSS feeds with enhanced content extraction
    Returns: Number of articles added/updated
    """
    logger.info("Starting enhanced RSS collection...")

    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return 0

    try:
        cur = conn.cursor()

        # Get all active RSS feeds
        cur.execute("""
            SELECT id, name, url, category
            FROM rss_feeds
            WHERE is_active = true
        """)
        feeds = cur.fetchall()

        total_articles_processed = 0

        for feed_id, feed_name, feed_url, feed_category in feeds:
            logger.info(f"Processing enhanced feed: {feed_name} ({feed_url})")

            try:
                # Set timeout for RSS parsing
                def timeout_handler(signum, frame):
                    raise TimeoutError("RSS parsing timeout")

                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout

                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                signal.alarm(0)  # Cancel timeout

                articles_processed = 0

                for entry in feed.entries:
                    try:
                        title = entry.get("title", "")[:500]
                        url = entry.get("link", "")[:500]
                        summary = entry.get("summary", "") or entry.get("description", "")

                        # Parse published date
                        published_at = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            published_at = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                            published_at = datetime(*entry.updated_parsed[:6])
                        else:
                            published_at = datetime.now()

                        # Check if article already exists
                        cur.execute(
                            """
                            SELECT id, content FROM articles WHERE url = %s
                        """,
                            (url,),
                        )

                        existing = cur.fetchone()

                        if existing:
                            article_id, existing_content = existing

                            # Update content if it's empty or summary only
                            if not existing_content or len(existing_content) < 100:
                                enhanced_content = extract_article_content(url)
                                if enhanced_content:
                                    cur.execute(
                                        """
                                        UPDATE articles
                                        SET content = %s, updated_at = NOW()
                                        WHERE id = %s
                                    """,
                                        (enhanced_content, article_id),
                                    )
                                    articles_processed += 1
                                    logger.debug(f"Enhanced content for existing article: {title}")
                        else:
                            # Insert new article with enhanced content
                            enhanced_content = extract_article_content(url)
                            if not enhanced_content:
                                enhanced_content = summary

                            cur.execute(
                                """
                                INSERT INTO articles
                                (title, url, content, published_at, created_at)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (url) DO NOTHING
                            """,
                                (title, url, enhanced_content, published_at, datetime.now()),
                            )

                            if cur.rowcount > 0:
                                articles_processed += 1
                                logger.debug(f"Added new article with enhanced content: {title}")

                        # Small delay to be respectful to servers
                        time.sleep(0.1)

                    except Exception as e:
                        logger.warning(f"Error processing article from {feed_name}: {e}")
                        continue

                # Update last fetched timestamp
                cur.execute(
                    """
                    UPDATE rss_feeds
                    SET last_fetched = NOW()
                    WHERE id = %s
                """,
                    (feed_id,),
                )

                total_articles_processed += articles_processed
                logger.info(f"Processed {articles_processed} articles from {feed_name}")

            except TimeoutError:
                logger.error(f"Timeout processing enhanced feed: {feed_name}")
                continue
            except Exception as e:
                logger.error(f"Error processing enhanced feed {feed_name}: {e}")
                continue

        conn.commit()
        logger.info(
            f"Enhanced RSS collection completed. Total articles processed: {total_articles_processed}"
        )
        return total_articles_processed

    except Exception as e:
        logger.error(f"Error during enhanced RSS collection: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()


def enhance_existing_articles(limit: int = 100) -> int:
    """
    Deprecated: content fetching merged into content_enrichment (trafilatura, domain schemas).
    Use the content_enrichment automation phase or article_content_enrichment_service.enrich_articles_batch().
    """
    logger.warning("enhance_existing_articles is deprecated (use content_enrichment); returning 0")
    return 0


if __name__ == "__main__":
    # Test enhanced RSS collection
    print("Testing enhanced RSS collection...")
    result = collect_enhanced_rss()
    print(f"Enhanced collection completed. Articles processed: {result}")

    # Test article enhancement
    print("Testing article enhancement...")
    enhanced = enhance_existing_articles(5)
    print(f"Article enhancement completed. Articles enhanced: {enhanced}")
