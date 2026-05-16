from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app import models
from app.core.job_operations_service import update_job_operation_status_async


TENANT_ID = "tenant-outbound-webhook-test"
USER_ID = "supervisor-outbound-webhook-test"
JOB_ID = UUID("60000000-0000-4000-8000-000000000001")
JOB_OPERATION_ID = UUID("60000000-0000-4000-8000-000000000002")
WEBHOOK_ID = UUID("60000000-0000-4000-8000-000000000003")
WEBHOOK_URL = "https://example.test/roodha-webhook"


class FakeScalarResult:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeRowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class OutboundWebhookDB:
    def __init__(self):
        self.completed_at = datetime(2026, 5, 15, 10, 30, 0)
        self.job = SimpleNamespace(
            job_id=JOB_ID,
            tenant_id=TENANT_ID,
            quantity=10,
            status=models.JobStatus.IN_PROGRESS,
        )
        self.operation = SimpleNamespace(
            job_op_id=JOB_OPERATION_ID,
            tenant_id=TENANT_ID,
            job_id=JOB_ID,
            op_id=uuid4(),
            machine_id=None,
            worker_id=None,
            shift_id=None,
            sequence_number=1,
            status=models.OperationStatus.IN_PROGRESS,
            actual_start_time=datetime(2026, 5, 15, 9, 0, 0),
            actual_end_time=None,
            quantity_completed=0,
            quantity_rejected=0,
            planned_start_date=None,
            planned_end_date=None,
        )
        self.webhook = SimpleNamespace(
            webhook_id=WEBHOOK_ID,
            tenant_id=TENANT_ID,
            name="Dummy ERP webhook",
            direction="OUTBOUND",
            url=WEBHOOK_URL,
            event_types_json=["JOB_COMPLETED"],
            is_active=True,
        )
        self.events = []
        self.audit_logs = []
        self.commits = 0

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)

        if "from job_operations" in text and "with_for_update" not in text:
            if "sequence_number <" in text:
                return FakeScalarResult(rows=[])
            if "status =" in text and "job_op_id !=" in text:
                return FakeScalarResult(None)
            if "select job_operations.status" in text:
                return FakeRowsResult([(self.operation.status,)])

        if "from job_operations" in text:
            return FakeScalarResult(self.operation)

        if "select jobs.quantity" in text:
            return FakeScalarResult(self.job.quantity)

        if "from jobs" in text:
            return FakeScalarResult(self.job)

        if "from integration_webhooks" in text:
            return FakeScalarResult(rows=[self.webhook])

        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.Event):
            self.events.append(record)
        elif isinstance(record, models.AuditLog):
            self.audit_logs.append(record)
        else:
            raise AssertionError(f"Unexpected added record: {type(record)!r}")

    async def commit(self):
        self.commits += 1

    async def refresh(self, _record):
        return None


class FakeHTTPResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeAsyncClient:
    posts = []
    mode = "success"

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json):
        self.posts.append({"url": url, "json": json})
        if self.mode == "timeout":
            raise httpx.TimeoutException("simulated timeout")
        if self.mode == "server_error":
            return FakeHTTPResponse(500)
        return FakeHTTPResponse(200)


@pytest.mark.asyncio
async def test_job_completed_event_and_outbound_webhook_success(monkeypatch, capsys):
    db = OutboundWebhookDB()
    FakeAsyncClient.posts = []
    FakeAsyncClient.mode = "success"
    monkeypatch.setattr("app.core.outbound_webhook_service.httpx.AsyncClient", FakeAsyncClient)

    updated = await update_job_operation_status_async(
        db=db,
        job_op_id=JOB_OPERATION_ID,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        new_status="COMPLETED",
        quantity_completed=10,
        quantity_rejected=0,
        actual_end_time=db.completed_at,
    )

    assert updated.status == "COMPLETED"
    assert db.job.status == models.JobStatus.COMPLETED
    assert len(db.events) == 1
    event = db.events[0]
    assert event.event_type == "JOB_COMPLETED"
    assert event.entity_id == str(JOB_ID)

    assert FakeAsyncClient.posts == [
        {
            "url": WEBHOOK_URL,
            "json": {
                "job_id": str(JOB_ID),
                "status": "COMPLETED",
                "completion_date": db.completed_at.isoformat(),
            },
        }
    ]
    print(
        "OUTBOUND_WEBHOOK_SUCCESS "
        f"event={event.event_type} job={event.entity_id} "
        f"url={FakeAsyncClient.posts[0]['url']} status=200"
    )


@pytest.mark.parametrize("failure_mode, expected_status", [("server_error", 500), ("timeout", "timeout")])
@pytest.mark.asyncio
async def test_outbound_webhook_failure_does_not_rollback_job_completion(monkeypatch, failure_mode, expected_status):
    db = OutboundWebhookDB()
    FakeAsyncClient.posts = []
    FakeAsyncClient.mode = failure_mode
    monkeypatch.setattr("app.core.outbound_webhook_service.httpx.AsyncClient", FakeAsyncClient)

    updated = await update_job_operation_status_async(
        db=db,
        job_op_id=JOB_OPERATION_ID,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        new_status="COMPLETED",
        quantity_completed=10,
        quantity_rejected=0,
        actual_end_time=db.completed_at,
    )

    assert updated.status == "COMPLETED"
    assert db.job.status == models.JobStatus.COMPLETED
    assert len(db.events) == 1
    assert db.events[0].event_type == "JOB_COMPLETED"
    assert FakeAsyncClient.posts[0]["json"]["job_id"] == str(JOB_ID)
    print(
        "OUTBOUND_WEBHOOK_FAILURE_SAFE "
        f"mode={failure_mode} external_status={expected_status} "
        f"job_status={db.job.status.value} events={len(db.events)}"
    )
