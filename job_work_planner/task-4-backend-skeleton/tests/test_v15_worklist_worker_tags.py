from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.routes.worklist import get_worklist


TENANT_ID = "tenant-worklist-worker-tags-test"
TODAY = date(2026, 5, 15)
MACHINE_ID = UUID("80000000-0000-4000-8000-000000000001")
TARGET_WORKER_ID = UUID("80000000-0000-4000-8000-000000000002")
OTHER_WORKER_ID = UUID("80000000-0000-4000-8000-000000000003")


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


class WorkerTagsWorklistDB:
    def __init__(self):
        planned_start = datetime.combine(TODAY, time(hour=9))
        self.machine = SimpleNamespace(machine_id=MACHINE_ID, tenant_id=TENANT_ID, name="Milling-01")
        self.target_worker = SimpleNamespace(worker_id=TARGET_WORKER_ID, tenant_id=TENANT_ID, name="Asha Worker")
        self.other_worker = SimpleNamespace(worker_id=OTHER_WORKER_ID, tenant_id=TENANT_ID, name="Other Worker")
        self.operation_master = SimpleNamespace(name="Milling")
        self.part = SimpleNamespace(part_number="TAG-PART", description="Tagged Part")
        self.customer = SimpleNamespace(name="Tagged Customer")
        self.rows = [
            self._make_row("TAG-JOB-CRITICAL", TARGET_WORKER_ID, self.target_worker, ["Critical"], planned_start),
            self._make_row("TAG-JOB-NORMAL", OTHER_WORKER_ID, self.other_worker, [], planned_start),
        ]

    def _make_row(self, job_number, worker_id, worker, tags, planned_start):
        job_id = uuid4()
        operation = SimpleNamespace(
            job_op_id=uuid4(),
            tenant_id=TENANT_ID,
            job_id=job_id,
            op_id=uuid4(),
            machine_id=MACHINE_ID,
            worker_id=worker_id,
            shift_id=None,
            sequence_number=1,
            status=models.OperationStatus.NOT_STARTED,
            planned_start_date=planned_start,
            planned_end_date=planned_start + timedelta(hours=2),
        )
        job = SimpleNamespace(
            job_id=job_id,
            tenant_id=TENANT_ID,
            job_number=job_number,
            quantity=20,
            due_date=planned_start + timedelta(days=2),
            tags_json=tags,
        )
        return (operation, job, self.operation_master, self.part, self.customer, self.machine, worker)

    def _params(self, statement):
        return getattr(statement.compile(), "params", {})

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)
        params = self._params(statement)
        values = {str(value) for value in params.values()}

        if text.strip().startswith("select machines.machine_id") and "from machines" in text:
            return FakeScalar(MACHINE_ID if str(MACHINE_ID) in values else None)

        if text.strip().startswith("select workers.worker_id") and "from workers" in text:
            if str(TARGET_WORKER_ID) in values:
                return FakeScalar(TARGET_WORKER_ID)
            if str(OTHER_WORKER_ID) in values:
                return FakeScalar(OTHER_WORKER_ID)
            return FakeScalar(None)

        if text.strip().startswith("select shifts.shift_id") and "from shifts" in text:
            return FakeScalar(None)

        if "from job_operations" in text:
            datetimes = [value for value in params.values() if isinstance(value, datetime)]
            start = min(datetimes) if datetimes else datetime.min
            end = max(datetimes) if datetimes else datetime.max
            filtered = []
            for row in self.rows:
                operation = row[0]
                if str(TARGET_WORKER_ID) in values and operation.worker_id != TARGET_WORKER_ID:
                    continue
                if str(OTHER_WORKER_ID) in values and operation.worker_id != OTHER_WORKER_ID:
                    continue
                if not (start <= operation.planned_start_date <= end):
                    continue
                filtered.append(row)
            return FakeRows(filtered)

        raise AssertionError(f"Unhandled fake SQL: {text}")


def supervisor_request():
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": "supervisor-worker-tags-test",
                "role": "SUPERVISOR",
            }
        )
    )


@pytest.mark.asyncio
async def test_worklist_worker_filter_returns_only_assigned_worker_and_tags():
    db = WorkerTagsWorklistDB()

    response = await get_worklist(
        supervisor_request(),
        machine_id=None,
        worker_id=str(TARGET_WORKER_ID),
        shift_date=TODAY,
        shift_id=None,
        db=db,
    )
    items = response["data"]["items"]

    print(f"WORKLIST_WORKER_FILTER worker={TARGET_WORKER_ID} returned={len(items)} tags={items[0]['tags']}")

    assert len(items) == 1
    assert items[0]["job_number"] == "TAG-JOB-CRITICAL"
    assert items[0]["worker_id"] == str(TARGET_WORKER_ID)
    assert items[0]["machine_id"] == str(MACHINE_ID)
    assert items[0]["tags"] == ["Critical"]
    assert "TAG-JOB-NORMAL" not in {item["job_number"] for item in items}
