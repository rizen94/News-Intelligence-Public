"""
News Intelligence System v3.3.0 - Comprehensive Error Handling Middleware
Provides centralized error handling, logging, and recovery mechanisms
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import psycopg2
import sqlalchemy.exc
from pydantic import ValidationError

from config.logging_config import get_component_logger
from services.log_storage_service import get_log_storage, LogEntry

class ErrorHandler:
    """
    Comprehensive error handling system
    Provides centralized error processing, logging, and recovery
    """
    
    def __init__(self):
        self.logger = get_component_logger('error')
        self.log_storage = get_log_storage()
        self.error_counts = {}
        self.error_thresholds = {
            'database_connection': 5,
            'validation_error': 10,
            'external_api': 3,
            'ml_processing': 2
        }
    
    def handle_exception(self, 
                        exception: Exception, 
                        context: Dict[str, Any],
                        request: Optional[Request] = None) -> Dict[str, Any]:
        """
        Handle any exception with comprehensive logging and context
        
        Args:
            exception: The exception that occurred
            context: Additional context information
            request: FastAPI request object (if available)
            
        Returns:
            Dict containing error response information
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # Create comprehensive error context
        error_context = {
            'error_type': error_type,
            'error_message': error_message,
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'request_info': self._extract_request_info(request) if request else None
        }
        
        # Log the error
        self._log_error(exception, error_context)
        
        # Check for error patterns
        self._check_error_patterns(error_type, error_context)
        
        # Determine error response
        return self._create_error_response(exception, error_context)
    
    def _extract_request_info(self, request: Request) -> Dict[str, Any]:
        """Extract relevant information from FastAPI request"""
        try:
            return {
                'method': request.method,
                'url': str(request.url),
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'headers': dict(request.headers),
                'client_ip': request.client.host if request.client else None,
                'user_agent': request.headers.get('user-agent')
            }
        except Exception as e:
            self.logger.warning(f"Failed to extract request info: {e}")
            return {'error': 'Failed to extract request info'}
    
    def _log_error(self, exception: Exception, error_context: Dict[str, Any]):
        """Log error with comprehensive context"""
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level='ERROR',
            logger='news_intelligence.error_handler',
            message=f"{type(exception).__name__}: {str(exception)}",
            module=exception.__class__.__module__,
            function=traceback.extract_tb(exception.__traceback__)[-1].name if exception.__traceback__ else 'unknown',
            line=traceback.extract_tb(exception.__traceback__)[-1].lineno if exception.__traceback__ else 0,
            exception={
                'type': type(exception).__name__,
                'message': str(exception),
                'traceback': traceback.format_exc()
            },
            extra_data=error_context
        )
        
        # Store in log storage
        self.log_storage.store_log_entry(log_entry)
        
        # Log to standard logger
        self.logger.error(f"Error handled: {error_context}")
    
    def _check_error_patterns(self, error_type: str, error_context: Dict[str, Any]):
        """Check for error patterns and alert if thresholds exceeded"""
        # Count errors by type
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
        
        # Check thresholds
        threshold = self.error_thresholds.get(error_type, 10)
        if self.error_counts[error_type] > threshold:
            self.logger.critical(f"Error threshold exceeded for {error_type}: {self.error_counts[error_type]} errors")
            
            # Reset counter after alerting
            self.error_counts[error_type] = 0
    
    def _create_error_response(self, exception: Exception, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create appropriate error response based on exception type"""
        error_type = type(exception).__name__
        
        # Database errors
        if isinstance(exception, psycopg2.Error):
            return self._handle_database_error(exception, error_context)
        
        # SQLAlchemy errors
        elif isinstance(exception, sqlalchemy.exc.SQLAlchemyError):
            return self._handle_sqlalchemy_error(exception, error_context)
        
        # Validation errors
        elif isinstance(exception, (ValidationError, RequestValidationError)):
            return self._handle_validation_error(exception, error_context)
        
        # HTTP errors
        elif isinstance(exception, (HTTPException, StarletteHTTPException)):
            return self._handle_http_error(exception, error_context)
        
        # ML processing errors
        elif 'ml' in error_context.get('context', {}).get('operation', '').lower():
            return self._handle_ml_error(exception, error_context)
        
        # Generic errors
        else:
            return self._handle_generic_error(exception, error_context)
    
    def _handle_database_error(self, exception: psycopg2.Error, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle database-specific errors"""
        error_code = getattr(exception, 'pgcode', 'UNKNOWN')
        
        if error_code == '23505':  # Unique constraint violation
            return {
                'status_code': status.HTTP_409_CONFLICT,
                'error_type': 'duplicate_entry',
                'message': 'Resource already exists',
                'details': str(exception),
                'recoverable': True
            }
        elif error_code == '23503':  # Foreign key constraint violation
            return {
                'status_code': status.HTTP_400_BAD_REQUEST,
                'error_type': 'foreign_key_violation',
                'message': 'Referenced resource does not exist',
                'details': str(exception),
                'recoverable': True
            }
        elif error_code == '23502':  # Not null constraint violation
            return {
                'status_code': status.HTTP_400_BAD_REQUEST,
                'error_type': 'null_constraint_violation',
                'message': 'Required field is missing',
                'details': str(exception),
                'recoverable': True
            }
        else:
            return {
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error_type': 'database_error',
                'message': 'Database operation failed',
                'details': str(exception),
                'recoverable': False
            }
    
    def _handle_sqlalchemy_error(self, exception: sqlalchemy.exc.SQLAlchemyError, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SQLAlchemy-specific errors"""
        if isinstance(exception, sqlalchemy.exc.IntegrityError):
            return {
                'status_code': status.HTTP_409_CONFLICT,
                'error_type': 'integrity_error',
                'message': 'Data integrity constraint violated',
                'details': str(exception),
                'recoverable': True
            }
        elif isinstance(exception, sqlalchemy.exc.OperationalError):
            return {
                'status_code': status.HTTP_503_SERVICE_UNAVAILABLE,
                'error_type': 'operational_error',
                'message': 'Database connection or operation failed',
                'details': str(exception),
                'recoverable': True
            }
        else:
            return {
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error_type': 'sqlalchemy_error',
                'message': 'Database operation failed',
                'details': str(exception),
                'recoverable': False
            }
    
    def _handle_validation_error(self, exception: Union[ValidationError, RequestValidationError], error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle validation errors"""
        if isinstance(exception, RequestValidationError):
            errors = exception.errors()
            return {
                'status_code': status.HTTP_422_UNPROCESSABLE_ENTITY,
                'error_type': 'validation_error',
                'message': 'Request validation failed',
                'details': errors,
                'recoverable': True
            }
        else:
            return {
                'status_code': status.HTTP_400_BAD_REQUEST,
                'error_type': 'validation_error',
                'message': 'Data validation failed',
                'details': str(exception),
                'recoverable': True
            }
    
    def _handle_http_error(self, exception: Union[HTTPException, StarletteHTTPException], error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle HTTP errors"""
        return {
            'status_code': exception.status_code,
            'error_type': 'http_error',
            'message': exception.detail,
            'details': str(exception),
            'recoverable': exception.status_code < 500
        }
    
    def _handle_ml_error(self, exception: Exception, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ML processing errors"""
        return {
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'error_type': 'ml_processing_error',
            'message': 'Machine learning processing failed',
            'details': str(exception),
            'recoverable': True,
            'retry_recommended': True
        }
    
    def _handle_generic_error(self, exception: Exception, error_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic errors"""
        return {
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'error_type': 'internal_error',
            'message': 'An internal error occurred',
            'details': str(exception),
            'recoverable': False
        }


class ErrorRecoveryService:
    """
    Service for handling error recovery and retry mechanisms
    """
    
    def __init__(self):
        self.logger = get_component_logger('error')
        self.retry_strategies = {
            'database_connection': self._retry_database_connection,
            'external_api': self._retry_external_api,
            'ml_processing': self._retry_ml_processing,
            'file_operation': self._retry_file_operation
        }
    
    def attempt_recovery(self, 
                        error_type: str, 
                        operation: Callable, 
                        *args, 
                        max_retries: int = 3,
                        **kwargs) -> Any:
        """
        Attempt to recover from an error by retrying the operation
        
        Args:
            error_type: Type of error to recover from
            operation: Function to retry
            *args: Arguments for the operation
            max_retries: Maximum number of retry attempts
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation or raises the last exception
        """
        retry_strategy = self.retry_strategies.get(error_type, self._retry_generic)
        
        for attempt in range(max_retries + 1):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    self.logger.error(f"Recovery failed after {max_retries} attempts: {e}")
                    raise
                
                self.logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")
                retry_strategy(attempt, e)
    
    def _retry_database_connection(self, attempt: int, exception: Exception):
        """Retry strategy for database connection errors"""
        import time
        time.sleep(2 ** attempt)  # Exponential backoff
    
    def _retry_external_api(self, attempt: int, exception: Exception):
        """Retry strategy for external API errors"""
        import time
        time.sleep(1 + attempt)  # Linear backoff
    
    def _retry_ml_processing(self, attempt: int, exception: Exception):
        """Retry strategy for ML processing errors"""
        import time
        time.sleep(5 + (attempt * 2))  # Longer backoff for ML operations
    
    def _retry_file_operation(self, attempt: int, exception: Exception):
        """Retry strategy for file operation errors"""
        import time
        time.sleep(0.5 + attempt)  # Short backoff
    
    def _retry_generic(self, attempt: int, exception: Exception):
        """Generic retry strategy"""
        import time
        time.sleep(1 + attempt)


# Global error handler instance
_error_handler_instance = None

def get_error_handler() -> ErrorHandler:
    """Get global error handler instance"""
    global _error_handler_instance
    if _error_handler_instance is None:
        _error_handler_instance = ErrorHandler()
    return _error_handler_instance

def get_error_recovery() -> ErrorRecoveryService:
    """Get global error recovery service instance"""
    return ErrorRecoveryService()
