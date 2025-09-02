"""
GDELT API Integration for RAG Enhancement
Provides additional context and timeline data for news articles
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time

logger = logging.getLogger(__name__)

class GDELTRAGService:
    """Service for integrating GDELT API data into RAG context"""
    
    def __init__(self):
        self.base_url = "https://api.gdeltproject.org/api/v2"
        self.timeout = 30
        self.rate_limit_delay = 1  # seconds between requests
        
    def get_event_timeline(self, query: str, days_back: int = 7) -> Dict[str, Any]:
        """
        Get GDELT event timeline for a query
        
        Args:
            query: Search query (keywords, entities, etc.)
            days_back: Number of days to look back
            
        Returns:
            Dict containing timeline data and events
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Format dates for GDELT API
            start_str = start_date.strftime("%Y%m%d%H%M%S")
            end_str = end_date.strftime("%Y%m%d%H%M%S")
            
            # Build GDELT query
            gdelt_query = f"{query} STARTDATE:{start_str} ENDDATE:{end_str}"
            
            # Make request to GDELT API
            url = f"{self.base_url}/doc/doc"
            params = {
                "query": gdelt_query,
                "mode": "artlist",
                "maxrecords": 100,
                "format": "json"
            }
            
            logger.info(f"Fetching GDELT timeline for query: {query}")
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            
            data = response.json()
            
            # Process and structure the data
            timeline_data = {
                "query": query,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "total_events": len(data.get("articles", [])),
                "events": self._process_gdelt_events(data.get("articles", [])),
                "summary": self._generate_timeline_summary(data.get("articles", [])),
                "sources": self._extract_sources(data.get("articles", [])),
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved {timeline_data['total_events']} GDELT events for query: {query}")
            return timeline_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GDELT API request failed: {e}")
            return {"error": f"GDELT API request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Error processing GDELT timeline: {e}")
            return {"error": f"Error processing GDELT timeline: {str(e)}"}
    
    def get_entity_context(self, entity: str, entity_type: str = "person") -> Dict[str, Any]:
        """
        Get GDELT context for a specific entity
        
        Args:
            entity: Entity name (person, organization, location, etc.)
            entity_type: Type of entity (person, org, location, theme)
            
        Returns:
            Dict containing entity context and related events
        """
        try:
            # Build entity-specific query
            if entity_type == "person":
                query = f"person:{entity}"
            elif entity_type == "org":
                query = f"org:{entity}"
            elif entity_type == "location":
                query = f"location:{entity}"
            else:
                query = entity
            
            # Get timeline data
            timeline_data = self.get_event_timeline(query, days_back=14)
            
            if "error" in timeline_data:
                return timeline_data
            
            # Enhance with entity-specific analysis
            entity_context = {
                "entity": entity,
                "entity_type": entity_type,
                "timeline": timeline_data,
                "mentions": self._count_entity_mentions(timeline_data["events"], entity),
                "related_entities": self._extract_related_entities(timeline_data["events"]),
                "sentiment_analysis": self._analyze_entity_sentiment(timeline_data["events"]),
                "geographic_analysis": self._analyze_geographic_distribution(timeline_data["events"]),
                "timestamp": datetime.now().isoformat()
            }
            
            return entity_context
            
        except Exception as e:
            logger.error(f"Error getting entity context for {entity}: {e}")
            return {"error": f"Error getting entity context: {str(e)}"}
    
    def get_background_context(self, keywords: List[str], article_date: str = None) -> Dict[str, Any]:
        """
        Get background context for an article using GDELT data
        
        Args:
            keywords: List of keywords from the article
            article_date: Publication date of the article
            
        Returns:
            Dict containing background context and historical events
        """
        try:
            # Combine keywords into query
            query = " ".join(keywords[:5])  # Use top 5 keywords
            
            # Get timeline data (30 days back for background context)
            timeline_data = self.get_event_timeline(query, days_back=30)
            
            if "error" in timeline_data:
                return timeline_data
            
            # Analyze the timeline for background context
            background_context = {
                "article_keywords": keywords,
                "article_date": article_date,
                "historical_timeline": timeline_data,
                "key_events": self._identify_key_events(timeline_data["events"]),
                "trend_analysis": self._analyze_trends(timeline_data["events"]),
                "context_summary": self._generate_background_summary(timeline_data),
                "related_stories": self._identify_related_stories(timeline_data["events"]),
                "timestamp": datetime.now().isoformat()
            }
            
            return background_context
            
        except Exception as e:
            logger.error(f"Error getting background context: {e}")
            return {"error": f"Error getting background context: {str(e)}"}
    
    def _process_gdelt_events(self, articles: List[Dict]) -> List[Dict]:
        """Process raw GDELT articles into structured events"""
        processed_events = []
        
        for article in articles:
            try:
                event = {
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "source": article.get("domain", ""),
                    "published_date": article.get("seendate", ""),
                    "language": article.get("language", "en"),
                    "country": article.get("country", ""),
                    "tone": article.get("tone", 0),
                    "word_count": article.get("wordcount", 0),
                    "relevance_score": article.get("relevance", 0),
                    "entities": article.get("entities", []),
                    "themes": article.get("themes", [])
                }
                processed_events.append(event)
            except Exception as e:
                logger.warning(f"Error processing GDELT article: {e}")
                continue
        
        return processed_events
    
    def _generate_timeline_summary(self, events: List[Dict]) -> Dict[str, Any]:
        """Generate a summary of the timeline events"""
        if not events:
            return {"summary": "No events found", "key_points": []}
        
        # Count events by date
        date_counts = {}
        for event in events:
            date = event.get("published_date", "")[:8]  # YYYYMMDD
            if date:
                date_counts[date] = date_counts.get(date, 0) + 1
        
        # Get top themes
        all_themes = []
        for event in events:
            all_themes.extend(event.get("themes", []))
        
        theme_counts = {}
        for theme in all_themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
        
        top_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_events": len(events),
            "date_range": {
                "start": min(date_counts.keys()) if date_counts else "",
                "end": max(date_counts.keys()) if date_counts else ""
            },
            "peak_date": max(date_counts.items(), key=lambda x: x[1])[0] if date_counts else "",
            "top_themes": [{"theme": theme, "count": count} for theme, count in top_themes],
            "average_tone": sum(event.get("tone", 0) for event in events) / len(events) if events else 0
        }
    
    def _extract_sources(self, events: List[Dict]) -> List[Dict]:
        """Extract and analyze source information"""
        source_counts = {}
        for event in events:
            source = event.get("source", "")
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
        
        return [{"source": source, "count": count} for source, count in source_counts.items()]
    
    def _count_entity_mentions(self, events: List[Dict], entity: str) -> int:
        """Count mentions of a specific entity across events"""
        mentions = 0
        for event in events:
            entities = event.get("entities", [])
            if entity.lower() in [e.lower() for e in entities]:
                mentions += 1
        return mentions
    
    def _extract_related_entities(self, events: List[Dict]) -> List[str]:
        """Extract related entities from events"""
        all_entities = []
        for event in events:
            all_entities.extend(event.get("entities", []))
        
        # Count entity frequency
        entity_counts = {}
        for entity in all_entities:
            entity_counts[entity] = entity_counts.get(entity, 0) + 1
        
        # Return top entities
        return [entity for entity, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    def _analyze_entity_sentiment(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze sentiment for entity mentions"""
        sentiments = [event.get("tone", 0) for event in events if event.get("tone")]
        
        if not sentiments:
            return {"average": 0, "positive": 0, "negative": 0, "neutral": 0}
        
        avg_sentiment = sum(sentiments) / len(sentiments)
        positive = len([s for s in sentiments if s > 0])
        negative = len([s for s in sentiments if s < 0])
        neutral = len([s for s in sentiments if s == 0])
        
        return {
            "average": avg_sentiment,
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "total": len(sentiments)
        }
    
    def _analyze_geographic_distribution(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze geographic distribution of events"""
        countries = {}
        for event in events:
            country = event.get("country", "")
            if country:
                countries[country] = countries.get(country, 0) + 1
        
        return {
            "countries": [{"country": country, "count": count} for country, count in countries.items()],
            "total_countries": len(countries)
        }
    
    def _identify_key_events(self, events: List[Dict]) -> List[Dict]:
        """Identify key events based on relevance and tone"""
        # Sort by relevance score and tone magnitude
        key_events = sorted(events, key=lambda x: (x.get("relevance_score", 0), abs(x.get("tone", 0))), reverse=True)
        return key_events[:5]  # Top 5 key events
    
    def _analyze_trends(self, events: List[Dict]) -> Dict[str, Any]:
        """Analyze trends in the timeline"""
        if not events:
            return {"trend": "stable", "description": "No events to analyze"}
        
        # Group events by date
        daily_events = {}
        for event in events:
            date = event.get("published_date", "")[:8]
            if date:
                if date not in daily_events:
                    daily_events[date] = []
                daily_events[date].append(event)
        
        # Analyze trend
        dates = sorted(daily_events.keys())
        if len(dates) < 2:
            return {"trend": "stable", "description": "Insufficient data for trend analysis"}
        
        # Calculate trend
        early_count = len(daily_events[dates[0]])
        late_count = len(daily_events[dates[-1]])
        
        if late_count > early_count * 1.5:
            trend = "increasing"
        elif late_count < early_count * 0.5:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "description": f"Event frequency is {trend}",
            "early_period": early_count,
            "late_period": late_count,
            "change_percentage": ((late_count - early_count) / early_count * 100) if early_count > 0 else 0
        }
    
    def _generate_background_summary(self, timeline_data: Dict[str, Any]) -> str:
        """Generate a background summary from timeline data"""
        summary = timeline_data.get("summary", {})
        total_events = summary.get("total_events", 0)
        top_themes = summary.get("top_themes", [])
        
        if total_events == 0:
            return "No relevant background events found."
        
        theme_list = ", ".join([theme["theme"] for theme in top_themes[:3]])
        return f"Found {total_events} related events over the past 30 days. Key themes include: {theme_list}."
    
    def _identify_related_stories(self, events: List[Dict]) -> List[Dict]:
        """Identify related stories from the timeline"""
        # Sort by relevance and return top stories
        related_stories = sorted(events, key=lambda x: x.get("relevance_score", 0), reverse=True)
        return related_stories[:10]  # Top 10 related stories
