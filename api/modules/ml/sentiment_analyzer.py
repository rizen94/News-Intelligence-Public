"""
Sentiment Analysis Module for News Intelligence System v3.0
Uses local LLM models via Ollama for reliable sentiment analysis
"""

import logging
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SentimentResult:
    """Structured sentiment analysis result"""
    sentiment_score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    emotions: Dict[str, float]  # Emotion breakdown
    context: str  # Explanation of the sentiment
    model_used: str
    processing_time: float
    local_processing: bool = True

class LocalSentimentAnalyzer:
    """
    Local sentiment analyzer using Ollama models
    No training required - uses pre-trained models with structured prompts
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.available_models = ["llama3.1:8b", "llama3.1:70b"]
        self.default_model = "llama3.1:70b"
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
        
    def analyze_sentiment(self, 
                         text: str, 
                         model: Optional[str] = None,
                         use_cache: bool = True) -> SentimentResult:
        """
        Analyze sentiment of text using local LLM
        
        Args:
            text: Text to analyze
            model: Specific model to use (optional)
            use_cache: Whether to use cached results
            
        Returns:
            SentimentResult with detailed analysis
        """
        try:
            start_time = time.time()
            
            # Check cache first
            if use_cache:
                cache_key = f"{hash(text)}_{model or self.default_model}"
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        logger.info(f"Using cached sentiment result for text: {text[:50]}...")
                        return SentimentResult(**cached_result['data'])
            
            # Select model
            selected_model = model or self.default_model
            if selected_model not in self.available_models:
                logger.warning(f"Model {selected_model} not available, using {self.default_model}")
                selected_model = self.default_model
            
            # Create structured prompt
            prompt = self._create_sentiment_prompt(text)
            
            # Call Ollama
            response = self._call_ollama(prompt, selected_model)
            
            # Parse response
            sentiment_data = self._parse_sentiment_response(response)
            
            # Create result
            processing_time = time.time() - start_time
            result = SentimentResult(
                sentiment_score=sentiment_data['sentiment_score'],
                confidence=sentiment_data['confidence'],
                emotions=sentiment_data['emotions'],
                context=sentiment_data['context'],
                model_used=selected_model,
                processing_time=processing_time
            )
            
            # Cache result
            if use_cache:
                self.cache[cache_key] = {
                    'data': {
                        'sentiment_score': result.sentiment_score,
                        'confidence': result.confidence,
                        'emotions': result.emotions,
                        'context': result.context,
                        'model_used': result.model_used,
                        'processing_time': result.processing_time,
                        'local_processing': result.local_processing
                    },
                    'timestamp': time.time()
                }
            
            logger.info(f"Sentiment analysis completed in {processing_time:.2f}s: {result.sentiment_score:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            # Return neutral result on error
            return SentimentResult(
                sentiment_score=0.0,
                confidence=0.0,
                emotions={'neutral': 1.0},
                context="Error in analysis",
                model_used=selected_model,
                processing_time=time.time() - start_time
            )
    
    def analyze_batch(self, 
                     texts: List[str], 
                     model: Optional[str] = None) -> List[SentimentResult]:
        """
        Analyze sentiment for multiple texts
        
        Args:
            texts: List of texts to analyze
            model: Specific model to use (optional)
            
        Returns:
            List of SentimentResult objects
        """
        results = []
        for i, text in enumerate(texts):
            logger.info(f"Analyzing sentiment {i+1}/{len(texts)}")
            result = self.analyze_sentiment(text, model)
            results.append(result)
        return results
    
    def get_sentiment_trends(self, 
                           articles: List[Dict[str, Any]], 
                           time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Analyze sentiment trends over time
        
        Args:
            articles: List of articles with sentiment data
            time_window_hours: Time window for trend analysis
            
        Returns:
            Dictionary with trend analysis
        """
        try:
            if not articles:
                return {"error": "No articles provided"}
            
            # Filter articles by time window
            cutoff_time = datetime.now().timestamp() - (time_window_hours * 3600)
            recent_articles = [
                article for article in articles 
                if article.get('created_at', 0) > cutoff_time
            ]
            
            if not recent_articles:
                return {"error": "No recent articles found"}
            
            # Calculate trend metrics
            sentiment_scores = [article.get('sentiment_score', 0) for article in recent_articles]
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            
            # Calculate trend direction
            if len(sentiment_scores) >= 2:
                first_half = sentiment_scores[:len(sentiment_scores)//2]
                second_half = sentiment_scores[len(sentiment_scores)//2:]
                trend_direction = "improving" if sum(second_half)/len(second_half) > sum(first_half)/len(first_half) else "declining"
            else:
                trend_direction = "stable"
            
            # Calculate emotion distribution
            emotion_totals = {}
            for article in recent_articles:
                emotions = article.get('emotions', {})
                for emotion, score in emotions.items():
                    emotion_totals[emotion] = emotion_totals.get(emotion, 0) + score
            
            # Normalize emotions
            total_emotion_score = sum(emotion_totals.values())
            emotion_distribution = {
                emotion: score / total_emotion_score if total_emotion_score > 0 else 0
                for emotion, score in emotion_totals.items()
            }
            
            return {
                "time_window_hours": time_window_hours,
                "article_count": len(recent_articles),
                "average_sentiment": round(avg_sentiment, 3),
                "trend_direction": trend_direction,
                "emotion_distribution": emotion_distribution,
                "sentiment_range": {
                    "min": min(sentiment_scores),
                    "max": max(sentiment_scores)
                },
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in sentiment trend analysis: {e}")
            return {"error": str(e)}
    
    def _create_sentiment_prompt(self, text: str) -> str:
        """Create structured prompt for sentiment analysis"""
        return f"""
Analyze the sentiment of the following text and provide a detailed analysis.

Text: "{text}"

Please provide your analysis in the following JSON format:
{{
    "sentiment_score": -0.5,
    "confidence": 0.85,
    "emotions": {{
        "joy": 0.1,
        "anger": 0.3,
        "fear": 0.1,
        "sadness": 0.2,
        "surprise": 0.05,
        "disgust": 0.1,
        "neutral": 0.15
    }},
    "context": "The text expresses frustration and concern about the topic"
}}

Guidelines:
- sentiment_score: -1.0 (very negative) to 1.0 (very positive)
- confidence: 0.0 (low confidence) to 1.0 (high confidence)
- emotions: percentages that add up to 1.0
- context: brief explanation of the sentiment
- Be objective and analytical
- Consider the overall tone and emotional content
"""
    
    def _call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama API for sentiment analysis"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for more consistent analysis
                        "num_predict": 500,
                        "top_p": 0.9
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama API error: {response.status_code}")
            
            # Parse streaming response
            result = ""
            for line in response.text.split('\n'):
                if line.strip():
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            result += data['response']
                    except json.JSONDecodeError:
                        continue
            
            return result
            
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            raise
    
    def _parse_sentiment_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama response and extract sentiment data"""
        try:
            # Try to find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Validate and normalize data
                sentiment_score = max(-1.0, min(1.0, float(data.get('sentiment_score', 0))))
                confidence = max(0.0, min(1.0, float(data.get('confidence', 0.5))))
                
                emotions = data.get('emotions', {})
                # Normalize emotions to sum to 1.0
                emotion_sum = sum(emotions.values())
                if emotion_sum > 0:
                    emotions = {k: v/emotion_sum for k, v in emotions.items()}
                else:
                    emotions = {'neutral': 1.0}
                
                context = data.get('context', 'Analysis completed')
                
                return {
                    'sentiment_score': sentiment_score,
                    'confidence': confidence,
                    'emotions': emotions,
                    'context': context
                }
            else:
                # Fallback parsing if JSON not found
                return self._fallback_parse(response)
                
        except Exception as e:
            logger.error(f"Error parsing sentiment response: {e}")
            return self._fallback_parse(response)
    
    def _fallback_parse(self, response: str) -> Dict[str, Any]:
        """Fallback parsing when JSON parsing fails"""
        # Simple keyword-based fallback
        response_lower = response.lower()
        
        # Determine sentiment based on keywords
        positive_words = ['positive', 'good', 'great', 'excellent', 'happy', 'joy']
        negative_words = ['negative', 'bad', 'terrible', 'angry', 'sad', 'fear']
        
        positive_count = sum(1 for word in positive_words if word in response_lower)
        negative_count = sum(1 for word in negative_words if word in response_lower)
        
        if positive_count > negative_count:
            sentiment_score = 0.3
        elif negative_count > positive_count:
            sentiment_score = -0.3
        else:
            sentiment_score = 0.0
        
        return {
            'sentiment_score': sentiment_score,
            'confidence': 0.5,
            'emotions': {'neutral': 1.0},
            'context': 'Fallback analysis - low confidence'
        }
    
    def clear_cache(self):
        """Clear the sentiment analysis cache"""
        self.cache.clear()
        logger.info("Sentiment analysis cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_ttl": self.cache_ttl,
            "available_models": self.available_models,
            "default_model": self.default_model
        }

# Global instance
sentiment_analyzer = LocalSentimentAnalyzer()


