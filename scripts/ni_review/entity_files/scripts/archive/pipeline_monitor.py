#!/usr/bin/env python3
"""
Pipeline Monitor
Real-time monitoring dashboard for RSS collection and ML processing pipeline
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import requests

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PipelineMonitor:
    """Real-time pipeline monitoring and status reporting"""
    
    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.monitoring_data = {}
        self.start_time = datetime.now()
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            # Check API health
            health_response = requests.get(f"{self.api_base_url}/api/health/", timeout=5)
            api_healthy = health_response.status_code == 200
            
            # Check database connectivity
            articles_response = requests.get(f"{self.api_base_url}/api/articles/?limit=1", timeout=5)
            db_healthy = articles_response.status_code == 200
            
            # Check RSS feeds
            rss_response = requests.get(f"{self.api_base_url}/api/rss/feeds/", timeout=5)
            rss_healthy = rss_response.status_code == 200
            
            return {
                'overall_status': 'healthy' if all([api_healthy, db_healthy, rss_healthy]) else 'degraded',
                'api_status': 'healthy' if api_healthy else 'unhealthy',
                'database_status': 'healthy' if db_healthy else 'unhealthy',
                'rss_status': 'healthy' if rss_healthy else 'unhealthy',
                'uptime': str(datetime.now() - self.start_time),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {
                'overall_status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline metrics"""
        try:
            # Get articles data
            articles_response = requests.get(f"{self.api_base_url}/api/articles/?limit=100")
            articles_data = articles_response.json() if articles_response.status_code == 200 else {}
            articles = articles_data.get('data', {}).get('articles', [])
            
            # Get RSS feeds data
            rss_response = requests.get(f"{self.api_base_url}/api/rss/feeds/")
            rss_data = rss_response.json() if rss_response.status_code == 200 else {}
            feeds = rss_data.get('data', {}).get('feeds', [])
            
            # Get storylines data
            storylines_response = requests.get(f"{self.api_base_url}/api/storylines/")
            storylines_data = storylines_response.json() if storylines_response.status_code == 200 else {}
            storylines = storylines_data.get('data', {}).get('storylines', [])
            
            # Calculate metrics
            total_articles = len(articles)
            recent_articles = len([a for a in articles if self._is_recent(a.get('created_at'), hours=24)])
            ml_processed = len([a for a in articles if a.get('ml_processed', False)])
            
            # Source distribution
            source_dist = {}
            for article in articles:
                source = article.get('source', 'Unknown')
                source_dist[source] = source_dist.get(source, 0) + 1
            
            # Quality distribution
            quality_dist = {'high': 0, 'medium': 0, 'low': 0}
            for article in articles:
                quality = article.get('quality_score', 0.5)
                if quality >= 0.8:
                    quality_dist['high'] += 1
                elif quality >= 0.5:
                    quality_dist['medium'] += 1
                else:
                    quality_dist['low'] += 1
            
            return {
                'articles': {
                    'total': total_articles,
                    'recent_24h': recent_articles,
                    'ml_processed': ml_processed,
                    'ml_processing_rate': (ml_processed / total_articles * 100) if total_articles > 0 else 0
                },
                'rss_feeds': {
                    'total_feeds': len(feeds),
                    'active_feeds': len([f for f in feeds if f.get('is_active', True)]),
                    'feeds_with_data': len([f for f in feeds if f.get('last_fetched')])
                },
                'storylines': {
                    'total_storylines': len(storylines),
                    'active_storylines': len([s for s in storylines if s.get('article_count', 0) > 0])
                },
                'content_distribution': {
                    'by_source': source_dist,
                    'by_quality': quality_dist
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting pipeline metrics: {e}")
            return {'error': str(e)}
    
    def get_recent_activity(self, hours: int = 6) -> Dict[str, Any]:
        """Get recent pipeline activity"""
        try:
            # Get recent articles
            articles_response = requests.get(f"{self.api_base_url}/api/articles/?limit=50&order_by=created_at&order=desc")
            articles_data = articles_response.json() if articles_response.status_code == 200 else {}
            articles = articles_data.get('data', {}).get('articles', [])
            
            # Filter recent articles
            recent_articles = []
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            for article in articles:
                created_at = article.get('created_at')
                if created_at:
                    try:
                        article_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        if article_time >= cutoff_time:
                            recent_articles.append({
                                'id': article.get('id'),
                                'title': article.get('title', '')[:100] + '...' if len(article.get('title', '')) > 100 else article.get('title', ''),
                                'source': article.get('source'),
                                'created_at': created_at,
                                'ml_processed': article.get('ml_processed', False),
                                'quality_score': article.get('quality_score', 0)
                            })
                    except:
                        continue
            
            # Group by hour
            hourly_activity = {}
            for article in recent_articles:
                try:
                    article_time = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
                    hour_key = article_time.strftime('%Y-%m-%d %H:00')
                    if hour_key not in hourly_activity:
                        hourly_activity[hour_key] = 0
                    hourly_activity[hour_key] += 1
                except:
                    continue
            
            return {
                'period_hours': hours,
                'recent_articles': recent_articles[:10],  # Last 10 articles
                'total_recent': len(recent_articles),
                'hourly_activity': hourly_activity,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            return {'error': str(e)}
    
    def _is_recent(self, timestamp: str, hours: int = 24) -> bool:
        """Check if timestamp is within the last N hours"""
        if not timestamp:
            return False
        
        try:
            article_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            cutoff_time = datetime.now() - timedelta(hours=hours)
            return article_time >= cutoff_time
        except:
            return False
    
    def generate_status_report(self) -> str:
        """Generate a comprehensive status report"""
        try:
            health = self.get_system_health()
            metrics = self.get_pipeline_metrics()
            activity = self.get_recent_activity()
            
            report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        NEWS INTELLIGENCE PIPELINE STATUS                    ║
║                              {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ SYSTEM HEALTH: {health.get('overall_status', 'unknown').upper():<20} UPTIME: {health.get('uptime', 'unknown'):<20} ║
║ API: {health.get('api_status', 'unknown'):<10} DB: {health.get('database_status', 'unknown'):<10} RSS: {health.get('rss_status', 'unknown'):<10} ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ ARTICLES: {metrics.get('articles', {}).get('total', 0):<6} Total | {metrics.get('articles', {}).get('recent_24h', 0):<6} Recent | {metrics.get('articles', {}).get('ml_processed', 0):<6} ML Processed ║
║ RSS FEEDS: {metrics.get('rss_feeds', {}).get('total_feeds', 0):<6} Total | {metrics.get('rss_feeds', {}).get('active_feeds', 0):<6} Active | {metrics.get('rss_feeds', {}).get('feeds_with_data', 0):<6} With Data ║
║ STORYLINES: {metrics.get('storylines', {}).get('total_storylines', 0):<6} Total | {metrics.get('storylines', {}).get('active_storylines', 0):<6} Active ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ RECENT ACTIVITY (Last 6 Hours): {activity.get('total_recent', 0):<6} Articles ║
║ ML Processing Rate: {metrics.get('articles', {}).get('ml_processing_rate', 0):.1f}% ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating status report: {e}")
            return f"Error generating report: {e}"
    
    def monitor_continuously(self, interval_seconds: int = 30):
        """Continuously monitor the pipeline"""
        logger.info("🔍 Starting continuous pipeline monitoring...")
        
        try:
            while True:
                # Clear screen (works on most terminals)
                os.system('clear' if os.name == 'posix' else 'cls')
                
                # Generate and display report
                report = self.generate_status_report()
                print(report)
                
                # Wait for next update
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("🛑 Pipeline monitoring stopped")
        except Exception as e:
            logger.error(f"❌ Pipeline monitoring error: {e}")

def main():
    """Main entry point"""
    monitor = PipelineMonitor()
    
    try:
        # Generate one-time report
        report = monitor.generate_status_report()
        print(report)
        
        # Ask if user wants continuous monitoring
        response = input("\nStart continuous monitoring? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            monitor.monitor_continuously()
        else:
            logger.info("📊 One-time report completed")
            
    except KeyboardInterrupt:
        logger.info("🛑 Pipeline monitor stopped")
    except Exception as e:
        logger.error(f"❌ Pipeline monitor error: {e}")

if __name__ == "__main__":
    main()
