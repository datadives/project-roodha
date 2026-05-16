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
from datetime import date, datetime, time, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from sqlalchemy import case, cast, Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.auth_middleware import require_roles
from app.core.planning_service import get_planning_calendar_service, get_machine_load_service
from app.core.event_service import record_event
from app.schemas.value_features import AutoScheduleApplyRequest, AutoSchedulePreviewRequest, AutoScheduleResponse
from app.database import get_async_db
from app.routes.response_utils import api_success

router = APIRouter(prefix="/planning", tags=["Planning Calendar"])
logger = logging.getLogger("jobwork-backend")
MACHINE_DAILY_CAPACITY_HOURS = 10.0
SCHEDULER_SHIFT_CAPACITY_HOURS = 8.0


def select_capacity_machine(machines, load_by_machine: dict[str, float]):
    """Choose the least-loaded machine that is still below the daily capacity cap."""
    available_machines = [
        machine
        for machine in machines
        if float(load_by_machine.get(str(machine.machine_id), 0.0)) < MACHINE_DAILY_CAPACITY_HOURS
    ]
    if not available_machines:
        return None

    return min(
        available_machines,
        key=lambda machine: load_by_machine.get(str(machine.machine_id), 0.0),
    )


def _normalize_machine_type(value: str | None) -> str:
    return str(value or "").strip().lower()


def _estimated_hours(quantity: int | None, cycle_minutes: int | None) -> float:
    cycle_time = float(cycle_minutes or 0)
    if cycle_time <= 0:
        return 0.1
    return round((float(quantity or 1) * cycle_time) / 60.0, 2)


def _date_start(value: date | None) -> datetime:
    return datetime.combine(value or date.today(), time.min)


def _date_end(value: date | None) -> datetime:
    end_date = value or (date.today() + timedelta(days=7))
    return datetime.combine(end_date, time.max)


def _plan_days(from_day: date, to_day: date, due_date: datetime | None) -> list[date]:
    last_day = min(to_day, due_date.date()) if due_date else to_day
    if last_day < from_day:
        last_day = from_day
    return [from_day + timedelta(days=offset) for offset in range((last_day - from_day).days + 1)]


async def _daily_machine_loads(db: AsyncSession, tenant_id: str, from_dt: datetime, to_dt: datetime) -> dict[tuple[str, date], float]:
    operation_hours = case(
        (models.OperationsMaster.standard_cycle_time_mins <= 0, 0.1),
        else_=(cast(models.Job.quantity, Float) * cast(models.OperationsMaster.standard_cycle_time_mins, Float)) / 60.0,
    )
    result = await db.execute(
        select(
            models.JobOperation.machine_id,
            func.date(func.coalesce(models.JobOperation.planned_start_date, models.Job.due_date, models.Job.created_at)).label("plan_day"),
            func.coalesce(func.sum(operation_hours), 0.0).label("booked_hours"),
        )
        .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
        .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.machine_id.isnot(None),
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
            func.coalesce(models.JobOperation.planned_start_date, models.Job.due_date, models.Job.created_at) >= from_dt,
            func.coalesce(models.JobOperation.planned_start_date, models.Job.due_date, models.Job.created_at) <= to_dt,
        )
        .group_by(models.JobOperation.machine_id, "plan_day")
    )
    return {
        (str(row.machine_id), row.plan_day): float(row.booked_hours or 0)
        for row in result.all()
        if row.machine_id and row.plan_day
    }


async def build_auto_schedule_suggestions(
    db: AsyncSession,
    tenant_id: str,
    payload: AutoSchedulePreviewRequest,
) -> list[dict]:
    from_dt = _date_start(payload.from_date)
    to_dt = _date_end(payload.to_date)
    limit = min(max(int(payload.limit or 50), 1), 100)

    machine_result = await db.execute(
        select(models.Machine).where(
            models.Machine.tenant_id == tenant_id,
            models.Machine.is_active == True,  # noqa: E712
        )
    )
    machines = machine_result.scalars().all()
    loads = await _daily_machine_loads(db, tenant_id, from_dt, to_dt)

    stmt = (
        select(models.JobOperation, models.Job, models.OperationsMaster)
        .join(models.Job, models.JobOperation.job_id == models.Job.job_id)
        .join(models.OperationsMaster, models.JobOperation.op_id == models.OperationsMaster.operation_id)
        .where(
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.status.notin_([
                models.OperationStatus.COMPLETED,
                models.OperationStatus.CANCELLED,
            ]),
        )
        .order_by(models.Job.due_date.asc().nulls_last(), models.JobOperation.sequence_number.asc())
        .limit(limit)
    )
    if payload.job_ids:
        stmt = stmt.where(models.Job.job_id.in_(payload.job_ids))

    result = await db.execute(stmt)
    suggestions = []
    for operation, job, operation_master in result.all():
        estimated_hours = _estimated_hours(job.quantity, operation_master.standard_cycle_time_mins)
        wanted_type = _normalize_machine_type(operation_master.default_machine_type)
        candidates = [
            machine for machine in machines
            if not wanted_type or _normalize_machine_type(machine.type) == wanted_type
        ]

        plan_days = _plan_days(from_dt.date(), to_dt.date(), job.due_date)
        selected_machine = None
        selected_day = None
        conflict_reason = None
        if not candidates:
            conflict_reason = (
                f"No active machine matches {operation_master.default_machine_type}"
                if wanted_type
                else "No active machines available"
            )
        else:
            candidate_slots = []
            for machine in candidates:
                for plan_day in plan_days:
                    current = loads.get((str(machine.machine_id), plan_day), 0.0)
                    remaining = SCHEDULER_SHIFT_CAPACITY_HOURS - current
                    if remaining >= estimated_hours:
                        candidate_slots.append((remaining, current, machine, plan_day))
            if candidate_slots:
                _remaining, _current, selected_machine, selected_day = min(
                    candidate_slots,
                    key=lambda slot: (slot[3].toordinal(), -slot[0], slot[1]),
                )
            else:
                conflict_reason = f"No shift capacity available within {SCHEDULER_SHIFT_CAPACITY_HOURS:g}h/day"

        if selected_machine:
            key = (str(selected_machine.machine_id), selected_day)
            current_load = loads.get(key, 0.0)
            start_hour = min(current_load, SCHEDULER_SHIFT_CAPACITY_HOURS)
            planned_start = datetime.combine(selected_day, time(hour=8)) + timedelta(hours=start_hour)
            planned_end = planned_start + timedelta(hours=estimated_hours)
            projected = current_load + estimated_hours
            loads[key] = projected
        else:
            planned_start = None
            planned_end = None

        suggestions.append(
            {
                "job_operation_id": operation.job_op_id,
                "job_id": operation.job_id,
                "job_number": job.job_number,
                "operation_name": operation_master.name,
                "sequence_number": operation.sequence_number,
                "machine_id": selected_machine.machine_id if selected_machine else None,
                "planned_machine_id": selected_machine.machine_id if selected_machine else None,
                "machine_name": selected_machine.name if selected_machine else None,
                "planned_start_date": planned_start,
                "planned_end_date": planned_end,
                "due_date": job.due_date,
                "due_date_risk": bool(planned_end and job.due_date and planned_end > job.due_date),
                "estimated_hours": estimated_hours,
                "reason": "Best capacity fit before due date" if selected_machine else "Needs manual planning",
                "conflict_reason": conflict_reason,
            }
        )
    return suggestions


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
    from_date: date | None = Query(None, description="Optional planned start date lower bound"),
    to_date: date | None = Query(None, description="Optional planned start date upper bound"),
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    """
    GET /api/planning/machine-load
    Returns tenant-scoped total booked hours per machine for active operations.
    """
    tenant_id = user["tenant_id"]
    try:
        operation_hours = case(
            (models.OperationsMaster.standard_cycle_time_mins <= 0, 0.1),
            else_=(cast(models.Job.quantity, Float) * cast(models.OperationsMaster.standard_cycle_time_mins, Float)) / 60.0,
        )
        booked_hours = func.coalesce(func.sum(operation_hours), 0.0)
        operation_count = func.count(models.JobOperation.job_operation_id)
        filters = [
            models.Machine.tenant_id == tenant_id,
            models.JobOperation.tenant_id == tenant_id,
            models.Job.tenant_id == tenant_id,
            models.OperationsMaster.tenant_id == tenant_id,
            models.JobOperation.machine_id.isnot(None),
            models.JobOperation.status.in_([
                models.OperationStatus.NOT_STARTED,
                models.OperationStatus.IN_PROGRESS,
            ]),
        ]
        if from_date:
            filters.append(func.date(models.JobOperation.planned_start_date) >= from_date)
        if to_date:
            filters.append(func.date(models.JobOperation.planned_start_date) <= to_date)

        result = await db.execute(
            select(
                models.Machine.machine_id,
                models.Machine.name.label("machine_name"),
                operation_count.label("operation_count"),
                booked_hours.label("booked_hours"),
            )
            .join(models.JobOperation, models.JobOperation.machine_id == models.Machine.machine_id)
            .join(models.Job, models.Job.job_id == models.JobOperation.job_id)
            .join(models.OperationsMaster, models.OperationsMaster.operation_id == models.JobOperation.op_id)
            .where(*filters)
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
            "operation_count": int(row.operation_count or 0),
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
    suggestions = await build_auto_schedule_suggestions(
        db=db,
        tenant_id=user["tenant_id"],
        payload=AutoSchedulePreviewRequest(limit=25),
    )
    return AutoScheduleResponse(suggestions=suggestions)


@router.post("/auto-schedule/preview")
async def preview_auto_schedule(
    payload: AutoSchedulePreviewRequest,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    suggestions = await build_auto_schedule_suggestions(db, user["tenant_id"], payload)
    return api_success({"suggestions": suggestions}, message="Auto-plan preview ready")


@router.post("/auto-schedule/apply")
async def apply_auto_schedule(
    payload: AutoScheduleApplyRequest,
    user: dict = Depends(require_roles(["OWNER", "SUPERVISOR"])),
    db: AsyncSession = Depends(get_async_db),
):
    tenant_id = user["tenant_id"]
    applied = []
    for item in payload.suggestions:
        result = await db.execute(
            select(models.JobOperation).where(
                models.JobOperation.job_op_id == item.job_operation_id,
                models.JobOperation.tenant_id == tenant_id,
                models.JobOperation.status.notin_([
                    models.OperationStatus.COMPLETED,
                    models.OperationStatus.CANCELLED,
                ]),
            ).with_for_update()
        )
        operation = result.scalar_one_or_none()
        if not operation:
            continue
        machine_check = await db.execute(
            select(models.Machine.machine_id).where(
                models.Machine.machine_id == item.machine_id,
                models.Machine.tenant_id == tenant_id,
                models.Machine.is_active == True,  # noqa: E712
            )
        )
        if not machine_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected machine is inactive or unavailable for this tenant",
            )
        operation.machine_id = item.machine_id
        operation.planned_start_date = item.planned_start_date
        operation.planned_end_date = item.planned_end_date
        if operation.status == models.OperationStatus.NOT_STARTED:
            operation.status = models.OperationStatus.PLANNED
        await record_event(
            db,
            tenant_id=tenant_id,
            event_type="AUTO_PLAN_APPLIED",
            entity_type="JOB_OPERATION",
            entity_id=str(operation.job_op_id),
            payload={"machine_id": str(item.machine_id)},
        )
        applied.append(str(operation.job_op_id))
    await db.commit()
    return api_success({"applied": applied, "applied_count": len(applied)}, message="Auto-plan applied")

