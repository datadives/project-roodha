from types import SimpleNamespace

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.core import auth_middleware
from app.main import app
from app.routes.planning import select_capacity_machine


def bearer_headers(token: str = "header.payload.signature", tenant_id: str = "tenant-a") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant_id,
    }


@pytest.mark.asyncio
async def test_tenant_isolation_blocks_cross_tenant_header(monkeypatch):
    async def fake_decode_verified_token(_token: str) -> dict:
        return {
            "sub": "owner-1",
            "email": "owner@example.com",
            "tenant_id": "tenant-a",
            "custom:tenant_id": "tenant-a",
            "custom:role": "OWNER",
            "token_use": "id",
        }

    monkeypatch.setattr(auth_middleware, "_decode_verified_token", fake_decode_verified_token)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me", headers=bearer_headers(tenant_id="tenant-b"))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Cross-tenant access attempt blocked"


def test_auto_scheduler_bypasses_machines_already_over_10_hours():
    overloaded = SimpleNamespace(machine_id="machine-overloaded", name="Busy CNC")
    available = SimpleNamespace(machine_id="machine-available", name="Open CNC")

    selected = select_capacity_machine(
        machines=[overloaded, available],
        load_by_machine={
            "machine-overloaded": 11.25,
            "machine-available": 7.5,
        },
    )

    assert selected == available


def test_auto_scheduler_returns_none_when_all_machines_are_overloaded():
    machines = [
        SimpleNamespace(machine_id="machine-a", name="CNC A"),
        SimpleNamespace(machine_id="machine-b", name="CNC B"),
    ]

    selected = select_capacity_machine(
        machines=machines,
        load_by_machine={
            "machine-a": 12.0,
            "machine-b": 10.5,
        },
    )

    assert selected is None
