#!/usr/bin/env python3
"""
Minimal test server to isolate blocking issues
"""

import sys
sys.path.append('api')

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Minimal test server working"}

@app.get("/health")
async def health():
    return {"status": "healthy", "message": "Server is running"}

@app.get("/api/health/")
async def api_health():
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "timestamp": "2025-09-09T11:45:00Z",
            "services": {
                "database": "healthy",
                "redis": "healthy",
                "system": "healthy"
            }
        },
        "message": "System health retrieved successfully"
    }

if __name__ == "__main__":
    print("Starting minimal test server...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
