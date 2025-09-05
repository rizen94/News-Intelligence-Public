"""
News Intelligence System v3.1.0 - Production FastAPI Application
Robust, production-ready API with comprehensive error handling
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import production route modules
from routes.articles_production import router as articles_router
from routes.rss_feeds_production import router as rss_feeds_router
from routes.health_production import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting News Intelligence System v3.1.0")
    yield
    # Shutdown
    logger.info("Shutting down News Intelligence System v3.1.0")

# Create FastAPI application
app = FastAPI(
    title="News Intelligence System v3.1.0",
    description="Production-ready news intelligence and analysis platform",
    version="3.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "message": "Internal server error",
            "error": str(exc),
            "timestamp": "2025-09-05T17:00:00Z"
        }
    )

# Include routers
app.include_router(articles_router, prefix="/api")
app.include_router(rss_feeds_router, prefix="/api")
app.include_router(health_router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System",
            "version": "3.1.0",
            "status": "operational",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "message": "News Intelligence System v3.1.0 is running",
        "timestamp": "2025-09-05T17:00:00Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
