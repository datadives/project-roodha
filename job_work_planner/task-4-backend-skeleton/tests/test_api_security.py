import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import app


def auth_headers(token: str | None = None, tenant_id: str | None = "tenant-123") -> dict[str, str]:
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if tenant_id is not None:
        headers["X-Tenant-ID"] = tenant_id
    return headers


@pytest.mark.asyncio
async def test_users_me_rejects_missing_authorization_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me", headers={"X-Tenant-ID": "tenant-123"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Authorization header missing"


@pytest.mark.asyncio
async def test_users_me_rejects_bearer_null_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me", headers=auth_headers("null"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Bearer token missing"


@pytest.mark.asyncio
async def test_users_me_rejects_bearer_undefined_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me", headers=auth_headers("undefined"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Bearer token missing"


@pytest.mark.asyncio
async def test_cors_preflight_does_not_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/users/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
