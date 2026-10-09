"""
News Intelligence System v3.0 - ML Summarization Service
Handles AI-powered content summarization using Ollama via CB hub.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class MLSummarizationService:
    def __init__(self, ollama_host: str = "localhost", ollama_port: int = 11434):
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.model = "llama3.1:8b"

    async def summarize_content(self, content: str, max_length: int = 200) -> dict[str, Any]:
        """Summarize content using Ollama via CB hub."""
        try:
            from shared.services.llm_service import ollama_generate_async

            prompt = f"""Summarize the following content in {max_length} words or less. Focus on key facts and main points:

{content}

Summary:"""

            summary = (
                await ollama_generate_async(
                    prompt,
                    model=self.model,
                    max_tokens=max_length * 2,
                    ollama_base_url=self.base_url,
                )
            ).strip()

            if summary:
                return {
                    "success": True,
                    "summary": summary,
                    "model": self.model,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            return {
                "success": False,
                "error": "Ollama returned empty summary",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in content summarization: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def analyze_sentiment(self, text: str) -> dict[str, Any]:
        """Analyze sentiment of text using Ollama via CB hub."""
        try:
            from shared.services.llm_service import ollama_generate_async

            prompt = f"""Analyze the sentiment of the following text. Respond with only one word: "positive", "negative", or "neutral":

{text}

Sentiment:"""

            sentiment = (
                await ollama_generate_async(
                    prompt,
                    model=self.model,
                    max_tokens=10,
                    ollama_base_url=self.base_url,
                )
            ).strip().lower()

            if sentiment not in ["positive", "negative", "neutral"]:
                sentiment = "neutral"

            return {
                "success": True,
                "sentiment": sentiment,
                "model": self.model,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.utcnow().isoformat()}
