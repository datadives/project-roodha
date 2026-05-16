from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app import models
from app.routes.integrations import IntegrationJobPayload, create_job_from_integration


TENANT_ID = "tenant-v15-master-e2e-contract"


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


class MasterE2EDB:
    def __init__(self):
        self.tenant = SimpleNamespace(tenant_id=TENANT_ID)
        self.custom_field = SimpleNamespace(
            field_id=UUID("40000000-0000-4000-8000-000000000001"),
            tenant_id=TENANT_ID,
            entity_type="JOB",
            field_name="Material Grade",
            field_type="DROPDOWN",
            options_json=["EN8", "EN24", "MS"],
            is_required=True,
        )
        self.customers = []
        self.parts = []
        self.operations = []
        self.jobs = []
        self.job_operations = []
        self.custom_field_values = []
        self.events = []
        self.notifications = []
        self.commits = 0

    async def get(self, model, key):
        if model is models.Tenant and key == TENANT_ID:
            return self.tenant
        return None

    async def execute(self, statement):
        text = str(statement.compile()).lower()
        if "from customers" in text:
            return FakeScalar(self.customers[0] if self.customers else None)
        if "from parts" in text:
            return FakeScalar(self.parts[0] if self.parts else None)
        if "from custom_fields" in text:
            return FakeScalarList([self.custom_field])
        if "from operations_master" in text:
            return FakeScalarList(self.operations)
        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.Customer):
            record.customer_id = record.customer_id or uuid4()
            self.customers.append(record)
        elif isinstance(record, models.Part):
            record.part_id = record.part_id or uuid4()
            self.parts.append(record)
        elif isinstance(record, models.OperationsMaster):
            record.operation_id = record.operation_id or uuid4()
            self.operations.append(record)
        elif isinstance(record, models.Job):
            record.job_id = record.job_id or uuid4()
            record.job_number = record.job_number or "E2E-1001"
            self.jobs.append(record)
        elif isinstance(record, models.JobOperation):
            record.job_op_id = record.job_op_id or uuid4()
            self.job_operations.append(record)
        elif isinstance(record, models.CustomFieldValue):
            self.custom_field_values.append(record)
        elif isinstance(record, models.Event):
            self.events.append(record)
        elif isinstance(record, models.Notification):
            self.notifications.append(record)
        else:
            raise AssertionError(f"Unexpected record type: {type(record)}")

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def refresh(self, record):
        return record


@pytest.mark.asyncio
async def test_v15_master_integration_webhook_accepts_custom_fields_tags_and_route(monkeypatch, capsys):
    monkeypatch.setenv("INTEGRATION_WEBHOOK_TOKEN", "valid-integration-token")
    db = MasterE2EDB()
    payload = IntegrationJobPayload(
        tenant_id=TENANT_ID,
        customer_name="E2E Customer",
        part_number="E2E-PART-001",
        part_description="Live smoke part",
        default_operations_route=[
            {"operation": "Cutting", "sequence_number": 1, "default_machine_type": "Lathe"},
            {"operation": "Turning", "sequence_number": 2, "default_machine_type": "Lathe"},
            {"operation": "QC", "sequence_number": 3, "default_machine_type": "QC"},
        ],
        quantity=25,
        due_date=datetime(2026, 5, 25),
        priority="HIGH",
        custom_fields={"Material Grade": "EN24"},
        tags=["Critical"],
    )

    response = await create_job_from_integration(
        payload=payload,
        x_roodha_integration_token="valid-integration-token",
        db=db,
    )

    assert response["success"] is True
    assert response["data"]["operation_count"] == 3
    assert response["data"]["tags"] == ["Critical"]
    assert len(db.jobs) == 1
    assert db.jobs[0].tags_json == ["Critical"]
    assert len(db.job_operations) == 3
    assert [op.sequence_number for op in db.job_operations] == [1, 2, 3]
    assert all(op.status == models.OperationStatus.NOT_STARTED for op in db.job_operations)
    assert len(db.custom_field_values) == 1
    assert db.custom_field_values[0].value_text == "EN24"
    assert len(db.events) == 1
    assert db.events[0].event_type == "JOB_CREATED"
    assert len(db.notifications) == 1
    assert db.notifications[0].type == "HIGH_PRIORITY_JOB"

    print(
        "MASTER_E2E_INTEGRATION_CONTRACT_PASS "
        f"job={response['data']['job_id']} operations={len(db.job_operations)} "
        f"material_grade={db.custom_field_values[0].value_text} tags={db.jobs[0].tags_json}"
    )
