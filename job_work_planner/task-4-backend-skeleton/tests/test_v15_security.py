import importlib
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import models
from app.database import get_async_db
from app.routes.worklist import _validate_tenant_resource


TENANT_A = "tenant-a-security-test"
TENANT_B = "tenant-b-security-test"
TENANT_A_MACHINE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_B_MACHINE_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
TENANT_B_MACHINE_NAME = "Tenant B Secret CNC"


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeTenantResourceDB:
    async def execute(self, statement):
        params = getattr(statement.compile(), "params", {})
        if TENANT_A in params.values() and TENANT_A_MACHINE_ID in params.values():
            return FakeScalarResult(TENANT_A_MACHINE_ID)
        return FakeScalarResult(None)


def security_log(method: str, path: str, role: str, tenant: str, status_code: int, detail: str):
    print(
        f"SECURITY_BLOCK method={method} path={path} role={role} "
        f"tenant={tenant} status={status_code} detail={detail}"
    )


@pytest.mark.asyncio
async def test_worklist_rejects_cross_tenant_machine_id_without_leaking_data(capsys):
    db = FakeTenantResourceDB()

    with pytest.raises(HTTPException) as exc:
        await _validate_tenant_resource(
            db=db,
            tenant_id=TENANT_A,
            model=models.Machine,
            id_field_name="machine_id",
            resource_id=TENANT_B_MACHINE_ID,
            label="Machine",
        )

    body = str(exc.value.detail)
    security_log("GET", f"/api/worklist?machine_id={TENANT_B_MACHINE_ID}", "SUPERVISOR", TENANT_A, exc.value.status_code, body)

    assert exc.value.status_code == 404
    assert body == "Machine not found for tenant"
    assert TENANT_B not in body
    assert TENANT_B_MACHINE_NAME not in body
    assert str(TENANT_B_MACHINE_ID) not in body

    captured = capsys.readouterr().out
    assert "SECURITY_BLOCK" in captured
    assert str(TENANT_B_MACHINE_ID) in captured


@pytest.mark.asyncio
async def test_worklist_accepts_same_tenant_machine_id():
    db = FakeTenantResourceDB()

    await _validate_tenant_resource(
        db=db,
        tenant_id=TENANT_A,
        model=models.Machine,
        id_field_name="machine_id",
        resource_id=TENANT_A_MACHINE_ID,
        label="Machine",
    )


def build_dev_client(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("DEV_PASS_TOKEN", "roodha-dev-test-123")
    monkeypatch.setenv("ENABLE_DEMO_API_STUBS", "false")

    import app.main as main

    importlib.reload(main)

    async def fake_db():
        yield SimpleNamespace()

    main.app.dependency_overrides[get_async_db] = fake_db
    return TestClient(main.app), main


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/planning/auto-schedule", {}),
        ("post", "/api/planning/auto-schedule/preview", {"limit": 5}),
        (
            "post",
            "/api/planning/auto-schedule/apply",
            {"suggestions": [{"job_operation_id": str(TENANT_A_MACHINE_ID), "machine_id": str(TENANT_A_MACHINE_ID)}]},
        ),
        ("post", "/api/exports/jobs", {}),
    ],
)
def test_operator_is_blocked_from_v15_planning_and_exports(monkeypatch, capsys, method, path, payload):
    client, main = build_dev_client(monkeypatch)
    response = getattr(client, method)(
        path,
        json=payload,
        headers={
            "Authorization": "Bearer roodha-dev-test-123",
            "X-Tenant-ID": TENANT_A,
            "X-Dev-Role": "OPERATOR",
        },
    )

    detail = response.json().get("detail") or response.json().get("message") or ""
    security_log(method.upper(), path, "OPERATOR", TENANT_A, response.status_code, str(detail))

    assert response.status_code == 403
    assert "unauthorized" in str(detail).lower()

    captured = capsys.readouterr().out
    assert f"path={path}" in captured

    main.app.dependency_overrides.clear()
