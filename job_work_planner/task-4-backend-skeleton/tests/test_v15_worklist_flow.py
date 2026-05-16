from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.core import job_operations_service
from app.core.job_operations_service import update_job_operation_status_async
from app.routes.worklist import get_worklist


TENANT_ID = "tenant-worklist-flow-test"
USER_ID = "operator-cutting-test"
CUTTING_MACHINE_ID = UUID("10000000-0000-4000-8000-000000000001")
TURNING_MACHINE_ID = UUID("10000000-0000-4000-8000-000000000002")
QC_MACHINE_ID = UUID("10000000-0000-4000-8000-000000000003")


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FactoryFlowDB:
    def __init__(self):
        now = datetime.now(UTC).replace(tzinfo=None)
        self.job_id = uuid4()
        self.cut_op_id = uuid4()
        self.turn_op_id = uuid4()
        self.qc_op_id = uuid4()
        self.job = SimpleNamespace(
            job_id=self.job_id,
            tenant_id=TENANT_ID,
            job_number="WL-ROUTE-001",
            quantity=10,
            due_date=now + timedelta(days=3),
            status=models.JobStatus.NOT_STARTED,
        )
        self.part = SimpleNamespace(part_number="PART-3STEP", description="Three step part")
        self.customer = SimpleNamespace(name="Queue Customer")
        self.machines = {
            CUTTING_MACHINE_ID: SimpleNamespace(machine_id=CUTTING_MACHINE_ID, tenant_id=TENANT_ID, name="Cutting-01"),
            TURNING_MACHINE_ID: SimpleNamespace(machine_id=TURNING_MACHINE_ID, tenant_id=TENANT_ID, name="Lathe-01"),
            QC_MACHINE_ID: SimpleNamespace(machine_id=QC_MACHINE_ID, tenant_id=TENANT_ID, name="QC-01"),
        }
        self.operation_masters = {
            "cutting": SimpleNamespace(name="Cutting"),
            "turning": SimpleNamespace(name="Turning"),
            "qc": SimpleNamespace(name="QC"),
        }
        self.operations = [
            SimpleNamespace(
                job_op_id=self.cut_op_id,
                tenant_id=TENANT_ID,
                job_id=self.job_id,
                op_id=uuid4(),
                machine_id=CUTTING_MACHINE_ID,
                worker_id=None,
                shift_id=None,
                sequence_number=1,
                status=models.OperationStatus.NOT_STARTED,
                actual_start_time=None,
                actual_end_time=None,
                quantity_completed=0,
                quantity_rejected=0,
                planned_start_date=now,
                planned_end_date=now + timedelta(hours=1),
            ),
            SimpleNamespace(
                job_op_id=self.turn_op_id,
                tenant_id=TENANT_ID,
                job_id=self.job_id,
                op_id=uuid4(),
                machine_id=TURNING_MACHINE_ID,
                worker_id=None,
                shift_id=None,
                sequence_number=2,
                status=models.OperationStatus.NOT_STARTED,
                actual_start_time=None,
                actual_end_time=None,
                quantity_completed=0,
                quantity_rejected=0,
                planned_start_date=now + timedelta(hours=1),
                planned_end_date=now + timedelta(hours=2),
            ),
            SimpleNamespace(
                job_op_id=self.qc_op_id,
                tenant_id=TENANT_ID,
                job_id=self.job_id,
                op_id=uuid4(),
                machine_id=QC_MACHINE_ID,
                worker_id=None,
                shift_id=None,
                sequence_number=3,
                status=models.OperationStatus.NOT_STARTED,
                actual_start_time=None,
                actual_end_time=None,
                quantity_completed=0,
                quantity_rejected=0,
                planned_start_date=now + timedelta(hours=2),
                planned_end_date=now + timedelta(hours=3),
            ),
        ]
        self.commits = 0
        self.rollbacks = 0

    def _operation_by_id(self, operation_id):
        return next((op for op in self.operations if str(op.job_op_id) == str(operation_id)), None)

    def _params(self, statement):
        return getattr(statement.compile(), "params", {})

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)
        params = self._params(statement)
        values = {str(value) for value in params.values()}

        if text.strip().startswith("select machines.machine_id") and "from machines" in text:
            for machine_id in self.machines:
                if str(machine_id) in values:
                    return FakeScalar(machine_id)
            return FakeScalar(None)

        if text.strip().startswith("select job_operations.status") and "sequence_number =" in text:
            requested_seq = next((value for value in params.values() if isinstance(value, int)), None)
            previous = next((op for op in self.operations if op.job_id == self.job_id and op.sequence_number == requested_seq), None)
            return FakeScalar(previous.status if previous else None)

        if text.strip().startswith("select jobs.quantity"):
            return FakeScalar(self.job.quantity)

        if text.strip().startswith("select jobs.") and "from jobs" in text:
            return FakeScalar(self.job)

        if text.strip().startswith("select job_operations.status"):
            return FakeRows([(op.status,) for op in self.operations])

        if "sequence_number" in text and " < " in text:
            sequence_number = next((value for value in params.values() if isinstance(value, int)), None)
            if sequence_number is None:
                return FakeScalars([])
            return FakeScalars([
                op for op in self.operations
                if op.sequence_number < sequence_number and op.status != models.OperationStatus.COMPLETED
            ])

        if "status =" in text and "job_op_id !=" in text:
            operation_id = next((value for value in params.values() if str(value) in {str(op.job_op_id) for op in self.operations}), None)
            operation = self._operation_by_id(operation_id)
            active = [
                op for op in self.operations
                if op.job_id == self.job_id
                and op.job_op_id != getattr(operation, "job_op_id", None)
                and op.status == models.OperationStatus.IN_PROGRESS
            ]
            return FakeScalar(active[0] if active else None)

        if "from job_operations" in text and "job_op_id" in text and "join jobs" not in text:
            operation_id = next((value for value in params.values() if str(value) in {str(op.job_op_id) for op in self.operations}), None)
            return FakeScalar(self._operation_by_id(operation_id))

        if "from job_operations" in text:
            machine_filter = next((machine_id for machine_id in self.machines if str(machine_id) in values), None)
            rows = []
            for operation in self.operations:
                if operation.status in {models.OperationStatus.COMPLETED, models.OperationStatus.CANCELLED}:
                    continue
                if machine_filter and operation.machine_id != machine_filter:
                    continue
                operation_master = list(self.operation_masters.values())[operation.sequence_number - 1]
                rows.append((
                    operation,
                    self.job,
                    operation_master,
                    self.part,
                    self.customer,
                    self.machines[operation.machine_id],
                    None,
                ))
            return FakeRows(rows)

        raise AssertionError(f"Unhandled fake SQL: {text}")

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _record):
        return None

    def add(self, _record):
        return None


def request_for(role="OPERATOR", machine_id=CUTTING_MACHINE_ID):
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "role": role,
                "machine_id": str(machine_id) if machine_id else None,
            }
        )
    )


async def noop_audit(**_kwargs):
    return None


@pytest.mark.asyncio
async def test_worklist_route_progression_and_quantity_guard(monkeypatch):
    db = FactoryFlowDB()
    monkeypatch.setattr(job_operations_service, "log_audit_event_async", noop_audit)

    cutting_queue = await get_worklist(request_for(), machine_id=None, worker_id=None, shift_id=None, shift_date=None, db=db)
    cutting_items = cutting_queue["data"]["items"]
    print(f"WORKLIST_INITIAL role=OPERATOR machine=Cutting items={[item['operation_name'] for item in cutting_items]}")
    assert [item["operation_name"] for item in cutting_items] == ["Cutting"]

    await update_job_operation_status_async(
        db=db,
        job_op_id=db.cut_op_id,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        new_status="IN_PROGRESS",
    )
    assert db._operation_by_id(db.cut_op_id).status == "IN_PROGRESS"

    with pytest.raises(ValueError) as exc:
        await update_job_operation_status_async(
            db=db,
            job_op_id=db.cut_op_id,
            tenant_id=TENANT_ID,
            user_id=USER_ID,
            new_status="COMPLETED",
            quantity_completed=9,
            quantity_rejected=2,
        )
    print(f"WORKLIST_INVALID_COMPLETE status=400 detail={exc.value}")
    assert "exceeds total job quantity" in str(exc.value)
    assert db._operation_by_id(db.cut_op_id).status == "IN_PROGRESS"

    await update_job_operation_status_async(
        db=db,
        job_op_id=db.cut_op_id,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        new_status="COMPLETED",
        quantity_completed=9,
        quantity_rejected=1,
    )

    cutting_queue_after = await get_worklist(request_for(), machine_id=None, worker_id=None, shift_id=None, shift_date=None, db=db)
    cutting_after_items = cutting_queue_after["data"]["items"]
    assert cutting_after_items == []

    turning_queue = await get_worklist(
        request_for(role="SUPERVISOR", machine_id=None),
        machine_id=str(TURNING_MACHINE_ID),
        worker_id=None,
        shift_id=None,
        shift_date=None,
        db=db,
    )
    turning_items = turning_queue["data"]["items"]
    print(f"WORKLIST_AFTER_CUTTING role=SUPERVISOR machine=Turning items={[item['operation_name'] for item in turning_items]}")

    assert [item["operation_name"] for item in turning_items] == ["Turning"]
    assert turning_items[0]["previous_operation_status"] == "COMPLETED"
