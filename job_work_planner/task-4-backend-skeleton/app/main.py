import logging
import os
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- SYSTEM PATH INITIALIZATION ---
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth_middleware import JWTAuthMiddleware
from app.database import refresh_engine_pools
from app.routes import (
    auth, job_operations, jobs, master_data, metrics, 
    notifications, planning, system, kanban, maintenance, exports
)

logger = logging.getLogger("jobwork-backend")

app = FastAPI(
    title="Project Roodha Backend",
    version="1.5.7",
    redirect_slashes=False,
)

# --- MIDDLEWARE (ORDER MATTERS) ---
# CORS must be OUTERMOST to handle browser pre-flights
# Change this section in app/main.py
app.add_middleware(
    CORSMiddleware,
    # Replace ["*"] with the specific origins your app uses
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)

@app.on_event("startup")
async def startup_event():
    await refresh_engine_pools()
    logger.info("✅ Backend started and connected to AWS RDS")

# --- ROUTE REGISTRATION ---
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

@app.get("/api/ping")
async def ping():
    return {"message": "pong"}