from app.core.auth_middleware import _allow_dev_pass, _identity_fields_from_claims
from app.routes import auth
from app.routes.auth import DevConfirmSignUp, UserInviteRequest
from fastapi import HTTPException
import pytest


def test_dev_pass_is_local_only(monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("ENV", "production")

    assert _allow_dev_pass() is False

    monkeypatch.setenv("ENV", "local")
    assert _allow_dev_pass() is True


def test_identity_fields_require_explicit_tenant_claim():
    claims = {
        "sub": "user-123",
        "email": "owner@example.com",
        "custom:tenant_id": "tenant-a",
        "custom:user_role": "SUPERVISOR",
    }

    identity = _identity_fields_from_claims(claims)

    assert identity["tenant_id"] == "tenant-a"
    assert identity["role"] == "SUPERVISOR"


@pytest.mark.asyncio
async def test_dev_confirm_signup_rejects_production_even_when_flag_enabled(monkeypatch):
    monkeypatch.setenv("ALLOW_DEV_PASS", "true")
    monkeypatch.setenv("ENV", "production")

    with pytest.raises(HTTPException) as exc:
        await auth.dev_confirm_signup(DevConfirmSignUp(email="owner@example.com"), request=None)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_invite_user_adds_cognito_group(monkeypatch):
    calls = []

    class FakeCognito:
        class exceptions:
            class UsernameExistsException(Exception):
                pass

        def admin_create_user(self, **kwargs):
            calls.append(("create", kwargs))
            return {"User": {"Username": kwargs["Username"]}}

        def admin_add_user_to_group(self, **kwargs):
            calls.append(("group", kwargs))

    class FakeDB:
        async def scalar(self, *args, **kwargs):
            return None

        def add(self, value):
            calls.append(("db_add", value))

        async def commit(self):
            calls.append(("commit", {}))

    monkeypatch.setenv("COGNITO_USER_POOL_ID", "pool-123")
    monkeypatch.setattr(auth.boto3, "client", lambda *args, **kwargs: FakeCognito())

    response = await auth.invite_user(
        UserInviteRequest(email="supervisor@example.com", role="SUPERVISOR"),
        owner={"tenant_id": "tenant-a"},
        db=FakeDB(),
    )

    assert response["success"] is True
    assert ("group", {"UserPoolId": "pool-123", "Username": "supervisor@example.com", "GroupName": "SUPERVISOR"}) in calls
