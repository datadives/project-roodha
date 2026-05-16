from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.routes.planning import (
    SCHEDULER_SHIFT_CAPACITY_HOURS,
    apply_auto_schedule,
    build_auto_schedule_suggestions,
)
from app.schemas.value_features import AutoScheduleApplyRequest, AutoSchedulePreviewRequest


TENANT_ID = "tenant-scheduler-priority-test"
MILLING_ID = UUID("70000000-0000-4000-8000-000000000001")
FROM_DATE = date(2026, 5, 15)


class FakeScalarList:
    def __init__(self, values):
        self.values = values

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None

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


class SchedulerPriorityDB:
    def __init__(self):
        self.machine = SimpleNamespace(
            machine_id=MILLING_ID,
            tenant_id=TENANT_ID,
            name="Milling-01",
            type="Milling",
            is_active=True,
        )
        self.operation_master = SimpleNamespace(
            operation_id=uuid4(),
            tenant_id=TENANT_ID,
            name="Milling",
            default_machine_type="Milling",
            standard_cycle_time_mins=60,
        )
        self.rows = self._make_rows()
        self.operation_by_id = {row[0].job_op_id: row[0] for row in self.rows}
        self.calls = 0
        self.committed = False
        self.events = []

    def _make_rows(self):
        jobs = [
            ("MILL-EARLY", 1),
            ("MILL-MIDDLE", 3),
            ("MILL-LATE", 5),
        ]
        rows = []
        for job_number, due_offset in jobs:
            job_id = uuid4()
            operation = SimpleNamespace(
                job_op_id=uuid4(),
                job_id=job_id,
                tenant_id=TENANT_ID,
                sequence_number=1,
                status=models.OperationStatus.NOT_STARTED,
                machine_id=None,
                planned_start_date=None,
                planned_end_date=None,
            )
            job = SimpleNamespace(
                job_id=job_id,
                tenant_id=TENANT_ID,
                job_number=job_number,
                quantity=2,
                due_date=datetime.combine(FROM_DATE + timedelta(days=due_offset), time(hour=18)),
                priority="MEDIUM",
                created_at=datetime.now(UTC),
            )
            rows.append((operation, job, self.operation_master))
        return rows

    def _params(self, statement):
        return getattr(statement.compile(), "params", {})

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        self.calls += 1
        text = self._statement_text(statement)
        params = self._params(statement)
        values = {str(value) for value in params.values()}

        if "from machines" in text and "machines.name" in text:
            return FakeScalarList([self.machine])

        if "select machines.machine_id" in text:
            return FakeScalar(MILLING_ID if str(MILLING_ID) in values else None)

        if "from job_operations" in text and "group by" in text:
            return FakeRows([])

        if "from job_operations" in text and "join jobs" in text:
            return FakeRows(self.rows)

        if "from job_operations" in text and "job_op_id" in text:
            operation_id = next((value for value in self.operation_by_id if str(value) in values), None)
            return FakeScalar(self.operation_by_id.get(operation_id))

        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.Event):
            self.events.append(record)
            return
        raise AssertionError(f"Unexpected record type: {type(record)!r}")

    async def flush(self):
        return None

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_auto_scheduler_prioritizes_milling_jobs_by_earliest_due_date():
    db = SchedulerPriorityDB()

    suggestions = await build_auto_schedule_suggestions(
        db=db,
        tenant_id=TENANT_ID,
        payload=AutoSchedulePreviewRequest(
            from_date=FROM_DATE,
            to_date=FROM_DATE + timedelta(days=7),
            limit=3,
        ),
    )

    ordered_jobs = [item["job_number"] for item in suggestions]
    starts = [item["planned_start_date"] for item in suggestions]
    daily_load = sum(float(item["estimated_hours"]) for item in suggestions)

    print(f"SCHEDULER_DUE_DATE_ORDER jobs={ordered_jobs}")

    assert ordered_jobs == ["MILL-EARLY", "MILL-MIDDLE", "MILL-LATE"]
    assert all(item["machine_id"] == MILLING_ID for item in suggestions)
    assert starts == sorted(starts)
    assert [start.time().hour for start in starts] == [8, 10, 12]
    assert daily_load <= SCHEDULER_SHIFT_CAPACITY_HOURS


@pytest.mark.asyncio
async def test_auto_schedule_bulk_apply_updates_all_three_operations():
    db = SchedulerPriorityDB()
    suggestions = await build_auto_schedule_suggestions(
        db=db,
        tenant_id=TENANT_ID,
        payload=AutoSchedulePreviewRequest(
            from_date=FROM_DATE,
            to_date=FROM_DATE + timedelta(days=7),
            limit=3,
        ),
    )

    response = await apply_auto_schedule(
        payload=AutoScheduleApplyRequest(
            suggestions=[
                {
                    "job_operation_id": item["job_operation_id"],
                    "machine_id": item["machine_id"],
                    "planned_start_date": item["planned_start_date"],
                    "planned_end_date": item["planned_end_date"],
                }
                for item in suggestions
            ]
        ),
        user={"tenant_id": TENANT_ID, "role": "SUPERVISOR"},
        db=db,
    )

    applied = response["data"]["applied"]
    planned_operations = [db.operation_by_id[UUID(operation_id)] for operation_id in applied]

    print(f"SCHEDULER_BULK_APPLY applied_count={response['data']['applied_count']}")

    assert response["data"]["applied_count"] == 3
    assert len(applied) == 3
    assert db.committed is True
    assert all(operation.machine_id == MILLING_ID for operation in planned_operations)
    assert all(operation.planned_start_date is not None for operation in planned_operations)
    assert all(operation.planned_end_date is not None for operation in planned_operations)
    assert all(operation.status == models.OperationStatus.PLANNED for operation in planned_operations)
