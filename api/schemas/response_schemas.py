"""
Standardized API Response Schemas for News Intelligence System v3.0
Provides consistent response formats across all API endpoints
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata"""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class FilterMeta(BaseModel):
    """Filter metadata"""

    applied_filters: dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    available_filters: dict[str, list[str]] = Field(
        default_factory=dict, description="Available filter options"
    )


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response format"""

    success: bool = Field(..., description="Whether the request was successful")
    data: T = Field(..., description="Response data")
    message: str | None = Field(None, description="Success or informational message")
    error: str | None = Field(None, description="Error message if unsuccessful")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response format"""

    success: bool = Field(..., description="Whether the request was successful")
    data: list[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    filters: FilterMeta | None = Field(None, description="Filter metadata")
    message: str | None = Field(None, description="Success or informational message")
    error: str | None = Field(None, description="Error message if unsuccessful")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class ErrorResponse(BaseModel):
    """Standardized error response format"""

    success: bool = Field(False, description="Always false for errors")
    data: Any | None = Field(None, description="Null for errors")
    error: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code for programmatic handling")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# Utility functions for creating responses
def create_success_response(
    data: T, message: str = None, meta: dict[str, Any] = None
) -> APIResponse[T]:
    """Create a standardized success response"""
    return APIResponse(success=True, data=data, message=message, meta=meta)


def create_error_response(
    error: str, error_code: str = None, details: dict[str, Any] = None
) -> ErrorResponse:
    """Create a standardized error response"""
    return ErrorResponse(error=error, error_code=error_code, details=details)


def create_paginated_response(
    data: list[T],
    page: int,
    per_page: int,
    total: int,
    message: str = None,
    filters: FilterMeta = None,
) -> PaginatedResponse[T]:
    """Create a standardized paginated response"""
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    pagination = PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
    )

    return PaginatedResponse(
        success=True, data=data, pagination=pagination, filters=filters, message=message
    )
