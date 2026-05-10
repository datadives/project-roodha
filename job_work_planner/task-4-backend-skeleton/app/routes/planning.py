"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: planning.py
 * 
 * 1) Purpose: Defines API endpoints for planning.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from sqlalchemy import cast, Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.auth_middleware import require_roles
from app.core.planning_service import get_planning_calendar_service, get_machine_load_service
from app.schemas.value_features import AutoScheduleResponse
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/planning", tags=["Planning Calendar"])
logger = logging.getLogger("jobwork-backend")
MACHINE_DAILY_CAPACITY_HOURS = 10.0


def select_capacity_machine(machines, load_by_machine: dict[str, float]):
    """Choose the least-loaded machine that is still below the daily capacity cap."""
    available_machines = [
        machine
        for machine in machines
        if float(load_by_machine.get(str(machine.machine_id), 0.0)) <= MACHINE_DAILY_CAPACITY_HOURS
    ]
    if not available_machines:
        return None

    return min(
        available_machines,
        key=lambda machine: load_by_machine.get(str(machine.machine_id), 0.0),
    )


@router.get("")
async def get_planning_calendar(
    request: Request,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    machine_id: str | None = Query(None),
    shift_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    try:
        response = await get_planning_calendar_service(
            db=db,
            tenant_id=user["tenant_id"],
            from_date=from_date,
            to_date=to_date,
            machine_id=machine_id,
            shift_id=shift_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return api_success(response)


@router.get("/machine-load")
async def get_machine_load(
    request: Request,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    """
    GET /api/planning/machine-load
    Returns tenant-scoped total booked hours per machine for active operations.
    """
    tenant_id = user["tenant_id"]
    try:
        booked_hours = func.coalesce(
            func.sum(
                (cast(models.Job.quantity, Float) * cast(models.OperationsMaster.standard_cycle_time_mins, Float)) / 60.0
            ),
            0.0,
        )
        result = await db.execute(
            select(
                models.Machine.machine_id,
                models.Machine.name.label("machine_name"),
                booked_hours.label("booked_hours"),
            )
            .join(models.JobOperation, models.JobOperation.machine_id == models.Machine.machine_id)
            .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
            .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id)
            .where(
                models.Machine.tenant_id == tenant_id,
                models.JobOperation.tenant_id == tenant_id,
                models.Job.tenant_id == tenant_id,
                models.OperationsMaster.tenant_id == tenant_id,
                models.JobOperation.machine_id.isnot(None),
                models.JobOperation.status.in_([
                    models.OperationStatus.NOT_STARTED,
                    models.OperationStatus.IN_PROGRESS,
                ]),
            )
            .group_by(models.Machine.machine_id, models.Machine.name)
            .order_by(booked_hours.desc(), models.Machine.name.asc())
        )
    except Exception as exc:
        logger.exception("Failed to fetch machine load for tenant %s", tenant_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    machines = [
        {
            "machine_id": str(row.machine_id),
            "machine_name": row.machine_name,
            "booked_hours": round(float(row.booked_hours or 0), 2),
            "is_overloaded": float(row.booked_hours or 0) > 10,
        }
        for row in result.all()
    ]
    return api_success({"machines": machines}, message="Machine load synchronized")


@router.post("/auto-assign", response_model=AutoScheduleResponse)
@router.post("/auto-schedule", response_model=AutoScheduleResponse)
async def auto_schedule(
    request: Request,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    """
    POST /api/planning/auto-schedule
    Returns capacity-based machine suggestions for unplanned operations.
    This is a safe dry-run endpoint: it does not mutate plans until the user applies a suggestion.
    """
    tenant_id = user["tenant_id"]
    current_load = await get_machine_load_service(db, tenant_id)
    load_by_machine = {}
    for item in current_load:
        machine_id = str(item["machine_id"])
        load_by_machine[machine_id] = load_by_machine.get(machine_id, 0.0) + float(item["total_hours"] or 0)

    machine_result = await db.execute(
        select(models.Machine).where(
            models.Machine.tenant_id == tenant_id,
            models.Machine.is_active == True,  # noqa: E712
        )
    )
    machines = machine_result.scalars().all()
    if not machines:
        return AutoScheduleResponse(suggestions=[])

    result = await db.execute(
        select(models.JobOperation, models.Job, models.OperationsMaster)
        .join(models.Job, models.JobOperation.job_id == models.Job.job_id)
        .join(models.OperationsMaster, models.JobOperation.op_id == models.OperationsMaster.operation_id)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.machine_id.is_(None),
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
        )
        .order_by(models.Job.due_date.asc(), models.JobOperation.sequence_number.asc())
        .limit(25)
    )

    suggestions = []
    for operation, job, operation_master in result.all():
        cycle_time = float(operation_master.standard_cycle_time_mins or 6)
        estimated_hours = round((float(job.quantity or 1) * cycle_time) / 60.0, 2)
        selected_machine = select_capacity_machine(machines, load_by_machine)
        if not selected_machine:
            logger.warning("AUTO_SCHEDULE | no available machine capacity for tenant=%s", tenant_id)
            break

        machine_key = str(selected_machine.machine_id)
        projected_hours = load_by_machine.get(machine_key, 0.0) + estimated_hours
        load_by_machine[machine_key] = projected_hours

        suggestions.append(
            {
                "job_operation_id": operation.job_op_id,
                "job_id": operation.job_id,
                "machine_id": selected_machine.machine_id,
                "machine_name": selected_machine.name,
                "estimated_hours": estimated_hours,
                "reason": (
                    "Best current capacity fit"
                    if projected_hours <= 10
                    else "Least-loaded machine, but projected load exceeds 10h"
                ),
            }
        )

    return AutoScheduleResponse(suggestions=suggestions)

