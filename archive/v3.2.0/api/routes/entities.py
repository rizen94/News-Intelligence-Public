"""
Entity Extraction API Routes for News Intelligence System v3.0
Provides entity extraction endpoints using local LLM models
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from modules.ml.entity_extractor import entity_extractor, EntityExtractionResult
from schemas.response_schemas import create_success_response, create_error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/entities", tags=["entities"])

@router.post("/extract")
async def extract_entities(
    text: str = Body(..., description="Text to analyze for entities"),
    entity_types: Optional[List[str]] = Body(None, description="Specific entity types to extract"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """
    Extract entities from a single text
    
    Args:
        text: Text to analyze
        entity_types: Specific entity types to extract (optional)
        model: Specific model to use (optional)
        use_cache: Whether to use cached results
        
    Returns:
        Entity extraction result
    """
    try:
        if not text or len(text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Text cannot be empty").dict()
            )
        
        # Extract entities
        result = entity_extractor.extract_entities(
            text=text,
            entity_types=entity_types,
            model=model,
            use_cache=use_cache
        )
        
        # Convert entities to dict format
        entities_data = []
        for entity in result.entities:
            entities_data.append({
                "text": entity.text,
                "label": entity.label,
                "confidence": entity.confidence,
                "start_pos": entity.start_pos,
                "end_pos": entity.end_pos,
                "context": entity.context,
                "model_used": entity.model_used,
                "local_processing": entity.local_processing
            })
        
        return create_success_response(
            data={
                "entities": entities_data,
                "text": result.text,
                "model_used": result.model_used,
                "processing_time": result.processing_time,
                "total_entities": result.total_entities,
                "entity_types": result.entity_types,
                "local_processing": result.local_processing
            },
            message="Entity extraction completed successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in entity extraction API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Entity extraction failed: {str(e)}").dict()
        )

@router.post("/extract-batch")
async def extract_entities_batch(
    texts: List[str] = Body(..., description="List of texts to analyze"),
    entity_types: Optional[List[str]] = Body(None, description="Specific entity types to extract"),
    model: Optional[str] = Body(None, description="Specific model to use"),
    use_cache: bool = Body(True, description="Whether to use cached results")
) -> Dict[str, Any]:
    """
    Extract entities from multiple texts
    
    Args:
        texts: List of texts to analyze
        entity_types: Specific entity types to extract (optional)
        model: Specific model to use (optional)
        use_cache: Whether to use cached results
        
    Returns:
        List of entity extraction results
    """
    try:
        if not texts or len(texts) == 0:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Texts list cannot be empty").dict()
            )
        
        if len(texts) > 50:  # Limit batch size
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Batch size cannot exceed 50 texts").dict()
            )
        
        # Extract entities
        results = entity_extractor.extract_entities_batch(
            texts=texts,
            entity_types=entity_types,
            model=model
        )
        
        # Convert results to dict format
        results_data = []
        for i, result in enumerate(results):
            entities_data = []
            for entity in result.entities:
                entities_data.append({
                    "text": entity.text,
                    "label": entity.label,
                    "confidence": entity.confidence,
                    "start_pos": entity.start_pos,
                    "end_pos": entity.end_pos,
                    "context": entity.context,
                    "model_used": entity.model_used,
                    "local_processing": entity.local_processing
                })
            
            results_data.append({
                "text": result.text,
                "entities": entities_data,
                "model_used": result.model_used,
                "processing_time": result.processing_time,
                "total_entities": result.total_entities,
                "entity_types": result.entity_types,
                "local_processing": result.local_processing
            })
        
        return create_success_response(
            data={
                "results": results_data,
                "total_analyzed": len(results),
                "model_used": results[0].model_used if results else None
            },
            message=f"Batch entity extraction completed for {len(results)} texts"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error in batch entity extraction API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Batch entity extraction failed: {str(e)}").dict()
        )

@router.post("/statistics")
async def get_entity_statistics(
    extraction_results: List[Dict[str, Any]] = Body(..., description="List of extraction results")
) -> Dict[str, Any]:
    """
    Get statistics from entity extraction results
    
    Args:
        extraction_results: List of extraction results
        
    Returns:
        Entity statistics
    """
    try:
        if not extraction_results:
            raise HTTPException(
                status_code=400,
                detail=create_error_response("Extraction results list cannot be empty").dict()
            )
        
        # Convert dict results to EntityExtractionResult objects
        results = []
        for result_data in extraction_results:
            entities = []
            for entity_data in result_data.get('entities', []):
                from modules.ml.entity_extractor import Entity
                entity = Entity(
                    text=entity_data.get('text', ''),
                    label=entity_data.get('label', 'UNKNOWN'),
                    confidence=entity_data.get('confidence', 0.0),
                    start_pos=entity_data.get('start_pos', 0),
                    end_pos=entity_data.get('end_pos', 0),
                    context=entity_data.get('context', ''),
                    model_used=entity_data.get('model_used', 'unknown')
                )
                entities.append(entity)
            
            result = EntityExtractionResult(
                entities=entities,
                text=result_data.get('text', ''),
                model_used=result_data.get('model_used', 'unknown'),
                processing_time=result_data.get('processing_time', 0.0),
                total_entities=result_data.get('total_entities', 0),
                entity_types=result_data.get('entity_types', {}),
                local_processing=result_data.get('local_processing', True)
            )
            results.append(result)
        
        # Calculate statistics
        stats = entity_extractor.get_entity_statistics(results)
        
        if "error" in stats:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(stats["error"]).dict()
            )
        
        return create_success_response(
            data=stats,
            message="Entity statistics calculated successfully"
        ).dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in entity statistics API: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Entity statistics calculation failed: {str(e)}").dict()
        )

@router.get("/types")
async def get_entity_types() -> Dict[str, Any]:
    """
    Get available entity types
    
    Returns:
        List of available entity types with descriptions
    """
    try:
        cache_stats = entity_extractor.get_cache_stats()
        
        return create_success_response(
            data={
                "entity_types": entity_extractor.entity_types,
                "available_models": cache_stats["available_models"],
                "default_model": cache_stats["default_model"],
                "cache_size": cache_stats["cache_size"],
                "cache_ttl": cache_stats["cache_ttl"]
            },
            message="Entity types retrieved successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error getting entity types: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to get entity types: {str(e)}").dict()
        )

@router.post("/clear-cache")
async def clear_entity_cache() -> Dict[str, Any]:
    """
    Clear entity extraction cache
    
    Returns:
        Confirmation message
    """
    try:
        entity_extractor.clear_cache()
        
        return create_success_response(
            data={"cache_cleared": True},
            message="Entity extraction cache cleared successfully"
        ).dict()
        
    except Exception as e:
        logger.error(f"Error clearing entity cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=create_error_response(f"Failed to clear cache: {str(e)}").dict()
        )

@router.get("/health")
async def entity_health_check() -> Dict[str, Any]:
    """
    Health check for entity extraction service
    
    Returns:
        Service health status
    """
    try:
        # Test with a simple entity extraction
        test_result = entity_extractor.extract_entities(
            text="Apple Inc. announced new products in California.",
            use_cache=False
        )
        
        return create_success_response(
            data={
                "status": "healthy",
                "model_used": test_result.model_used,
                "processing_time": test_result.processing_time,
                "entities_found": test_result.total_entities,
                "local_processing": test_result.local_processing,
                "timestamp": datetime.now().isoformat()
            },
            message="Entity extraction service is healthy"
        ).dict()
        
    except Exception as e:
        logger.error(f"Entity health check failed: {e}")
        return create_success_response(
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            },
            message="Entity extraction service is unhealthy"
        ).dict()