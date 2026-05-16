from datetime import date, datetime, time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/worklist", tags=["Work To List"])


def _require_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not user.get("tenant_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


def _as_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid UUID: {value}")


async def _validate_tenant_resource(
    db: AsyncSession,
    tenant_id: str,
    model,
    id_field_name: str,
    resource_id: UUID | None,
    label: str,
) -> None:
    """Reject cross-tenant or unknown resource IDs without revealing ownership."""
    if not resource_id:
        return
    result = await db.execute(
        select(getattr(model, id_field_name)).where(
            model.tenant_id == tenant_id,
            getattr(model, id_field_name) == resource_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found for tenant",
        )


@router.get("")
async def get_worklist(
    request: Request,
    machine_id: str | None = Query(None),
    worker_id: str | None = Query(None),
    shift_date: date | None = Query(None),
    shift_id: str | None = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    user = _require_user(request)
    tenant_id = user["tenant_id"]
    role = str(user.get("role") or "").upper()
    requested_machine_id = _as_uuid(machine_id)
    requested_worker_id = _as_uuid(worker_id)
    requested_shift_id = _as_uuid(shift_id)

    if role == "OPERATOR":
        assigned_machine_id = user.get("machine_id")
        assigned_worker_id = user.get("worker_id")
        if assigned_machine_id:
            requested_machine_id = UUID(str(assigned_machine_id))
        elif assigned_worker_id:
            requested_worker_id = UUID(str(assigned_worker_id))
        else:
            return api_success({"items": []}, message="No operator assignment found")

    await _validate_tenant_resource(db, tenant_id, models.Machine, "machine_id", requested_machine_id, "Machine")
    await _validate_tenant_resource(db, tenant_id, models.Worker, "worker_id", requested_worker_id, "Worker")
    await _validate_tenant_resource(db, tenant_id, models.Shift, "shift_id", requested_shift_id, "Shift")

    stmt = (
        select(
            models.JobOperation,
            models.Job,
            models.OperationsMaster,
            models.Part,
            models.Customer,
            models.Machine,
            models.Worker,
        )
        .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
        .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id)
        .join(models.Part, models.Part.part_id == models.Job.part_id, isouter=True)
        .join(models.Customer, models.Customer.customer_id == models.Job.customer_id, isouter=True)
        .join(models.Machine, models.Machine.machine_id == models.JobOperation.machine_id, isouter=True)
        .join(models.Worker, models.Worker.worker_id == models.JobOperation.worker_id, isouter=True)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
        )
        .order_by(
            models.JobOperation.planned_start_date.asc().nulls_last(),
            models.Job.due_date.asc().nulls_last(),
            models.JobOperation.sequence_number.asc(),
        )
    )
    if requested_machine_id:
        stmt = stmt.where(models.JobOperation.machine_id == requested_machine_id)
    if requested_worker_id:
        stmt = stmt.where(models.JobOperation.worker_id == requested_worker_id)
    if requested_shift_id:
        stmt = stmt.where(models.JobOperation.shift_id == requested_shift_id)
    if shift_date:
        start = datetime.combine(shift_date, time.min)
        end = datetime.combine(shift_date, time.max)
        stmt = stmt.where(models.JobOperation.planned_start_date >= start, models.JobOperation.planned_start_date <= end)

    result = await db.execute(stmt)
    items = []
    for operation, job, operation_master, part, customer, machine, worker in result.all():
        previous_status = "READY"
        if operation.sequence_number > 1:
            previous = await db.execute(
                select(models.JobOperation.status).where(
                    models.JobOperation.tenant_id == tenant_id,
                    models.JobOperation.job_id == job.job_id,
                    models.JobOperation.sequence_number == operation.sequence_number - 1,
                )
            )
            previous_status = previous.scalar_one_or_none() or "UNKNOWN"
            previous_status = previous_status.value if hasattr(previous_status, "value") else str(previous_status)
            if previous_status != models.OperationStatus.COMPLETED.value:
                continue
        items.append(
            {
                "job_operation_id": str(operation.job_op_id),
                "job_id": str(job.job_id),
                "job_number": job.job_number,
                "operation_name": operation_master.name,
                "sequence_number": operation.sequence_number,
                "part_number": part.part_number if part else "",
                "part_name": part.description if part else "",
                "customer_name": customer.name if customer else "",
                "quantity": job.quantity,
                "tags": getattr(job, "tags_json", None) or [],
                "status": operation.status.value if hasattr(operation.status, "value") else str(operation.status),
                "previous_operation_status": previous_status,
                "machine_id": str(operation.machine_id) if operation.machine_id else None,
                "machine_name": machine.name if machine else None,
                "worker_id": str(operation.worker_id) if operation.worker_id else None,
                "worker_name": worker.name if worker else None,
                "planned_start_date": operation.planned_start_date,
                "planned_end_date": operation.planned_end_date,
                "due_date": job.due_date,
            }
        )
    return api_success({"items": items}, message="Worklist ready")
