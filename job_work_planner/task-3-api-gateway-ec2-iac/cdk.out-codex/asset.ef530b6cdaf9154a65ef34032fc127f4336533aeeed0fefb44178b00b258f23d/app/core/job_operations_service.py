"""
job_operations_service.py
-------------------------
Core Business Logic for Job Operations.
"""

from datetime import datetime
import uuid
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app import models
from app.core.audit_service import log_audit_event

logger = logging.getLogger("jobwork-backend")

class CapacityConflictError(Exception):
    def __init__(self, message, clashes=None):
        super().__init__(message)
        self.clashes = clashes or []
        self.message = message


ALLOWED_OPERATION_STATUSES = {
    "NOT_STARTED",
    "PLANNED",
    "READY",
    "IN_PROGRESS",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
}


def _serialize_job_operation(operation: models.JobOperation) -> dict:
    return {
        "job_operation_id": operation.job_operation_id,
        "tenant_id": operation.tenant_id,
        "job_id": operation.job_id,
        "operation_id": operation.operation_id,
        "machine_id": operation.machine_id,
        "shift_id": operation.shift_id,
        "sequence_number": operation.sequence_number,
        "status": operation.status,
        "actual_start_time": operation.actual_start_time,
        "actual_end_time": operation.actual_end_time,
        "planned_start_date": operation.planned_start_date,
        "planned_end_date": operation.planned_end_date,
    }


def _serialize_production_entry(entry: models.ProductionEntry) -> dict:
    return {
        "entry_id": entry.entry_id,
        "tenant_id": entry.tenant_id,
        "job_operation_id": entry.job_operation_id,
        "operator_id": entry.operator_id,
        "produced_qty": entry.produced_qty,
        "scrap_qty": entry.scrap_qty,
        "rework_qty": entry.rework_qty,
        "timestamp": entry.timestamp,
    }


def _validate_status_transition(current_status: str, new_status: str, override_sequence: bool = False):
    normalized_current = (current_status or "").strip().upper()
    normalized_new = (new_status or "").strip().upper()

    if normalized_new not in ALLOWED_OPERATION_STATUSES:
        raise ValueError(f"Unsupported operation status: {normalized_new}")

    if override_sequence:
        return

    if normalized_new == "COMPLETED" and normalized_current != "IN_PROGRESS":
        raise ValueError("Operation must be IN_PROGRESS before it can be marked COMPLETED")


def _sync_parent_job_status(db: Session, tenant_id: str, job_id: str):
    job = db.query(models.Job).filter(
        models.Job.job_id == job_id,
        models.Job.tenant_id == tenant_id,
    ).first()
    if not job:
        return

    operations = db.query(models.JobOperation).filter(
        models.JobOperation.job_id == job_id,
        models.JobOperation.tenant_id == tenant_id,
    ).all()

    if not operations:
        return

    operation_statuses = {(operation.status or "").strip().upper() for operation in operations}
    if operation_statuses and operation_statuses.issubset({"COMPLETED"}):
        job.status = "COMPLETED"
    elif operation_statuses.intersection({"IN_PROGRESS", "PAUSED"}) or "COMPLETED" in operation_statuses:
        job.status = "IN_PROGRESS"
    else:
        job.status = "NOT_STARTED"


def _validate_planning_dates(planned_start_date: str | None, planned_end_date: str | None):
    if bool(planned_start_date) != bool(planned_end_date):
        raise ValueError("Planned start date and planned end date must be provided together")

    if planned_start_date and planned_end_date and planned_end_date < planned_start_date:
        raise ValueError("Planned end date must be on or after the planned start date")


def _build_capacity_clashes(
    db: Session,
    tenant_id: str,
    job_operation_id: str,
    machine_id: str,
    shift_id: str | None,
    planned_start_date: str,
    planned_end_date: str,
):
    query = db.query(models.JobOperation).filter(
        models.JobOperation.tenant_id == tenant_id,
        models.JobOperation.job_operation_id != job_operation_id,
        models.JobOperation.machine_id == machine_id,
        models.JobOperation.planned_start_date.isnot(None),
        models.JobOperation.planned_end_date.isnot(None),
        models.JobOperation.status.notin_(["COMPLETED", "CANCELLED"]),
        models.JobOperation.planned_start_date <= planned_end_date,
        models.JobOperation.planned_end_date >= planned_start_date,
    )

    if shift_id:
        query = query.filter(
            or_(models.JobOperation.shift_id == shift_id, models.JobOperation.shift_id.is_(None))
        )

    clashes = query.order_by(models.JobOperation.planned_start_date.asc()).all()
    if not clashes:
        return []

    jobs = {
        job.job_id: job.job_number
        for job in db.query(models.Job).filter(
            models.Job.tenant_id == tenant_id,
            models.Job.job_id.in_([operation.job_id for operation in clashes]),
        ).all()
    }

    return [
        {
            "job_operation_id": operation.job_operation_id,
            "job_id": operation.job_id,
            "job_number": jobs.get(operation.job_id, operation.job_id),
            "machine_id": operation.machine_id,
            "shift_id": operation.shift_id,
            "status": operation.status,
            "planned_start_date": operation.planned_start_date,
            "planned_end_date": operation.planned_end_date,
            "sequence_number": operation.sequence_number,
        }
        for operation in clashes
    ]

# -------------------------------------------------------
# SCRUM 25: Auto-generate Job Operations from Part Route
# -------------------------------------------------------
def create_job_operations(
    db: Session,
    job_id: str,
    part_id: str,
    tenant_id: str,
    user_id: str | None = None,
):
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

    valid_operation_ids = {
        operation_id
        for (operation_id,) in db.query(models.OperationsMaster.operation_id)
        .filter(models.OperationsMaster.tenant_id == tenant_id)
        .all()
    }

    created_ops = []
    # 2. Iterate through the JSON route
    # Expecting format: [{"operation_id": "op-1", "sequence": 1}, ...]
    for route_item in sorted(part.default_operations_route, key=lambda item: item.get("sequence", 0)):
        operation_id = route_item.get("operation_id")
        if operation_id not in valid_operation_ids:
            raise ValueError(
                f"Part route references unknown operation_id '{operation_id}' for tenant {tenant_id}"
            )
        new_op = models.JobOperation(
            job_operation_id=f"JOP-{str(uuid.uuid4())[:8]}",
            tenant_id=tenant_id,
            job_id=job_id,
            operation_id=operation_id,
            sequence_number=route_item.get("sequence", 0),
            status="READY" # Default starting status
        )
        db.add(new_op)
        created_ops.append(new_op)

    db.commit()

    for operation in created_ops:
        db.refresh(operation)
        if user_id:
            log_audit_event(
                db=db,
                tenant_id=tenant_id,
                entity_type="JOB_OPERATION",
                entity_id=operation.job_operation_id,
                action="CREATED",
                user_id=user_id,
                after=_serialize_job_operation(operation),
            )

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

    before_state = _serialize_job_operation(operation)
    normalized_status = new_status.strip().upper()
    _validate_status_transition(
        current_status=operation.status,
        new_status=normalized_status,
        override_sequence=bool(kwargs.get("override_sequence")),
    )
    operation.status = normalized_status

    # Use caller-supplied timestamps if provided; otherwise auto-stamp.
    caller_start = kwargs.get("actual_start_time")
    caller_end = kwargs.get("actual_end_time")

    if normalized_status == "IN_PROGRESS" and not operation.actual_start_time:
        if caller_start:
            try:
                operation.actual_start_time = datetime.fromisoformat(str(caller_start))
            except ValueError:
                operation.actual_start_time = datetime.utcnow()
        else:
            operation.actual_start_time = datetime.utcnow()
    elif normalized_status == "COMPLETED":
        if caller_end:
            try:
                operation.actual_end_time = datetime.fromisoformat(str(caller_end))
            except ValueError:
                operation.actual_end_time = datetime.utcnow()
        else:
            operation.actual_end_time = datetime.utcnow()
        # Also capture start if somehow still missing
        if not operation.actual_start_time:
            operation.actual_start_time = datetime.utcnow()

    _sync_parent_job_status(db, tenant_id, operation.job_id)

    db.commit()
    db.refresh(operation)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=operation.job_operation_id,
        action="STATUS_CHANGED",
        user_id=user_id,
        before=before_state,
        after=_serialize_job_operation(operation),
    )

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
    _validate_planning_dates(planned_start_date, planned_end_date)

    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise ValueError("Operation not found")

    machine = db.query(models.Machine).filter(
        models.Machine.machine_id == machine_id,
        models.Machine.tenant_id == tenant_id,
    ).first()
    if not machine:
        raise ValueError("Machine not found")
    if machine.is_active is False:
        raise ValueError("Machine is inactive and cannot be assigned")

    if shift_id:
        shift = db.query(models.Shift).filter(
            models.Shift.shift_id == shift_id,
            models.Shift.tenant_id == tenant_id,
        ).first()
        if not shift:
            raise ValueError("Shift not found")

    ignore_conflicts = bool(kwargs.get("ignore_conflicts") or kwargs.get("force"))
    override_reason = kwargs.get("reschedule_reason")
    if ignore_conflicts and not override_reason:
        raise ValueError("A reason is required when overriding planning conflicts")

    if planned_start_date and planned_end_date and not ignore_conflicts:
        clashes = _build_capacity_clashes(
            db=db,
            tenant_id=tenant_id,
            job_operation_id=job_operation_id,
            machine_id=machine_id,
            shift_id=shift_id,
            planned_start_date=planned_start_date,
            planned_end_date=planned_end_date,
        )
        if clashes:
            raise CapacityConflictError(
                "The selected machine already has planned work in the requested window.",
                clashes=clashes,
            )

    before_state = _serialize_job_operation(operation)
    operation.machine_id = machine_id
    operation.shift_id = shift_id
    
    # These columns must exist in models.py (JobOperation class)
    if hasattr(operation, 'planned_start_date'):
        operation.planned_start_date = planned_start_date
    if hasattr(operation, 'planned_end_date'):
        operation.planned_end_date = planned_end_date

    db.commit()
    db.refresh(operation)

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=operation.job_operation_id,
        action="PLANNED",
        user_id=kwargs.get("user_id", "system"),
        before=before_state,
        after=_serialize_job_operation(operation),
    )

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
    operation = db.query(models.JobOperation).filter(
        models.JobOperation.job_operation_id == job_operation_id,
        models.JobOperation.tenant_id == tenant_id
    ).first()

    if not operation:
        raise ValueError("Operation not found")

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

    log_audit_event(
        db=db,
        tenant_id=tenant_id,
        entity_type="JOB_OPERATION",
        entity_id=operation.job_operation_id,
        action="PRODUCTION_RECORDED",
        user_id=operator_id,
        before=_serialize_job_operation(operation),
        after={
            "job_operation": _serialize_job_operation(operation),
            "production_entry": _serialize_production_entry(new_entry),
            "notes": kwargs.get("notes"),
        },
    )

    return new_entry
