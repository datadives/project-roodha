"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: proactive_delay_guard.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.notification_service import create_notification


def calculate_alert_priority(due_date: datetime | None) -> str:
    """ProactiveDelayGuard v1.5.6 - Section 7.3 Notifications."""
    if not due_date:
        return "NORMAL"

    now = datetime.now(timezone.utc)
    normalized_due = due_date
    if normalized_due.tzinfo is None:
        normalized_due = normalized_due.replace(tzinfo=timezone.utc)

    if normalized_due < now:
        return "CRITICAL"
    if normalized_due <= now + timedelta(hours=24):
        return "HIGH"
    return "NORMAL"


async def evaluate_tenant_delays(db: AsyncSession, tenant_id: str) -> dict:
    """
    Evaluate active jobs for overdue / near-due risk and create tenant-wide
    delay notifications. Existing unread notifications for the same job are
    reused to keep manual and scheduled triggers idempotent.
    """
    now = datetime.now(timezone.utc)
    naive_now = now.replace(tzinfo=None)
    naive_threshold = (now + timedelta(hours=24)).replace(tzinfo=None)

    jobs_stmt = (
        select(models.Job)
        .where(
            models.Job.tenant_id == tenant_id,
            models.Job.status != models.JobStatus.COMPLETED,
            models.Job.due_date.is_not(None),
            models.Job.due_date <= naive_threshold,
        )
        .order_by(models.Job.due_date.asc())
    )
    jobs_result = await db.execute(jobs_stmt)
    at_risk_jobs = jobs_result.scalars().all()

    created_notifications = []
    skipped_existing = 0

    for job in at_risk_jobs:
        priority = calculate_alert_priority(job.due_date)
        if priority == "NORMAL":
            continue

        entity_ref = str(job.job_number or job.job_id)
        existing_stmt = select(models.Notification.notification_id).where(
            models.Notification.tenant_id == tenant_id,
            models.Notification.type == "DELAY",
            models.Notification.entity_reference == entity_ref,
            models.Notification.is_read == False,  # noqa: E712
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            skipped_existing += 1
            continue

        due_label = job.due_date.isoformat() if job.due_date else "unknown"
        if priority == "CRITICAL":
            message = f"Job {entity_ref} is overdue. Due date was {due_label}."
        else:
            message = f"Job {entity_ref} is due within 24 hours. Due date: {due_label}."

        notification = await create_notification(
            db=db,
            tenant_id=tenant_id,
            user_id=None,
            notif_type="DELAY",
            message=message,
            entity_ref=entity_ref,
        )
        created_notifications.append(
            {
                "notification_id": str(notification.notification_id),
                "job_id": str(job.job_id),
                "job_number": job.job_number,
                "priority": priority,
                "due_date": due_label,
            }
        )

    return {
        "tenant_id": tenant_id,
        "evaluated_at": naive_now.isoformat(),
        "jobs_evaluated": len(at_risk_jobs),
        "notifications_created": len(created_notifications),
        "notifications_skipped_existing": skipped_existing,
        "created": created_notifications,
    }
