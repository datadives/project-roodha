import importlib

from fastapi.testclient import TestClient

from app.database import get_async_db
from app.models import User


TENANT_ID = "tenant-invite-rbac-test"
INVITE_EMAIL_RAW = "New.Supervisor@Example.COM"
INVITE_EMAIL_NORMALIZED = "new.supervisor@example.com"
INVITE_PAYLOAD = {"email": INVITE_EMAIL_RAW, "role": "SUPERVISOR"}
OPERATOR_MACHINE_ID = "11111111-2222-4333-8444-555555555555"
DEV_TOKEN = "roodha-dev-test-123"


class FakeCognito:
    class exceptions:
        class UsernameExistsException(Exception):
            pass

    def __init__(self, calls):
        self.calls = calls

    def admin_create_user(self, **kwargs):
        self.calls.append(("admin_create_user", kwargs))
        return {"User": {"Username": kwargs["Username"]}}

    def admin_add_user_to_group(self, **kwargs):
        self.calls.append(("admin_add_user_to_group", kwargs))

    def admin_get_user(self, **kwargs):
        self.calls.append(("admin_get_user", kwargs))
        return {"Username": kwargs["Username"], "UserAttributes": []}


class InviteFakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, *_args, **_kwargs):
        return None

    def add(self, record):
        self.added.append(record)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def build_invite_client(monkeypatch, fake_db, cognito_calls):
    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("DEV_PASS_TOKEN", DEV_TOKEN)
    monkeypatch.setenv("ENABLE_DEMO_API_STUBS", "false")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-invite-rbac-test")
    monkeypatch.setenv("COGNITO_REGION", "ap-south-1")

    import app.main as main

    importlib.reload(main)
    monkeypatch.setattr(main.auth.boto3, "client", lambda *_args, **_kwargs: FakeCognito(cognito_calls))

    async def override_db():
        yield fake_db

    main.app.dependency_overrides[get_async_db] = override_db
    return TestClient(main.app), main


def invite_headers(role):
    return {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "X-Tenant-ID": TENANT_ID,
        "X-Dev-Role": role,
    }


def test_supervisor_cannot_invite_user_to_tenant(monkeypatch, capsys):
    fake_db = InviteFakeDB()
    cognito_calls = []
    client, main = build_invite_client(monkeypatch, fake_db, cognito_calls)

    response = client.post(
        "/api/users/invite",
        json=INVITE_PAYLOAD,
        headers=invite_headers("SUPERVISOR"),
    )

    print(f"INVITE_RBAC_BLOCK role=SUPERVISOR status={response.status_code}")

    assert response.status_code == 403
    assert cognito_calls == []
    assert fake_db.added == []
    assert fake_db.commits == 0

    captured = capsys.readouterr().out
    assert "INVITE_RBAC_BLOCK role=SUPERVISOR status=403" in captured

    main.app.dependency_overrides.clear()


def test_owner_can_invite_user_and_send_cognito_setup_email(monkeypatch, capsys):
    fake_db = InviteFakeDB()
    cognito_calls = []
    client, main = build_invite_client(monkeypatch, fake_db, cognito_calls)

    response = client.post(
        "/api/users/invite",
        json=INVITE_PAYLOAD,
        headers=invite_headers("OWNER"),
    )

    body = response.json()
    created_user = next((record for record in fake_db.added if isinstance(record, User)), None)
    create_call = next((payload for name, payload in cognito_calls if name == "admin_create_user"), None)
    group_call = next((payload for name, payload in cognito_calls if name == "admin_add_user_to_group"), None)

    print(
        "INVITE_RBAC_ALLOW "
        f"role=OWNER status={response.status_code} "
        f"email={body['data']['email']} tenant={body['data']['tenant_id']} "
        f"delivery={body['data']['delivery_medium']}"
    )

    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Employee invite sent"
    assert body["data"]["email"] == INVITE_EMAIL_NORMALIZED
    assert body["data"]["tenant_id"] == TENANT_ID
    assert body["data"]["role"] == "SUPERVISOR"
    assert body["data"]["delivery_medium"] == "EMAIL"

    assert create_call is not None
    assert create_call["UserPoolId"] == "pool-invite-rbac-test"
    assert create_call["Username"] == INVITE_EMAIL_NORMALIZED
    assert create_call["DesiredDeliveryMediums"] == ["EMAIL"]
    assert {"Name": "custom:tenant_id", "Value": TENANT_ID} in create_call["UserAttributes"]
    assert {"Name": "custom:user_role", "Value": "SUPERVISOR"} in create_call["UserAttributes"]

    assert group_call == {
        "UserPoolId": "pool-invite-rbac-test",
        "Username": INVITE_EMAIL_NORMALIZED,
        "GroupName": "SUPERVISOR",
    }

    assert created_user is not None
    assert created_user.tenant_id == TENANT_ID
    assert created_user.email == INVITE_EMAIL_NORMALIZED
    assert created_user.role == "SUPERVISOR"
    assert fake_db.commits == 1

    captured = capsys.readouterr().out
    assert "INVITE_RBAC_ALLOW role=OWNER status=200" in captured

    main.app.dependency_overrides.clear()


def test_owner_can_invite_operator_with_machine_assignment(monkeypatch, capsys):
    fake_db = InviteFakeDB()
    cognito_calls = []
    client, main = build_invite_client(monkeypatch, fake_db, cognito_calls)

    response = client.post(
        "/api/users/invite",
        json={
            "name": "Ravi Operator",
            "email": "Ravi.Operator@Example.COM",
            "role": "OPERATOR",
            "machine_id": OPERATOR_MACHINE_ID,
        },
        headers=invite_headers("OWNER"),
    )

    body = response.json()
    created_user = next((record for record in fake_db.added if isinstance(record, User)), None)
    create_call = next((payload for name, payload in cognito_calls if name == "admin_create_user"), None)
    group_call = next((payload for name, payload in cognito_calls if name == "admin_add_user_to_group"), None)

    print(
        "INVITE_OPERATOR_ALLOW "
        f"role=OWNER status={response.status_code} "
        f"email={body['data']['email']} machine_id={body['data']['machine_id']}"
    )

    assert response.status_code == 200
    assert body["success"] is True
    assert body["message"] == "Employee invite sent"
    assert body["data"]["email"] == "ravi.operator@example.com"
    assert body["data"]["role"] == "OPERATOR"
    assert body["data"]["machine_id"] == OPERATOR_MACHINE_ID

    assert create_call is not None
    assert create_call["DesiredDeliveryMediums"] == ["EMAIL"]
    assert {"Name": "custom:tenant_id", "Value": TENANT_ID} in create_call["UserAttributes"]
    assert {"Name": "custom:user_role", "Value": "OPERATOR"} in create_call["UserAttributes"]
    assert {"Name": "custom:machine_id", "Value": OPERATOR_MACHINE_ID} in create_call["UserAttributes"]
    assert {"Name": "name", "Value": "Ravi Operator"} in create_call["UserAttributes"]

    assert group_call == {
        "UserPoolId": "pool-invite-rbac-test",
        "Username": "ravi.operator@example.com",
        "GroupName": "OPERATOR",
    }

    assert created_user is not None
    assert created_user.tenant_id == TENANT_ID
    assert created_user.email == "ravi.operator@example.com"
    assert created_user.role == "OPERATOR"
    assert fake_db.commits == 1

    captured = capsys.readouterr().out
    assert "INVITE_OPERATOR_ALLOW role=OWNER status=200" in captured

    main.app.dependency_overrides.clear()
