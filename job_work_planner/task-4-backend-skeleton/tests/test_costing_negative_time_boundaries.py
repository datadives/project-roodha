from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import models
from app.services.costing_service import calculate_job_costs
from app.services.maintenance_service import run_batch_costing_service


TENANT_ID = "tenant-costing-negative-time-test"
JOB_ID = UUID("60000000-0000-4000-8000-000000000001")
MACHINE_ID = UUID("60000000-0000-4000-8000-000000000002")
WORKER_ID = UUID("60000000-0000-4000-8000-000000000003")
JOB_OP_ID = UUID("60000000-0000-4000-8000-000000000004")


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


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


class CostingBoundaryDB:
    def __init__(self):
        self.summary = None
        self.commits = 0
        self.rollbacks = 0
        self.job = SimpleNamespace(
            tenant_id=TENANT_ID,
            job_id=JOB_ID,
            quantity=4,
            status=models.JobStatus.COMPLETED,
            updated_at=datetime.utcnow(),
            part=SimpleNamespace(default_material_cost_per_unit=Decimal("25.00")),
        )
        self.operation = SimpleNamespace(
            tenant_id=TENANT_ID,
            job_op_id=JOB_OP_ID,
            job_id=JOB_ID,
            machine_id=MACHINE_ID,
            worker_id=WORKER_ID,
            status=models.OperationStatus.COMPLETED,
            actual_start_time=datetime(2026, 5, 16, 10, 0, 0),
            actual_end_time=datetime(2026, 5, 16, 9, 0, 0),
        )

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)
        if "from jobs" in text and "where jobs.status" in text:
            return FakeScalarList([self.job])
        if "from jobs" in text and "jobs.job_id" in text:
            return FakeScalar(self.job)
        if "from job_operations" in text:
            return FakeRows([(self.operation, Decimal("120.00"), Decimal("50.00"))])
        if "from job_cost_summaries" in text:
            return FakeScalar(self.summary)
        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.JobCostSummary):
            self.summary = record

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_calculate_job_costs_clamps_negative_operation_duration(capsys):
    db = CostingBoundaryDB()

    await calculate_job_costs(db, TENANT_ID, JOB_ID)

    assert db.rollbacks == 0
    assert db.summary is not None
    assert db.summary.machine_cost == Decimal("0.00")
    assert db.summary.labour_cost == Decimal("0.00")
    assert db.summary.material_cost == Decimal("100.00")
    assert db.summary.total_cost == Decimal("100.00")
    assert db.summary.total_cost >= Decimal("0.00")

    print(
        "COSTING_NEGATIVE_DURATION_CLAMP "
        f"job={JOB_ID} machine_cost={db.summary.machine_cost} "
        f"labour_cost={db.summary.labour_cost} total_cost={db.summary.total_cost}"
    )


@pytest.mark.asyncio
async def test_batch_costing_processes_negative_time_job_without_failure(capsys):
    db = CostingBoundaryDB()

    result = await run_batch_costing_service(db)

    assert result["processed_jobs"] == 1
    assert result["failed_jobs"] == 0
    assert db.rollbacks == 0
    assert db.summary is not None
    assert db.summary.total_cost >= Decimal("0.00")

    print(
        "BATCH_COSTING_NEGATIVE_TIME "
        f"processed_jobs={result['processed_jobs']} failed_jobs={result['failed_jobs']}"
    )
