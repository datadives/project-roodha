"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: maintenance.py
 * 
 * 1) Purpose: Defines API endpoints for maintenance.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
maintenance.py
--------------
Maintenance routes for batch processing and reconciliations.
Authorized via IAM SigV4 for safe EventBridge/Lambda triggers.
"""

import logging
import os
from datetime import UTC, datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import case, cast, Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_async_db
from app.core.event_service import record_event
from app.core.notification_service import create_notification, send_email
from app.services.maintenance_service import run_batch_costing_service
from app.core.response_models import ApiResponse

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])
logger = logging.getLogger("jobwork-backend")

async def require_iam_auth(request: Request):
    """
    Dependency that enforces IAM-based authorization.
    Verifies that the request was signed via AWS SigV4 and passed by API Gateway.
    """
    # 1. Check for standard AWS Lambda/API Gateway authorizer context
    # Mangum usually populates 'aws.event' in the scope
    aws_event = request.scope.get("aws_event") or {}
    request_context = aws_event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    
    # Check for IAM context (populated when using AWS_IAM auth type)
    iam_context = authorizer.get("iam")
    
    if not iam_context:
        # Fallback: check if we are in development
        import os
        if os.getenv("ENV") == "development":
            logger.warning("MAINTENANCE | Bypassing IAM check in development.")
            return True
            
        logger.error(f"MAINTENANCE | Forbidden: Access attempt without valid IAM context. Scope: {authorizer}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Maintenance routes require IAM-based authorization."
        )
    
    logger.info(f"MAINTENANCE | Authorized via IAM: {iam_context.get('accessKey')}")
    return True


async def require_maintenance_secret(request: Request):
    configured = os.getenv("MAINTENANCE_SECRET")
    provided = request.headers.get("x-roodha-maintenance-secret")
    if configured and provided == configured:
        return True
    if os.getenv("ENV", "").lower() in {"local", "development", "dev"}:
        logger.warning("MAINTENANCE | Bypassing shared secret in local runtime.")
        return True
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: invalid maintenance secret.")


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _utc_day_bounds(value: datetime) -> tuple[datetime, datetime]:
    day = value.date()
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


async def _notification_exists_today(
    db: AsyncSession,
    tenant_id: str,
    notif_type: str,
    entity_type: str,
    entity_id: str,
    now: datetime,
) -> bool:
    start, end = _utc_day_bounds(now)
    result = await db.execute(
        select(models.Notification.notification_id)
        .where(
            models.Notification.tenant_id == tenant_id,
            models.Notification.type == notif_type,
            models.Notification.entity_type == entity_type,
            models.Notification.entity_id == entity_id,
            models.Notification.created_at >= start,
            models.Notification.created_at <= end,
        )
        .limit(1)
    )
    return bool(result.scalar_one_or_none())


async def _send_tenant_alert_email(db: AsyncSession, tenant_id: str, subject: str, body: str) -> int:
    result = await db.execute(
        select(models.User.email)
        .where(
            models.User.tenant_id == tenant_id,
            models.User.role.in_(["OWNER", "SUPERVISOR"]),
            models.User.email.isnot(None),
        )
    )
    sent = 0
    for email in result.scalars().all():
        if await send_email(email, subject, body):
            sent += 1
    return sent

@router.post("/batch-costing", response_model=ApiResponse)
async def trigger_batch_costing(
    request: Request,
    is_authorized: bool = Depends(require_iam_auth),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Manually triggers the batch costing reconciliation.
    Designed for EventBridge invocation at 11:30 PM UTC.
    """
    result = await run_batch_costing_service(db)
    return ApiResponse(data=result, message="Batch costing reconciliation completed.")


@router.post("/v15-nightly", response_model=ApiResponse)
async def trigger_v15_nightly(
    request: Request,
    is_authorized: bool = Depends(require_maintenance_secret),
    db: AsyncSession = Depends(get_async_db),
):
    now = _utcnow_naive()
    tenants = (await db.execute(select(models.Tenant.tenant_id))).scalars().all()
    created = {"delay_risks": 0, "machine_overloads": 0, "emails_sent": 0, "duplicates_skipped": 0}

    for tenant_id in tenants:
        late_jobs = await db.execute(
            select(models.Job)
            .join(models.JobOperation, models.JobOperation.job_id == models.Job.job_id, isouter=True)
            .where(
                models.Job.tenant_id == tenant_id,
                models.Job.status != models.JobStatus.COMPLETED,
                func.coalesce(models.JobOperation.planned_end_date, models.Job.due_date).isnot(None),
                func.coalesce(models.JobOperation.planned_end_date, models.Job.due_date) < now,
            )
            .distinct()
        )
        for job in late_jobs.scalars().all():
            if await _notification_exists_today(db, tenant_id, "JOB_DELAY_RISK", "JOB", str(job.job_id), now):
                created["duplicates_skipped"] += 1
                continue
            await create_notification(
                db=db,
                tenant_id=tenant_id,
                user_id=None,
                notif_type="JOB_DELAY_RISK",
                title="Job delay risk",
                message=f"Job {job.job_number} is past due and still open.",
                entity_ref=job.job_number,
                entity_type="JOB",
                entity_id=str(job.job_id),
                created_at=now,
            )
            created["emails_sent"] += await _send_tenant_alert_email(
                db,
                tenant_id,
                subject=f"Roodha delay risk: {job.job_number}",
                body=f"Job {job.job_number} is past due and still open.",
            )
            await record_event(db, tenant_id, "JOB_DELAY_RISK", "JOB", str(job.job_id), {"job_number": job.job_number}, flush_only=False)
            created["delay_risks"] += 1

        operation_hours = case(
            (models.OperationsMaster.standard_cycle_time_mins <= 0, 0.1),
            else_=(cast(models.Job.quantity, Float) * cast(models.OperationsMaster.standard_cycle_time_mins, Float)) / 60.0,
        )
        overloads = await db.execute(
            select(models.Machine, func.coalesce(func.sum(operation_hours), 0.0).label("booked_hours"))
            .join(models.JobOperation, models.JobOperation.machine_id == models.Machine.machine_id)
            .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
            .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id)
            .where(
                models.Machine.tenant_id == tenant_id,
                models.JobOperation.tenant_id == tenant_id,
                models.Job.tenant_id == tenant_id,
                models.JobOperation.status.notin_([models.OperationStatus.COMPLETED, models.OperationStatus.CANCELLED]),
            )
            .group_by(models.Machine.machine_id)
            .having(func.coalesce(func.sum(operation_hours), 0.0) > 10)
        )
        for machine, booked_hours in overloads.all():
            if await _notification_exists_today(db, tenant_id, "MACHINE_OVERLOAD", "MACHINE", str(machine.machine_id), now):
                created["duplicates_skipped"] += 1
                continue
            await create_notification(
                db=db,
                tenant_id=tenant_id,
                user_id=None,
                notif_type="MACHINE_OVERLOAD",
                title="Machine overload",
                message=f"{machine.name} has {round(float(booked_hours or 0), 2)} planned hours.",
                entity_ref=machine.name,
                entity_type="MACHINE",
                entity_id=str(machine.machine_id),
                created_at=now,
            )
            created["emails_sent"] += await _send_tenant_alert_email(
                db,
                tenant_id,
                subject=f"Roodha machine overload: {machine.name}",
                body=f"{machine.name} has {round(float(booked_hours or 0), 2)} planned hours.",
            )
            await record_event(
                db,
                tenant_id,
                "MACHINE_OVERLOAD",
                "MACHINE",
                str(machine.machine_id),
                {"machine_name": machine.name, "booked_hours": round(float(booked_hours or 0), 2)},
                flush_only=False,
            )
            created["machine_overloads"] += 1

    return ApiResponse(data=created, message="V1.5 nightly checks completed.")
