import importlib

from fastapi.testclient import TestClient


S3_ORIGIN = "http://roodha-build-src-918172959197.s3-website.ap-south-1.amazonaws.com"


def test_cors_headers(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", S3_ORIGIN)

    import app.main as main

    importlib.reload(main)
    client = TestClient(main.app)
    response = client.options(
        "/api/users/me",
        headers={
            "Origin": S3_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-tenant-id",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == S3_ORIGIN
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed_headers
    assert "x-tenant-id" in allowed_headers
