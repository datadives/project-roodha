"""
job_operations_service.py
-------------------------
Core Business Logic for Job Operations.
"""

from datetime import datetime
import uuid
import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger("jobwork-backend")

class CapacityConflictError(Exception):
    def __init__(self, message, clashes=None):
        super().__init__(message)
        self.clashes = clashes or []
        self.message = message

# -------------------------------------------------------
# SCRUM 25: Auto-generate Job Operations from Part Route
# -------------------------------------------------------
def create_job_operations(db: Session, job_id: str, part_id: str, tenant_id: str):
    """
    Reads the default route from the Part model and creates 
    individual JobOperation records in AWS RDS.
    """
    # 1. Fetch the Part to get its default route (JSONB)
    part = db.query(models.Part).filter(
        models.Part.part_id == part_id,
        models.Part.tenant_id == tenant_id
    ).first()

    if not part or not part.default_operations_route:
        logger.warning(f"No route found for part {part_id}")
        return []

    created_ops = []
    # 2. Iterate through the JSON route
    # Expecting format: [{"operation_id": "op-1", "sequence": 1}, ...]
    for route_item in part.default_operations_route:
        new_op = models.JobOperation(
            job_operation_id=f"JOP-{str(uuid.uuid4())[:8]}",
            tenant_id=tenant_id,
            job_id=job_id,
            operation_id=route_item.get("operation_id"),
            sequence_number=route_item.get("sequence", 0),
            status="READY" # Default starting status
        )
        db.add(new_op)
        created_ops.append(new_op)

    db.commit()
    return created_ops

# -------------------------------------------------------
# SCRUM 28 + 31: Update Status & Timestamps
# -------------------------------------------------------
def update_job_operation_status(
    db: Session,
    job_operation_id: str,
    tenant_id: str,
    user_id: str,
    new_status: str,
    **kwargs
):
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise ValueError("Operation not found")

    # Update logic
    operation.status = new_status
    
    if new_status == "IN_PROGRESS" and not operation.actual_start_time:
        operation.actual_start_time = datetime.utcnow().isoformat()
    elif new_status == "COMPLETED":
        operation.actual_end_time = datetime.utcnow().isoformat()

    db.commit()
    db.refresh(operation)
    return operation

# -------------------------------------------------------
# SCRUM 29 + 34: Planning Service
# -------------------------------------------------------
def plan_job_operation_service(
    db: Session,
    job_operation_id: str,
    machine_id: str,
    tenant_id: str,
    shift_id: str = None,
    planned_start_date: str = None,
    planned_end_date: str = None,
    **kwargs
):
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise ValueError("Operation not found")

    # Assign machine and schedule
    operation.machine_id = machine_id
    operation.shift_id = shift_id
    
    # These columns must exist in models.py (JobOperation class)
    if hasattr(operation, 'planned_start_date'):
        operation.planned_start_date = planned_start_date
    if hasattr(operation, 'planned_end_date'):
        operation.planned_end_date = planned_end_date

    db.commit()
    db.refresh(operation)
    return operation

# -------------------------------------------------------
# SCRUM 32: Production Entry
# -------------------------------------------------------
def add_production_entry_service(
    db: Session,
    job_operation_id: str,
    tenant_id: str,
    produced_qty: int,
    operator_id: str,
    **kwargs
):
    new_entry = models.ProductionEntry(
        entry_id=f"PRD-{str(uuid.uuid4())[:8]}",
        tenant_id=tenant_id,
        job_operation_id=job_operation_id,
        operator_id=operator_id,
        produced_qty=produced_qty,
        scrap_qty=kwargs.get("scrap_qty", 0),
        rework_qty=kwargs.get("rework_qty", 0),
        timestamp=datetime.utcnow().isoformat()
    )
    
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return new_entry