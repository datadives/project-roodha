from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.core.auth_middleware import JWTAuthMiddleware
from app.database import engine
from app.routes import auth, job_operations, jobs, master_data, metrics, notifications, planning, system

# Automatically creates tables in AWS RDS on startup for development.
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Project Roodha Backend",
    description="Digital Nervous System for Job-Work Units",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTAuthMiddleware)

app.include_router(system.router)
app.include_router(auth.router)
app.include_router(master_data.router)
app.include_router(jobs.router)
app.include_router(job_operations.router)
app.include_router(planning.router)
app.include_router(metrics.router)
app.include_router(notifications.router)
