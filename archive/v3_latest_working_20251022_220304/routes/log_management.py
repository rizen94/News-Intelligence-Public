"""
News Intelligence System v3.3.0 - Log Management API Routes
Provides endpoints for log viewing, analysis, and management
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config.database import get_db
from config.logging_config import get_component_logger
from services.log_storage_service import get_log_storage, LogStats
from schemas.robust_schemas import APIResponse

router = APIRouter(prefix="/logs", tags=["Log Management"])
logger = get_component_logger('api')

@router.get("/statistics", response_model=APIResponse)
async def get_log_statistics(
    days: int = Query(7, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get comprehensive log statistics"""
    try:
        log_storage = get_log_storage()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        stats = log_storage.get_log_statistics(start_date, end_date)
        
        return APIResponse(
            success=True,
            data={
                'period_days': days,
                'total_entries': stats.total_entries,
                'error_count': stats.error_count,
                'warning_count': stats.warning_count,
                'info_count': stats.info_count,
                'debug_count': stats.debug_count,
                'time_range': {
                    'start': stats.time_range[0].isoformat(),
                    'end': stats.time_range[1].isoformat()
                },
                'top_loggers': [{'logger': name, 'count': count} for name, count in stats.top_loggers],
                'top_errors': [{'error': error, 'count': count} for error, count in stats.top_errors]
            },
            message=f"Log statistics for last {days} days"
        )
        
    except Exception as e:
        logger.error(f"Error getting log statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries", response_model=APIResponse)
async def get_log_entries(
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    level: Optional[str] = Query(None, description="Log level filter"),
    logger_name: Optional[str] = Query(None, description="Logger name filter"),
    limit: int = Query(100, description="Maximum number of entries"),
    db: Session = Depends(get_db)
):
    """Get log entries with filtering"""
    try:
        log_storage = get_log_storage()
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        entries = log_storage.get_log_entries(
            start_time=start_dt,
            end_time=end_dt,
            level=level,
            logger=logger_name,
            limit=limit
        )
        
        # Convert to serializable format
        serialized_entries = []
        for entry in entries:
            serialized_entries.append({
                'timestamp': entry.timestamp.isoformat(),
                'level': entry.level,
                'logger': entry.logger,
                'message': entry.message,
                'module': entry.module,
                'function': entry.function,
                'line': entry.line,
                'exception': entry.exception,
                'extra_data': entry.extra_data
            })
        
        return APIResponse(
            success=True,
            data={
                'entries': serialized_entries,
                'count': len(serialized_entries),
                'filters': {
                    'start_time': start_time,
                    'end_time': end_time,
                    'level': level,
                    'logger': logger_name,
                    'limit': limit
                }
            },
            message=f"Retrieved {len(serialized_entries)} log entries"
        )
        
    except Exception as e:
        logger.error(f"Error getting log entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/errors", response_model=APIResponse)
async def get_error_analysis(
    days: int = Query(7, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get detailed error analysis"""
    try:
        log_storage = get_log_storage()
        
        analysis = log_storage.analyze_error_patterns(days)
        
        return APIResponse(
            success=True,
            data=analysis,
            message=f"Error analysis for last {days} days"
        )
        
    except Exception as e:
        logger.error(f"Error analyzing errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=APIResponse)
async def get_system_health_from_logs(
    db: Session = Depends(get_db)
):
    """Get system health metrics based on logs"""
    try:
        log_storage = get_log_storage()
        
        health_metrics = log_storage.get_system_health_metrics()
        
        return APIResponse(
            success=True,
            data=health_metrics,
            message="System health metrics from logs"
        )
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export", response_model=APIResponse)
async def export_logs(
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    format: str = Query("json", description="Export format (json, csv)"),
    db: Session = Depends(get_db)
):
    """Export logs to file"""
    try:
        log_storage = get_log_storage()
        
        # Parse datetime strings
        start_dt = datetime.fromisoformat(start_time) if start_time else None
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs_export_{timestamp}.{format}"
        filepath = f"/tmp/{filename}"
        
        # Export logs
        success = log_storage.export_logs(
            output_path=filepath,
            start_time=start_dt,
            end_time=end_dt,
            format=format
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to export logs")
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"Error exporting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup", response_model=APIResponse)
async def cleanup_old_logs(
    db: Session = Depends(get_db)
):
    """Clean up old log files and database entries"""
    try:
        log_storage = get_log_storage()
        
        # Compress old logs
        log_storage.compress_old_logs()
        
        # Clean up old entries
        log_storage.cleanup_old_logs()
        
        return APIResponse(
            success=True,
            data={'cleanup_completed': True},
            message="Log cleanup completed successfully"
        )
        
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files", response_model=APIResponse)
async def list_log_files(
    db: Session = Depends(get_db)
):
    """List available log files"""
    try:
        import os
        from pathlib import Path
        
        log_dir = Path("/app/logs")
        log_files = []
        
        for file_path in log_dir.glob("*.log*"):
            stat = file_path.stat()
            log_files.append({
                'name': file_path.name,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'type': 'compressed' if file_path.suffix == '.gz' else 'active'
            })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return APIResponse(
            success=True,
            data={'log_files': log_files},
            message=f"Found {len(log_files)} log files"
        )
        
    except Exception as e:
        logger.error(f"Error listing log files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/realtime", response_model=APIResponse)
async def get_realtime_logs(
    limit: int = Query(50, description="Number of recent entries"),
    db: Session = Depends(get_db)
):
    """Get real-time log entries (last few minutes)"""
    try:
        log_storage = get_log_storage()
        
        # Get logs from last 5 minutes
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        entries = log_storage.get_log_entries(
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Convert to serializable format
        serialized_entries = []
        for entry in entries:
            serialized_entries.append({
                'timestamp': entry.timestamp.isoformat(),
                'level': entry.level,
                'logger': entry.logger,
                'message': entry.message,
                'module': entry.module,
                'function': entry.function,
                'line': entry.line
            })
        
        return APIResponse(
            success=True,
            data={
                'entries': serialized_entries,
                'count': len(serialized_entries),
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            },
            message=f"Retrieved {len(serialized_entries)} recent log entries"
        )
        
    except Exception as e:
        logger.error(f"Error getting realtime logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
