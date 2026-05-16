import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import get_async_db


def build_client(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("DEV_PASS_TOKEN", "roodha-dev-test-123")
    monkeypatch.setenv("ENABLE_DEMO_API_STUBS", "false")
    monkeypatch.setenv("INTEGRATION_WEBHOOK_TOKEN", "valid-integration-token")

    import app.main as main

    importlib.reload(main)

    async def fake_db():
        yield SimpleNamespace()

    main.app.dependency_overrides[get_async_db] = fake_db
    return TestClient(main.app), main


def test_integration_webhook_rejects_missing_or_invalid_token(monkeypatch, capsys):
    client, main = build_client(monkeypatch)
    payload = {
        "tenant_id": "tenant-webhook-test",
        "customer_name": "Apex Components",
        "part_number": "PX-100",
        "quantity": 10,
    }

    missing = client.post("/api/integrations/jobs", json=payload)
    invalid = client.post(
        "/api/integrations/jobs",
        json=payload,
        headers={"x-roodha-integration-token": "wrong-token"},
    )

    print(f"WEBHOOK_TOKEN_BLOCK case=missing status={missing.status_code} detail={missing.json().get('detail')}")
    print(f"WEBHOOK_TOKEN_BLOCK case=invalid status={invalid.status_code} detail={invalid.json().get('detail')}")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "Invalid integration token" in missing.json()["detail"]
    assert "Invalid integration token" in invalid.json()["detail"]

    main.app.dependency_overrides.clear()


def test_integration_webhook_rejects_missing_customer_payload_as_400(monkeypatch, capsys):
    client, main = build_client(monkeypatch)
    malformed_payload = {
        "tenant_id": "tenant-webhook-test",
        "part_number": "PX-100",
        "quantity": 10,
        "priority": "HIGH",
    }

    response = client.post(
        "/api/integrations/jobs",
        json=malformed_payload,
        headers={"x-roodha-integration-token": "valid-integration-token"},
    )

    body = response.json()
    detail = body.get("detail", [])
    print(
        "WEBHOOK_PAYLOAD_REJECT "
        f"status={response.status_code} message={body.get('message')} "
        f"missing_fields={[error.get('loc', [])[-1] for error in detail if isinstance(error, dict)]}"
    )

    assert response.status_code == 400
    assert body["success"] is False
    assert body["message"] == "Malformed integration job payload"
    assert any(error.get("loc", [])[-1] == "customer_name" for error in body["detail"])

    main.app.dependency_overrides.clear()
