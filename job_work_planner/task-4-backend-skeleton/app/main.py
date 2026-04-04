# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
<<<<<<< ours
<<<<<<< ours
from app.routes import (
    auth, 
    job_operations, 
    jobs, 
    master_data, 
    metrics, 
    notifications, 
    planning, 
    system
)
from app.core.auth_middleware import JWTAuthMiddleware
from app.database import engine, Base
=======
>>>>>>> theirs
=======
>>>>>>> theirs

# ---------------------------------------------------------
# 1. Database Initialization
# ---------------------------------------------------------
<<<<<<< ours
<<<<<<< ours
# Automatically creates tables in AWS RDS on startup (Development use)
Base.metadata.create_all(bind=engine)
=======
from app.routes import auth, job_operations, jobs, master_data, metrics, notifications, planning, system
>>>>>>> theirs
=======
from app.routes import auth, job_operations, jobs, master_data, metrics, notifications, planning, system
>>>>>>> theirs

# ---------------------------------------------------------
# 2. FastAPI App Configuration
# ---------------------------------------------------------
app = FastAPI(
    title="Project Roodha Backend",
    description="Digital Nervous System for Job-Work Units",
    version="1.0.0"
)

# ---------------------------------------------------------
# 3. Middleware Registration
# ---------------------------------------------------------
<<<<<<< ours
# CORS - Essential for React/PWA frontend communication 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
=======
app = FastAPI(
    title="JobWork Backend Skeleton",
    version="0.1.0",
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
)

# JWT Auth - Enforces strict tenant-id isolation for SaaS security [cite: 13, 131]
app.add_middleware(JWTAuthMiddleware)

# ---------------------------------------------------------
<<<<<<< ours
# 4. Router Registration (V1.0 & V1.5 Scope)
# ---------------------------------------------------------
app.include_router(auth.router, tags=["Authentication"])
app.include_router(master_data.router, tags=["Master Data"]) # [cite: 102]
app.include_router(jobs.router, tags=["Jobs"]) # [cite: 102]
app.include_router(job_operations.router, tags=["Job WIP"]) # [cite: 102]
app.include_router(planning.router, tags=["Planning & Capacity"]) # [cite: 103]
app.include_router(metrics.router, tags=["Analytics & Dashboard"]) # [cite: 104]
app.include_router(notifications.router, tags=["Notifications"]) # [cite: 104]
app.include_router(system.router, tags=["System Logs"])
=======
# Register middleware
# ---------------------------------------------------------
# NOTE:
# - CORSMiddleware is required for frontend integration.
# - JWTAuthMiddleware enforces tenant-aware authentication context.
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)
>>>>>>> theirs

# ---------------------------------------------------------
# 5. Global Health Check
# ---------------------------------------------------------
<<<<<<< ours
<<<<<<< ours
@app.get("/health", tags=["System"])
def health_check():
    """Verifies backend operational status and AWS RDS connectivity."""
    return {
        "status": "ok", 
        "message": "Backend is running and connected to AWS RDS!"
    }
=======
=======
>>>>>>> theirs
# Keep V1.0 + V1.5 surface area active.
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(master_data.router)
app.include_router(jobs.router)
app.include_router(job_operations.router)
app.include_router(planning.router)
app.include_router(metrics.router)
app.include_router(notifications.router)
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
