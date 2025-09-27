#!/usr/bin/env python3
"""
RSS Feed Automation Manager
Comprehensive automation system for RSS collection, ML processing, and pipeline tracking
"""

import os
import sys
import time
import logging
import asyncio
import schedule
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from api.modules.ml.summarization_service import MLSummarizationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/rss_automation.log')
    ]
)
logger = logging.getLogger(__name__)

class RSSAutomationManager:
    """Comprehensive RSS automation and pipeline tracking system"""
    
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.ml_service = MLSummarizationService()
        self.running = False
        self.stats = {
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'total_articles_collected': 0,
            'total_articles_processed': 0,
            'start_time': None,
            'last_collection': None,
            'next_collection': None,
            'feed_stats': {}
        }
        
        # Collection schedule
        self.collection_intervals = {
            'politics_feeds': 15,  # Every 15 minutes for politics
            'general_feeds': 30,  # Every 30 minutes for general news
            'tech_feeds': 60     # Every hour for tech news
        }
        
        # Feed categories
        self.feed_categories = {
            'politics_feeds': [2, 3, 4, 5, 6],  # Fox, CNN, MSNBC, BBC, Reuters
            'tech_feeds': [1],                   # Hacker News
            'general_feeds': []
        }
    
    def start_automation(self):
        """Start the automated RSS collection system"""
        if self.running:
            logger.warning("RSS automation is already running")
            return
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # Schedule different collection intervals for different feed types
        schedule.every(self.collection_intervals['politics_feeds']).minutes.do(
            self._collect_politics_feeds
        )
        schedule.every(self.collection_intervals['tech_feeds']).minutes.do(
            self._collect_tech_feeds
        )
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Schedule first collection
        self.stats['next_collection'] = datetime.now() + timedelta(
            minutes=self.collection_intervals['politics_feeds']
        )
        
        logger.info("🚀 RSS Automation Manager started")
        logger.info(f"📰 Politics feeds: Every {self.collection_intervals['politics_feeds']} minutes")
        logger.info(f"💻 Tech feeds: Every {self.collection_intervals['tech_feeds']} minutes")
    
    def stop_automation(self):
        """Stop the automated RSS collection system"""
        self.running = False
        schedule.clear()
        logger.info("🛑 RSS Automation Manager stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)
    
    def _collect_politics_feeds(self):
        """Collect articles from politics feeds"""
        logger.info("🗳️ Collecting politics feeds...")
        self._collect_feeds_by_category('politics_feeds')
    
    def _collect_tech_feeds(self):
        """Collect articles from tech feeds"""
        logger.info("💻 Collecting tech feeds...")
        self._collect_feeds_by_category('tech_feeds')
    
    def _collect_feeds_by_category(self, category: str):
        """Collect articles from feeds in a specific category"""
        try:
            feed_ids = self.feed_categories[category]
            if not feed_ids:
                logger.info(f"No feeds configured for category: {category}")
                return
            
            total_articles = 0
            successful_feeds = 0
            
            for feed_id in feed_ids:
                try:
                    articles = self._collect_single_feed(feed_id)
                    if articles > 0:
                        total_articles += articles
                        successful_feeds += 1
                        logger.info(f"✅ Feed {feed_id}: {articles} articles collected")
                    else:
                        logger.info(f"ℹ️ Feed {feed_id}: No new articles")
                        
                except Exception as e:
                    logger.error(f"❌ Error collecting feed {feed_id}: {e}")
            
            # Update statistics
            self.stats['total_cycles'] += 1
            self.stats['last_collection'] = datetime.now()
            self.stats['total_articles_collected'] += total_articles
            
            if successful_feeds > 0:
                self.stats['successful_cycles'] += 1
                logger.info(f"📊 {category}: {total_articles} articles from {successful_feeds} feeds")
                
                # Trigger ML processing if articles were collected
                if total_articles > 0:
                    self._trigger_ml_processing()
            else:
                self.stats['failed_cycles'] += 1
                logger.warning(f"⚠️ {category}: No articles collected")
                
        except Exception as e:
            logger.error(f"❌ Error in {category} collection: {e}")
            self.stats['failed_cycles'] += 1
    
    def _collect_single_feed(self, feed_id: int) -> int:
        """Collect articles from a single RSS feed"""
        try:
            # Refresh the RSS feed
            response = requests.post(f"{self.api_base_url}/api/rss/feeds/{feed_id}/refresh")
            
            if response.status_code == 200:
                result = response.json()
                articles_fetched = result.get('data', {}).get('articles_fetched', 0)
                
                # Update feed stats
                if feed_id not in self.stats['feed_stats']:
                    self.stats['feed_stats'][feed_id] = {
                        'total_collections': 0,
                        'total_articles': 0,
                        'last_collection': None
                    }
                
                self.stats['feed_stats'][feed_id]['total_collections'] += 1
                self.stats['feed_stats'][feed_id]['total_articles'] += articles_fetched
                self.stats['feed_stats'][feed_id]['last_collection'] = datetime.now()
                
                return articles_fetched
            else:
                logger.error(f"Failed to refresh feed {feed_id}: {response.status_code}")
                return 0
                
        except Exception as e:
            logger.error(f"Error collecting feed {feed_id}: {e}")
            return 0
    
    def _trigger_ml_processing(self):
        """Trigger ML processing for newly collected articles"""
        try:
            logger.info("🤖 Triggering ML processing...")
            
            # Get recent articles that need ML processing
            response = requests.get(f"{self.api_base_url}/api/articles/?limit=10&order_by=created_at&order=desc")
            
            if response.status_code == 200:
                articles_data = response.json()
                articles = articles_data.get('data', {}).get('articles', [])
                
                if articles:
                    # Process articles through ML pipeline
                    processed_count = 0
                    
                    for article in articles[:5]:  # Process up to 5 recent articles
                        try:
                            # Generate summary using ML service
                            summary_result = self.ml_service.generate_summary(
                                article.get('content', ''),
                                article.get('title', '')
                            )
                            
                            # Extract key points
                            key_points_result = self.ml_service.extract_key_points(
                                article.get('content', ''),
                                article.get('title', '')
                            )
                            
                            # Analyze sentiment
                            sentiment_result = self.ml_service.analyze_sentiment(
                                article.get('content', '')
                            )
                            
                            # Update article with ML results
                            article_id = article.get('id')
                            if article_id:
                                self._update_article_ml_results(
                                    article_id,
                                    summary_result,
                                    key_points_result,
                                    sentiment_result
                                )
                                processed_count += 1
                                
                        except Exception as e:
                            logger.error(f"Error processing article {article.get('id')}: {e}")
                    
                    self.stats['total_articles_processed'] += processed_count
                    logger.info(f"✅ ML processing completed: {processed_count} articles processed")
                else:
                    logger.info("ℹ️ No articles found for ML processing")
            else:
                logger.error(f"Failed to get articles for ML processing: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error triggering ML processing: {e}")
    
    def _update_article_ml_results(self, article_id: int, summary_result: Dict, key_points_result: Dict, sentiment_result: Dict):
        """Update article with ML processing results"""
        try:
            update_data = {
                'summary': summary_result.get('summary', ''),
                'key_points': json.dumps(key_points_result.get('key_points', [])),
                'sentiment_score': sentiment_result.get('sentiment', 'neutral'),
                'ml_processed': True,
                'ml_processed_at': datetime.now().isoformat()
            }
            
            response = requests.put(f"{self.api_base_url}/api/articles/{article_id}", json=update_data)
            
            if response.status_code == 200:
                logger.debug(f"Updated article {article_id} with ML results")
            else:
                logger.error(f"Failed to update article {article_id}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
    
    def collect_all_feeds_now(self) -> Dict[str, Any]:
        """Manually trigger collection of all feeds"""
        logger.info("🔄 Manual collection of all feeds triggered")
        
        total_articles = 0
        results = {}
        
        for category, feed_ids in self.feed_categories.items():
            if feed_ids:
                logger.info(f"Collecting {category}...")
                category_articles = 0
                
                for feed_id in feed_ids:
                    articles = self._collect_single_feed(feed_id)
                    category_articles += articles
                
                results[category] = {
                    'feeds': feed_ids,
                    'articles_collected': category_articles
                }
                total_articles += category_articles
        
        # Trigger ML processing if articles were collected
        if total_articles > 0:
            self._trigger_ml_processing()
        
        results['total_articles'] = total_articles
        results['timestamp'] = datetime.now().isoformat()
        
        logger.info(f"📊 Manual collection completed: {total_articles} total articles")
        return results
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        try:
            # Get RSS feed status
            rss_response = requests.get(f"{self.api_base_url}/api/rss/feeds/")
            rss_data = rss_response.json() if rss_response.status_code == 200 else {}
            
            # Get article statistics
            articles_response = requests.get(f"{self.api_base_url}/api/articles/?limit=100")
            articles_data = articles_response.json() if articles_response.status_code == 200 else {}
            
            # Get storyline statistics
            storylines_response = requests.get(f"{self.api_base_url}/api/storylines/")
            storylines_data = storylines_response.json() if storylines_response.status_code == 200 else {}
            
            # Calculate uptime
            uptime = None
            if self.stats['start_time']:
                uptime = str(datetime.now() - self.stats['start_time'])
            
            return {
                'automation': {
                    'running': self.running,
                    'uptime': uptime,
                    'statistics': self.stats,
                    'next_collection': self.stats['next_collection'].isoformat() if self.stats['next_collection'] else None
                },
                'rss_feeds': {
                    'total_feeds': len(rss_data.get('data', {}).get('feeds', [])),
                    'active_feeds': len([f for f in rss_data.get('data', {}).get('feeds', []) if f.get('is_active', True)]),
                    'feeds': rss_data.get('data', {}).get('feeds', [])
                },
                'articles': {
                    'total_articles': len(articles_data.get('data', {}).get('articles', [])),
                    'recent_articles': articles_data.get('data', {}).get('articles', [])[:5]
                },
                'storylines': {
                    'total_storylines': len(storylines_data.get('data', {}).get('storylines', [])),
                    'storylines': storylines_data.get('data', {}).get('storylines', [])
                },
                'ml_service': {
                    'status': self.ml_service.get_service_status(),
                    'fallback_mode': self.ml_service.fallback_mode
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return {'error': str(e)}
    
    def get_collection_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get collection history and statistics"""
        try:
            # Get articles from the last N hours
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            response = requests.get(f"{self.api_base_url}/api/articles/?limit=1000")
            if response.status_code != 200:
                return {'error': 'Failed to get articles'}
            
            articles_data = response.json()
            articles = articles_data.get('data', {}).get('articles', [])
            
            # Filter articles by time
            recent_articles = []
            for article in articles:
                created_at = article.get('created_at')
                if created_at:
                    try:
                        article_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        if article_time >= cutoff_time:
                            recent_articles.append(article)
                    except:
                        continue
            
            # Group by source
            source_stats = {}
            for article in recent_articles:
                source = article.get('source', 'Unknown')
                if source not in source_stats:
                    source_stats[source] = 0
                source_stats[source] += 1
            
            # Group by hour
            hourly_stats = {}
            for article in recent_articles:
                created_at = article.get('created_at')
                if created_at:
                    try:
                        article_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        hour_key = article_time.strftime('%Y-%m-%d %H:00')
                        if hour_key not in hourly_stats:
                            hourly_stats[hour_key] = 0
                        hourly_stats[hour_key] += 1
                    except:
                        continue
            
            return {
                'period_hours': hours,
                'total_articles': len(recent_articles),
                'source_distribution': source_stats,
                'hourly_distribution': hourly_stats,
                'collection_stats': self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting collection history: {e}")
            return {'error': str(e)}

def main():
    """Main entry point for RSS automation"""
    manager = RSSAutomationManager()
    
    try:
        # Start automation
        manager.start_automation()
        
        # Keep running
        logger.info("🔄 RSS Automation Manager is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping RSS Automation Manager...")
        manager.stop_automation()
    except Exception as e:
        logger.error(f"❌ RSS Automation Manager error: {e}")
        manager.stop_automation()

if __name__ == "__main__":
    main()
