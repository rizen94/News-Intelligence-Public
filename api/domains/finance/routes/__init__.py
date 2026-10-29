# Finance Domain Routes Package
from fastapi import APIRouter

from .finance import router as finance_router

__all__ = ["router"]
