# User Management Routes Package
from fastapi import APIRouter

from .user_management import router as user_management_router

__all__ = ["router"]
