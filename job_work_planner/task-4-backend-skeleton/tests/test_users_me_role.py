import pytest

from app.routes.auth import get_user_profile


class FakeDB:
    async def scalar(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_users_me_preserves_cognito_owner_role():
    current_user = {
        "user_id": "user-123",
        "tenant_id": "tenant-abc",
        "email": "owner@example.com",
        "role": "OWNER",
        "user_role": "OWNER",
        "userRole": "OWNER",
    }

    response = await get_user_profile(current_user=current_user, db=FakeDB())

    payload = response["data"]["user"]
    assert payload["role"] == "OWNER"
    assert payload["user_role"] == "OWNER"
    assert payload["userRole"] == "OWNER"
