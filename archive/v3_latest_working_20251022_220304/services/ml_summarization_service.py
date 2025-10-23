"""
News Intelligence System v3.0 - ML Summarization Service
Handles AI-powered content summarization using Ollama
"""

import logging
import requests
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MLSummarizationService:
    def __init__(self, ollama_host: str = "localhost", ollama_port: int = 11434):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.model = "llama3.1:70b"
        
    async def summarize_content(self, content: str, max_length: int = 200) -> Dict[str, Any]:
        """Summarize content using Ollama"""
        try:
            prompt = f"""Summarize the following content in {max_length} words or less. Focus on key facts and main points:

{content}

Summary:"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "max_tokens": max_length * 2
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get("response", "").strip()
                
                return {
                    "success": True,
                    "summary": summary,
                    "model": self.model,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {
                    "success": False,
                    "error": f"Ollama API error: {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in content summarization: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text using Ollama"""
        try:
            prompt = f"""Analyze the sentiment of the following text. Respond with only one word: "positive", "negative", or "neutral":

{text}

Sentiment:"""

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "max_tokens": 10
                    }
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                sentiment = result.get("response", "").strip().lower()
                
                # Validate sentiment
                if sentiment not in ["positive", "negative", "neutral"]:
                    sentiment = "neutral"
                
                return {
                    "success": True,
                    "sentiment": sentiment,
                    "model": self.model,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return {
                    "success": False,
                    "error": f"Ollama API error: {response.status_code}",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
