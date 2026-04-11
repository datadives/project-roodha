import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models
from app.core.auth_middleware import JWTAuthMiddleware
from app.database import SessionLocal
from app.routes import auth, job_operations, jobs, master_data, metrics, notifications, planning, system

DEV_TENANT_ID = "tenant-123"
DEV_OPERATIONS = [
    {"operation_id": "CUTTING", "name": "Cutting", "standard_cycle_time_mins": 30},
    {"operation_id": "MACHINING", "name": "Machining", "standard_cycle_time_mins": 45},
    {"operation_id": "QUALITY_CHECK", "name": "Quality Check", "standard_cycle_time_mins": 15},
]

logger = logging.getLogger("jobwork-backend")

app = FastAPI(
    title="Project Roodha Backend",
    description="Digital Nervous System for Job-Work Units",
    version="1.0.0",
    redirect_slashes=False,
)

configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
cors_origins = list(
    dict.fromkeys(
        [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            # V1.0 Production staging — S3 static website
            "http://roodha-staging.s3-website-ap-south-1.amazonaws.com",
            "https://roodha-staging.s3-website-ap-south-1.amazonaws.com",
            *configured_origins,
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)


@app.middleware("http")
async def normalize_trailing_slash(request: Request, call_next):
    path = request.scope.get("path", "")
    if path not in {"", "/"} and path.endswith("/"):
        request.scope["path"] = path.rstrip("/")
    return await call_next(request)


@app.on_event("startup")
def bootstrap_development_foundation():
    if os.getenv("ENV", "").lower() != "development":
        return

    db = SessionLocal()
    try:
        existing_tenant = (
            db.query(models.Tenant)
            .filter(models.Tenant.tenant_id == DEV_TENANT_ID)
            .first()
        )
        if not existing_tenant:
            db.add(
                models.Tenant(
                    tenant_id=DEV_TENANT_ID,
                    company_name="Project Roodha Development Tenant",
                    subscription_plan="development",
                )
            )

        existing_operation_ids = {
            operation_id
            for (operation_id,) in db.query(models.OperationsMaster.operation_id)
            .filter(models.OperationsMaster.tenant_id == DEV_TENANT_ID)
            .all()
        }
        for operation in DEV_OPERATIONS:
            if operation["operation_id"] in existing_operation_ids:
                continue
            db.add(
                models.OperationsMaster(
                    tenant_id=DEV_TENANT_ID,
                    operation_id=operation["operation_id"],
                    name=operation["name"],
                    standard_cycle_time_mins=operation["standard_cycle_time_mins"],
                )
            )

        db.commit()
        logger.info("Development bootstrap verified for tenant %s", DEV_TENANT_ID)
    except Exception:
        db.rollback()
        logger.exception("Development bootstrap failed")
        raise
    finally:
        db.close()

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(master_data.router)
app.include_router(jobs.router)
app.include_router(job_operations.router)
app.include_router(planning.router)
app.include_router(metrics.router)
app.include_router(notifications.router)
