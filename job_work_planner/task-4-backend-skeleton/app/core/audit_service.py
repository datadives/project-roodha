"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: audit_service.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
# app/core/audit_service.py

from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from app import models

logger = logging.getLogger("jobwork-backend")


def serialize_audit_record(audit_record: models.AuditLog) -> dict:
    return {
        "audit_id": audit_record.audit_id,
        "tenant_id": audit_record.tenant_id,
        "entity_type": audit_record.entity_type,
        "entity_id": audit_record.entity_id,
        "action": audit_record.action,
        "user_id": audit_record.user_id,
        "before_state": audit_record.before_state or {},
        "after_state": audit_record.after_state or {},
        "timestamp": audit_record.timestamp,
    }

def log_audit_event(
    db: Session, # 👈 NEW: Database session parameter
    tenant_id: str,
    entity_type: str,  # 'JOB' or 'JOB_OPERATION'
    entity_id: str,
    action: str,       # e.g., 'CREATED', 'STATUS_CHANGED', 'PLANNED'
    user_id: str,
    before: dict | None = None,
    after: dict | None = None,
):
    """
    Writes an immutable audit record directly to AWS RDS PostgreSQL.
    """
    # Create the SQLAlchemy model instance
    audit_record = models.AuditLog(
        audit_id=f"AUD-{str(uuid.uuid4())[:8]}",
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        before_state=before or {}, # Maps to JSONB in DB
        after_state=after or {},   # Maps to JSONB in DB
        timestamp=datetime.utcnow().isoformat()
    )
    
    # Save to AWS RDS (Append-only / Immutable)
    db.add(audit_record)
    db.commit()
    db.refresh(audit_record)
    
    # Also dump to stdout/logger for infrastructure logging (CloudWatch/Datadog)
    logger.info(f"AUDIT | {entity_type} | {action} | User: {user_id}")
    
    return audit_record


async def log_audit_event_async(
    db: Session,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    user_id: str,
    before: dict | None = None,
    after: dict | None = None,
):
    """
    Asynchronous version of log_audit_event.
    """
    audit_record = models.AuditLog(
        audit_id=f"AUD-{str(uuid.uuid4())[:8]}",
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        before_state=before or {},
        after_state=after or {},
        timestamp=datetime.utcnow().isoformat()
    )
    
    db.add(audit_record)
    await db.commit()
    await db.refresh(audit_record)
    
    logger.info(f"AUDIT | {entity_type} | {action} | User: {user_id}")
    return audit_record


    return [serialize_audit_record(record) for record in trail]


async def get_audit_trail_async(db: Session, tenant_id: str, entity_type: str, entity_id: str):
    """
    Asynchronous version of get_audit_trail.
    """
    stmt = (
        select(models.AuditLog)
        .where(
            models.AuditLog.tenant_id == tenant_id,
            models.AuditLog.entity_type == entity_type,
            models.AuditLog.entity_id == entity_id
        )
        .order_by(models.AuditLog.timestamp.desc())
    )
    result = await db.execute(stmt)
    trail = result.scalars().all()
    
    return [serialize_audit_record(record) for record in trail]
