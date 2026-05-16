from datetime import datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app import models
from app.routes import maintenance


TENANT_ID = "tenant-nightly-notification-test"
JOB_ID = UUID("30000000-0000-4000-8000-000000000001")
MACHINE_ID = UUID("30000000-0000-4000-8000-000000000002")
BOUNDARY_NOW = datetime(2026, 5, 16, 0, 0, 1)
PLANNED_END_AT_UTC_BOUNDARY = datetime(2026, 5, 16, 0, 0, 0)


class FakeScalarList:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


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


class NightlyNotificationDB:
    def __init__(self):
        self.notifications = []
        self.events = []
        self.include_late_job = True
        self.machine_booked_hours = 10.0
        self.job = SimpleNamespace(
            job_id=JOB_ID,
            tenant_id=TENANT_ID,
            job_number="DELAY-UTC-001",
            status=models.JobStatus.IN_PROGRESS,
            due_date=None,
        )
        self.machine = SimpleNamespace(
            machine_id=MACHINE_ID,
            tenant_id=TENANT_ID,
            name="Lathe Boundary",
        )

    def _statement_text(self, statement):
        return str(statement.compile()).lower()

    async def execute(self, statement):
        text = self._statement_text(statement)
        if text.strip().startswith("select tenants.tenant_id"):
            return FakeScalarList([TENANT_ID])

        if "from jobs" in text and "coalesce(job_operations.planned_end_date" in text:
            return FakeScalarList([self.job] if self.include_late_job else [])

        if text.strip().startswith("select notifications.notification_id"):
            for notification in self.notifications:
                if (
                    notification.tenant_id == TENANT_ID
                    and f"notifications.type = :type_1" in text
                    and notification.created_at.date() == BOUNDARY_NOW.date()
                    and (
                        (notification.type == "JOB_DELAY_RISK" and notification.entity_id == str(JOB_ID))
                        or (notification.type == "MACHINE_OVERLOAD" and notification.entity_id == str(MACHINE_ID))
                    )
                ):
                    return FakeScalar(notification.notification_id)
            return FakeScalar(None)

        if text.strip().startswith("select users.email"):
            return FakeScalarList(["owner@example.com", "supervisor@example.com"])

        if "having" in text and "sum" in text:
            if self.machine_booked_hours > 10:
                return FakeRows([(self.machine, self.machine_booked_hours)])
            return FakeRows([])

        raise AssertionError(f"Unhandled fake SQL: {text}")

    def add(self, record):
        if isinstance(record, models.Notification):
            self.notifications.append(record)
        elif isinstance(record, models.Event):
            self.events.append(record)

    async def commit(self):
        return None

    async def refresh(self, record):
        return record


@pytest.mark.asyncio
async def test_eventbridge_nightly_delay_risk_email_and_idempotency(monkeypatch, capsys):
    db = NightlyNotificationDB()
    email_payloads = []

    async def fake_send_email(to_email: str, subject: str, body_text: str, body_html=None):
        email_payloads.append({
            "to": to_email,
            "subject": subject,
            "body": body_text,
            "html": body_html,
        })
        return True

    monkeypatch.setattr(maintenance, "_utcnow_naive", lambda: BOUNDARY_NOW)
    monkeypatch.setattr(maintenance, "send_email", fake_send_email)

    first = await maintenance.trigger_v15_nightly(
        request=SimpleNamespace(),
        is_authorized=True,
        db=db,
    )

    print(
        "NIGHTLY_FIRST "
        f"delay_risks={first.data['delay_risks']} machine_overloads={first.data['machine_overloads']} "
        f"emails_sent={first.data['emails_sent']} notifications={len(db.notifications)}"
    )

    assert first.data["machine_overloads"] == 0
    assert first.data["delay_risks"] == 1
    assert first.data["emails_sent"] == 2
    assert len(db.notifications) == 1
    assert db.notifications[0].type == "JOB_DELAY_RISK"
    assert db.notifications[0].entity_id == str(JOB_ID)
    assert len(email_payloads) == 2
    assert all("DELAY-UTC-001" in payload["subject"] for payload in email_payloads)

    second = await maintenance.trigger_v15_nightly(
        request=SimpleNamespace(),
        is_authorized=True,
        db=db,
    )

    print(
        "NIGHTLY_SECOND "
        f"delay_risks={second.data['delay_risks']} machine_overloads={second.data['machine_overloads']} "
        f"emails_sent={second.data['emails_sent']} duplicates_skipped={second.data['duplicates_skipped']} "
        f"notifications={len(db.notifications)}"
    )

    assert second.data["delay_risks"] == 0
    assert second.data["machine_overloads"] == 0
    assert second.data["emails_sent"] == 0
    assert second.data["duplicates_skipped"] == 1
    assert len(db.notifications) == 1
    assert len(email_payloads) == 2


@pytest.mark.asyncio
async def test_eventbridge_nightly_machine_overload_email_and_event(monkeypatch):
    db = NightlyNotificationDB()
    db.include_late_job = False
    db.machine_booked_hours = 10.25
    email_payloads = []

    async def fake_send_email(to_email: str, subject: str, body_text: str, body_html=None):
        email_payloads.append({
            "to": to_email,
            "subject": subject,
            "body": body_text,
            "html": body_html,
        })
        return True

    monkeypatch.setattr(maintenance, "_utcnow_naive", lambda: BOUNDARY_NOW)
    monkeypatch.setattr(maintenance, "send_email", fake_send_email)

    result = await maintenance.trigger_v15_nightly(
        request=SimpleNamespace(),
        is_authorized=True,
        db=db,
    )

    assert result.data["delay_risks"] == 0
    assert result.data["machine_overloads"] == 1
    assert result.data["emails_sent"] == 2
    assert len(db.notifications) == 1
    assert db.notifications[0].type == "MACHINE_OVERLOAD"
    assert db.notifications[0].entity_id == str(MACHINE_ID)
    assert len(email_payloads) == 2
    assert all("Lathe Boundary" in payload["subject"] for payload in email_payloads)
    assert len(db.events) == 1
    assert db.events[0].event_type == "MACHINE_OVERLOAD"

    second = await maintenance.trigger_v15_nightly(
        request=SimpleNamespace(),
        is_authorized=True,
        db=db,
    )

    print(
        "NIGHTLY_SECOND "
        f"delay_risks={second.data['delay_risks']} machine_overloads={second.data['machine_overloads']} "
        f"emails_sent={second.data['emails_sent']} duplicates_skipped={second.data['duplicates_skipped']} "
        f"notifications={len(db.notifications)}"
    )

    assert second.data["delay_risks"] == 0
    assert second.data["machine_overloads"] == 0
    assert second.data["emails_sent"] == 0
    assert second.data["duplicates_skipped"] == 1
    assert len(db.notifications) == 1
    assert len(email_payloads) == 2
