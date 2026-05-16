from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app import models
from app.routes.planning import (
    SCHEDULER_SHIFT_CAPACITY_HOURS,
    apply_auto_schedule,
    build_auto_schedule_suggestions,
)
from app.schemas.value_features import AutoScheduleApplyRequest, AutoSchedulePreviewRequest


TENANT_ID = "tenant-scheduler-edge-test"
LATHE_ID = UUID("11111111-1111-4111-8111-111111111111")
INACTIVE_MACHINE_ID = UUID("99999999-9999-4999-8999-999999999999")


class FakeScalarList:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSchedulerDB:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeScalarList([
                SimpleNamespace(
                    machine_id=LATHE_ID,
                    tenant_id=TENANT_ID,
                    name="Lathe-01",
                    type="Lathe",
                    is_active=True,
                )
            ])
        if self.calls == 2:
            return FakeRows([])
        return FakeRows(self.rows)


class FakeNoCapacitySchedulerDB(FakeSchedulerDB):
    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeScalarList([
                SimpleNamespace(
                    machine_id=LATHE_ID,
                    tenant_id=TENANT_ID,
                    name="Lathe-01",
                    type="Lathe",
                    is_active=True,
                )
            ])
        if self.calls == 2:
            return FakeRows([
                SimpleNamespace(
                    machine_id=LATHE_ID,
                    plan_day=date.today(),
                    booked_hours=SCHEDULER_SHIFT_CAPACITY_HOURS,
                )
            ])
        return FakeRows(self.rows)


class FakeInactiveApplyDB:
    def __init__(self):
        self.calls = 0
        self.committed = False

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return FakeScalar(
                SimpleNamespace(
                    job_op_id=uuid4(),
                    tenant_id=TENANT_ID,
                    status=models.OperationStatus.NOT_STARTED,
                )
            )
        return FakeScalar(None)

    async def commit(self):
        self.committed = True


def make_scheduler_rows():
    rows = []
    horizon_end = datetime.combine(date.today() + timedelta(days=6), datetime.max.time())
    for index in range(50):
        blank_cycle_time = index < 5
        job_id = uuid4()
        rows.append(
            (
                SimpleNamespace(
                    job_op_id=uuid4(),
                    job_id=job_id,
                    tenant_id=TENANT_ID,
                    sequence_number=1,
                    status=models.OperationStatus.NOT_STARTED,
                ),
                SimpleNamespace(
                    job_id=job_id,
                    tenant_id=TENANT_ID,
                    job_number=f"HP-LATHE-{index + 1:03d}",
                    quantity=2,
                    due_date=horizon_end,
                    priority="HIGH",
                    created_at=datetime.now(UTC),
                ),
                SimpleNamespace(
                    operation_id=uuid4(),
                    tenant_id=TENANT_ID,
                    name="Lathe Turning",
                    default_machine_type="Lathe",
                    standard_cycle_time_mins=None if blank_cycle_time else 60,
                ),
            )
        )
    return rows


def make_missing_cycle_time_rows(count=10):
    rows = []
    for index in range(count):
        job_id = uuid4()
        rows.append(
            (
                SimpleNamespace(
                    job_op_id=uuid4(),
                    job_id=job_id,
                    tenant_id=TENANT_ID,
                    sequence_number=1,
                    status=models.OperationStatus.NOT_STARTED,
                ),
                SimpleNamespace(
                    job_id=job_id,
                    tenant_id=TENANT_ID,
                    job_number=f"NO-CYCLE-{index + 1:03d}",
                    quantity=5,
                    due_date=datetime.combine(date.today(), datetime.max.time()),
                    priority="HIGH",
                    created_at=datetime.now(UTC),
                ),
                SimpleNamespace(
                    operation_id=uuid4(),
                    tenant_id=TENANT_ID,
                    name="Lathe Turning",
                    default_machine_type="Lathe",
                    standard_cycle_time_mins=None,
                ),
            )
        )
    return rows


@pytest.mark.asyncio
async def test_auto_scheduler_respects_8h_capacity_and_uses_cycle_time_fallback():
    rows = make_scheduler_rows()
    db = FakeSchedulerDB(rows)

    suggestions = await build_auto_schedule_suggestions(
        db=db,
        tenant_id=TENANT_ID,
        payload=AutoSchedulePreviewRequest(
            from_date=date.today(),
            to_date=date.today() + timedelta(days=6),
            limit=50,
        ),
    )

    assigned = [item for item in suggestions if item["machine_id"]]
    blocked = [item for item in suggestions if not item["machine_id"]]
    fallback_rows = [item for item in suggestions if item["job_number"] in {f"HP-LATHE-{i:03d}" for i in range(1, 6)}]
    load_by_day = {}
    for item in assigned:
        plan_day = item["planned_start_date"].date()
        load_by_day[plan_day] = load_by_day.get(plan_day, 0.0) + float(item["estimated_hours"])

    print(
        "SCHEDULER_CAPACITY "
        f"jobs={len(suggestions)} assigned={len(assigned)} blocked={len(blocked)} "
        f"fallback_count={len(fallback_rows)} daily_loads="
        f"{ {day.isoformat(): round(hours, 2) for day, hours in load_by_day.items()} }"
    )

    assert len(suggestions) == 50
    assert len(fallback_rows) == 5
    assert all(item["estimated_hours"] == 0.1 for item in fallback_rows)
    assert blocked
    assert all(float(hours) <= SCHEDULER_SHIFT_CAPACITY_HOURS for hours in load_by_day.values())
    assert all(item["conflict_reason"] == "No shift capacity available within 8h/day" for item in blocked)


@pytest.mark.asyncio
async def test_auto_scheduler_missing_cycle_times_and_zero_capacity_are_safe(capsys):
    rows = make_missing_cycle_time_rows()
    db = FakeNoCapacitySchedulerDB(rows)

    suggestions = await build_auto_schedule_suggestions(
        db=db,
        tenant_id=TENANT_ID,
        payload=AutoSchedulePreviewRequest(
            from_date=date.today(),
            to_date=date.today(),
            limit=10,
        ),
    )

    assigned = [item for item in suggestions if item["machine_id"]]
    blocked = [item for item in suggestions if not item["machine_id"]]

    print(
        "SCHEDULER_NO_CAPACITY "
        f"jobs={len(suggestions)} assigned={len(assigned)} blocked={len(blocked)} "
        f"fallback_hours={sorted({item['estimated_hours'] for item in suggestions})}"
    )

    assert len(suggestions) == 10
    assert len(assigned) == 0
    assert len(blocked) == 10
    assert all(item["estimated_hours"] == 0.1 for item in suggestions)
    assert all(item["reason"] == "Needs manual planning" for item in blocked)
    assert all(item["conflict_reason"] == "No shift capacity available within 8h/day" for item in blocked)
    assert all(item["planned_start_date"] is None and item["planned_end_date"] is None for item in blocked)


@pytest.mark.asyncio
async def test_auto_schedule_apply_blocks_inactive_machine_override():
    db = FakeInactiveApplyDB()

    with pytest.raises(HTTPException) as exc:
        await apply_auto_schedule(
            payload=AutoScheduleApplyRequest(
                suggestions=[
                    {
                        "job_operation_id": uuid4(),
                        "machine_id": INACTIVE_MACHINE_ID,
                        "planned_start_date": datetime.now(UTC),
                        "planned_end_date": datetime.now(UTC) + timedelta(hours=1),
                    }
                ]
            ),
            user={"tenant_id": TENANT_ID, "role": "SUPERVISOR"},
            db=db,
        )

    print(
        "SCHEDULER_OVERRIDE_BLOCK "
        f"role=SUPERVISOR tenant={TENANT_ID} machine_id={INACTIVE_MACHINE_ID} "
        f"status={exc.value.status_code} detail={exc.value.detail}"
    )

    assert exc.value.status_code == 400
    assert "inactive or unavailable" in exc.value.detail
    assert db.committed is False
