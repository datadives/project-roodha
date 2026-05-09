"""
PROJECT ROODHA - BACKEND CORE
FILE: main.py
PURPOSE: Primary entry point for the Project Roodha FastAPI application. 
         Handles middleware orchestration, database bootstrap, and route registration.
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# --- SYSTEM PATH INITIALIZATION ---
# Ensures the 'app' module is discoverable regardless of current working directory.
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from app import models
from app.core.auth_middleware import JWTAuthMiddleware
from app.database import AsyncSessionLocal, fetch_db_runtime_snapshot, refresh_engine_pools
from app.routes import auth, job_operations, jobs, master_data, metrics, notifications, planning, system, kanban, maintenance, exports

# --- DEVELOPMENT DEFAULTS ---
DEV_TENANT_ID = "tenant-123"
DEV_OPERATIONS = [
    {"id": "00000000-0000-0000-0000-000000000001", "name": "Cutting", "standard_cycle_time_mins": 30},
    {"id": "00000000-0000-0000-0000-000000000002", "name": "Machining", "standard_cycle_time_mins": 45},
    {"id": "00000000-0000-0000-0000-000000000003", "name": "Quality Check", "standard_cycle_time_mins": 15},
]

logger = logging.getLogger("jobwork-backend")

# --- FASTAPI APP DEFINITION ---
app = FastAPI(
    title="Project Roodha Backend",
    description="Digital Nervous System for Job-Work Units",
    version="1.5.7",
    redirect_slashes=False,
)

# --- CORS & SECURITY ORCHESTRATION ---
configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
configured_cloudfront_origin = os.getenv("CLOUDFRONT_FRONTEND_ORIGIN", "").strip()
cors_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"https://.*\.cloudfront\.net").strip()
cors_origins = list(
    dict.fromkeys(
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            # V1.0 Production S3 static website origins
            "http://roodhaprodbucketstackv1-roodhaprodbucketv1709e8cd5-eyi4xpi7ilog.s3-website.ap-south-1.amazonaws.com",
            "https://roodhaprodbucketstackv1-roodhaprodbucketv1709e8cd5-eyi4xpi7ilog.s3-website.ap-south-1.amazonaws.com",
            configured_cloudfront_origin,
            *configured_origins,
        ]
    )
)
cors_origins = [origin for origin in cors_origins if origin]

app.add_middleware(JWTAuthMiddleware)
# Keep CORS as the final middleware registration so it is the outermost layer.
# This lets browser OPTIONS preflight requests complete before JWT validation.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- LIFECYCLE HOOKS ---

@app.on_event("startup")
async def log_runtime_database_connection():
    """
    Verifies and logs the active database connection details on startup.
    """
    await refresh_engine_pools()
    # snapshot = await fetch_db_runtime_snapshot()
    logger.info("Server started (DB snapshot skipped for SQLite)")

# --- ROUTE REGISTRATION ---
# All endpoints are namespaced under /api for consistent frontend consumption.
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(master_data.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(job_operations.router, prefix="/api")
app.include_router(planning.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(kanban.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
