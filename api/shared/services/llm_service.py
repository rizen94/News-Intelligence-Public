"""
Shared LLM Service for News Intelligence System v7
Uses Ollama-hosted Llama 3.1 8B (primary) and Mistral 7B (secondary).
v7: Global concurrency limit so async Ollama callers share one cap.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from enum import Enum
import httpx
from datetime import datetime

from config.settings import NARRATIVE_FINISHER_MODEL, OLLAMA_HOST

logger = logging.getLogger(__name__)

# v7: Global cap. Burst (48h catch-up): 6; revert to 5 after
OLLAMA_CONCURRENCY = 6
_ollama_semaphore: Optional[asyncio.Semaphore] = None


def _get_ollama_semaphore() -> asyncio.Semaphore:
    global _ollama_semaphore
    if _ollama_semaphore is None:
        _ollama_semaphore = asyncio.Semaphore(OLLAMA_CONCURRENCY)
    return _ollama_semaphore

class ModelType(str, Enum):
    """Ollama text models. LLAMA_70B tag comes from settings.NARRATIVE_FINISHER_MODEL."""

    LLAMA_8B = "llama3.1:8b"
    MISTRAL_7B = "mistral:7b"
    LLAMA_70B = NARRATIVE_FINISHER_MODEL

class TaskType(Enum):
    """Task types for model selection"""
    REAL_TIME = "real_time"
    BATCH_PROCESSING = "batch_processing"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    QUICK_SUMMARY = "quick_summary"

class LLMService:
    """
    Centralized LLM service using Ollama-hosted models
    Optimized for Llama 3.1 8B (primary) and Mistral 7B (secondary)
    """
    
    def __init__(self, ollama_base_url: Optional[str] = None):
        self.ollama_base_url = (ollama_base_url or OLLAMA_HOST).rstrip("/")
        self.client = httpx.AsyncClient(timeout=180.0)  # Increased timeout to 180s for comprehensive analysis
        self.model_performance = {
            ModelType.LLAMA_8B: {
                "speed": 2.93,  # seconds for 200 words
                "quality": 73.0,  # MMLU score
                "memory": 5.0,  # GB VRAM
                "best_for": ["comprehensive_analysis", "real_time", "quick_summary"]
            },
            ModelType.MISTRAL_7B: {
                "speed": 4.17,  # seconds for 200 words
                "quality": "very_good",  # competitive benchmarks
                "memory": 4.4,  # GB VRAM
                "best_for": ["batch_processing", "alternative_analysis"]
            }
        }
    
    def select_model(
        self,
        task_type: TaskType,
        urgency: str = "standard",
        approx_prompt_chars: int = 0,
    ) -> ModelType:
        """
        Model selection via shared policy (ollama_model_policy).
        approx_prompt_chars: large background prompts may route to secondary (Mistral).
        """
        from shared.services.ollama_model_policy import resolve_model_for_llm_task

        return resolve_model_for_llm_task(task_type, urgency, approx_prompt_chars)
    
    async def generate_summary(self, content: str, task_type: TaskType = TaskType.QUICK_SUMMARY) -> Dict[str, Any]:
        """
        Generate article summary using appropriate model
        """
        model = self.select_model(task_type, approx_prompt_chars=len(content or ""))

        prompt = f"""
        Write a professional, journalistic summary of the following news article. 
        Focus on the key facts, main points, and important context. 
        Keep it concise but comprehensive. Write in a clear, objective tone.

        Article content:
        {content[:2000]}  # Limit content to avoid token limits
        """
        
        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()
            
            processing_time = (end_time - start_time).total_seconds()
            
            return {
                "success": True,
                "summary": response,
                "model_used": model.value,
                "processing_time": processing_time,
                "task_type": task_type.value,
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.value,
                "task_type": task_type.value
            }
    
    async def analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """
        Analyze sentiment using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B
        
        prompt = f"""
        Analyze the sentiment of this news article. Provide:
        1. Overall sentiment (positive, negative, neutral)
        2. Confidence score (0-100)
        3. Key emotional indicators
        4. Political bias indicators (if any)
        
        Article:
        {content[:1500]}
        
        Respond in JSON format:
        {{
            "overall_sentiment": "positive/negative/neutral",
            "confidence": 85,
            "emotional_indicators": ["optimistic", "concerned"],
            "political_bias": "none/minimal/moderate/strong",
            "reasoning": "brief explanation"
        }}
        """
        
        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()
            
            # Try to parse JSON response
            try:
                sentiment_data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                sentiment_data = {
                    "overall_sentiment": "neutral",
                    "confidence": 50,
                    "emotional_indicators": ["unclear"],
                    "political_bias": "none",
                    "reasoning": "Could not parse structured response",
                    "raw_response": response
                }
            
            return {
                "success": True,
                "sentiment": sentiment_data,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.value
            }
    
    async def extract_entities(self, content: str) -> Dict[str, Any]:
        """
        Extract named entities using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B
        
        prompt = f"""
        Extract named entities from this news article. Identify:
        1. People (PERSON)
        2. Organizations (ORG)
        3. Locations (LOC)
        4. Events (EVENT)
        5. Dates (DATE)
        
        Article:
        {content[:1500]}
        
        Respond in JSON format:
        {{
            "people": ["Name1", "Name2"],
            "organizations": ["Org1", "Org2"],
            "locations": ["City1", "Country1"],
            "events": ["Event1", "Event2"],
            "dates": ["2024-01-01", "January 2024"],
            "relationships": [
                {{"entity1": "Name1", "entity2": "Org1", "relation": "works_for"}}
            ]
        }}
        """
        
        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()
            
            # Try to parse JSON response
            try:
                entities_data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                entities_data = {
                    "people": [],
                    "organizations": [],
                    "locations": [],
                    "events": [],
                    "dates": [],
                    "relationships": [],
                    "raw_response": response
                }
            
            return {
                "success": True,
                "entities": entities_data,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.value
            }
    
    async def generate_storyline_analysis(self, storyline_context: str) -> Dict[str, Any]:
        """
        Generate comprehensive storyline analysis using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B
        
        prompt = f"""
        Analyze this storyline and provide a comprehensive report:
        1. Main narrative thread
        2. Key developments
        3. Timeline of events
        4. Stakeholders involved
        5. Potential future developments
        6. Quality assessment
        
        Storyline context:
        {storyline_context}
        
        Write a professional, journalistic analysis that would be suitable for publication.
        """
        
        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()
            
            return {
                "success": True,
                "analysis": response,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating storyline analysis: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.value
            }
    
    async def generate_briefing_lead(self, context: str, domain: str = "") -> Dict[str, Any]:
        """
        Generate a short editorial lead paragraph for a daily briefing from headline/storyline context.
        Uses a direct prompt (no article-summary wrapper). Returns {"success", "summary" or "error"}.
        """
        if not (context or "").strip():
            return {"success": False, "error": "Empty context"}
        domain_instruction = ""
        if domain:
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config
                cfg = get_domain_synthesis_config(domain)
                if cfg.llm_context:
                    domain_instruction = f" {cfg.llm_context}"
            except ImportError:
                domain_instruction = f" Domain: {domain}."
        prompt = (
            "You are writing the lead paragraph for a daily news briefing."
            + domain_instruction
            + " Focus on developments from the last 24 hours. Prefer items marked [recent] or [recent activity]; mention older storylines only briefly if they are still the main focus. Based only on the following headlines and storylines, write 2–3 short sentences that tell the reader what matters most today. Be factual and concise. No preamble.\n\n"
            + context[:2500]
        )
        try:
            model = self.select_model(TaskType.QUICK_SUMMARY, approx_prompt_chars=len(context or ""))
            response = await self._call_ollama(model, prompt)
            return {"success": True, "summary": (response or "").strip()}
        except Exception as e:
            logger.debug("generate_briefing_lead failed: %s", e)
            return {"success": False, "error": str(e)}

    async def _call_ollama(self, model: ModelType, prompt: str) -> str:
        """Make API call to Ollama with circuit breaker protection. v7: acquires global semaphore."""
        sem = _get_ollama_semaphore()
        async with sem:
            return await self._call_ollama_impl(model, prompt)

    async def _call_ollama_impl(self, model: ModelType, prompt: str) -> str:
        """Inner Ollama call (no semaphore)."""
        from services.circuit_breaker_service import get_circuit_breaker_service, CircuitBreakerOpenException
        cb_service = get_circuit_breaker_service()
        cb = cb_service.get_circuit_breaker("ollama")

        if cb.state.value == "open":
            raise Exception("Ollama circuit breaker is OPEN — skipping call to avoid cascading timeouts")

        try:
            response = await self.client.post(
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": model.value,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": 2000,
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                await cb._record_success()
                return result.get("response", "")
            else:
                await cb._record_failure()
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")

        except httpx.TimeoutException:
            await cb._record_failure()
            raise Exception("Ollama request timed out")
        except httpx.ConnectError:
            await cb._record_failure()
            raise Exception("Cannot connect to Ollama service")
        except Exception as e:
            if "circuit breaker" not in str(e).lower():
                await cb._record_failure()
            raise Exception(f"Ollama API error: {str(e)}")
    
    async def get_model_status(self, timeout_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Get status of available models.
        Use timeout_seconds (e.g. 1.0) for health checks to avoid blocking when Ollama is busy.
        """
        try:
            if timeout_seconds is not None:
                response = await asyncio.wait_for(
                    self.client.get(f"{self.ollama_base_url}/api/tags"),
                    timeout=timeout_seconds
                )
            else:
                response = await self.client.get(f"{self.ollama_base_url}/api/tags")
            
            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [model["name"] for model in models]
                
                finisher = ModelType.LLAMA_70B.value
                return {
                    "success": True,
                    "available_models": available_models,
                    "primary_model": ModelType.LLAMA_8B.value,
                    "secondary_model": ModelType.MISTRAL_7B.value,
                    "narrative_finisher_model": finisher,
                    "primary_available": ModelType.LLAMA_8B.value in available_models,
                    "secondary_available": ModelType.MISTRAL_7B.value in available_models,
                    "narrative_finisher_available": finisher in available_models,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": f"Ollama API error: {response.status_code}"
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Ollama busy (timeout) — web requests take priority",
                "primary_available": None,
                "secondary_available": None,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Cannot connect to Ollama: {str(e)}"
            }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global LLM service instance
llm_service = LLMService()
