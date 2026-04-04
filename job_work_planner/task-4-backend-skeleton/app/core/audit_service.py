# app/core/audit_service.py

from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")

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


def get_audit_trail(db: Session, tenant_id: str, entity_type: str, entity_id: str):
    """
    Retrieves the audit trail from AWS RDS, strictly enforcing tenant isolation.
    """
    # Query the database, filter strictly by tenant, and sort newest-first
    trail = db.query(models.AuditLog).filter(
        models.AuditLog.tenant_id == tenant_id,
        models.AuditLog.entity_type == entity_type,
        models.AuditLog.entity_id == entity_id
    ).order_by(
        models.AuditLog.timestamp.desc()
    ).all()
    
    return trail