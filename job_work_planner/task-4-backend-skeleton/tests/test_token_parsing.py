from app.core.auth_middleware import _identity_fields_from_claims


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

