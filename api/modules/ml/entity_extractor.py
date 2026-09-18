"""
Entity Extraction Module for News Intelligence System v3.0
Uses local LLM models via Ollama for reliable entity extraction
"""

import logging
import json
import time
import re
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_JSON_RETRY_SUFFIX = (
    "\n\nYour previous answer was not valid JSON. "
    'Reply with ONLY a JSON object {"entities": [...]} — no markdown, no commentary.'
)


def _repair_json_object_text(text: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
    if t.endswith("```"):
        t = t.rsplit("```", 1)[0]
    t = t.strip()
    t = re.sub(r",\s*]", "]", t)
    t = re.sub(r",\s*}", "}", t)
    return t


def _extract_entity_dicts_from_text(text: str) -> list[dict[str, Any]]:
    """Salvage entity objects when the outer JSON object fails to parse."""
    out: list[dict[str, Any]] = []
    for chunk in re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL):
        try:
            obj = json.loads(_repair_json_object_text(chunk))
            if isinstance(obj, dict) and (obj.get("text") or obj.get("label")):
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out

@dataclass
class Entity:
    """Structured entity representation"""
    text: str
    label: str  # PERSON, ORGANIZATION, LOCATION, EVENT, etc.
    confidence: float
    start_pos: int
    end_pos: int
    context: str  # Surrounding text
    model_used: str
    local_processing: bool = True

@dataclass
class EntityExtractionResult:
    """Complete entity extraction result"""
    entities: List[Entity]
    text: str
    model_used: str
    processing_time: float
    total_entities: int
    entity_types: Dict[str, int]
    local_processing: bool = True

class LocalEntityExtractor:
    """
    Local entity extractor using Ollama models
    No training required - uses pre-trained models with structured prompts
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.available_models = ["llama3.1:8b", "llama3.1:70b"]
        self.default_model = "llama3.1:8b"  # Fast model (70b available for higher quality)
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Entity type definitions
        self.entity_types = {
            "PERSON": "People, individuals, characters",
            "ORGANIZATION": "Companies, institutions, groups, agencies",
            "LOCATION": "Places, cities, countries, regions",
            "EVENT": "Events, incidents, occurrences",
            "PRODUCT": "Products, services, brands",
            "TECHNOLOGY": "Technologies, software, systems",
            "DATE": "Dates, times, periods",
            "MONEY": "Monetary amounts, currencies",
            "PERCENT": "Percentages, rates",
            "QUANTITY": "Numbers, measurements, counts"
        }
    
    def extract_entities(self, 
                        text: str, 
                        entity_types: Optional[List[str]] = None,
                        model: Optional[str] = None,
                        use_cache: bool = True) -> EntityExtractionResult:
        """
        Extract entities from text using local LLM
        
        Args:
            text: Text to analyze
            entity_types: Specific entity types to extract (optional)
            model: Specific model to use (optional)
            use_cache: Whether to use cached results
            
        Returns:
            EntityExtractionResult with extracted entities
        """
        try:
            start_time = time.time()
            
            # Check cache first
            if use_cache:
                cache_key = f"{hash(text)}_{model or self.default_model}_{str(entity_types)}"
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    if time.time() - cached_result['timestamp'] < self.cache_ttl:
                        logger.info(f"Using cached entity extraction result for text: {text[:50]}...")
                        return EntityExtractionResult(**cached_result['data'])
            
            # Select model
            selected_model = model or self.default_model
            if selected_model not in self.available_models:
                logger.warning(f"Model {selected_model} not available, using {self.default_model}")
                selected_model = self.default_model
            
            # Create structured prompt
            prompt = self._create_entity_prompt(text, entity_types)
            
            # Call Ollama (retry once with JSON-only suffix on parse failure)
            response = self._call_ollama(prompt, selected_model)
            entities_data, json_ok = self._parse_entity_response(response, text, selected_model)
            if not json_ok:
                retry_prompt = prompt + _JSON_RETRY_SUFFIX
                retry_response = self._call_ollama(retry_prompt, selected_model)
                retry_entities, retry_ok = self._parse_entity_response(
                    retry_response, text, selected_model, log_parse_warning=True
                )
                if retry_ok or len(retry_entities) > len(entities_data):
                    entities_data = retry_entities
            
            # Create result
            processing_time = time.time() - start_time
            
            # Count entity types
            entity_type_counts = {}
            for entity in entities_data:
                entity_type_counts[entity.label] = entity_type_counts.get(entity.label, 0) + 1
            
            result = EntityExtractionResult(
                entities=entities_data,
                text=text,
                model_used=selected_model,
                processing_time=processing_time,
                total_entities=len(entities_data),
                entity_types=entity_type_counts
            )
            
            # Cache result
            if use_cache:
                self.cache[cache_key] = {
                    'data': {
                        'entities': [
                            {
                                'text': e.text,
                                'label': e.label,
                                'confidence': e.confidence,
                                'start_pos': e.start_pos,
                                'end_pos': e.end_pos,
                                'context': e.context,
                                'model_used': e.model_used,
                                'local_processing': e.local_processing
                            } for e in entities_data
                        ],
                        'text': text,
                        'model_used': selected_model,
                        'processing_time': processing_time,
                        'total_entities': len(entities_data),
                        'entity_types': entity_type_counts,
                        'local_processing': True
                    },
                    'timestamp': time.time()
                }
            
            logger.info(f"Entity extraction completed in {processing_time:.2f}s: {len(entities_data)} entities found")
            return result
            
        except Exception as e:
            logger.error(f"Error in entity extraction: {e}")
            # Return empty result on error
            return EntityExtractionResult(
                entities=[],
                text=text,
                model_used=selected_model,
                processing_time=time.time() - start_time,
                total_entities=0,
                entity_types={}
            )
    
    def extract_entities_batch(self, 
                              texts: List[str], 
                              entity_types: Optional[List[str]] = None,
                              model: Optional[str] = None) -> List[EntityExtractionResult]:
        """
        Extract entities from multiple texts
        
        Args:
            texts: List of texts to analyze
            entity_types: Specific entity types to extract (optional)
            model: Specific model to use (optional)
            
        Returns:
            List of EntityExtractionResult objects
        """
        results = []
        for i, text in enumerate(texts):
            logger.info(f"Extracting entities {i+1}/{len(texts)}")
            result = self.extract_entities(text, entity_types, model)
            results.append(result)
        return results
    
    def get_entity_statistics(self, 
                            extraction_results: List[EntityExtractionResult]) -> Dict[str, Any]:
        """
        Get statistics from entity extraction results
        
        Args:
            extraction_results: List of extraction results
            
        Returns:
            Dictionary with entity statistics
        """
        try:
            if not extraction_results:
                return {"error": "No extraction results provided"}
            
            # Aggregate statistics
            total_entities = sum(result.total_entities for result in extraction_results)
            total_texts = len(extraction_results)
            
            # Entity type distribution
            entity_type_totals = {}
            confidence_scores = []
            
            for result in extraction_results:
                for entity in result.entities:
                    entity_type_totals[entity.label] = entity_type_totals.get(entity.label, 0) + 1
                    confidence_scores.append(entity.confidence)
            
            # Calculate averages
            avg_entities_per_text = total_entities / total_texts if total_texts > 0 else 0
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            # Most common entity types
            most_common_types = sorted(
                entity_type_totals.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
            
            return {
                "total_texts_analyzed": total_texts,
                "total_entities_found": total_entities,
                "average_entities_per_text": round(avg_entities_per_text, 2),
                "average_confidence": round(avg_confidence, 3),
                "entity_type_distribution": dict(most_common_types),
                "unique_entity_types": len(entity_type_totals),
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating entity statistics: {e}")
            return {"error": str(e)}
    
    def _create_entity_prompt(self, text: str, entity_types: Optional[List[str]] = None) -> str:
        """Create structured prompt for entity extraction"""
        if entity_types is None:
            entity_types = list(self.entity_types.keys())
        
        entity_descriptions = "\n".join([
            f"- {etype}: {desc}" for etype, desc in self.entity_types.items() 
            if etype in entity_types
        ])
        
        return f"""
Extract named entities from the following text and provide detailed information about each entity.

Text: "{text}"

Entity types to extract:
{entity_descriptions}

Please provide your analysis in the following JSON format:
{{
    "entities": [
        {{
            "text": "John Doe",
            "label": "PERSON",
            "confidence": 0.95,
            "start_pos": 0,
            "end_pos": 8,
            "context": "John Doe is a software engineer"
        }},
        {{
            "text": "Apple Inc",
            "label": "ORGANIZATION",
            "confidence": 0.90,
            "start_pos": 15,
            "end_pos": 24,
            "context": "Apple Inc announced new products"
        }}
    ]
}}

Guidelines:
- Extract all relevant entities from the text
- Provide accurate start and end positions
- Include surrounding context (10-20 words)
- Assign appropriate entity types
- Provide confidence scores (0.0 to 1.0)
- Be thorough but accurate
- Only extract entities that are clearly identifiable
"""
    
    def _call_ollama(self, prompt: str, model: str) -> str:
        """Call Ollama API for entity extraction"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "temperature": 0.1,  # Very low temperature for consistent extraction
                        "num_predict": 500,   # Entity list; 500 sufficient, faster
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
    
    def _parse_entity_response(
        self,
        response: str,
        original_text: str,
        model: str | None = None,
        *,
        log_parse_warning: bool = True,
    ) -> tuple[List[Entity], bool]:
        """Parse Ollama response. Second value is True when JSON parsed cleanly."""
        model_used = model or self.default_model
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start != -1 and json_end > json_start:
            json_str = _repair_json_object_text(response[json_start:json_end])
            try:
                data = json.loads(json_str)
                entities = []
                for entity_data in data.get("entities", []):
                    if not isinstance(entity_data, dict):
                        continue
                    entity = Entity(
                        text=entity_data.get("text", ""),
                        label=entity_data.get("label", "UNKNOWN"),
                        confidence=max(
                            0.0, min(1.0, float(entity_data.get("confidence", 0.5)))
                        ),
                        start_pos=int(entity_data.get("start_pos", 0)),
                        end_pos=int(entity_data.get("end_pos", 0)),
                        context=entity_data.get("context", ""),
                        model_used=model_used,
                    )
                    entities.append(entity)
                if isinstance(data, dict) and "entities" in data:
                    return entities, True
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                if log_parse_warning:
                    logger.warning("Error parsing entity response: %s", e)
                salvaged = _extract_entity_dicts_from_text(response)
                if salvaged:
                    return [
                        Entity(
                            text=str(item.get("text") or ""),
                            label=str(item.get("label") or "UNKNOWN"),
                            confidence=max(
                                0.0,
                                min(1.0, float(item.get("confidence", 0.5))),
                            ),
                            start_pos=int(item.get("start_pos", 0)),
                            end_pos=int(item.get("end_pos", 0)),
                            context=str(item.get("context") or ""),
                            model_used=model_used,
                        )
                        for item in salvaged
                        if item.get("text")
                    ], True

        return self._fallback_parse(response, original_text), False
    
    def _fallback_parse(self, response: str, original_text: str) -> List[Entity]:
        """Fallback parsing when JSON parsing fails"""
        entities = []
        
        # Simple regex-based fallback
        # Look for capitalized words that might be entities
        words = original_text.split()
        for i, word in enumerate(words):
            if len(word) > 2 and word[0].isupper():
                # Simple heuristics for entity types
                if word.lower() in ['inc', 'corp', 'ltd', 'llc', 'co']:
                    label = "ORGANIZATION"
                elif word.lower() in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                    label = "DATE"
                elif word.isdigit() or any(char.isdigit() for char in word):
                    label = "QUANTITY"
                else:
                    label = "PERSON"  # Default assumption
                
                entity = Entity(
                    text=word,
                    label=label,
                    confidence=0.5,  # Low confidence for fallback
                    start_pos=original_text.find(word),
                    end_pos=original_text.find(word) + len(word),
                    context=f"...{word}...",
                    model_used=self.default_model
                )
                entities.append(entity)
        
        return entities
    
    def clear_cache(self):
        """Clear the entity extraction cache"""
        self.cache.clear()
        logger.info("Entity extraction cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cache_size": len(self.cache),
            "cache_ttl": self.cache_ttl,
            "available_models": self.available_models,
            "default_model": self.default_model,
            "entity_types": list(self.entity_types.keys())
        }

# Global instance
entity_extractor = LocalEntityExtractor()


