# System Monitoring — consolidated router
from fastapi import APIRouter

from .orchestrator import router as orchestrator_router
from .realtime import router as realtime_router
from .resource_dashboard import router as resource_dashboard_router
from .route_supervisor import router as supervisor_router
from .sql_explorer import router as sql_explorer_router
from .system_monitoring import router as monitoring_router

router = APIRouter(tags=["System Monitoring"])
router.include_router(monitoring_router)
router.include_router(supervisor_router)
router.include_router(orchestrator_router)
router.include_router(resource_dashboard_router)
router.include_router(realtime_router)
router.include_router(sql_explorer_router)

__all__ = ["router"]
