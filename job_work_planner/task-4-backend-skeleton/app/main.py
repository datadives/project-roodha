"""
main.py
-------
Application entry point.

Responsibilities:
- Create FastAPI application
- Register middleware
- Register all API routers
"""

from fastapi import FastAPI

# ---------------------------------------------------------
# Routers
# ---------------------------------------------------------
from app.routes import system, auth, jobs, job_operations

# ---------------------------------------------------------
# Middleware
# ---------------------------------------------------------
from app.core.auth_middleware import JWTAuthMiddleware

# ---------------------------------------------------------
# Create FastAPI app
# ---------------------------------------------------------
app = FastAPI(
    title="JobWork Backend Skeleton",
    version="0.1.0"
)

# ---------------------------------------------------------
# Register middleware
# ---------------------------------------------------------
# NOTE:
# JWTAuthMiddleware is implemented as ASGI middleware,
# so it MUST be registered using add_middleware()
# ---------------------------------------------------------
app.add_middleware(JWTAuthMiddleware)

# ---------------------------------------------------------
# Register API routers
# ---------------------------------------------------------
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(job_operations.router)  # ✅ SCRUM 28 API