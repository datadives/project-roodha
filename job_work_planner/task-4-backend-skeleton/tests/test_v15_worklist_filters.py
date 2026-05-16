from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.core import job_operations_service
from app.core.job_operations_service import plan_job_operation_service_async
from app.routes.worklist import get_worklist


TENANT_ID = "tenant-worklist-filter-test"
USER_ID = "supervisor-worklist-filter-test"
TODAY = date(2026, 5, 15)
MACHINE_A_ID = UUID("40000000-0000-4000-8000-000000000001")
SHIFT_1_ID = UUID("40000000-0000-4000-8000-000000000002")


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class WorklistFilterDB:
    def __init__(self):
        planned_start = datetime.combine(TODAY, time(hour=9))
        self.job_id = uuid4()
        self.job_op_id = uuid4()
        self.job = SimpleNamespace(
            job_id=self.job_id,
            tenant_id=TENANT_ID,
            job_number="WL-FILTER-001",
            quantity=25,
            due_date=datetime.combine(TODAY + timedelta(days=3), time(hour=18)),
            status=models.JobStatus.NOT_STARTED,
        )
        self.operation = SimpleNamespace(
            job_op_id=self.job_op_id,
            tenant_id=TENANT_ID,
            job_id=self.job_id,
            op_id=uuid4(),
            machine_id=MACHINE_A_ID,
            worker_id=None,
            shift_id=SHIFT_1_ID,
            sequence_number=1,
            status=models.OperationStatus.NOT_STARTED,
            actual_start_time=None,
            actual_end_time=None,
            quantity_completed=0,
            quantity_rejected=0,
            planned_start_date=planned_start,
            planned_end_date=planned_start + timedelta(hours=2),
        )
        self.operation_master = SimpleNamespace(name="Cutting")
        self.part = SimpleNamespace(part_number="FILTER-PART", description="Filtered worklist part")
        self.customer = SimpleNamespace(name="Filter Customer")
        self.machine = SimpleNamespace(machine_id=MACHINE_A_ID, tenant_id=TENANT_ID, name="Machine A")
        self.shift = SimpleNamespace(shift_id=SHIFT_1_ID, tenant_id=TENANT_ID, name="Shift 1")
        self.commits = 0

    def _params(self, statement):
        return getattr(statement.compile(), "params", {})

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    def _date_window_from_params(self, params):
        datetimes = [value for value in params.values() if isinstance(value, datetime)]
        if len(datetimes) < 2:
            return None
        return min(datetimes), max(datetimes)

    async def execute(self, statement):
        text = self._statement_text(statement)
        params = self._params(statement)
        values = {str(value) for value in params.values()}

        if text.strip().startswith("select machines.machine_id") and "from machines" in text:
            return FakeScalar(MACHINE_A_ID if str(MACHINE_A_ID) in values else None)

        if text.strip().startswith("select shifts.shift_id") and "from shifts" in text:
            return FakeScalar(SHIFT_1_ID if str(SHIFT_1_ID) in values else None)

        if text.strip().startswith("select workers.worker_id") and "from workers" in text:
            return FakeScalar(None)

        if "from job_operations" in text and "job_op_id" in text and "join jobs" not in text:
            return FakeScalar(self.operation if str(self.job_op_id) in values else None)

        if "from job_operations" in text:
            rows = []
            requested_machine = str(MACHINE_A_ID) in values
            requested_shift = str(SHIFT_1_ID) in values
            window = self._date_window_from_params(params)
            in_window = True
            if window:
                start, end = window
                in_window = start <= self.operation.planned_start_date <= end
            if requested_machine and requested_shift and in_window:
                rows.append((
                    self.operation,
                    self.job,
                    self.operation_master,
                    self.part,
                    self.customer,
                    self.machine,
                    None,
                ))
            return FakeRows(rows)

        raise AssertionError(f"Unhandled fake SQL: {text}")

    async def commit(self):
        self.commits += 1

    async def refresh(self, _record):
        return None

    def add(self, _record):
        return None


def supervisor_request():
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "role": "SUPERVISOR",
            }
        )
    )


async def noop_audit(**_kwargs):
    return None


@pytest.mark.asyncio
async def test_worklist_date_shift_filter_removes_replanned_operation(monkeypatch):
    db = WorklistFilterDB()
    monkeypatch.setattr(job_operations_service, "log_audit_event_async", noop_audit)

    today_queue = await get_worklist(
        supervisor_request(),
        machine_id=str(MACHINE_A_ID),
        worker_id=None,
        shift_date=TODAY,
        shift_id=str(SHIFT_1_ID),
        db=db,
    )
    today_items = today_queue["data"]["items"]
    print(f"WORKLIST_FILTER_INITIAL tenant={TENANT_ID} machine=Machine A shift=Shift 1 date={TODAY} count={len(today_items)}")
    assert [item["job_number"] for item in today_items] == ["WL-FILTER-001"]

    tomorrow_start = datetime.combine(TODAY + timedelta(days=1), time(hour=9))
    await plan_job_operation_service_async(
        db=db,
        job_op_id=db.job_op_id,
        machine_id=MACHINE_A_ID,
        tenant_id=TENANT_ID,
        shift_id=SHIFT_1_ID,
        planned_start_date=tomorrow_start,
        planned_end_date=tomorrow_start + timedelta(hours=2),
        user_id=USER_ID,
    )
    assert db.commits == 1

    today_after_edit = await get_worklist(
        supervisor_request(),
        machine_id=str(MACHINE_A_ID),
        worker_id=None,
        shift_date=TODAY,
        shift_id=str(SHIFT_1_ID),
        db=db,
    )
    after_items = today_after_edit["data"]["items"]
    print(f"WORKLIST_FILTER_AFTER_EDIT tenant={TENANT_ID} machine=Machine A shift=Shift 1 date={TODAY} count={len(after_items)}")
    assert after_items == []
