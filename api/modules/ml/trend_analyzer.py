"""
Trend Analysis Module for News Intelligence System v3.0
Uses local LLM models via Ollama for intelligent trend detection and analysis
"""

import logging
import json
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)

@dataclass
class TrendData:
    """Structured trend data point"""
    timestamp: datetime
    value: float
    confidence: float
    metadata: Dict[str, Any]

@dataclass
class TrendPattern:
    """Structured trend pattern"""
    pattern_type: str  # 'rising', 'falling', 'stable', 'volatile', 'cyclical'
    strength: float  # 0.0 to 1.0
    duration_hours: float
    start_time: datetime
    end_time: datetime
    peak_value: float
    valley_value: float
    volatility: float
    description: str

@dataclass
class TrendAnalysis:
    """Complete trend analysis result"""
    trends: List[TrendPattern]
    overall_trend: str
    trend_strength: float
    volatility_score: float
    key_events: List[Dict[str, Any]]
    predictions: List[Dict[str, Any]]
    analysis_period: Dict[str, datetime]
    processing_time: float
    model_used: str
    local_processing: bool = True

class LocalTrendAnalyzer:
    """
    Local trend analyzer using Ollama models
    No training required - uses statistical analysis and LLM insights
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.available_models = ["llama3.1:8b", "llama3.1:70b"]
        self.default_model = "llama3.1:8b"
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 1800  # 30 minutes cache TTL
        
        # Trend detection parameters
        self.MIN_TREND_DURATION = 2  # hours
        self.VOLATILITY_THRESHOLD = 0.3
        self.TREND_STRENGTH_THRESHOLD = 0.5
    
    def analyze_trends(self, 
                      articles: List[Dict[str, Any]], 
                      metric: str = 'sentiment',
                      time_window_hours: int = 24,
                      model: Optional[str] = None,
                      use_cache: bool = True) -> TrendAnalysis:
        """
        Analyze trends in article data
        
        Args:
            articles: List of articles with timestamps and metrics
            metric: Metric to analyze ('sentiment', 'engagement', 'volume', 'quality')
            time_window_hours: Time window for analysis
            model: Specific model to use (optional)
            use_cache: Whether to use cached results
            
        Returns:
            TrendAnalysis with trend patterns and insights
        """
        try:
            start_time = time.time()
            
            if not articles or len(articles) < 3:
                raise ValueError("Need at least 3 articles to analyze trends")
            
            # Check cache first
            if use_cache:
                cache_key = f"{hash(str(articles))}_{metric}_{time_window_hours}_{model or self.default_model}"
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        logger.info(f"Using cached trend analysis for {len(articles)} articles")
                        return TrendAnalysis(**cached_result['data'])
            
            # Select model
            selected_model = model or self.default_model
            if selected_model not in self.available_models:
                logger.warning(f"Model {selected_model} not available, using {self.default_model}")
                selected_model = self.default_model
            
            # Prepare time series data
            time_series = self._prepare_time_series(articles, metric, time_window_hours)
            
            # Detect trend patterns
            trends = self._detect_trend_patterns(time_series)
            
            # Analyze overall trend
            overall_trend, trend_strength = self._analyze_overall_trend(time_series)
            
            # Calculate volatility
            volatility_score = self._calculate_volatility(time_series)
            
            # Identify key events
            key_events = self._identify_key_events(articles, time_series)
            
            # Generate predictions
            predictions = self._generate_predictions(time_series, selected_model)
            
            # Create analysis result
            processing_time = time.time() - start_time
            
            result = TrendAnalysis(
                trends=trends,
                overall_trend=overall_trend,
                trend_strength=trend_strength,
                volatility_score=volatility_score,
                key_events=key_events,
                predictions=predictions,
                analysis_period={
                    'start': time_series[0].timestamp if time_series else datetime.now(),
                    'end': time_series[-1].timestamp if time_series else datetime.now()
                },
                processing_time=processing_time,
                model_used=selected_model
            )
            
            # Cache result
            if use_cache:
                self.cache[cache_key] = {
                    'data': {
                        'trends': [
                            {
                                'pattern_type': trend.pattern_type,
                                'strength': trend.strength,
                                'duration_hours': trend.duration_hours,
                                'start_time': trend.start_time.isoformat(),
                                'end_time': trend.end_time.isoformat(),
                                'peak_value': trend.peak_value,
                                'valley_value': trend.valley_value,
                                'volatility': trend.volatility,
                                'description': trend.description
                            } for trend in trends
                        ],
                        'overall_trend': overall_trend,
                        'trend_strength': trend_strength,
                        'volatility_score': volatility_score,
                        'key_events': key_events,
                        'predictions': predictions,
                        'analysis_period': {
                            'start': result.analysis_period['start'].isoformat(),
                            'end': result.analysis_period['end'].isoformat()
                        },
                        'processing_time': processing_time,
                        'model_used': selected_model,
                        'local_processing': True
                    },
                    'timestamp': time.time()
                }
            
            logger.info(f"Trend analysis completed in {processing_time:.2f}s: {len(trends)} patterns found")
            return result
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            # Return empty result on error
            return TrendAnalysis(
                trends=[],
                overall_trend="unknown",
                trend_strength=0.0,
                volatility_score=0.0,
                key_events=[],
                predictions=[],
                analysis_period={'start': datetime.now(), 'end': datetime.now()},
                processing_time=time.time() - start_time,
                model_used=selected_model
            )
    
    def _prepare_time_series(self, articles: List[Dict[str, Any]], 
                           metric: str, time_window_hours: int) -> List[TrendData]:
        """Prepare time series data from articles"""
        try:
            # Filter articles by time window
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            recent_articles = [
                article for article in articles 
                if self._parse_timestamp(article.get('created_at', 0)) > cutoff_time
            ]
            
            if not recent_articles:
                return []
            
            # Group articles by hour
            hourly_data = defaultdict(list)
            for article in recent_articles:
                timestamp = self._parse_timestamp(article.get('created_at', 0))
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                
                # Extract metric value
                value = self._extract_metric_value(article, metric)
                if value is not None:
                    hourly_data[hour_key].append(value)
            
            # Create time series data points
            time_series = []
            for hour, values in sorted(hourly_data.items()):
                avg_value = np.mean(values)
                confidence = min(1.0, len(values) / 10.0)  # More articles = higher confidence
                
                time_series.append(TrendData(
                    timestamp=hour,
                    value=avg_value,
                    confidence=confidence,
                    metadata={'article_count': len(values)}
                ))
            
            return time_series
            
        except Exception as e:
            logger.error(f"Error preparing time series: {e}")
            return []
    
    def _extract_metric_value(self, article: Dict[str, Any], metric: str) -> Optional[float]:
        """Extract metric value from article"""
        try:
            if metric == 'sentiment':
                return article.get('sentiment_score', 0.0)
            elif metric == 'engagement':
                return article.get('engagement_score', 0.0)
            elif metric == 'volume':
                return 1.0  # Each article counts as 1
            elif metric == 'quality':
                return article.get('quality_score', 0.0)
            else:
                return article.get(metric, 0.0)
        except Exception:
            return None
    
    def _parse_timestamp(self, timestamp) -> datetime:
        """Parse timestamp from various formats"""
        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, datetime):
                return timestamp
            else:
                return datetime.now()
        except Exception:
            return datetime.now()
    
    def _detect_trend_patterns(self, time_series: List[TrendData]) -> List[TrendPattern]:
        """Detect trend patterns in time series data"""
        try:
            if len(time_series) < 3:
                return []
            
            patterns = []
            values = [point.value for point in time_series]
            timestamps = [point.timestamp for point in time_series]
            
            # Detect rising trends
            rising_trends = self._detect_rising_trends(values, timestamps)
            patterns.extend(rising_trends)
            
            # Detect falling trends
            falling_trends = self._detect_falling_trends(values, timestamps)
            patterns.extend(falling_trends)
            
            # Detect volatility patterns
            volatility_patterns = self._detect_volatility_patterns(values, timestamps)
            patterns.extend(volatility_patterns)
            
            # Detect cyclical patterns
            cyclical_patterns = self._detect_cyclical_patterns(values, timestamps)
            patterns.extend(cyclical_patterns)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting trend patterns: {e}")
            return []
    
    def _detect_rising_trends(self, values: List[float], timestamps: List[datetime]) -> List[TrendPattern]:
        """Detect rising trend patterns"""
        patterns = []
        
        try:
            for i in range(len(values) - 2):
                # Check for consistent rise over 3+ points
                if all(values[j] < values[j+1] for j in range(i, min(i+3, len(values)-1))):
                    # Find end of trend
                    end_idx = i + 2
                    while end_idx < len(values) - 1 and values[end_idx] < values[end_idx + 1]:
                        end_idx += 1
                    
                    if end_idx - i >= 2:  # Minimum 3 points
                        duration = (timestamps[end_idx] - timestamps[i]).total_seconds() / 3600
                        if duration >= self.MIN_TREND_DURATION:
                            strength = (values[end_idx] - values[i]) / max(values[i], 0.001)
                            patterns.append(TrendPattern(
                                pattern_type='rising',
                                strength=min(1.0, strength),
                                duration_hours=duration,
                                start_time=timestamps[i],
                                end_time=timestamps[end_idx],
                                peak_value=values[end_idx],
                                valley_value=values[i],
                                volatility=self._calculate_volatility_in_range(values[i:end_idx+1]),
                                description=f"Rising trend: {values[i]:.2f} to {values[end_idx]:.2f}"
                            ))
        except Exception as e:
            logger.error(f"Error detecting rising trends: {e}")
        
        return patterns
    
    def _detect_falling_trends(self, values: List[float], timestamps: List[datetime]) -> List[TrendPattern]:
        """Detect falling trend patterns"""
        patterns = []
        
        try:
            for i in range(len(values) - 2):
                # Check for consistent fall over 3+ points
                if all(values[j] > values[j+1] for j in range(i, min(i+3, len(values)-1))):
                    # Find end of trend
                    end_idx = i + 2
                    while end_idx < len(values) - 1 and values[end_idx] > values[end_idx + 1]:
                        end_idx += 1
                    
                    if end_idx - i >= 2:  # Minimum 3 points
                        duration = (timestamps[end_idx] - timestamps[i]).total_seconds() / 3600
                        if duration >= self.MIN_TREND_DURATION:
                            strength = (values[i] - values[end_idx]) / max(values[i], 0.001)
                            patterns.append(TrendPattern(
                                pattern_type='falling',
                                strength=min(1.0, strength),
                                duration_hours=duration,
                                start_time=timestamps[i],
                                end_time=timestamps[end_idx],
                                peak_value=values[i],
                                valley_value=values[end_idx],
                                volatility=self._calculate_volatility_in_range(values[i:end_idx+1]),
                                description=f"Falling trend: {values[i]:.2f} to {values[end_idx]:.2f}"
                            ))
        except Exception as e:
            logger.error(f"Error detecting falling trends: {e}")
        
        return patterns
    
    def _detect_volatility_patterns(self, values: List[float], timestamps: List[datetime]) -> List[TrendPattern]:
        """Detect high volatility patterns"""
        patterns = []
        
        try:
            for i in range(len(values) - 4):
                # Check for high volatility over 5+ points
                window_values = values[i:i+5]
                volatility = self._calculate_volatility_in_range(window_values)
                
                if volatility > self.VOLATILITY_THRESHOLD:
                    duration = (timestamps[i+4] - timestamps[i]).total_seconds() / 3600
                    patterns.append(TrendPattern(
                        pattern_type='volatile',
                        strength=volatility,
                        duration_hours=duration,
                        start_time=timestamps[i],
                        end_time=timestamps[i+4],
                        peak_value=max(window_values),
                        valley_value=min(window_values),
                        volatility=volatility,
                        description=f"High volatility: {volatility:.2f} over {duration:.1f} hours"
                    ))
        except Exception as e:
            logger.error(f"Error detecting volatility patterns: {e}")
        
        return patterns
    
    def _detect_cyclical_patterns(self, values: List[float], timestamps: List[datetime]) -> List[TrendPattern]:
        """Detect cyclical patterns"""
        patterns = []
        
        try:
            # Simple cyclical detection - look for repeating patterns
            if len(values) >= 6:
                # Check for cycles of 3-6 hours
                for cycle_length in range(3, min(7, len(values) // 2)):
                    if self._is_cyclical(values, cycle_length):
                        duration = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
                        patterns.append(TrendPattern(
                            pattern_type='cyclical',
                            strength=0.7,  # Moderate strength for detected cycles
                            duration_hours=duration,
                            start_time=timestamps[0],
                            end_time=timestamps[-1],
                            peak_value=max(values),
                            valley_value=min(values),
                            volatility=self._calculate_volatility_in_range(values),
                            description=f"Cyclical pattern: {cycle_length}-hour cycle"
                        ))
                        break  # Only detect one cycle type
        except Exception as e:
            logger.error(f"Error detecting cyclical patterns: {e}")
        
        return patterns
    
    def _is_cyclical(self, values: List[float], cycle_length: int) -> bool:
        """Check if values show cyclical pattern"""
        try:
            if len(values) < cycle_length * 2:
                return False
            
            # Compare first cycle with second cycle
            first_cycle = values[:cycle_length]
            second_cycle = values[cycle_length:cycle_length*2]
            
            # Calculate correlation
            correlation = np.corrcoef(first_cycle, second_cycle)[0, 1]
            return not np.isnan(correlation) and correlation > 0.5
            
        except Exception:
            return False
    
    def _analyze_overall_trend(self, time_series: List[TrendData]) -> Tuple[str, float]:
        """Analyze overall trend direction and strength"""
        try:
            if len(time_series) < 2:
                return "stable", 0.0
            
            values = [point.value for point in time_series]
            first_value = values[0]
            last_value = values[-1]
            
            # Calculate trend strength
            if first_value == 0:
                strength = 0.0
            else:
                strength = abs(last_value - first_value) / abs(first_value)
            
            # Determine trend direction
            if last_value > first_value * 1.1:  # 10% increase
                return "rising", min(1.0, strength)
            elif last_value < first_value * 0.9:  # 10% decrease
                return "falling", min(1.0, strength)
            else:
                return "stable", strength
                
        except Exception as e:
            logger.error(f"Error analyzing overall trend: {e}")
            return "stable", 0.0
    
    def _calculate_volatility(self, time_series: List[TrendData]) -> float:
        """Calculate overall volatility score"""
        try:
            if len(time_series) < 2:
                return 0.0
            
            values = [point.value for point in time_series]
            return self._calculate_volatility_in_range(values)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.0
    
    def _calculate_volatility_in_range(self, values: List[float]) -> float:
        """Calculate volatility for a range of values"""
        try:
            if len(values) < 2:
                return 0.0
            
            # Calculate coefficient of variation
            mean_val = np.mean(values)
            std_val = np.std(values)
            
            if mean_val == 0:
                return 0.0
            
            return min(1.0, std_val / abs(mean_val))
            
        except Exception as e:
            logger.error(f"Error calculating volatility in range: {e}")
            return 0.0
    
    def _identify_key_events(self, articles: List[Dict[str, Any]], 
                            time_series: List[TrendData]) -> List[Dict[str, Any]]:
        """Identify key events that might explain trends"""
        try:
            key_events = []
            
            # Find articles with high engagement or unusual metrics
            for article in articles:
                if article.get('engagement_score', 0) > 0.8:
                    key_events.append({
                        'type': 'high_engagement',
                        'timestamp': self._parse_timestamp(article.get('created_at', 0)),
                        'title': article.get('title', 'Unknown'),
                        'description': f"High engagement: {article.get('engagement_score', 0):.2f}"
                    })
                
                if article.get('sentiment_score', 0) > 0.7 or article.get('sentiment_score', 0) < -0.7:
                    key_events.append({
                        'type': 'extreme_sentiment',
                        'timestamp': self._parse_timestamp(article.get('created_at', 0)),
                        'title': article.get('title', 'Unknown'),
                        'description': f"Extreme sentiment: {article.get('sentiment_score', 0):.2f}"
                    })
            
            # Sort by timestamp
            key_events.sort(key=lambda x: x['timestamp'])
            return key_events[:10]  # Return top 10 events
            
        except Exception as e:
            logger.error(f"Error identifying key events: {e}")
            return []
    
    def _generate_predictions(self, time_series: List[TrendData], model: str) -> List[Dict[str, Any]]:
        """Generate trend predictions using LLM"""
        try:
            if len(time_series) < 3:
                return []
            
            # Prepare data for prediction
            recent_values = [point.value for point in time_series[-10:]]  # Last 10 points
            recent_timestamps = [point.timestamp.isoformat() for point in time_series[-10:]]
            
            # Create prediction prompt
            prompt = f"""
Analyze the following time series data and provide predictions for the next 6 hours.

Recent data points:
{json.dumps(list(zip(recent_timestamps, recent_values)), indent=2)}

Please provide your analysis in the following JSON format:
{{
    "predictions": [
        {{
            "time_hours_ahead": 1,
            "predicted_value": 0.65,
            "confidence": 0.8,
            "reasoning": "Based on recent upward trend"
        }},
        {{
            "time_hours_ahead": 3,
            "predicted_value": 0.70,
            "confidence": 0.6,
            "reasoning": "Trend continuation with some uncertainty"
        }},
        {{
            "time_hours_ahead": 6,
            "predicted_value": 0.75,
            "confidence": 0.4,
            "reasoning": "Long-term projection with high uncertainty"
        }}
    ],
    "trend_analysis": "Overall trend analysis and key factors"
}}

Guidelines:
- Provide 3 predictions: 1, 3, and 6 hours ahead
- Confidence should decrease with time horizon
- Be realistic about uncertainty
- Consider recent patterns and volatility
"""
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 500
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = ""
                for line in response.text.split('\n'):
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if 'response' in data:
                                result += data['response']
                        except json.JSONDecodeError:
                            continue
                
                # Parse response
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    data = json.loads(json_str)
                    return data.get('predictions', [])
            
            # Fallback predictions
            return [
                {
                    "time_hours_ahead": 1,
                    "predicted_value": recent_values[-1],
                    "confidence": 0.5,
                    "reasoning": "No change expected"
                },
                {
                    "time_hours_ahead": 3,
                    "predicted_value": recent_values[-1],
                    "confidence": 0.3,
                    "reasoning": "Uncertain trend"
                },
                {
                    "time_hours_ahead": 6,
                    "predicted_value": recent_values[-1],
                    "confidence": 0.1,
                    "reasoning": "High uncertainty"
                }
            ]
            
        except Exception as e:
            logger.error(f"Error generating predictions: {e}")
            return []
    
    def clear_cache(self):
        """Clear the trend analysis cache"""
        self.cache.clear()
        logger.info("Trend analysis cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_ttl": self.cache_ttl,
            "available_models": self.available_models,
            "default_model": self.default_model,
            "min_trend_duration": self.MIN_TREND_DURATION,
            "volatility_threshold": self.VOLATILITY_THRESHOLD
        }

# Global instance
trend_analyzer = LocalTrendAnalyzer()


