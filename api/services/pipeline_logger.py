"""
Pipeline Logger Service for News Intelligence System v3.0
Comprehensive logging and tracking for RSS feeds and articles through the entire pipeline
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import traceback

from config.database import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

class PipelineStage(Enum):
    """Pipeline stages for tracking"""
    RSS_FEED_DISCOVERY = "rss_feed_discovery"
    RSS_FEED_FETCH = "rss_feed_fetch"
    ARTICLE_EXTRACTION = "article_extraction"
    CONTENT_VALIDATION = "content_validation"
    DEDUPLICATION = "deduplication"
    EARLY_QUALITY_GATE = "early_quality_gate"
    ML_SUMMARIZATION = "ml_summarization"
    STORY_CLASSIFICATION = "story_classification"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    ENTITY_EXTRACTION = "entity_extraction"
    RAG_ENHANCEMENT = "rag_enhancement"
    MULTI_PERSPECTIVE_ANALYSIS = "multi_perspective_analysis"
    EXPERT_ANALYSIS = "expert_analysis"
    IMPACT_ASSESSMENT = "impact_assessment"
    HISTORICAL_CONTEXT = "historical_context"
    PREDICTIVE_ANALYSIS = "predictive_analysis"
    STORYLINE_CREATION = "storyline_creation"
    TIMELINE_GENERATION = "timeline_generation"
    COMPREHENSIVE_SUMMARY = "comprehensive_summary"
    DATABASE_STORAGE = "database_storage"
    CACHE_UPDATE = "cache_update"
    NOTIFICATION = "notification"

class LogLevel(Enum):
    """Log levels for pipeline tracking"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class PipelineCheckpoint:
    """Individual checkpoint in the pipeline"""
    checkpoint_id: str
    stage: PipelineStage
    article_id: Optional[str]
    storyline_id: Optional[str]
    rss_feed_id: Optional[str]
    timestamp: datetime
    duration_ms: float
    status: str  # "started", "completed", "failed", "skipped"
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    error_message: Optional[str]
    metadata: Dict[str, Any]

@dataclass
class PipelineTrace:
    """Complete pipeline trace for an article or RSS feed"""
    trace_id: str
    rss_feed_id: Optional[str]
    article_id: Optional[str]
    storyline_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_ms: float
    checkpoints: List[PipelineCheckpoint]
    success: bool
    error_stage: Optional[PipelineStage]
    performance_metrics: Dict[str, Any]

class PipelineLogger:
    """
    Comprehensive pipeline logger for tracking RSS feeds and articles through the entire system
    """
    
    def __init__(self, db_connection=None):
        """
        Initialize the pipeline logger
        
        Args:
            db_connection: Database connection for persistent logging
        """
        self.db_connection = db_connection
        self.active_traces = {}  # In-memory trace tracking
        self.performance_metrics = {}
        
        # Configure logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup comprehensive logging configuration"""
        # Create pipeline-specific logger
        self.pipeline_logger = logging.getLogger('pipeline')
        self.pipeline_logger.setLevel(logging.DEBUG)
        
        # Try to create file handler for pipeline logs, fallback to console if permission denied
        try:
            pipeline_handler = logging.FileHandler('logs/pipeline_trace.log')
            pipeline_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
            )
            pipeline_handler.setFormatter(formatter)
            
            # Add handler to pipeline logger
            if not self.pipeline_logger.handlers:
                self.pipeline_logger.addHandler(pipeline_handler)
        except (PermissionError, OSError) as e:
            # Fallback to console logging if file logging fails
            logger.warning(f"Could not create pipeline log file: {e}. Using console logging instead.")
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
            )
            console_handler.setFormatter(formatter)
            if not self.pipeline_logger.handlers:
                self.pipeline_logger.addHandler(console_handler)
    
    def start_trace(self, rss_feed_id: Optional[str] = None, 
                   article_id: Optional[str] = None,
                   storyline_id: Optional[str] = None) -> str:
        """
        Start a new pipeline trace
        
        Args:
            rss_feed_id: ID of the RSS feed being processed
            article_id: ID of the article being processed
            storyline_id: ID of the storyline being processed
            
        Returns:
            trace_id: Unique identifier for this trace
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        trace = PipelineTrace(
            trace_id=trace_id,
            rss_feed_id=rss_feed_id,
            article_id=article_id,
            storyline_id=storyline_id,
            start_time=start_time,
            end_time=None,
            total_duration_ms=0.0,
            checkpoints=[],
            success=False,
            error_stage=None,
            performance_metrics={}
        )
        
        self.active_traces[trace_id] = trace
        
        self.pipeline_logger.info(f"🚀 Starting pipeline trace {trace_id} for RSS:{rss_feed_id}, Article:{article_id}, Storyline:{storyline_id}")
        
        return trace_id
    
    def add_checkpoint(self, trace_id: str, stage: PipelineStage, 
                      status: str, input_data: Dict[str, Any] = None,
                      output_data: Dict[str, Any] = None, 
                      error_message: str = None,
                      metadata: Dict[str, Any] = None) -> str:
        """
        Add a checkpoint to a pipeline trace
        
        Args:
            trace_id: ID of the trace
            stage: Pipeline stage
            status: Checkpoint status
            input_data: Input data for this stage
            output_data: Output data from this stage
            error_message: Error message if failed
            metadata: Additional metadata
            
        Returns:
            checkpoint_id: Unique identifier for this checkpoint
        """
        if trace_id not in self.active_traces:
            self.pipeline_logger.warning(f"Trace {trace_id} not found in active traces - may have been completed")
            return None
        
        trace = self.active_traces[trace_id]
        
        # Check if trace is already completed
        if trace.end_time is not None:
            self.pipeline_logger.warning(f"Attempted to add checkpoint to completed trace {trace_id}")
            return None
            
        checkpoint_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Calculate duration from last checkpoint
        duration_ms = 0.0
        if trace.checkpoints:
            last_checkpoint = trace.checkpoints[-1]
            duration_ms = (timestamp - last_checkpoint.timestamp).total_seconds() * 1000
        
        checkpoint = PipelineCheckpoint(
            checkpoint_id=checkpoint_id,
            stage=stage,
            article_id=trace.article_id,
            storyline_id=trace.storyline_id,
            rss_feed_id=trace.rss_feed_id,
            timestamp=timestamp,
            duration_ms=duration_ms,
            status=status,
            input_data=input_data or {},
            output_data=output_data or {},
            error_message=error_message,
            metadata=metadata or {}
        )
        
        trace.checkpoints.append(checkpoint)
        
        # Log checkpoint
        log_level = self._get_log_level(status)
        self.pipeline_logger.log(
            log_level,
            f"📍 Checkpoint {checkpoint_id} - Stage: {stage.value} - Status: {status} - Duration: {duration_ms:.2f}ms"
        )
        
        if error_message:
            self.pipeline_logger.error(f"❌ Error in {stage.value}: {error_message}")
        
        return checkpoint_id
    
    def end_trace(self, trace_id: str, success: bool = True, 
                  error_stage: PipelineStage = None) -> PipelineTrace:
        """
        End a pipeline trace
        
        Args:
            trace_id: ID of the trace
            success: Whether the trace completed successfully
            error_stage: Stage where error occurred if failed
            
        Returns:
            Completed trace object
        """
        if trace_id not in self.active_traces:
            self.pipeline_logger.warning(f"Trace {trace_id} not found in active traces - may have been completed")
            return None
        
        trace = self.active_traces[trace_id]
        trace.end_time = datetime.now(timezone.utc)
        trace.total_duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
        trace.success = success
        trace.error_stage = error_stage
        
        # Calculate performance metrics
        trace.performance_metrics = self._calculate_performance_metrics(trace)
        
        # Log completion
        status_emoji = "✅" if success else "❌"
        self.pipeline_logger.info(
            f"{status_emoji} Completed pipeline trace {trace_id} - Duration: {trace.total_duration_ms:.2f}ms - Success: {success}"
        )
        
        # Store trace in database
        asyncio.create_task(self._store_trace(trace))
        
        # Remove from active traces
        del self.active_traces[trace_id]
        
        return trace
    
    def _get_log_level(self, status: str) -> int:
        """Get log level based on status"""
        status_levels = {
            "started": logging.INFO,
            "completed": logging.INFO,
            "failed": logging.ERROR,
            "skipped": logging.WARNING
        }
        return status_levels.get(status, logging.INFO)
    
    def _calculate_performance_metrics(self, trace: PipelineTrace) -> Dict[str, Any]:
        """Calculate performance metrics for a trace"""
        metrics = {
            "total_duration_ms": trace.total_duration_ms,
            "checkpoint_count": len(trace.checkpoints),
            "successful_checkpoints": len([c for c in trace.checkpoints if c.status == "completed"]),
            "failed_checkpoints": len([c for c in trace.checkpoints if c.status == "failed"]),
            "skipped_checkpoints": len([c for c in trace.checkpoints if c.status == "skipped"]),
            "stage_durations": {},
            "bottlenecks": [],
            "efficiency_score": 0.0
        }
        
        # Calculate stage durations
        for checkpoint in trace.checkpoints:
            stage = checkpoint.stage.value
            if stage not in metrics["stage_durations"]:
                metrics["stage_durations"][stage] = 0.0
            metrics["stage_durations"][stage] += checkpoint.duration_ms
        
        # Identify bottlenecks (stages taking >20% of total time)
        total_time = trace.total_duration_ms
        for stage, duration in metrics["stage_durations"].items():
            if total_time > 0 and (duration / total_time) > 0.2:
                metrics["bottlenecks"].append({
                    "stage": stage,
                    "duration_ms": duration,
                    "percentage": (duration / total_time) * 100
                })
        
        # Calculate efficiency score
        if trace.checkpoints:
            successful_ratio = metrics["successful_checkpoints"] / len(trace.checkpoints)
            metrics["efficiency_score"] = successful_ratio * 100
        
        return metrics
    
    async def _store_trace(self, trace: PipelineTrace):
        """Store trace in database"""
        try:
            if not self.db_connection:
                return
            
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Store trace
                trace_query = text("""
                    INSERT INTO pipeline_traces (
                        trace_id, rss_feed_id, article_id, storyline_id,
                        start_time, end_time, total_duration_ms, success,
                        error_stage, performance_metrics
                    ) VALUES (
                        :trace_id, :rss_feed_id, :article_id, :storyline_id,
                        :start_time, :end_time, :total_duration_ms, :success,
                        :error_stage, :performance_metrics
                    )
                """)
                
                db.execute(trace_query, {
                    'trace_id': trace.trace_id,
                    'rss_feed_id': trace.rss_feed_id,
                    'article_id': trace.article_id,
                    'storyline_id': trace.storyline_id,
                    'start_time': trace.start_time,
                    'end_time': trace.end_time,
                    'total_duration_ms': trace.total_duration_ms,
                    'success': trace.success,
                    'error_stage': trace.error_stage.value if trace.error_stage else None,
                    'performance_metrics': json.dumps(trace.performance_metrics)
                })
                
                # Store checkpoints
                for checkpoint in trace.checkpoints:
                    checkpoint_query = text("""
                        INSERT INTO pipeline_checkpoints (
                            checkpoint_id, trace_id, stage, article_id,
                            storyline_id, rss_feed_id, timestamp, duration_ms,
                            status, input_data, output_data, error_message, metadata
                        ) VALUES (
                            :checkpoint_id, :trace_id, :stage, :article_id,
                            :storyline_id, :rss_feed_id, :timestamp, :duration_ms,
                            :status, :input_data, :output_data, :error_message, :metadata
                        )
                    """)
                    
                    db.execute(checkpoint_query, {
                        'checkpoint_id': checkpoint.checkpoint_id,
                        'trace_id': checkpoint.trace_id,
                        'stage': checkpoint.stage.value,
                        'article_id': checkpoint.article_id,
                        'storyline_id': checkpoint.storyline_id,
                        'rss_feed_id': checkpoint.rss_feed_id,
                        'timestamp': checkpoint.timestamp,
                        'duration_ms': checkpoint.duration_ms,
                        'status': checkpoint.status,
                        'input_data': json.dumps(checkpoint.input_data),
                        'output_data': json.dumps(checkpoint.output_data),
                        'error_message': checkpoint.error_message,
                        'metadata': json.dumps(checkpoint.metadata)
                    })
                
                db.commit()
                
            finally:
                db.close()
        except Exception as e:
            self.pipeline_logger.error(f"Error storing trace {trace.trace_id}: {e}")
    
    def get_trace(self, trace_id: str) -> Optional[PipelineTrace]:
        """Get a trace by ID"""
        return self.active_traces.get(trace_id)
    
    def get_all_active_traces(self) -> Dict[str, PipelineTrace]:
        """Get all active traces"""
        return self.active_traces.copy()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of all traces"""
        if not self.active_traces:
            return {"message": "No active traces"}
        
        total_traces = len(self.active_traces)
        successful_traces = len([t for t in self.active_traces.values() if t.success])
        
        avg_duration = sum(t.total_duration_ms for t in self.active_traces.values()) / total_traces
        
        return {
            "total_active_traces": total_traces,
            "successful_traces": successful_traces,
            "success_rate": (successful_traces / total_traces) * 100 if total_traces > 0 else 0,
            "average_duration_ms": avg_duration,
            "traces": [
                {
                    "trace_id": trace.trace_id,
                    "rss_feed_id": trace.rss_feed_id,
                    "article_id": trace.article_id,
                    "storyline_id": trace.storyline_id,
                    "duration_ms": trace.total_duration_ms,
                    "success": trace.success,
                    "checkpoint_count": len(trace.checkpoints)
                }
                for trace in self.active_traces.values()
            ]
        }
    
    def log_ml_step(self, trace_id: str, stage: PipelineStage, 
                   model_name: str, input_tokens: int, output_tokens: int,
                   processing_time_ms: float, success: bool, error: str = None):
        """
        Log ML processing step with detailed metrics
        
        Args:
            trace_id: ID of the trace
            stage: Pipeline stage
            model_name: Name of the ML model used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            processing_time_ms: Processing time in milliseconds
            success: Whether the step was successful
            error: Error message if failed
        """
        metadata = {
            "ml_model": model_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "processing_time_ms": processing_time_ms,
            "tokens_per_second": output_tokens / (processing_time_ms / 1000) if processing_time_ms > 0 else 0,
            "efficiency_ratio": output_tokens / input_tokens if input_tokens > 0 else 0
        }
        
        status = "completed" if success else "failed"
        error_message = error if not success else None
        
        self.add_checkpoint(
            trace_id=trace_id,
            stage=stage,
            status=status,
            metadata=metadata,
            error_message=error_message
        )
    
    def log_database_operation(self, trace_id: str, operation: str, 
                             table: str, record_count: int, 
                             duration_ms: float, success: bool, error: str = None):
        """
        Log database operation with metrics
        
        Args:
            trace_id: ID of the trace
            operation: Database operation (INSERT, UPDATE, DELETE, SELECT)
            table: Database table name
            record_count: Number of records affected
            duration_ms: Operation duration in milliseconds
            success: Whether the operation was successful
            error: Error message if failed
        """
        metadata = {
            "db_operation": operation,
            "table": table,
            "record_count": record_count,
            "duration_ms": duration_ms,
            "records_per_second": record_count / (duration_ms / 1000) if duration_ms > 0 else 0
        }
        
        status = "completed" if success else "failed"
        error_message = error if not success else None
        
        # Map to appropriate pipeline stage
        stage_mapping = {
            "INSERT": PipelineStage.DATABASE_STORAGE,
            "UPDATE": PipelineStage.DATABASE_STORAGE,
            "DELETE": PipelineStage.DATABASE_STORAGE,
            "SELECT": PipelineStage.DATABASE_STORAGE
        }
        
        stage = stage_mapping.get(operation, PipelineStage.DATABASE_STORAGE)
        
        self.add_checkpoint(
            trace_id=trace_id,
            stage=stage,
            status=status,
            metadata=metadata,
            error_message=error_message
        )
    
    def log_api_call(self, trace_id: str, api_endpoint: str, 
                    method: str, status_code: int, 
                    duration_ms: float, success: bool, error: str = None):
        """
        Log API call with metrics
        
        Args:
            trace_id: ID of the trace
            api_endpoint: API endpoint called
            method: HTTP method
            status_code: HTTP status code
            duration_ms: Call duration in milliseconds
            success: Whether the call was successful
            error: Error message if failed
        """
        metadata = {
            "api_endpoint": api_endpoint,
            "http_method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "success": success
        }
        
        status = "completed" if success else "failed"
        error_message = error if not success else None
        
        # Map to appropriate pipeline stage based on endpoint
        if "rag" in api_endpoint.lower():
            stage = PipelineStage.RAG_ENHANCEMENT
        elif "expert" in api_endpoint.lower():
            stage = PipelineStage.EXPERT_ANALYSIS
        elif "impact" in api_endpoint.lower():
            stage = PipelineStage.IMPACT_ASSESSMENT
        elif "historical" in api_endpoint.lower():
            stage = PipelineStage.HISTORICAL_CONTEXT
        elif "predictive" in api_endpoint.lower():
            stage = PipelineStage.PREDICTIVE_ANALYSIS
        else:
            stage = PipelineStage.DATABASE_STORAGE
        
        self.add_checkpoint(
            trace_id=trace_id,
            stage=stage,
            status=status,
            metadata=metadata,
            error_message=error_message
        )

# Global instance
_pipeline_logger = None

def get_pipeline_logger(db_connection=None) -> PipelineLogger:
    """Get global pipeline logger instance"""
    global _pipeline_logger
    if _pipeline_logger is None:
        _pipeline_logger = PipelineLogger(db_connection)
    return _pipeline_logger
