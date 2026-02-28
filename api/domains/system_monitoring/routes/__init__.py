# System Monitoring — consolidated router
from fastapi import APIRouter
from .system_monitoring import router as monitoring_router
from .route_supervisor import router as supervisor_router

router = APIRouter(tags=["System Monitoring"])
router.include_router(monitoring_router)
router.include_router(supervisor_router)

__all__ = ["router"]
