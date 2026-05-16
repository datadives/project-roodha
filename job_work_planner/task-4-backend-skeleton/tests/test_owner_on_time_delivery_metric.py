import importlib

from fastapi.testclient import TestClient

from app.database import get_async_db


TENANT_ID = "tenant-owner-on-time-metric-test"
DEV_TOKEN = "roodha-dev-test-123"


class FakeDB:
    pass


def build_metrics_client(monkeypatch):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("DEV_PASS_TOKEN", DEV_TOKEN)
    monkeypatch.setenv("ENABLE_DEMO_API_STUBS", "false")

    import app.main as main

    importlib.reload(main)

    fake_db = FakeDB()

    async def override_db():
        yield fake_db

    async def fake_on_time_service(db, tenant_id):
        assert db is fake_db
        assert tenant_id == TENANT_ID
        return {
            "otd_percentage": 92.5,
            "total_completed": 40,
            "on_time_count": 37,
            "late_count": 3,
        }

    main.metrics.get_on_time_delivery_percentage_service = fake_on_time_service
    main.app.dependency_overrides[get_async_db] = override_db
    return TestClient(main.app), main


def auth_headers(role):
    return {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "X-Tenant-ID": TENANT_ID,
        "X-Dev-Role": role,
    }


def test_owner_can_read_on_time_delivery_metric(monkeypatch, capsys):
    client, main = build_metrics_client(monkeypatch)

    response = client.get("/api/metrics/on-time-delivery", headers=auth_headers("OWNER"))
    body = response.json()

    print(
        "OWNER_OTD_METRIC_ALLOW "
        f"role=OWNER status={response.status_code} otd={body['data']['otd_percentage']}"
    )

    assert response.status_code == 200
    assert body["success"] is True
    assert body["data"] == {
        "otd_percentage": 92.5,
        "total_completed": 40,
        "on_time_count": 37,
        "late_count": 3,
    }
    assert "OWNER_OTD_METRIC_ALLOW role=OWNER status=200" in capsys.readouterr().out

    main.app.dependency_overrides.clear()


def test_operator_cannot_read_on_time_delivery_metric(monkeypatch, capsys):
    client, main = build_metrics_client(monkeypatch)

    response = client.get("/api/metrics/on-time-delivery", headers=auth_headers("OPERATOR"))

    print(f"OWNER_OTD_METRIC_BLOCK role=OPERATOR status={response.status_code}")

    assert response.status_code == 403
    assert "OWNER_OTD_METRIC_BLOCK role=OPERATOR status=403" in capsys.readouterr().out

    main.app.dependency_overrides.clear()
