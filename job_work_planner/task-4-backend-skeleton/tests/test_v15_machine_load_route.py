from datetime import date
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.routes.planning import get_machine_load


TENANT_ID = "tenant-machine-load-route-test"
MACHINE_ID = UUID("11111111-2222-4333-8444-555555555555")


class FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeMachineLoadDB:
    async def execute(self, _statement):
        return FakeRows([
            SimpleNamespace(
                machine_id=MACHINE_ID,
                machine_name="Lathe-01",
                operation_count=2,
                booked_hours=9.75,
            )
        ])


@pytest.mark.asyncio
async def test_machine_load_uses_job_op_id_and_returns_capacity_rows():
    response = await get_machine_load(
        request=None,
        from_date=date(2026, 5, 16),
        to_date=date(2026, 5, 16),
        user={"tenant_id": TENANT_ID, "role": "SUPERVISOR"},
        db=FakeMachineLoadDB(),
    )

    rows = response["data"]["machines"]

    print(f"MACHINE_LOAD_ROUTE rows={len(rows)} operation_count={rows[0]['operation_count']}")

    assert response["success"] is True
    assert rows == [
        {
            "machine_id": str(MACHINE_ID),
            "machine_name": "Lathe-01",
            "operation_count": 2,
            "booked_hours": 9.75,
            "is_overloaded": False,
        }
    ]
