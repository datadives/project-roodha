from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app import models
from app.routes.jobs import update_job
from app.schemas.jobs import JobUpdate


TENANT_ID = "tenant-route-edit-lifecycle-test"
USER_ID = "supervisor-route-edit-test"
JOB_ID = UUID("50000000-0000-4000-8000-000000000001")
STARTED_OP_ID = UUID("50000000-0000-4000-8000-000000000011")
PENDING_OP_ID = UUID("50000000-0000-4000-8000-000000000012")
QC_OP_ID = UUID("50000000-0000-4000-8000-000000000013")


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


class RouteEditDB:
    def __init__(self):
        self.job = SimpleNamespace(job_id=JOB_ID, tenant_id=TENANT_ID)
        self.operations = [
            SimpleNamespace(job_op_id=STARTED_OP_ID, tenant_id=TENANT_ID, job_id=JOB_ID, sequence_number=1, status=models.OperationStatus.IN_PROGRESS),
            SimpleNamespace(job_op_id=PENDING_OP_ID, tenant_id=TENANT_ID, job_id=JOB_ID, sequence_number=2, status=models.OperationStatus.NOT_STARTED),
            SimpleNamespace(job_op_id=QC_OP_ID, tenant_id=TENANT_ID, job_id=JOB_ID, sequence_number=3, status=models.OperationStatus.NOT_STARTED),
        ]
        self.deleted = []
        self.committed = False

    async def execute(self, statement):
        text = str(statement.compile()).lower()
        if "from jobs" in text:
            return FakeScalar(self.job)
        if "from job_operations" in text:
            return FakeScalarList(self.operations)
        raise AssertionError(f"Unhandled fake SQL: {text}")

    async def delete(self, record):
        self.deleted.append(record)

    async def commit(self):
        self.committed = True

    async def refresh(self, record):
        return record


def request_for_supervisor():
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "role": "SUPERVISOR",
            }
        )
    )


@pytest.mark.asyncio
async def test_job_route_edit_rejects_removing_in_progress_operation(capsys):
    db = RouteEditDB()
    payload = JobUpdate(
        operations=[
            {"job_operation_id": str(PENDING_OP_ID)},
            {"job_operation_id": str(QC_OP_ID)},
        ]
    )

    with pytest.raises(HTTPException) as exc:
        await update_job(
            job_id=JOB_ID,
            payload=payload,
            request=request_for_supervisor(),
            db=db,
        )

    print(
        "JOB_ROUTE_EDIT_BLOCK "
        f"removed_operation={STARTED_OP_ID} status={exc.value.status_code} detail={exc.value.detail}"
    )

    assert exc.value.status_code == 409
    assert "Cannot remove operation" in exc.value.detail
    assert db.deleted == []
    assert db.committed is False
