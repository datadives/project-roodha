from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.routes.jobs import create_job
from app.schemas.jobs import JobCreate


TENANT_ID = "tenant-high-priority-notification-test"
USER_ID = "owner-high-priority-notification-test"
CUSTOMER_ID = UUID("50000000-0000-4000-8000-000000000001")
PART_ID = UUID("50000000-0000-4000-8000-000000000002")
OPERATION_ID = UUID("50000000-0000-4000-8000-000000000003")


class FakeResult:
    def __init__(self, values=None, scalar_value=None):
        self.values = values or []
        self.scalar_value = scalar_value if scalar_value is not None else (self.values[0] if self.values else None)

    def scalar_one_or_none(self):
        return self.scalar_value

    def scalars(self):
        return self

    def all(self):
        return self.values


class HighPriorityJobDB:
    def __init__(self):
        self.now = datetime(2026, 5, 15, 9, 0, 0)
        self.part = SimpleNamespace(
            part_id=PART_ID,
            tenant_id=TENANT_ID,
            default_operations_route=[
                {
                    "operation_id": str(OPERATION_ID),
                    "sequence_number": 1,
                    "machine_id": None,
                }
            ],
        )
        self.operation = SimpleNamespace(
            operation_id=OPERATION_ID,
            tenant_id=TENANT_ID,
            name="Cutting",
            sequence_number=1,
            standard_cycle_time_mins=30,
        )
        self.jobs = []
        self.job_operations = []
        self.events = []
        self.notifications = []
        self.commits = 0

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)

        if "from parts" in text:
            return FakeResult([self.part], self.part)

        if "from custom_fields" in text:
            return FakeResult([])

        if "from operations_master" in text:
            return FakeResult([self.operation], self.operation)

        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.Job):
            record.created_at = self.now
            record.updated_at = self.now
            record.created_by = USER_ID
            record.updated_by = USER_ID
            if not record.job_number:
                record.job_number = "HP-NOTIF-001"
            self.jobs.append(record)
        elif isinstance(record, models.JobOperation):
            if record.quantity_completed is None:
                record.quantity_completed = 0
            if record.quantity_rejected is None:
                record.quantity_rejected = 0
            self.job_operations.append(record)
        elif isinstance(record, models.Event):
            self.events.append(record)
        elif isinstance(record, models.Notification):
            self.notifications.append(record)
        else:
            raise AssertionError(f"Unexpected record type: {type(record)!r}")

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def refresh(self, _record):
        return None


def owner_request():
    return SimpleNamespace(
        state=SimpleNamespace(
            user={
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "role": "OWNER",
            }
        )
    )


@pytest.mark.asyncio
async def test_high_priority_job_creation_creates_unread_broadcast_notification():
    db = HighPriorityJobDB()
    due_date = db.now + timedelta(days=5)

    response = await create_job(
        payload=JobCreate(
            customer_id=CUSTOMER_ID,
            part_id=PART_ID,
            job_number="HP-NOTIF-001",
            quantity=12,
            due_date=due_date,
            priority="HIGH",
        ),
        request=owner_request(),
        db=db,
    )

    assert response.data.job_number == "HP-NOTIF-001"
    assert len(db.notifications) == 1

    notification = db.notifications[0]
    print(
        "HIGH_PRIORITY_JOB_CREATED "
        f"job={response.data.job_number} "
        f"notification={notification.notification_id} "
        f"type={notification.type} "
        f"unread={notification.is_read}"
    )

    assert notification.type == "HIGH_PRIORITY_JOB"
    assert notification.title == "High priority job created"
    assert notification.entity_type == "JOB"
    assert notification.entity_id == str(response.data.job_id)
    assert notification.user_id is None
    assert notification.is_read is False
