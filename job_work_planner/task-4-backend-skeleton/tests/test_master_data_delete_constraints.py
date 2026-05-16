from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.routes.master_data import delete_part


TENANT_ID = "tenant-master-delete-constraint-test"
OWNER_ID = "owner-master-delete-test"
PART_ID = UUID("70000000-0000-4000-8000-000000000001")
JOB_ID = UUID("70000000-0000-4000-8000-000000000002")


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class PartDeleteConstraintDB:
    def __init__(self, *, linked_job=True):
        self.linked_job = linked_job
        self.part = SimpleNamespace(part_id=PART_ID, tenant_id=TENANT_ID, part_number="LOCKED-PART-001")
        self.deleted = []
        self.committed = False

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)
        if "from parts" in text:
            return FakeScalar(self.part)
        if "from jobs" in text:
            return FakeScalar(JOB_ID if self.linked_job else None)
        raise AssertionError(f"Unhandled fake SQL: {text}")

    async def delete(self, record):
        self.deleted.append(record)

    async def commit(self):
        self.committed = True


def owner_request():
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": OWNER_ID,
                "role": "OWNER",
            }
        )
    )


@pytest.mark.asyncio
async def test_owner_cannot_delete_part_used_by_existing_job(capsys):
    db = PartDeleteConstraintDB(linked_job=True)

    with pytest.raises(HTTPException) as exc:
        await delete_part(part_id=PART_ID, request=owner_request(), db=db)

    detail = str(exc.value.detail)
    print(f"PART_DELETE_BLOCK part={PART_ID} job={JOB_ID} status={exc.value.status_code} detail={detail}")

    assert exc.value.status_code == 400
    assert "Cannot delete part with linked jobs" in detail
    assert "IntegrityError" not in detail
    assert "foreign key" not in detail.lower()
    assert "traceback" not in detail.lower()
    assert "sql" not in detail.lower()
    assert db.deleted == []
    assert db.committed is False


@pytest.mark.asyncio
async def test_owner_can_delete_unused_part(capsys):
    db = PartDeleteConstraintDB(linked_job=False)

    response = await delete_part(part_id=PART_ID, request=owner_request(), db=db)

    print(f"PART_DELETE_ALLOW part={PART_ID} status=deleted")

    assert response.data == {"part_id": PART_ID}
    assert db.deleted == [db.part]
    assert db.committed is True
