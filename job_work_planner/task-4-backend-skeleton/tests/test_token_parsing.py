from types import SimpleNamespace

import pytest

from app.core import auth_middleware
from app.core.auth_middleware import _identity_fields_from_claims, _user_from_claims


def test_token_parsing_extracts_tenant_and_user_role():
    claims = {
        "sub": "user-123",
        "email": "owner@example.com",
        "custom:tenant_id": "roodha-demo",
        "custom:user_role": "OWNER",
    }

    identity = _identity_fields_from_claims(claims)

    assert identity["tenant_id"] == "roodha-demo"
    assert identity["user_id"] == "user-123"
    assert identity["role"] == "OWNER"
    assert identity["email"] == "owner@example.com"


def test_worker_claim_normalizes_to_operator():
    claims = {
        "sub": "user-456",
        "email": "worker@example.com",
        "custom:tenant_id": "roodha-demo",
        "cognito:groups": ["WORKER"],
    }

    identity = _identity_fields_from_claims(claims)

    assert identity["role"] == "OPERATOR"


@pytest.mark.asyncio
async def test_database_role_wins_over_cognito_claim(monkeypatch):
    calls = {"scalar": 0, "commit": 0}
    db_user = SimpleNamespace(
        user_id="user-789",
        email="operator@example.com",
        role="SUPERVISOR",
    )

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *_args, **_kwargs):
            return None

        async def scalar(self, *_args, **_kwargs):
            calls["scalar"] += 1
            if calls["scalar"] == 1:
                return "TENANT"
            return db_user

        def add(self, _value):
            raise AssertionError("existing users must not be recreated")

        async def commit(self):
            calls["commit"] += 1

    monkeypatch.setattr(auth_middleware, "AsyncSessionLocal", lambda: FakeSession())

    user = await _user_from_claims(
        {
            "sub": "user-789",
            "email": "operator@example.com",
            "custom:tenant_id": "tenant-a",
            "custom:user_role": "OPERATOR",
        }
    )

    assert user["role"] == "SUPERVISOR"
    assert user["userRole"] == "SUPERVISOR"
    assert calls["commit"] == 0
    print("AUTH_DB_ROLE_AUTHORITY claim=OPERATOR db=SUPERVISOR effective=SUPERVISOR")

